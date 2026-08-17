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
# wifi-off REFUSES unless the cable is PHYSICALLY connected, so you cannot cut
# off the only way you have of reaching the robot.
# ==========================================================================

IFACE=eth0

# A configured address is NOT proof of a link: eth0 keeps its static address
# while unplugged. Only the carrier tells you a cable is really there.
cable_in()  { [ "$(cat /sys/class/net/$IFACE/carrier 2>/dev/null)" = "1" ]; }
eth_ip()    { ip -4 -brief addr show $IFACE 2>/dev/null | awk '{print $3}' | head -1; }
dhcp_up()   { pgrep -f "dnsmasq.*$(eth_ip | cut -d/ -f1)" >/dev/null 2>&1; }

status() {
    echo "=== interfaces ==="
    ip -brief addr | grep -vE '^lo '
    echo
    echo "=== the cable ==="
    if cable_in; then
        echo "  CONNECTED   $IFACE carrier is up"
    else
        echo "  NOT CONNECTED   nothing plugged into $IFACE"
    fi
    echo "  Pi address        : $(eth_ip)"
    if dhcp_up; then
        echo "  address server    : running (the laptop gets 192.168.50.10+)"
    else
        echo "  address server    : NOT running - run 'sudo nmcli con up \"Wired connection 1\"'"
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
    if cable_in; then
        echo "  Cable is live - safe to turn Wi-Fi off."
    else
        echo "  Plug the cable in (laptop Ethernet -> Pi Ethernet), wait ~5 s,"
        echo "  then run this again. Leave the laptop on automatic DHCP."
    fi
}

case "${1:-status}" in
    status) status ;;
    wifi-off)
        if ! cable_in; then
            echo "REFUSING: nothing is plugged into $IFACE, so this would cut"
            echo "you off completely. ($IFACE keeps its address while unplugged,"
            echo "so an address alone does not mean a cable is there.)"
            echo
            echo "Plug in, run './tools/venue_net.sh status', and try again"
            echo "once it says CONNECTED."
            exit 1
        fi
        if ! dhcp_up; then
            echo "WARNING: the address server is not running, so the laptop may"
            echo "not get an address. Fix that before disabling Wi-Fi:"
            echo "  sudo nmcli con up \"Wired connection 1\""
            exit 1
        fi
        echo "Cable is live at $(eth_ip) - turning the radios off."
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
