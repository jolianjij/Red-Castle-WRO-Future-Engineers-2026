#!/usr/bin/env python3
"""
open_challenge.py - WRO 2026 Future Engineers, OPEN CHALLENGE.
Three laps of an empty track. No traffic signs.

=========================== HOW THIS FILE WORKS ===========================
Every challenge program here has the SAME three parts, in the same order.
Learn them once and you can write the surprise challenge yourself:

    1. TUNABLES   the numbers you change.  Nothing else needs editing.
    2. decide()   the brain: ONE frame in, one steering decision out.
                  Pure logic - no camera, no motor - so it can be tested
                  on a laptop with tools/test_logic.py.
    3. main()     the loop: LOOK -> THINK -> ACT, over and over.

To write a new challenge: copy this file, rewrite decide(), leave main()
almost alone. See src/README.md.
===========================================================================

Run on the Pi:
    cd ~/wro2026 && source .venv/bin/activate && python open_challenge.py
Then PRESS THE BUTTON to start. Press it again to stop.
"""
import collections
import csv
import os
import time

import robot as R

# ==========================================================================
# 1. TUNABLES - everything you might want to change lives here
# ==========================================================================

# --- speed ---
CRUISE           = 100     # base speed %. Falls automatically with steering,
                           # so this is the straight-line figure.

# --- direction ---
FORCE_DIRECTION  = 0       # 0 = detect from the corner lines (normal).
                           # +1 forces CW, -1 forces CCW. Only set this if the
                           # judges tell you the run direction.

# --- how far from the outer wall to drive ---
LANE_DISTANCE_CM = 30.0    # hold this far from the OUTER wall on the straights
# density = 0.1032 at 40 cm, slope 0.00501 per cm closer (measured on this car)
LANE_TARGET      = 0.1032 - (LANE_DISTANCE_CM - 40.0) * 0.00501

# --- corners: WALL DENSITY decides when to turn ---
# The corner LINES are used for COUNTING LAPS ONLY. They do not steer the car.
# Why: the lines are a colour measurement, and a colour that drifts takes the
# steering with it. Measured on this track, blue was over its threshold on 43%
# of frames - it was matching the mat, not the line - so anything steering off
# it was being told to corner in the middle of a straight. The wall ahead is a
# geometric measurement: it cannot be fooled by a colour range being wrong.
TURN_ON_FRONT    = 0.30    # front wall fill that STARTS a corner turn. Bigger
                           # = turns later (closer to the wall). This is now the
                           # ONLY thing that triggers a turn.
TURN_OFF_FRONT   = 0.20    # ...and the fill it must drop below to END it. Kept
                           # well under TURN_ON_FRONT so a noisy reading cannot
                           # flicker the turn on and off.
TURN_BLIND       = True    # turn even BEFORE the direction is known, toward
                           # whichever side has more room. Without this the car
                           # drives straight into the first corner while it
                           # waits for a line it may never read - and with the
                           # lines now only counting, it might wait a long time.
TURN_MIN_GAP_S   = 1.5     # a corner cannot physically follow another sooner
                           # than this, so ignore a re-trigger inside it

# --- run control ---
STOP_AFTER_QUADRANT = 11   # 12 corners = 3 laps. Stopping after 11 + the coast
                           # below leaves the car resting in the start section.
STOP_EXTRA_S     = 2.5     # HOW LONG THE CAR KEEPS DRIVING after that last
                           # corner is counted, before it stops. Raise it to
                           # finish further round the section; lower it to stop
                           # sooner. It used to be tied to the lap debounce
                           # timer, which meant you could not change one without
                           # changing the other.
MAX_RUNTIME_S    = 150     # SAFETY net only, not a lap limit
DEBUG_EVERY      = 15      # console status line every N frames (0 = silent)

# --- decisive frames ---
# Not every frame: the ones where the run was DECIDED and could have gone
# wrong. They land in frames/ with a 00-WHAT-HAPPENED.txt index.
SAVE_MOMENTS     = True
MAX_MOMENT_SAVES = 200

# Corner lines live in config.py because BOTH challenges need the same values:
#     R.LINE_FRACTION_ORANGE   lower bar - orange is faint on this camera
#     R.LINE_FRACTION_BLUE     higher bar - blue over-triggers on background
#     R.LINE_DIR_MIN_RATIO     how decisively one must beat the other
# ==========================================================================

R.STOP_AFTER_QUADRANT = STOP_AFTER_QUADRANT


# ==========================================================================
# 2. THE BRAIN - one frame in, one decision out
# ==========================================================================
Decision = collections.namedtuple("Decision", "steer mode")


def decide(view, laps, outer, turner):
    """Return (steer_deg, mode) for this frame. +steer = right.

    PRIORITY LADDER - highest first, exactly one branch answers:

        1. EMERGENCY  a wall is too close -> escape. Outranks everything.
        2. TURN       a wall AHEAD means a corner. Geometric, so it needs no
                      colour tuning and cannot be faked by lighting. The lines
                      are for COUNTING laps only.
        3. LANE       normal driving: PD on the distance to the OUTER wall.

    Why the outer wall and not the middle: in this challenge the inner walls
    move every round, so the corridor width changes. Centring chases a moving
    reference; the outer wall is the one thing that stays put.

    THE CORNER LINES DO NOT APPEAR HERE AT ALL. They count laps and nothing
    else. Turning is decided by the wall ahead, which is a geometric fact rather
    than a colour measurement, so a drifting colour range can no longer steer
    the car.
    """
    # ---- 1. EMERGENCY ----
    escape = R.wall_emergency(view.left, view.right, outer, laps.direction)
    if escape is not None:
        return Decision(escape, "emergency")

    # ---- 2. TURN ----
    # Fired by the WALL AHEAD, never by a line. The line count and the steering
    # are now completely independent, so a bad colour range can cost a lap
    # count but can no longer make the car turn in the wrong place.
    turner.update(view.front)
    if turner.active:
        return Decision(turner.steer(), "turn")
    if view.front > TURN_ON_FRONT:
        if laps.direction != 0:
            turner.trigger(laps.direction)
            return Decision(turner.steer(), "turn")
        if TURN_BLIND:
            # No direction yet. A wall ahead still has to be dealt with, and
            # driving into it while waiting for a line is the worse option, so
            # turn toward whichever side has more ROOM.
            return Decision(R.STEER_MAX * (1 if view.left > view.right else -1),
                            "turn-blind")

    # ---- 3. LANE ----
    return Decision(R.apply_bias(outer.steer(view.left, view.right, laps.direction)),
                    "lane")


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
    turner = R.TurnSequencer(exit_front=TURN_OFF_FRONT,
                             min_gap_s=TURN_MIN_GAP_S)
    rec = R.FrameRecorder(enabled=SAVE_MOMENTS, max_saves=MAX_MOMENT_SAVES)

    os.makedirs("logs", exist_ok=True)
    logpath = time.strftime("logs/open_%Y%m%d_%H%M%S.csv")
    logf = open(logpath, "w", newline="")
    log = csv.writer(logf)
    log.writerow(["t_ms", "frame", "dir", "quad", "mode",
                  "left", "right", "front", "blue", "orange", "steer", "speed"])

    print("OPEN CHALLENGE")
    print(f"  direction : {'FORCED ' + ('CW' if FORCE_DIRECTION > 0 else 'CCW')}"
          if FORCE_DIRECTION else "  direction : auto from the corner lines")
    print(f"  lane      : {LANE_DISTANCE_CM:.0f} cm from the outer wall "
          f"(density {LANE_TARGET:.4f})")
    print(f"  turns     : {'blind before direction known, ' if TURN_BLIND else ''}"
          f"on front wall > {TURN_ON_FRONT}, ends below "
          f"{TURN_OFF_FRONT}  (lines do NOT steer)")
    print(f"  lines     : COUNTING ONLY.  orange>{R.LINE_FRACTION_ORANGE:.3f} "
          f"blue>{R.LINE_FRACTION_BLUE:.3f} ratio>{R.LINE_DIR_MIN_RATIO:.2f}")
    print(f"  speed     : {CRUISE}%   stop after quadrant "
          f"{STOP_AFTER_QUADRANT} + {STOP_EXTRA_S:.1f}s")
    print(f"  log       : {logpath}")

    button.wait_for_start("Open Challenge")

    t0 = time.time()
    frame = 0
    reason = "?"
    mode = ""
    R.motor(CRUISE)
    try:
        while True:
            frame += 1

            # ---------------- LOOK ----------------
            view = R.look(cam)
            before, had_dir = laps.quadrant, laps.direction
            laps.update(view.blue, view.orange, view.left, view.right, view.front)
            t = time.time() - t0

            # THE decision of the whole run: which way round the track.
            if had_dir == 0 and laps.direction != 0:
                rec.moment(view, "direction-%s" % ("CW" if laps.direction > 0 else "CCW"),
                           t, lines=["DIRECTION LOCKED %s" % laps.direction_source,
                                     "blue %.4f  orange %.4f" % (view.blue, view.orange),
                                     "L %.3f  R %.3f" % (view.left, view.right)])
            if laps.quadrant > before:
                # COUNTING ONLY. The turn is fired by the wall ahead, in decide().
                rec.moment(view, "quadrant-%02d" % laps.quadrant, t,
                           lines=["QUADRANT %d of %d" % (laps.quadrant, R.STOP_AFTER_QUADRANT),
                                  "blue %.4f  orange %.4f" % (view.blue, view.orange),
                                  "front %.3f" % view.front])

            # ---------------- THINK ----------------
            prev_mode = mode
            d = decide(view, laps, outer, turner)
            mode = d.mode
            speed = R.cruise_speed(CRUISE, d.steer)

            # each ESCAPE and each TURN, once at the moment it starts
            if d.mode != prev_mode and d.mode in ("emergency", "turn", "turn-blind"):
                rec.moment(view, "%s-%s" % (d.mode, "%05.1fs" % t), t,
                           lines=["%s  steer %+.1f" % (d.mode.upper(), d.steer),
                                  "L %.3f  R %.3f  (escape at %.3f)"
                                  % (view.left, view.right, R.WALL_EMERGENCY),
                                  "front %.3f" % view.front])

            # ---------------- ACT ----------------
            R.servo(d.steer)
            R.motor(speed)

            # ---------------- RECORD / FINISH ----------------
            t_ms = int((time.time() - t0) * 1000)
            log.writerow([t_ms, frame, laps.direction, laps.quadrant, d.mode,
                          f"{view.left:.3f}", f"{view.right:.3f}",
                          f"{view.front:.3f}", f"{view.blue:.3f}",
                          f"{view.orange:.3f}", f"{d.steer:.1f}", f"{speed:.0f}"])
            if DEBUG_EVERY and frame % DEBUG_EVERY == 0:
                logf.flush()
                print(f"  t={t_ms/1000:5.1f}s dir={laps.direction:+d} "
                      f"q={laps.quadrant:2d} {d.mode:10s} "
                      f"L={view.left:.3f} R={view.right:.3f} steer={d.steer:+6.1f}")

            if button.stop_pressed():
                reason = "BUTTON pressed"
                break
            if laps.ready_to_finish(STOP_EXTRA_S):
                reason = (f"{laps.quadrant} quadrants + {STOP_EXTRA_S:.1f}s coast")
                break
            if time.time() - t0 > MAX_RUNTIME_S:
                reason = "SAFETY timeout"
                break

    except KeyboardInterrupt:
        reason = "Ctrl+C"
    finally:
        R.motor(0)
        R.servo(0)
        dt = time.time() - t0
        print(f"\nFINISHED ({reason})  quadrants={laps.quadrant}  "
              f"{frame} frames  {dt:.1f}s  {1000*dt/max(frame,1):.1f} ms/frame")
        print(f"  fusion: {laps.summary()}")
        idx = rec.write_index()
        if idx:
            print(f"  decisive frames: {rec.saved} -> frames/  (index: {idx})")
        log.writerow([])
        log.writerow(["#", reason, laps.summary()])
        logf.flush()
        logf.close()
        R.shutdown()
        cam.close()
        print(f"  log saved: {logpath}")


if __name__ == "__main__":
    main()
