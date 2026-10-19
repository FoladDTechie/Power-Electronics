### Forward drop and dissipation (worst-case datasheet limits, 25 C parts)

| Load | Ideal diode drop | Ideal diode heat | Ideal ΔT (81 °C/W) | SS34 drop | SS34 heat | SS34 ΔT (55 °C/W) | Loss at 12 V: ideal / Schottky |
|---|---|---|---|---|---|---|---|
| 0.5 A | 32 mV | 16 mW | 1.3 K | ≤ 500 mV | ≤ 0.25 W | ≤ 14 K | 0.27 % / ≤ 4.2 % |
| 1.0 A | 32 mV | 32 mW | 2.6 K | ≤ 500 mV | ≤ 0.50 W | ≤ 28 K | 0.27 % / ≤ 4.2 % |
| 2.0 A | 32 mV | 64 mW | 5.2 K | ≤ 500 mV | ≤ 1.00 W | ≤ 55 K | 0.27 % / ≤ 4.2 % |
| 3.0 A | 48 mV | 144 mW | 11.7 K | ≤ 500 mV | ≤ 1.50 W | ≤ 82 K | 0.40 % / ≤ 4.2 % |

At 3 A, 40 °C ambient [ASSUMPTION]:
- Ideal diode, RDS(on) x1.5 hot [ASSUMPTION]: 72 mV, 216 mW, TJ ≈ 57 °C
- SS34 at VF max: 1.50 W, TJ ≈ 122 °C (TJ max 150 °C; VF falls when hot, so this is pessimistic for drop)
- Quiescent cost of the ideal diode: LTC4412 ≤ 26 µA (= 0.31 mW at 12 V)

### Reverse leakage (blocking direction)

| Condition | Ideal diode (SiS443DN IDSS + LTC4412 leakage) | SS34 IR |
|---|---|---|
| 25 °C | ≤ 4 µA (IDSS at −40 V) | ≤ 0.5 mA (at 40 V) |
| Hot | ≤ 8 µA (IDSS at 55 °C) | ≤ 20 mA (at 100 °C) |

### Gate drive check
- LTC4412 VG(ON) min = 6.3 V once VIN ≥ 6.3 V, above the -4.5 V at which RDS(on) max = 16 mΩ is specified.
- Full gate drive is limited to VIN below 6.3 V; RDS(on) is not specified for |VGS| < 4.5 V, so the 16 mΩ figure holds only for VIN ≥ 4.5 V.
- MOSFET fully on above I = VFR / RDS = 2.0 A (below that the drop is held at VFR, 10-32 mV).
