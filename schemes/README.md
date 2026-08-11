# schemes — electromechanical / wiring diagrams

Add the wiring schematic image(s) here (PNG/PDF). It should show:

- **Raspberry Pi 4** GPIO connections:
  - Steering servo signal → **GPIO13**
  - L9110S `A-IA` → **GPIO23**, `A-IB` → **GPIO24**
- **L9110S** H-bridge: `VCC` → battery +, `GND` → common ground, MOTOR-A → drive motor
- **Power**: battery → L9110S `VCC` (motor) and battery → 5 V regulator → Pi 5 V
- **Common ground** tying Pi GND, driver GND and battery − together

> Key design points: separate power rails for motor vs Pi, a shared ground, and
> no direct forward↔reverse switching (regulator protection).
