# models — 3D-printed parts and CAD

## CAD renders

<p align="center">
  <img src="renders/chassis-top-steering-centered.png" width="300" alt="Chassis, steering centred">
  <img src="renders/chassis-top-steering-left.png" width="300" alt="Chassis, steering turned">
</p>

| Render | Shows |
|---|---|
| [`chassis-top-steering-centered.png`](renders/chassis-top-steering-centered.png) | Full chassis from above, **steering centred** — Ackermann tie-rod, servo bay, rear axle |
| [`chassis-top-steering-left.png`](renders/chassis-top-steering-left.png) | Same view with the **steering turned**, showing the linkage sweep and wheel angles |
| [`chassis-top-plate.png`](renders/chassis-top-plate.png) | Base plate with the mounting-hole pattern (Pi, driver, battery) and the rear-axle cut-out |
| [`chassis-side.png`](renders/chassis-side.png) | Side profile — ride height and wheelbase |
| [`chassis-rear-axle.png`](renders/chassis-rear-axle.png) | Rear axle assembly — drive gear and axle supports |

### Design notes visible in the renders
- **Ackermann front steering**: a single SG90 servo drives a central bell-crank
  through a tie-rod to both steering knuckles, so the inner wheel turns more
  sharply than the outer one through a corner. Mechanical limit **±35°**.
- **Rear axle with a differential**: an **N20 gear motor (12 V, 200 rpm)** drives
  the axle through a **25:20 spur pair (1.25:1)** into a **differential**, letting
  the driven wheels turn at different speeds. This is what allows the full ±35° of
  steering — an earlier solid axle scrubbed and forced the software limit down to
  ~8°. See [`../ENGINEERING-JOURNAL.md`](../ENGINEERING-JOURNAL.md).
- The base plate's hole grid carries the Raspberry Pi, the L9110S driver, the
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

> **Fasteners, bearings, and bronze spacers:** the mechanical BOM currently
> lists only the printed parts. Screw sizes/counts and spacer types per
> assembly are still to be added.

## Folder contents

```
models/
├── renders/       # CAD renders (above)
├── 3d-parts/      # source CAD — individual part STLs, by subassembly, + Mechanical-BOM.docx
└── printing/      # 5 pre-sliced 3MF plates, ready to print on the Bambu Lab A1
```

> **To add:** the full Fusion 360 assembly file, the differential/steering
> assembly notes and photos, and photos for the BOM table above.
