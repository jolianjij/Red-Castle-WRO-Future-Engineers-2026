#!/usr/bin/env python3
"""
color_count.py - count the pixels of ANY colour, for the surprise challenge.

Two ways to use it.

AS A TOOL, to find the numbers for a colour you have never seen before. Point
the car at the thing and give it a hue range:

    python tools/color_count.py 90 135                 # hue 90..135
    python tools/color_count.py 90 135 --smin 140      # add a saturation floor
    python tools/color_count.py 174 8  --smin 120      # a range that WRAPS
    python tools/color_count.py 90 135 --live          # keep printing

It prints the count, what fraction of the frame that is, the left/right split,
the biggest blob and its shape, and the H/S/V percentiles INSIDE that blob -
which is what you set the thresholds from.

AS A FUNCTION, in the program you write on the day:

    from color_count import grab, color_count, halves, biggest_blob

    frame, hsv = grab(cam)
    n, mask = color_count(hsv, hue=(90, 135), s_min=140, v=(20, 200))
    if n > 800:
        left, right = halves(mask)
        ...

Everything here works on the SAME 320x120 cropped frame the two challenge
programs use, so a threshold measured with this tool transfers straight into
them without rescaling.
"""
import sys
import os
import numpy as np
import cv2

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, os.path.join(_HERE, ".."))

PROC_W, PROC_H = 320, 120
FRAME_PIXELS = PROC_W * PROC_H          # 38400


# ==========================================================================
#  THE FUNCTION
# ==========================================================================
def color_count(hsv, hue, s_min=0, s_max=255, v=(0, 255), clean=0):
    """Count the pixels matching an HSV range. Returns (count, mask).

    hue     (lo, hi) in OpenCV units, 0..179. If lo > hi the range WRAPS
            through 0 - which is what red needs, e.g. (174, 8).
    s_min   saturation floor. This is usually the one that matters: it is
            what separates a coloured object from the grey mat.
    s_max   saturation ceiling, rarely needed.
    v       (min, max) brightness. Keep the floor LOW - objects on this car
            measure far darker than they look; the green cube sits at V=38.
    clean   0 = raw. Any odd number >= 3 runs a morphological OPEN with that
            kernel, which deletes speckle without moving the real edges.

    The mask is a boolean array the same shape as the frame, so you can pass
    it straight to halves() or biggest_blob(), or index the image with it.
    """
    h = hsv[:, :, 0].astype(np.int16)
    s = hsv[:, :, 1].astype(np.int16)
    val = hsv[:, :, 2].astype(np.int16)
    lo, hi = hue
    if lo <= hi:
        hue_ok = (h >= lo) & (h <= hi)
    else:                                     # wraps through 0, e.g. red
        hue_ok = (h >= lo) | (h <= hi)
    m = hue_ok & (s >= s_min) & (s <= s_max) & (val >= v[0]) & (val <= v[1])
    if clean and clean >= 3:
        k = np.ones((clean, clean), np.uint8)
        m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, k) > 0
    return int(m.sum()), m


def halves(mask):
    """(left, right) pixel counts. The frame is split down the middle."""
    return (int(mask[:, :PROC_W // 2].sum()), int(mask[:, PROC_W // 2:].sum()))


def density(mask):
    """(left, right) as FRACTIONS, on the same scale the wall targets use."""
    l, r = halves(mask)
    return l / 12800.0, r / 12800.0


def biggest_blob(mask):
    """Largest connected region: (area, cx, cy, x, y, w, h) or None."""
    n, lab, stats, cent = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), 8)
    if n <= 1:
        return None
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h, a = stats[i]
    return (int(a), int(cent[i][0]), int(cent[i][1]), int(x), int(y),
            int(w), int(h))


def grab(cam, crop_top=None):
    """Capture one frame through the challenge pipeline. Returns (bgr, hsv)."""
    import obstacle_challenge as O
    raw = O.capture_array(cam)
    top = O.CROP_TOP if crop_top is None else crop_top
    crop = raw[top:480, 0:640:2]
    crop = cv2.resize(crop, (PROC_W, PROC_H), interpolation=cv2.INTER_AREA)
    if O.ROTATE_180:
        crop = crop[::-1, ::-1]
    return crop, cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)


def open_camera():
    """Start the camera with the challenge programs' locked settings."""
    import obstacle_challenge as O
    return O.Setup_Camera()


# ==========================================================================
#  THE TOOL
# ==========================================================================
def _report(hsv, frame, hue, s_min, v, clean):
    n, m = color_count(hsv, hue, s_min=s_min, v=v, clean=clean)
    l, r = halves(m)
    print()
    print("  hue %d..%d%s   S >= %d   V %d..%d%s"
          % (hue[0], hue[1], "  (WRAPS through 0)" if hue[0] > hue[1] else "",
             s_min, v[0], v[1], "   clean=%d" % clean if clean else ""))
    print("  count %6d px   %.2f%% of the frame   left %d / right %d"
          % (n, 100.0 * n / FRAME_PIXELS, l, r))
    b = biggest_blob(m)
    if b:
        a, cx, cy, x, y, w, h = b
        shape = ("WIDE - line-like" if w > 2 * h else
                 "TALL - pillar-like" if h > w else "squarish")
        print("  biggest blob %d px at (%d,%d), box %dx%d - %s"
              % (a, cx, cy, w, h, shape))
        blob = np.zeros(m.shape, bool)
        nl, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
        i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        blob = lab == i
        for nm, arr in (("H", hsv[:, :, 0]), ("S", hsv[:, :, 1]),
                        ("V", hsv[:, :, 2])):
            q = np.percentile(arr[blob].astype(int), [1, 5, 50, 95, 99])
            print("      %s in it: p01=%3d p05=%3d p50=%3d p95=%3d p99=%3d"
                  % (nm, q[0], q[1], q[2], q[3], q[4]))
        print("  -> set the floors just OUTSIDE p05/p95, not at p50")
    else:
        print("  nothing matched. Widen the hue, or drop the V floor - things")
        print("  on this car are darker than they look.")
    vis = frame.copy()
    vis[m] = (255, 255, 255)
    cv2.imwrite("color_count.png", np.vstack([frame, vis]))
    return n


def _main():
    args = [a for a in sys.argv[1:]]
    nums = [a for a in args if a.replace("-", "").isdigit()]
    if len(nums) < 2:
        print(__doc__)
        return
    hue = (int(nums[0]), int(nums[1]))
    def opt(name, dflt):
        return int(args[args.index(name) + 1]) if name in args else dflt
    s_min = opt("--smin", 0)
    v = (opt("--vmin", 0), opt("--vmax", 255))
    clean = opt("--clean", 0)
    live = "--live" in args

    import time
    cam = open_camera()
    time.sleep(0.6)
    try:
        while True:
            frame, hsv = grab(cam)
            _report(hsv, frame, hue, s_min, v, clean)
            print("  saved color_count.png (bottom: white = matched)")
            if not live:
                break
            time.sleep(1.0)
    finally:
        cam.close()


if __name__ == "__main__":
    _main()
