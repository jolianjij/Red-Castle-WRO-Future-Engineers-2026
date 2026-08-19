#!/usr/bin/env python3
"""
wall_calib.py - calibrate the open challenge's wall-following targets.

Park the car CENTRED between the inner and outer wall, pointing the way it will
drive, and run this. Nothing moves; the motor is never touched.

    python tools/wall_calib.py cw      # car centred, facing clockwise
    python tools/wall_calib.py ccw     # car centred, facing counter-clockwise

It IMPORTS open_challenge.py and calls that file's own capture, crop and
process_hsv. Not a copy of them - the same functions - so the crop, the camera
locks and the wall mask cannot drift apart from what actually drives the car.

Centred is the whole point: when the car is centred the controller should
command ZERO steering. So the target constant IS the density measured here.

It also reports the LEGACY density (the bare v < WALL_VAL_MAX the port shipped
with) beside the current one. The difference is the shadow being rejected.
"""
import sys
import os
import time
import numpy as np
import cv2

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import open_challenge as OPEN          # noqa: E402  (its main() is guarded)

which = (sys.argv[1] if len(sys.argv) > 1 else "cw").lower()
N = int(sys.argv[2]) if len(sys.argv) > 2 else 30

picam2 = OPEN.Setup_Camera()
time.sleep(0.5)

Ls, Rs, legL, legR = [], [], [], []
last_frame = None
last_hsv = None

for _ in range(N):
    raw = OPEN.capture_array(picam2)
    OPEN.raw_frame[:] = raw
    frame = np.empty((120, 320, 3), dtype=np.uint8)
    OPEN.process_frame(OPEN.raw_frame, frame)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    OPEN.process_hsv(hsv)              # the controller's own maths
    Ls.append(OPEN.left_wall)
    Rs.append(OPEN.right_wall)

    # what the un-fixed port would have read, for comparison
    v = hsv[:, :, 2].astype(np.int16)
    leg = v < OPEN.WALL_VAL_MAX
    legL.append(np.count_nonzero(leg[:, :160]) / 12800.0)
    legR.append(np.count_nonzero(leg[:, 160:]) / 12800.0)

    last_frame, last_hsv = frame, hsv

L, R = float(np.mean(Ls)), float(np.mean(Rs))
sdL, sdR = float(np.std(Ls)), float(np.std(Rs))
gL, gR = float(np.mean(legL)), float(np.mean(legR))
GAIN = OPEN.WALL_GAIN

# ---- pictures ----
h = last_hsv[:, :, 0].astype(np.int16)
s = last_hsv[:, :, 1].astype(np.int16)
v = last_hsv[:, :, 2].astype(np.int16)
now = OPEN.wall_mask(h, s, v)
leg = v < OPEN.WALL_VAL_MAX

vis = np.zeros((120, 320, 3), np.uint8)
vis[leg & ~now] = (0, 0, 255)        # red   = counted before, rejected now
vis[now] = (0, 255, 0)               # green = counted as wall now
cv2.line(vis, (160, 0), (160, 119), (255, 255, 255), 1)
cv2.imwrite("wall_calib_mask.png", np.vstack([last_frame, vis]))

print()
print("=" * 68)
print("  WALL CALIBRATION   direction = %s   (%d frames, car CENTRED)"
      % (which.upper(), N))
print("=" * 68)
print()
print("  left_wall   = %.4f   (frame-to-frame spread +/- %.4f)" % (L, sdL))
print("  right_wall  = %.4f   (frame-to-frame spread +/- %.4f)" % (R, sdR))
print()

if OPEN.WALL_SHADOW_REJECT:
    print("  SHADOW REJECTION IS ON. Against the legacy bare v < %d:"
          % OPEN.WALL_VAL_MAX)
    print("      left   %.4f -> %.4f   (%+.1f%% of it was not a solid wall)"
          % (gL, L, -100.0 * (gL - L) / gL if gL else 0.0))
    print("      right  %.4f -> %.4f   (%+.1f%%)"
          % (gR, R, -100.0 * (gR - R) / gR if gR else 0.0))
    print("  Red in wall_calib_mask.png is what the shadow test threw away.")
else:
    print("  SHADOW REJECTION IS OFF - this is the bare v < %d."
          % OPEN.WALL_VAL_MAX)
print()

if L + R < 0.02:
    print("  !! Almost NOTHING reads as wall. Either the walls are out of the")
    print("     crop (CROP_TOP=%d) or the mask is too strict. LOOK at" % OPEN.CROP_TOP)
    print("     wall_calib_mask.png before trusting any number here.")
    print()
elif L + R > 1.5:
    print("  !! Almost EVERYTHING reads as wall - the mask is counting mat.")
    print()

if which.startswith("cw"):
    tgt, cur, name, arm = L, OPEN.CW_TARGET, "CW_TARGET", "LEFT"
    bias = (L - cur) * GAIN
    print("  CW follows the %s wall:  dir = (left_wall - TARGET) * %g"
          % (arm, GAIN))
else:
    tgt, cur, name, arm = R, OPEN.CCW_TARGET, "CCW_TARGET", "RIGHT"
    bias = (cur - R) * GAIN
    print("  CCW follows the %s wall: dir = (TARGET - right_wall) * %g"
          % (arm, GAIN))

print("  Centred here that wall reads %.4f, so for the car to sit still:" % tgt)
print()
print("      %s = %.3f        (the file currently says %.3f)"
      % (name, tgt, cur))
print()
if abs(bias) < 0.5:
    print("  The current value is already right - it would command %+.1f deg"
          % bias)
    print("  with the car centred, which is nothing.")
else:
    print("  The CURRENT value commands %+.1f deg while the car is PERFECTLY"
          % bias)
    print("  CENTRED. That is a constant lean into one wall, every cycle.")
print()
print("  GAIN CHECK (WALL_GAIN = %g, STEER_MAX = %d)" % (GAIN, OPEN.STEER_MAX))
for err in (0.02, 0.05, 0.10, 0.20):
    d = err * GAIN
    tag = "   CLAMPED to %d" % OPEN.STEER_MAX if abs(d) > OPEN.STEER_MAX else ""
    print("      %.0f%% density error -> %+6.1f deg%s" % (err * 100, d, tag))
print("      full %d deg needs a density error of %.3f"
      % (OPEN.STEER_MAX, OPEN.STEER_MAX / GAIN))
print()
print("  Saved wall_calib_mask.png")
print("        top    = what the camera saw")
print("        green  = counted as wall")
print("        red    = dark, but rejected as shadow")
print("=" * 68)
