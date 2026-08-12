<p align="center">
  <img src="other/team-logo.jpg" alt="Team The Red Castle" width="620">
</p>

<h1 align="center">Team The Red Castle — WRO 2026 Future Engineers</h1>

An autonomous, self-driving model car for the **World Robot Olympiad 2026,
Future Engineers** category. It completes the **Open Challenge** (three laps of a
track with a randomised wall layout) and the **Obstacle Challenge** (three laps
avoiding red and green traffic signs, then parallel-parks) using a **single
camera as its only sensor** — no LiDAR, no ultrasonic rangefinders, no wheel
encoders, no IMU.

> **Design thesis:** everything the car needs to know — where the walls are, which
> way to lap, where the traffic signs are, and where the parking lot is — is
> visible. A well-tuned camera plus disciplined image processing can do the whole
> job, so we spent our engineering effort on making that one sensor reliable
> rather than fusing many.

---

## Table of contents
1. [The challenge](#1-the-challenge)
2. [Vehicle at a glance](#2-vehicle-at-a-glance)
3. [Mobility management](#3-mobility-management)
4. [Power & sense management](#4-power--sense-management)
5. [Software & obstacle management](#5-software--obstacle-management)
6. [Calibration workflow](#6-calibration-workflow)
7. [Build & run](#7-build--run)
8. [Bill of materials & cost](#8-bill-of-materials--cost)
9. [Engineering process](#9-engineering-process)
10. [Results & future work](#10-results--future-work)
11. [Repository map](#11-repository-map)
12. [Team](#12-team)

---

## 1. The challenge

WRO Future Engineers asks for a fully autonomous vehicle that drives a track
bounded by walls:

- **Open Challenge** — 3 laps; the inner walls are placed at random distances each
  round, so the path width changes and cannot be hard-coded.
- **Obstacle Challenge** — 3 laps with red/green **traffic signs** on the track:
  the car must pass **red signs on their right** and **green signs on their left**,
  then finish by **parking** in the magenta parking lot.

Scoring rewards completing laps without touching walls or signs, correct sign
handling, a clean park, and — importantly — **thorough engineering documentation**
(this repository).

## 2. Vehicle at a glance

| Subsystem | Choice |
|---|---|
| **Compute** | Raspberry Pi 4 Model B (Raspberry Pi OS *Bookworm*, 64-bit) |
| **Sensor** | **OV5647 Wide-angle** camera (5 MP, ~120° FOV, **fixed focus**) — sole sensor |
| **Steering** | Ackermann front steering, one servo on **GPIO13** (hardware PWM) |
| **Drive** | Single DC gear motor via an **L9110S** H-bridge on **GPIO24 / GPIO23** |
| **Power** | Battery → motor driver directly; separate 5 V regulator → Pi; common ground |
| **Software** | Python 3, OpenCV, Picamera2 |
| **Reference** | Studied Team KyivRoboMagic (Ukraine, WRO 2024 International Final) |

_Vehicle photos: [`v-photos/`](v-photos) · driving video: [`video/video.md`](video/video.md)_

## 3. Mobility management

### 3.1 Chassis
A custom 3D-printed chassis (files in [`models/`](models)) carries the Pi, battery,
motor driver, drive motor, steering servo and the camera mast. Design priorities:
low and central mass, a rigid camera mast, and easy access to the wiring.

### 3.2 Steering
Front-wheel **Ackermann steering** driven by a single servo (GPIO13, which is a
hardware-PWM pin for a smooth, low-jitter signal). Steering is **software-limited**
to a small maximum deviation (`STEER_MAX` in `src/robot.py`). One constant caps
every steering command — wall-following, obstacle-passing and emergency turns.

> **Engineering decision — the steering limit.** Our current drivetrain has **no
> differential**, so both driven wheels are forced to the same speed. At large
> steering angles the inner and outer wheels must travel different distances, so
> they *scrub*, losing traction and pushing the car wide (or stalling it in the
> turn). We reduced `STEER_MAX` step by step on the field until the scrub
> disappeared. **Planned upgrade:** fit a small differential (a WLtoys 1/28 micro
> metal differential, as used in spirit by top teams who favour low-backlash
> gearing) so we can raise the steering limit and corner harder. See
> [`ENGINEERING-JOURNAL.md`](ENGINEERING-JOURNAL.md).

### 3.3 Drivetrain
A single DC gear motor drives the rear axle through an **L9110S** dual H-bridge:

| L9110S | Connection |
|---|---|
| `A-IA` | GPIO24 — PWM here = **forward** |
| `A-IB` | GPIO23 — PWM here = **reverse** |
| `VCC` | Battery + (motor supply) |
| `GND` | Common ground |
| MOTOR-A | Drive motor |

Speed = PWM duty on one input, the other held LOW. The L9110S was chosen for its
tiny size and simple two-pin-per-motor interface.

> **Safety rule in software.** `motor()` **never switches forward↔reverse
> directly**: it first coasts to a stop and waits (`STOP_FLIP_DELAY`) before
> driving the other way. A hard reversal while the motor is still spinning dumps
> the motor's back-EMF onto the supply and can destroy the Pi's regulator — we
> learned this the hard way (see the journal).

## 4. Power & sense management

### 4.1 Power topology
Early on, the Pi rebooted every time the motor drew current. The fix defines our
power design and is now standard on the car:

```
Battery + ─┬─────────────────────────► L9110S VCC   (motor power, direct)
           └─► 5V / ≥3A regulator ────► Raspberry Pi 5V
Battery − ──── common ground ── L9110S GND ── Pi GND
```

1. **Separate rails** — the motor draws straight from the battery; the Pi has its
   **own regulator**. Motor current spikes never pass through the Pi's supply.
2. **Common ground** — Pi, driver and battery negatives are tied together so the
   GPIO control signals share a reference. (Without it, the only link between Pi
   and driver is the signal wire, and motor return current back-feeds the GPIO pin
   — which browns out or damages the Pi.)

### 4.2 Sensing — the camera
The camera is the entire perception system, so most of our tuning went here.

**Sensor choice.** We began with a Raspberry Pi Camera Module 3 Wide (IMX708) but
switched to an **OV5647 wide-angle module**. The Module 3's large sensor and
autofocus lens gave a *shallow depth of field*: focus it on the mat and distant
traffic signs blurred, which desaturated their colour and made them undetectable.
The OV5647 is a **small-sensor, fixed-focus** module, so its depth of field covers
the whole track — near mat and far walls are sharp simultaneously — and there is
no autofocus to hunt mid-run. Losing autofocus cost us nothing; a ground robot
never needs to refocus.

**Mount.** **12.5 cm above the mat**, tilted **~15° downward**, centred laterally
and facing straight ahead on a rigid mast. It is physically mounted
**upside-down**, so frames are rotated 180° in software.

**Locked settings** (`src/camera.py`), chosen from on-field capture tests:

| Setting | Value | Why |
|---|---|---|
| Sensor mode | 1296×972 (full ~120° FOV) → scaled to 640×480 | keep the wide FOV; cropped modes would lose it |
| Orientation | `hflip + vflip` (180°) | camera mounted upside-down |
| Focus | **fixed** (no AF hardware) | deep depth of field — sharp from the near mat to the far wall |
| Exposure | fixed (~9–12 ms) | freeze motion — auto-exposure ran ~60 ms and smeared when moving |
| White balance | locked `ColourGains` | keep HSV thresholds stable as the car turns toward/away from lights |
| Saturation | raised (~1.4) | separates red / orange / green / magenta in HSV, free in the ISP |

> **Why camera-only?** A single well-configured camera sees walls, the orange/blue
> corner lines, the coloured signs and the parking lot — everything the rules
> reference. Removing LiDAR/ultrasonic cut cost, weight, wiring and failure modes,
> and let us focus on making the vision robust (locked exposure/AWB, fixed focus,
> field-tuned HSV).

## 5. Software & obstacle management

All control software is in [`src/`](src). Four core modules import each other and
run together; the calibration and test utilities live in [`src/tools/`](src/tools).

```
src/robot.py               shared library — pins, servo()/motor(), HSV masks, wall/line/pillar analysis
src/camera.py              locked camera setup
src/open_challenge.py      Open Challenge main
src/obstacle_challenge.py  Obstacle Challenge main
```

### 5.1 Vision pipeline
`capture → 180° flip → crop the mat ROI → resize 320×160 → HSV`. HSV is computed
with `cv2.COLOR_BGR2HSV` everywhere so thresholds transfer between the tuner and
the challenge code. Six colours are thresholded from `colors.json` (produced by
`tools/color_tuner.py`):

- **black** → walls (dark-pixel density per image half → `left_wall`, `right_wall`)
- **blue / orange** → corner lines (driving direction + lap counting)
- **green / red** → traffic signs
- **magenta** → parking lot

### 5.2 Open Challenge algorithm
1. **Wall-follow** the continuous *outer* wall with a **PD** controller — clockwise
   follows the left wall, counter-clockwise the right; either wall getting
   dangerously close forces a hard steer away.
2. **Direction** from the first corner line seen: **orange → clockwise**, **blue →
   counter-clockwise**.
3. **Lap counting** — a debounced falling edge on the driving-direction line counts
   one *quadrant*; **12 quadrants = 3 laps**, then the car coasts and stops.

### 5.3 Obstacle Challenge algorithm
A strict **per-frame priority** decides steering:

1. **Wall emergency** — never crash a wall, even mid-dodge.
2. **Park** (after 3 laps) — find the **magenta** lot, aim at it, stop when close.
3. **Sign** — pass **red on the right**, **green on the left** (steer to push the
   sign toward the correct frame edge; react harder as it nears).
4. **Wall-follow** — the Open-Challenge behaviour otherwise.

### 5.4 Speed
Base speed is `CRUISE`; `cruise_speed()` **eases off in proportion to steering
effort**, so the car runs fast on straights and slows automatically for corners.

## 6. Calibration workflow

Two field calibrations, saved to files that `robot.py` loads at start:

| Tool | Produces | Purpose |
|---|---|---|
| `tools/color_tuner.py` | `colors.json` | tune each colour with the real object in view |
| `tools/servo_center.py` | `servo_center.txt` | trim the steering so 0° = straight |
| `tools/motor_speed_steps.py` | — | find the motor's usable speed range |
| `tools/preview.py` | — | live camera view over VNC |

## 7. Build & run

**Raspberry Pi OS Bookworm** — Picamera2/OpenCV come from `apt`, **not** pip
(mixing a pip numpy breaks Picamera2):

```bash
sudo apt update
sudo apt install -y python3-picamera2 python3-libcamera python3-opencv python3-rpi-lgpio python3-venv
python3 -m venv --system-site-packages ~/wro2026/.venv
source ~/wro2026/.venv/bin/activate
```

Run (always from `~/wro2026` so `colors.json` / `servo_center.txt` resolve):
```bash
cd ~/wro2026 && source .venv/bin/activate
python tools/color_tuner.py     # tune colours
python tools/servo_center.py    # center steering
python open_challenge.py        # Open Challenge
python obstacle_challenge.py    # Obstacle Challenge
```

## 8. Bill of materials & cost

Full component list: [`other/bill-of-materials.md`](other/bill-of-materials.md).
Wiring: [`schemes/`](schemes). _(Total cost: to fill.)_

## 9. Engineering process

The interesting part of this project was making one camera and a cheap drivetrain
reliable. The full design log — sensor choice, the power-brownout debugging, the
motor stall, the no-differential steering decision, and the camera focus/exposure
tuning — is in **[`ENGINEERING-JOURNAL.md`](ENGINEERING-JOURNAL.md)**.

## 10. Results & future work

**Results.** _(To fill: best Open lap time, Obstacle completion, parking success
rate.)_

**Future work.**
- Fit a small differential and raise `STEER_MAX` for tighter cornering.
- Extend camera depth of field (or a fixed-focus wide module) so distant signs
  stay sharp and detectable earlier.
- Upgrade wall-following to a heading + offset controller; add sign tracking across
  frames.

## 11. Repository map

```
README.md                 # this engineering document
ENGINEERING-JOURNAL.md     # design process & problem-solving log
CHECKLIST.md               # submission checklist
src/                       # control software (core + tools/)
models/                    # 3D-printable parts + source CAD
schemes/                   # wiring / electromechanical diagrams
t-photos/                  # team photos
v-photos/                  # vehicle photos (6 angles)
video/                     # link to the driving demonstration
other/                     # BOM, rulebook, misc
```

## 12. Team

<p align="center">
  <img src="other/team-logo.jpg" alt="Red Castle" width="300">
  &nbsp;&nbsp;&nbsp;
  <img src="other/hmk-club-logo.jpg" alt="HMK AI and Robotics Club" width="150">
</p>

**Team The Red Castle** — HMK AI and Robotics Club.

_(to fill: member names + roles, e.g. mechanical, electronics, software.)_

Built on a Raspberry Pi 4 with an OV5647 wide-angle camera. Reference study: Team
KyivRoboMagic (Ukraine, WRO 2024).
