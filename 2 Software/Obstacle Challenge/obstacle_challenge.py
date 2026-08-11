#!/usr/bin/env python3
"""
obstacle_challenge.py - WRO 2026 Future Engineers, OBSTACLE challenge.

Logic (priority order each frame):
  1. WALL EMERGENCY - if either wall is dangerously close, hard-steer away.
     (Never crash into a wall, even while dodging a pillar.)
  2. PARK (after 3 laps) - hunt the magenta parking gate, aim at it, stop when close.
  3. PILLAR - if a red/green pillar is near, pass it:
        red  -> pass on the RIGHT (keep pillar to our left)
        green-> pass on the LEFT  (keep pillar to our right)
  4. WALL-FOLLOW - otherwise, PD outer-wall following (same as open challenge).

Direction (orange=CW / blue=CCW) and 12-quadrant lap counting are identical to
the open challenge.

Run on the Pi:  python3 obstacle_challenge.py
(keep robot.py, camera.py, colors.json in the same folder / ~/wro2026)
"""
import time

import robot as R

# ---- tunables ----
CRUISE = 100           # base speed (100%)                                       (TUNE)
PILLAR_SPEED = 42      # speed while actively passing a pillar                    (TUNE)
PARK_SPEED = 30        # speed while parking                                      (TUNE)
KP_PARK = 90.0
DEBUG = False


def main():
    R.setup_hardware()
    R.servo(0)
    cam = R.open_camera()

    laps = R.LapTracker()
    follower = R.WallFollower()

    input("Obstacle Challenge ready. Press Enter to START...")
    R.motor(CRUISE)

    n = 0
    try:
        while True:
            n += 1
            proc, hsv = R.read_hsv(cam)

            left, right = R.wall_readings(hsv)
            blue, orange = R.line_counts(hsv)
            laps.update(blue, orange)

            steer = 0.0
            speed = CRUISE
            mode = "follow"

            # ---- 2. PARK (after 3 laps) ----
            if laps.quadrant >= 12:
                mode = "park"
                area, mcx = R.magenta_area(hsv)
                speed = PARK_SPEED
                if area > 0:
                    steer = KP_PARK * ((mcx - R.PROC_W / 2) / R.PROC_W)
                    steer = max(-R.STEER_MAX, min(R.STEER_MAX, steer))
                    if area > R.PARK_STOP_AREA:      # close enough -> parked
                        R.motor(0); R.servo(0)
                        print("PARKED.")
                        break
                else:
                    steer = follower.steer(left, right, laps.direction)

            # ---- 1. WALL EMERGENCY ----
            elif left > R.WALL_EMERGENCY:
                steer = R.STEER_MAX; mode = "wall!"
            elif right > R.WALL_EMERGENCY:
                steer = -R.STEER_MAX; mode = "wall!"

            else:
                # ---- 3. PILLAR ----
                pil = R.find_pillars(hsv)
                if pil is not None:
                    color, cx, cy, aarea = pil
                    steer = R.pillar_steer(color, cx, cy)
                    speed = PILLAR_SPEED
                    mode = "pass-" + color
                else:
                    # ---- 4. WALL-FOLLOW ----
                    steer = follower.steer(left, right, laps.direction)

            R.servo(steer)
            R.motor(R.cruise_speed(speed, steer))

            if DEBUG and n % 30 == 0:
                print(f"n={n} dir={laps.direction} quad={laps.quadrant} "
                      f"L={left:.2f} R={right:.2f} {mode} steer={steer:+.0f}")

        print(f"FINISHED obstacle: {laps.quadrant} quadrants, {n} cycles.")
    except KeyboardInterrupt:
        print("interrupted")
    finally:
        R.shutdown()
        cam.close()


if __name__ == "__main__":
    main()
