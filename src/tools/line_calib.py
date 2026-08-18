#!/usr/bin/env python3
"""
line_calib.py - set the line thresholds from a REAL crossing, on this camera.

    python tools/line_calib.py

Park the car so ONE line fills the view the way it would while driving over it,
run this, and it reports the count that line actually produces - and what the
threshold should therefore be. Do it for blue, then for orange, then with the
car on BARE MAT so you can see the false-positive floor.

WHY: the thresholds in the ported files are pixel counts measured on ANOTHER
camera. On bare mat, with their blue saturation floor of 60, ours counted 2538
px against their 1100 threshold - so blue "saw a line" on empty floor, the
direction locked CCW on every run, and a clockwise run then followed the INNER
wall all the way round.
"""
import sys, os, time
import numpy as np, cv2
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

src = open(os.path.join(os.path.dirname(__file__), "..", "open_challenge.py")).read()
ns = {"__name__": "calib"}
exec(compile(src.replace("\nmain()\n", "\n"), "open_challenge.py", "exec"), ns)

ns["Setup_GPIO"]()
cam = ns["Setup_Camera"]()
time.sleep(1.2)
acc = None
for _ in range(10):
    raw = ns["capture_array"](cam)
    fr = np.empty((120, 320, 3), dtype=np.uint8)
    ns["process_frame"](raw, fr)
    h = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV).astype(np.float32)
    acc = h if acc is None else acc + h
    time.sleep(0.04)
cam.close()
hsv = (acc / 10).astype(np.uint8)
H, S, V = [hsv[:, :, k].astype(int) for k in (0, 1, 2)]

print("=" * 62)
print("LINE CALIBRATION - what this view produces (frame is 38400 px)")
print("=" * 62)
for nm in ("blue", "orange"):
    if nm == "blue":
        inr = (H > ns["BLUE_HUE_MIN"]) & (H < ns["BLUE_HUE_MAX"])
        smin, vlo, vhi = ns["BLUE_SAT_MIN"], ns["BLUE_VAL_MIN"], ns["BLUE_VAL_MAX"]
        thr = ns["blue_line_threshould"]
    else:
        inr = (H >= ns["ORANGE_HUE_MIN"]) & (H <= ns["ORANGE_HUE_MAX"])
        smin, vlo, vhi = ns["ORANGE_SAT_MIN"], ns["ORANGE_VAL_MIN"], ns["ORANGE_VAL_MAX"]
        thr = ns["orange_line_threshould"]
    m = inr & (S > smin) & (V > vlo) & (V < vhi)
    n = int(np.count_nonzero(m))
    print("\n  %s : %d px   (threshold %d -> %s)"
          % (nm.upper(), n, thr, "FIRES" if n > thr else "silent"))
    if n:
        nb, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8))
        if nb > 1:
            i = 1 + int(np.argmax(st[1:, 4]))
            x, y, w, hh = st[i][0], st[i][1], st[i][2], st[i][3]
            print("      biggest blob %d px, %dx%d %s"
                  % (st[i][4], w, hh,
                     "WIDE - looks like a line" if w > hh * 2.5 else
                     "NOT line-shaped - probably a false match"))
        print("      its saturation: p05=%d p50=%d p95=%d"
              % tuple(int(np.percentile(S[m], q)) for q in (5, 50, 95)))
    print("      suggested threshold if THIS is a real crossing: %d"
          % max(200, int(n * 0.6)))
    print("      suggested threshold if THIS is bare mat:        %d"
          % max(200, int(n * 2.5)))
print("\n  Run this THREE times: over blue, over orange, and on bare mat.")
print("  Set each threshold between its bare-mat count and its crossing count.")
