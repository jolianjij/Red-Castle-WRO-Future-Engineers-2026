# Every file, what it is, and when to use it

Two things to know before the list:

**There are two generations of code here.** The `robot.py` library came first;
the two ported programs replaced it. Both are still on disk. A tool built
against `robot.py` reads **different constants** from the ones the car actually
runs on, so its numbers do **not** transfer. Each tool below says which
generation it belongs to.

**Run everything from `~/wro2026` on the Pi**, with the venv active:

```bash
cd ~/wro2026 && source .venv/bin/activate
```

---

# The two programs

These are what drive the car. Nothing else does.

| file | what it is |
|---|---|
| **`open_challenge.py`** | Three laps, no obstacles. Follows one wall at a measured density target, counts quadrants off the lines, stops 3 s after the twelfth. |
| **`obstacle_challenge.py`** | Three laps avoiding red and green pillars. Leaves the parking lot, chooses its lap direction from which side has more magenta, steers around pillars, stops 3 s after the twelfth quadrant. Parking at the end is **deleted**. |

```bash
python open_challenge.py
python obstacle_challenge.py
```

Both wait for the **button on GPIO19** before anything moves, and the same
button is the emergency stop. Both print their whole configuration at startup
and one full line per cycle, and both write `logs/<name>_<timestamp>.csv` — a
new file per run, so a bad run is never overwritten by the next one.

### The old library — still on disk, no longer driving

| file | status |
|---|---|
| `robot.py`, `config.py`, `camera.py` | **LEGACY.** The pre-port library. Its constants are *not* the ones the car runs on. Kept because several tools still import it. |

---

# Tuning tools — the current generation

These import the ported programs and use their **real** crop, camera locks and
masks, so a number measured here means the same thing as a number inside the
program. **These are the ones to use.**

### `wall_calib.py` — the wall-following targets

```bash
python tools/wall_calib.py cw 30      # then flip the car and run ccw
```

Park the car **centred** between the walls. Reports the wall density each side
and tells you what `CW_TARGET` / `CCW_TARGET` should be — because a centred car
should be commanded to steer **zero**, so the target *is* the centred density.

*The check that matters:* a centred car must read left and right within about
0.01 of each other. If they differ by 0.05 the car is not actually centred, and
the target you take from it will lean the car into a wall for the whole run.

### `sign_calib.py` — pillar detection and the steering law

```bash
python tools/sign_calib.py 15
```

Put a **green and a red cube at equal distance** and run it. Reports each one's
area, centre, box and whether it is accepted as a sign, then what the steering
law would command for each.

*The check that matters:* at equal distance the two must report **the same area
and the same y**. Before the green fix they were 10 px against 1222; after,
1279 against 1218.

### `line_audit.py` — why a line's pixel count is what it is

```bash
python tools/line_audit.py blue
python tools/line_audit.py orange
```

For **each bound separately**, counts the pixels that pass every *other* bound
and fail only that one. That is how you find which threshold is wrong instead of
guessing. Also measures what the crop costs, and warns if the threshold sits
inside the frame-to-frame spread — which is what makes a line flicker and get
counted twice.

### `park_calib.py` — the parking walls and the exit direction

```bash
python tools/park_calib.py 15
```

Car in the **start box**, exactly as it will start. Reports purple left vs
right, which direction that chooses, and whether the mask is getting the whole
wall.

*It flags two silent failures:* no purple at all (the comparison is `False`, so
the car quietly commits to CCW) and the two sides being too close (a little
noise then flips your lap direction).

### `hsv_pick.py` — get NEW HSV bounds at the venue

```bash
python tools/hsv_pick.py green
python tools/hsv_pick.py red --wrap
```

The others *check* bounds you have; this one **proposes** new ones from what the
object measures under the venue's light. Prints lines to paste in, then
re-counts with them and reports how much of the rest of the frame they let in.

### `color_count.py` — pixel count for any HSV range

Both a tool and an importable function — this is the one for the **surprise
challenge**.

```bash
python tools/color_count.py 90 135 140 255 20 200 --name blue
```

```python
from color_count import color_count, color_count_halves, color_blob
n = color_count(hsv, h=(35, 85), s=(120, 255), v=(40, 255))
```

`color_count_halves()` gives left/right for side decisions; `color_blob()` gives
shape, because a pixel count cannot tell a solid object from speckle. Hue wrap
is handled for red-like ranges.

### `mask_debug.py` — see every mask at once

```bash
python tools/mask_debug.py
```

Renders the camera view with each colour mask overlaid, so you can *see* what is
matching rather than infer it from counts.

### `servo_jitter.py` — is the steering noise the code or the pulse?

```bash
python tools/servo_jitter.py
```

Front wheels hanging free. Holds **one constant angle** three ways —
`RPi.GPIO` held, `RPi.GPIO` released, `pigpio` DMA-timed — six seconds each. The
command never changes inside a phase, so anything that moves is not the control
loop. This is what proved the buzzing was software PWM.

---

# Tests — no car needed

Run these on the laptop after any edit.

| file | what it proves |
|---|---|
| **`test_obstacle_run.py`** | Actually **runs** `cycle()` across seventeen states — both directions, each cube, each line, the parking wall, quadrants 11/12/13, a live kick and an expired one — and checks the run really stops 3 s after the twelfth quadrant. Catches what a compile check cannot. |
| **`test_pillars.py`** | Nine checks on the pillar recorder and the sign decay: one pillar gives one entry, a different colour interrupts, a short dropout does not re-arm, the decay flips once and settles. |
| `test_logic.py` | **LEGACY.** Tests `robot.py`, the corner kick, the button and the steering limits. Stops cleanly at the pre-port boundary and says so. |

---

# Workflow scripts

| file | use |
|---|---|
| **`sync.sh`** | `./sync.sh push` copies the laptop's code to the Pi. **It overwrites what is on the Pi** — check first if you have tuned there. |
| **`backup.sh`** | `./backup.sh save` pulls a full snapshot from the Pi into `backups/`. Run before changing anything. |
| `src/run.sh` | What autostart runs. The `PROGRAM=` line picks which challenge. |
| `src/autostart.sh` | `on` / `off` / `status`. Installs the systemd unit that runs the car at boot. It waits for `pigpiod`, because without it the servo silently falls back to software PWM and buzzes. |
| `src/tools/venue_net.sh` | `status` / `wifi-off` / `wifi-on` on the Pi. `wifi-off` refuses unless the laptop has actually taken an address and answers a ping. |

---

# Documents

| file | what it answers |
|---|---|
| **`color-tuning-strategy.md`** | Every colour, one at a time — what it decides, its measured H/S/V, what breaks it, and the command to check it. Plus the venue procedure and the collision map. **Read this before touching any threshold.** |
| **`file-guide.md`** | This file. |
| **`moving-files-scp.md`** | Copying files both ways with `scp`, and the gotchas that have actually bitten us. |
| `new-laptop-setup.md` | Setting up a second laptop on the Pi's Ethernet cable. |
| `venue-setup.md` | Wired networking, radios off, and recalibrating for the venue's light. |
| `ssh-commands.md` | The commands used most often, ready to paste. |
| `tuning-strategy.md` | The older, driving-focused strategy: what to do at the venue in order, and what to change when it hits walls or mishandles signs. |
| `rules-and-mission.md`, `wro-requirements-compliance.md`, `bill-of-materials.md` | The competition rules, how this robot meets them, and the parts list. |
| `start-here.html` and the other HTML | Generated reference pages — open in a browser. |

---

# Older tools, kept but superseded

All of these were written against **`robot.py`**, so their numbers do not match
what the car now runs. Use the current-generation equivalent instead.

| old tool | use instead |
|---|---|
| `tune_colors.py`, `color_tuner.py` | `hsv_pick.py`, `color_count.py` |
| `tune_walls.py` | `wall_calib.py` |
| `line_check.py`, `line_calib.py` | `line_audit.py` |
| `park_check.py` | `park_calib.py` |
| `shadow_check.py` | `wall_calib.py` (it shows the shadow mask directly) |
| `symmetry_check.py`, `outer_test.py`, `dryrun.py` | `test_obstacle_run.py` |
| `video_colors.py` | `hsv_pick.py` on the real field |

Small standalone hardware checks, still fine to use:

| tool | use |
|---|---|
| `servo_center.py` | find the steering trim |
| `motor_debug.py`, `motor_speed_steps.py` | motor direction and speed |
| `button_test.py` | prove the button reads |
| `preview.py`, `cam_capture.py`, `mjpeg_stream.py` | look through the camera |
| `driver_on.py` | power the motor driver |

---

# The order to use them in at the venue

1. `backup.sh save` — before touching anything.
2. `wall_calib.py cw` and `ccw` — if the densities are near 0.215 a side, the light has not moved and you may need nothing else.
3. `line_audit.py blue` and `orange` — the lines, if a lap is miscounted.
4. `sign_calib.py` — the cubes, if a pillar is mishandled.
5. `park_calib.py` — the start box, before the first obstacle run.
6. `hsv_pick.py <colour>` — only if something is genuinely **missed**, and check its brightness floor first.
7. `test_obstacle_run.py` on the laptop after any edit.
