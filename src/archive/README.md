# archive — superseded diagnostic programs

These are **not used in competition**. They are kept because the engineering
journal cites the measurements they produced, and each one settled a question
that changed the design.

| File | What it was for | What it proved |
|---|---|---|
| `legacy_open.py` | Last year's Open Challenge code, ported to this year's hardware | Their constants do **not** transfer. Their wall target of 0.5 read **0.021** on our camera — different lens, different mounting height, different ROI. This is why every distance constant was re-measured on this car instead of copied. |
| `pure_open.py` | The single-wall control law and nothing else — no emergency, no corner code, no lap counting | That corners are handled **implicitly**: approaching one, the wall ahead raises the outer-wall density, which drives the steering into the turn. No dedicated corner detector is needed for the law to work. |
| `freespace_test.py` | Visualiser for the free-space / follow-the-gap profile ("method B") | The gap follower was built and measured, then **rejected**: it skipped the wall emergency, and 79 of 98 near-collision frames had zero avoidance. The outer-wall PD replaced it. |

The live programs are `src/open_challenge.py` and `src/obstacle_challenge.py`.
