# v-photos — vehicle photos

Six views of the car, Team The Red Castle.

| View | File | What it shows |
|---|---|---|
| Front | [front.jpg](front.jpg) | OV5647 wide camera on its mast, front Ackermann steering axle |
| Back | [back.jpg](back.jpg) | Raspberry Pi 4 ports, rear drive axle and motor coupling |
| Left | [left.jpg](left.jpg) | Side profile — camera height/tilt, Pi deck, battery on top |
| Right | [right.jpg](right.jpg) | Side profile — power switch, 5 V regulator, drive gear |
| Top | [top.jpg](top.jpg) | Battery pack, camera mast, overall footprint |
| Bottom | [bottom.jpg](bottom.jpg) | Chassis underside — steering servo + linkage, motor, drive gear |

Key details visible: the camera is centred and forward-facing on a rigid mast
(12.5 cm above the mat, tilted ~15° down), the steering servo drives an Ackermann
linkage on the front axle, and the drive motor turns the rear axle through a spur
gear. The Pi sits on its own deck with a separate 5 V regulator below, keeping the
motor supply on its own rail (see the wiring notes in [`../schemes/`](../schemes)).
