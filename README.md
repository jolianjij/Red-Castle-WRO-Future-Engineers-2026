# WRO 2026 Future Engineers — Autonomous Vehicle

Self-driving 1:X model car for the **WRO Future Engineers 2026** season. The car
completes the **Open Challenge** (three laps, random wall layout) and the
**Obstacle Challenge** (three laps avoiding red/green traffic signs, then parks)
using a **single camera** as its only sensor — no LiDAR, no ultrasonic, no
encoders.

---

## 1. Overview

| | |
|---|---|
| **Compute** | Raspberry Pi 4 (Raspberry Pi OS *Bookworm*, 64-bit) |
| **Sensor** | Raspberry Pi Camera Module 3 **Wide** (Sony IMX708, 120° FOV) — the *only* sensor |
| **Steering** | Servo on **GPIO13** (hardware PWM), Ackermann-style front steering |
| **Drive** | Single DC motor via **L9110S** H-bridge on **GPIO23 / GPIO24** |
| **Power** | Battery → motor driver directly; separate 5 V regulator → Pi; common ground |
| **Language** | Python 3 (OpenCV + Picamera2) |

The software philosophy: keep the **proven camera-only wall-following** approach
(HSV masks + a proportional/PD steering loop) and make it robust with locked
camera settings, a shared hardware library, and a clean per-challenge state machine.

---

## 2. Mobility management

**Chassis & steering.** Front-wheel Ackermann steering driven by one servo
(GPIO13). The drivetrain has **no differential**, so large steering angles cause
the driven wheels to scrub. To avoid traction loss and binding, the steering
deviation is **software-limited to a small maximum** (`STEER_MAX` in `robot.py`,
currently ±8°). This single constant caps every steering output (wall-follow,
obstacle-pass, emergency).

**Drive motor.** A single DC gear motor drives the rear axle through an **L9110S**
dual H-bridge:

| L9110S pin | Connection |
|---|---|
| `A-IA` | GPIO23 (PWM = forward) |
| `A-IB` | GPIO24 (PWM = reverse) |
| `VCC` | Battery + (motor supply, 2.5–12 V) |
| `GND` | Common ground (battery − **and** Pi GND) |
| MOTOR-A | DC motor terminals |

Speed is set by PWM on one input while the other is held LOW. A safety rule in
software (`motor()`): the car **never switches forward↔reverse directly** — it
coasts to a stop and waits (`STOP_FLIP_DELAY`) before reversing, because the
motor's back-EMF spike on a hard reversal can destroy the Pi's voltage regulator.

## 3. Power & sense management

**Power topology (critical).** Early testing showed the Pi rebooting whenever the
motor drew current. Two fixes were required and are now standard on the car:

1. **Separate rails.** The motor is powered **straight from the battery** to the
   L9110S `VCC`; the Raspberry Pi has its **own regulator**. The motor's current
   spikes never pass through the Pi's supply.
2. **Common ground.** Pi GND, driver GND and battery − are tied together, giving
   the GPIO control signals a shared reference. (Without it, the only link between
   Pi and driver is the signal wire, and motor current back-feeds the GPIO pin.)

**Sensing.** All perception comes from the camera. See §4.

## 4. Camera & vision

**Mounting.** Camera Module 3 Wide, mounted **12.5 cm above the mat**, tilted
**~15° downward**, centered laterally and facing straight ahead on a rigid mast.
It is physically **upside-down**, so frames are rotated 180° in software.

**Locked settings** (`camera.py`) — chosen from on-field capture tests so the
image is sharp, motion-frozen, and colour-stable:

| Setting | Value | Reason |
|---|---|---|
| Sensor mode | 2304×1296 (full 120° FOV) → scaled to 640×480 | keep the wide FOV, avoid the cropped mode |
| Orientation | `hflip + vflip` (180°) | camera mounted upside-down |
| Focus | **Manual**, `LensPosition ≈ 3.0` (~0.33 m) | sharp across the whole mat; no AF hunting mid-run |
| Exposure | fixed ~9 ms | freeze motion (long auto-exposure blurred when moving) |
| White balance | locked `ColourGains` | keep HSV thresholds stable as the car turns |

**Pipeline.** `capture → 180° flip → crop mat ROI → resize 320×160 → HSV`. HSV is
computed with `cv2.COLOR_BGR2HSV` on the RGB888 frame everywhere, so thresholds
transfer between tools and challenge code.

**Colour thresholds** live in `colors.json`, produced by the interactive
`color_tuner.py`. Six colours are tuned one-by-one: **black** (walls), **blue**
and **orange** (corner lines), **green** and **red** (traffic signs), **magenta**
(parking gate). Red uses a hue-wrap range.

## 5. Software architecture

All runtime modules live together (on the Pi: `~/wro2026/`):

```
camera.py               # locked camera setup (open_camera())
robot.py                # shared hardware + vision library (imported by both challenges)
open_challenge.py       # Open Challenge main
obstacle_challenge.py   # Obstacle Challenge main
colors.json             # tuned HSV thresholds (from color_tuner.py)
servo_center.txt        # steering center trim (from servo_center.py)
```

**`robot.py`** is the single source of truth for pins, the `servo()`/`motor()`
helpers (with the reverse-guard and steering clamp), the HSV `mask()` helper, and
the vision analysers: `wall_readings()`, `line_counts()`, `find_pillars()`,
`magenta_area()`, plus `LapTracker` and `WallFollower`.

### Open Challenge algorithm
1. **Wall-follow** the *outer* (continuous) wall with a PD controller — clockwise
   follows the left wall, counter-clockwise the right. Either wall getting
   dangerously close triggers a hard steer away.
2. **Direction** is set by the first corner line seen: **orange → clockwise**,
   **blue → counter-clockwise**.
3. **Lap counting**: a debounced falling-edge on the driving-direction line counts
   one *quadrant*; **12 quadrants = 3 laps**, then the car coasts briefly and stops.

### Obstacle Challenge algorithm
A strict per-frame **priority** decides steering:
1. **Wall emergency** — never crash a wall, even while dodging.
2. **Park** (after 3 laps) — hunt the **magenta** gate, aim at it, stop when close.
3. **Pillar** — pass **red on the right**, **green on the left** (steer to push the
   pillar toward the correct frame edge; react harder as it nears).
4. **Wall-follow** — the Open-Challenge behaviour otherwise.

### Speed
Base speed is `CRUISE` (per challenge). `cruise_speed()` automatically **slows in
proportion to steering effort** — full speed on straights, easing off in corners.

## 6. Tools (in `src/`)

| Script | Purpose |
|---|---|
| `test.py` | Menu-driven hardware bring-up: servo, motor, camera |
| `driver_on.py` | Bare L9110S on/off test |
| `motor_debug.py` | Direct-drive vs PWM comparison (stall diagnosis) |
| `motor_speed_steps.py` | Speed staircase 100→50 % to find the stall point |
| `servo_center.py` | Find & save the steering center trim → `servo_center.txt` |
| `color_tuner.py` | Interactive HSV tuner → `colors.json` |
| `cam_capture.py` | Field capture / focus & exposure testing |

## 7. Setup & run (Raspberry Pi, Bookworm)

```bash
# system packages (Bookworm ships these via apt, NOT pip)
sudo apt update
sudo apt install -y python3-picamera2 python3-libcamera python3-opencv python3-rpi-lgpio python3-venv

# project venv that can see the system camera/GPIO packages
python3 -m venv --system-site-packages ~/wro2026/.venv
source ~/wro2026/.venv/bin/activate
# NOTE: do NOT pip install numpy/opencv — the apt builds must match picamera2
```

Calibrate, then run:
```bash
cd ~/wro2026 && source .venv/bin/activate
python color_tuner.py        # tune colours (each object in view) -> colors.json
python servo_center.py       # center the steering        -> servo_center.txt
python open_challenge.py     # Open Challenge
python obstacle_challenge.py # Obstacle Challenge
```

## 8. Repository structure (official WRO Future Engineers layout)

```
README.md      # this engineering document
src/           # all control software (robot.py, camera.py, challenges, tools)
models/        # 3D-printable parts (printing/) and source CAD (3d-parts/)
schemes/       # wiring / electromechanical diagrams
t-photos/      # team photos (official + fun)
v-photos/      # vehicle photos (6 angles)
video/         # video.md — link to the driving demonstration
other/         # datasheets, rulebook, strategy notes
```

## 9. Photos & video

- Vehicle photos → `v-photos/` (6 angles). Team photos → `t-photos/`.
- Wiring diagram → `schemes/` (Pi ↔ L9110S ↔ servo ↔ power).
- Driving video → `video/video.md`.

---

*Team: (add names/roles). Built on Raspberry Pi 4 + Camera Module 3 Wide.*
