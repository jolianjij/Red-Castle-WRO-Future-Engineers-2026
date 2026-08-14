#!/usr/bin/env python3
"""
obstacle_challenge.py - WRO 2026 Obstacle Challenge (diagnostic build).

Control priority, per frame - all of it in decide(), one function:
    1. KICK   open-loop corner exit, fired when a corner is counted and the last
              sign pushed the car toward the INNER wall. May exceed STEER_MAX.
    2. WALL   outer wall too close -> full lock away (also turns corners)
    3. SIGN   a red/green sign in view -> steer to place it correctly
    4. HOLD   a sign was here in the last SIGN_HOLD_S -> don't hand back yet
    5. LANE   nothing else -> outer-wall law (the Open Challenge one)

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
import collections
import csv
import os
import time

import cv2
import numpy as np

import robot as R

# ==========================================================================
# TUNABLES - everything you might want to change lives here
# ==========================================================================
CRUISE           = 70    # base speed %  (falls with steering, floor MIN_SPEED)
FORCE_CW         = True   # False = detect direction from the first corner line.
                           # Until a line is seen the car CENTRES between the
                           # walls, which is safe whichever way the track runs.

# --- lane keeping when no sign is near ---
LANE_DISTANCE_CM = 30.0    # hold this far from the OUTER wall between signs
# density = 0.1032 at 40 cm, slope 0.00501 per cm closer (measured)
LANE_TARGET      = 0.1032 - (LANE_DISTANCE_CM - 40.0) * 0.00501

# --- how hard the car reacts to a sign ---
PILLAR_KP        = 0.3   # deg per unit of Err
GREEN_TARGET_X   = 180.0   # column a GREEN sign is pushed toward (>160 = right)
RED_TARGET_X     = 140.0   # column a RED sign is pushed toward  (<160 = left)
Y_GAIN           = 2.0     # how much the target slides outward as a sign nears

# --- what counts as a sign ---
PILLAR_MIN_AREA  = 55      # min contour area (px) in the 320x160 buffer
PILLAR_MIN_ASPECT= 1.0     # height/width must exceed this (signs are tall)
SIGN_HOLD_S      = 3.0     # after the last sign is seen, do NOT return to lane
                           # keeping for this long. Stops the wall follower
                           # yanking the car back mid-pass.
SIGN_STEER_HOLD_S= 0.5     # of that hold, keep steering as the sign commanded
                           # for this long, then run straight for the remainder

# --- when a sign counts as PASSED (for the order list) ---
PASS_MIN_AREA    = 250     # it must have got at least this big (i.e. come close)
PASS_LOST_S      = 3.0     # ...and then be gone this long. A sign is recorded
                           # once the hold above expires, so a brief dropout can
                           # no longer register the same sign several times.
PASS_COOLDOWN_S  = 0.8     # ignore a re-detection of the SAME colour within this
                           # long (absorbs flicker). Two real signs of the same
                           # colour are seconds apart, so keep this well under
                           # that or a genuine second sign gets swallowed.

# --- CORNER-EXIT KICK ---------------------------------------------------
# When a corner is counted AND the last sign seen was the one that pushed the
# car toward the INNER wall, fire a fixed hard turn so the next section comes
# into view. See robot.CornerKick for the full reasoning.
#     CW  : inner wall is RIGHT, RED   pushes the car right -> kick RIGHT
#     CCW : inner wall is LEFT,  GREEN pushes the car left  -> kick LEFT
CORNER_KICK      = True    # False disables the whole behaviour
KICK_ANGLE       = 30.0    # deg. May exceed STEER_MAX (20) - that is the point.
                           # Hard ceiling is the linkage limit, STEER_MECH_MAX=35.
KICK_TIME_S      = 0.9     # how long to hold it. Longer = tighter turn.
KICK_SPEED       = 55      # % speed during the kick; slower turns in less space
KICK_SIGN_CW     = "red"   # sign colour that arms the kick when running CW
KICK_SIGN_CCW    = "green" # ...and when running CCW. Swap these if a venue
                           # proves the opposite convention.

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


def wall_override(direction, left, right):
    """Emergency steer, or None if neither wall is dangerously close.

    Returns +STEER_MAX (hard right) or -STEER_MAX (hard left). The OUTER wall is
    tested first, because that is the one the car is deliberately hugging:
    in CW the outer wall is on the left, in CCW it is on the right.
    """
    outer_first = (("left", left), ("right", right)) if direction >= 0 \
        else (("right", right), ("left", left))
    for side, density in outer_first:
        if density > R.WALL_EMERGENCY:
            return R.STEER_MAX if side == "left" else -R.STEER_MAX
    return None


def opposes(a, b):
    """True if two steering commands pull in opposite directions."""
    return a is not None and b is not None and a * b < 0


def clamp_steer(steer, servo_limit):
    """Clamp to STEER_MAX, or to a raised (kick) ceiling that never exceeds the
    linkage's mechanical limit."""
    ceiling = R.STEER_MAX if servo_limit is None \
        else min(servo_limit, R.STEER_MECH_MAX)
    return max(-ceiling, min(ceiling, steer))


# What one frame of decision-making produces.
Decision = collections.namedtuple(
    "Decision", "steer mode kind sx sy area servo_limit speed_cap")


def decide(now, sign, hold, kick, outer, left, right, direction):
    """THE CONTROL PRIORITY LADDER - the entire driving decision, in one place.

    Highest priority first; EXACTLY ONE branch produces the answer:

        1 KICK  open-loop corner exit. Outranks everything, because it is a
                committed manoeuvre - except a wall closing from the far side.
        2 WALL  emergency: the outer wall is too close.
        3 SIGN  a red/green sign is in view -> steer to place it correctly.
        4 HOLD  a sign was here very recently. Do NOT hand back to lane keeping
                yet, or the wall follower drags the car back across the pass.
        5 LANE  nothing else is happening -> outer-wall PD.

    This is deliberately pure: no hardware, no camera, no globals it writes to
    except `hold`. That is what lets tools/test_logic.py drive it directly, and
    it means changing how the car decides never means reading the main loop.
    """
    wall = wall_override(direction, left, right)

    # ---- 1. KICK ----
    if kick.active(now):
        k_steer, k_limit, k_speed = kick.command()
        if not opposes(wall, k_steer):
            return Decision(k_steer, "kick", "", 0.0, 0.0, 0, k_limit, k_speed)
        kick.cancel()          # wall closing the other way - abandon the kick

    # ---- 2. WALL ----
    if wall is not None:
        return Decision(wall, "wall-L" if wall > 0 else "wall-R",
                        "", 0.0, 0.0, 0, None, None)

    # ---- 3. SIGN ----
    if sign is not None:
        kind, sx, sy, area, _ = sign
        steer = sign_error(kind, sx, sy) * PILLAR_KP
        hold["kind"], hold["t"], hold["steer"] = kind, now, steer
        return Decision(steer, "sign-" + kind, kind, sx, sy, area, None, None)

    # ---- 4. HOLD ----
    if hold["kind"] and (now - hold["t"]) < SIGN_HOLD_S:
        if (now - hold["t"]) < SIGN_STEER_HOLD_S:
            steer, mode = hold["steer"], "sign-hold"
        else:
            steer, mode = 0.0, "sign-clear"      # run straight past it
        return Decision(steer, mode, hold["kind"], 0.0, 0.0, 0, None, None)

    # ---- 5. LANE ----
    return Decision(outer.steer(left, right, direction), "lane",
                    "", 0.0, 0.0, 0, None, None)


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
        self._seen = 0.0
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
            self._seen = now
        elif self._kind and (now - self._seen) >= PASS_LOST_S:
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
        self._kind, self._peak = "", 0

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
    kick = R.CornerKick(angle=KICK_ANGLE, duration_s=KICK_TIME_S,
                        speed=KICK_SPEED, sign_cw=KICK_SIGN_CW,
                        sign_ccw=KICK_SIGN_CCW, enabled=CORNER_KICK)
    hold = {"kind": "", "t": -1e9, "steer": 0.0}
    last_sign_kind = ""        # most recent sign COLOUR seen, kept across the
                               # gap between the sign and the corner it precedes

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
    print(f"  kick      : {'ON' if CORNER_KICK else 'OFF'}  {KICK_ANGLE:.0f}deg for"
          f" {KICK_TIME_S:.1f}s @ {KICK_SPEED}%  "
          f"(CW<-{KICK_SIGN_CW}, CCW<-{KICK_SIGN_CCW})")
    print(f"  lines     : orange>{R.LINE_FRACTION_ORANGE:.3f}  "
          f"blue>{R.LINE_FRACTION_BLUE:.3f}  (separate thresholds)")
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
            q_before = laps.quadrant
            laps.update(blue, orange, left, right, front)

            sign = find_sign(hsv)
            passes.update(sign, now)
            if sign is not None:
                last_sign_kind = sign[0]

            # A corner was just counted -> if the sign we last saw pushed us
            # toward the inner wall, swing hard so the next section comes up.
            if laps.quadrant > q_before:
                if kick.maybe_fire(laps.direction, last_sign_kind, now):
                    last_sign_kind = ""     # consumed; don't re-fire next corner

            d = decide(now, sign, hold, kick, outer, left, right, laps.direction)
            kind, sx, sy, area, mode = d.kind, d.sx, d.sy, d.area, d.mode

            steer = clamp_steer(d.steer, d.servo_limit)
            last_steer = steer
            speed = d.speed_cap if d.speed_cap is not None \
                else R.cruise_speed(CRUISE, steer)
            R.servo(steer, limit=d.servo_limit); R.motor(speed)

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
        print(f"  corner kicks fired: {kick.fired}")
        print(f"  lap fusion: {laps.summary()}")
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
