#!/usr/bin/env python3
"""
line_audit.py - why is a line's pixel count what it is?

Park the car so the line you care about fills the view, then:

    python tools/line_audit.py blue
    python tools/line_audit.py orange
    python tools/line_audit.py            # both

It runs open_challenge.py's OWN capture and crop, then answers three questions
the plain pixel count cannot:

  1. WHERE ARE THE PIXELS GOING? For each bound (hue floor, hue ceiling,
     saturation floor, value floor, value ceiling) it counts the pixels that
     pass every OTHER bound and fail only that one. That is the marginal cost
     of the bound - the pixels it, and it alone, is throwing away. A bound with
     a big number is the one to move; a bound with zero is doing nothing.

  2. WHAT DOES THE LINE ACTUALLY LOOK LIKE? The biggest blob's size, shape and
     H/S/V percentiles, so the thresholds can be set from the line rather than
     from a number that came off somebody else's camera.

  3. HOW MUCH IS THE CROP COSTING? The same frame is measured through their
     original crop (rows 240-480) as well as ours (CROP_TOP). Raising CROP_TOP
     to get the walls in frame squashes the image harder vertically, and a line
     is mostly HORIZONTAL - so it loses pixels in direct proportion. Their
     thresholds were measured on their crop.

Nothing moves. The motor is never touched.
"""
import sys
import os
import time
import numpy as np
import cv2

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import open_challenge as OPEN          # noqa: E402

WANT = [a.lower() for a in sys.argv[1:] if not a.isdigit()] or ["blue", "orange"]
N = next((int(a) for a in sys.argv[1:] if a.isdigit()), 12)

SPEC = {
    "blue": dict(
        hue=(OPEN.BLUE_HUE_MIN, OPEN.BLUE_HUE_MAX),
        sat=OPEN.BLUE_SAT_MIN,
        val=(OPEN.BLUE_VAL_MIN, OPEN.BLUE_VAL_MAX),
        thr=OPEN.blue_line_threshould,
        strict=True),           # blue uses > and < (exclusive) in process_hsv
    "orange": dict(
        hue=(OPEN.ORANGE_HUE_MIN, OPEN.ORANGE_HUE_MAX),
        sat=OPEN.ORANGE_SAT_MIN,
        val=(OPEN.ORANGE_VAL_MIN, OPEN.ORANGE_VAL_MAX),
        thr=OPEN.orange_line_threshould,
        strict=False),          # orange uses >= and <= on hue
}


def crop_at(raw, top):
    c = raw[top:480, 0:640:2]
    c = cv2.resize(c, (320, 120), interpolation=cv2.INTER_AREA)
    if OPEN.ROTATE_180:
        c = c[::-1, ::-1]
    return c


def masks(hsv, sp):
    h = hsv[:, :, 0].astype(np.int16)
    s = hsv[:, :, 1].astype(np.int16)
    v = hsv[:, :, 2].astype(np.int16)
    lo, hi = sp["hue"]
    vlo, vhi = sp["val"]
    if sp["strict"]:
        conds = {"hue >  %d" % lo: h > lo, "hue <  %d" % hi: h < hi}
    else:
        conds = {"hue >= %d" % lo: h >= lo, "hue <= %d" % hi: h <= hi}
    conds["sat >  %d" % sp["sat"]] = s > sp["sat"]
    conds["val >  %d" % vlo] = v > vlo
    conds["val <  %d" % vhi] = v < vhi
    return conds, h, s, v


picam2 = OPEN.Setup_Camera()
time.sleep(0.6)
frames = []
for _ in range(N):
    frames.append(OPEN.capture_array(picam2).copy())
raw = frames[-1]

print()
print("=" * 70)
print("  LINE AUDIT     CROP_TOP=%d   (their original was 240)" % OPEN.CROP_TOP)
print("=" * 70)

for name in WANT:
    if name not in SPEC:
        continue
    sp = SPEC[name]
    frame = crop_at(raw, OPEN.CROP_TOP)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    conds, h, s, v = masks(hsv, sp)

    full = np.ones(h.shape, bool)
    for c in conds.values():
        full &= c
    n = int(full.sum())

    print()
    print("-" * 70)
    print("  %s : %d px   threshold %d  ->  %s"
          % (name.upper(), n, sp["thr"], "FIRES" if n > sp["thr"] else "SILENT"))
    print("-" * 70)

    # 1. marginal cost of each bound
    print("  pixels that pass every OTHER bound and fail only this one:")
    worst = None
    for label, c in conds.items():
        others = np.ones(h.shape, bool)
        for l2, c2 in conds.items():
            if l2 != label:
                others &= c2
        lost = int((others & ~c).sum())
        flag = ""
        if lost > max(50, n * 0.15):
            flag = "   <-- THIS is what is costing you"
            worst = label
        print("      %-14s rejects %6d px%s" % (label, lost, flag))
    if worst is None:
        print("      (no single bound dominates - the pixels are simply not there)")

    # 2. what the line looks like
    m8 = full.astype(np.uint8)
    nlab, lab, stats, _ = cv2.connectedComponentsWithStats(m8, 8)
    if nlab > 1:
        i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        x, y, w, hh, a = stats[i]
        blob = lab == i
        print("  biggest blob %d px  %dx%d at (%d,%d)  %s"
              % (a, w, hh, x, y, "WIDE - looks like a line" if w > 2 * hh
                 else "not line-shaped"))
        for ch, arr in (("H", h), ("S", s), ("V", v)):
            q = np.percentile(arr[blob], [5, 50, 95])
            print("      %s in the blob: p05=%3d p50=%3d p95=%3d"
                  % (ch, q[0], q[1], q[2]))
    else:
        print("  NO BLOB AT ALL - nothing passed the mask.")
        # show what the brightest/most saturated region looks like instead
        print("      whole frame: S p50=%d p95=%d   V p50=%d p95=%d"
              % (np.percentile(s, 50), np.percentile(s, 95),
                 np.percentile(v, 50), np.percentile(v, 95)))

    # 3. what the crop costs
    f2 = crop_at(raw, 240)
    hsv2 = cv2.cvtColor(f2, cv2.COLOR_BGR2HSV)
    c2, _, _, _ = masks(hsv2, sp)
    full2 = np.ones(hsv2.shape[:2], bool)
    for c in c2.values():
        full2 &= c
    n2 = int(full2.sum())
    print("  same frame through THEIR crop (rows 240-480): %d px" % n2)
    if n2:
        print("      our crop keeps %.0f%% of that. Their threshold of %d was"
              % (100.0 * n / n2, sp["thr"]))
        print("      measured on their crop, so the like-for-like number here")
        print("      is about %d." % int(sp["thr"] * n / n2))

    # stability across frames
    counts = []
    for fr in frames:
        hv = cv2.cvtColor(crop_at(fr, OPEN.CROP_TOP), cv2.COLOR_BGR2HSV)
        cc, hh2, _, _ = masks(hv, sp)
        f = np.ones(hh2.shape, bool)
        for c in cc.values():
            f &= c
        counts.append(int(f.sum()))
    print("  across %d frames: min %d  median %d  max %d"
          % (len(counts), min(counts), int(np.median(counts)), max(counts)))
    if min(counts) <= sp["thr"] < max(counts):
        print("      !! THE THRESHOLD SITS INSIDE THAT SPREAD - this line will")
        print("         flicker on and off and be counted more than once.")

cv2.imwrite("line_audit_frame.png", crop_at(raw, OPEN.CROP_TOP))
print()
print("  Saved line_audit_frame.png")
print("=" * 70)
