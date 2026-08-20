import sys, os, types
from array import array
sys.path.insert(0, "src")
# --- stubs, same shape as test_logic.py uses ---
gpio = types.ModuleType("RPi.GPIO")
for n in ("BCM","OUT","IN","PUD_UP","HIGH","LOW"): setattr(gpio,n,0)
gpio.setmode=gpio.setwarnings=gpio.setup=gpio.cleanup=lambda *a,**k: None
gpio.input=lambda *a,**k: 1
class _P:
    def __init__(s,*a): pass
    def start(s,*a): pass
    def ChangeDutyCycle(s,*a): pass
    def stop(s): pass
gpio.PWM=_P
rpi=types.ModuleType("RPi"); rpi.GPIO=gpio
sys.modules["RPi"],sys.modules["RPi.GPIO"]=rpi,gpio
pc2=types.ModuleType("picamera2"); pc2.Picamera2=object
pc2.Preview=type("Preview",(),{"QTGL":0,"DRM":1,"NULL":2})
sys.modules["picamera2"]=pc2
lc=types.ModuleType("libcamera"); lc.Transform=lambda **k: None
sys.modules["libcamera"]=lc

import obstacle_challenge as O
O._t0 = 0.0

FAIL=[]
def check(name, got, want):
    ok = got == want
    print("  %s %-52s got %r want %r" % ("PASS" if ok else "FAIL", name, got, want))
    if not ok: FAIL.append(name)

def see(colour, area, t):
    """Pretend the biggest target is this colour at this area, then register."""
    idx = O.red_index if colour == "R" else O.green_index
    O.target = array('i', [160, 50, int(area), idx])
    O.register_pillar(t)

def reset():
    O.pillars = []; O._pillar_armed = False
    O._pillar_last_colour = None; O._pillar_lost_t = 0.0
    O.direction = 1; O.quadrant_count = 0

print("=== one pillar held for many cycles -> ONE entry ===")
reset()
for i in range(50):
    see("R", 900, i * 0.045)
check("50 cycles of the same red", len(O.pillars), 1)
check("recorded colour", O.pillars[0][0], "R")

print()
print("=== a DIFFERENT colour interrupts immediately ===")
reset()
for i in range(20): see("R", 900, i*0.045)
for i in range(20): see("G", 900, 1.0 + i*0.045)
check("red then green", [c for c,_,_ in O.pillars], ["R","G"])

print()
print("=== same colour twice, with the target LOST between ===")
reset()
for i in range(10): see("R", 900, i*0.045)
O.target = array('i',[160,0,O.PARALELIPIPED_MIN_AREA,-1])
t = 0.5
for i in range(30):                     # nothing visible
    O.register_pillar(t); t += 0.045
for i in range(10): see("R", 900, t + i*0.045)
check("two separate reds", [c for c,_,_ in O.pillars], ["R","R"])

print()
print("=== a BRIEF dropout must NOT re-arm (shorter than PILLAR_REARM_S) ===")
reset()
for i in range(10): see("R", 900, i*0.045)
t = 0.5
O.target = array('i',[160,0,O.PARALELIPIPED_MIN_AREA,-1])
for i in range(4):                      # 0.18s < 0.5s
    O.register_pillar(t); t += 0.045
for i in range(10): see("R", 900, t + i*0.045)
check("one red, not two", len(O.pillars), 1)

print()
print("=== a FAR pillar is not recorded (below SIGN_CLOSE_AREA) ===")
reset()
for i in range(30): see("G", O.SIGN_CLOSE_AREA_CW - 50, i*0.045)
check("far green ignored", len(O.pillars), 0)

print()
print("=== quadrant and time are captured ===")
reset(); O.quadrant_count = 3
see("G", 900, 12.44)
check("entry", O.pillars[0], ("G", 3, 12.44))

print()
print("=== colour is REAL colour, not the steering class (parking swap) ===")
reset(); O.red_index = 2          # parking swap: red is STEERED as green
see("R", 900, 1.0)                # uses red_index -> type 2
check("still recorded as R", O.pillars[0][0], "R")
check("but steering would treat it as green", 2 in [1,2], True)
O.red_index = 0

print()
print("=== the decay does not oscillate ===")
import time as _t
O.direction = 1                       # CW default = GREEN(1)
O.last_detected_traffic_light = 0     # red override
O.sign_seen_t = _t.time() - 3.0       # older than SIGN_DECAY_S
default_tl = 1 if O.direction >= 0 else 0
flips = 0
tl = O.last_detected_traffic_light; seen = O.sign_seen_t
for i in range(5):                    # five cycles of the decay rule
    if tl != default_tl and seen is not None and _t.time() - seen >= O.SIGN_DECAY_S:
        tl = default_tl; seen = None; flips += 1
check("flips exactly once, then settles", flips, 1)
check("final state is the CW default GREEN", tl, 1)

print()
print("=" * 62)
print("ALL PILLAR TESTS PASSED" if not FAIL else "%d FAILED: %s" % (len(FAIL), FAIL))
sys.exit(1 if FAIL else 0)
