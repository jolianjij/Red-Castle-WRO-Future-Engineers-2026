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

**Reference study.** We analysed Team **KyivRoboMagic** (Ukraine, WRO 2024
International Final), who reached the world final with a camera-only car. Their
approach — HSV masks, wall-following by counting dark (wall) pixels in the left vs
right image halves, a proportional steering law, and orange/blue line counting for
laps — validated our direction and gave us a proven baseline to build on.

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

## 6. The no-differential steering problem

**Problem.** In turns the car **scrubbed and pushed wide**, sometimes stalling in
the corner.

**Investigation.** The drivetrain has **no differential**, so both driven wheels
are locked to the same speed. At larger steering angles the wheels must roll
different distances, so they scrub — wasting traction.

**Solution (interim).** We reduced the steering limit (`STEER_MAX`) step by step on
the field until the scrub disappeared, trading turning radius for traction.

**Solution (planned).** Fit a **small differential**. We surveyed how strong WRO
teams solve this and found most avoid *printed* differentials (too much backlash),
using compact **LEGO** or **micro RC** differentials instead. Our pick is a
**WLtoys 1/28 micro metal differential** — tiny, low-backlash, low-cost — after
which we can raise `STEER_MAX` and corner harder.

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

## 8. Software architecture

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
