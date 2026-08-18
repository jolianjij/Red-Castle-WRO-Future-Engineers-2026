#!/bin/bash
# ==========================================================================
# backup.sh - never lose a working configuration.
#
#   ./backup.sh save "green tuned"   snapshot the PI's state right now
#   ./backup.sh list                 what snapshots exist
#   ./backup.sh show <name>          what is in one
#   ./backup.sh restore <name>       put it back ON THE PI
#   ./backup.sh undo                 undo the last push or restore
#
# A snapshot is the five code files plus every calibration file - the numbers
# that took hours to measure and cannot be re-derived from anything else.
#
# Each one lands in THREE places, because one copy is not a backup:
#     backups/<name>/   here on the laptop
#     a git tag         in the repository history
#     GitHub            pushed, so it survives this laptop dying
#
# restore ALWAYS auto-saves first, so restoring is itself undoable.
# ==========================================================================
set -e
HOST=pi@raspberrypi
REMOTE=wro2026
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR="$HERE/backups"
CODE="robot.py config.py camera.py open_challenge.py obstacle_challenge.py"
CAL="colors.json camera_settings.json servo_center.txt wall_settings.json"

slug() { echo "$1" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9-' | cut -c1-40; }

do_save() {
    label="${1:-snapshot}"
    quiet="${2:-}"
    name="$(date +%Y%m%d-%H%M%S)-$(slug "$label")"
    out="$DIR/$name"
    mkdir -p "$out"
    for f in $CODE $CAL; do
        scp -q "$HOST:$REMOTE/$f" "$out/$f" 2>/dev/null || true
    done
    if [ ! -f "$out/robot.py" ]; then
        echo "COULD NOT REACH THE PI - nothing saved."
        rm -rf "$out"
        return 1
    fi
    # what this snapshot WAS - so `show` is still useful in a month
    {
      echo "label: $label"
      echo "taken: $(date '+%Y-%m-%d %H:%M:%S')"
      echo "from : $HOST:$REMOTE"
      echo
      echo "key values:"
      grep -hE "^(CRUISE|FORCE_DIRECTION|PARK_START|LANE_DISTANCE_CM|GREEN_KP|RED_KP|GREEN_MIN_AREA|RED_MIN_AREA|SIGN_HOLD_S|KICK_ANGLE|STOP_ON_LAPS) " \
           "$out/obstacle_challenge.py" 2>/dev/null | sed 's/#.*//;s/ *$//;s/^/  /'
      grep -hE "^(LINE_FRACTION_ORANGE|LINE_FRACTION_BLUE|WALL_EMERGENCY|OUTER_TARGET|OUTER_KP|STEER_BIAS) " \
           "$out/config.py" 2>/dev/null | sed 's/#.*//;s/ *$//;s/^/  /'
      echo
      echo "colours:"
      tr -d ' \n' < "$out/colors.json" 2>/dev/null
      echo
    } > "$out/WHAT-THIS-IS.txt"
    if [ -z "$quiet" ]; then
        echo "saved  $name"
        sed -n '1,3p' "$out/WHAT-THIS-IS.txt" | sed 's/^/    /'
    fi
    echo "$name" > "$DIR/.last"
    (
      cd "$HERE"
      git add -A backups >/dev/null 2>&1 || true
      git -c user.name="jolianjij" -c user.email="jolianwassof69@gmail.com" \
          commit -q -m "backup: $label" >/dev/null 2>&1 || true
      git tag -f "backup/$name" >/dev/null 2>&1 || true
      git push -q origin master --tags >/dev/null 2>&1 || \
          echo "    (GitHub push failed - it is still saved here on the laptop)"
    )
}

case "${1:-list}" in
  save)
      do_save "${2:-manual}"
      ;;
  auto)
      do_save "${2:-before-push}" quiet || true
      ;;
  list)
      if [ ! -d "$DIR" ]; then
          echo "no snapshots yet.  Take one now:  ./backup.sh save \"working\""
          exit 0
      fi
      echo "=== snapshots, newest first ==="
      for d in $(ls -1r "$DIR" 2>/dev/null | grep -v '^\.'); do
          lbl="$(grep '^label:' "$DIR/$d/WHAT-THIS-IS.txt" 2>/dev/null | cut -d' ' -f2-)"
          printf "  %-44s %s\n" "$d" "$lbl"
      done
      echo
      echo "look inside one :  ./backup.sh show <name>"
      echo "put one back    :  ./backup.sh restore <name>"
      ;;
  show)
      [ -n "$2" ] || { echo "which one?  ./backup.sh list"; exit 1; }
      cat "$DIR/$2/WHAT-THIS-IS.txt"
      ;;
  restore)
      [ -n "$2" ] || { echo "which one?  ./backup.sh list"; exit 1; }
      [ -d "$DIR/$2" ] || { echo "no such snapshot: $2"; exit 1; }
      echo "saving the CURRENT state first, so this restore is itself undoable..."
      do_save "before-restore-of-$2" quiet || true
      for f in $CODE $CAL; do
          if [ -f "$DIR/$2/$f" ]; then
              scp -q "$DIR/$2/$f" "$HOST:$REMOTE/$f" && echo "  -> $f"
          fi
      done
      echo "restored $2 onto the Pi."
      echo "PROVE IT BEFORE DRIVING:"
      echo "  ssh $HOST 'cd $REMOTE && source .venv/bin/activate && python tools/test_logic.py'"
      ;;
  undo)
      last="$(cat "$DIR/.last" 2>/dev/null || true)"
      [ -n "$last" ] || { echo "nothing to undo"; exit 1; }
      echo "undoing by restoring the snapshot taken just before it: $last"
      "$0" restore "$last"
      ;;
  *)
      sed -n '3,10p' "$0" | sed 's/^# \?//'
      exit 1
      ;;
esac
