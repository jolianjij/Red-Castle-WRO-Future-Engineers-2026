#!/usr/bin/env python3
"""
test_obstacle_run.py - RUN obstacle_challenge's real cycle() on a laptop.

The static audit proves the file compiles and has no dead names. This proves the
code actually EXECUTES, across the states a run passes through, without raising.
That is the class of bug a compile check cannot see: a name that only exists on
one branch, a global that was never declared, an index that goes out of range
once the quadrant count passes twelve.

    python tools/test_obstacle_run.py

No camera, no GPIO, no car. Everything is stubbed.
"""
import sys
import os
import types

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# ----------------------------------------------------------------- stubs
gpio = types.ModuleType("RPi.GPIO")
for _n in ("BCM", "OUT", "IN", "PUD_UP", "HIGH", "LOW"):
    setattr(gpio, _n, 0)
gpio.setmode = gpio.setwarnings = gpio.setup = gpio.cleanup = lambda *a, **k: None
gpio.input = lambda *a, **k: 1          # button released


class _PWM(object):
    def __init__(self, *a): pass
    def start(self, *a): pass
    def ChangeDutyCycle(self, *a): pass
    def stop(self): pass


gpio.PWM = _PWM
_rpi = types.ModuleType("RPi"); _rpi.GPIO = gpio
sys.modules["RPi"], sys.modules["RPi.GPIO"] = _rpi, gpio
_pc2 = types.ModuleType("picamera2"); _pc2.Picamera2 = object
_pc2.Preview = type("Preview", (), {"QTGL": 0, "DRM": 1, "NULL": 2})
sys.modules["picamera2"] = _pc2
_lc = types.ModuleType("libcamera"); _lc.Transform = lambda **k: None
sys.modules["libcamera"] = _lc

import obstacle_challenge as O          # noqa: E402


class FakeCam(object):
    """A camera that can be told what to show."""

    def __init__(self):
        self.scene = "empty"

    def capture_array(self):
        # a plausible mat: mid grey-green, H~74 S~93 V~135
        f = np.zeros((480, 640, 3), np.uint8)
        f[:, :] = (past := (120, 150, 110))
        if self.scene in ("red", "both"):
            f[200:340, 80:180] = (40, 40, 200)        # a red cube, BGR
        if self.scene in ("green", "both"):
            f[200:340, 440:540] = (40, 200, 40)       # a green cube
        if self.scene == "blue_line":
            f[430:470, :] = (200, 60, 40)             # a wide blue band
        if self.scene == "orange_line":
            f[430:470, :] = (30, 110, 230)            # a wide orange band
        if self.scene == "purple":
            f[160:300, :] = (180, 40, 170)            # magenta wall
        if self.scene == "dark":
            f[:] = (10, 10, 10)
        return f


FAIL = []


def run(label, scene, cycles, **state):
    """Set some state, show a scene, run cycle() that many times."""
    O.STOP = False
    for k, v in state.items():
        setattr(O, k, v)
    cam.scene = scene
    try:
        for _ in range(cycles):
            O.cycle(cam)
    except Exception as exc:                      # noqa: BLE001
        import traceback
        traceback.print_exc()
        FAIL.append("%s -> %s: %s" % (label, type(exc).__name__, exc))
        print("  FAIL %-46s %s" % (label, exc))
        return
    print("  ok   %-46s q=%-3d dir=%-3d tl=%-3d STOP=%s"
          % (label, O.quadrant_count, O.direction,
             O.last_detected_traffic_light, O.STOP))


print()
print("=" * 74)
print("  RUNNING obstacle_challenge.cycle() FOR REAL - stubbed hardware")
print("=" * 74)

O.Setup_GPIO()
cam = FakeCam()
O._open_log()
import time as _time
O._t0 = _time.time()

run("empty mat, direction not yet set", "empty", 5, direction=0)
run("empty mat, CW", "empty", 5, direction=1)
run("empty mat, CCW", "empty", 5, direction=-1)
run("a red cube, CW", "red", 5, direction=1)
run("a green cube, CW", "green", 5, direction=1)
run("both cubes, CW", "both", 5, direction=1)
run("a red cube, CCW", "red", 5, direction=-1)
run("a green cube, CCW", "green", 5, direction=-1)
run("blue line, CCW", "blue_line", 5, direction=-1)
run("orange line, CW", "orange_line", 5, direction=1)
run("the parking wall, Zaid set", "purple", 5, direction=1, Zaid=True)
run("everything dark", "dark", 5, direction=1)
run("quadrant 11 - just before the end", "empty", 3,
    direction=1, quadrant_count=11, mission_end_not_activated=True)
run("quadrant 12 - the finish arms", "empty", 3,
    direction=1, quadrant_count=12, mission_end_not_activated=True)
run("quadrant 13 - past the end", "empty", 3, direction=1, quadrant_count=13)
run("a kick armed and live", "empty", 3,
    direction=1, _kick_until=_time.time() + 1.0, _kick_sign=1)
run("a kick that has expired", "empty", 3,
    direction=1, _kick_until=_time.time() - 1.0, _kick_sign=1)

# ---- the finish really does stop ----
print()
O.STOP = False
O.quadrant_count = 12
O.mission_end_not_activated = True
O.direction = 1
cam.scene = "empty"
t0 = _time.time()
n = 0
while not O.STOP and _time.time() - t0 < O.FINISH_RUN_S + 2.0:
    O.cycle(cam); n += 1
elapsed = _time.time() - t0
print("  finish: STOP=%s after %.2fs and %d cycles (FINISH_RUN_S=%.1f)"
      % (O.STOP, elapsed, n, O.FINISH_RUN_S))
if not O.STOP:
    FAIL.append("the run never stopped after 12 quadrants")
elif abs(elapsed - O.FINISH_RUN_S) > 0.5:
    FAIL.append("stopped after %.2fs, expected about %.1f" % (elapsed, O.FINISH_RUN_S))

print()
print("  pillars recorded during all of the above: %s"
      % (O.pillars if O.pillars else "none"))

if O.logfile is not None:
    O.logfile.close()
    try:
        os.remove(O.LOG_PATH)
    except OSError:
        pass

print()
print("=" * 74)
print("ALL CYCLE RUNS PASSED" if not FAIL else "%d FAILED:" % len(FAIL))
for f in FAIL:
    print("   - " + f)
sys.exit(1 if FAIL else 0)
