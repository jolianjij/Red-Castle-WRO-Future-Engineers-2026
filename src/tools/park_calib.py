#!/usr/bin/env python3
"""
park_calib.py - check the purple parking walls and the exit direction.

Put the car IN THE START BOX, exactly as it will start a run, then:

    python tools/park_calib.py            # 15 frames
    python tools/park_calib.py 30

It uses obstacle_challenge.py's OWN capture, crop and process_hsv, so the
numbers are what the car will actually decide on. Nothing moves.

The exit direction is decided by  purple_left > purple_right  :
    more purple on the LEFT  -> the way out is RIGHT -> direction CW  (+1)
    more purple on the RIGHT -> the way out is LEFT  -> direction CCW (-1)
With no purple at all that comparison is False, so the car silently commits
to CCW. This tool exists so that never happens unnoticed.
"""
import sys, os, time
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
os.chdir(os.path.join(HERE, ".."))
import obstacle_challenge as O

N = int(sys.argv[1]) if len(sys.argv) > 1 else 15
cam = O.Setup_Camera(); time.sleep(0.6)

L, R, last = [], [], None
for _ in range(N):
    raw = O.capture_array(cam)
    O.raw_frame[:] = raw
    fr = np.empty((120, 320, 3), np.uint8)
    O.process_frame(O.raw_frame, fr)
    hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
    O.process_hsv(hsv, O.red_mask, O.green_mask, O.purple_mask)
    L.append(O.purple_left); R.append(O.purple_right)
    last = (fr, hsv)

fr, hsv = last
h = hsv[:,:,0].astype(np.int16); s = hsv[:,:,1].astype(np.int16); v = hsv[:,:,2].astype(np.int16)
l, r = float(np.mean(L)), float(np.mean(R))

print()
print("=" * 70)
print("  PARKING EXIT CALIBRATION   %d frames" % N)
print("=" * 70)
print()
print("  purple LEFT  = %7.0f px   (frame spread %.0f - %.0f)" % (l, min(L), max(L)))
print("  purple RIGHT = %7.0f px   (frame spread %.0f - %.0f)" % (r, min(R), max(R)))
print("  total        = %7.0f px" % (l + r))
print()
decision = "CW  (+1), exit to the RIGHT" if l > r else "CCW (-1), exit to the LEFT"
print("  DECISION: %s" % decision)
if l + r < 200:
    print("  !! THAT IS NOT A DECISION. With almost no purple in view the")
    print("     comparison is False and the car falls through to CCW. It")
    print("     cannot see the parking walls from here.")
elif min(l, r) > 0 and max(l, r) / max(1.0, min(l, r)) < 1.5:
    print("  !! THE TWO SIDES ARE TOO CLOSE (ratio %.2f). A few pixels of noise"
          % (max(l, r) / min(l, r)))
    print("     would flip the direction. Move the car so one side clearly wins.")
else:
    print("  margin: the winning side has %.1fx the loser. Comfortable."
          % (max(l, r) / max(1.0, min(l, r))))
print()
print("-" * 70)
print("  IS THE MASK GETTING THE WHOLE WALL?")
print("-" * 70)
conds = {
    "S > %d" % O.PURPLE_SAT_MIN: s > O.PURPLE_SAT_MIN,
    "V > %d" % O.PURPLE_VAL_MIN: v > O.PURPLE_VAL_MIN,
    "V < %d" % O.PURPLE_VAL_MAX: v < O.PURPLE_VAL_MAX,
    "H >= %d" % O.PURPLE_HUE_MIN: h >= O.PURPLE_HUE_MIN,
    "H <= %d" % O.PURPLE_HUE_MAX: h <= O.PURPLE_HUE_MAX,
}
full = np.ones(h.shape, bool)
for c in conds.values(): full &= c
print("  pixels passing all: %d" % full.sum())
print("  pixels that pass every OTHER bound and fail only this one:")
for lbl, c in conds.items():
    o = np.ones(h.shape, bool)
    for l2, c2 in conds.items():
        if l2 != lbl: o &= c2
    lost = int((o & ~c).sum())
    print("      %-10s rejects %6d px%s" % (lbl, lost,
          "   <-- costing you wall" if lost > 200 else ""))

# the wall's own pixels, isolated by hue+saturation alone
wall = (h >= 140) & (h <= 179) & (s > 120)
if wall.sum() > 50:
    print()
    print("  THE WALL ITSELF (H140-179, S>120): %d px" % wall.sum())
    for nm, A in (("H", h), ("S", s), ("V", v)):
        q = np.percentile(A[wall], [1, 5, 50, 95, 99])
        print("      %s  p01=%3d p05=%3d p50=%3d p95=%3d p99=%3d"
              % (nm, q[0], q[1], q[2], q[3], q[4]))
    print("      how many of those each V floor keeps:")
    for f in (10, 20, 30, 40, 50, 60):
        print("         V > %2d  keeps %6d (%3.0f%%)%s"
              % (f, int((wall & (v > f)).sum()),
                 100.0 * (wall & (v > f)).sum() / wall.sum(),
                 "   <-- CURRENT" if f == O.PURPLE_VAL_MIN else ""))

# does RED steal the wall?
red_m = ((s > O.RED_SAT_MIN) & (v > O.RED_VAL_MIN) & (v < O.RED_VAL_MAX) &
         ((h < O.RED_HUE_LO) | (h > O.RED_HUE_HI)))
overlap = int((red_m & wall).sum())
print()
print("  RED claims %d px of the wall (its hue wrap starts at %d, the wall"
      % (overlap, O.RED_HUE_HI))
print("  measures up to H%d). Anything here is wall being called a SIGN."
      % (int(np.percentile(h[wall], 99)) if wall.sum() > 50 else 0))

vis = fr.copy()
vis[full] = (255, 0, 255)
cv2.line(vis, (160, 0), (160, 119), (255, 255, 255), 1)
cv2.imwrite("park_calib.png", np.vstack([fr, vis]))
print()
print("  Saved park_calib.png (magenta = counted as parking wall)")
print("=" * 70)
