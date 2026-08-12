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

## Folder contents

```
models/
├── renders/       # CAD renders (above)
├── 3d-parts/      # source CAD — full robot assembly (F3D / STEP) + individual parts
└── printing/      # STL files + sliced plates, ready to print, with slicer settings
```

> **To add:** the full Fusion 360 assembly, the individual part STLs, and the
> sliced print plates with their settings — so judges can reproduce the whole car.
