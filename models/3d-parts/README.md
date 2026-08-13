# 3D Parts — source CAD

Individual printable parts, exported as STL, one folder per subassembly.
`Mechanical-BOM.docx` is the authoritative parts list (quantities, moving/fixed,
material) — reproduced as a table in [`../README.md`](../README.md).

```
3d-parts/
├── chassis/                     base plate, middle plate, top plate, camera holder
├── steering/                    Ackermann linkage — base, servo mount, ring, nut, wheel mounts
├── rear-drive/                  differential, gears, N20 motor holder
├── wheels/                      wheel + shaft mount
├── battery-slider-mechanism/    battery tray, sliding part
└── Mechanical-BOM.docx          source bill of materials
```

Individual per-part renders (17 of 20, used as the BOM photo column) are in
[`../renders/parts/`](../renders/parts) and shown in the BOM table in
[`../README.md`](../README.md#bill-of-materials--3d-printed-parts).

> **Still to add:** the full Fusion 360 robot assembly file (`.f3d` / `.step`),
> the differential + steering assembly-with-pictures notes, and renders for
> the last 2 parts (battery slider p2, wheel-mount-to-shaft).
