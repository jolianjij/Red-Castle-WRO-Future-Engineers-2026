# Reference source — Team KyivRoboMagic (Ukraine), WRO 2024

From <https://github.com/KyivRoboMagic/WRO-2024>. Kept here so our scaling
arithmetic can be checked against the real code rather than a summary.

They reached the WRO 2024 International Final on camera-only hardware
comparable to ours, which is why their control law is our base.

## Open challenge — the entire steering law

```c
if (direction == 1)       dir = (left_wall  - 0.5) * 75;   // CW  -> outer wall is LEFT
else if (direction == -1) dir = (0.5 - right_wall) * 75;   // CCW -> outer wall is RIGHT
else {                                                     // direction unknown
    if (left_wall  > 0.5) dir = (left_wall  - 0.5) * 75;
    if (right_wall > 0.5) dir = (0.5 - right_wall) * 75;
}
```

No emergency override, no corner detection, no gap logic. Corners are handled
**implicitly**: approaching one, the wall ahead raises the outer-wall density,
which drives the steering into the turn — and the sign is correct in both
directions.

## The normalisation quirk that matters for scaling

```c
if (val < 70) { if (j < 160) left_wall += 1; else right_wall += 1; }
left_wall  /= 160 * 80;      // 12800, but each half is 160x120 = 19200 px
right_wall /= 160 * 80;
```

So their wall value maxes at **1.5**, not 1.0, and the 0.5 setpoint is really
**33 % dark**. In terms of the true dark fraction `f`:

```
dir = (1.5f - 0.5) * 75 = 112.5f - 37.5
sensitivity 112.5 per unit f against a +-45 deg clamp = 2.5 x clamp
```

Our clamp is +-20 deg, so the equivalent gain is `20 * 2.5 = 50` — see
`OUTER_KP` in [`../../src/config.py`](../../src/config.py).

## Other details taken from the source

| Item | Their value |
|---|---|
| Servo trim | `angle += 7` — they had a mechanical drift too |
| Line thresholds | 1500 px of 38400 = **0.039** fraction |
| Blue line HSV | `sat>60, 90<val<240, 90<hue<135` |
| Orange line HSV | `sat>30, 60<val<240, 15<=hue<=45` |
| Speed | `motor(1)` — full, always |
| Finish | quadrant 12 -> run 100 more cycles -> stop |

## Obstacle challenge — structurally different

Steering comes **only** from pillars: `dir = Err * kp` (kp = 0.30), where

```c
green: Err = -((180 + y*2) - x)      red: Err = (x - (140 - y*2))
```

With no pillar visible `Err = 0`, so it drives straight until a wall exceeds
**0.625**, which is the only wall reaction (`dir = +-45`). Parking is a separate
state machine: `dir = (left_wall - 0.8) * 50`, stopping when the magenta area
exceeds 3400.
