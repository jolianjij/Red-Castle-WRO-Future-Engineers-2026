#!/bin/bash
# ==========================================================================
# run.sh - the program the car runs. CHANGE THE ONE LINE BELOW.
#
# This is what the autostart service launches at boot. The program waits for
# the BUTTON before anything moves, so booting straight into it is safe: power
# on, wait for the light, press the button, the car goes.
#
#   ./run.sh                     run whatever PROGRAM says
#   ./run.sh open_challenge.py   run something else, just this once
# ==========================================================================

PROGRAM="obstacle_challenge.py"        # <<<< CHANGE THIS LINE

# ==========================================================================
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE" || exit 1

[ -n "$1" ] && PROGRAM="$1"            # a command-line argument wins

if [ ! -f "$PROGRAM" ]; then
    echo "run.sh: no such program: $HERE/$PROGRAM" >&2
    echo "available:" >&2
    ls -1 *.py 2>/dev/null | sed 's/^/  /' >&2
    exit 1
fi

if [ -f "$HERE/.venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$HERE/.venv/bin/activate"
else
    echo "run.sh: warning - no .venv here, using the system python" >&2
fi

echo "=================================================="
echo " WRO 2026   $(date '+%Y-%m-%d %H:%M:%S')"
echo " running: $PROGRAM"
echo " press the button to start; press it again to stop"
echo "=================================================="

exec python -u "$PROGRAM"
