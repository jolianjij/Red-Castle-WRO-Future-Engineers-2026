#!/usr/bin/env python3
"""
park_check.py - what does the car see from inside the parking lot?

    python tools/park_check.py

Answers the one question that matters before an Obstacle run: from where the
car is standing RIGHT NOW, which way will it decide to leave, and how confident
is that decision? The motor is never touched.

It prints the same numbers ParkingExit uses, says which way it would go, and
saves park_check.png - the frame split down the middle with the magenta it
found highlighted, so you can see whether it is looking at what you think.
"""
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import robot as R                  # noqa: E402
import obstacle_challenge as OBS   # noqa: E402

FRAMES = 12


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

    ml, mr, wl, wr = R.park_readings(hsv)
    half = R.PROC_W // 2

    print("=" * 62)
    print("PARKING LOT - what the car sees from here")
    print("=" * 62)
    print(f"  magenta   LEFT {ml:.4f}   RIGHT {mr:.4f}")
    print(f"  wall      LEFT {wl:.4f}   RIGHT {wr:.4f}   (not used by default)")
    print()

    if max(ml, mr) < OBS.PARK_MIN_MAGENTA:
        print(f"  NOT ENOUGH MAGENTA. The most either side has is "
              f"{max(ml, mr):.4f},")
        print(f"  below the {OBS.PARK_MIN_MAGENTA} floor, so the car would "
              f"REFUSE to guess and")
        print( "  leave the direction to the corner lines instead.")
        print()
        print( "  Either the car is not in the lot, the lot is out of frame, or")
        print( "  magenta needs retuning:  python tools/tune_colors.py magenta")
    else:
        left = ml + (wl if OBS.PARK_USE_WALL else 0.0)
        right = mr + (wr if OBS.PARK_USE_WALL else 0.0)
        direction = 1 if left > right else -1
        margin = (max(left, right) / max(1e-9, min(left, right))
                  if min(left, right) > 0 else float("inf"))
        print(f"  {'LEFT' if left > right else 'RIGHT'} side is more blocked")
        print(f"  -> leave to the {'RIGHT' if direction > 0 else 'LEFT'}")
        print(f"  -> lap direction {'CW (+1)' if direction > 0 else 'CCW (-1)'}")
        print(f"  -> exit steering {direction * OBS.PARK_ANGLE:+.0f} deg "
              f"for {OBS.PARK_TIME_S}s at {OBS.PARK_SPEED}%")
        print()
        if margin < 1.5:
            print(f"  ! MARGIN IS ONLY {margin:.2f}x - the two sides look almost")
            print( "    the same, so this decision is nearly a coin toss. Turn")
            print( "    the car so one magenta wall clearly fills more of one")
            print( "    half, then run this again.")
        else:
            print(f"  margin {margin:.1f}x - a clear decision.")

    # ---- picture of what it matched ----
    vis = proc.copy()
    mag = R.mask(hsv, "magenta") > 0
    vis[mag] = (255, 0, 255)
    cv2.line(vis, (half, 0), (half, R.PROC_H), (0, 255, 255), 1)
    cv2.putText(vis, f"L {ml:.3f}", (6, 14), cv2.FONT_HERSHEY_SIMPLEX,
                0.4, (0, 255, 255), 1)
    cv2.putText(vis, f"R {mr:.3f}", (half + 6, 14), cv2.FONT_HERSHEY_SIMPLEX,
                0.4, (0, 255, 255), 1)
    out = np.vstack([proc, vis])
    cv2.imwrite("park_check.png", cv2.resize(out, (R.PROC_W * 3, R.PROC_H * 6),
                                             interpolation=cv2.INTER_NEAREST))
    print("\n  saved park_check.png  (original on top, magenta highlighted below)")


if __name__ == "__main__":
    main()
