#!/usr/bin/env python3
"""
sign_calib.py - calibrate pillar detection and the sign-following law.

Park the car facing a GREEN and a RED cube at equal distance and run this.
Nothing moves; the motor is never touched.

    python tools/sign_calib.py            # 15 frames
    python tools/sign_calib.py 30

It uses obstacle_challenge.py's OWN capture, crop, masks and contour filter,
so what it reports is exactly what the car sees.
"""
import sys, os, time
import numpy as np
import cv2

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import obstacle_challenge as O

N = int(sys.argv[1]) if len(sys.argv) > 1 else 15
cam = O.Setup_Camera()
time.sleep(0.6)

acc = {"red": [], "green": []}
last = None
for _ in range(N):
    raw = O.capture_array(cam)
    O.raw_frame[:] = raw
    fr = np.empty((120, 320, 3), np.uint8)
    O.process_frame(O.raw_frame, fr)
    hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
    O.process_hsv(hsv, O.red_mask, O.green_mask, O.purple_mask)
    last = fr
    for name, mask in (("red", O.red_mask), ("green", O.green_mask)):
        cs, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        best = None
        for c in cs:
            a = cv2.contourArea(c)
            if best is None or a > best[0]:
                x, y, w, h = cv2.boundingRect(c)
                m = cv2.moments(c)
                if m['m00'] != 0:
                    best = (a, int(m['m10']/m['m00']), int(m['m01']/m['m00']), w, h)
        if best:
            acc[name].append(best)

print()
print("=" * 72)
print("  SIGN CALIBRATION   %d frames   CROP_TOP=%d" % (N, O.CROP_TOP))
print("=" * 72)

res = {}
for name in ("green", "red"):
    d = acc[name]
    print()
    print("  %s" % name.upper())
    if not d:
        print("    NOT SEEN AT ALL in %d frames." % N)
        print("    Either the cube is out of the crop, or its HSV range is wrong.")
        continue
    A = np.array([r[0] for r in d]); X = np.array([r[1] for r in d])
    Y = np.array([r[2] for r in d]); W = np.array([r[3] for r in d])
    H = np.array([r[4] for r in d])
    a, x, y, w, h = A.mean(), X.mean(), Y.mean(), W.mean(), H.mean()
    res[name] = (a, x, y, w, h)
    print("    seen in %d/%d frames" % (len(d), N))
    print("    area   %6.0f px   (min to be a sign: %d)" % (a, O.PARALELIPIPED_MIN_AREA))
    print("    centre x=%5.1f  y=%5.1f" % (x, y))
    print("    box    %.0f wide x %.0f tall" % (w, h))
    ok_area = a > O.PARALELIPIPED_MIN_AREA
    ok_shape = w < h
    print("    accepted as a sign?  area %s   shape(w<h) %s   -> %s"
          % ("OK" if ok_area else "TOO SMALL",
             "OK" if ok_shape else "REJECTED (wider than tall!)",
             "YES" if (ok_area and ok_shape) else "NO"))
    if not ok_shape:
        print("      !! process_traffic_contours DISCARDS any blob that is not")
        print("         taller than wide. Our crop squashes 320 rows into 120")
        print("         where theirs squashed 240, so an upright pillar comes")
        print("         out %.2fx shorter here than it did for them." % (240/320))
        print("         This alone stops the car reacting to ANY pillar.")

print()
print("-" * 72)
print("  WHAT THE SIGN LAW WOULD DO WITH THESE")
print("-" * 72)
for name in ("green", "red"):
    if name not in res:
        continue
    a, x, y, w, h = res[name]
    dterm = O.SIGN_Y_GAIN * (119 - y)
    for dlabel, dirn in (("CW ", 1), ("CCW", -1)):
        if name == "green":
            near = O.GREEN_NEAR_CW if dirn >= 0 else O.GREEN_NEAR_CCW
            tgt = near + dterm
            Err = -(tgt - x)
        else:
            tgt = O.RED_NEAR - dterm
            Err = (x - tgt)
        d = Err * O.kp
        clamped = max(-O.STEER_MAX, min(O.STEER_MAX, d))
        side = "steer RIGHT" if clamped > 0 else ("steer LEFT " if clamped < 0 else "straight   ")
        want = ("pass LEFT of it  -> want steer LEFT " if name == "green"
                else "pass RIGHT of it -> want steer RIGHT")
        good = (clamped < 0) if name == "green" else (clamped > 0)
        print("  %-5s %s | target x=%7.1f  Err=%+8.1f  dir=%+6.1f -> %s  %s  %s"
              % (name, dlabel, tgt, Err, clamped, side, want,
                 "OK" if good else "<-- WRONG WAY"))
print()
print("  reference: image is 320 wide, 120 tall; x=160 is straight ahead")
if "green" in res and "red" in res:
    ga, gx, gy, _, _ = res["green"]; ra, rx, ry, _, _ = res["red"]
    print()
    print("  the two cubes are at EQUAL distance, so these should agree:")
    print("      y:    green %5.1f   red %5.1f   (differ by %.1f)" % (gy, ry, abs(gy-ry)))
    print("      area: green %5.0f   red %5.0f   (ratio %.2f)" % (ga, ra, ga/ra if ra else 0))
    print("  a big area ratio means one colour's HSV range is clipping the cube.")
    print()
    print("  SUGGESTED AREA GATES from this distance:")
    small = min(ga, ra)
    print("      PARALELIPIPED_MIN_AREA  %4d   (a quarter of the smaller: %.0f)"
          % (max(20, int(small * 0.25)), small))
    print("      SIGN_CLOSE_AREA_*       %4d   (this distance counts as CLOSE"
          % int(small * 0.9))
    print("                                     only if the car is meant to act here)")

vis = last.copy()
for name, mask, col in (("red", O.red_mask, (0,0,255)), ("green", O.green_mask, (0,255,0))):
    cs, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    for c in cs:
        if cv2.contourArea(c) > 20:
            x,y,w,h = cv2.boundingRect(c)
            cv2.rectangle(vis, (x,y), (x+w,y+h), col, 1)
cv2.line(vis, (160,0), (160,119), (255,255,255), 1)
cv2.imwrite("sign_calib.png", np.vstack([last, vis]))
print()
print("  Saved sign_calib.png (top = view, bottom = boxes, white = centre)")
print("=" * 72)
