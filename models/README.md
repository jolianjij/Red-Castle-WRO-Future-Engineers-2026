# models — 3D-printed parts and CAD

## Full assembly

<p align="center">
  <img src="renders/full-assembly.png" width="600" alt="Full car assembly, angled view">
</p>

Front Ackermann steering axle on the left, rear differential axle with the N20
motor and gear cluster on the right.

## Front steering assembly

<p align="center">
  <img src="renders/front-steering-linkage.png" width="420" alt="Front steering linkage, top view">
  <img src="renders/chassis-top-steering-centered.png" width="280" alt="Chassis, steering centred">
  <img src="renders/chassis-top-steering-left.png" width="280" alt="Chassis, steering turned">
</p>

A single MG90S servo drives a central bell-crank through a tie-rod to both
steering knuckles, so the inner wheel turns more sharply than the outer one
through a corner. Mechanical limit **±35°**.

## Rear axle and differential

<p align="center">
  <img src="renders/rear-axle-differential-front.png" width="280" alt="Rear axle, front view">
  <img src="renders/rear-axle-differential-top.png" width="280" alt="Rear axle, top view">
  <img src="renders/rear-axle-differential-mesh.png" width="280" alt="Differential gear mesh detail">
</p>

An **N20 gear motor (12 V, 200 rpm)** drives the axle through a **25:20 spur
pair (1.25:1)** into the differential. The differential lets the driven wheels
turn at different speeds through a corner, which is what allows the full ±35°
of steering — an earlier solid axle scrubbed and forced the software limit
down to ~8°. See [`../ENGINEERING-JOURNAL.md`](../ENGINEERING-JOURNAL.md).

## Chassis

<p align="center">
  <img src="renders/chassis-top-plate.png" width="300" alt="Base plate, mounting holes">
  <img src="renders/chassis-side.png" width="230" alt="Side profile">
</p>

The base plate's hole grid carries the Raspberry Pi, the L9110S driver, the
buck converter and the battery holder; the camera mast bolts to the front.

## Manufacturing

| | |
|---|---|
| **CAD** | Fusion 360 |
| **Printer** | Bambu Lab A1 |
| **Material** | PLA+ Silk Silver |

## Bill of materials — 3D-printed parts

All printed parts, quantities, and whether each is a fixed or moving part
(from `3d-parts/Mechanical-BOM.docx`). All parts are **PLA+**.

| Part | Qty | Fixed / Moving | Photo |
|---|---|---|---|
| Base | 1 | Fixed | <img src="renders/parts/base.png" width="110"> |
| Middle plate | 1 | Fixed | <img src="renders/parts/middle-plate.png" width="110"> |
| Top plate | 1 | Fixed | <img src="renders/parts/top-plate.png" width="110"> |
| Camera holder | 1 | Fixed | <img src="renders/parts/camera-holder.png" width="110"> |
| Battery slider p1 | 1 | Fixed | <img src="renders/parts/battery-slider.png" width="110"> |
| Battery slider p2 | 1 | Moving | _<photo: battery slider p2 — mating half not yet photographed separately>_ |
| N20 motor holder | 1 | Fixed | <img src="renders/parts/n20-motor-holder.png" width="110"> |
| N20 gear | 1 | Moving | <img src="renders/parts/n20-gear.png" width="110"> |
| Inner differential gear | 2 | Moving | <img src="renders/parts/inner-differential-gear.png" width="110"> |
| Outer differential gear | 1 | Moving | <img src="renders/parts/outer-differential-gear.png" width="110"> |
| Differential outer shell | 1 | Fixed | <img src="renders/parts/differential-outer-shell.png" width="110"> |
| Inner gear with long shaft | 1 | Moving | <img src="renders/parts/inner-gear-long-shaft.png" width="110"> |
| Inner gear with short shaft | 1 | Moving | <img src="renders/parts/inner-gear-short-shaft.png" width="110"> |
| Ring | 2 | Moving | <img src="renders/parts/ring.png" width="110"> |
| Steering base | 1 | Moving | <img src="renders/parts/steering-base.png" width="110"> |
| Steering base servo mount | 1 | Moving | <img src="renders/parts/steering-base-servo-mount.png" width="110"> |
| Steering nut | 2 | Moving | <img src="renders/parts/steering-nut.png" width="110"> |
| Steering wheel mount | 2 | Moving | <img src="renders/parts/steering-wheel-mount.png" width="110"> |
| Wheel | 4 | Moving | <img src="renders/parts/wheel.png" width="110"> |
| Wheel mount to shaft | 4 | Moving | _<photo: wheel mount to shaft>_ |

**Print note:** moving parts need lubrication to reduce friction — we use
Vaseline on all mating surfaces listed as "Moving" above.

## Fasteners and spacers

| Part | Spec | Qty |
|---|---|---|
| Screw | M3 × 8 mm | 18 |
| Screw | M3 × 20 mm | 4 |
| Standoff, male–female | brass, 25 mm | 4 |
| Standoff, female–female | brass, 20 mm | 4 |

## Folder contents

```
models/
├── renders/       # CAD renders (above)
│   └── parts/     # individual per-part renders, used in the BOM photo column
├── 3d-parts/      # source CAD — individual part STLs, by subassembly, + Mechanical-BOM.docx
└── printing/      # 5 pre-sliced 3MF plates, ready to print on the Bambu Lab A1
```

> **To add:** the full Fusion 360 assembly file, a separate photo for battery
> slider p2 (its mating half), and a photo for the wheel-to-shaft mount.
