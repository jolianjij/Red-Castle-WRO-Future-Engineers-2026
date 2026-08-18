#!/bin/bash
# ==========================================================================
# venue_net.sh - laptop <-> Pi over ONE Ethernet cable, no wireless.
#
#   ./tools/venue_net.sh status     is the cable up? can I be reached?
#   ./tools/venue_net.sh wifi-off   turn Wi-Fi AND Bluetooth off
#   ./tools/venue_net.sh wifi-on    turn them back on
#
# THE LAPTOP NEEDS NO SETUP. eth0 runs in NetworkManager "shared" mode, so the
# Pi itself hands the laptop an address over the cable. Leave the laptop's
# wired adapter on "Obtain an IP address automatically" and just plug in.
#
#     Pi      192.168.50.1        (fixed)
#     laptop  192.168.50.10+      (given out by the Pi)
#     reach it at  raspberrypi.local   or   192.168.50.1
#
# wifi-off REFUSES unless the laptop has actually TAKEN an address from us and
# answers a ping. A carrier alone is not enough - a router or an idle port
# raises one too - and turning Wi-Fi off with no real wired path locks you out
# of the robot completely.
# ==========================================================================

IFACE=eth0

# THREE separate things, each weaker than the next one looks:
#   eth_ip    an ADDRESS proves nothing - eth0 keeps its static address while
#             completely unplugged.
#   cable_in  a CARRIER proves a cable exists, but not what is on the far end.
#             A router, a switch, a powered-but-idle port all raise carrier.
#   client_on a LEASE proves a real machine asked us for an address and got
#             one. That is the only evidence that the laptop is actually there
#             and can reach us. This is what wifi-off requires.
LEASES=/var/lib/NetworkManager/dnsmasq-$IFACE.leases

cable_in()  { [ "$(cat /sys/class/net/$IFACE/carrier 2>/dev/null)" = "1" ]; }
eth_ip()    { ip -4 -brief addr show $IFACE 2>/dev/null | awk '{print $3}' | head -1; }
dhcp_up()   { pgrep -f "dnsmasq.*$(eth_ip | cut -d/ -f1)" >/dev/null 2>&1; }
client_ip() { sudo awk '{print $3}' "$LEASES" 2>/dev/null | head -1; }
client_on() { [ -n "$(client_ip)" ]; }
client_alive() {
    ip="$(client_ip)"; [ -n "$ip" ] || return 1
    ping -c1 -W2 "$ip" >/dev/null 2>&1
}

status() {
    echo "=== interfaces ==="
    ip -brief addr | grep -vE '^lo '
    echo
    echo "=== the cable ==="
    if cable_in; then
        echo "  cable          : CONNECTED (carrier up)"
    else
        echo "  cable          : nothing plugged in"
    fi
    echo "  Pi address     : $(eth_ip)"
    if dhcp_up; then
        echo "  address server : running"
    else
        echo "  address server : NOT running - 'sudo nmcli con up \"Wired connection 1\"'"
    fi
    if client_on; then
        if client_alive; then
            echo "  the laptop     : $(client_ip)  ANSWERING  <- this is the proof"
        else
            echo "  the laptop     : $(client_ip)  leased, but NOT answering ping"
        fi
    else
        echo "  the laptop     : nothing has asked us for an address"
    fi
    echo
    echo "=== reach the Pi at ==="
    echo "  raspberrypi.local        (works over the cable via mDNS)"
    echo "  192.168.50.1             (if .local ever fails)"
    echo
    echo "=== services ==="
    printf "  ssh    : %s\n" "$(systemctl is-active ssh)"
    printf "  vnc    : %s   -> raspberrypi.local:5900\n" "$(systemctl is-active wayvnc)"
    printf "  mdns   : %s   (this is what makes .local work)\n" \
        "$(systemctl is-active avahi-daemon)"
    printf "  wifi   : %s\n" "$(nmcli radio wifi 2>/dev/null)"
    echo
    if client_on && client_alive; then
        echo "  The laptop is on the cable and answering - safe to turn Wi-Fi off."
    elif cable_in; then
        echo "  A cable is connected, but nothing has taken an address from us."
        echo "  Carrier alone does NOT mean the laptop is there. Plug the cable"
        echo "  into the LAPTOP, leave its adapter on automatic DHCP, wait ~10 s."
    else
        echo "  Plug the cable in (laptop Ethernet -> Pi Ethernet), wait ~10 s,"
        echo "  then run this again. Leave the laptop on automatic DHCP."
    fi
}

case "${1:-status}" in
    status) status ;;
    wifi-off)
        # The bar is deliberately high. Turning Wi-Fi off with no working wired
        # path locks you out of the robot entirely, and the only recovery is a
        # screen and keyboard. So we demand PROOF the laptop is really there:
        # a DHCP lease it asked us for, and a ping it answers. Carrier alone is
        # NOT enough - a router, a switch or an idle powered port all raise it,
        # and that is exactly how this went wrong once already.
        if ! cable_in; then
            echo "REFUSING: nothing is plugged into $IFACE."
            echo "($IFACE keeps its address while unplugged, so an address"
            echo " alone never means a cable is there.)"
            exit 1
        fi
        if ! dhcp_up; then
            echo "REFUSING: the address server is not running, so the laptop"
            echo "could not get an address even with the cable in. Fix with:"
            echo "  sudo nmcli con up \"Wired connection 1\""
            exit 1
        fi
        if ! client_on; then
            echo "REFUSING: a cable is plugged in, but NOTHING has ever asked"
            echo "us for an address. A carrier only proves something is on the"
            echo "far end - a router, a switch, an idle port all raise it."
            echo
            echo "Plug the cable into the LAPTOP, leave its wired adapter on"
            echo "automatic DHCP, wait ~10 s, then check:"
            echo "  ./tools/venue_net.sh status"
            echo "It must say the laptop is ANSWERING before this will run."
            exit 1
        fi
        if ! client_alive; then
            echo "REFUSING: $(client_ip) took an address but does not answer"
            echo "ping. It may have moved, slept, or be firewalled. Confirm you"
            echo "can reach the Pi over the cable FIRST:"
            echo "  ssh pi@$(eth_ip | cut -d/ -f1)"
            exit 1
        fi
        echo "Laptop $(client_ip) is on the cable and answering."
        sudo nmcli radio wifi off
        sudo rfkill block bluetooth 2>/dev/null || true
        echo
        nmcli radio
        echo
        echo "Wi-Fi and Bluetooth are OFF. You are on the cable now."
        echo "Undo with:  ./tools/venue_net.sh wifi-on"
        echo "If you lose the cable too, plug the Pi into a screen and keyboard"
        echo "and run:  nmcli radio wifi on"
        ;;
    wifi-on)
        sudo nmcli radio wifi on
        sudo rfkill unblock bluetooth 2>/dev/null || true
        sleep 3
        nmcli radio
        echo "Wi-Fi back on."
        ;;
    *) sed -n '3,18p' "$0" | sed 's/^# \?//'; exit 1 ;;
esac
