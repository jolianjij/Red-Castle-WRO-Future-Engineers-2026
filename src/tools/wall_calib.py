#!/usr/bin/env python3
"""
wall_calib.py - calibrate the open challenge's wall-following targets.

Park the car CENTRED between the inner and outer wall, pointing the way it will
drive, and run this. It measures left_wall / right_wall through the EXACT same
pipeline open_challenge.py uses - it execs that file's own tunables block, so
the crop, the flip and WALL_VAL_MAX can never drift apart from it.

    python tools/wall_calib.py cw      # car centred, facing clockwise
    python tools/wall_calib.py ccw     # car centred, facing counter-clockwise

Centred is the whole point: when the car is centred the controller should
command ZERO steering. So the target constant IS the density measured here.

Nothing moves. The motor is never touched.
"""
import sys, time, os
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
OPEN_PY = os.path.join(HERE, "..", "open_challenge.py")

# ---- borrow open_challenge.py's own tunables, so they cannot drift apart ----
src = open(OPEN_PY).read()
block = src.split("# TUNABLES", 1)[1].split("OUTPUT = GPIO.OUT", 1)[0]
_L = block.splitlines()[1:]          # drop the rest of the banner line
block = chr(10).join(l for l in _L if not l.startswith("import"))
T = {}
exec(block, T)

CROP_TOP      = T["CROP_TOP"]
ROTATE_180    = T["ROTATE_180"]
WALL_VAL_MAX  = T["WALL_VAL_MAX"]
CAM_FLIP_180  = T["CAM_FLIP_180"]
kp_gain       = 75.0          # their control law's fixed gain

which = (sys.argv[1] if len(sys.argv) > 1 else "cw").lower()
N     = int(sys.argv[2]) if len(sys.argv) > 2 else 30

from picamera2 import Picamera2
from libcamera import Transform

picam2 = Picamera2()
tf = Transform(hflip=1, vflip=1) if CAM_FLIP_180 else Transform()
picam2.configure(picam2.create_preview_configuration(
    main={"format": 'RGB888', "size": (640, 480)}, transform=tf))
picam2.start()
picam2.set_controls({
    "AeEnable": False, "ExposureTime": T["CAM_EXPOSURE_US"],
    "AnalogueGain": T["CAM_GAIN"],
    "AwbEnable": False, "ColourGains": T["CAM_COLOUR_GAINS"],
    "Saturation": T["CAM_SATURATION"], "Contrast": T["CAM_CONTRAST"],
})
time.sleep(1.5)

Ls, Rs = [], []
last_hsv = None
for i in range(N):
    raw = picam2.capture_array()
    crop = raw[CROP_TOP:480, 0:640:2]
    crop = cv2.resize(crop, (320, 120), interpolation=cv2.INTER_AREA)
    if ROTATE_180:
        crop = crop[::-1, ::-1]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    last_hsv, last_crop = hsv, crop
    dark = hsv[:, :, 2] < WALL_VAL_MAX
    Ls.append(np.count_nonzero(dark[:, :160]) / 12800.0)
    Rs.append(np.count_nonzero(dark[:, 160:]) / 12800.0)

L, R = float(np.mean(Ls)), float(np.mean(Rs))
Ls_sd, Rs_sd = float(np.std(Ls)), float(np.std(Rs))

# save what it saw
walls = np.where(last_hsv[:, :, 2] < WALL_VAL_MAX, 255, 0).astype(np.uint8)
vis = cv2.cvtColor(walls, cv2.COLOR_GRAY2BGR)
cv2.line(vis, (160, 0), (160, 119), (0, 0, 255), 1)
cv2.imwrite("wall_calib_mask.png", vis)
cv2.imwrite("wall_calib_frame.png", last_crop)

print()
print("=" * 66)
print("  WALL CALIBRATION   direction = %s   (%d frames, car CENTRED)" % (which.upper(), N))
print("=" * 66)
print()
print("  left_wall   = %.4f   (frame-to-frame spread +/- %.4f)" % (L, Ls_sd))
print("  right_wall  = %.4f   (frame-to-frame spread +/- %.4f)" % (R, Rs_sd))
print("  total dark  = %.4f   of the cropped frame" % ((L + R) / 2.0))
print()

if L + R < 0.02:
    print("  !! Almost NOTHING is dark. Either the walls are out of the crop")
    print("     (raise CROP_TOP) or WALL_VAL_MAX=%d is too strict for this" % WALL_VAL_MAX)
    print("     lighting. Look at wall_calib_mask.png before trusting anything.")
    print()
elif L + R > 1.5:
    print("  !! Almost EVERYTHING is dark. WALL_VAL_MAX=%d is too loose - it is" % WALL_VAL_MAX)
    print("     counting the mat as wall. Look at wall_calib_mask.png.")
    print()

if which.startswith("cw"):
    tgt, cur, want = L, T.get("CW_TARGET", 0.30), "CW_TARGET"
    print("  CW follows the LEFT wall:   dir = (left_wall - TARGET) * %g" % kp_gain)
    print("  Centred here, left_wall is %.4f, so for the car to sit still:" % L)
    print()
    print("      %s = %.3f        (currently %.3f)" % (want, tgt, cur))
    print()
    print("  With the CURRENT %.3f it would command dir = %+.1f deg while" % (cur, (L - cur) * kp_gain))
    print("  perfectly centred - it would steer %s." %
          ("RIGHT, into the outer wall" if (L - cur) > 0 else "LEFT, into the inner wall"))
else:
    tgt, cur, want = R, T.get("CCW_TARGET", 0.40), "CCW_TARGET"
    print("  CCW follows the RIGHT wall: dir = (TARGET - right_wall) * %g" % kp_gain)
    print("  Centred here, right_wall is %.4f, so for the car to sit still:" % R)
    print()
    print("      %s = %.3f        (currently %.3f)" % (want, tgt, cur))
    print()
    print("  With the CURRENT %.3f it would command dir = %+.1f deg while" % (cur, (cur - R) * kp_gain))
    print("  perfectly centred - it would steer %s." %
          ("LEFT" if (cur - R) > 0 else "RIGHT"))

print()
print("  GAIN CHECK (the *75 in their law)")
STEER_MAX = 20
for err in (0.02, 0.05, 0.10, 0.20):
    d = err * kp_gain
    print("      %.0f%% density error -> %+6.1f deg%s" %
          (err * 100, d, "   (CLAMPED to %d)" % STEER_MAX if abs(d) > STEER_MAX else ""))
need = STEER_MAX / kp_gain
print("      full %d deg lock needs a density error of %.3f" % (STEER_MAX, need))
print()
print("  Saved wall_calib_mask.png (white = counted as wall, red = centre)")
print("        wall_calib_frame.png (what the camera actually saw)")
print("=" * 66)
