#!/usr/bin/env python3
"""
outer_test.py - validate the OUTER-WALL controller WITHOUT driving.

The motor is never touched. Move the car by hand and watch what the controller
WOULD command, so the law is proven before it is trusted at speed.

    python tools/outer_test.py           # 40 samples, ~8 s
    python tools/outer_test.py 100       # longer

What to check, holding the car in a straight section:
  * centred, pointing straight  -> steer near 0
  * moved TOWARD the outer wall -> steer AWAY from it (sign flips correctly)
  * moved away from the outer wall -> steer gently back toward it
  * crossing a corner line       -> "TURN" fires for TURN_DURATION_S

Reminder of which wall is 'outer':
    CW  (direction +1) -> LEFT wall
    CCW (direction -1) -> RIGHT wall
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import robot as R

n = int(sys.argv[1]) if len(sys.argv) > 1 else 40

cam = R.open_camera()
time.sleep(0.7)
laps = R.LapTracker()
follower = R.WallFollower()
outer = R.OuterWallFollower()
turner = R.TurnSequencer()

print(__doc__)
print(f"NAV_METHOD={R.NAV_METHOD}  OUTER_TARGET={R.OUTER_TARGET}  "
      f"KP={R.OUTER_KP} KD={R.OUTER_KD}  STEER_MAX={R.STEER_MAX}")
print(f"FORCE_DIRECTION={R.FORCE_DIRECTION}  TURN_DURATION_S={R.TURN_DURATION_S}\n")
print("  left  right  outer  err     steer  mode      dir quad")

try:
    for i in range(n):
        _, hsv = R.read_hsv(cam)
        left, right = R.wall_readings(hsv)
        front = R.front_reading(hsv)
        blue, orange = R.line_counts(hsv)

        q0 = laps.quadrant
        laps.update(blue, orange, left, right, front)
        if laps.quadrant > q0:
            turner.trigger(laps.direction)

        steer, mode = R.navigate(hsv, left, right, laps, follower, outer, turner)

        d = laps.direction
        o = left if d >= 0 else right
        err = (left - R.OUTER_TARGET) if d >= 0 else (R.OUTER_TARGET - right)
        tag = "TURN" if mode == "turn" else mode
        print(f"  {left:5.3f} {right:5.3f}  {o:5.3f} {err:+6.3f} {steer:+7.1f}  "
              f"{tag:9s} {d:+d}  {laps.quadrant}")
        time.sleep(0.2)
finally:
    cam.close()
    print("\n", laps.summary())
    print("\nNothing was driven. If the signs above look right, it is safe to run.")
