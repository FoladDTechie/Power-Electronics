## Variant A: LMR33630A buck, 9-24 V -> 5 V
- Feedback 100k / 24.9k: Vout typ 5.016 V; worst case (VFB +-1.5 %, R +-1 %) 4.862-5.174 V
- Vin  9.0 V: D = 0.556, ton = 1634 ns, toff = 1307 ns; ripple 0.82 A (L-20 %, f min) -> peak 2.91 A, valley 2.09 A
- Vin 12.0 V: D = 0.417, ton = 1225 ns, toff = 1716 ns; ripple 1.07 A (L-20 %, f min) -> peak 3.04 A, valley 1.96 A
- Vin 24.0 V: D = 0.208, ton = 613 ns, toff = 2328 ns; ripple 1.46 A (L-20 %, f min) -> peak 3.23 A, valley 1.77 A
  High-side limit min 3.85 A; min on-time 108 ns, min off-time 85 ns
- Inductor XAL6060-103: Isat 7.6 A (30 % drop, typ) vs current-limit max 5.05 A; DCR loss at 2.5 A = 186 mW
- IC conduction loss at 9 V, 2.5 A (RDS max): 0.86 W (switching loss not included; datasheet gives curves only)
- IC conduction loss at 24 V, 2.5 A (RDS max): 0.75 W (switching loss not included; datasheet gives curves only)
- Output ripple (capacitive term, 24 V worst ripple, Ceff 70 uF [ASSUMPTION]): 7.6 mV
- Input RMS ripple current, worst at D = 0.5: 1.25 A
- EN divider 100k / 18.2k: start 7.79-8.18 V (typ 7.99), stop typ 7.35 V; EN at 24 V = 3.70 V
- Input current at 9 V [ASSUMPTION eta 0.85]: 1.63 A -> fuse rating >= 2.72 A (0.75 x 0.80 derating at 70 C) -> 3 A fuse, 32 V
- Reverse FET SiS443DN loss at 1.63 A: 43 mW; |VGS| at 9 V = 9 V, at 24 V clamped to 11.4-12.7 V by BZX84-C12 (VGS max 20.0 V)
- Zener current at 24 V: 0.13 mA (through 100 k)
- TVS SMAJ24A: VR 24.0 V, VC 38.9 V at Ipp vs LMR33630 VIN abs max 38.0 V -> exceeds by 0.9 V at full rated pulse
- PG pull-up 100 k from 5 V: 50 uA sink when low (VOL <= 0.2 V specified at 50 uA)

## Variant B: MT3608 boost, 1S Li-ion (3.0-4.2 V) -> 5 V
- Feedback 73.2k / 10k: Vout typ 4.992 V; worst case (VFB +-2 %, R +-1 %) 4.807-5.182 V
- Vbat 3.0 V: D = 0.455, Iin [ASSUMPTION eta 0.85] = 1.96 A, ripple 0.30 A (L-20 %), peak 2.11 A
- Vbat 3.7 V: D = 0.327, Iin [ASSUMPTION eta 0.85] = 1.59 A, ripple 0.27 A (L-20 %), peak 1.72 A
- Vbat 4.2 V: D = 0.236, Iin [ASSUMPTION eta 0.85] = 1.40 A, ripple 0.22 A (L-20 %), peak 1.51 A
  vs MT3608 switch current limit 4.0 A typ (no minimum given) and 4 A peak abs max; inductor Isat 6.7 A
- Diode SS34: average 1.0 A, peak 2.1 A; loss <= 0.50 W (VF <= 0.5 V bound from the 3 A point)
- Output ripple (capacitive term) at 3.0 V, 1.0 A: 10.8 mV [ASSUMPTION Ceff 35 uF]
- Battery current 1.96 A -> fuse rating >= 3.27 A -> 4 A fuse, 32 V. Interrupting rating 50 A: a Li-ion cell short can exceed this
- Reverse FET AON6411 at |VGS| = Vbat >= 3.0 V (spec at 2.5 V): RDS <= 3.6 mOhm, loss 14 mW
- TVS SMAJ8.5A: VR 8.5 V, IR <= 20 uA at VR (SMAJ5.0A would be up to 800 uA); VC 14.4 V < MT3608 IN abs max 26.0 V
- MT3608 UVLO 1.98 V typ: it will run a cell far below a safe Li-ion cut-off; the pack must have its own protection

