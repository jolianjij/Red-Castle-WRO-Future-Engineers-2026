#!/usr/bin/env python3
"""
video_colors.py - open a video, pick a frame, see what every colour matches.

    python tools/video_colors.py run.mp4                 # frame in the middle
    python tools/video_colors.py run.mp4 --frame 250     # one frame by number
    python tools/video_colors.py run.mp4 --time 12.5     # one frame by seconds
    python tools/video_colors.py run.mp4 --every 60      # a sweep through it
    python tools/video_colors.py run.mp4 --worst         # the frame with the
                                                         # most colour overlap
    python tools/video_colors.py frames/*.png            # images work too

WHY THIS EXISTS
Colour tuning fails in a way that looks like a steering bug. A range that is
right on the pillar in your hand can also match the mat, the floor, a shadow or
the wall behind it - and you only find out from the way the car drives. Point
this at a recording of a real run and you see, frame by frame, exactly which
pixels each colour claimed.

WHAT YOU GET
  * a PNG per frame: the original, then EACH colour drawn in its own colour
  * pixel COUNT and PERCENTAGE for every colour
  * the biggest blob of each, its size and shape, because "one wide band"
    versus "many scattered specks" is what tells a line from a false match
  * every OVERLAP between two colours, which is the failure that matters most

It uses the SAME mask() and the SAME colors.json the car uses, so what you see
here is exactly what the car saw.
"""
import argparse
import glob
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import robot as R           # noqa: E402

# what each colour is PAINTED as in the output (BGR), chosen to be obvious
# rather than accurate - magenta and red must not look alike here of all places
PAINT = {
    "blue":    (255, 90, 0),
    "orange":  (0, 150, 255),
    "green":   (0, 255, 0),
    "red":     (0, 0, 255),
    "magenta": (255, 0, 255),
    "black":   (128, 128, 128),
}
ORDER = ["blue", "orange", "green", "red", "magenta"]


def to_proc(frame):
    """Put a video frame through the SAME crop and resize the car uses, so the
    numbers here are the numbers the car would have seen."""
    if frame.shape[0] > R.ROI_TOP + 20:
        frame = frame[R.ROI_TOP:, :, :]
    proc = cv2.resize(frame, (R.PROC_W, R.PROC_H))
    return proc, cv2.cvtColor(proc, cv2.COLOR_BGR2HSV)


def describe(hsv, names):
    """(rows, masks) - a line per colour with count, percent and biggest blob."""
    rows, masks = [], {}
    total = float(hsv.shape[0] * hsv.shape[1])
    for name in names:
        m = R.mask(hsv, name) > 0
        masks[name] = m
        n = int(np.count_nonzero(m))
        pct = 100.0 * n / total
        shape = "-"
        big = 0
        if n:
            nb, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8))
            if nb > 1:
                i = 1 + int(np.argmax(st[1:, 4]))
                x, y, w, h = st[i][0], st[i][1], st[i][2], st[i][3]
                big = int(st[i][4])
                kind = ("TALL" if h > w * 1.2 else
                        "WIDE" if w > h * 2.5 else "blocky")
                shape = "%dx%d %s" % (w, h, kind)
        rows.append((name, n, pct, big, shape))
    return rows, masks


def overlaps(masks):
    out = []
    names = [n for n in masks if n != "black"]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            n = int(np.count_nonzero(masks[a] & masks[b]))
            if n:
                out.append((n, a, b))
    return sorted(out, reverse=True)


def render(proc, masks, names):
    """Original on top, then one panel per colour, then all of them together."""
    panels = [proc]
    for name in names:
        p = proc.copy()
        p[masks[name]] = PAINT.get(name, (255, 255, 255))
        n = int(np.count_nonzero(masks[name]))
        pct = 100.0 * n / float(proc.shape[0] * proc.shape[1])
        cv2.putText(p, "%s  %d px  %.2f%%" % (name, n, pct), (4, 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, PAINT.get(name), 1)
        panels.append(p)
    allp = proc.copy()
    for name in names:                       # last drawn wins where they overlap
        allp[masks[name]] = PAINT.get(name, (255, 255, 255))
    cv2.putText(allp, "ALL", (4, 12), cv2.FONT_HERSHEY_SIMPLEX,
                0.36, (255, 255, 255), 1)
    panels.append(allp)
    return np.vstack(panels)


def report(tag, proc, hsv, names, outdir, quiet=False):
    rows, masks = describe(hsv, names)
    ov = overlaps(masks)
    if not quiet:
        print("\n=== %s ===" % tag)
        print("  %-8s %8s %8s %8s  %s" % ("colour", "pixels", "percent",
                                          "biggest", "shape of biggest"))
        for name, n, pct, big, shape in rows:
            flag = "" if n else "   (nothing)"
            print("  %-8s %8d %7.2f%% %8d  %s%s" % (name, n, pct, big, shape, flag))
        if ov:
            print("  OVERLAPS - two colours claiming the same pixels:")
            for n, a, b in ov:
                print("    %-8s vs %-8s  %d px   <-- one of these is wrong" % (a, b, n))
        else:
            print("  no overlaps - every colour is exclusive here")
    out = os.path.join(outdir, "colors_%s.png" % tag)
    img = render(proc, masks, names)
    scale = 2 if img.shape[0] < 900 else 1
    if scale > 1:
        img = cv2.resize(img, (img.shape[1] * scale, img.shape[0] * scale),
                         interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(out, img)
    return out, sum(n for n, _, _ in ov)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", nargs="+", help="a video file, or image files")
    ap.add_argument("--frame", type=int, help="one frame by number")
    ap.add_argument("--time", type=float, help="one frame by seconds")
    ap.add_argument("--every", type=int, help="sweep: every Nth frame")
    ap.add_argument("--worst", action="store_true",
                    help="find the frame with the most colour overlap")
    ap.add_argument("--colors", nargs="+", default=ORDER,
                    help="which colours (default: all but black)")
    ap.add_argument("--out", default="color_check",
                    help="folder for the PNGs (default color_check/)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    files = []
    for pat in args.source:
        files.extend(sorted(glob.glob(pat)) or [pat])

    print("colours from colors.json, exactly as the car uses them:")
    for c in args.colors:
        print("   %-8s %s" % (c, R.COLORS.get(c)))

    # ---- images ----
    if not files[0].lower().endswith((".mp4", ".avi", ".mov", ".mkv", ".h264")):
        for f in files:
            img = cv2.imread(f)
            if img is None:
                print("  cannot read %s" % f)
                continue
            proc, hsv = to_proc(img)
            out, _ = report(os.path.splitext(os.path.basename(f))[0],
                            proc, hsv, args.colors, args.out)
            print("  saved %s" % out)
        return

    # ---- video ----
    path = files[0]
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print("cannot open %s" % path)
        sys.exit(1)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    print("\n%s : %d frames, %.1f fps, %.1f s" % (path, total, fps, total / fps))

    if args.worst:
        print("\nscanning for the frame where colours overlap most...")
        worst, worst_i = -1, 0
        step = max(1, total // 200)
        for i in range(0, total, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ok, fr = cap.read()
            if not ok:
                break
            _, hsv = to_proc(fr)
            _, masks = describe(hsv, args.colors)
            n = sum(x for x, _, _ in overlaps(masks))
            if n > worst:
                worst, worst_i = n, i
        print("  worst frame is %d (%.2fs) with %d overlapping pixels"
              % (worst_i, worst_i / fps, worst))
        wanted = [worst_i]
    elif args.every:
        wanted = list(range(0, total, args.every))
    elif args.frame is not None:
        wanted = [args.frame]
    elif args.time is not None:
        wanted = [int(args.time * fps)]
    else:
        wanted = [total // 2]

    bad = []
    for i in wanted:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, fr = cap.read()
        if not ok:
            continue
        proc, hsv = to_proc(fr)
        out, ovn = report("f%05d_%.2fs" % (i, i / fps), proc, hsv,
                          args.colors, args.out, quiet=len(wanted) > 6)
        if ovn:
            bad.append((ovn, i))
    cap.release()

    print("\nPNGs in %s/  (original on top, then one panel per colour)" % args.out)
    if len(wanted) > 6:
        if bad:
            print("frames with colour overlap, worst first:")
            for n, i in sorted(bad, reverse=True)[:8]:
                print("   frame %5d (%.2fs)  %d px" % (i, i / fps, n))
            print("look at those first - an overlap means one range is wrong.")
        else:
            print("no colour overlapped another in any frame sampled.")


if __name__ == "__main__":
    main()
