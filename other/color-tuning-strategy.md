# Colour tuning strategy

Everything here was **measured on this car**, on this field, with these two
programs. Numbers without a measurement behind them are marked as such.

---

## The single most important fact

> **Every colour failure on this car has been a BRIGHTNESS FLOOR, not a hue.**

Five separate times. Each one was a `V >` floor inherited from a camera brighter
than ours, and each one silently discarded most or all of the object:

| object | their floor | its real V on our camera | what happened |
|---|---|---|---|
| blue line | `V > 70` | p50 **43**, p95 79 | most of the line rejected |
| orange line | `V > 125` | p50 **78**, p95 106 | orange could **never** fire |
| green cube | `V > 60` | p50 **38**, p99 61 | kept **16 of 1107 px — 1%** |
| purple parking wall | `v >= 70` | p50 **67**, p05 52 | over half the wall discarded |
| wall detector | `v < 70` alone | — | counted shadow as wall |

Our whole frame tops out around **V = 137–143**. Any inherited threshold above
about 60 is suspect on this camera. **When a colour is not detected, check its
brightness floor first.**

---

## What every colour actually measures here

Measured with `tools/line_audit.py`, `tools/sign_calib.py`, `tools/park_calib.py`.

| object | hue | saturation | value | separated from the mat by |
|---|---|---|---|---|
| **mat** (the adversary) | **70–79** | p50 93, p99 146 | p50 135 | — |
| blue line | 90–135 | p50 228 | p50 43 | saturation |
| orange line | 0–30 | p50 167 | p50 79 | hue |
| red cube | 0–7 | p50 216 | p50 72 | hue |
| green cube | **p50 71** | p50 247, p01 157 | p50 38 | **saturation only** |
| purple wall | 163–179 | p50 198 | p50 67 | hue |
| black wall | — | low | < 32, or < 62 desaturated | brightness |

### The two facts that explain most of the difficulty

**1. The mat sits in the green hue band.** Mat H70–79, green cube H p50 **71**.
They are the *same hue*. Hue cannot separate green from the floor — only
saturation can, and the gap is narrow: mat p99 **146** against cube p01 **157**.
That is why `GREEN_SAT_MIN = 150` and why lowering it re-admits the mat. If you
ever drop green's V floor further, you **must** keep S high.

**2. Orange and red share a hue band.** Red measures H0–7; the orange line band
is H0–30. A red pillar can pad the orange count. This is why orange is the
unreliable line and blue is the trustworthy one.

---

## The order to tune in, and why

### 0. Lock the exposure before anything else

Auto-exposure and auto-white-balance move **every threshold below** while the
car drives. They are already locked:

```
AeEnable False, ExposureTime 12000, AnalogueGain 8.0
AwbEnable False, ColourGains (1.329, 1.446)
```

If you change exposure at the venue, **every colour must be re-measured.** Treat
that as a last resort, not a first move.

### 1. Hue — widest bound, least often wrong

Hue is the most stable property under changing light. Set it generously and
leave it. In five failures, hue was the culprit **zero** times.

Only two hue edges here are delicate, and both are collisions rather than
lighting:

- **red's wrap vs the purple wall.** Red matches `h < 15 or h > RED_HUE_HI`. The
  parking wall reaches **H179**. With `RED_HUE_HI = 175`, red claims **4558 px
  of the wall** — measured. Raising it to 178+ is the fix if red ever "sees a
  sign" that is really the parking wall.
- **green's floor vs nothing.** Green's band is wide and safe; its problem is
  never hue.

### 2. Saturation — this is what excludes the mat

Saturation is the bound doing the real work of keeping the floor out.

- **blue**: `S > 140`. Measured, **9556 px** pass every other bound and fail only
  this one — that is the mat, whose hue drifts into blue's range. Lowering this
  re-creates a bug we already fixed once.
- **green**: `S > 150`. At 120 the mat leaks 61 px; at 150 it leaks **zero**
  while keeping 1088 of 1107 cube pixels.
- **orange**: `S > 70` is loose, and it can afford to be — hue already separates
  orange from the mat (H13 vs H70).

### 3. Brightness — last, and LOW

This is the one that has broken every time. Set it just low enough to keep the
object, no lower.

The method: isolate the object by hue+saturation alone, then look at how many of
**its own pixels** each candidate floor would keep. For the green cube:

```
V > 10  keeps 1097 of 1107  (99%)
V > 25  keeps 1088          (98%)     <- chosen
V > 30  keeps 1033          (93%)
V > 40  keeps  334          (30%)
V > 60  keeps   16          ( 1%)     <- was here
```

The cliff between 30 and 40 is the cube's actual brightness distribution. Sit
clearly below the cliff.

---

## The diagnostic that replaces guessing

Do not tune by changing a number and re-running. For each bound, count the
pixels that pass **every other bound** and fail **only that one** — the marginal
cost of that bound. `tools/line_audit.py` prints exactly this:

```
pixels that pass every OTHER bound and fail only this one:
    hue >  90      rejects    580 px
    hue <  135     rejects      0 px      <- doing nothing, could be removed
    sat >  140     rejects   9556 px      <- this is the MAT, leave it alone
    val >  20      rejects     76 px
    val <  200     rejects      0 px      <- doing nothing
```

Read it as: a bound rejecting thousands is either doing essential work (the mat)
or destroying your object — look at *what* it is rejecting before deciding. A
bound rejecting zero is doing nothing at all.

---

## Two rules that prevent the classic mistakes

### Never tune from a single number

A count of 1200 px means nothing on its own. Measure the **object** and the
**background** in the same frame. Blue reads 1036 on the line and **3–9 on bare
mat** — that ratio is what makes the threshold safe, not the 1036.

### Thresholds belong to a CROP, not just a camera

`CROP_TOP` changes every pixel count. Ours is 160 where theirs was 240, which
squashes 320 rows into 120 instead of 240 into 120 — so the same physical line
lands on **76%** as many pixels (measured; geometry predicts 75%).

That is why their 1100/1300 became **830/930** here. **If you ever change
`CROP_TOP`, every pixel-count threshold must be re-measured.** Areas too: a
pillar keeps about 75% of its area, which is why the sign area gates were
rescaled.

---

## At the venue

Venue light changes **V** most, **S** second, **H** least. So:

1. Run `tools/line_audit.py`, `tools/sign_calib.py` and `tools/park_calib.py`
   on the actual field first.
2. If something is missed, check its **V floor** before touching anything else.
3. Re-check the **mat's** S — if the venue floor is shinier, the mat's
   saturation rises and green's 150 gap narrows.
4. Only re-measure hue if a colour is being *confused* with another, not merely
   missed.

**Do not change exposure at the venue** unless nothing else works. It invalidates
every number in this document.

---

## Setting NEW HSV at the venue — the actual procedure

The other tools *check* bounds you already have. `hsv_pick.py` *proposes* new
ones from whatever the object measures under the venue's light.

**For each colour that needs redoing:**

```bash
python tools/hsv_pick.py green
python tools/hsv_pick.py orange
python tools/hsv_pick.py red --wrap      # red's hue wraps past 0
```

Park so the object **fills as much of the view as you can**, with nothing else
coloured in frame. The tool finds the most saturated large blob, measures its
H/S/V over several frames, and prints lines you can paste straight in.

It then re-counts with those bounds and reports two numbers:

```
of the object     : 1088 of 1107 px kept   (98%)
of everything else: 0 px let in
```

**The second number is the one that matters.** Bounds that catch the object are
easy; bounds that catch the object *and not the mat* are the job.

**Then check the other direction** — this is the step people skip:

```bash
# move the object OUT of view, then:
python tools/color_count.py <the six numbers it gave you>
```

A threshold is only safe when you know **both** readings. Blue reads 1036 on the
line and 3–9 on bare mat; that *ratio* is what makes 830 safe, not the 1036.

### The order to do them in at the venue

1. **Nothing at first.** Run `wall_calib.py cw` — if the wall densities are
   close to 0.215 a side, the light has not moved much and you may need nothing.
2. **Whichever colour is missed**, in this order of likelihood: green (darkest),
   orange, blue, purple. Red has never needed it.
3. **Re-check the mat** with `color_count.py 45 90 0 255 0 255` — if the venue
   floor is shinier its saturation rises, and green's 150 gap narrows.
4. **Re-measure the line thresholds** with `line_audit.py` after any blue or
   orange change — the HSV bounds and the pixel thresholds are not independent.

### What NOT to do

Do not change exposure. Every number in this document is measured at
`ExposureTime 12000, AnalogueGain 8.0` with AWB locked. Changing it invalidates
all of them at once, and you will not have time to redo everything.

---

## Adding a new colour (surprise challenge)

Use `tools/color_count.py`. It gives a pixel count for any HSV range through the
same pipeline the car uses, so a number you measure with it means the same thing
as a number in the programs:

```python
from color_count import color_count
n = color_count(hsv, h=(35, 85), s=(120, 255), v=(40, 255))
```

Tune it in the order above — hue wide, saturation to exclude the mat, brightness
last and low — and always measure the background in the same frame.

---
---

# Every colour, one at a time

Six masks matter on this car. For each: what it decides, where its numbers live,
what it actually measures here, what breaks it, and how to check it.

---

## 1. BLUE — the counted line

**Decides:** the quadrant count, and in the open challenge the lap direction.
This is the line to trust.

| | |
|---|---|
| constants | `BLUE_HUE_MIN/MAX = 90, 135`, `BLUE_SAT_MIN = 140`, `BLUE_VAL_MIN/MAX = 20, 200` |
| threshold | `blue_line_threshould = 830` |
| measured on the line | H 90–107, S p50 **228**, V p50 **43** |
| measured on bare mat | **3–9 px** |
| on the line, static | 1017–1048 px |
| driving over it | peaks **1883–3624** |

**What breaks it:** the brightness floor. Their `V > 70` against a real V of 43
cut most of the line away.

**What must not move:** `BLUE_SAT_MIN = 140`. Measured, **9556 px** pass every
other bound and fail only this one — that is the **mat**, whose hue drifts into
blue's range. Saturation is the only thing keeping the floor out of the blue
count. Lowering it re-creates a bug already fixed once.

**The hue floor costs 580 real line pixels** (the blurred edges, where averaging
pulls the hue down) and could be lowered to about 88 — but green pillars measure
H81–86 and the obstacle program shares this range, so it stays at 90.

**Check it:**

```bash
python tools/line_audit.py blue
```

It fires with about 1.2x margin on the worst frame, and the tool warns if the
threshold sits inside the frame-to-frame spread — which is what made it flicker
before.

---

## 2. ORANGE — the other line

**Decides:** the lap direction in the open challenge, and the corner kick in the
obstacle one. **Less reliable than blue, structurally.**

| | |
|---|---|
| constants | `ORANGE_HUE_MIN/MAX = 0, 30`, `ORANGE_SAT_MIN = 70`, `ORANGE_VAL_MIN/MAX = 30, 240` |
| threshold | `orange_line_threshould = 930` |
| measured on the line | H 5–26, S p50 **167**, V p50 **79** |
| measured on bare mat | 0–87 px |
| on the line, static | 1107–1196 px |

**What breaks it:** brightness again. Their `V > 125` against a real V of 78
meant orange could **never** fire — the direction fell through to blue every
time, and a clockwise run then followed the inner wall.

**Its structural problem: red lives in its hue band.** Red measures H0–7; the
orange band is H0–30. A red pillar pads the orange count. Measured in a CCW run,
orange reached **845** against its 930 threshold from pillars alone — 9%
headroom. This is why the obstacle program can be set to count blue only.

**Its saturation floor is loose (70) and can afford to be** — hue already
separates orange from the mat (H13 vs H70). Do not tighten it to fix red; that
is a hue collision, not a saturation one.

**Check it:**

```bash
python tools/line_audit.py orange
```

---

## 3. RED — the pillar you pass on the RIGHT

**Decides:** steer right, and `last_detected_traffic_light`.

| | |
|---|---|
| constants | `RED_HUE_LO/HI = 15, 175` — matches `h < 15` **or** `h > 175` |
| | `RED_SAT_MIN = 120`, `RED_VAL_MIN/MAX = 60, 240` |
| measured on the cube | H **0–7**, S p50 **216**, V p50 **72** |
| area at calibration distance | **1218 px**, box 36 × 44 |

**Red works.** It is the one colour that has never needed a brightness fix — its
V of 72 clears the 60 floor.

**Its one real hazard: the magenta parking wall.** The wall measures up to
**H179**, and red matches everything above `RED_HUE_HI = 175`. Measured with the
car in the start box, **red claims 4558 px of the parking wall** — wall being
reported as a sign.

Since red's own hue is only H0–7, the upper arm of that wrap does nothing for red
and everything for the false positive. **Raise `RED_HUE_HI` to 178–179** if red
ever "sees a sign" that is really the parking wall.

**Check it:** park facing a red cube and run

```bash
python tools/sign_calib.py
```

---

## 4. GREEN — the pillar you pass on the LEFT

**Decides:** steer left. The hardest colour on this field, for two reasons.

| | |
|---|---|
| constants | `GREEN_HUE_MIN/MAX = 45, 90`, `GREEN_SAT_MIN = 150`, `GREEN_VAL_MIN/MAX = 25, 240` |
| measured on the cube | H **p50 71**, S p50 **247** (p01 157), V p50 **38** (p99 61) |
| area at calibration distance | **1279 px**, box 38 × 46 |

**Reason one — it is dark.** V p50 38 against their `V > 60` floor kept
**16 pixels of 1107**. One percent. Green never reached the minimum area, so no
green target was ever built and the sign law never saw one. Every "it does not
avoid the green pillar" report traced back to here.

```
V > 10  keeps 99%       V > 30  keeps 93%
V > 25  keeps 98%  <--  V > 40  keeps 30%
                        V > 60  keeps  1%   <-- was here
```

**Reason two — the mat is the same hue.** Mat H70–79, cube H p50 **71**. Hue
cannot separate them at all. Only saturation can, and the gap is narrow:

| S floor | cube kept | mat leaked |
|---|---|---|
| 100 | 1088 | 335 |
| 120 | 1088 | 61 |
| **150** | **1088** | **0** |

So **if you ever lower green's V floor further, you must keep S at 150 or
above.** Dropping both at once puts the floor into the green mask, and the car
steers for a patch of mat.

**Check it:** put a green and a red cube at equal distance and run

```bash
python tools/sign_calib.py
```

The check that matters is not the absolute number — it is that green and red
report the **same area and the same y** at equal distance. Before the fix they
were 10 vs 1222; after, 1279 vs 1218, a ratio of 1.05.

---

## 5. MAGENTA / PURPLE — the parking walls

**Decides:** which way to leave the parking lot, and therefore the whole lap
direction. Also an obstacle to avoid during the laps.

| | |
|---|---|
| constants | `PURPLE_HUE_MIN/MAX = 135, 175`, `PURPLE_SAT_MIN = 120`, `PURPLE_VAL_MIN/MAX = 60, 240` |
| measured on the wall | H **163–179** (p50 174), S p50 **198**, V p50 **67** (p05 52) |
| in the start box | left 5065 px, right 5952 px |

**Two bounds are cutting the wall:**

1. **`V > 60` against a wall at V p50 67, p05 52.** Measured, that keeps only
   **77%** of it; `V > 30` keeps 99%.
2. **`H <= 175` against a wall reaching H179.** Measured, that bound alone
   rejects **4558 px** — and those are the very pixels red then claims.

**How the direction is decided, and how it fails:**

```python
if purple_left > purple_right:  direction = CW     # way out is RIGHT
else:                           direction = CCW    # way out is LEFT
```

With **no purple in view at all** the comparison is `False`, so the car silently
commits to CCW. It looks like a decision and is really a fall-through. The
program now warns loudly when the total is under 200 px.

The second failure mode is the two sides being **too close**: measured 5065 vs
5952 is a ratio of only **1.17**, and a little noise flips the lap direction.
Park so one side clearly wins.

**Check it:** put the car in the start box exactly as it will start, and run

```bash
python tools/park_calib.py
```

---

## 6. BLACK — the walls

Not a colour mask. The wall detector uses brightness and saturation together
plus a **geometric** test, and none of it goes through `colors.json`.

| | |
|---|---|
| constants | `WALL_V_HARD = 32`, `WALL_V_SOFT = 62`, `WALL_S_MAX = 90` |
| | `WALL_OPEN_K = 3`, `WALL_MIN_RUN = 6` |
| centred density | **0.215** per side |

```
wall = (V < 32)  or  (V < 62 and S < 90)
```

**Why two cases and not one threshold:** HSV saturation is unreliable when V is
tiny — a black wall can report S>200 from pure sensor noise. Testing saturation
alone therefore **rejects real walls**, and testing brightness alone **accepts
the coloured lines**. Hence: very dark is wall whatever S says; dark *and*
desaturated is wall; dark but saturated is a line, not wall.

**The shadow test is geometric, not colour.** A real wall is a **tall solid
vertical run**; a shadow is a broad shallow smear. Any dark region without a run
of `WALL_MIN_RUN = 6` rows is discarded. On the field this removed the mat's
printed dots — 327 px, sitting on the left, which had been inflating
`left_wall` specifically.

- Shadow still getting through → **raise** `WALL_MIN_RUN`
- Distant walls dropping out of the reading → **lower** it

**Check it:**

```bash
python tools/wall_calib.py cw      # then flip the car, and ccw
```

The check that matters: a **centred** car must read left and right within about
0.01 of each other. When CW read 0.2415 / 0.1825 — a gap of 0.059 — that was not
a camera asymmetry, it was the car not actually being centred, and it produced a
target telling the car to hold 13% closer to one wall for the whole run.

---

# The collision map

Two pairs share hue space. Neither can be fixed with saturation or brightness —
only by moving a hue edge, or by not relying on the weaker one.

```
  H0        H7   H15                H30
  |---------|     |------------------|
  RED cube        ORANGE line band            red pads the orange count

                       H70  H79   H90
                       |-----|
                       MAT          green band starts at H45
                       green cube sits at H71, INSIDE the mat

       H163                      H175  H179
       |--------------------------|-----|
       PURPLE wall                      red's wrap starts at 175,
                                        so red claims H176-179 of the wall
```

| collision | why saturation cannot fix it | what to do |
|---|---|---|
| red vs orange line | red is genuinely inside the orange hue band | count **blue** instead — it has no twin on this field |
| green vs mat | identical hue, H71 both | saturation is the *only* separator; keep `GREEN_SAT_MIN` at 150 |
| red vs purple wall | red's wrap overlaps the wall's top hue | raise `RED_HUE_HI` past H179 |

---

# One-page tuning order

1. **Lock the exposure.** Changing it invalidates every number in this document.
2. **Hue** — set wide, and touch it only to fix a *collision*, never a *miss*.
3. **Saturation** — the bound that excludes the mat. Blue 140, green 150.
4. **Brightness — last, and low.** Five failures out of five were here.
5. **Measure the object AND the background in the same frame.** A count without
   its background is not a threshold.
6. **Re-measure everything if `CROP_TOP` changes.** Pixel counts and areas both
   scale with the crop — ours keeps 76% of what theirs did.
