# Engineering Journal — Team The Red Castle

The design process behind the car, written as problem → investigation → solution.
This is where most of the real engineering happened: making a single camera and a
low-cost drivetrain behave reliably.

---

## 1. Sensor strategy: why camera-only

**Decision.** Use one camera as the sole sensor — no LiDAR, ultrasonic, encoders,
or IMU.

**Reasoning.** Everything the rules reference is visible: walls, the orange/blue
corner lines (direction + laps), the red/green traffic signs, and the magenta
parking lot. A single camera can perceive all of it, which removes cost, weight,
wiring and failure modes. The trade-off — the camera must be *very* well
configured — became the focus of our work.

**Reference study.** We researched other camera-only Future Engineers builds that
reached the international final. The common approach — HSV masks, wall-following
by counting dark (wall) pixels in the left vs right image halves, a proportional
steering law, and orange/blue line counting for laps — validated our direction and
gave us a proven baseline to build on.

## 2. Camera: mounting and settings

**Problem.** First field captures were **blurry and dim**, and unusable once the
car moved.

**Investigation.** We captured stills on the actual mat and inspected them:
- The autofocus locked to **infinity** (the distant room), leaving the near mat
  soft.
- Auto-exposure sat at **~60 ms** in the ~100-lux room — fine for a still, but it
  would smear badly the instant the car moved.
- The camera is mounted **upside-down**, so every frame needed a 180° rotation.
- The 120°-FOV sensor has a **cropped** high-fps mode that would throw away the
  wide field of view we rely on to see both walls.

**Solution.** We locked the camera (`src/camera.py`):
- **Manual focus** at a fixed distance (tuned via a focus sweep) — sharp across the
  mat, no hunting.
- **Fixed short exposure (~9 ms)** to freeze motion; the mat stays bright enough
  for detection while the background clutter goes dark (and is cropped anyway).
- **180° flip** in the pipeline; **full-FOV sensor mode** (2304×1296) scaled to the
  working resolution.
- **Locked white balance** so HSV thresholds don't drift as the car turns.

**Mount.** 12.5 cm above the mat, ~15° down, centred and facing straight — a
lateral offset would bias the left/right wall comparison permanently.

## 2b. Changing the camera: autofocus was the wrong tool

**Problem.** Even with focus locked, **distant traffic signs were blurry**. Blur
desaturates colour, so the HSV masks lost far-away signs entirely — the car only
"saw" an obstacle once it was already close.

**Investigation.** This was not a tuning fault but a property of the sensor. The
Camera Module 3 has a comparatively large sensor and an autofocus lens, giving a
**shallow depth of field**: focused on the mat, anything far is soft; focused far,
the near mat is soft. A focus sweep confirmed we could have one or the other, not
both. Autofocus itself was also a liability — it hunted, and it locked to the
distant background rather than the track.

**Solution.** We replaced it with an **OV5647 wide-angle module** — a small sensor
with a **fixed-focus** lens. Small sensors have a much larger depth of field, so
the near mat and the far wall are sharp *at the same time*, and there is no
autofocus to hunt or mis-lock. A ground robot never needs to refocus, so losing
autofocus cost us nothing and removed a whole class of failure.

**Consequences.**
- `camera.py` was rewritten: the OV5647 has no `LensPosition`/`AfMode`, so those
  controls had to go (they raise an error on this sensor). Full-FOV mode is now
  1296×972.
- All colour thresholds had to be **re-tuned** — a different sensor renders colour
  differently, so the old `colors.json` was invalid.
- We also began raising **Saturation** in the ISP (~1.4), which separates
  red/orange/green/magenta in HSV at no CPU cost.

**Trade-off accepted.** The OV5647 is lower resolution and noisier in dim light
than the Module 3. For our task that does not matter: we process at 320×160 and
care about *where* colour regions are, not fine detail. Reliable focus everywhere
beat higher resolution somewhere.

## 3. The power brownout

**Problem.** The Raspberry Pi **rebooted every time the motor ran**. Repeated hard
resets also risked SD-card corruption.

**Investigation.** Classic voltage brownout: the motor's inrush/stall current
spikes sagged a shared rail below the Pi's under-voltage threshold. We also found
the motor driver's ground was **not connected to the Pi** — so the only link
between them was the GPIO signal wire, forcing motor return current through that
pin.

**Solution.** Two rules, now standard on the car:
1. **Separate power rails** — motor straight from the battery to the driver; the Pi
   on its **own regulator**. Motor spikes never reach the Pi's supply.
2. **Common ground** — Pi, driver and battery negatives tied together, giving the
   control signals a shared reference.

## 4. Motor driver and the stall

**Problem.** With power fixed, the motor **stalled/buzzed even at 100 %**, with
nothing mechanically blocking it.

**Investigation.** We isolated the PWM path from the power path with a direct
digital-drive test. The symptom (buzz, not spin) pointed at **insufficient
effective voltage**: the **L9110S drops ~1.5–1.8 V** across itself, so with a
modest battery the motor never sees enough to overcome static friction.

**Solution / status.** Confirmed the driver wiring and the voltage-drop
characteristic; the remedy is adequate battery voltage (and keeping the motor
within the L9110S's current limit). Documented so the battery choice in the BOM is
made with this headroom in mind.

## 5. Motor reversal safety

**Problem / insight.** Slamming the motor from forward straight into reverse pushes
the motor's **back-EMF onto the supply**, which can **destroy the Pi's regulator**.

**Solution.** The `motor()` function tracks the last non-zero direction and, on any
direction flip, **coasts to a stop and waits (`STOP_FLIP_DELAY`)** before driving
the other way. The protection lives inside `motor()` so *every* caller — including
the parking reverse — is safe automatically.

## 6. The steering-scrub problem, and the differential that fixed it

**Problem.** In turns the car **scrubbed and pushed wide**, sometimes stalling in
the corner.

**Investigation.** The first drivetrain used a **solid rear axle**, locking both
driven wheels to the same speed. In a corner the outer wheel must cover a longer
arc than the inner one; with a solid axle one of them has to slip. That slip
wasted traction, pushed the car wide, and loaded the motor enough to stall it
mid-turn.

**Interim workaround.** We cut the steering limit (`STEER_MAX`) down step by step
on the field until the scrub disappeared — roughly **8°**. It kept traction, but
the car then could not corner tightly enough to follow the track properly. We were
treating the symptom.

**Real solution — fit a differential.** We surveyed how strong WRO teams solve
this and found most avoid *printed* differentials (too much backlash), preferring
compact **LEGO** or **micro RC** units. We fitted a **differential on the rear
axle**, driven from the **N20 motor (12 V, 200 rpm)** through a **25:20 spur pair
(1.25:1 reduction)**.

**Result.** The driven wheels can now turn at different speeds, so the scrub is
gone at its source. We raised `STEER_MAX` from ~8° to the linkage's full
**±35°**, and the car corners tightly without losing traction or stalling.

**Lesson.** The software limit was a workaround for a mechanical flaw. Capping the
steering hid the symptom but cost cornering ability; fixing the drivetrain removed
the constraint entirely and let the controller use the full mechanical range.

## 7. Vision tuning

**Problem.** Colour detection was inconsistent — especially signs far away.

**Investigation.** Two causes: (a) unlocked exposure/AWB made HSV drift (fixed in
§2), and (b) the interactive tuner can only tune a colour while that object is in
the camera's view, so colours whose objects weren't staged stayed at defaults. We
also caught a tuner bug where a magenta range with `h_low > h_high` was
mis-interpreted as a hue-wrap and matched almost everything.

**Solution.** A one-colour-at-a-time tuner (`tools/color_tuner.py`) that writes
`colors.json`, with each object staged in front of the camera; a validation step
that renders every mask on a live capture to confirm cleanliness before driving.

## 7b. Validating the free-space navigator with measured data

**Approach.** Before letting the car drive on the new navigator we validated the
*perception* alone with `tools/freespace_test.py`, which draws the detected
mat/wall boundary and the chosen gap on a real frame **without touching the
motor**. The car was placed at measured distances from a wall and each frame was
recorded.

**Measurements** (head-on to a wall, `front` = wall fill straight ahead,
`free` = drivable depth in the wall-ward columns):

| Distance to wall | `front` | `free` at wall columns | Steering produced |
|---|---|---|---|
| far (>60 cm) | 0.15 | 0.94 | 0° (correctly ignores) |
| 40 cm | 0.40 | 0.82 | −6.5° (begins easing away) |
| 25 cm | 0.51–0.54 | 0.74 | full turn once corrected |

**Three defects this exposed — none of which a driving test would have shown
safely:**

1. **The "open" threshold was far too permissive.** `GAP_OPEN_FRAC = 0.55` meant a
   wall only 25 cm ahead still scored 0.74 and counted as drivable, so the gap
   spanned the whole frame and the car would have driven straight into the corner.
   Raised to **0.80**, chosen from the measured spread above.
2. **Corner detection used the wrong signal.** It compared `left + right` against
   0.55; at 25 cm that read **0.54 — it would have missed the corner by 0.01**.
   The `front` metric separates distance far better (0.15 / 0.40 / 0.51), so
   corner detection now uses `front` with a threshold of 0.38, firing ~40 cm out.
3. **A fisheye sliver was mistaken for an opening.** With a wall spanning the
   whole view, a **12-pixel-wide** artifact at the extreme frame edge — where the
   wide lens sees *past* the wall — was selected as the gap and produced a
   **+23° steer into the wall**. Fixed by requiring a gap to be at least **60
   columns** wide (the car is ~20 cm wide, so a real opening occupies a large
   fraction of the frame) and by ignoring 20 edge columns instead of 10.

**Result.** At 25 cm the navigator now reports `front=0.51 CORNER!` and
`NO GAP - blocked`, and the full decision chain commands a committed **−35° turn
with speed automatically reduced to 50 %**. Perception is also extremely stable:
20 consecutive frames of a static scene produced *identical* readings, so there is
no jitter entering the steering loop.

**Lesson.** Validating perception separately from control, with the robot
stationary at measured distances, found three failures that would each have caused
a crash — and cost nothing but a few minutes. Numbers from the field, not intuition,
set every threshold.

## 9. The bug that cost us the most: the car could not tell a LINE from a WALL

**Symptom.** The car followed the wall correctly along a straight, then crashed
near the corner. It did this in **both** directions, and no amount of gain,
setpoint or steering-limit tuning changed it. Every fix helped for a metre and
then failed in the same place.

**Why it resisted diagnosis.** Each failure looked like a control problem, so we
kept tuning the controller. We re-derived gains, rescaled the setpoint, rewrote
the corner logic and added an emergency override. The behaviour barely moved.
That pattern - a controller that behaves well in one region and fails identically
in another - should have pointed at the *input* much sooner than it did.

**How we found it.** We stripped the program down to the bare control law (no
emergency, no corner state machine, no lap counting) and made it **save an
annotated frame whenever the steering exceeded 12 degrees**, drawing every pixel
the code counted as "wall" in red. Looking at those frames answered the question
immediately.

**Root cause.** The wall detector was `value < 62` - *any* dark pixel. The blue
corner line, the orange corner line and the mat's printed dotted markings are all
dark, so **they were being counted as walls**. Worse, they were not spread evenly
between the left and right halves of the image, so they injected a *steering
bias* - and they only entered the frame near the corners. That is exactly why the
fault appeared at corners, in both directions, and was immune to tuning: the
controller was fine, its measurement was not.

Measured on one failure frame, removing them changed the reading from
`left 0.164 / right 0.256` to `left 0.072 / right 0.172` - the left inflated by
2.3x and the right by 1.5x.

**The fix, and a trap inside it.** The obvious repair is "a wall is dark AND
desaturated, a coloured line is saturated". That alone **fails**: HSV saturation
is numerically meaningless when brightness is near zero, so a genuinely black wall
can report S > 200 from sensor noise. Tested on a nose-to-wall frame, a
saturation-only rule discarded **99%** of a real wall. The rule that works needs
both cases:

```
wall = (V < 32)                      very dark  -> wall regardless of saturation
       or (V < 62 and S < 90)        dark AND desaturated
followed by a morphological open to drop the small printed dots
```

**Consequence.** Every distance constant in the project had been calibrated
against the faulty mask and was void. We re-measured from scratch, car parallel to
the outer wall, gap measured car-side to wall-face:

| Distance | Density |
|---|---|
| 40 cm | 0.1032 |
| 25 cm | 0.1783 |

giving 0.00501 density per cm. From that, every threshold became a real distance:
driving line **40 cm**, emergency **18 cm**, full steering lock at **20 cm** of
error - and, importantly, **22 cm of margin** between the driving line and the
panic threshold, where the earlier (mis-calibrated) values had left only 13 cm and
made the emergency fire almost continuously.

**A related instrumentation bug.** The mat is a warm cream at hue ~17, saturation
~42 - inside the orange range we had set. The orange mask was therefore matching
**44% of the image with the car parked**, which would have locked the driving
direction from a false reading on the very first frame. The real orange line
measures hue 5-8 at saturation 86-94, so hue *and* saturation separate them:
`H 2-13, S >= 72`. Parked, both line detectors now read 0.0000.

**Result.** With the measurement corrected and the constants re-derived in
centimetres, the car completed the Open Challenge **in both directions with stable
control**.

**Lesson.** When a controller fails identically in one specific place and resists
every tuning change, stop tuning and go and *look* at what the sensor is
reporting. An annotated frame answered in one glance what hours of parameter
changes could not, because the fault was never in the control law.

## 10. Software architecture

We consolidated all hardware and vision logic into a single shared library
(`src/robot.py`) imported by both challenge programs, so pins, the `servo()`/
`motor()` safety, HSV masking, and the wall/line/sign analysers are defined **once**.
Each challenge is a thin main loop: the Open Challenge is pure wall-follow + lap
counting; the Obstacle Challenge is a strict priority state machine
(wall-emergency → park → sign-pass → wall-follow). Calibration outputs
(`colors.json`, `servo_center.txt`) are plain files the library loads at start, so
re-tuning never touches code.

---

_This journal is a living document; entries are added as the design evolves._
