#!/usr/bin/env python3
"""
tune_walls.py - re-measure the WALL DENSITY <-> DISTANCE relationship.

    python tools/tune_walls.py            # guided calibration
    python tools/tune_walls.py --live     # live read-out, no calibration
    python tools/tune_walls.py --check 40 # what does 40 cm read right now?

WHY THIS EXISTS
The car never measures distance. It measures DENSITY: the fraction of one half
of the picture that is wall. A nearer wall fills more of the frame, so density
rises as distance falls. Every distance constant in the code is really a
density, and the conversion depends on the camera's height, its angle, the lens
AND the lighting - so it must be re-measured whenever any of those change.

    OUTER_TARGET / LANE_TARGET   the density we drive at   = the racing line
    WALL_EMERGENCY               the density we escape at  = too close

This tool asks you to park the car at a few known distances, fits a straight
line through the measurements, and prints the exact constants to paste in.

HOW TO MEASURE THE DISTANCE
Measure from the SIDE OF THE CAR to the wall, level with the camera mast, with
the car parallel to the wall. Being parallel matters more than being exact: a
car at an angle sees a wedge of wall and reads high.
"""
import argparse
import json
import os
import shutil
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import robot as R           # noqa: E402

FRAMES = 12
DEFAULT_DISTANCES = [25, 40, 55, 70]


def grab(cam, n=FRAMES):
    acc = None
    for _ in range(n):
        _, hsv = R.read_hsv(cam)
        acc = hsv.astype(np.float32) if acc is None else acc + hsv
        time.sleep(0.03)
    return (acc / n).astype(np.uint8)


def centre_box(hsv, frac=0.30):
    h, w = hsv.shape[:2]
    y0, y1 = int(h * (0.5 - frac / 2)), int(h * (0.5 + frac / 2))
    x0, x1 = int(w * (0.5 - frac / 2)), int(w * (0.5 + frac / 2))
    return hsv[y0:y1, x0:x1]


def detector(cam):
    """Re-derive WALL_V_HARD / WALL_V_SOFT / WALL_S_MAX for this venue's light.

    DO THIS FIRST. Every density below is the fraction of the picture the wall
    detector calls 'wall', so if the detector is wrong for the venue's light,
    every distance you calibrate afterwards is wrong too.

    The detector's rule is:
        wall = V < V_HARD                    very dark: definitely a wall
               or (V < V_SOFT and S < S_MAX) dark AND colourless

    So it needs to know three things about THIS room: how dark the wall is, how
    bright the mat is, and how saturated the coloured lines are.
    """
    print("\n" + "=" * 66)
    print("WALL DETECTOR - what counts as a wall in this light")
    print("=" * 66)
    print("Three samples. Fill the MIDDLE of the view with each in turn.\n")

    input("  1/3  the BLACK WALL, close and filling the middle > ")
    wv = centre_box(grab(cam))[:, :, 2].astype(int)
    print(f"       wall  V: p50={int(np.percentile(wv,50))} "
          f"p90={int(np.percentile(wv,90))} p99={int(np.percentile(wv,99))}")

    input("  2/3  the MAT, no wall in the middle at all       > ")
    mv = centre_box(grab(cam))[:, :, 2].astype(int)
    print(f"       mat   V: p01={int(np.percentile(mv,1))} "
          f"p10={int(np.percentile(mv,10))} p50={int(np.percentile(mv,50))}")

    print("  3/3  a COLOURED LINE (blue or orange), filling the middle")
    print("       (press Enter with nothing in view to keep the current S_MAX)")
    input("       > ")
    lb = centre_box(grab(cam))
    line_s = lb[:, :, 1].astype(int)
    line_v = lb[:, :, 2].astype(int)
    dark_line = line_s[line_v < 120]           # the part a wall test could catch
    print(f"       line  S: p05={int(np.percentile(line_s,5))} "
          f"p50={int(np.percentile(line_s,50))}")

    wall_hi = int(np.percentile(wv, 90))
    mat_lo = int(np.percentile(mv, 1))
    print("\n" + "-" * 66)
    if wall_hi >= mat_lo:
        print(f"  ! The wall (up to V={wall_hi}) and the mat (down to V={mat_lo})")
        print("    OVERLAP in brightness. No threshold can separate them here.")
        print("    Add light, or angle the camera down so less ceiling shows.")
        print("    Nothing written.")
        return

    v_soft = (wall_hi + mat_lo) // 2
    v_hard = int(np.percentile(wv, 60))
    v_hard = max(8, min(v_hard, v_soft - 4))
    if len(dark_line):
        s_max = max(30, int(np.percentile(dark_line, 5)) - 15)
    else:
        s_max = R.WALL_S_MAX
        print("  (no dark line sampled - keeping the current S_MAX)")

    print(f"  wall reaches V={wall_hi}, mat starts at V={mat_lo}"
          f"  -> a clear gap of {mat_lo - wall_hi}")
    print(f"\n    WALL_V_HARD = {v_hard}   definitely wall, whatever its colour")
    print(f"    WALL_V_SOFT = {v_soft}   dark AND colourless is also wall")
    print(f"    WALL_S_MAX  = {s_max}   above this it is a coloured line, not wall")

    if input("\n  write these to wall_settings.json? [y/N] ").strip().lower() \
            not in ("y", "yes"):
        print("  not written.")
        return
    if os.path.exists("wall_settings.json"):
        shutil.copy("wall_settings.json", "wall_settings.json.bak")
    with open("wall_settings.json", "w") as f:
        json.dump({"WALL_V_HARD": v_hard, "WALL_V_SOFT": v_soft,
                   "WALL_S_MAX": s_max}, f, indent=2)
    print("  saved wall_settings.json - robot.py picks it up automatically.")
    print("  Now re-run the distance calibration, because the densities have"
          " just changed.")


def read(cam, n=FRAMES):
    """Averaged (left, right, front) densities."""
    L, Rr, F = [], [], []
    for _ in range(n):
        _, hsv = R.read_hsv(cam)
        l, r = R.wall_readings(hsv)
        L.append(l)
        Rr.append(r)
        F.append(R.front_reading(hsv))
        time.sleep(0.03)
    return float(np.mean(L)), float(np.mean(Rr)), float(np.mean(F)), \
        float(np.std(L)), float(np.std(Rr))


def live(cam):
    print("LIVE wall densities. Move the car and watch. Ctrl+C to stop.\n")
    try:
        while True:
            l, r, f, sl, sr = read(cam, 4)
            bar_l = "#" * int(l * 100)
            bar_r = "#" * int(r * 100)
            print(f"  L={l:.4f} R={r:.4f} front={f:.4f}   "
                  f"L|{bar_l:<25}|  R|{bar_r:<25}|")
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nstopped")


def calibrate(cam, side, distances):
    """Park at each distance, measure, fit density = a + b*cm."""
    print("\n" + "=" * 66)
    print(f"CALIBRATION - {side.upper()} wall")
    print("=" * 66)
    print("Park the car PARALLEL to the wall at each distance in turn.")
    print("Measure from the side of the car to the wall, at camera height.")
    print("Enter = measure,  s = skip this distance,  q = finish early\n")

    pts = []
    for cm in distances:
        while True:
            ans = input(f"  place the car {cm:3d} cm from the {side} wall "
                        f"> ").strip().lower()
            if ans == "q":
                cm = None
                break
            if ans == "s":
                break
            l, r, f, sl, sr = read(cam)
            d = l if side == "left" else r
            noise = sl if side == "left" else sr
            print(f"      density = {d:.4f}   (noise +-{noise:.4f}, "
                  f"other side {r if side == 'left' else l:.4f}, "
                  f"front {f:.4f})")
            if noise > 0.01:
                print("      ! noisy - is the car steady and the light stable?")
            if d < 0.005:
                print("      ! almost nothing detected. Is the wall in view, "
                      "and is the black range tuned for this venue?")
                continue
            pts.append((cm, d))
            break
        if cm is None:
            break

    if len(pts) < 2:
        print("\nNeed at least two distances to fit a line. Nothing written.")
        return

    xs = np.array([p[0] for p in pts], dtype=float)
    ys = np.array([p[1] for p in pts], dtype=float)
    b, a = np.polyfit(xs, ys, 1)           # density = a + b*cm  (b is negative)
    resid = ys - (a + b * xs)
    rms = float(np.sqrt(np.mean(resid ** 2)))

    print("\n" + "-" * 66)
    print("  measured:")
    for cm, d in pts:
        fit = a + b * cm
        print(f"    {cm:3.0f} cm -> {d:.4f}   (fit {fit:.4f}, "
              f"off by {d - fit:+.4f})")
    print(f"\n  straight-line fit:  density = {a:.5f} {b:+.6f} * cm")
    print(f"  slope             = {abs(b):.5f} density per cm closer")
    print(f"  fit error (rms)   = {rms:.5f}")
    if rms > 0.008:
        print("  ! the points do not lie on a line. Most likely the car was")
        print("    not parallel at one of them, or a distance was misread.")
    if abs(b) < 0.001:
        print("  ! the density barely changes with distance. The wall may be")
        print("    out of frame, or the black range is not tuned for this light.")
        return

    def at(cm):
        return a + b * cm

    print("\n" + "=" * 66)
    print("  PASTE THESE IN")
    print("=" * 66)
    print("  In BOTH open_challenge.py and obstacle_challenge.py, replace the")
    print("  LANE_TARGET line with this venue's numbers:\n")
    print(f"    LANE_TARGET = {at(40):.4f} - (LANE_DISTANCE_CM - 40.0) "
          f"* {abs(b):.5f}")
    print(f"\n  In config.py:\n")
    print(f"    OUTER_TARGET   = {at(40):.4f}   # the 40 cm driving line")
    print(f"    WALL_EMERGENCY = {at(18):.4f}   # escape at 18 cm")
    print("\n  For reference, this fit says:")
    for cm in (15, 20, 30, 40, 50, 60, 80):
        print(f"    {cm:3d} cm -> {at(cm):.4f}")
    warn = at(18)
    if warn <= at(40):
        print("\n  ! WALL_EMERGENCY came out below the driving line, which "
              "cannot be\n    right - the fit is bad. Re-measure.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detector", action="store_true",
                    help="re-derive what counts as a wall in this light. "
                         "DO THIS FIRST when the venue's lighting differs.")
    ap.add_argument("--live", action="store_true", help="live read-out only")
    ap.add_argument("--check", type=float, metavar="CM",
                    help="report the density at one distance you are already at")
    ap.add_argument("--side", choices=("left", "right"), default="left",
                    help="which wall you are measuring (default left)")
    ap.add_argument("--distances", type=int, nargs="+",
                    default=DEFAULT_DISTANCES,
                    help=f"distances in cm (default {DEFAULT_DISTANCES})")
    args = ap.parse_args()

    cam = R.open_camera()
    time.sleep(0.8)
    try:
        if args.detector:
            detector(cam)
            return
        if args.live:
            live(cam)
            return
        if args.check is not None:
            l, r, f, sl, sr = read(cam)
            d = l if args.side == "left" else r
            print(f"  at {args.check:.0f} cm, the {args.side} wall reads "
                  f"{d:.4f}")
            print(f"  (L={l:.4f} R={r:.4f} front={f:.4f})")
            print(f"  the code currently drives at OUTER_TARGET="
                  f"{R.OUTER_TARGET:.4f} and escapes at "
                  f"WALL_EMERGENCY={R.WALL_EMERGENCY:.4f}")
            return
        print("Has the lighting changed since the last calibration?")
        print("If yes, the wall DETECTOR must be re-derived before any")
        print("distance means anything (tools/tune_walls.py --detector).")
        if input("Run the detector step now? [y/N] ").strip().lower() in ("y", "yes"):
            detector(cam)
        calibrate(cam, args.side, args.distances)
    finally:
        cam.close()


if __name__ == "__main__":
    main()
