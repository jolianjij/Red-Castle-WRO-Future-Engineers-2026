#!/usr/bin/env python3
"""
test_logic.py - offline tests for the decision logic. NO Pi, NO camera.

Runs on a laptop. It stubs RPi.GPIO and picamera2 so robot.py imports, then
drives the real classes with synthetic numbers and asserts on the results.

py_compile only proves a file parses; it does not prove decide() can run
without a NameError. This does. Run it before every deploy:

    python src/tools/test_logic.py
"""
import os
import sys
import types

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---- stub the Pi-only modules so robot.py imports on a laptop ----
gpio = types.ModuleType("RPi.GPIO")
for _n in ("BCM", "OUT", "IN", "HIGH", "LOW", "PUD_UP", "PUD_DOWN"):
    setattr(gpio, _n, 0)
gpio.setmode = gpio.setwarnings = gpio.setup = gpio.cleanup = lambda *a, **k: None
gpio.output = lambda *a, **k: None
gpio.LEVEL = {"pin": 1}          # 1 = released with a pull-up
gpio.input = lambda pin: gpio.LEVEL["pin"]


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
lc = types.ModuleType("libcamera")
lc.Transform = lambda **k: None
sys.modules["libcamera"] = lc

import robot as R            # noqa: E402
import open_challenge as OPEN      # noqa: E402
import obstacle_challenge as OBS   # noqa: E402

FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: got {got!r}, want {want!r}")
    if not ok:
        FAILED.append(name)


def section(t):
    print(f"\n=== {t} ===")


def view(left=0.01, right=0.01, front=0.05, blue=0.0, orange=0.0):
    """A fake camera reading."""
    return R.View(None, None, left, right, front, blue, orange)


# ==========================================================================
section("per-colour line thresholds")
print(f"  orange bar {R.LINE_FRACTION_ORANGE}   blue bar {R.LINE_FRACTION_BLUE}")

# THE BUG THIS FIXES: a real orange crossing with background blue bleeding in.
# Raw pixels say blue wins (0.030 > 0.025) -> the old code locked CCW on a CW
# run. By confidence, orange is 2.08x its bar and blue only 0.86x of its own.
t = R.LapTracker()
t.direction = 0
t.update(blue_frac=0.030, orange_frac=0.025, left=0.10, right=0.05, front=0.15)
check("orange crossing + blue bleed -> CW", t.direction, 1)

t = R.LapTracker()
t.direction = 0
t.update(blue_frac=0.090, orange_frac=0.002, left=0.05, right=0.10, front=0.15)
check("clean blue crossing -> CCW", t.direction, -1)

t = R.LapTracker()
t.direction = 0
t.update(blue_frac=0.030, orange_frac=0.008, left=0.05, right=0.05, front=0.10)
check("both under their own bars -> undecided", t.direction, 0)

t = R.LapTracker()
t.direction = 0
t.update(blue_frac=0.040, orange_frac=0.014, left=0.05, right=0.05, front=0.10)
check("both convincing -> stays undecided", t.direction, 0)
t.update(blue_frac=0.001, orange_frac=0.030, left=0.10, right=0.05, front=0.10)
check("...then a clean orange frame -> CW", t.direction, 1)

# ==========================================================================
section("wall emergency")
check("clear track -> no emergency", R.wall_emergency(0.01, 0.01), None)
e = R.wall_emergency(R.WALL_EMERGENCY + 0.001, 0.01)
check("left wall just over -> steers RIGHT", e > 0, True)
check("...starting at HALF lock, not zero",
      abs(e - R.STEER_MAX * 0.5) < 0.5, True)
e = R.wall_emergency(R.WALL_EMERGENCY + 0.12, 0.01)
check("left wall deep in -> full lock right", round(e), R.STEER_MAX)
e = R.wall_emergency(0.01, R.WALL_EMERGENCY + 0.12)
check("right wall deep in -> full lock left", round(e), -R.STEER_MAX)

# both walls close = facing a corner: the direction must LATCH, not flip
R._esc["dir"] = 0
a = R.wall_emergency(0.30, 0.28)
b = R.wall_emergency(0.28, 0.30)      # L and R swap over
check("both walls close -> latched, does not flip", a, b)
R.wall_emergency(0.01, 0.01)          # clearing resets the latch
check("latch resets when clear", R._esc["dir"], 0)


class FakeOuter:
    def __init__(self, out=0.0):
        self.out = out

    def steer(self, left, right, direction):
        return self.out


# the emergency must never be WEAKER than the normal controller in that sense
e = R.wall_emergency(R.WALL_EMERGENCY + 0.001, 0.01, FakeOuter(18.0), 1)
check("emergency floored by the normal command", e, 18.0)

# ==========================================================================
section("CornerKick - which sign arms it")
k = R.CornerKick(angle=30.0, duration_s=0.9, speed=55,
                 sign_cw="red", sign_ccw="green")
check("CW trigger colour", k.trigger_colour(1), "red")
check("CCW trigger colour", k.trigger_colour(-1), "green")

NOW = 1000.0
check("CW + red fires", k.maybe_fire(1, "red", NOW), True)
check("kick is active", k.active(NOW + 0.5), True)
steer, limit, speed = k.command()
check("CW kick steers RIGHT (+)", steer > 0, True)
check("kick raises the servo ceiling", limit, 30.0)
check("kick uses its own speed", speed, 55)
check("kick expires", k.active(NOW + 1.0), False)

k2 = R.CornerKick(sign_cw="red", sign_ccw="green")
check("CCW + green fires", k2.maybe_fire(-1, "green", NOW), True)
check("CCW kick steers LEFT (-)", k2.command()[0] < 0, True)

k3 = R.CornerKick(sign_cw="red", sign_ccw="green")
check("CW + green does NOT fire", k3.maybe_fire(1, "green", NOW), False)
check("CCW + red does NOT fire", k3.maybe_fire(-1, "red", NOW), False)
check("no sign does NOT fire", k3.maybe_fire(1, "", NOW), False)
check("unknown direction does NOT fire", k3.maybe_fire(0, "red", NOW), False)
check("disabled never fires",
      R.CornerKick(enabled=False).maybe_fire(1, "red", NOW), False)

# ==========================================================================
section("servo ceiling")
R.setup_hardware()
R.servo(30.0)                  # no limit -> clamped to STEER_MAX
R.servo(30.0, limit=30.0)      # the kick path -> allowed through
R.servo(99.0, limit=99.0)      # never past the linkage
check("STEER_MAX", R.STEER_MAX, 20)
check("STEER_MECH_MAX", R.STEER_MECH_MAX, 35)
check("no limit -> STEER_MAX", OBS.clamp_steer(99.0, None), R.STEER_MAX)
check("limit never beats the linkage", OBS.clamp_steer(99.0, 99.0), R.STEER_MECH_MAX)
check("kick angle passes through", OBS.clamp_steer(30.0, 30.0), 30.0)

# ==========================================================================
section("BUTTON - start and emergency stop")
gpio.LEVEL["pin"] = 1                       # released (pull-up)
b = R.Button()
check("released reads not-down", b.is_down(), False)
gpio.LEVEL["pin"] = 0                       # pressed pulls to GND
check("pressed reads down", b.is_down(), True)

# wired the other way round
R.BUTTON_PULL_UP = False
gpio.LEVEL["pin"] = 1
check("pull-down wiring: HIGH is pressed", R.Button().is_down(), True)
R.BUTTON_PULL_UP = True

# the stop is EDGE triggered: holding it must not fire every frame
gpio.LEVEL["pin"] = 1
b = R.Button()
b._ignore_until = 0.0
import time as _t                            # noqa: E402
gpio.LEVEL["pin"] = 0                        # press
for _ in range(20):                          # let the debounce settle
    b._debounced()
    _t.sleep(0.005)
fires = sum(1 for _ in range(10) if b.stop_pressed())
check("one press = exactly one stop event", fires, 1)
gpio.LEVEL["pin"] = 1                        # release
for _ in range(20):
    b._debounced()
    _t.sleep(0.005)
check("release does not fire", b.stop_pressed(), False)

# the hold-off stops the START press being read as a STOP
b2 = R.Button()
b2._ignore_until = _t.monotonic() + 5.0
gpio.LEVEL["pin"] = 0
for _ in range(20):
    b2._debounced()
    _t.sleep(0.005)
check("hold-off suppresses the start press", b2.stop_pressed(), False)

# ==========================================================================
section("OPEN decide() - the ladder")
laps = R.LapTracker()
laps.direction = 1
outer = FakeOuter(3.3)
turner = R.TurnSequencer()

d = OPEN.decide(view(left=0.05, right=0.05, front=0.05), laps, outer, turner)
check("clear track -> lane", d.mode, "lane")
check("lane = outer PD + drift trim", d.steer, R.apply_bias(3.3))

d = OPEN.decide(view(left=0.40, right=0.01), laps, outer, turner)
check("close wall -> emergency", d.mode, "emergency")

turner.trigger(1)
d = OPEN.decide(view(front=0.9), laps, outer, turner)
check("scripted turn running -> turn", d.mode, "turn")
check("CW turn steers right", d.steer > 0, True)
turner.active = False

d = OPEN.decide(view(front=R.FRONT_TURN_BACKUP + 0.05), laps, outer, turner)
check("missed line, wall ahead -> turn-geom", d.mode, "turn-geom")

# ==========================================================================
section("OBSTACLE decide() - the ladder")
outer = FakeOuter(3.3)
kick = R.CornerKick(sign_cw="red", sign_ccw="green")
T = 5000.0


def hold0():
    return {"kind": "", "t": -1e9, "steer": 0.0}


d = OBS.decide(T, view(), None, hold0(), kick, outer, 1)
check("clear track -> lane", d.mode, "lane")
check("lane uses the outer follower", d.steer, 3.3)

h = {"kind": "red", "t": T - 0.2, "steer": -8.0}
d = OBS.decide(T, view(), None, h, kick, outer, 1)
check("recent sign -> sign-hold", d.mode, "sign-hold")
check("sign-hold keeps the sign's steer", d.steer, -8.0)

h = {"kind": "red", "t": T - 1.5, "steer": -8.0}
d = OBS.decide(T, view(), None, h, kick, outer, 1)
check("hold elapsed -> sign-clear", d.mode, "sign-clear")
check("sign-clear runs straight", d.steer, 0.0)

h = {"kind": "red", "t": T - 5.0, "steer": -8.0}
check("hold fully expired -> lane",
      OBS.decide(T, view(), None, h, kick, outer, 1).mode, "lane")

fake_sign = ("green", 100.0, 80.0, 900, (90, 60, 20, 40))
hh = hold0()
d = OBS.decide(T, view(), fake_sign, hh, kick, outer, 1)
check("sign in view -> sign-green", d.mode, "sign-green")
check("sign refreshes the hold", hh["kind"], "green")

d = OBS.decide(T, view(left=0.40), fake_sign, hold0(), kick, outer, 1)
check("wall beats sign", d.mode, "wall")

k5 = R.CornerKick(angle=30.0, sign_cw="red", sign_ccw="green")
k5.maybe_fire(1, "red", T)
d = OBS.decide(T + 0.1, view(left=0.40), fake_sign, hold0(), k5, outer, 1)
check("kick beats wall+sign", d.mode, "kick")
check("kick angle passes through", d.steer, 30.0)
check("kick sets its own speed", d.speed_cap, 55)

# a wall closing from the OPPOSITE side must abort the kick
k6 = R.CornerKick(angle=30.0, sign_cw="red", sign_ccw="green")
k6.maybe_fire(1, "red", T)                       # kick pulls RIGHT
d = OBS.decide(T + 0.1, view(right=0.40), None, hold0(), k6, outer, 1)
check("opposing wall aborts the kick", d.mode, "wall")
check("kick was cancelled", k6.active(T + 0.2), False)

# ==========================================================================
section("ParkingExit - the way out decides the lap direction")


def park_view(mag_left, mag_right):
    """A frame with a chosen amount of magenta in each half, no walls."""
    img = np.zeros((R.PROC_H, R.PROC_W, 3), np.uint8)
    lo_h, hi_h, lo_s, _, lo_v, _ = R.COLORS["magenta"]
    mid_h = (lo_h + hi_h) // 2
    half = R.PROC_W // 2
    for frac, x0, x1 in ((mag_left, 0, half), (mag_right, half, R.PROC_W)):
        rows = int(R.PROC_H * frac)
        img[:rows, x0:x1] = (mid_h, min(255, lo_s + 40), min(255, lo_v + 60))
    return R.View(None, img, 0.0, 0.0, 0.0, 0.0, 0.0)


def run_park(p, v, t0=0.0, known=0):
    """Drive a ParkingExit through settle -> exit -> done. Returns the modes."""
    modes = []
    for i in range(p.settle_frames + 2):
        out = p.update(v, t0, known)
        modes.append(out[1] if out else "done")
        if out is None:
            break
    return modes


# more magenta on the LEFT -> leave RIGHT -> CW (+1)
p = R.ParkingExit(angle=30.0, time_s=1.0, use_wall=False)
m = run_park(p, park_view(0.60, 0.05))
check("left blocked -> direction CW", p.direction, 1)
check("left blocked -> steers RIGHT out", p.update(park_view(0.6, 0.05), 0.1)[0] > 0, True)
# BUG FIXED: the settle phase used to return PARK_SPEED, so the car rolled
# forward at 45% during the one measurement whose whole point is no motion blur.
p_still = R.ParkingExit(angle=30.0, time_s=1.0, speed=45, use_wall=False)
check("SPEED 0 while measuring", p_still.update(park_view(0.6, 0.05), 0.0)[2], 0)
run_park(p_still, park_view(0.6, 0.05))
check("...and its own speed while driving out",
      p_still.update(park_view(0.6, 0.05), 0.1)[2], 45)
check("settles before deciding", m[0], "park-look")
check("then drives out", "park-exit" in m, True)

# more magenta on the RIGHT -> leave LEFT -> CCW (-1)
p = R.ParkingExit(angle=30.0, time_s=1.0, use_wall=False)
run_park(p, park_view(0.05, 0.60))
check("right blocked -> direction CCW", p.direction, -1)
check("right blocked -> steers LEFT out", p.update(park_view(0.05, 0.6), 0.1)[0] < 0, True)

# BUG FIXED: a FORCED direction must WIN over the measurement. Exiting the lot
# one way and then racing the other is worse than either choice alone.
p_forced = R.ParkingExit(angle=30.0, time_s=1.0, use_wall=False)
out = p_forced.update(park_view(0.05, 0.60), 0.0, known_direction=1)  # lot says CCW
check("forced CW beats a lot that measures CCW", p_forced.direction, 1)
check("...and it exits to the RIGHT", out[0] > 0, True)
check("...without wasting frames measuring", out[1], "park-exit")

# the exit is time-boxed, then it hands back
p = R.ParkingExit(angle=30.0, time_s=1.0, use_wall=False)
run_park(p, park_view(0.60, 0.05))
check("still leaving before the time is up", p.update(park_view(0.6, 0.05), 0.5)[1], "park-exit")
check("finished after it", p.update(park_view(0.6, 0.05), 1.5), None)
check("marked done", p.done, True)

# no magenta at all -> refuse to guess
p = R.ParkingExit(use_wall=False)
run_park(p, park_view(0.0, 0.0))
check("no parking lot -> gives up", p.done, True)
check("...and does NOT invent a direction", p.direction, 0)

# disabled
p = R.ParkingExit(enabled=False)
check("disabled is done immediately", p.done, True)
check("disabled never steers", p.update(park_view(0.6, 0.0), 0.0), None)

# and through the real ladder: PARK outranks even the wall escape
p = R.ParkingExit(angle=30.0, time_s=1.0, use_wall=False)
pv = park_view(0.60, 0.05)
for _ in range(p.settle_frames):
    p.update(pv, 0.0)
walled = R.View(None, pv.hsv, 0.40, 0.01, 0.0, 0.0, 0.0)   # wall screaming close
d = OBS.decide(0.1, walled, None, hold0(), R.CornerKick(), outer, 0, p)
check("PARK outranks the wall escape", d.mode, "park-exit")
# NOTE: compare against what THIS object was built with, not OBS.PARK_SPEED -
# that is a value the user tunes, and their tuning must never fail the suite.
check("park uses its own speed", d.speed_cap, p.speed)
d2 = OBS.decide(2.0, walled, None, hold0(), R.CornerKick(), outer, 1, p)
check("once out, the wall escape works again", d2.mode, "wall")

# PARK_USE_WALL is off by default. Note what this does and does NOT claim:
# on the REAL track the magenta and wall readings AGREE (measured in the lot,
# magenta L 0.716/R 0.449, wall L 0.174/R 0.093 - same side). An earlier
# synthetic test appeared to show them cancelling, but that was an artifact of
# the blank test image, where the background counted as wall. So all we assert
# here is the thing that actually matters: magenta ALONE reads the lot
# correctly, and it is what the default uses.
p_mag = R.ParkingExit(use_wall=False)
run_park(p_mag, park_view(0.60, 0.05))
check("magenta alone reads the lot correctly", p_mag.direction, 1)
check("the default is magenta only", OBS.PARK_USE_WALL, False)

# ==========================================================================
section("set_direction starts the lap timer")
# BUG FIXED: assigning .direction directly skipped the timer init, leaving
# _last_count_t at 0.0. `elapsed = now - 0.0` is then the machine's uptime, so
# the timer looked permanently expired and the FIRST line crossing counted with
# no debounce - a car starting beside a line would begin one quadrant ahead.
raw = R.LapTracker()
raw.direction = 1                      # the WRONG way, kept here as the contrast
check("assigning directly leaves the timer at zero", raw._last_count_t, 0.0)

good = R.LapTracker()
good.set_direction(1, "test")
check("set_direction locks the direction", good.direction, 1)
check("...and starts the lap timer", good._last_count_t > 0.0, True)
check("...and records why", "test" in good.direction_source, True)

# with the timer started, an immediate crossing is correctly IGNORED
good.update(blue_frac=0.0, orange_frac=0.20, left=0.05, right=0.05, front=0.1)
good.update(blue_frac=0.0, orange_frac=0.0, left=0.05, right=0.05, front=0.1)
check("a crossing inside the lockout does not count", good.quadrant, 0)

# ==========================================================================
section("sign geometry and the pass logger")
check("green is pushed RIGHT of frame", OBS.sign_error("green", 100.0, 80.0) < 0, True)
check("red is pushed LEFT of frame", OBS.sign_error("red", 220.0, 80.0) > 0, True)

pl = OBS.PassLogger()
pl.update(("red", 0, 0, 3000, None), 100.0)
pl.update(None, 100.0 + OBS.PASS_LOST_S + 0.1)
check("a big red then gone -> recorded", pl.order, ["red"])
pl.update(("green", 0, 0, 3000, None), 200.0)
pl.update(None, 200.0 + OBS.PASS_LOST_S + 0.1)
check("a different colour is never blocked", pl.order, ["red", "green"])
pl2 = OBS.PassLogger()
pl2.update(("red", 0, 0, 50, None), 300.0)       # too small to be a real pass
pl2.update(None, 300.0 + OBS.PASS_LOST_S + 0.1)
check("a distant speck is not a pass", pl2.order, [])

# ==========================================================================
section("both challenges expose the same shape")
for mod, name in ((OPEN, "open_challenge"), (OBS, "obstacle_challenge")):
    check(f"{name} has decide()", callable(mod.decide), True)
    check(f"{name} has main()", callable(mod.main), True)
    check(f"{name} has CRUISE", isinstance(mod.CRUISE, (int, float)), True)
    check(f"{name} has LANE_TARGET", isinstance(mod.LANE_TARGET, float), True)


# ---- PARK_INVERT: the one-line venue flip ----
section("PARK_INVERT")
pn = R.ParkingExit(use_wall=False, invert=False)
run_park(pn, park_view(0.60, 0.05))
pi_ = R.ParkingExit(use_wall=False, invert=True)
run_park(pi_, park_view(0.60, 0.05))
check("normal: left blocked -> CW", pn.direction, 1)
check("inverted: same view -> CCW", pi_.direction, -1)
check("...and it steers the other way",
      pn.update(park_view(0.6, 0.05), 0.1)[0] > 0
      and pi_.update(park_view(0.6, 0.05), 0.1)[0] < 0, True)
check("default is NOT inverted", OBS.PARK_INVERT, False)


# ==========================================================================
section("sign wall guard - the failed run's root cause")
# MEASURED on obstacle_20260818_062223: the sign law commanded -20 deg (full
# left lock) to place a green sign while the LEFT wall already read 0.20
# against a 0.213 escape threshold. 628 of 1707 frames (37%) were past that
# threshold. The sign law has no idea walls exist, so it must be faded out as
# it aims at one.
G = R.WALL_EMERGENCY * OBS.SIGN_WALL_GUARD
check("open space: command passes through untouched",
      OBS.limit_toward_wall(-20.0, 0.02, 0.02), -20.0)
check("steering LEFT with the LEFT wall close is faded",
      abs(OBS.limit_toward_wall(-20.0, (G + R.WALL_EMERGENCY) / 2, 0.02)) < 20.0, True)
check("...to ZERO exactly where the escape takes over",
      OBS.limit_toward_wall(-20.0, R.WALL_EMERGENCY, 0.02), -0.0)
check("steering LEFT with the RIGHT wall close is NOT faded",
      OBS.limit_toward_wall(-20.0, 0.02, R.WALL_EMERGENCY), -20.0)
check("steering RIGHT with the RIGHT wall close is faded",
      OBS.limit_toward_wall(20.0, 0.02, R.WALL_EMERGENCY), 0.0)
check("never flips sign", OBS.limit_toward_wall(-20.0, 0.99, 0.02) <= 0.0, True)

# and through the real ladder
d = OBS.decide(T, view(left=0.02, right=0.02), ("green", 100.0, 80.0, 900, None),
               hold0(), R.CornerKick(), outer, 1)
free = d.steer
d = OBS.decide(T, view(left=R.WALL_EMERGENCY * 0.95, right=0.02),
               ("green", 100.0, 80.0, 900, None), hold0(), R.CornerKick(), outer, 1)
check("a green sign no longer drives the car into the left wall",
      abs(d.steer) < abs(free), True)

# ==========================================================================
print("\n" + "=" * 62)
if FAILED:
    print(f"{len(FAILED)} FAILED: {FAILED}")
    sys.exit(1)
print("ALL TESTS PASSED")
