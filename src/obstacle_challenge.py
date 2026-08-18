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

It also records the ORDER of the signs it passed (sign_order.txt) and saves the
frames where the run was DECIDED (frames/, with 00-WHAT-HAPPENED.txt listing
them in order) - which is what the video and the engineering journal are built
from, and what makes a bad run diagnosable afterwards.

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
CRUISE           = 80      # base speed %  (falls with steering)

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
PARK_START       = False    # False = skip it and start already on the track
PARK_ANGLE       = 40.0    # deg of lock while pulling out (may exceed STEER_MAX)
PARK_TIME_S      = 2     # how long to hold it. Longer = tighter exit.
PARK_SPEED       = 50      # % speed while leaving
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
                           # OFF, but for a plainer reason than first recorded.
                           # A synthetic test suggested the two signals were
                           # ANTI-correlated (the magenta wall hides the black
                           # one behind it). ON THE REAL TRACK THEY AGREE:
                           # measured in the lot, magenta read L 0.716 R 0.449
                           # and the wall read L 0.174 R 0.093 - both naming
                           # the same side. The anti-correlation was an
                           # artifact of the synthetic image, where the blank
                           # background counted as wall.
                           # It stays off because magenta alone already gives a
                           # clear margin and is the DIRECT signal: the lot is
                           # defined by magenta, whereas black is every wall on
                           # the track. Turn it on only if magenta's margin is
                           # marginal and the wall's is not.

# --- lane keeping, when no sign is near ---
LANE_DISTANCE_CM = 40.0    # hold this far from the OUTER wall between signs
# density = 0.1032 at 40 cm, slope 0.00501 per cm closer (measured)
LANE_TARGET      = 0.1032 - (LANE_DISTANCE_CM - 40.0) * 0.00501

# --- how hard the car reacts to a sign ---
# GREEN AND RED ARE TUNED SEPARATELY. They are not symmetric in practice: on a
# real run green was detected 738 frames with a MEDIAN AREA of 186 px while red
# was detected 351 frames at a median of 718 - green arrives as smaller, more
# broken-up blobs, so the same numbers do not suit both.
#   *_KP        deg of steering per unit of error. Higher = reacts harder.
#   *_TARGET_X  the column the sign is pushed toward. Centre is 160, so
#               GREEN > 160 (drive it right, we pass on its left) and
#               RED   < 160 (drive it left,  we pass on its right).
#               FURTHER from 160 = a wider berth around the sign.
#   *_MIN_AREA  smaller than this and it is ignored. Raise it if the car
#               chases distant specks; lower it if it notices signs too late.
#   *_MIN_ASPECT height/width. A standing sign is taller than it is wide, and
#               this is what rejects lines, markings and patches of floor.
#               1.0 = "taller than wide". Raise toward 1.5 to be stricter.
GREEN_KP         = 0.3
GREEN_TARGET_X   = 220.0
GREEN_MIN_AREA   = 70
GREEN_MIN_ASPECT = 1.0

RED_KP           = 0.3
RED_TARGET_X     = 120.0
RED_MIN_AREA     = 70
RED_MIN_ASPECT   = 1.0

Y_GAIN           = 2.0     # how much the target slides outward as a sign nears

# --- what counts as a sign (shared) ---
SIGN_HOLD_S      = 3.0     # after the last sign is seen, do NOT return to lane
                           # keeping for this long - it would drag the car back
                           # across the pass it is halfway through
SIGN_WALL_GUARD  = 0.70    # where the fade STARTS, as a fraction of
                           # WALL_EMERGENCY. 1.0 disables the fade entirely.
SIGN_WALL_FLOOR  = 0.55    # ...and how much of the sign steer SURVIVES it.
                           # THIS MUST NOT BE 0. Measured on a failed run:
                           # a GREEN sign must be passed on its LEFT, and in CW
                           # the outer wall IS on the left - so every green pass
                           # steers toward a wall by geometry, not by mistake.
                           # Fading to zero killed 226 of 388 green-steering
                           # frames, and when green was closest (area>2000) the
                           # left wall averaged 0.172 - right in the fade band.
                           # The car could never complete a green pass.
                           # The ESCAPE at WALL_EMERGENCY is the real safety
                           # line and still outranks the sign completely; this
                           # is only meant to stop a DISTANT sign causing a
                           # full-lock charge at a wall.
SIGN_STEER_HOLD_S= 0.9     # of that hold, keep steering as the sign commanded
                           # for this long, then run straight for the remainder

# --- corner-exit kick ---
# When a corner is counted AND the last sign pushed the car toward the INNER
# wall, fire a fixed hard turn so the next section comes into view.
#     CW  : inner wall is RIGHT, RED   pushes the car right -> kick RIGHT
#     CCW : inner wall is LEFT,  GREEN pushes the car left  -> kick LEFT
CORNER_KICK      = True
KICK_ANGLE       = 35.0    # deg. May exceed STEER_MAX (20) - that is the point.
                           # Hard ceiling is the linkage, STEER_MECH_MAX = 35.
KICK_TIME_S      = 1     # how long to hold it. Longer = tighter turn.
KICK_SPEED       = 100      # % speed during the kick
KICK_SIGN_CW     = "red"   # sign colour that arms the kick when running CW
KICK_SIGN_CCW    = "green" # ...and when running CCW

# --- recording the order of signs passed ---
PASS_MIN_AREA    = 300     # a sign must have got this big to count as passed
PASS_LOST_S      = 3     # ...and then be gone this long
PASS_COOLDOWN_S  = 0.8     # ignore a re-detection of the SAME colour this soon

# --- frame saving ---
SAVE_FRAMES      = True
MAX_SAVES        = 120

# --- run control ---
STOP_ON_LAPS     = True    # True = stop by itself after the quadrants below.
                           # False = run until the button is pressed.
STOP_AFTER_QUADRANT = 11   # 12 corners = 3 laps. Stopping after 11 plus the
                           # coast below leaves the car resting in the start
                           # section rather than halting on the line.
STOP_EXTRA_S     = 3.0     # how long to keep driving past that last corner
MAX_RUNTIME_S    = 300     # SAFETY net
DEBUG_EVERY      = 15      # console status line every N frames (0 = silent)

# WHEN THE PARKING EXIT DECIDES THE DIRECTION, ONE MORE QUADRANT IS NEEDED.
# Normally the direction is learned by CROSSING the first corner line, and that
# crossing is itself quadrant 1 - so the count and the distance travelled line
# up. Starting from the parking lot, the direction is already known before the
# car has crossed anything, so that first line is still ahead of it: without
# this the car would stop one corner short of where it should.
STOP_QUADRANT = STOP_AFTER_QUADRANT + (1 if PARK_START else 0)

# ==========================================================================

Y_SCALE = 120.0 / R.PROC_H   # map our 160-row frame onto the 120-row reference

# Everything that differs between the two sign colours, in one place, so adding
# a third colour for the surprise challenge is a new entry rather than a new
# branch in every function.
SIGN = {
    "green": dict(kp=GREEN_KP, target_x=GREEN_TARGET_X,
                  min_area=GREEN_MIN_AREA, min_aspect=GREEN_MIN_ASPECT),
    "red":   dict(kp=RED_KP,   target_x=RED_TARGET_X,
                  min_area=RED_MIN_AREA,   min_aspect=RED_MIN_ASPECT),
}


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
        cfg = SIGN[kind]
        m = R.mask(hsv, kind)
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            area = cv2.contourArea(c)
            if area < cfg["min_area"] or (best and area <= best[3]):
                continue
            x, y, w, h = cv2.boundingRect(c)
            if h < w * cfg["min_aspect"]:
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
    tx = SIGN[kind]["target_x"]
    if kind == "green":
        return -((tx + y * Y_GAIN) - cx)
    return cx - (tx - y * Y_GAIN)


def limit_toward_wall(steer, left, right):
    """Fade a steering command out as it aims at a wall that is already close.

    The sign law does not know walls exist - it will command full lock to place
    a sign, and in a 3 m corridor that means driving into the wall until the
    escape fires and the two fight. Measured on a failed run: 37% of frames
    past the escape threshold, the sign law asking -20 deg while the left wall
    read 0.20 against 0.213.

    It fades to SIGN_WALL_FLOOR, NOT to zero - see that setting for why. The
    ESCAPE is the real safety line and outranks the sign entirely; this only
    stops a DISTANT sign causing a full-lock charge at a wall.
    """
    approaching = left if steer < 0 else right   # -steer = left = the LEFT wall
    start = R.WALL_EMERGENCY * SIGN_WALL_GUARD
    if approaching <= start:
        return steer
    span = max(1e-6, R.WALL_EMERGENCY - start)
    frac = min(1.0, (approaching - start) / span)
    # fade DOWN TO THE FLOOR, never to nothing. A GREEN sign is passed on its
    # LEFT, and in CW the outer wall IS on the left - so a green pass steers
    # toward a wall by geometry, not by mistake. Fading to zero meant the car
    # could never finish one: measured, 226 of 388 green-steering frames were
    # being faded, and when green was closest the left wall sat at 0.172, right
    # in the middle of the fade band.
    keep = 1.0 - (1.0 - SIGN_WALL_FLOOR) * frac
    return steer * keep


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
        steer = sign_error(kind, sx, sy) * SIGN[kind]["kp"]
        steer = limit_toward_wall(steer, view.left, view.right)
        hold["kind"], hold["t"], hold["steer"] = kind, now, steer
        return Decision(steer, "sign-" + kind, kind, sx, sy, area, None, None)

    # ---- 4. HOLD ----
    if hold["kind"] and (now - hold["t"]) < SIGN_HOLD_S:
        if (now - hold["t"]) < SIGN_STEER_HOLD_S:
            steer = limit_toward_wall(hold["steer"], view.left, view.right)
            mode = "sign-hold"
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
    laps.stop_quadrant = STOP_QUADRANT
    outer = R.OuterWallFollower(target=LANE_TARGET)
    passes = PassLogger()
    rec = R.FrameRecorder(enabled=SAVE_FRAMES, max_saves=MAX_SAVES)
    kick = R.CornerKick(angle=KICK_ANGLE, duration_s=KICK_TIME_S,
                        speed=KICK_SPEED, sign_cw=KICK_SIGN_CW,
                        sign_ccw=KICK_SIGN_CCW, enabled=CORNER_KICK)
    park = R.ParkingExit(angle=PARK_ANGLE, time_s=PARK_TIME_S,
                         speed=PARK_SPEED, settle_frames=PARK_SETTLE,
                         min_magenta=PARK_MIN_MAGENTA,
                         use_wall=PARK_USE_WALL, enabled=PARK_START,
                         invert=PARK_INVERT)
    hold = {"kind": "", "t": -1e9, "steer": 0.0}
    last_mode = ""
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
    print(f"  green     : kp={GREEN_KP} ->x{GREEN_TARGET_X:.0f} "
          f"area>{GREEN_MIN_AREA} aspect>{GREEN_MIN_ASPECT}")
    print(f"  red       : kp={RED_KP} ->x{RED_TARGET_X:.0f} "
          f"area>{RED_MIN_AREA} aspect>{RED_MIN_ASPECT}")
    print(f"  parking   : {'ON' if PARK_START else 'OFF'} "
          f"{PARK_ANGLE:.0f}deg for {PARK_TIME_S:.1f}s @ {PARK_SPEED}%  "
          f"(more magenta LEFT -> out RIGHT -> CW)")
    print(f"  kick      : {'ON' if CORNER_KICK else 'OFF'} {KICK_ANGLE:.0f}deg "
          f"for {KICK_TIME_S:.1f}s @ {KICK_SPEED}%  "
          f"(CW<-{KICK_SIGN_CW}, CCW<-{KICK_SIGN_CCW})")
    print(f"  lines     : orange>{R.LINE_FRACTION_ORANGE:.3f} "
          f"blue>{R.LINE_FRACTION_BLUE:.3f}")
    print(f"  speed     : {CRUISE}%")
    print(f"  stop      : " + (
        f"after quadrant {STOP_QUADRANT} + {STOP_EXTRA_S:.1f}s"
        f"  ({STOP_AFTER_QUADRANT}"
        + (" +1 because the parking exit sets the direction)" if PARK_START else ")")
        if STOP_ON_LAPS else "button only"))
    print(f"  log       : {logpath}")

    button.wait_for_start("Obstacle Challenge")

    t0 = time.time()
    frame = 0
    reason = "?"
    R.motor(CRUISE)
    try:
        while True:
            frame += 1
            now = time.time()

            # ---------------- LOOK ----------------
            view = R.look(cam)
            before, had_dir = laps.quadrant, laps.direction
            laps.update(view.blue, view.orange, view.left, view.right, view.front)

            sign = find_sign(view.hsv)
            passes.update(sign, now)
            t = now - t0

            # the direction: the one decision the whole run rests on
            if had_dir == 0 and laps.direction != 0:
                rec.moment(view, "direction-%s" % ("CW" if laps.direction > 0 else "CCW"),
                           t, lines=["DIRECTION LOCKED %s" % laps.direction_source,
                                     "blue %.4f  orange %.4f" % (view.blue, view.orange)])
            # each sign, the FIRST time that colour appears in this approach
            if sign is not None:
                k, sx, sy, area, bb = sign
                if k != last_sign_kind:
                    col = (0, 0, 255) if k == "red" else (0, 255, 0)
                    rec.moment(view, "sign-%s-first" % k, t,
                               lines=["%s FIRST SEEN  area %d" % (k.upper(), int(area)),
                                      "at x=%.0f y=%.0f -> target x=%.0f"
                                      % (sx, sy, SIGN[k]["target_x"]),
                                      "L %.3f  R %.3f" % (view.left, view.right)],
                               boxes=[(bb[0], bb[1], bb[2], bb[3], col, k)])
                last_sign_kind = k

            if laps.quadrant > before:
                rec.moment(view, "quadrant-%02d" % laps.quadrant, t,
                           lines=["QUADRANT %d of %d" % (laps.quadrant, STOP_QUADRANT),
                                  "blue %.4f  orange %.4f" % (view.blue, view.orange)])
            # a corner was just counted -> maybe kick out of it
            if laps.quadrant > before:
                if kick.maybe_fire(laps.direction, last_sign_kind, now):
                    last_sign_kind = ""      # consumed; don't re-fire next corner

            # ---------------- THINK ----------------
            prev_mode = last_mode
            d = decide(now, view, sign, hold, kick, outer, laps.direction, park)
            last_mode = d.mode
            # each escape, kick and parking phase, once as it starts
            if d.mode != prev_mode and d.mode in (
                    "wall", "kick", "park-look", "park-exit"):
                rec.moment(view, "%s-%05.1fs" % (d.mode, t), t,
                           lines=["%s  steer %+.1f" % (d.mode.upper(), d.steer),
                                  "L %.3f  R %.3f  (escape at %.3f)"
                                  % (view.left, view.right, R.WALL_EMERGENCY)])
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
            if STOP_ON_LAPS and laps.ready_to_finish(STOP_EXTRA_S):
                reason = (f"{laps.quadrant} quadrants + {STOP_EXTRA_S:.1f}s coast")
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
        idx = rec.write_index()
        print(f"  decisive frames   : {rec.saved} -> frames/")
        if idx:
            print(f"  what happened     : {idx}")
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
