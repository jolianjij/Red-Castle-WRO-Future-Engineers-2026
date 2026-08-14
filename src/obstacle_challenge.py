#!/usr/bin/env python3
"""
obstacle_challenge.py - WRO 2026 Obstacle Challenge (diagnostic build).

Control priority, per frame:
    1. WALL OVERRIDE   outer wall too close  -> full lock away (also turns corners)
    2. SIGN            a red/green sign in view -> steer to place it correctly
    3. LANE            nothing else -> outer-wall law (the Open Challenge one)

Sign-positioning law:
    green : Err = -((GREEN_TARGET_X + y*Y_GAIN) - x)   push the sign RIGHT of frame
    red   : Err =  (x - (RED_TARGET_X   - y*Y_GAIN))   push the sign LEFT  of frame
so the car passes GREEN on its left and RED on its right, and the target column
slides further out as the sign gets nearer (the y term).

DIAGNOSTIC FEATURES
  * every tunable is in the TUNABLES block below - nothing else needs editing
  * saves annotated frames through each pass (frames/), showing the detected sign
  * builds the ORDER OF SIGNS PASSED, e.g. ['red','green','green','red'],
    printed at the end and written to sign_order.txt
  * MAGENTA is ignored completely (removed from the track)

Run:  cd ~/wro2026 && source .venv/bin/activate && python obstacle_challenge.py
"""
import csv
import os
import time

import cv2
import numpy as np

import robot as R

# ==========================================================================
# TUNABLES - everything you might want to change lives here
# ==========================================================================
CRUISE           = 55      # base speed %  (falls with steering, floor MIN_SPEED)
FORCE_CW         = False   # False = detect direction from the first corner line.
                           # Until a line is seen the car CENTRES between the
                           # walls, which is safe whichever way the track runs.

# --- lane keeping when no sign is near ---
LANE_DISTANCE_CM = 50.0    # hold this far from the OUTER wall between signs
# density = 0.1032 at 40 cm, slope 0.00501 per cm closer (measured)
LANE_TARGET      = 0.1032 - (LANE_DISTANCE_CM - 40.0) * 0.00501

# --- how hard the car reacts to a sign ---
PILLAR_KP        = 0.111   # deg per unit of Err
GREEN_TARGET_X   = 180.0   # column a GREEN sign is pushed toward (>160 = right)
RED_TARGET_X     = 140.0   # column a RED sign is pushed toward  (<160 = left)
Y_GAIN           = 2.0     # how much the target slides outward as a sign nears

# --- what counts as a sign ---
PILLAR_MIN_AREA  = 60      # min contour area (px) in the 320x160 buffer
PILLAR_MIN_ASPECT= 1.0     # height/width must exceed this (signs are tall)
SIGN_MEMORY      = 8       # frames to hold a manoeuvre after losing the sign

# --- when a sign counts as PASSED (for the order list) ---
PASS_MIN_AREA    = 250     # it must have got at least this big (i.e. come close)
PASS_LOST_FRAMES = 6       # ...and then be gone this many frames
PASS_COOLDOWN_S  = 0.8     # ignore a re-detection of the SAME colour within this
                           # long (absorbs flicker). Two real signs of the same
                           # colour are seconds apart, so keep this well under
                           # that or a genuine second sign gets swallowed.

# --- frame saving ---
SAVE_FRAMES      = True
SAVE_EVERY       = 3       # while a sign is in view, save every Nth frame
MAX_SAVES        = 120

# --- run control ---
STOP_ON_LAPS     = False   # False = ignore the lap counter, run until Ctrl+C
MAX_RUNTIME_S    = 300     # hard safety stop
DEBUG_EVERY      = 15      # console line every N frames
# ==========================================================================

Y_SCALE = 120.0 / R.PROC_H     # map our 160-row frame onto the 120-row reference


def find_sign(hsv):
    """Largest red/green contour that is taller than wide.
    Returns (kind, cx, cy, area, bbox) or None."""
    best = None
    for kind in ("red", "green"):
        m = R.mask(hsv, kind)
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            area = cv2.contourArea(c)
            if area < PILLAR_MIN_AREA or (best and area <= best[3]):
                continue
            x, y, w, h = cv2.boundingRect(c)
            if h < w * PILLAR_MIN_ASPECT:
                continue
            mm = cv2.moments(c)
            if mm["m00"] == 0:
                continue
            best = (kind, mm["m10"] / mm["m00"], mm["m01"] / mm["m00"],
                    area, (x, y, w, h))
    return best


def sign_error(kind, cx, cy):
    y = cy * Y_SCALE
    if kind == "green":
        return -((GREEN_TARGET_X + y * Y_GAIN) - cx)
    return cx - (RED_TARGET_X - y * Y_GAIN)


class PassLogger:
    """Builds the ORDER of signs the car has passed.

    A sign counts as passed when it grew to at least PASS_MIN_AREA (so it was
    genuinely approached, not a distant speck) and then stayed out of view for
    PASS_LOST_FRAMES. A cooldown stops one sign being recorded twice if the
    detection flickers back on.
    """

    def __init__(self):
        self.order = []
        self._kind = ""
        self._peak = 0
        self._lost = 0
        self._last_kind = ""       # what was committed last
        self._last_t = -1e9        # NOT 0.0 - that blocked the very first commit

    def update(self, sign, now):
        if sign is not None:
            kind, _, _, area, _ = sign
            if kind != self._kind:                 # a different sign appeared
                self._commit(now)
                self._kind, self._peak = kind, int(area)
            else:
                self._peak = max(self._peak, int(area))
            self._lost = 0
        elif self._kind:
            self._lost += 1
            if self._lost >= PASS_LOST_FRAMES:
                self._commit(now)

    def _commit(self, now):
        # the cooldown guards against the SAME sign being recorded twice when the
        # detection flickers back on; it must never block a DIFFERENT sign.
        same_again = (self._kind == self._last_kind
                      and now - self._last_t < PASS_COOLDOWN_S)
        if self._kind and self._peak >= PASS_MIN_AREA and not same_again:
            self.order.append(self._kind)
            self._last_kind, self._last_t = self._kind, now
            print(f"  >> PASSED {self._kind.upper()} "
                  f"(peak area {self._peak})  order so far: {self.order}")
        self._kind, self._peak, self._lost = "", 0, 0

    def finish(self, now):
        self._commit(now)
        return self.order


def annotate(proc, hsv, sign, steer, mode, left, right):
    vis = proc.copy()
    vis[R.wall_mask(hsv)] = (0, 0, 255)                      # red = wall
    if sign is not None:
        kind, cx, cy, area, (x, y, w, h) = sign
        col = (0, 0, 255) if kind == "red" else (0, 255, 0)
        cv2.rectangle(vis, (x, y), (x + w, y + h), col, 1)
        cv2.circle(vis, (int(cx), int(cy)), 2, (0, 255, 255), -1)
        tx = (GREEN_TARGET_X + cy * Y_SCALE * Y_GAIN) if kind == "green" \
             else (RED_TARGET_X - cy * Y_SCALE * Y_GAIN)
        tx = int(max(0, min(R.PROC_W - 1, tx)))
        cv2.line(vis, (tx, 0), (tx, R.PROC_H), col, 1)       # where we want it
        cv2.putText(vis, f"{kind} a={int(area)}", (4, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, col, 1)
    cv2.line(vis, (R.PROC_W // 2, 0), (R.PROC_W // 2, R.PROC_H), (255, 255, 0), 1)
    cv2.putText(vis, f"{mode} s{steer:+.0f} L{left:.2f} R{right:.2f}", (4, 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)
    return np.vstack([proc, vis])


def main():
    R.setup_hardware(); R.servo(0)
    cam = R.open_camera()
    laps = R.LapTracker()
    outer = R.OuterWallFollower(target=LANE_TARGET)
    passes = PassLogger()
    hold = {"kind": "", "n": 0}

    if FORCE_CW:
        laps.direction = 1

    os.makedirs("logs", exist_ok=True)
    os.makedirs("frames", exist_ok=True)
    for f in os.listdir("frames"):
        os.remove(os.path.join("frames", f))

    path = time.strftime("logs/obstacle_%Y%m%d_%H%M%S.csv")
    lf = open(path, "w", newline=""); log = csv.writer(lf)
    log.writerow(["t_ms", "cycle", "dir", "quad", "mode", "sign", "sx", "sy",
                  "area", "left", "right", "steer", "speed", "frame"])

    print("OBSTACLE (diagnostic)")
    print(f"  direction : {'FORCED CW' if FORCE_CW else 'auto from corner lines'}"
          f"   CRUISE={CRUISE}")
    print(f"  lane      : {LANE_DISTANCE_CM:.0f} cm from the outer wall"
          f" (density {LANE_TARGET:.4f})")
    print(f"  sign      : KP={PILLAR_KP} green->x{GREEN_TARGET_X} red->x{RED_TARGET_X}"
          f" min_area={PILLAR_MIN_AREA}")
    print(f"  wall      : override at {R.WALL_EMERGENCY}   magenta ignored"
          f" (MAGENTA_IS_WALL={R.MAGENTA_IS_WALL})")
    print(f"  stop      : {'lap counter' if STOP_ON_LAPS else 'Ctrl+C only'}"
          f"   log -> {path}")
    input("Press Enter to START...")

    t0 = time.time(); n = 0; saves = 0; last_steer = 0.0; reason = "?"
    try:
        R.motor(CRUISE)
        while True:
            n += 1
            now = time.time()
            proc, hsv = R.read_hsv(cam)
            left, right = R.wall_readings(hsv)
            front = R.front_reading(hsv)
            blue, orange = R.line_counts(hsv)
            laps.update(blue, orange, left, right, front)

            sign = find_sign(hsv)
            passes.update(sign, now)

            # ---- SIGN (primary) / LANE (default) ----
            if sign is not None:
                kind, sx, sy, area, _ = sign
                steer = sign_error(kind, sx, sy) * PILLAR_KP
                mode = "sign-" + kind
                hold["kind"], hold["n"] = kind, SIGN_MEMORY
            elif hold["n"] > 0:
                hold["n"] -= 1
                kind, sx, sy, area = hold["kind"], 0.0, 0.0, 0
                steer, mode = last_steer, "sign-hold"
            else:
                kind, sx, sy, area = "", 0.0, 0.0, 0
                steer = outer.steer(left, right, laps.direction)
                mode = "lane"

            # ---- WALL OVERRIDE (highest priority) ----
            if laps.direction >= 0:
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

            fname = ""
            if (SAVE_FRAMES and saves < MAX_SAVES
                    and (sign is not None or mode == "sign-hold")
                    and n % SAVE_EVERY == 0):
                fname = (f"frames/{n:05d}_{kind or 'hold'}_a{int(area):04d}"
                         f"_s{steer:+05.1f}.png")
                cv2.imwrite(fname, annotate(proc, hsv, sign, steer, mode, left, right))
                saves += 1

            t_ms = int((now - t0) * 1000)
            log.writerow([t_ms, n, laps.direction, laps.quadrant, mode, kind,
                          f"{sx:.0f}", f"{sy:.0f}", int(area),
                          f"{left:.3f}", f"{right:.3f}", f"{steer:.1f}",
                          f"{speed:.0f}", fname])

            if DEBUG_EVERY and n % DEBUG_EVERY == 0:
                lf.flush()
                print(f"  t={t_ms/1000:5.1f}s q={laps.quadrant:2d} {mode:10s} "
                      f"L={left:.3f} R={right:.3f} area={int(area):4d} "
                      f"steer={steer:+6.1f}")

            if STOP_ON_LAPS and laps.ready_to_finish():
                reason = f"{laps.quadrant} quadrants"; break
            if now - t0 > MAX_RUNTIME_S:
                reason = "timeout"; break
        R.motor(0); R.servo(0)
    except KeyboardInterrupt:
        reason = "stopped by user"
        print("\ninterrupted")
    finally:
        R.motor(0); R.servo(0)
        order = passes.finish(time.time())
        dt = time.time() - t0
        print(f"\nFINISHED ({reason})  {dt:.1f}s  {n} frames  "
              f"{1000*dt/max(n,1):.1f} ms/cycle")
        print(f"  SIGN ORDER PASSED: {order if order else '(none)'}")
        print(f"  frames saved: {saves} -> frames/")
        with open("sign_order.txt", "w") as f:
            f.write(",".join(order) + "\n")
        log.writerow([])
        log.writerow(["#", "sign order", " ".join(order)])
        lf.flush(); lf.close()
        R.shutdown(); cam.close()
        print(f"  log: {path}   order also in sign_order.txt")


if __name__ == "__main__":
    main()
