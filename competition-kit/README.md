# Competition kit — WRO 2026 Future Engineers

Team The Red Castle · HMK AI and Robotics Club

Everything needed at the venue, in one folder. The layout **mirrors the Pi**,
so the whole folder can be copied to `~/wro2026` and every tool will find the
programs next to it.

```
competition-kit/
├── open_challenge.py                  the open challenge program
├── obstacle_challenge.py              the obstacle challenge program
├── WRO2026-Control-and-Tunables.pdf   every tunable + the control equations
├── TUNING-STRATEGY.md                 what to do at the venue, in order
├── build_pdf.py                       regenerates the PDF from the code
└── tools/
    ├── mask_debug.py     every mask on one picture       START HERE
    ├── wall_calib.py     wall-following targets
    ├── line_audit.py     line thresholds
    ├── sign_calib.py     pillar distance and pixel counts
    ├── park_calib.py     parking walls and the exit direction
    ├── color_count.py    pixel count for ANY new colour   surprise challenge
    └── servo_jitter.py   proves whether the servo shake is the pulse
```

## Which program is which

**`open_challenge.py`** — wall following on density, lines only count laps.
Finishes 3 s after the 12th quadrant.

**`obstacle_challenge.py`** — the version you asked for: their original green
release and per-direction line counting, the blocking corner kick on orange,
the `v >= 70` parking-wall filter — **with the parking algorithm removed**.
After the 12th quadrant it finishes like the open challenge instead of hunting
for the parking bay. `PARKING_ENABLED = True` brings the whole thing back.

Both keep every value you tuned on the Pi.

## Running

```bash
cd ~/wro2026 && source .venv/bin/activate && python open_challenge.py
```

Press the button to start. Press it again to stop — it is the emergency stop.

Every run writes its own timestamped CSV under `logs/`, so a bad run is never
overwritten by the next one. Both programs print every tunable at startup, so
the log says what produced it.

## The tools

All of them import the challenge program itself, so they use its real capture,
crop, colour tests and wall mask. They cannot quietly disagree with the car —
which is how two genuine bugs were caught.

| tool | run it when |
|---|---|
| `mask_debug.py` | first thing at the venue, and any time something looks wrong |
| `wall_calib.py cw` / `ccw` | before every session — lighting moves the densities |
| `line_audit.py blue` / `orange` | if a lap is miscounted or a line is missed |
| `sign_calib.py` | if a pillar is ignored or hit |
| `park_calib.py` | before an obstacle run, in the start box |
| `color_count.py` | surprise challenge, or any new colour |
| `servo_jitter.py` | if the steering buzzes |

None of them move the car. The motor is never touched.

## Before the first run of the day

1. `systemctl is-active pigpiod` — must say `active`. Without it the servo
   falls back to software PWM and buzzes. The program warns loudly if so.
2. `python tools/mask_debug.py` — look at the picture.
3. `python tools/wall_calib.py cw` and `ccw` — re-measure the targets.

## Regenerating the PDF

Every number in the PDF is parsed out of the two programs at build time, so it
can never drift from the code. After changing a tunable:

```bash
python build_pdf.py
```

Run it on the laptop — it never imports `picamera2`.
