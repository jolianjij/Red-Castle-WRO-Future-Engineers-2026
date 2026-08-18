#!/usr/bin/env python3
"""
dryrun.py - run BOTH challenges' decision paths against the real camera,
WITHOUT touching the motor. The car will not move.

This is the last check before a real run: it proves decide() survives real
camera frames, which tools/test_logic.py (synthetic numbers) cannot.

    cd ~/wro2026 && source .venv/bin/activate && python tools/dryrun.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import robot as R                  # noqa: E402
import open_challenge as OPEN      # noqa: E402
import obstacle_challenge as OBS   # noqa: E402

FRAMES = 40


def run_open(cam):
    print("\n--- OPEN CHALLENGE decision path ---")
    laps = R.LapTracker()
    outer = R.OuterWallFollower(target=OPEN.LANE_TARGET)
    turner = R.TurnSequencer()
    modes = {}
    for i in range(FRAMES):
        v = R.look(cam)
        before = laps.quadrant
        laps.update(v.blue, v.orange, v.left, v.right, v.front)
        if laps.quadrant > before:
            turner.trigger(laps.direction)
        d = OPEN.decide(v, laps, outer, turner)
        speed = R.cruise_speed(OPEN.CRUISE, d.steer)
        modes[d.mode] = modes.get(d.mode, 0) + 1
        if i % 10 == 0:
            print(f"  {i:2d}: {d.mode:10s} steer={d.steer:+6.1f} speed={speed:3.0f} "
                  f"L={v.left:.3f} R={v.right:.3f} front={v.front:.3f} "
                  f"blue={v.blue:.3f} orange={v.orange:.3f}")
        time.sleep(0.03)
    print(f"  modes: {modes}")
    print(f"  fusion: {laps.summary()}")


def run_obstacle(cam):
    print("\n--- OBSTACLE CHALLENGE decision path ---")
    laps = R.LapTracker()
    if OBS.FORCE_DIRECTION:
        laps.set_direction(OBS.FORCE_DIRECTION, "FORCE_DIRECTION")
    outer = R.OuterWallFollower(target=OBS.LANE_TARGET)
    passes = OBS.PassLogger()
    kick = R.CornerKick(angle=OBS.KICK_ANGLE, duration_s=OBS.KICK_TIME_S,
                        speed=OBS.KICK_SPEED, sign_cw=OBS.KICK_SIGN_CW,
                        sign_ccw=OBS.KICK_SIGN_CCW, enabled=OBS.CORNER_KICK)
    park = R.ParkingExit(angle=OBS.PARK_ANGLE, time_s=OBS.PARK_TIME_S,
                         speed=OBS.PARK_SPEED, settle_frames=OBS.PARK_SETTLE,
                         min_magenta=OBS.PARK_MIN_MAGENTA,
                         use_wall=OBS.PARK_USE_WALL, enabled=OBS.PARK_START)
    hold = {"kind": "", "t": -1e9, "steer": 0.0}
    last_kind = ""
    modes = {}
    for i in range(FRAMES):
        now = time.time()
        v = R.look(cam)
        before = laps.quadrant
        laps.update(v.blue, v.orange, v.left, v.right, v.front)
        sign = OBS.find_sign(v.hsv)
        passes.update(sign, now)
        if sign is not None:
            last_kind = sign[0]
        if laps.quadrant > before and kick.maybe_fire(laps.direction, last_kind, now):
            last_kind = ""
        d = OBS.decide(now, v, sign, hold, kick, outer, laps.direction, park)
        if park.direction and laps.direction == 0:
            laps.set_direction(park.direction, "parking-lot exit")
        steer = OBS.clamp_steer(d.steer, d.servo_limit)
        speed = d.speed_cap if d.speed_cap is not None \
            else R.cruise_speed(OBS.CRUISE, steer)
        modes[d.mode] = modes.get(d.mode, 0) + 1
        if i % 10 == 0:
            print(f"  {i:2d}: {d.mode:10s} steer={steer:+6.1f} speed={speed:3.0f} "
                  f"L={v.left:.3f} R={v.right:.3f} sign={d.kind or '-':5s} "
                  f"area={int(d.area)}")
        time.sleep(0.03)
    print(f"  modes: {modes}")
    print(f"  sign order: {passes.finish(time.time()) or '(none)'}")
    print(f"  kicks fired: {kick.fired}")
    print(f"  parking exit: direction="
          f"{'CW' if park.direction > 0 else 'CCW' if park.direction else 'none'}"
          f"  ({park.reason or 'ran normally'})")


def main():
    R.setup_hardware()
    R.servo(0)
    cam = R.open_camera()
    time.sleep(0.6)
    print("DRY RUN - the motor is never touched, the car will not move.")
    try:
        run_open(cam)
        run_obstacle(cam)
        print(f"\n*** both decision paths ran {FRAMES} camera frames each, "
              f"no exception ***")
    finally:
        cam.close()
        R.shutdown()


if __name__ == "__main__":
    main()
