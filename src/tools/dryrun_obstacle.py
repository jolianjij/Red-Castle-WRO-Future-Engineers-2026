"""Exercise the FULL obstacle loop with the camera but WITHOUT touching the motor.

Mirrors obstacle_challenge.main()'s per-frame path exactly, so a NameError or a
bad variable in the real loop shows up here instead of on the track.
"""
import time

import robot as R
import obstacle_challenge as OC

cam = R.open_camera()
time.sleep(0.6)
laps = R.LapTracker()
outer = R.OuterWallFollower(target=OC.LANE_TARGET)
passes = OC.PassLogger()
kick = R.CornerKick(angle=OC.KICK_ANGLE, duration_s=OC.KICK_TIME_S,
                    speed=OC.KICK_SPEED, sign_cw=OC.KICK_SIGN_CW,
                    sign_ccw=OC.KICK_SIGN_CCW, enabled=OC.CORNER_KICK)
hold = {"kind": "", "t": -1e9, "steer": 0.0}
last_sign_kind = ""
if OC.FORCE_CW:
    laps.direction = 1

print("dry run - obstacle decision path, motor untouched")
print(f"  kick {'ON' if OC.CORNER_KICK else 'OFF'} "
      f"{OC.KICK_ANGLE}deg/{OC.KICK_TIME_S}s  CW<-{OC.KICK_SIGN_CW} "
      f"CCW<-{OC.KICK_SIGN_CCW}")
print(f"  lines orange>{R.LINE_FRACTION_ORANGE} blue>{R.LINE_FRACTION_BLUE}\n")

modes = {}
for i in range(40):
    now = time.time()
    proc, hsv = R.read_hsv(cam)
    left, right = R.wall_readings(hsv)
    front = R.front_reading(hsv)
    blue, orange = R.line_counts(hsv)
    q0 = laps.quadrant
    laps.update(blue, orange, left, right, front)

    sign = OC.find_sign(hsv)
    passes.update(sign, now)
    if sign is not None:
        last_sign_kind = sign[0]
    if laps.quadrant > q0:
        if kick.maybe_fire(laps.direction, last_sign_kind, now):
            last_sign_kind = ""

    d = OC.decide(now, sign, hold, kick, outer, left, right, laps.direction)
    steer = OC.clamp_steer(d.steer, d.servo_limit)
    speed = d.speed_cap if d.speed_cap is not None \
        else R.cruise_speed(OC.CRUISE, steer)
    modes[d.mode] = modes.get(d.mode, 0) + 1
    if i % 10 == 0:
        print("  %2d: mode=%-11s steer=%+6.1f speed=%3.0f  L=%.3f R=%.3f "
              "blue=%.3f orange=%.3f sign=%s"
              % (i, d.mode, steer, speed, left, right, blue, orange,
                 d.kind or "-"))
    time.sleep(0.03)

cam.close()
print("\n  modes seen:", modes)
print("  sign order:", passes.finish(time.time()) or "(none)")
print("  kicks fired:", kick.fired)
print("  fusion:", laps.summary())
print("\n  *** obstacle decision path ran 40 frames with no exception ***")
