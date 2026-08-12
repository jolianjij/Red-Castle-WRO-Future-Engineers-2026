#!/usr/bin/env python3
"""
obstacle_challenge.py - WRO 2026 Obstacle Challenge.

STRUCTURE IS KYIVROBOMAGIC'S, READ FROM THEIR SOURCE (obstacle_challenge_3.cpp).
Their control block, in order, is:

    dir = Err * kp                      # PILLAR steering is the PRIMARY control
    if outer wall too close: dir = +-45 # wall override (this also turns corners)
    lines -> driving direction and quadrant count

ONE DELIBERATE DEPARTURE. Their design has no lane keeping: with no sign in view
Err = 0 and the car drives STRAIGHT, relying on the wall override to fire often
enough to stay in the corridor. That holds on their optics but not ours - measured
L=0.112 R=0.129 against our 0.213 override threshold, so 44% of a run was
steer = 0 and the car drove into things. Between signs we therefore fall back to
the outer-wall law that scored full marks in the Open Challenge. Sign steering is
still primary and the override still outranks everything.

Their sign-positioning law (verbatim):
    green : Err = -((180 + y*2) - x)     -> push the sign toward the RIGHT of frame
    red   : Err =  (x - (140 - y*2))     -> push the sign toward the LEFT of frame
so the car passes GREEN on its left and RED on its right, and the target column
slides further out as the sign gets nearer (the y*2 term).

WHAT IS OURS:
  * every distance/threshold is MEASURED on our camera, not copied. Their numbers
    are for their optics and do not transfer (proven when their open-challenge
    constants read 0.021 against their own 0.5 reference on our camera).
  * the corrected wall mask, so the blue/orange lines and mat markings are not
    counted as walls.
  * MAGENTA COUNTS AS A WALL. They do the same until the parking phase; we have no
    parking walls to tune against yet, so it stays a wall for the whole run.

Run:  cd ~/wro2026 && source .venv/bin/activate && python obstacle_challenge.py
"""
import csv
import os
import time

import cv2
import numpy as np

import robot as R

# ---- tunables ----
CRUISE = 55             # start conservative; the sign manoeuvre needs reaction time
PILLAR_KP = 0.111       # their kp was 0.25 against a +-45 clamp; we clamp at +-20,
                        # so 0.25 * (20/45) keeps the same response shape
PILLAR_MIN_AREA = 60    # min contour area in our 320x160 buffer
SIGN_MEMORY = 8         # frames to hold a manoeuvre after losing the sign
Y_SCALE = 120.0 / R.PROC_H   # their frame was 120 rows tall, ours is 160
MAX_RUNTIME_S = 150
DEBUG = True


def find_sign(hsv):
    """Largest red/green contour that is TALLER than wide (their filter).
    Returns (kind, cx, cy, area) using the CENTROID, as they do, or None."""
    best = None
    for kind in ("red", "green"):
        m = R.mask(hsv, kind)
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            area = cv2.contourArea(c)
            if area < PILLAR_MIN_AREA or (best and area <= best[3]):
                continue
            x, y, w, h = cv2.boundingRect(c)
            if w >= h:                     # must be taller than wide
                continue
            mm = cv2.moments(c)
            if mm["m00"] == 0:
                continue
            best = (kind, mm["m10"] / mm["m00"], mm["m01"] / mm["m00"], area)
    return best


def sign_error(kind, cx, cy):
    """Their formulas, with y mapped onto their 120-row frame."""
    y = cy * Y_SCALE
    if kind == "green":
        return -((180.0 + y * 2.0) - cx)
    return cx - (140.0 - y * 2.0)


def main():
    R.setup_hardware(); R.servo(0)
    cam = R.open_camera()
    laps = R.LapTracker()
    outer = R.OuterWallFollower()   # lane keeping between signs
    hold = {"kind": "", "n": 0}     # short memory so detection flicker does not
                                    # drop us out of a manoeuvre mid-pass

    os.makedirs("logs", exist_ok=True)
    path = time.strftime("logs/obstacle_%Y%m%d_%H%M%S.csv")
    lf = open(path, "w", newline=""); log = csv.writer(lf)
    log.writerow(["t_ms", "cycle", "dir", "quad", "mode", "sign", "sx", "sy",
                  "area", "left", "right", "steer", "speed"])

    print(f"OBSTACLE - KyivRoboMagic structure, our measured constants")
    print(f"  CRUISE={CRUISE} PILLAR_KP={PILLAR_KP} STEER_MAX={R.STEER_MAX}")
    print(f"  wall override at {R.WALL_EMERGENCY} (~18 cm)   magenta counts as wall")
    print(f"  log -> {path}")
    input("Press Enter to START...")

    t0 = time.time(); n = 0; reason = "?"; last_steer = 0.0
    try:
        R.motor(CRUISE)
        while True:
            n += 1
            proc, hsv = R.read_hsv(cam)
            left, right = R.wall_readings(hsv)
            front = R.front_reading(hsv)
            blue, orange = R.line_counts(hsv)
            laps.update(blue, orange, left, right, front)

            # ---- 1. PRIMARY: steer to place the sign correctly ----
            sign = find_sign(hsv)
            if sign is not None:
                kind, sx, sy, area = sign
                steer = sign_error(kind, sx, sy) * PILLAR_KP
                mode = "sign-" + kind
                hold["kind"], hold["n"] = kind, SIGN_MEMORY
            elif hold["n"] > 0:
                # detection dropped for a frame - keep the manoeuvre committed.
                # MEASURED: sign-red toggled with 'straight' frame to frame
                # (area 61 -> 851 -> 0 -> 1060), which broke every pass.
                hold["n"] -= 1
                kind, sx, sy, area = hold["kind"], 0.0, 0.0, 0
                steer = last_steer
                mode = "sign-hold"
            else:
                kind, sx, sy, area = "", 0.0, 0.0, 0
                # NOT "drive straight". Their design leans on the wall override
                # firing constantly, which it does on their optics but not ours:
                # measured L=0.112 R=0.129 against a 0.213 threshold, so 44% of a
                # run was steer=0 and the car simply drove into things. Between
                # signs we use the outer-wall law that scored full marks in the
                # Open Challenge.
                steer = outer.steer(left, right, laps.direction)
                mode = "lane"

            # ---- 2. WALL OVERRIDE (also what turns the corners) ----
            d = laps.direction
            if d >= 0:
                if left > R.WALL_EMERGENCY:
                    steer, mode = R.STEER_MAX, "wall-L"
                elif right > R.WALL_EMERGENCY:
                    steer, mode = -R.STEER_MAX, "wall-R"
            else:
                if right > R.WALL_EMERGENCY:
                    steer, mode = -R.STEER_MAX, "wall-R"
                elif left > R.WALL_EMERGENCY:
                    steer, mode = R.STEER_MAX, "wall-L"

            steer = max(-R.STEER_MAX, min(R.STEER_MAX, steer))
            last_steer = steer
            speed = R.cruise_speed(CRUISE, steer)
            R.servo(steer); R.motor(speed)

            t_ms = int((time.time() - t0) * 1000)
            log.writerow([t_ms, n, laps.direction, laps.quadrant, mode, kind,
                          f"{sx:.0f}", f"{sy:.0f}", int(area),
                          f"{left:.3f}", f"{right:.3f}", f"{steer:.1f}", f"{speed:.0f}"])

            if DEBUG and n % 15 == 0:
                lf.flush()
                print(f"  t={t_ms/1000:5.1f}s dir={laps.direction:+d} q={laps.quadrant:2d} "
                      f"{mode:10s} L={left:.3f} R={right:.3f} steer={steer:+6.1f}")

            if laps.ready_to_finish():
                reason = f"{laps.quadrant} quadrants"
                break
            if time.time() - t0 > MAX_RUNTIME_S:
                reason = "timeout"
                break

        R.motor(0); R.servo(0)
        dt = time.time() - t0
        print(f"FINISHED ({reason}) quadrants={laps.quadrant} {dt:.1f}s "
              f"{1000*dt/max(n,1):.1f} ms/cycle")
        print("  fusion: " + laps.summary())
    except KeyboardInterrupt:
        print("interrupted")
    finally:
        R.motor(0); R.servo(0)
        lf.flush(); lf.close()
        R.shutdown(); cam.close()
        print(f"log saved: {path}")


if __name__ == "__main__":
    main()
