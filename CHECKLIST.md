# Submission Checklist — Team The Red Castle

Two days to go. **📷 = only you can do it · 🤖 = Claude can do/commit.**

## Done
- [x] Official WRO repo structure (`src`, `models`, `schemes`, `t-photos`, `v-photos`, `video`, `other`)
- [x] Engineering `README.md` (mobility, power/sense, camera/vision, both algorithms, setup/run)
- [x] All control code + tools in `src/`
- [x] Bill of Materials (`other/bill-of-materials.md`)
- [x] Public repo pushed

## 🔴 Mandatory for judging
- [ ] 📷 `v-photos/` — 6 vehicle photos (front, back, left, right, top, bottom)
- [ ] 📷 `t-photos/` — 2 team photos (official + fun)
- [ ] 🎥 `video/video.md` — driving video links (Open + Obstacle, one take each)
- [ ] 🖼️ `schemes/` — wiring diagram image (Pi ↔ L9110S ↔ servo ↔ power, common ground)
- [ ] 🧩 `models/` — actual CAD/STL files of the printed parts
- [ ] ✍️ Team names + roles in `README.md` (🤖 give me the names)

## 🟡 Recommended (higher documentation score)
- [ ] 🤖 Wiring pin-table / ASCII schematic in `schemes/` (text backup to the image)
- [ ] 🤖 Assembly / build-steps section
- [ ] 🤖 Engineering journal (design process: brownout fix, no-diff steering, focus/exposure)
- [ ] 🤖 Finish BOM specifics (battery, motor, servo, wheels) — needs your confirmation
- [ ] 🤖 Commit reference `colors.json` + `servo_center.txt` (pull from Pi once tuning is final)

## ⚙️ To actually compete (not GitHub, but required)
- [ ] Finish color tuning — orange, green, red, magenta with each object in view
- [ ] Open Challenge field test → tune `STEER_MAX` and PD gains
- [ ] Obstacle Challenge field test → pillar passing + parking
- [ ] Record the runs for the video

## Info Claude needs from you
- [ ] Team members' names + roles
- [ ] Battery voltage & type
- [ ] Drive motor model/voltage
- [ ] Steering servo model
- [ ] Wheel/tire sizes
