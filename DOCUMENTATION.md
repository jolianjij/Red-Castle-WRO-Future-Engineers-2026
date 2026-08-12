# Engineering Documentation — WRO 2026 Future Engineers

**Team Name:** The Red Castle
**Team Members:** Jolian Wassof, Omar Shammout, Louay Rashwan
**Team Coach:** Ahmad Kalthom
**Club:** HMK AI and Robotics Club

> **[ INSERT IMAGE: `team-logo` — The Red Castle team logo (cover page) ]**

---

## Table of Contents

1. Introduction
2. Solution
   1. Open Challenge
   2. Obstacle Challenge
3. Mobility Management
   1. The Steering Assembly
   2. The Driving Assembly
   3. The Robot's Body / 3D Design
   4. The Mobility Measurement
4. Power and Sense Management
   1. The Robot's Power Source
   2. Main Components
   3. Wiring Diagrams
   4. Sensing
5. The Evolution of The Robot
   1. Past
   2. Present
   3. Future
6. The Vehicle's Photos
7. Links and Credits

---

## 1. Introduction

Last season we built a self-driving car for this same category, and it worked — but
by the end of it we had a long list of things we wished we had done differently. The
LEGO parts flexed. The camera had to be re-tuned every time the room lighting
changed. And the car could never corner properly because the rear axle was solid.

So this year we started again from the chassis up. The goal was the same: a vehicle
that senses its environment and drives itself around the mat without anyone touching
it. What changed is how much of it we designed ourselves, and how much of it we
insisted on *measuring* instead of guessing.

The car uses a **Raspberry Pi 4 Model B (2 GB)** as its brain and a **single wide-angle
camera** as its only sensor. There is no LiDAR, no ultrasonic sensor, no encoder and
no IMU on this robot. Everything it knows about the track — where the walls are,
which direction it is lapping, where the traffic signs are, where the parking lot is —
it works out from one camera image, thirty times a second.

That was a deliberate choice and we explain our reasoning for it in section 4.

---

## 2. Solution

We solved the two challenges separately, but they share the same image processing
and the same hardware. Only the decision-making on top of it differs.

### 2.1 Open Challenge

For the open challenge the robot has to drive three laps around the mat without
touching a wall, and the inner walls are moved to random positions before each round,
so the corridor is a different width every time.

Our approach is built on **following the outer wall**. The outer wall is the one thing on
the track that never moves. If the robot keeps a constant distance from it, the random
inner walls stop mattering entirely — we never measure them at all.

> **[ INSERT IMAGE: `game-field-mat` — Figure 1: The Game Field Mat ]**

The steering is handled by a **PD controller** working on a single error value: how far
the robot is from its target distance to the outer wall. Corners are detected from the
coloured strips on the mat, and the same strips are counted to know when three laps
are finished.

Below is a step-by-step breakdown of how it runs.

#### 2.1.1 Starting the Robot

The robot is placed on the mat and the main power switch closes the circuit. The
program is then started from the terminal (or by the push button, which is wired to
GPIO 9). The camera initialises, the calibration files are loaded, and the program
waits for a keypress before the motor starts — this gives us a moment to get our
hands clear.

On start-up the program prints its whole configuration, which we found genuinely
useful during testing:

```
config: NAV_METHOD=outer CRUISE=100 STEER_MAX=20 trim=-9.0
colors loaded: ['black', 'blue', 'orange', 'green', 'red', 'magenta']
logging -> logs/open_20260812_031805.csv
```

#### 2.1.2 Image Processing

The camera captures at **640×480**. Because of how the camera is mounted on the
mast, the image arrives upside down, so the first thing we do is rotate it 180°.

We then cut away the top 160 rows. Those rows contain the room — chairs, people,
walls of the building — none of which are on the game field, and all of which caused
us problems last year. What remains is the mat and the walls, and that region is
resized down to **320×160** pixels.

> **[ INSERT IMAGE: `raw-frame` — Figure 2: Raw Image from the camera (before flip) ]**
> **[ INSERT IMAGE: `processed-frame` — Figure 3: Processed Image (flipped, cropped, resized) ]**

A median blur is applied before anything else. We run the camera with a short
exposure so that the picture does not smear while the car is moving, and the cost of a
short exposure is a noisier image. The blur cleans that up.

The image is then converted to **HSV** (Hue, Saturation, Value), which is the colour
model we use for every detection on the robot. HSV separates *what colour* something
is from *how bright* it is, which matters a lot on a mat that has bright patches and
shadowed patches.

From the HSV image we extract:

* **Walls** — any pixel darker than a set brightness. The image is split down the
  middle and we count the dark pixels in each half separately, giving a left-wall
  reading and a right-wall reading.
* **Corner strips** — blue and orange. These are only searched for in the **bottom
  45 %** of the image, because the strips are painted on the mat and can only ever
  appear there. Anything blue near the top of the frame is part of the room, not the
  track.
* **Traffic signs and the parking lot** — red, green and magenta, used in the
  obstacle challenge.

> **[ INSERT IMAGE: `wall-mask` — Figure 4: Wall detection — walls shown in white ]**
> **[ INSERT IMAGE: `line-detection` — Figure 5: The robot's view of the corner strips ]**

#### 2.1.3 Analysis and Solving the Challenge

**Step One.** When the program starts, the motor spins up and the camera begins
processing. We measured the loop at about **30 frames per second**, which works out
to roughly 33 ms per frame.

**Step Two — deciding the direction.** The robot does not know which way round the
track it is going until it sees its first coloured strip. Whichever strip is bigger in the
frame decides it: **orange means clockwise**, **blue means counter-clockwise**. The
wall geometry is checked at the same time as a second opinion, and if the two agree
the program prints a confirmation. Once the direction is set it is **locked for the whole
run** and can never change. That was a deliberate fix — an earlier version could flip
direction mid-lap, which ruined several test runs.

The direction also decides which wall is the outer one:

| Driving direction | Outer wall | Corners are |
|---|---|---|
| Clockwise (orange first) | on the **left** | right turns |
| Counter-clockwise (blue first) | on the **right** | left turns |

**Step Three — staying on line.** Every frame, the robot compares its outer-wall
reading against a target value and steers to correct the difference:

```
clockwise          error = left_wall  − target
counter-clockwise  error = target − right_wall

steering = Kp × error + Kd × (error − previous error)
```

The proportional term does the correcting and the derivative term stops it
oscillating. We limit the steering to ±20° in software even though the linkage can
physically reach 35°, because at full speed anything sharper makes the car unstable.

We **measured** the target rather than guessing it. With the car parked parallel to the
outer wall we recorded the wall reading at two known distances:

| Distance from outer wall | Wall reading |
|---|---|
| 29 cm | 0.2044 |
| 19 cm | 0.2619 |

That gives a slope of **0.00575 per centimetre**, so we can convert the robot's
steering behaviour into real distances:

| Distance from wall | Steering output |
|---|---|
| 39 cm (too far) | −11.7° (steer toward the wall) |
| **29 cm (target)** | **0°** |
| 19 cm (too close) | +11.9° (steer away) |
| 9 cm (about to hit) | +20° (full lock) |

**Step Four — the corners.** When the robot crosses the coloured strip that matches
its driving direction, it knows it is physically at a corner, so it holds full steering
lock for a fixed time and then goes back to following the wall. Triggering the turn from
the strip rather than from a wall measurement makes the timing predictable.

Because a missed strip would mean a missed turn, there is a **backup**: if the wall
directly ahead gets close and no strip has fired, the turn is triggered anyway. The
strip is the primary trigger and the geometry is the safety net.

**Step Five — counting laps.** Each strip crossing counts as one quadrant, but only if
a **timer** has expired since the last one. This was necessary — without it a single
strip that flickered in and out of view was counted several times, and one of our early
runs recorded eleven laps that never happened. The timer restarts on every count, so
one physical crossing can only ever add one.

The robot stops after the eleventh quadrant plus the timer, which leaves it resting in
the starting section rather than halted on top of a line.

**A wall emergency overrides everything.** If either wall gets too close, the robot
steers hard away from it regardless of what any other part of the program wants. This
sits above the wall following, above the corner turn, above everything.

### 2.2 Obstacle Challenge

The obstacle challenge adds red and green traffic signs to the track. The robot has to
pass **red signs on their right** and **green signs on their left**, then park in the
magenta parking lot after three laps.

> **[ INSERT IMAGE: `obstacle-map` — Figure 6: Obstacle Challenge Map ]**

The image processing is identical to the open challenge. What changes is the
decision-making, which runs as a strict priority list. Each frame, the first rule that
applies wins:

| Priority | Behaviour | Why it sits here |
|---|---|---|
| 1 | **Wall emergency** | Touching a wall ends the run. Nothing may override this, not even an obstacle manoeuvre. |
| 2 | **Parking** (after 3 laps) | Once the laps are done the mission goal changes. |
| 3 | **Passing a sign** | Sign obedience scores points, so it outranks ordinary lane keeping — but never safety. |
| 4 | **Corner turn** | A committed turn through a corner. |
| 5 | **Wall following** | The default behaviour when nothing else applies. |

#### 2.2.1 Detecting the Signs

Red and green pixels are turned into masks, and `cv2.findContours()` groups them
into shapes. A shape is only accepted as a sign if it is **taller than it is wide** —
traffic signs are upright, so this simple test throws out reflections and stray marks.
Of the ones that pass, the robot acts on the **nearest**, which is the one whose base
sits lowest in the image.

> **[ INSERT IMAGE: `pillar-detection` — Figure 7: Red and green sign detection with contours ]**

Separating red from orange gave us trouble, because in the HSV model red and orange
sit right next to each other, and the orange strip is on the mat where signs also
stand. We solved it by measuring both:

| Object | Hue | Saturation |
|---|---|---|
| Red sign | ~178 | **252** |
| Orange strip | ~5–8 | **~90** |

The saturation difference is large and reliable, so we separate them on **saturation as
well as hue** — red requires a high saturation, orange is capped below it. After this
change the two masks share **zero** pixels.

#### 2.2.2 Passing a Sign

Passing is done by steering so that the sign moves toward the correct side of the
image. For a red sign the robot steers to push it toward the left edge of the frame,
which sends the car around its right side; a green sign is pushed toward the right
edge. The correction is proportional to how far off the sign is, and it grows stronger as
the sign gets nearer. If the sign is lost for a frame or two the manoeuvre is held, so a
single bad frame does not abandon a pass halfway through.

#### 2.2.3 Parking

After three laps the robot looks for the **magenta** parking lot, steers toward its
centre, and stops once it fills enough of the frame to mean the car is inside the bay.

---

## 3. Mobility Management

### 3.1 The Steering Assembly

**SG90 Micro Servo Motor.** Steering is driven by a single SG90 servo connected to
**GPIO 13**, which is one of the Raspberry Pi's hardware-PWM pins — we chose that pin
deliberately, since a software-generated PWM signal jitters and makes the wheels
twitch. The SG90 runs on 4.8–6 V, covers 180°, and is controlled by pulse width: 1.5 ms
holds centre, with roughly 1 ms and 2 ms at the extremes. It is small and light, which
matters on a car this size, and its torque is more than enough to turn a steering
linkage that carries no vehicle weight.

> **[ INSERT IMAGE: `sg90` — Figure 8: SG90 Micro Servo Motor ]**

**Ackermann steering geometry.** The servo drives a central bell-crank, which pushes
a tie-rod out to both steering knuckles. The linkage is set up so the **inner wheel
turns through a sharper angle than the outer wheel** during a corner. This is the
Ackermann principle, and the reason for it is that in a turn the two front wheels are
travelling around circles of different radius. If both wheels pointed the same way, one
of them would have to skid. With Ackermann geometry each wheel rolls along its own
path.

The full mechanical travel of our linkage is **±35°**. In software we limit it to **±20°**,
which we found gave better stability at full speed.

> **[ INSERT IMAGE: `steering-cad-centered` — Figure 9: Steering linkage, wheels centred (CAD) ]**
> **[ INSERT IMAGE: `steering-cad-turned` — Figure 10: Steering linkage at full lock (CAD) ]**
> **[ INSERT IMAGE: `steering-assembly-photo` — Figure 11: The steering assembly on the car ]**

**Finding the true centre.** The servo horn cannot be mounted at a perfect angle, so
"centre" in software is not the same as wheels-pointing-straight in reality. We wrote a
small calibration tool that lets us nudge the servo a degree at a time until the wheels
are genuinely straight, then saves that offset to a file which the main program loads
at start-up. Our measured trim is **−9°**. Re-calibrating never means editing code.

### 3.2 The Driving Assembly

**GA12-N20 Geared Mini DC Motor (12 V, 200 RPM).** We used an N20 again this year.
It is small, it has a metal gearbox, and the torque is enough to pull the car away from
rest without stalling. We went with the 200 RPM version rather than the 150 RPM one
we used last season because the extra speed is useful and the differential means we
no longer lose energy to wheel scrub.

> **[ INSERT IMAGE: `n20-motor` — Figure 12: GA12-N20 Geared Mini DC Motor ]**

**L9110S Motor Driver.** The motor is driven through an L9110S dual H-bridge. It takes
two input pins per channel — we use **GPIO 24** and **GPIO 23** — and the speed is set
by sending a PWM signal on one pin while holding the other low. Reversing is a matter
of swapping which pin carries the PWM. It is rated for 2.5–12 V and handles the
current our motor draws.

> **[ INSERT IMAGE: `l9110s` — Figure 13: L9110S Motor Driver ]**

One thing we learned the hard way is written into the code as a rule: **the motor is
never switched straight from forward to reverse.** The program forces it to coast to a
stop and wait before driving the other way. When a spinning motor is suddenly
reversed, the energy stored in it is pushed back into the supply, and that spike is
capable of destroying the voltage regulator feeding the Raspberry Pi. The delay costs
0.3 s and only ever happens during parking.

**The differential — the biggest mechanical change this year.** Our previous car had a
solid rear axle, which forces both driven wheels to turn at exactly the same speed. In
a corner the outer wheel has further to travel than the inner one, so with a solid axle
one of them has to slip. That slip cost us traction, pushed the car wide in every turn,
and sometimes loaded the motor enough to stall it.

We worked around it in software last year by cutting the steering angle right down —
about 8° — which kept the wheels gripping but left the car unable to corner properly.
It treated the symptom.

This year we fitted a **differential** on the rear axle, driven from the motor through a
**25:20 spur gear pair** (a 1.25:1 reduction). The wheels can now rotate at different
speeds, the scrub is gone at its source, and we can use the full steering range. This
single change did more for the car's cornering than any amount of software tuning.

> **[ INSERT IMAGE: `differential-cad` — Figure 14: Rear axle and differential (CAD) ]**
> **[ INSERT IMAGE: `differential-photo` — Figure 15: The differential assembly installed ]**
> **[ INSERT IMAGE: `gear-pair` — Figure 16: 25:20 spur gear pair between motor and differential ]**

### 3.3 The Robot's Body / 3D Design

The entire chassis was designed by us in **Fusion 360** and printed on a **Bambu Lab
A1** in **PLA+ Silk Silver**.

We wanted the car small, low, and easy to work on. The battery and the Pi sit over the
wheelbase so the mass is central and low down, the wiring stays reachable without
taking the car apart, and the camera mast is a single rigid piece rather than an arm
that can flex. That last point is not cosmetic — a camera that vibrates produces noisy
wall measurements, and noisy measurements go straight into the steering.

> **[ INSERT IMAGE: `chassis-cad-top` — Figure 17: Chassis, top view (CAD) ]**
> **[ INSERT IMAGE: `chassis-cad-side` — Figure 18: Chassis, side profile (CAD) ]**
> **[ INSERT IMAGE: `chassis-baseplate` — Figure 19: Base plate with mounting hole pattern ]**
> **[ INSERT IMAGE: `robot-full-3d` — Figure 20: The complete robot, 3D design ]**

The STL files and the sliced, print-ready plates are in the repository.

### 3.4 The Mobility Measurement

To work out the robot's velocity we need the following:

**The perimeter of the wheels (Pw):**
```
wheel diameter = 4.7 cm  →  rw = 0.0235 m
Pw = 2πrw = 2 × 3.1416 × 0.0235 ≈ 0.1476 m
```

**The speed at the axle (ω):**
```
motor speed          = 200 RPM
gear reduction 25:20 = 1.25 : 1
ω = 200 / 1.25 = 160 RPM
```

**The velocity of the robot:**
```
v = Pw × ω = 0.1476 × 160 = 23.62 m·min⁻¹
v ≈ 0.394 m·s⁻¹
```

**The power of the robot:**
```
P = V × I = 12 × 0.8 = 9.6 W
```

The 0.394 m/s figure is the theoretical no-load ceiling. The real speed on the mat is
lower once friction and the weight of the car are taken into account.

> **[ MEASUREMENT TO ADD: timed run over a measured distance to record the real top speed ]**

**Measured physical properties:**

| Property | Value |
|---|---|
| Mass | 407 g |
| Overall dimensions (L × W × H) | 14.2 × 9.3 × 15 cm |
| Wheel diameter | 4.7 cm |
| Wheelbase (front axle ↔ rear axle) | 9.4 cm |
| Track (rear wheel centre ↔ centre) | 8.5 cm |
| Steering range (mechanical) | ±35° |
| Steering range (used in software) | ±20° |

---

## 4. Power and Sense Management

### 4.1 The Robot's Power Source

**3 × 18650 Lithium-Ion Cells in Series.** Three 18650 cells wired in series give a
nominal **11.1 V**, rising to about 12.6 V fully charged. We chose 18650s because they
are easy to source, easy to replace mid-session, and hold enough charge to get through
a long testing session.

> **[ INSERT IMAGE: `18650-pack` — Figure 21: 3 × 18650 battery pack and holder ]**

A note we want to record honestly: a freshly charged pack sits at **12.6 V**, and the
L9110S is rated to **12 V**. That is marginally over specification for the first part of a
run, and we keep an eye on the driver temperature because of it.

**DC-DC Buck Converter.** The Raspberry Pi cannot be fed from the battery directly, so
a step-down converter takes the pack voltage and produces a stable **5 V** for the Pi.
It is adjustable and rated well above what the Pi draws, and that headroom is
deliberate.

> **[ INSERT IMAGE: `buck-converter` — Figure 22: DC-DC buck converter module ]**

**Rocker Switch.** A single switch in the battery line is the master power control for
the whole robot.

**Smoothing Capacitor.** A capacitor across the motor driver's supply absorbs the
current spike when the motor starts, which would otherwise show up as a voltage dip
everywhere else on the robot.

> **[ INSERT IMAGE: `capacitor` — Figure 23: Smoothing capacitor across the motor supply ]**

#### The power problem we had to solve

Early in the build the Raspberry Pi rebooted every single time the motor ran. It took
us a while to understand it, and the fix defines how the robot is wired now.

There were two faults. The first was that the motor and the Pi were sharing one supply,
so every time the motor drew a surge of current the voltage sagged and the Pi
browned out. The second was that the motor driver's ground was not connected to the
Pi at all — the only wire between them was the signal line, which meant the motor's
return current was trying to travel back through a GPIO pin.

The rules we now follow:

```
Battery + ─┬──────────────────────────► L9110S VCC   (motor power, straight from the pack)
           └──► DC-DC buck (5 V) ─────► Raspberry Pi 5 V
Battery − ───── COMMON GROUND ───── L9110S GND ───── Pi GND
```

1. **Separate rails.** The motor is fed directly from the battery and the Pi has its own
   converter. Motor current never passes through the Pi's supply.
2. **One common ground.** Battery negative, driver ground and Pi ground are all tied
   together, so the control signals share a reference.

Since making both changes we have not had a single brownout.

#### Power budget

| Load | Rail | Typical | Peak |
|---|---|---|---|
| Raspberry Pi 4 (2 GB) | 5 V | ~0.6 A | ~1.2 A |
| OV5647 camera | via the Pi's CSI port | ~0.25 A | ~0.25 A |
| SG90 steering servo | 5 V | ~0.15 A | ~0.7 A |
| N20 drive motor | 12 V | ~0.15 A | ~0.8 A |

The 5 V side draws about 1 A in normal running and around 2 A in the worst case where
the Pi peaks at the same moment the servo snaps to full lock. Our converter is rated
comfortably above that, which is intentional — under-sizing this rail is exactly what
caused the brownouts.

### 4.2 Main Components

#### 4.2.1 OV5647 Wide-Angle Camera Module

The camera is a 5 MP **OV5647** with a wide-angle lens, roughly 120° field of view, and
it is the robot's only sensor. It connects to the Pi's dedicated **CSI port** through a
flat ribbon cable, so it uses no GPIO pins and needs no separate power supply.

> **[ INSERT IMAGE: `ov5647` — Figure 24: OV5647 wide-angle camera module ]**

**Why we changed camera.** We began this season with the Raspberry Pi Camera Module 3
Wide, the same one we used last year. It has a better sensor on paper, but it gave us a
problem we could not tune our way out of: its large sensor and autofocus lens produce a
**shallow depth of field**. Focused on the mat, distant traffic signs went blurry — and
blur washes the colour out of an object, so the signs simply stopped being detected
until the car was almost on top of them. Focus it far away instead and the near mat
went soft. We could have one or the other, never both. The autofocus was a second
problem on its own, because it hunted during runs and kept locking onto the room
behind the track.

We replaced it with the OV5647, which has a **small sensor and a fixed-focus lens**.
Small sensors have a much larger depth of field, so the near mat and the far wall are
sharp at the same time, and there is no autofocus to hunt or mis-lock. A car that drives
on the floor never needs to refocus, so losing autofocus cost us nothing and removed a
whole category of failure.

The trade-off we accepted is lower resolution and more noise in dim light. For our
purposes that does not matter — we process the image at 320×160 and we care about
*where* the colour regions are, not fine detail.

#### 4.2.2 Raspberry Pi 4 Model B (2 GB)

The Raspberry Pi 4 Model B is the robot's central processor. It has a quad-core
Cortex-A72 running at 1.8 GHz and our version carries 2 GB of RAM. It provides the CSI
camera interface, a 40-pin GPIO header with hardware PWM, and enough processing
power to run the whole vision pipeline at 30 frames per second while also driving the
motor and servo.

> **[ INSERT IMAGE: `rpi4` — Figure 25: Raspberry Pi 4 Model B ]**

Everything runs in Python, using **OpenCV** for image processing, **Picamera2** for the
camera, and **RPi.GPIO** for the motor and servo.

#### 4.2.3 Push Button

A push button on GPIO 9 is used to start a run without needing a keyboard.

### 4.3 Wiring Diagrams

> **[ INSERT IMAGE: `wiring-diagram` — Figure 26: Full wiring diagram ]**
> **[ INSERT IMAGE: `schematic` — Figure 27: Schematic ]**

| Signal | Pi pin (BCM) | Connects to |
|---|---|---|
| Steering servo PWM | **GPIO 13** | SG90 signal wire |
| Motor `A-IA` | **GPIO 24** | L9110S input — PWM here drives forward |
| Motor `A-IB` | **GPIO 23** | L9110S input — PWM here drives reverse |
| Start button | GPIO 9 | push button to ground |
| Ground | any GND pin | common ground rail |
| Camera | CSI port | OV5647 via ribbon cable |

### 4.4 Sensing

Everything the robot knows comes from one camera, so where that camera sits is not a
detail — it is part of the algorithm. Each number below follows from the field itself.

| Choice | Value | Reasoning |
|---|---|---|
| Height above the mat | **12.5 cm** | The walls are 10 cm tall. The lens has to sit **above** the wall line so the camera looks down onto the mat and can see where each wall *meets the floor*. That mat-to-wall edge is the highest-contrast feature available to us. Mounted below 10 cm the walls fill the frame as a flat black band carrying no distance information at all. |
| Tilt | **~15° downward** | Enough to keep the mat and both wall bases in the lower part of the frame, while still seeing far enough ahead to notice a corner or a traffic sign before reaching it. |
| Position | **centred, facing straight** | Wall following compares the left half of the image against the right half. Any sideways offset or twist becomes a permanent steering bias that no amount of tuning will remove. |
| Lens | **~120° wide** | A narrow lens cannot see both side walls at once inside the corridor. |
| Mast | **rigid** | Vibration blurs the wall edge and feeds noise straight into the steering loop. |

> **[ INSERT IMAGE: `camera-too-low` — Figure 28: Camera mounted too low — it sees past the walls and out of the field ]**
> **[ INSERT IMAGE: `camera-too-high` — Figure 29: Camera mounted too high — it captures the room beyond the field ]**
> **[ INSERT IMAGE: `camera-correct` — Figure 30: Correct position — only the game field is visible ]**

#### Camera settings and calibration

Everything the camera does automatically, we turn off and set ourselves:

| Setting | Why it is fixed |
|---|---|
| **Exposure** (short, ~9–12 ms) | Auto-exposure settled on about 60 ms, which smeared the image the moment the car moved. |
| **White balance** (locked) | Explained below. |
| **Focus** | Fixed by the lens — nothing to set, and nothing that can drift. |
| **Saturation** (raised slightly) | Makes red, orange, green and magenta separate more cleanly in HSV, at no processing cost. |

**The white balance problem.** This is the single biggest thing we got wrong this
season, and it wasted several hours before we found it.

Our colour detection kept failing in ways that made no sense. Orange was never
detected at all, no matter what threshold we set. When we finally looked at the raw
numbers instead of the thresholds, we found that **almost every pixel in the frame was
being reported as a strongly saturated magenta** — the mat, which is white, was
reading as pink. The camera's colour gains were wrong, and the whole image had a
colour cast over it.

There was no orange in the picture to find. Every threshold we had set — and every
threshold we had carefully tuned by hand — was being applied to colours the camera
was reporting incorrectly.

We fixed it by letting the camera's automatic white balance settle on the mat under our
lighting, reading the gains it chose, and then locking those values permanently. After
the fix the mat reads as neutral, and the number of "saturated" pixels in a typical
frame dropped from about 47,000 to about 3,500.

The lesson we took from it: check that the image itself is correct before tuning
anything that depends on the image.

**Colour calibration.** With an honest image, we tune each colour on the real mat with
the real objects in front of the camera, and the values are written to a file which the
program loads at start-up. Re-tuning at a competition never means touching code. The
same applies to the steering centre and the camera settings — three files, all
generated by calibration tools we wrote.

---

## 5. The Evolution of The Robot

### 5.1 Past

Last season's robot was built mostly from LEGO Technic parts with a few 3D-printed
brackets holding things together. It completed both challenges, and we were happy with
it at the time, but testing exposed limits we could not design around:

* The LEGO beams flexed slightly under load, which conflicted with the rigidity the
  steering and the camera mast needed.
* The rear axle was solid, so the car scrubbed its wheels in every corner.
* There was nowhere secure to mount the battery.
* Parts were held with temporary fixtures rather than a proper solution.

> **[ INSERT IMAGE: `old-robot` — Figure 31: Last season's LEGO-based design ]**

### 5.2 Present

This year's car is a full redesign. The body is entirely our own CAD, printed rather than
assembled from a kit, and it was drawn around the components instead of the
components being squeezed into whatever the kit allowed.

The three changes that mattered most:

1. **A differential on the rear axle**, which removed the wheel scrub at its source and
   let us use the full steering range instead of limiting it to about 8°.
2. **A fixed-focus wide camera**, which keeps the whole track sharp and removed the
   autofocus as a source of failure.
3. **A properly separated power system**, with the motor fed straight from the battery,
   the Pi on its own regulator, and a common ground tying it all together.

We also changed how we work. Almost every constant in this year's software comes from
a measurement rather than a guess, and the car writes a log of every frame during a
run — steering, wall readings, mode, lap count — so that after a bad run we can read
what the robot actually did instead of arguing about what we think it did. Several
faults this season were only found because of those logs.

> **[ INSERT IMAGE: `current-robot` — Figure 32: The current robot ]**

### 5.3 Future

**Metric perception.** Our wall measurement is still a count of dark pixels, which is a
rough substitute for distance. The walls are a known height and the mat is a flat plane,
so with a proper camera calibration we could convert what we see into real distances in
centimetres and set our targets in physical units instead of pixel fractions. We have
started reading about inverse perspective mapping for this.

**Shadow handling.** We noticed during testing that shadows falling across the mat can
be dark enough to be counted as wall, which affects the steering in the corners where it
happens. We want to separate a real wall — a tall solid dark region — from a shadow,
which is broader and shallower.

**Speed.** The car currently runs at a speed chosen so the vision loop always has time to
react. A faster frame rate would let us raise that.

**Size.** There is room to make the car smaller, mostly by rearranging the battery.

---

## 6. The Vehicle's Photos

> **[ INSERT IMAGE: `v-front` — Front view ]**
> **[ INSERT IMAGE: `v-back` — Back view ]**
> **[ INSERT IMAGE: `v-left` — Left side view ]**
> **[ INSERT IMAGE: `v-right` — Right side view ]**
> **[ INSERT IMAGE: `v-top` — Top view ]**
> **[ INSERT IMAGE: `v-bottom` — Bottom view ]**

> **[ INSERT IMAGE: `team-official` — Official team photo ]**
> **[ INSERT IMAGE: `team-fun` — Team photo (informal) ]**

---

## 7. Links and Credits

**Component Links**

| Component | Link |
|---|---|
| Raspberry Pi 4 Model B (2 GB) | *[ ADD LINK ]* |
| OV5647 Wide-Angle Camera | *[ ADD LINK ]* |
| SG90 Micro Servo Motor | *[ ADD LINK ]* |
| GA12-N20 Geared Mini DC Motor, 12 V 200 RPM | *[ ADD LINK ]* |
| L9110S Motor Driver | *[ ADD LINK ]* |
| 18650 Cells and Holder | *[ ADD LINK ]* |
| DC-DC Buck Converter | *[ ADD LINK ]* |
| Differential and Gears | *[ ADD LINK ]* |
| STL Files | *[ ADD LINK ]* |

**Main Links**

| | |
|---|---|
| GitHub Repository | https://github.com/jolianjij/Red-Castle-WRO-Future-Engineers-2026 |
| Open Challenge — video | *[ ADD YOUTUBE LINK ]* |
| Obstacle Challenge — video | *[ ADD YOUTUBE LINK ]* |

> **[ INSERT IMAGE: `qr-github` — QR code to the GitHub repository ]**
> **[ INSERT IMAGE: `qr-open` — QR code to the Open Challenge video ]**
> **[ INSERT IMAGE: `qr-obstacle` — QR code to the Obstacle Challenge video ]**

**Credits**

We studied the publicly available work of **Team KyivRoboMagic (Ukraine, WRO 2024)**,
whose camera-only vehicle reached the International Final on hardware comparable to
ours. Their outer-wall control law is the basis of our own steering, adapted and
re-calibrated for our camera and vehicle. Their repository is
<https://github.com/KyivRoboMagic/WRO-2024>.

As a team we thank our coach **Ahmad Kalthom**, and the **HMK AI and Robotics Club**
for hosting and supporting us.

*[ ADD: national organiser thanks, and any friends who helped ]*
