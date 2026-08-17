# src — the code

## The whole thing in five files

```
open_challenge.py      RUN THIS   three laps, empty track
obstacle_challenge.py  RUN THIS   three laps, red/green traffic signs
robot.py               the car: hardware, camera, seeing, control
config.py              every tunable number shared by both challenges
camera.py              camera setup (locked exposure and white balance)
```

Only the first two are programs you run. Everything else is support.

```
colors.json            the tuned HSV ranges (made by tools/color_tuner.py)
camera_settings.json   the locked white balance (made by tools/camera_tune.py)
servo_center.txt       steering centre trim (made by tools/servo_center.py)
tools/                 helpers - see below
archive/               superseded experiments, kept for the journal
```

---

## Every challenge program has the same three parts

This is the important bit. Open either program and you will find, in order:

### 1. TUNABLES
A single block at the top. **Nothing outside it needs editing.** Speed,
direction, how far from the wall to drive, how hard to react to a sign.

### 2. `decide()`
The brain. **One frame in, one steering decision out.** It is a *priority
ladder* — a list of `if` statements from most urgent to least, where exactly
one branch answers:

```python
def decide(view, laps, outer, turner):
    if a wall is too close:      return escape        # 1. EMERGENCY
    if we are cornering:         return turn          # 2. TURN
    return follow the outer wall                      # 3. LANE
```

`decide()` touches no hardware and no camera — it is pure arithmetic on
numbers. That is deliberate: it means the whole brain can be tested on a
laptop, with no Pi, in under a second.

### 3. `main()`
The loop. Always the same four steps:

```python
button.wait_for_start()          # nothing moves until you press it
while True:
    view = R.look(cam)           # LOOK   one frame, everything measured
    d = decide(view, ...)        # THINK  one decision
    R.servo(d.steer)             # ACT
    R.motor(speed)
    if button.stop_pressed(): break   # RECORD / FINISH
```

---

## How to write the surprise challenge

The surprise challenge is announced at the venue. You will not have time to
invent anything, so don't — **copy a program and rewrite one function.**

**1. Copy the closest existing program.**
```bash
cp open_challenge.py surprise_challenge.py
```
Start from `open_challenge.py` if the task is about driving and walls; from
`obstacle_challenge.py` if it involves coloured objects.

**2. Change the TUNABLES block** to whatever the new task needs.

**3. Rewrite `decide()`.** This is the only real work. Write the ladder in
plain words first, most urgent at the top, then translate each line:

> *"Don't hit anything. Otherwise, if I can see the thing, go to it.
> Otherwise, keep driving down the middle."*

```python
def decide(view, laps, outer, turner):
    escape = R.wall_emergency(view.left, view.right, outer, laps.direction)
    if escape is not None:
        return Decision(escape, "emergency")
    ...your new rule here...
    return Decision(R.apply_bias(outer.steer(view.left, view.right,
                                             laps.direction)), "lane")
```

**4. Leave `main()` almost alone.** Change the log filename and the printed
header. The button, the loop, the logging and the safety timeout all work
already.

**5. Test before you drive it.**
```bash
python tools/test_logic.py     # on the laptop, no Pi needed
python tools/dryrun.py         # on the Pi, camera on, motor never touched
```

### What you can call inside `decide()`

Everything the car can sense arrives in one `view` object:

| field | meaning |
|---|---|
| `view.left`, `view.right` | how much of that half of the picture is wall. **Bigger = closer.** |
| `view.front` | the same, straight ahead. High means a corner. |
| `view.blue`, `view.orange` | how much corner line is visible |
| `view.hsv` | the raw HSV image, for your own colour work |
| `view.proc` | the colour image, for saving annotated frames |

Useful helpers in `robot.py`:

| call | what it does |
|---|---|
| `R.wall_emergency(left, right, outer, direction)` | escape steering, or `None` if safe |
| `R.mask(hsv, "red")` | pixels matching a tuned colour |
| `R.apply_bias(steer)` | adds the straight-line drift trim (lane keeping only) |
| `R.cruise_speed(base, steer)` | slows down in proportion to steering |
| `R.OuterWallFollower(target=…)` | PD control on the distance to one wall |
| `R.CornerKick(...)` | a fixed, time-boxed, open-loop turn |

**Sign conventions, everywhere:** steering `0` = straight, **+ = right**,
**− = left**. Direction `+1` = clockwise, `−1` = counter-clockwise.

---

## The button (GPIO 19)

One button does both jobs:

- **press once** → the run starts (nothing moves before this)
- **press again** → the run stops, at any time. This is the emergency stop.

Wired between **GPIO19 and GND**, using the Pi's internal pull-up, so no
resistor is needed. Check it before trusting it:

```bash
python tools/button_test.py
```

If it says the button reads PRESSED while you are not touching it, flip
`BUTTON_PULL_UP` in `config.py`. To bench-test without the button at all, set
`BUTTON_REQUIRED = False` and it falls back to pressing Enter.

---

## Tools

| tool | what it is for |
|---|---|
| `test_logic.py` | **run this before every deploy.** The whole brain, tested on a laptop with no Pi. |
| `dryrun.py` | both challenges against the real camera, motor never touched |
| `button_test.py` | check the start/stop button is wired and configured right |
| `color_tuner.py` | tune the HSV ranges → `colors.json` |
| `camera_tune.py` | lock exposure and white balance → `camera_settings.json` |
| `servo_center.py` | find the steering centre → `servo_center.txt` |
| `test.py` | move each piece of hardware on its own |

---

## Running on the Pi

```bash
cd ~/wro2026 && source .venv/bin/activate && python open_challenge.py
```

Then press the button. Every run writes a CSV to `logs/`; the obstacle run
also writes `sign_order.txt` and annotated frames to `frames/`.
