#!/usr/bin/env python3
"""
test_logic.py - offline tests for the decision logic. NO Pi, NO camera.

Runs on a laptop. It stubs RPi.GPIO and picamera2 so robot.py imports, then
drives the real classes with synthetic numbers and asserts on the results.

py_compile only proves a file parses; it does not prove `navigate()` can run
without a NameError. This does. Run it before every deploy.

    python src/tools/test_logic.py
"""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---- stub the Pi-only modules so robot.py can be imported on a laptop ----
gpio = types.ModuleType("RPi.GPIO")
for _n in ("BCM", "OUT", "HIGH", "LOW"):
    setattr(gpio, _n, 0)
gpio.setmode = gpio.setwarnings = gpio.setup = gpio.cleanup = lambda *a, **k: None
gpio.output = lambda *a, **k: None


class _PWM:
    def __init__(self, *a):
        self.duty = 0.0

    def start(self, d):
        self.duty = d

    def ChangeDutyCycle(self, d):
        self.duty = d

    def stop(self):
        pass


gpio.PWM = _PWM
rpi = types.ModuleType("RPi")
rpi.GPIO = gpio
sys.modules["RPi"], sys.modules["RPi.GPIO"] = rpi, gpio
pc2 = types.ModuleType("picamera2")
pc2.Picamera2 = object
sys.modules["picamera2"] = pc2
lt = types.ModuleType("libcamera")
lt.Transform = lambda **k: None
sys.modules["libcamera"] = lt

import robot as R  # noqa: E402

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: got {got!r}, want {want!r}")
    if not ok:
        FAILED.append(name)


def section(t):
    print(f"\n=== {t} ===")


# ==========================================================================
section("per-colour line thresholds")
print(f"  orange bar {R.LINE_FRACTION_ORANGE}   blue bar {R.LINE_FRACTION_BLUE}")

# THE BUG THIS FIXES: a real orange crossing, with background blue bleeding in.
# Raw pixels say blue wins (0.030 > 0.025) -> the old code locked CCW on a CW
# run. By confidence, orange is 2.08x its bar and blue only 0.86x of its own.
t = R.LapTracker()
t.direction = 0
t.update(blue_frac=0.030, orange_frac=0.025, left=0.10, right=0.05, front=0.15)
check("orange crossing + blue bleed -> CW", t.direction, 1)

# a genuine blue crossing must still lock CCW
t = R.LapTracker()
t.direction = 0
t.update(blue_frac=0.090, orange_frac=0.002, left=0.05, right=0.10, front=0.15)
check("clean blue crossing -> CCW", t.direction, -1)

# blue below its higher bar, orange below its lower bar = no decision at all
t = R.LapTracker()
t.direction = 0
t.update(blue_frac=0.030, orange_frac=0.008, left=0.05, right=0.05, front=0.10)
check("both under their own bars -> undecided", t.direction, 0)

# both convincing at once = ambiguous, must WAIT rather than guess
t = R.LapTracker()
t.direction = 0
t.update(blue_frac=0.040, orange_frac=0.014, left=0.05, right=0.05, front=0.10)
check("both convincing -> stays undecided", t.direction, 0)

# ...and a later clean frame still resolves it
t.update(blue_frac=0.001, orange_frac=0.030, left=0.10, right=0.05, front=0.10)
check("...then a clean orange frame -> CW", t.direction, 1)

# ==========================================================================
section("CornerKick - which sign arms it")
k = R.CornerKick(angle=30.0, duration_s=0.9, speed=55,
                 sign_cw="red", sign_ccw="green")
check("CW trigger colour", k.trigger_colour(1), "red")
check("CCW trigger colour", k.trigger_colour(-1), "green")

now = 1000.0
check("CW + red fires", k.maybe_fire(1, "red", now), True)
check("kick is active", k.active(now + 0.5), True)
steer, limit, speed = k.command()
check("CW kick steers RIGHT (+)", steer > 0, True)
check("CW kick angle", steer, 30.0)
check("kick raises the servo ceiling", limit, 30.0)
check("kick uses its own speed", speed, 55)
check("kick expires", k.active(now + 1.0), False)

k2 = R.CornerKick(sign_cw="red", sign_ccw="green")
check("CCW + green fires", k2.maybe_fire(-1, "green", now), True)
check("CCW kick steers LEFT (-)", k2.command()[0] < 0, True)

k3 = R.CornerKick(sign_cw="red", sign_ccw="green")
check("CW + green does NOT fire", k3.maybe_fire(1, "green", now), False)
check("CCW + red does NOT fire", k3.maybe_fire(-1, "red", now), False)
check("no sign does NOT fire", k3.maybe_fire(1, "", now), False)
check("unknown direction does NOT fire", k3.maybe_fire(0, "red", now), False)

k4 = R.CornerKick(sign_cw="red", sign_ccw="green", enabled=False)
check("disabled never fires", k4.maybe_fire(1, "red", now), False)

# ==========================================================================
section("servo() ceiling")
R.setup_hardware()
R.servo(30.0)                      # no limit -> clamped to STEER_MAX
check("30deg without limit clamps to STEER_MAX", R.STEER_MAX, 20)
R.servo(30.0, limit=30.0)          # kick path -> allowed through
R.servo(99.0, limit=99.0)          # never past the linkage limit
print(f"  STEER_MAX={R.STEER_MAX}  STEER_MECH_MAX={R.STEER_MECH_MAX}")
check("mech limit is the hard ceiling", R.STEER_MECH_MAX, 35)

# ==========================================================================
section("obstacle priority ladder")
import obstacle_challenge as OC  # noqa: E402

check("CW, left wall close -> hard right", OC.wall_override(1, 0.30, 0.01), R.STEER_MAX)
check("CW, right wall close -> hard left", OC.wall_override(1, 0.01, 0.30), -R.STEER_MAX)
check("CCW, right wall close -> hard left", OC.wall_override(-1, 0.01, 0.30), -R.STEER_MAX)
check("clear track -> no override", OC.wall_override(1, 0.01, 0.01), None)
check("opposes(+20,-30)", OC.opposes(20, -30), True)
check("opposes(+20,+30)", OC.opposes(20, 30), False)
check("opposes(None,+30)", OC.opposes(None, 30), False)

# the safety case: kick pulls right, a wall is closing from the right
kk = R.CornerKick(sign_cw="red", sign_ccw="green")
kk.maybe_fire(1, "red", now)
wall = OC.wall_override(1, 0.01, 0.30)          # -> hard LEFT
check("wall opposing the kick wins", OC.opposes(wall, kk.command()[0]), True)

# ==========================================================================
section("decide() - the full ladder, in priority order")


class FakeOuter:
    def steer(self, left, right, direction):
        return 3.3


fo = FakeOuter()
T = 5000.0


def fresh_hold():
    return {"kind": "", "t": -1e9, "steer": 0.0}


# 5. LANE - nothing happening
kq = R.CornerKick(sign_cw="red", sign_ccw="green")
d = OC.decide(T, None, fresh_hold(), kq, fo, 0.01, 0.01, 1)
check("clear track -> lane", d.mode, "lane")
check("lane uses the outer follower", d.steer, 3.3)

# 4. HOLD - a sign was here 0.2s ago (inside SIGN_STEER_HOLD_S)
h = {"kind": "red", "t": T - 0.2, "steer": -8.0}
d = OC.decide(T, None, h, kq, fo, 0.01, 0.01, 1)
check("recent sign -> sign-hold", d.mode, "sign-hold")
check("sign-hold keeps the sign's steer", d.steer, -8.0)

# 4b. HOLD, later - past the steer hold, still inside SIGN_HOLD_S -> straight
h = {"kind": "red", "t": T - 1.5, "steer": -8.0}
d = OC.decide(T, None, h, kq, fo, 0.01, 0.01, 1)
check("hold elapsed -> sign-clear", d.mode, "sign-clear")
check("sign-clear runs straight", d.steer, 0.0)

# 4c. HOLD expired entirely -> back to lane
h = {"kind": "red", "t": T - 5.0, "steer": -8.0}
d = OC.decide(T, None, h, kq, fo, 0.01, 0.01, 1)
check("hold fully expired -> lane", d.mode, "lane")

# 3. SIGN in view beats hold and lane
fake_sign = ("green", 100.0, 80.0, 900, (90, 60, 20, 40))
hh = fresh_hold()
d = OC.decide(T, fake_sign, hh, kq, fo, 0.01, 0.01, 1)
check("sign in view -> sign-green", d.mode, "sign-green")
check("sign refreshes the hold", hh["kind"], "green")

# 2. WALL beats a sign
d = OC.decide(T, fake_sign, fresh_hold(), kq, fo, 0.30, 0.01, 1)
check("wall beats sign", d.mode, "wall-L")
check("wall steers hard right", d.steer, R.STEER_MAX)

# 1. KICK beats the wall when they agree
k5 = R.CornerKick(angle=30.0, sign_cw="red", sign_ccw="green")
k5.maybe_fire(1, "red", T)
d = OC.decide(T + 0.1, fake_sign, fresh_hold(), k5, fo, 0.30, 0.01, 1)
check("kick beats wall+sign", d.mode, "kick")
check("kick angle passes through", d.steer, 30.0)
check("kick raises the ceiling", d.servo_limit, 30.0)
check("kick sets its own speed", d.speed_cap, 55)
check("kick clamps to 30, not STEER_MAX", OC.clamp_steer(d.steer, d.servo_limit), 30.0)

# 1b. ...but a wall closing from the OPPOSITE side aborts the kick
k6 = R.CornerKick(angle=30.0, sign_cw="red", sign_ccw="green")
k6.maybe_fire(1, "red", T)                       # kick pulls RIGHT
d = OC.decide(T + 0.1, None, fresh_hold(), k6, fo, 0.01, 0.30, 1)  # wall on right
check("opposing wall aborts the kick", d.mode, "wall-R")
check("kick was cancelled", k6.active(T + 0.2), False)

# normal steering is still capped at STEER_MAX
check("no limit -> clamped to STEER_MAX", OC.clamp_steer(99.0, None), R.STEER_MAX)
check("limit never beats the linkage", OC.clamp_steer(99.0, 99.0), R.STEER_MECH_MAX)

# ==========================================================================
section("open challenge imports and reads its tunables")
import open_challenge as OPEN  # noqa: E402

check("CRUISE present", isinstance(OPEN.CRUISE, int), True)
check("LANE_TARGET computed", round(OPEN.LANE_TARGET, 4), 0.1032)
print(f"  LANE_DISTANCE_CM={OPEN.LANE_DISTANCE_CM} -> LANE_TARGET={OPEN.LANE_TARGET:.4f}")

# ==========================================================================
print("\n" + "=" * 60)
if FAILED:
    print(f"{len(FAILED)} FAILED: {FAILED}")
    sys.exit(1)
print("ALL TESTS PASSED")
