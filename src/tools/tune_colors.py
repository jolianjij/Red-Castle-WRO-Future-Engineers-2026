#!/usr/bin/env python3
"""
tune_colors.py - re-tune every colour for the VENUE'S lighting. Headless.

Works over a plain SSH terminal - no display, no VNC. That is deliberate: at a
venue you may not get a working screen, and colour tuning is the one thing that
MUST be redone when the light changes.

    python tools/tune_colors.py            # guided: camera, then every colour
    python tools/tune_colors.py red green  # only these colours
    python tools/tune_colors.py --check    # measure what the CURRENT ranges see
    python tools/tune_colors.py --camera   # only re-lock exposure/white balance

The WALLS are tuned separately, by tools/tune_walls.py - they do not use a
colour range at all. Do the walls after this, because they are measured
through the same white balance.

HOW IT WORKS
You hold each object in the CENTRE of the camera's view and press Enter. The
tool samples the middle box of the frame, throws away anything whose hue is far
from the middle of that box (that is the background creeping in), and builds a
range from the percentiles of what is left. Then it checks every pair of
colours for overlap, because a range that is correct on its own is still wrong
if it also matches the pillar next to it.

The old colors.json is copied to colors.json.bak before anything is written.

ORDER MATTERS. Do the camera step FIRST: every colour is measured through the
white balance, so re-locking it afterwards invalidates the colours you tuned.
"""
import argparse
import json
import os
import shutil
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import robot as R           # noqa: E402

FRAMES = 8               # frames averaged per sample (kills sensor noise)
BOX = 0.30               # centre box as a fraction of width/height
HUE_WINDOW = 18          # keep pixels within this much hue of the box median
MIN_PIXELS = 150         # below this the sample is too small to trust

# Which colours to tune, in a sensible order, with what to point at.
# NOTE: "black" is deliberately NOT here. The wall detector does not use the
# black colour range - it uses WALL_V_HARD/WALL_V_SOFT/WALL_S_MAX, which
# tools/tune_walls.py --detector re-derives. Tuning "black" would look like it
# had retuned the walls while changing nothing that drives the car.
TARGETS = [
    ("blue",    "the BLUE corner line, close and filling the middle"),
    ("orange",  "the ORANGE corner line, close and filling the middle"),
    ("green",   "the GREEN traffic sign"),
    ("red",     "the RED traffic sign"),
    ("magenta", "the MAGENTA parking wall  (skip with 's' if not used)"),
]


# --------------------------------------------------------------------------
def grab(cam, n=FRAMES):
    """Average n frames and return the HSV image."""
    acc = None
    for _ in range(n):
        _, hsv = R.read_hsv(cam)
        acc = hsv.astype(np.float32) if acc is None else acc + hsv
        time.sleep(0.03)
    return (acc / n).astype(np.uint8)


def unwrap(h, centre):
    """Shift hues so a range spanning the 179->0 wrap becomes continuous."""
    h = h.astype(np.int16)
    if centre < 45:
        h = np.where(h > 135, h - 180, h)
    elif centre > 135:
        h = np.where(h < 45, h + 180, h)
    return h


def sample(hsv, name):
    """Measure the object in the centre box. Returns (range, report) or None."""
    h, w = hsv.shape[:2]
    y0, y1 = int(h * (0.5 - BOX / 2)), int(h * (0.5 + BOX / 2))
    x0, x1 = int(w * (0.5 - BOX / 2)), int(w * (0.5 + BOX / 2))
    box = hsv[y0:y1, x0:x1]
    H, S, V = box[:, :, 0], box[:, :, 1], box[:, :, 2]

    # centre of the hue cluster, wrap-aware
    centre = int(np.median(H))
    Hu = unwrap(H, centre)
    centre_u = int(np.median(Hu))
    keep = (np.abs(Hu - centre_u) <= HUE_WINDOW) & (S > 50) & (V > 35)
    n = int(np.count_nonzero(keep))
    if n < MIN_PIXELS:
        return None, (f"only {n} usable pixels in the centre box - move the "
                      f"object closer or add light")

    hs, ss, vs = Hu[keep], S[keep], V[keep]
    h_lo = int(np.percentile(hs, 2)) - 4
    h_hi = int(np.percentile(hs, 98)) + 4
    s_lo = max(30, int(np.percentile(ss, 5)) - 25)
    v_lo = max(20, int(np.percentile(vs, 5)) - 25)
    rng = [h_lo % 180, h_hi % 180, s_lo, 255, v_lo, 255]
    report = (f"{n:5d} px   H {int(np.median(hs)) % 180:3d} "
              f"({h_lo % 180}-{h_hi % 180})   S {int(np.median(ss)):3d}   "
              f"V {int(np.median(vs)):3d}")
    return rng, report


def overlaps(hsv, colors):
    """Every pair of colours that claims the same pixels, worst first."""
    masks = {}
    saved = dict(R.COLORS)
    R.COLORS.update(colors)
    try:
        for k in colors:
            masks[k] = R.mask(hsv, k) > 0
    finally:
        R.COLORS.clear()
        R.COLORS.update(saved)
    out = []
    names = list(colors)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if a == "black" or b == "black":
                continue          # black legitimately shares space with nothing
            n = int(np.count_nonzero(masks[a] & masks[b]))
            if n:
                out.append((n, a, b))
    return sorted(out, reverse=True), {k: int(np.count_nonzero(v))
                                       for k, v in masks.items()}


def separate(colors, a, b):
    """Suggest the single bound that pulls two colours apart."""
    ra, rb = colors.get(a), colors.get(b)
    if not ra or not rb:
        return None
    # saturation is the usual lever: the pillars are vivid, the lines are not
    if ra[2] > rb[2]:
        return f"lower {b}'s S ceiling below {ra[2]} (it is {rb[3]} now)"
    return f"lower {a}'s S ceiling below {rb[2]} (it is {ra[3]} now)"


# --------------------------------------------------------------------------
def tune_camera(cam):
    """Re-lock exposure and white balance for the venue's light."""
    print("\n" + "=" * 64)
    print("STEP 1  CAMERA - lock exposure and white balance to the venue light")
    print("=" * 64)
    print("Point the camera at the MAT, showing a normal mix of what it will")
    print("see while driving (mat, a wall, maybe a line). Do not fill the view")
    print("with one bright or one black thing.")
    input("Press Enter when the view is representative...")

    from picamera2 import Picamera2  # noqa: F401  (already imported by camera.py)
    print("  letting auto-exposure and auto-white-balance settle...")
    cam.set_controls({"AeEnable": True, "AwbEnable": True})
    time.sleep(4.0)
    md = cam.capture_metadata()
    exp = int(md.get("ExposureTime", 9000))
    gain = float(md.get("AnalogueGain", 1.0))
    cg = md.get("ColourGains", (1.9, 2.1))
    cg = (round(float(cg[0]), 3), round(float(cg[1]), 3))
    print(f"  measured: ExposureTime={exp}us  AnalogueGain={gain:.2f}  "
          f"ColourGains={cg}")

    # freeze motion: cap the exposure and let gain make up the difference
    if exp > 12000:
        print(f"  ! {exp}us is slow enough to blur while driving. Capping to "
              f"12000us; if the image is now too dark, add light at the venue.")
        exp = 12000
    cam.set_controls({"AeEnable": False, "ExposureTime": exp,
                      "AnalogueGain": gain, "AwbEnable": False,
                      "ColourGains": cg})
    time.sleep(0.6)

    settings = {"ExposureTime": exp, "AnalogueGain": round(gain, 3),
                "ColourGains": list(cg)}
    if os.path.exists("camera_settings.json"):
        shutil.copy("camera_settings.json", "camera_settings.json.bak")
    with open("camera_settings.json", "w") as f:
        json.dump(settings, f, indent=2)
    print(f"  saved camera_settings.json  (previous kept as .bak)")
    hsv = grab(cam)
    print(f"  scene now: mean V={int(hsv[:, :, 2].mean())} "
          f"blown={100.0*np.count_nonzero(hsv[:, :, 2] > 250)/hsv[:, :, 2].size:.1f}% "
          f"dark={100.0*np.count_nonzero(hsv[:, :, 2] < 25)/hsv[:, :, 2].size:.1f}%")


def check(cam):
    """Report what the CURRENT ranges match right now. Changes nothing."""
    print("\n" + "=" * 64)
    print("CHECK - what the current ranges see in this view")
    print("=" * 64)
    hsv = grab(cam)
    ov, counts = overlaps(hsv, dict(R.COLORS))
    for k in R.COLORS:
        m = R.mask(hsv, k)
        n = int(np.count_nonzero(m))
        loc = ""
        if n:
            ys, xs = np.nonzero(m)
            loc = f"  rows {ys.min()}-{ys.max()} cols {xs.min()}-{xs.max()}"
        print(f"  {k:8s} {str(R.COLORS[k]):32s} {n:6d} px{loc}")
    print("\n  overlaps:")
    if not ov:
        print("    none - every colour is exclusive")
    for n, a, b in ov:
        hint = separate(R.COLORS, a, b)
        print(f"    {a} vs {b}: {n} px  <-- FIX: {hint}")
    return 0 if not ov else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("colors", nargs="*", help="only tune these (default: all)")
    ap.add_argument("--check", action="store_true",
                    help="measure the current ranges, change nothing")
    ap.add_argument("--camera", action="store_true",
                    help="only re-lock exposure/white balance")
    ap.add_argument("--no-camera", action="store_true",
                    help="skip the camera step (colours only)")
    args = ap.parse_args()

    cam = R.open_camera()
    time.sleep(0.8)
    try:
        if args.check:
            sys.exit(check(cam))
        if args.camera:
            tune_camera(cam)
            print("\nNow re-run WITHOUT --camera to tune the colours through it.")
            return
        if not args.colors and not args.no_camera:
            tune_camera(cam)

        wanted = args.colors or [n for n, _ in TARGETS]
        colors = dict(R.COLORS)

        print("\n" + "=" * 64)
        print("STEP 2  COLOURS - one object at a time")
        print("=" * 64)
        print("Fill the MIDDLE of the view with the object, nothing else.")
        print("Enter = sample,  s = skip,  q = stop here and save\n")

        for name in wanted:
            hint = dict(TARGETS).get(name, name)
            while True:
                ans = input(f"  [{name}] point at {hint}\n"
                            f"          Enter/s/q > ").strip().lower()
                if ans == "q":
                    wanted = []
                    break
                if ans == "s":
                    print(f"          skipped, keeping {colors.get(name)}\n")
                    break
                hsv = grab(cam)
                rng, report = sample(hsv, name)
                if rng is None:
                    print(f"          ! {report}\n")
                    continue
                print(f"          {report}")
                print(f"          -> {rng}")
                colors[name] = rng
                m = R.mask(hsv, name) if name in R.COLORS else None
                saved = dict(R.COLORS)
                R.COLORS.update(colors)
                try:
                    n = int(np.count_nonzero(R.mask(hsv, name)))
                finally:
                    R.COLORS.clear()
                    R.COLORS.update(saved)
                print(f"          this range matches {n} px in the whole frame\n")
                break
            if not wanted:
                break

        # ---- separation check ----
        print("=" * 64)
        print("STEP 3  SEPARATION - no colour may claim another's pixels")
        print("=" * 64)
        print("Arrange the view so SEVERAL tuned objects are visible together.")
        input("Press Enter when they are all in view...")
        hsv = grab(cam)
        ov, counts = overlaps(hsv, colors)
        for k, n in counts.items():
            print(f"  {k:8s} {n:6d} px")
        print()
        if not ov:
            print("  no overlaps - every colour is exclusive")
        for n, a, b in ov:
            print(f"  ! {a} vs {b}: {n} px overlap")
            hint = separate(colors, a, b)
            if hint:
                print(f"      fix: {hint}")

        # ---- save ----
        if os.path.exists("colors.json"):
            shutil.copy("colors.json", "colors.json.bak")
        with open("colors.json", "w") as f:
            json.dump(colors, f, indent=2)
        print(f"\nsaved colors.json  (previous kept as colors.json.bak)")
        for k, v in colors.items():
            print(f"  {k:8s} {v}")
        if ov:
            print("\n*** THERE ARE OVERLAPS. Re-tune the colours named above, "
                  "or hand-edit\n    colors.json, then run --check again.")
    finally:
        cam.close()


if __name__ == "__main__":
    main()
