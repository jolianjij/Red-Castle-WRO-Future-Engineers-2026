# Tuning strategy — what to do at the venue, in order

The venue's light is different, and **almost every number in this car is a
measurement taken through that light.** This is the order to redo them in.
Each step is measured *through* the ones before it, so doing them out of order
silently invalidates the earlier work.

Budget about **40 minutes** for a full pass.

---

## The one rule

> **Change one number. Run. Read the log. Repeat.**

Changing two things and running once tells you nothing about either. Every run
writes a CSV to `logs/`, and that log is the only honest account of what
happened — not what you saw from the side of the track.

---

## Step 0 — before you touch anything (2 min)

```bash
cd ~/wro2026 && source .venv/bin/activate
python tools/test_logic.py     # must say ALL TESTS PASSED
./tools/venue_net.sh status    # can you still reach the Pi?
```

If the tests fail, fix that first. Everything below assumes the logic is sound
and only the *numbers* are wrong.

---

## Step 1 — camera, then colours (15 min)

```bash
python tools/tune_colors.py
```

Headless, so a plain SSH terminal is enough. It re-locks exposure and white
balance to the room **first**, then walks each colour.

**Why the order cannot be swapped:** every colour is measured *through* the
white balance. Re-locking it afterwards throws away every colour you just
tuned.

Then prove it:

```bash
python tools/tune_colors.py --check
```

**What you are looking for:** zero overlap between every pair. A range that is
right on its own is still wrong if it also matches the pillar beside it. This
check is what caught red swallowing the magenta parking wall.

---

## Step 2 — what counts as a wall (5 min)

```bash
python tools/tune_walls.py --detector
```

**This is the step everyone forgets.** The wall detector does **not** use a
colour range — it uses three brightness/saturation cuts. Tuning the colours
does *not* retune the walls. If it says wall and mat overlap in brightness, the
room is too dim and no threshold can work; add light.

---

## Step 3 — centimetres to density (10 min)

```bash
python tools/tune_walls.py
```

The car never measures distance. It measures **density** — how much of the
picture a wall fills. This parks it at known distances, fits a line, and prints
the constants to paste in.

Measure from the **side of the car**, at camera height, **parallel** to the
wall. Parallel matters more than exact: at an angle the camera sees a wedge and
reads high.

**Re-run this after Step 2** — changing the detector changes every density.

---

## Step 4 — the corner lines (5 min)

```bash
python tools/line_check.py
```

Point the car at a real corner line, then at bare mat.

**What you are looking for:** on the line, ONE wide shallow blob. On bare mat,
nothing. Scattered blobs or a tall blob mean the colour is matching something
else — and no threshold fixes that, so go back to `tune_colors.py`.

This matters more than it looks. **The first line the car crosses decides which
way round the track it drives**, and a wrong direction ruins the entire run.

Measured on this car: blue was triggering on **39–54 % of frames** — it was
matching the mat's near-field colour cast, not the line. Raising blue's bar from
0.035 to 0.100 put it in the gap between the noise (peaks ≤ 0.084) and real
crossings (peaks ≥ 0.114).

---

## Step 5 — the parking lot, if you use it (3 min)

```bash
python tools/park_check.py
```

Put the car where it will actually start.

**What you are looking for:** a margin of **1.5× or better**. Below that it is
close to a coin toss — turn the car so one magenta wall clearly fills more of
one half. If it picks the wrong way out, flip `PARK_INVERT`.

---

## Step 6 — prove it without driving (2 min)

```bash
python tools/dryrun.py
```

Both challenges against the live camera, motor never touched. Nothing here
should surprise you before you let the car move.

---

# Tuning the driving itself

Only after the perception above is right. **A control problem you can see is
usually a perception problem you cannot.**

## If it hits walls

| symptom in the log | change |
|---|---|
| many frames past `WALL_EMERGENCY` | lower `SIGN_WALL_GUARD` (0.7 → 0.5) so signs stop pulling it in |
| it hugs the outer wall | raise `LANE_DISTANCE_CM` |
| it wanders in the middle | raise `OUTER_KP` |
| it weaves / oscillates | lower `OUTER_KP`, or raise `OUTER_DEADBAND` |

## If it mishandles signs

| symptom | change |
|---|---|
| chases distant specks | raise `GREEN_MIN_AREA` / `RED_MIN_AREA` |
| notices signs too late | lower them |
| calls a line or floor patch a sign | raise `*_MIN_ASPECT` toward 1.5 |
| passes too close | move `*_TARGET_X` further from 160 |
| swings too hard | lower `*_KP` |
| abandons a pass halfway | raise `SIGN_HOLD_S` |
| drives straight too long after one | lower `SIGN_STEER_HOLD_S` |

**Green and red are tuned separately** and genuinely need it: on one run green
was detected at a median area of **186 px** and red at **718**.

## If corners go wrong

| symptom | change |
|---|---|
| turns the wrong way at every corner | the DIRECTION is wrong — Step 4 |
| cuts corners | raise `KICK_ANGLE` or `KICK_TIME_S` |
| swings too wide | lower them |
| stops in the wrong place | `STOP_EXTRA_S` |

---

## Reading a log fast

```bash
ls -t logs/*.csv | head -1        # the newest run
```

Three columns tell you most of it:

- **`dir`** — does it change, or lock at `t=0.000`? Locking instantly means it
  decided from a line merely *in view* at the start.
- **`mode`** — if `wall` is more than ~15 % of frames, the car is fighting the
  track, not driving it.
- **`quad`** — should reach 12 and no more. Higher means the line logic is
  counting things that are not corners.

---

## What NOT to do at the venue

- **Do not** change the control gains before the colours are right.
- **Do not** change two numbers between runs.
- **Do not** tune from what you saw. Tune from the log.
- **Do not** turn Wi-Fi off until `venue_net.sh status` says the laptop is
  ANSWERING. Carrier alone is not proof, and getting this wrong locks you out
  of the robot entirely.

---

# Backups — before you change anything

```bash
./backup.sh save "worked at the venue"    # snapshot the Pi as it is NOW
./backup.sh list                          # what you have
./backup.sh restore <name>                # put one back on the Pi
./backup.sh undo                          # undo the last push or restore
```

A snapshot is the five code files **plus every calibration file** — the numbers
that took hours to measure and cannot be re-derived from anything else. Each one
is stored in three places: here on the laptop, as a git tag, and on GitHub.

**`./sync.sh push` snapshots the Pi automatically before overwriting it**, so a
bad push is always one `./backup.sh undo` away.

**Take a snapshot the moment a run goes well.** That is the whole point — you
cannot get back to a configuration you never recorded, and "it was working an
hour ago" is not a state you can restore.

After any restore, prove it before driving:

```bash
ssh pi@raspberrypi 'cd wro2026 && source .venv/bin/activate && python tools/test_logic.py'
```

## The one backup this does not cover

If the **SD card itself** dies or corrupts, none of the above helps — the
operating system, the Python environment and the camera drivers are all on it.
Image the card from another machine while things are working:

- **Raspberry Pi Imager** → *Utilities* → read the card to a `.img` file, or
- Windows: **Win32DiskImager** → *Read*

Do this once, now, and keep the image somewhere other than this laptop. It is
the difference between a twenty-minute swap and losing the competition.
