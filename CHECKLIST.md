# Submission Checklist — Team The Red Castle

**📷 = only you can do it · 🤖 = Claude can do/commit.**

## Done
- [x] Official WRO repo structure (`src`, `models`, `schemes`, `t-photos`, `v-photos`, `video`, `other`)
- [x] Engineering `README.md` (mobility, power/sense, camera/vision, both algorithms, setup/run) — current with the final `src/`
- [x] All control code + tools in `src/`
- [x] Bill of Materials (`other/bill-of-materials.md`)
- [x] Public repo pushed

## 🔴 Mandatory for judging
- [x] 📷 `v-photos/` — 6 vehicle photos (front, back, left, right, top, bottom)
- [x] 📷 `t-photos/` — 4 member photos + 2 group photos
- [x] 🎥 `video/video.md` — Open Challenge + Obstacle Challenge YouTube links added
- [x] 🖼️ `schemes/` — wiring diagram image (Pi ↔ L9110S ↔ servo ↔ power, common ground)
- [x] 🧩 `models/3d-parts/` — 20 part STLs (5 subassemblies) + Mechanical-BOM.docx + CAD renders (full assembly, steering, rear axle/differential)
- [x] 🧩 `models/printing/` — 5 sliced 3MF plates, ready to print
- [x] ✍️ Team names + roles in `README.md`
- [x] ✍️ Bio + email for each member — filled in README §12
- [x] **Engineering Journal — `Engineering-Journal.pptx` and `.pdf`**, built in last year's template/structure with our current, accurate content

## 🟡 Recommended (higher documentation score)
- [ ] 🤖 Wiring pin-table / ASCII schematic in `schemes/` (text backup to the image)
- [ ] 🤖 Assembly / build-steps section
- [x] 🤖 Engineering journal narrative (design process, iterative debugging) — `ENGINEERING-JOURNAL.md`
- [x] 🤖 BOM: battery (3×18650), buck converter, SG90 servo confirmed from the wiring diagram
- [x] 🤖 BOM: N20 motor (12 V 200 rpm), differential, 25:20 gears, PLA+ Silk Silver / Bambu A1 / Fusion 360, Pi 2 GB
- [x] 🤖 BOM: 20-part printed-parts table with quantities and fixed/moving status
- [x] 🤖 BOM: fasteners (M3×8 ×18, M3×20 ×4) and brass spacers (M-F 25 mm ×4, F-F 20 mm ×4)
- [x] 🤖 BOM: total cost (≈ $120)
- [x] 📏 Measurements: mass (407 g), wheel diameter (4.7 cm), wheelbase (9.4 cm), track (8.5 cm), dimensions (14.2×9.3×15 cm), camera height/tilt, servo trim (−9°)
- [x] 🤖 Commit reference `colors.json`, `camera_settings.json`, `servo_center.txt` in `src/`
- [ ] 📏 Measured (timed) real max speed — deliberately left as the theoretical figure; not being chased further
- [ ] 📷 BOM part photos (one per printed part — placeholders are in `models/README.md`)
- [ ] 📷 Full Fusion 360 assembly file (`.f3d`/`.step`)
- [ ] 🤖 Tag a `v1.0` GitHub release once everything below is settled

## ⚙️ Competition readiness
- [x] Color tuning (blue, orange, green, red, magenta) calibrated on the real field
- [x] White balance / exposure locked (`camera_settings.json`)
- [x] Open Challenge field-tested, both directions, completes and stops correctly
- [x] Obstacle Challenge field-tested — sign passing + lane keeping between signs work
- [x] Both challenge runs recorded and uploaded
- [ ] **Known open issue:** shadow at two of four corners occasionally misread as wall — diagnosed (`tools/shadow_check.py`), not yet fully closed out
- [ ] **Known gap:** parking is not wired into the Obstacle Challenge main loop yet (magenta is treated as a wall to avoid, not a target)

## Info still needed from you
- [ ] Total build cost — ~~needed~~ **received: ≈ $120** ✓
- [ ] Fastener/spacer BOM — ~~needed~~ **received** ✓
- [ ] Servo trim — ~~needed~~ **received: −9°** ✓
- [ ] BOM part photos + Fusion assembly file (mentioned as coming)
- [ ] Real measured max speed — explicitly not required per your instruction
