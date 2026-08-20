#!/usr/bin/env python3
"""
color_count.py - pixel count for ANY HSV range, through the car's own pipeline.

Two ways to use it.

AS A FUNCTION, from your own code (the surprise challenge):

    import sys; sys.path.insert(0, "tools")
    from color_count import color_count, grab

    hsv = grab(picam2)                       # crop + HSV, same as the car
    n = color_count(hsv, h=(35, 85), s=(120, 255), v=(40, 255))
    left, right = color_count_halves(hsv, h=(35, 85), s=(120, 255), v=(40, 255))

AS A TOOL, to measure a colour on the field:

    python tools/color_count.py 35 85 120 255 40 255
    python tools/color_count.py 35 85 120 255 40 255 --name lime --frames 10

It uses open_challenge.py's crop and camera settings, so a number measured here
means the same thing as a number inside the programs. A count taken with a
different crop is NOT comparable - see other/color-tuning-strategy.md.

HUE WRAP is handled: if h_lo > h_hi the range wraps through 0, the way red does
(e.g. h=(175, 10) means 175..179 plus 0..10).
"""
import sys
import os

import numpy as np
import cv2

_HERE = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------
# the function - no camera needed, works on any HSV image
# --------------------------------------------------------------------------
def color_mask(hsv, h=(0, 179), s=(0, 255), v=(0, 255)):
    """Boolean mask for an HSV range. Bounds are INCLUSIVE.

    hsv : an HSV image, as cv2.cvtColor(frame, cv2.COLOR_BGR2HSV) gives
    h,s,v : (low, high) pairs. If h[0] > h[1] the hue range WRAPS through 0.
    """
    H = hsv[:, :, 0].astype(np.int16)
    S = hsv[:, :, 1].astype(np.int16)
    V = hsv[:, :, 2].astype(np.int16)
    if h[0] <= h[1]:
        hue_ok = (H >= h[0]) & (H <= h[1])
    else:                                   # wraps through 0, like red
        hue_ok = (H >= h[0]) | (H <= h[1])
    return hue_ok & (S >= s[0]) & (S <= s[1]) & (V >= v[0]) & (V <= v[1])


def color_count(hsv, h=(0, 179), s=(0, 255), v=(0, 255)):
    """How many pixels fall in this HSV range."""
    return int(np.count_nonzero(color_mask(hsv, h, s, v)))


def color_count_halves(hsv, h=(0, 179), s=(0, 255), v=(0, 255)):
    """(left, right) counts, split down the middle of the frame.

    This is the shape the wall and parking-lot decisions use: which side has
    more of the colour.
    """
    m = color_mask(hsv, h, s, v)
    mid = m.shape[1] // 2
    return int(np.count_nonzero(m[:, :mid])), int(np.count_nonzero(m[:, mid:]))


def color_blob(hsv, h=(0, 179), s=(0, 255), v=(0, 255)):
    """The BIGGEST connected blob: (area, cx, cy, w, hgt) or None.

    A pixel count alone cannot tell a solid object from scattered speckle.
    This can: a real line is wide and short, a real pillar is taller than wide,
    and noise is neither.
    """
    m = color_mask(hsv, h, s, v).astype(np.uint8)
    n, lab, stats, cent = cv2.connectedComponentsWithStats(m, 8)
    if n <= 1:
        return None
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, hgt, area = stats[i]
    return (int(area), int(cent[i][0]), int(cent[i][1]), int(w), int(hgt))


# --------------------------------------------------------------------------
# grabbing a frame the same way the car does
# --------------------------------------------------------------------------
def grab(picam2, prog=None):
    """Capture one frame and return it as HSV, cropped exactly like the car.

    prog : the already-imported challenge module to borrow the crop from.
           Defaults to open_challenge.
    """
    if prog is None:
        prog = _load_prog()
    raw = prog.capture_array(picam2)
    prog.raw_frame[:] = raw
    frame = np.empty((120, 320, 3), dtype=np.uint8)
    prog.process_frame(prog.raw_frame, frame)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2HSV), frame


def _load_prog():
    sys.path.insert(0, os.path.join(_HERE, ".."))
    import open_challenge as prog            # its main() is guarded
    return prog


# --------------------------------------------------------------------------
# command line
# --------------------------------------------------------------------------
def _main(argv):
    nums, name, frames = [], "colour", 8
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--name":
            i += 1; name = argv[i]
        elif a == "--frames":
            i += 1; frames = int(argv[i])
        else:
            nums.append(int(a))
        i += 1
    if len(nums) != 6:
        print(__doc__)
        print("  need six numbers: h_lo h_hi s_lo s_hi v_lo v_hi")
        return 2
    h = (nums[0], nums[1]); s = (nums[2], nums[3]); v = (nums[4], nums[5])

    prog = _load_prog()
    os.chdir(os.path.join(_HERE, ".."))
    picam2 = prog.Setup_Camera()

    counts, lefts, rights, last = [], [], [], None
    for _ in range(frames):
        hsv, frame = grab(picam2, prog)
        counts.append(color_count(hsv, h, s, v))
        l, r = color_count_halves(hsv, h, s, v)
        lefts.append(l); rights.append(r)
        last = (hsv, frame)

    hsv, frame = last
    total = hsv.shape[0] * hsv.shape[1]
    c = np.array(counts)

    print()
    print("=" * 66)
    print("  COLOUR COUNT   %s   H %d-%d  S %d-%d  V %d-%d%s"
          % (name, h[0], h[1], s[0], s[1], v[0], v[1],
             "   (hue WRAPS through 0)" if h[0] > h[1] else ""))
    print("=" * 66)
    print("  pixels   mean %5.0f   min %5d   max %5d   of %d (%.1f%% of frame)"
          % (c.mean(), c.min(), c.max(), total, 100.0 * c.mean() / total))
    print("  halves   left %5.0f   right %5.0f"
          % (np.mean(lefts), np.mean(rights)))
    blob = color_blob(hsv, h, s, v)
    if blob:
        area, cx, cy, w, hh = blob
        shape = ("WIDE - line-like" if w > 2 * hh else
                 ("TALL - pillar-like" if hh > w else "square-ish"))
        print("  biggest blob %5d px  %dx%d at (%d,%d)  %s"
              % (area, w, hh, cx, cy, shape))
        m = color_mask(hsv, h, s, v)
        for ch, idx in (("H", 0), ("S", 1), ("V", 2)):
            q = np.percentile(hsv[:, :, idx][m], [1, 5, 50, 95, 99])
            print("      %s in the mask: p01=%3d p05=%3d p50=%3d p95=%3d p99=%3d"
                  % (ch, q[0], q[1], q[2], q[3], q[4]))
    else:
        print("  no blob at all - nothing matched")
    print()
    print("  A COUNT ALONE IS NOT A THRESHOLD. Measure this colour with the")
    print("  object in view AND with it out of view - the gap between those")
    print("  two is what makes a threshold safe. See")
    print("  other/color-tuning-strategy.md")

    vis = frame.copy()
    vis[color_mask(hsv, h, s, v)] = (0, 255, 255)
    cv2.imwrite("color_count_%s.png" % name, np.vstack([frame, vis]))
    print()
    print("  Saved color_count_%s.png (yellow = matched)" % name)
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
