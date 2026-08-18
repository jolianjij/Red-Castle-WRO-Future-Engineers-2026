#!/bin/bash
# ==========================================================================
# sync.sh - move code between this laptop and the Pi.
#
#   ./sync.sh push        laptop  ->  Pi   (after editing in VS Code)
#   ./sync.sh pull        Pi      ->  laptop  (grab what you tuned on the Pi)
#   ./sync.sh diff        show what differs, without changing anything
#   ./sync.sh push-safe   run the tests FIRST, only push if they pass
#
# EDIT ON THE LAPTOP, RUN ON THE PI. But you also tune values directly on the
# Pi between runs, so `pull` exists to bring those back before you edit - do
# that FIRST or you will overwrite your own tuning.
# ==========================================================================
set -e
HOST=pi@raspberrypi
REMOTE=wro2026
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILES="robot.py config.py camera.py open_challenge.py obstacle_challenge.py"
DATA="colors.json camera_settings.json servo_center.txt wall_settings.json"

case "${1:-diff}" in
  push)
      # Snapshot the Pi BEFORE overwriting it, so a bad push is one command to
      # undo. This is what makes `./backup.sh undo` able to work at all.
      "$HERE/backup.sh" auto "before-push" 2>/dev/null || true
      for f in $FILES; do
        scp -q "$HERE/src/$f" "$HOST:$REMOTE/$f" && echo "  -> $f"
      done
      scp -q "$HERE"/src/tools/*.py "$HOST:$REMOTE/tools/" && echo "  -> tools/"
      scp -q "$HERE/src/run.sh" "$HERE/src/autostart.sh" "$HOST:$REMOTE/" 2>/dev/null || true
      ssh "$HOST" "cd $REMOTE && chmod +x run.sh autostart.sh tools/*.sh 2>/dev/null" || true
      echo "pushed. NOTE: this OVERWRITES anything you tuned on the Pi."
      ;;
  pull)
      for f in $FILES $DATA; do
        scp -q "$HOST:$REMOTE/$f" "$HERE/src/$f" 2>/dev/null && echo "  <- $f"
      done
      echo "pulled. Your Pi-side tuning is now in src/ - commit it."
      ;;
  diff)
      for f in $FILES; do
        if ! ssh "$HOST" "cat $REMOTE/$f" 2>/dev/null | diff -q - "$HERE/src/$f" >/dev/null; then
          echo "=== $f differs ==="
          ssh "$HOST" "cat $REMOTE/$f" 2>/dev/null | diff - "$HERE/src/$f" \
            | grep -E "^[<>]" | grep -E "=" | head -12
        fi
      done
      echo "(< is the Pi, > is this laptop)"
      ;;
  push-safe)
      echo "running the offline tests first..."
      python "$HERE/src/tools/test_logic.py" >/dev/null || {
          echo "TESTS FAILED - nothing pushed."; exit 1; }
      echo "tests pass."
      "$0" push
      ;;
  *) sed -n '3,12p' "$0" | sed 's/^# \?//'; exit 1 ;;
esac
