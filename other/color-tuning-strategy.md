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

1. Run `tools/mask_debug.py` (or `line_audit.py`) on the actual field first.
2. If something is missed, check its **V floor** before touching anything else.
3. Re-check the **mat's** S — if the venue floor is shinier, the mat's
   saturation rises and green's 150 gap narrows.
4. Only re-measure hue if a colour is being *confused* with another, not merely
   missed.

**Do not change exposure at the venue** unless nothing else works. It invalidates
every number in this document.

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
