# Tuning strategy — WRO 2026 Future Engineers

Team The Red Castle · HMK AI and Robotics Club

This is the field procedure. The PDF next to it has every tunable and the
control equations; this one is about **what to do, in what order, and how to
tell whether it worked**.

---

## The one idea behind all of it

The car has **no distance sensor**. Everything it knows comes from counting
pixels in one 320×120 image. So every number in both programs is really an
answer to *"how many pixels?"* — and a pixel count only means something on the
camera, the crop and the lighting it was measured on.

That is why the same class of bug has bitten this car five separate times:

| what happened | what it looked like |
|---|---|
| orange needed `V>125`, the line reads 78 | direction never locked CW |
| blue needed `V>70`, the line reads 43 | direction fell through to whatever fired |
| green needed `V>60`, the cube reads 38 | car ignored green pillars completely |
| line thresholds measured on a 2× crop, ours is 2.67× | both lines silently too high |
| neutral wall target 0.5, densities reach 0.25 | car drove straight out of the start into a wall |

**None of these looked like bugs.** A controller commanding zero looks exactly
like a controller that is happy. That is why the order below starts with
*looking at the image* and ends with *reading the log* — never with guessing.

---

## Order of work

Do these in order. Each step assumes the ones above are already right;
out of order, you are measuring through a mistake.

### 1 — Look at the image first

```bash
python tools/mask_debug.py
```

One picture, every mask the car uses: the camera view, the wall mask, blue,
orange, red, green, purple, each with its pixel count and percentage.

**Before any number, answer these by eye:**

- Are the walls solid in the WALL panel, or speckled and broken?
- Are the lines solid bands, or dotted and thin?
- Is the mat leaking into any coloured panel?

Venue lighting is the single biggest change between practice and competition.
If this picture looks wrong, nothing measured afterwards means anything.

### 2 — Walls, both directions

```bash
python tools/wall_calib.py cw       # park CENTRED, facing clockwise
python tools/wall_calib.py ccw      # flip it, same spot
```

**Centred is the whole point.** The target is the density a centred car reads,
so that a centred car is commanded to steer *zero*.

Two checks that catch a bad placement:

- The tool's own two halves should agree within about **0.01**. If left and
  right differ by 0.06, the car was not centred — the reading is of a car
  leaning on one wall, and putting it in the file bakes that lean into the run.
- CW and CCW should give **nearly the same number**, because both follow the
  outer wall. If they differ a lot, one placement was wrong.

A target wrong by 0.03 commands about 2° of steering while the car is already
centred — a constant lean, every cycle, all run.

### 3 — Lines

```bash
python tools/line_audit.py blue
python tools/line_audit.py orange
```

Park so the line fills the view. Set the threshold to roughly **77% of a full
line** — that is the ratio the original code used, and it leaves room for a
crossing seen at an angle.

Two things the tool tells you that a single reading cannot:

- **The frame-to-frame spread.** If the threshold sits *inside* it, the same
  crossing flickers on and off and gets counted twice.
- **Which bound is costing you pixels.** It reports, for each bound, how many
  pixels pass every *other* bound and fail only that one. A bound rejecting
  thousands is the one to move; a bound rejecting zero is doing nothing.

**Do not lower the blue saturation floor.** The mat's hue sits inside the blue
range — saturation is the only thing keeping it out.

### 4 — Pillars

```bash
python tools/sign_calib.py
```

Put a **green and a red cube side by side at equal distance** and run it.

The check that matters: **they should give equal area and equal `y`.** If one
is much smaller, that colour's range is clipping the cube, and no amount of
`kp` tuning will fix it — fix the colour first.

Green is the harder one, and always will be on this camera:

- the mat sits at **H70–79**; the green cube sits at **H≈71**. Same hue.
  Only saturation separates them.
- green is darker: **V≈38** against red's **≈72**.
- green demands the bigger manoeuvre — it must be passed on the left, so the
  aim runs far off frame.

### 5 — Parking walls (obstacle start only)

```bash
python tools/park_calib.py
```

Put the car in the start box exactly as it will start. The exit direction is
decided by `purple_left > purple_right`, so:

- **No purple at all** → that comparison is false → the car silently commits
  to CCW. The tool says so loudly.
- **Two sides nearly equal** → a few pixels of noise flips your lap direction.
  Move the car until one side clearly wins.

### 6 — Drive, then read the log

Every run writes its own timestamped file in `logs/`. Nothing is overwritten.

```bash
cd ~/wro2026 && source .venv/bin/activate && python open_challenge.py
```

**Tune from the log, not from memory of what the car looked like.** The log has
both wall densities, both pixel counts and their states, the target's x/y/area,
the traffic-light state, and the steering both before and after the clamp.

What to look for:

| symptom | look at | likely cause |
|---|---|---|
| leans into one wall all run | `dir_raw` on straights | target wrong — re-do step 2 |
| runs wide at corners | a run of `CLAMP` lines | `STEER_MAX` too low |
| stops early | `quadrant` jumps by 2 | phantom line — threshold too low, or orange catching red |
| ignores a pillar | `target_area`, `target_type` | min area too high, or the colour is clipping |
| swerves at nothing | `Err` large while area small | reacting to a distant sign |
| weaves on a straight | `dir_servo` reversals | gain too high, or smoothing too low |

---

## The surprise challenge

`tools/color_count.py` is written for this. Point the car at whatever the new
task involves and find its numbers:

```bash
python tools/color_count.py 90 135 --smin 140      # hue range, saturation floor
python tools/color_count.py 174 8  --smin 120      # a range that WRAPS (red)
python tools/color_count.py 40 80  --live          # keep printing while you move it
```

It prints the count, the left/right split, the biggest blob and its shape, and
the **H/S/V percentiles inside that blob** — which is what you set the
thresholds from. Set the floors just outside p05/p95, never at p50.

Then in the program you write on the day:

```python
from color_count import grab, color_count, halves, biggest_blob

frame, hsv = grab(cam)
n, mask = color_count(hsv, hue=(90, 135), s_min=140, v=(20, 200))
if n > 800:
    left, right = halves(mask)
```

It works on the same 320×120 frame as both challenge programs, so a threshold
measured with the tool drops straight in without rescaling.

---

## Rules of thumb, in priority order

1. **Slow the car down before tuning anything.** Every threshold is easier to
   hit at low speed, and `speed` is one line.
2. **If something is not detected, check the V floor first.** Three separate
   colours on this car were rejected by a brightness floor set on a brighter
   camera.
3. **Never change a threshold and the crop in the same session.** `CROP_TOP`
   invalidates *both* the wall targets and the line thresholds.
4. **Change one number, do one run, read the log.** Two changes at once and you
   learn nothing from the result.
5. **Saturation separates colour from mat; brightness separates object from
   shadow.** When a mask leaks, ask which of those two jobs is failing.
6. **Write down what you changed.** Both programs print every tunable at
   startup, so the run's own log says what produced it — keep the logs.

---

## If everything goes wrong at the venue

- `git log --oneline` on the laptop — every version is committed, and the
  commit messages say what was measured and why.
- `backups/` holds snapshots pulled from the Pi.
- Both programs fall back safely: if `pigpiod` is not running the servo still
  works (it just buzzes), and both say so loudly at startup rather than
  failing silently.
- The startup banner prints every tunable. If the car behaves unexpectedly,
  **read the banner first** — it is faster than reading the file.
