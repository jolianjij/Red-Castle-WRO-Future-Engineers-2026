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
- **Ackermann front steering**: a single servo drives a central bell-crank through
  a tie-rod to both steering knuckles, so the inner wheel turns more sharply than
  the outer one through a corner.
- **Rear axle**: one drive motor turns a spur gear on a solid rear axle. This is
  the drivetrain that currently has **no differential**, which is why the steering
  deviation is software-limited (`STEER_MAX`) to avoid wheel scrub — see
  [`../ENGINEERING-JOURNAL.md`](../ENGINEERING-JOURNAL.md).
- The base plate's hole grid carries the Raspberry Pi, the L9110S driver, the
  buck converter and the battery holder; the camera mast bolts to the front.

## Folder contents

```
models/
├── renders/       # CAD renders (above)
├── printing/      # print-ready files (STL / gcode) + slicer settings
└── 3d-parts/      # source CAD (STEP / F3D / SLDPRT ...)
```

> **To add:** the actual source CAD and STL files go in `3d-parts/` and
> `printing/`. The renders alone document the design, but judges should be able to
> re-print the parts.
