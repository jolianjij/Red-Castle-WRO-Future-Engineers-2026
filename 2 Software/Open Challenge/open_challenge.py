#!/usr/bin/env python3
"""
open_challenge.py - WRO 2026 Future Engineers, OPEN challenge.

Logic:
  1. Drive forward, wall-follow the outer wall with a PD controller.
  2. First corner line seen sets the driving direction (orange=CW, blue=CCW).
  3. Count quadrants on each corner line; 12 quadrants = 3 laps.
  4. After 3 laps, coast a moment then stop straight.

Run on the Pi:  python3 open_challenge.py
(keep robot.py, camera.py, colors.json in the same folder / ~/wro2026)
"""
import time

import robot as R

# ---- tunables ----
CRUISE = 100           # base forward speed (100%)                         (TUNE)
FINISH_EXTRA_CYCLES = 60   # keep going a bit after the 12th quadrant, then stop
DEBUG = False          # True -> save the wall mask every ~30 cycles


def main():
    R.setup_hardware()
    R.servo(0)
    cam = R.open_camera()

    laps = R.LapTracker()
    follower = R.WallFollower()

    input("Open Challenge ready. Press Enter to START...")
    R.motor(CRUISE)

    finish_at = None
    n = 0
    try:
        while True:
            n += 1
            proc, hsv = R.read_hsv(cam)

            left, right = R.wall_readings(hsv)
            blue, orange = R.line_counts(hsv)
            laps.update(blue, orange)

            steer = follower.steer(left, right, laps.direction)
            R.servo(steer)
            R.motor(R.cruise_speed(CRUISE, steer))

            # 3 laps done -> arm the finish countdown, then stop
            if laps.quadrant >= 12 and finish_at is None:
                finish_at = n + FINISH_EXTRA_CYCLES
            if finish_at is not None and n >= finish_at:
                break

            if DEBUG and n % 30 == 0:
                import cv2
                cv2.imwrite("dbg_walls.png", R.mask(hsv, "black"))
                print(f"n={n} dir={laps.direction} quad={laps.quadrant} "
                      f"L={left:.2f} R={right:.2f} steer={steer:+.0f}")

        R.motor(0)
        R.servo(0)
        print(f"FINISHED: {laps.quadrant} quadrants in {n} cycles.")
    except KeyboardInterrupt:
        print("interrupted")
    finally:
        R.shutdown()
        cam.close()


if __name__ == "__main__":
    main()
