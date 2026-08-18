#!/usr/bin/env python3
"""
obstacle_challenge.py - WRO 2026 Future Engineers, OBSTACLE CHALLENGE.
Three laps past red and green traffic signs.

    GREEN -> pass it on its LEFT     RED -> pass it on its RIGHT

=========================== HOW THIS FILE WORKS ===========================
Same three parts as open_challenge.py, in the same order:

    1. TUNABLES   the numbers you change.  Nothing else needs editing.
    2. decide()   the brain: ONE frame in, one steering decision out.
                  Pure logic - no camera, no motor - so it can be tested
                  on a laptop with tools/test_logic.py.
    3. main()     the loop: LOOK -> THINK -> ACT, over and over.

To write a new challenge: copy this file, rewrite decide(), leave main()
almost alone. See src/README.md.
===========================================================================

It also records the ORDER of the signs it passed (sign_order.txt) and saves
annotated frames of each pass (frames/), which is what the video and the
engineering journal are built from.

Run on the Pi:
    cd ~/wro2026 && source .venv/bin/activate && python obstacle_challenge.py
Then PRESS THE BUTTON to start. Press it again to stop.
"""
import collections
import csv
import os
import time

import cv2
import numpy as np

import robot as R

# ==========================================================================
# 1. TUNABLES - everything you might want to change lives here
# ==========================================================================

# --- speed ---
CRUISE           = 70      # base speed %  (falls with steering)

# --- direction ---
FORCE_DIRECTION  = 0       # +1 CW, -1 CCW, 0 = work it out from the parking lot
                           # (below), falling back to the corner lines. Until
                           # the direction is known the car CENTRES between the
                           # walls, which is safe whichever way the track runs.

# --- leaving the parking lot (this also decides the direction) ---
# The car starts inside the magenta parking lot. Whichever side is more blocked
# is the side it cannot leave by, so:
#     more magenta on the LEFT   -> leave RIGHT -> run CW
#     more magenta on the RIGHT  -> leave LEFT  -> run CCW
# One measurement, taken before the car moves, answers both questions.
PARK_START       = True    # False = skip it and start already on the track
PARK_ANGLE       = 30.0    # deg of lock while pulling out (may exceed STEER_MAX)
PARK_TIME_S      = 1.6     # how long to hold it. Longer = tighter exit.
PARK_SPEED       = 45      # % speed while leaving
PARK_SETTLE      = 8       # frames averaged before deciding. The car is still,
                           # so these are the sharpest frames of the whole run.
PARK_MIN_MAGENTA = 0.010   # if neither side has at least this much magenta the
                           # car is not in a lot: give up rather than guess, and
                           # let the corner lines decide as usual.
PARK_INVERT      = False   # ONE-LINE VENUE FIX. The measurement of which side
                           # is blocked is reliable; whether "blocked on the
                           # left" means CW depends on your track's physical
                           # layout. If the car reads the lot correctly but
                           # leaves the wrong way, set this True.
PARK_USE_WALL    = False   # count the black wall as well as magenta?
                           # DEFAULT OFF, and this is deliberate. The magenta
                           # wall physically HIDES the black wall behind it, so
                           # the blocked side shows LESS black, while the open
                           # side looks across the track at the far outer wall
                           # and shows MORE. The two signals are anti-correlated
                           # and adding them cancels the measurement - in the
                           # test case magenta said L=0.60 R=0.05 while wall
                           # said L=0.40 R=0.95, and the sum was an exact tie.
                           # Magenta alone is the honest signal. Turn this on
                           # only if a venue proves otherwise.

# --- lane keeping, when no sign is near ---
LANE_DISTANCE_CM = 30.0    # hold this far from the OUTER wall between signs
# density = 0.1032 at 40 cm, slope 0.00501 per cm closer (measured)
LANE_TARGET      = 0.1032 - (LANE_DISTANCE_CM - 40.0) * 0.00501

# --- how hard the car reacts to a sign ---
PILLAR_KP        = 0.3     # deg per unit of error
GREEN_TARGET_X   = 180.0   # column a GREEN sign is pushed toward (>160 = right)
RED_TARGET_X     = 140.0   # column a RED sign is pushed toward  (<160 = left)
Y_GAIN           = 2.0     # how much the target slides outward as a sign nears

# --- what counts as a sign ---
PILLAR_MIN_AREA  = 55      # min contour area (px) in the 320x160 buffer
PILLAR_MIN_ASPECT= 1.0     # height/width must exceed this (signs are tall)
SIGN_HOLD_S      = 3.0     # after the last sign is seen, do NOT return to lane
                           # keeping for this long - it would drag the car back
                           # across the pass it is halfway through
SIGN_STEER_HOLD_S= 0.5     # of that hold, keep steering as the sign commanded
                           # for this long, then run straight for the remainder

# --- corner-exit kick ---
# When a corner is counted AND the last sign pushed the car toward the INNER
# wall, fire a fixed hard turn so the next section comes into view.
#     CW  : inner wall is RIGHT, RED   pushes the car right -> kick RIGHT
#     CCW : inner wall is LEFT,  GREEN pushes the car left  -> kick LEFT
CORNER_KICK      = True
KICK_ANGLE       = 30.0    # deg. May exceed STEER_MAX (20) - that is the point.
                           # Hard ceiling is the linkage, STEER_MECH_MAX = 35.
KICK_TIME_S      = 0.9     # how long to hold it. Longer = tighter turn.
KICK_SPEED       = 55      # % speed during the kick
KICK_SIGN_CW     = "red"   # sign colour that arms the kick when running CW
KICK_SIGN_CCW    = "green" # ...and when running CCW

# --- recording the order of signs passed ---
PASS_MIN_AREA    = 250     # a sign must have got this big to count as passed
PASS_LOST_S      = 3.0     # ...and then be gone this long
PASS_COOLDOWN_S  = 0.8     # ignore a re-detection of the SAME colour this soon

# --- frame saving ---
SAVE_FRAMES      = True
SAVE_EVERY       = 3       # while a sign is in view, save every Nth frame
MAX_SAVES        = 120

# --- run control ---
STOP_ON_LAPS     = False   # False = ignore the lap counter, run until stopped
MAX_RUNTIME_S    = 300     # SAFETY net
DEBUG_EVERY      = 15      # console status line every N frames (0 = silent)
# ==========================================================================

Y_SCALE = 120.0 / R.PROC_H   # map our 160-row frame onto the 120-row reference


# ==========================================================================
# 2. THE BRAIN - one frame in, one decision out
# ==========================================================================
Decision = collections.namedtuple(
    "Decision", "steer mode kind sx sy area servo_limit speed_cap")


def find_sign(hsv):
    """The biggest red/green blob that is TALLER THAN WIDE.

    The aspect test is what rejects the corner lines and stray mat pixels: a
    traffic sign is a standing block, so it is always taller than it is wide.
    Returns (kind, cx, cy, area, bbox) or None.
    """
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
    """How far the sign is from where we want it in the picture.

    We never measure distance. We just keep pushing the sign toward one side of
    the frame, and the car ends up on the correct side of it:

        green -> drive the sign to the RIGHT of the frame -> we pass on its left
        red   -> drive the sign to the LEFT  of the frame -> we pass on its right

    The target slides further out as the sign gets nearer (the y term), so the
    car commits harder the closer it gets instead of clipping the corner of it.
    """
    y = cy * Y_SCALE
    if kind == "green":
        return -((GREEN_TARGET_X + y * Y_GAIN) - cx)
    return cx - (RED_TARGET_X - y * Y_GAIN)


def clamp_steer(steer, servo_limit):
    """Clamp to STEER_MAX, or to a raised (kick) ceiling that never exceeds the
    linkage's mechanical limit."""
    ceiling = R.STEER_MAX if servo_limit is None \
        else min(servo_limit, R.STEER_MECH_MAX)
    return max(-ceiling, min(ceiling, steer))


def decide(now, view, sign, hold, kick, outer, direction, park=None):
    """Return a Decision for this frame. +steer = right.

    PRIORITY LADDER - highest first, exactly one branch answers:

        0. PARK   still leaving the parking lot. Runs once, at the very start,
                  and locks the lap direction on the way out.
        1. KICK   open-loop corner exit. It is a committed manoeuvre, so it
                  outranks everything EXCEPT a wall closing from the far side.
        2. WALL   a wall is too close -> escape.
        3. SIGN   a red/green sign is in view -> steer to place it correctly.
        4. HOLD   a sign was here in the last SIGN_HOLD_S. Do NOT hand back to
                  lane keeping yet, or the wall follower drags the car back
                  across the pass it is halfway through.
        5. LANE   nothing else is happening -> PD on the outer wall.

    Pure logic: no hardware, no camera. That is what lets tools/test_logic.py
    drive it directly, and it means changing how the car decides never means
    reading the main loop.
    """
    none = ("", 0.0, 0.0, 0)

    # ---- 0. PARK ----
    # Deliberately ABOVE the wall escape: inside the lot the magenta walls are
    # close on purpose, and an escape firing here would fight the way out.
    if park is not None and not park.done:
        out = park.update(view, now, known_direction=direction)
        if out is not None:
            steer, mode, speed = out
            return Decision(steer, mode, *none, PARK_ANGLE, speed)

    # ---- 1. KICK ----
    escape = R.wall_emergency(view.left, view.right, outer, direction)
    if kick.active(now):
        k_steer, k_limit, k_speed = kick.command()
        if not (escape is not None and escape * k_steer < 0):
            return Decision(k_steer, "kick", *none, k_limit, k_speed)
        kick.cancel()          # wall closing the other way - abandon the kick

    # ---- 2. WALL ----
    if escape is not None:
        return Decision(escape, "wall", *none, None, None)

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
    return Decision(outer.steer(view.left, view.right, direction),
                    "lane", *none, None, None)


class PassLogger:
    """Builds the ORDER of the signs the car has passed, e.g. [red, green, red].

    A sign counts as passed once it grew to at least PASS_MIN_AREA (so it was
    genuinely approached, not a distant speck) and then stayed out of view for
    PASS_LOST_S. The cooldown stops ONE sign being recorded twice when the
    detection flickers; it must never block a DIFFERENT sign, because two real
    signs of the same colour can follow each other.
    """

    def __init__(self):
        self.order = []
        self._kind = ""
        self._peak = 0
        self._seen = 0.0
        self._last_kind = ""
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


def annotate(view, sign, d):
    """Original frame on top, what the car understood underneath."""
    vis = view.proc.copy()
    vis[R.wall_mask(view.hsv)] = (0, 0, 255)                 # red = wall
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
    cv2.putText(vis, f"{d.mode} s{d.steer:+.0f} "
                f"L{view.left:.2f} R{view.right:.2f}", (4, 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)
    return np.vstack([view.proc, vis])


# ==========================================================================
# 3. THE LOOP
# ==========================================================================
def main():
    R.setup_hardware()
    R.servo(0)
    button = R.Button()
    cam = R.open_camera()

    laps = R.LapTracker()
    if FORCE_DIRECTION:
        laps.set_direction(FORCE_DIRECTION, "FORCE_DIRECTION in this file")
    outer = R.OuterWallFollower(target=LANE_TARGET)
    passes = PassLogger()
    kick = R.CornerKick(angle=KICK_ANGLE, duration_s=KICK_TIME_S,
                        speed=KICK_SPEED, sign_cw=KICK_SIGN_CW,
                        sign_ccw=KICK_SIGN_CCW, enabled=CORNER_KICK)
    park = R.ParkingExit(angle=PARK_ANGLE, time_s=PARK_TIME_S,
                         speed=PARK_SPEED, settle_frames=PARK_SETTLE,
                         min_magenta=PARK_MIN_MAGENTA,
                         use_wall=PARK_USE_WALL, enabled=PARK_START,
                         invert=PARK_INVERT)
    hold = {"kind": "", "t": -1e9, "steer": 0.0}
    last_sign_kind = ""        # most recent sign COLOUR seen, kept across the
                               # gap between a sign and the corner it precedes

    os.makedirs("logs", exist_ok=True)
    os.makedirs("frames", exist_ok=True)
    for f in os.listdir("frames"):
        os.remove(os.path.join("frames", f))

    logpath = time.strftime("logs/obstacle_%Y%m%d_%H%M%S.csv")
    logf = open(logpath, "w", newline="")
    log = csv.writer(logf)
    log.writerow(["t_ms", "frame", "dir", "quad", "mode", "sign", "sx", "sy",
                  "area", "left", "right", "front", "steer", "speed", "file"])

    print("OBSTACLE CHALLENGE")
    print(f"  direction : {'FORCED ' + ('CW' if FORCE_DIRECTION > 0 else 'CCW')}"
          if FORCE_DIRECTION else "  direction : auto from the corner lines")
    print(f"  lane      : {LANE_DISTANCE_CM:.0f} cm from the outer wall "
          f"(density {LANE_TARGET:.4f})")
    print(f"  sign      : KP={PILLAR_KP} green->x{GREEN_TARGET_X} "
          f"red->x{RED_TARGET_X} min_area={PILLAR_MIN_AREA}")
    print(f"  parking   : {'ON' if PARK_START else 'OFF'} "
          f"{PARK_ANGLE:.0f}deg for {PARK_TIME_S:.1f}s @ {PARK_SPEED}%  "
          f"(more magenta LEFT -> out RIGHT -> CW)")
    print(f"  kick      : {'ON' if CORNER_KICK else 'OFF'} {KICK_ANGLE:.0f}deg "
          f"for {KICK_TIME_S:.1f}s @ {KICK_SPEED}%  "
          f"(CW<-{KICK_SIGN_CW}, CCW<-{KICK_SIGN_CCW})")
    print(f"  lines     : orange>{R.LINE_FRACTION_ORANGE:.3f} "
          f"blue>{R.LINE_FRACTION_BLUE:.3f}")
    print(f"  speed     : {CRUISE}%   "
          f"stop: {'lap counter' if STOP_ON_LAPS else 'button only'}")
    print(f"  log       : {logpath}")

    button.wait_for_start("Obstacle Challenge")

    t0 = time.time()
    frame = 0
    saves = 0
    reason = "?"
    R.motor(CRUISE)
    try:
        while True:
            frame += 1
            now = time.time()

            # ---------------- LOOK ----------------
            view = R.look(cam)
            before = laps.quadrant
            laps.update(view.blue, view.orange, view.left, view.right, view.front)

            sign = find_sign(view.hsv)
            passes.update(sign, now)
            if sign is not None:
                last_sign_kind = sign[0]

            # a corner was just counted -> maybe kick out of it
            if laps.quadrant > before:
                if kick.maybe_fire(laps.direction, last_sign_kind, now):
                    last_sign_kind = ""      # consumed; don't re-fire next corner

            # ---------------- THINK ----------------
            d = decide(now, view, sign, hold, kick, outer, laps.direction, park)
            if park.direction and laps.direction == 0:
                # the way out of the lot IS the way round the track
                laps.set_direction(park.direction, "parking-lot exit")
            steer = clamp_steer(d.steer, d.servo_limit)
            speed = d.speed_cap if d.speed_cap is not None \
                else R.cruise_speed(CRUISE, steer)

            # ---------------- ACT ----------------
            R.servo(steer, limit=d.servo_limit)
            R.motor(speed)

            # ---------------- RECORD / FINISH ----------------
            fname = ""
            if (SAVE_FRAMES and saves < MAX_SAVES
                    and (sign is not None or d.mode in ("sign-hold", "kick"))
                    and frame % SAVE_EVERY == 0):
                fname = (f"frames/{frame:05d}_{d.kind or d.mode}"
                         f"_a{int(d.area):04d}_s{steer:+05.1f}.png")
                cv2.imwrite(fname, annotate(view, sign, d))
                saves += 1

            t_ms = int((now - t0) * 1000)
            log.writerow([t_ms, frame, laps.direction, laps.quadrant, d.mode,
                          d.kind, f"{d.sx:.0f}", f"{d.sy:.0f}", int(d.area),
                          f"{view.left:.3f}", f"{view.right:.3f}",
                          f"{view.front:.3f}", f"{steer:.1f}", f"{speed:.0f}",
                          fname])
            if DEBUG_EVERY and frame % DEBUG_EVERY == 0:
                logf.flush()
                print(f"  t={t_ms/1000:5.1f}s q={laps.quadrant:2d} {d.mode:10s} "
                      f"L={view.left:.3f} R={view.right:.3f} "
                      f"area={int(d.area):4d} steer={steer:+6.1f}")

            if button.stop_pressed():
                reason = "BUTTON pressed"
                break
            if STOP_ON_LAPS and laps.ready_to_finish():
                reason = f"{laps.quadrant} quadrants"
                break
            if now - t0 > MAX_RUNTIME_S:
                reason = "SAFETY timeout"
                break

    except KeyboardInterrupt:
        reason = "Ctrl+C"
    finally:
        R.motor(0)
        R.servo(0)
        order = passes.finish(time.time())
        dt = time.time() - t0
        print(f"\nFINISHED ({reason})  {frame} frames  {dt:.1f}s  "
              f"{1000*dt/max(frame,1):.1f} ms/frame")
        print(f"  SIGN ORDER PASSED : {order if order else '(none)'}")
        print(f"  corner kicks fired: {kick.fired}")
        print(f"  frames saved      : {saves} -> frames/")
        print(f"  fusion: {laps.summary()}")
        with open("sign_order.txt", "w") as f:
            f.write(",".join(order) + "\n")
        log.writerow([])
        log.writerow(["#", reason, "sign order", " ".join(order)])
        logf.flush()
        logf.close()
        R.shutdown()
        cam.close()
        print(f"  log saved: {logpath}   order also in sign_order.txt")


if __name__ == "__main__":
    main()
