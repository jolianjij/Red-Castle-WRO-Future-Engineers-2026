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

A single SG90 servo drives a central bell-crank through a tie-rod to both
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
| Base | 1 | Fixed | _<photo: base plate>_ |
| Middle plate | 1 | Fixed | _<photo: middle plate>_ |
| Top plate | 1 | Fixed | _<photo: top plate>_ |
| Camera holder | 1 | Fixed | _<photo: camera holder>_ |
| Battery slider p1 | 1 | Fixed | _<photo: battery slider p1>_ |
| Battery slider p2 | 1 | Moving | _<photo: battery slider p2>_ |
| N20 motor holder | 1 | Fixed | _<photo: N20 holder>_ |
| N20 gear | 1 | Moving | _<photo: N20 gear>_ |
| Inner differential gear | 2 | Moving | _<photo: inner differential gear>_ |
| Outer differential gear | 1 | Moving | _<photo: outer differential gear>_ |
| Differential outer shell | 1 | Fixed | _<photo: differential outer shell>_ |
| Inner gear with long shaft | 1 | Moving | _<photo: inner gear, long shaft>_ |
| Inner gear with short shaft | 1 | Moving | _<photo: inner gear, short shaft>_ |
| Ring | 2 | Moving | _<photo: ring>_ |
| Steering base | 1 | Moving | _<photo: steering base>_ |
| Steering base servo mount | 1 | Moving | _<photo: steering base servo mount>_ |
| Steering nut | 2 | Moving | _<photo: steering nut>_ |
| Steering wheel mount | 2 | Moving | _<photo: steering wheel mount>_ |
| Wheel | 4 | Moving | _<photo: wheel>_ |
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
├── 3d-parts/      # source CAD — individual part STLs, by subassembly, + Mechanical-BOM.docx
└── printing/      # 5 pre-sliced 3MF plates, ready to print on the Bambu Lab A1
```

> **To add:** the full Fusion 360 assembly file and photos for the BOM table
> above.
