#!/bin/bash
# ==========================================================================
# autostart.sh - make the car run its program automatically at power-on.
#
#   ./autostart.sh on       start at boot from now on
#   ./autostart.sh off      stop starting at boot
#   ./autostart.sh status   is it on? did the last run work?
#   ./autostart.sh log      watch the running program's output live
#   ./autostart.sh start    start it right now (without rebooting)
#   ./autostart.sh stop     stop it right now
#
# WHY THIS IS SAFE: the program waits for the BUTTON before it moves. Booting
# into it just means the car is armed and waiting, not driving.
#
# Which program runs is set by the PROGRAM line in run.sh - edit that, then
# ./autostart.sh restart  (or just power-cycle the car).
# ==========================================================================
set -e

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT=/etc/systemd/system/wro.service
USER_NAME="$(id -un)"

write_unit() {
    sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=WRO 2026 Future Engineers - challenge program
# the camera needs udev to have settled, or picamera2 fails to open it
After=multi-user.target systemd-udev-settle.service
Wants=systemd-udev-settle.service

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$HERE
ExecStart=$HERE/run.sh
# a finished run exits; restarting re-arms it so the next press of the button
# starts another run. It never drives on its own - it waits for the button.
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal
SyslogIdentifier=wro

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
}

case "${1:-status}" in
    on)
        chmod +x "$HERE/run.sh"
        write_unit
        sudo systemctl enable wro.service
        sudo systemctl restart wro.service
        echo "autostart ON  - running '$(grep -m1 '^PROGRAM=' "$HERE/run.sh" \
              | cut -d'"' -f2)' at every boot"
        echo "watch it with:  ./autostart.sh log"
        ;;
    off)
        sudo systemctl disable --now wro.service 2>/dev/null || true
        echo "autostart OFF - the car will not run anything at boot"
        ;;
    start)   write_unit; sudo systemctl start wro.service; echo "started" ;;
    stop)    sudo systemctl stop wro.service; echo "stopped" ;;
    restart) write_unit; sudo systemctl restart wro.service; echo "restarted" ;;
    log)     journalctl -u wro.service -f -n 40 ;;
    status)
        echo "program in run.sh : $(grep -m1 '^PROGRAM=' "$HERE/run.sh" \
              | cut -d'"' -f2)"
        if systemctl is-enabled wro.service >/dev/null 2>&1; then
            echo "autostart        : ON"
        else
            echo "autostart        : OFF"
        fi
        echo "right now        : $(systemctl is-active wro.service 2>/dev/null)"
        echo
        systemctl status wro.service --no-pager -n 15 2>/dev/null || \
            echo "(service not installed yet - run './autostart.sh on')"
        ;;
    *)
        sed -n '3,16p' "$0" | sed 's/^# \?//'
        exit 1
        ;;
esac
