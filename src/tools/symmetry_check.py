#!/usr/bin/env python3
"""
symmetry_check.py - is the LEFT reading comparable to the RIGHT one?

    python tools/symmetry_check.py

WHY THIS MATTERS
The Open Challenge follows ONE wall, and which one depends on direction:

    CW  -> follows the LEFT reading      CCW -> follows the RIGHT reading

Both aim at the same number (OUTER_TARGET). So if the left and right halves of
the image do NOT read the same at the same true distance, the car will hold a
DIFFERENT real distance in each direction - and one of them will look like it
is hugging the inner wall. A camera aimed a few degrees off centre is enough to
cause it, and nothing in the control law can correct for it.

THE TEST
Park the car parallel to a wall on its LEFT at some distance, press Enter.
Then turn the car around and park it the SAME distance from a wall on its
RIGHT, press Enter. If the two readings differ, that difference is the
asymmetry, and it is measured in centimetres for you.
"""
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import robot as R           # noqa: E402

FRAMES = 15
SLOPE = 0.00501             # density per cm, measured on this car


def read(cam):
    L, Rr = [], []
    for _ in range(FRAMES):
        _, hsv = R.read_hsv(cam)
        l, r = R.wall_readings(hsv)
        L.append(l)
        Rr.append(r)
        time.sleep(0.03)
    return float(np.mean(L)), float(np.mean(Rr))


def main():
    cam = R.open_camera()
    time.sleep(0.8)
    try:
        print("=" * 64)
        print("LEFT / RIGHT SYMMETRY")
        print("=" * 64)
        cm = input("What distance will you use, in cm? [40] ").strip() or "40"
        print(f"\n1/2  Park the car PARALLEL to a wall on its LEFT, {cm} cm away.")
        input("     Press Enter...")
        l1, r1 = read(cam)
        print(f"     left reads {l1:.4f}   (right {r1:.4f})")

        print(f"\n2/2  Now turn the car around: wall on its RIGHT, {cm} cm away.")
        input("     Press Enter...")
        l2, r2 = read(cam)
        print(f"     right reads {r2:.4f}   (left {l2:.4f})")

        print("\n" + "-" * 64)
        diff = l1 - r2
        print(f"  LEFT at {cm} cm  : {l1:.4f}")
        print(f"  RIGHT at {cm} cm : {r2:.4f}")
        print(f"  difference       : {diff:+.4f}  ({abs(diff) / SLOPE:.1f} cm)")
        print()
        if abs(diff) < 0.008:
            print("  SYMMETRIC. Both halves read the same wall the same way, so")
            print("  CW and CCW will hold the same real distance. If one")
            print("  direction still misbehaves, it is not this.")
        else:
            closer = "LEFT" if diff > 0 else "RIGHT"
            print(f"  ASYMMETRIC by {abs(diff) / SLOPE:.1f} cm. The {closer} half reads")
            print( "  HIGHER at the same true distance, so a target that puts the")
            print( "  car 40 cm out in one direction puts it")
            print(f"  {40 - abs(diff) / SLOPE if closer == 'LEFT' else 40 + abs(diff) / SLOPE:.0f} cm out in the other.")
            print()
            print( "  Most likely the camera is not aimed straight down the centre.")
            print( "  Fix the aim if you can - it is the honest fix. If you cannot,")
            print( "  give each direction its own target in open_challenge.py:")
            print(f"      CW  target {l1:.4f}")
            print(f"      CCW target {r2:.4f}")
    finally:
        cam.close()


if __name__ == "__main__":
    main()
