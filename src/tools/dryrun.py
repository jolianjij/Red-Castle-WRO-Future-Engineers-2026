"""Exercise the FULL navigate() path with the camera but WITHOUT touching the motor."""
import time, robot as R
cam = R.open_camera(); time.sleep(0.6)
laps = R.LapTracker(); follower = R.WallFollower()
outer = R.OuterWallFollower(); turner = R.TurnSequencer()
print("dry run - navigate() called exactly as open_challenge does, motor untouched\n")
modes = {}
for i in range(40):
    proc, hsv = R.read_hsv(cam)
    left, right = R.wall_readings(hsv)
    front = R.front_reading(hsv)
    blue, orange = R.line_counts(hsv)
    q0 = laps.quadrant
    laps.update(blue, orange, left, right, front)
    if laps.quadrant > q0 and R.NAV_METHOD == "outer":
        turner.trigger(laps.direction)
    steer, mode = R.navigate(hsv, left, right, laps, follower, outer,
                             turner, front > R.FRONT_TURN_BACKUP, front)
    speed = R.cruise_speed(100, steer)
    modes[mode] = modes.get(mode, 0) + 1
    if i % 10 == 0:
        print("  %2d: mode=%-14s steer=%+6.1f speed=%3.0f  L=%.3f R=%.3f front=%.3f"
              % (i, mode, steer, speed, left, right, front))
    time.sleep(0.03)
cam.close()
print("\n  modes seen:", modes)
print("  fusion:", laps.summary())
print("\n  *** navigate() ran 40 frames with no exception ***")
