# Plan: BNO085 Power Gating with P-Channel MOSFET

## Problem

The BNO085 draws ~300-500µA in I2C sleep mode. With a 150mAh battery, idle draw alone consumes ~23mAh/day — over half the daily power budget. The nRF54L15 can drop to ~10µA in System OFF with BLE wake, but the BNO085 idles at 50x that.

## Impact

| Scenario | Daily draw | Battery life (150mAh) |
|----------|-----------|----------------------|
| Without power gating (1mA idle) | ~43mAh/day | ~3.5 days |
| With power gating (~0.01mA idle) | ~20mAh/day | ~7+ days |

## Solution

Add a P-channel MOSFET (SI2301, SOT-23) as a high-side switch between the XIAO's 3V3 rail and the BNO085's VIN pin. Controlled by a single GPIO.

## Part

- **SI2301CDS** — P-channel MOSFET, SOT-23 package
- Vgs(th): -1.0V to -2.0V (works with 3.3V logic)
- Rds(on): ~100mΩ (negligible voltage drop at 30mA)
- Package: 2.9mm × 1.6mm × 1.1mm
- Cost: ~$0.20

## Wiring

```
XIAO 3V3 ──────┬──── MOSFET Source
                │
              [10K]   Pull-up resistor (gate to source)
                │
XIAO D3 ───────┴──── MOSFET Gate

                      MOSFET Drain ──── BNO085 VIN
```

- **Gate LOW** (GPIO driven low) → MOSFET ON → BNO085 powered
- **Gate HIGH / floating** (GPIO high or tri-state) → MOSFET OFF → BNO085 draws zero
- 10K pull-up ensures BNO085 stays OFF at boot until firmware explicitly turns it on

## Connections Summary (5 wires + 1 component)

| Wire | From | To | Color |
|------|------|----|-------|
| 3V3 | XIAO 3V3 | MOSFET source | Red |
| VIN | MOSFET drain | BNO085 VIN | Red |
| GND | XIAO GND | BNO085 GND | Black |
| SDA | XIAO D4 | BNO085 SDA | Blue |
| SCL | XIAO D5 | BNO085 SCL | Yellow |
| GATE | XIAO D3 | MOSFET gate | White |
| Pull-up | 10K resistor, MOSFET gate to source | — |

## Physical Assembly

1. Dead-bug the SOT-23 MOSFET, tack down with kapton tape or hot glue
2. Place it on top of the BNO085 board near the VIN pin to keep wires short
3. Solder 30AWG wires to the three MOSFET pads
4. 10K 0402 or 0603 resistor soldered between gate and source leads

## Firmware

```c
// Initialize power control pin
nrf_gpio_cfg_output(D3);
nrf_gpio_pin_set(D3);      // HIGH = BNO085 OFF at boot

// Power on BNO085
nrf_gpio_pin_clear(D3);    // LOW = MOSFET on
k_msleep(100);             // BNO085 boot time
// ... init I2C, configure BNO085 ...

// Power off BNO085
nrf_gpio_pin_set(D3);      // HIGH = MOSFET off, zero draw
```

## Status

- [ ] Order SI2301CDS (or equivalent P-FET in SOT-23)
- [ ] Order 10K 0603 resistors
- [ ] Update connections.json with power gating wiring
- [ ] Add MOSFET to 3D assembly visualization
- [ ] Test power draw with multimeter before/after
- [ ] Implement firmware power control

## Decision

Add to dev kit #1 — it's one extra component and one extra wire for 2x battery life.
