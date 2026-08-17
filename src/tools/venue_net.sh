#!/bin/bash
# ==========================================================================
# venue_net.sh - switch the Pi to wired-only, as venues that ban wireless want.
#
#   ./tools/venue_net.sh status     what is connected, and can I be reached?
#   ./tools/venue_net.sh wifi-off   turn Wi-Fi AND Bluetooth off
#   ./tools/venue_net.sh wifi-on    turn them back on
#
# wifi-off REFUSES to run unless Ethernet is already working, so you cannot
# accidentally cut off the only way you have of reaching the Pi.
# ==========================================================================

eth_ip() { ip -4 -brief addr show eth0 2>/dev/null | awk '{print $3}' | head -1; }
eth_up() { [ -n "$(eth_ip)" ]; }

status() {
    echo "=== interfaces ==="
    ip -brief addr | grep -vE '^lo '
    echo
    echo "=== radios ==="
    nmcli radio 2>/dev/null
    echo
    echo "=== reachable at ==="
    echo "  hostname : $(hostname).local"
    for a in $(hostname -I); do echo "  address  : $a"; done
    echo
    echo "=== services ==="
    printf "  ssh    : %s\n" "$(systemctl is-active ssh)"
    printf "  vnc    : %s (port 5900)\n" "$(systemctl is-active wayvnc)"
    printf "  mdns   : %s (this is what makes '.local' work)\n" \
        "$(systemctl is-active avahi-daemon)"
    echo
    if eth_up; then
        echo "  Ethernet is UP at $(eth_ip) - safe to turn Wi-Fi off."
    else
        echo "  Ethernet is DOWN. Plug the cable in and wait ~10 s."
        echo "  With a cable straight to a laptop there is no DHCP server, so"
        echo "  the Pi uses its fixed address 192.168.50.1 - set the laptop's"
        echo "  wired adapter to 192.168.50.2 / 255.255.255.0."
    fi
}

case "${1:-status}" in
    status) status ;;
    wifi-off)
        if ! eth_up; then
            echo "REFUSING: Ethernet has no address, so this would cut you off."
            echo "Plug the cable in, run './tools/venue_net.sh status', and try"
            echo "again once it shows an address."
            exit 1
        fi
        echo "Ethernet is up at $(eth_ip) - turning the radios off."
        sudo nmcli radio wifi off
        sudo rfkill block bluetooth 2>/dev/null || true
        echo
        nmcli radio
        echo
        echo "Wi-Fi and Bluetooth are OFF. You are on the cable now."
        echo "To undo:  ./tools/venue_net.sh wifi-on"
        echo "If you ever lose the cable too, plug the Pi into a screen and"
        echo "keyboard and run:  nmcli radio wifi on"
        ;;
    wifi-on)
        sudo nmcli radio wifi on
        sudo rfkill unblock bluetooth 2>/dev/null || true
        sleep 3
        nmcli radio
        echo "Wi-Fi back on."
        ;;
    *) sed -n '3,12p' "$0" | sed 's/^# \?//'; exit 1 ;;
esac
