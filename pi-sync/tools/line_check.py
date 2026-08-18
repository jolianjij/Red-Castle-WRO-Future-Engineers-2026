#!/usr/bin/env python3
"""
line_check.py - what is the car ACTUALLY calling a corner line?

    python tools/line_check.py

The corner lines decide the driving direction and count the laps, so a colour
that matches anything else is not a tuning nuisance - it picks the wrong way
round the track and the run is lost. This reports, for the view right now:

  * the blue and orange fractions in the LINE BAND, against their thresholds
  * WHERE those pixels are (rows, columns, how many separate blobs, how big)
  * whether the shape looks like a line at all

and saves line_check.png with the matched pixels painted in, so you can see
what it is looking at. The motor is never touched.

A real corner line is ONE wide, shallow band lying across the mat. Many small
scattered blobs, or a tall blob, is something else - a wall, a shadow, a
reflection, or a pillar.
"""
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import robot as R           # noqa: E402

FRAMES = 10


def describe(band, name, bar):
    """Report what this colour matches inside the line band."""
    m = R.mask(band, name)
    total = int(np.count_nonzero(m))
    frac = total / float(m.size)
    over = frac > bar
    print(f"\n  {name.upper():7s} fraction {frac:.4f}   bar {bar:.3f}   "
          f"{frac/bar:5.2f}x  {'*** OVER ***' if over else 'under'}")
    if not total:
        print("          nothing matched")
        return
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    blobs = sorted((st[i][4], st[i][0], st[i][1], st[i][2], st[i][3])
                   for i in range(1, n))[::-1]
    big = [b for b in blobs if b[0] >= 20]
    print(f"          {total} px in {n-1} blobs ({len(big)} of them >= 20 px)")
    for a, x, y, w, h in big[:4]:
        shape = "WIDE+SHALLOW (line-like)" if w >= 3 * h else (
                "TALL (not a line)" if h > w else "blocky")
        print(f"            {a:5d} px  {w:3d}x{h:-3d} at col {x:3d} row {y:3d}"
              f"   {shape}")
    if len(big) > 4:
        print(f"            ...and {len(big)-4} more")
    if len(big) > 3:
        print("          ! many separate blobs - a real line is ONE band")


def main():
    cam = R.open_camera()
    time.sleep(0.8)
    try:
        acc = None
        proc = None
        for _ in range(FRAMES):
            proc, hsv = R.read_hsv(cam)
            acc = hsv.astype(np.float32) if acc is None else acc + hsv
            time.sleep(0.04)
        hsv = (acc / FRAMES).astype(np.uint8)
    finally:
        cam.close()

    r0 = int(R.PROC_H * (1.0 - R.LINE_ROWS))
    band = hsv[r0:, :, :]

    print("=" * 66)
    print("LINE BAND - what the direction and lap logic is reading")
    print("=" * 66)
    print(f"  the band is rows {r0}-{R.PROC_H} of {R.PROC_H} "
          f"(the bottom {R.LINE_ROWS:.0%}, i.e. the mat)")
    describe(band, "blue", R.LINE_FRACTION_BLUE)
    describe(band, "orange", R.LINE_FRACTION_ORANGE)

    print("\n" + "-" * 66)
    print("  A real corner line is ONE wide shallow band across the mat.")
    print("  Scattered blobs or tall blobs mean the colour is matching")
    print("  something else, and no threshold can fix that - retune the")
    print("  colour instead:  python tools/tune_colors.py blue")

    vis = proc.copy()
    cv2.rectangle(vis, (0, r0), (R.PROC_W - 1, R.PROC_H - 1), (0, 255, 255), 1)
    bm = np.zeros(hsv.shape[:2], bool)
    om = np.zeros(hsv.shape[:2], bool)
    bm[r0:] = R.mask(band, "blue") > 0
    om[r0:] = R.mask(band, "orange") > 0
    vis[bm] = (255, 100, 0)
    vis[om] = (0, 140, 255)
    cv2.imwrite("line_check.png",
                cv2.resize(np.vstack([proc, vis]),
                           (R.PROC_W * 3, R.PROC_H * 6),
                           interpolation=cv2.INTER_NEAREST))
    print("\n  saved line_check.png - blue matches in BLUE, orange in ORANGE,")
    print("  the yellow rectangle is the band that is actually searched.")


if __name__ == "__main__":
    main()
