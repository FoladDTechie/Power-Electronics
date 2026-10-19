## Charge voltage (VFB divider)
- R_top 100k / R_bot 102k (0.1 %): VBAT = 4.159 V; worst case (VREG +-0.5 %, R +-0.1 %) 4.134-4.184 V; VFB leakage <= 10.0 mV more
- Highest possible charge voltage 4.194 V (target: never above 4.20 V)
- Divider drain on the battery: 20.6 uA, plus IC sleep current 15 uA (datasheet, single value)

## Charge current (sense resistor)
- RSR = 40 mV / 2.0 A = 20 mOhm -> 20 mOhm WSL1206 (1 %)
- Fast charge 2.00 A +-3 % (plus 1 % resistor); precharge and termination 0.20 A +-25 %
- RSR dissipation 80 mW vs 250 mW rating; cycle-by-cycle limit 4.0 A

## MPP (input voltage regulation)
- R3 499k / R4 36.0k: VCC-side regulation 17.83 V (+-0.6 % ref, +-1 % R -> 17.37-18.30 V)
- Panel held at about 18.2 V including the input Schottky [ASSUMPTION VF ~0.4 V] vs panel Vmp 18.0 V [ASSUMPTION]
- MPPSET leakage bound 1 uA (spec'd at 7 V) x 33.6k = 33.6 mV -> up to 0.50 V shift at the input (worst case, unverified at 1.2 V)

## Power stage
- VIN 17.83 V, VBAT 3.00 V: D = 0.168; ripple 0.61 A (31 % of 2.0 A; L -20 %, f min), peak 2.31 A
- VIN 17.83 V, VBAT 4.16 V: D = 0.233; ripple 0.78 A (39 % of 2.0 A; L -20 %, f min), peak 2.39 A
- VIN 22.00 V, VBAT 3.00 V: D = 0.136; ripple 0.64 A (32 % of 2.0 A; L -20 %, f min), peak 2.32 A
- VIN 22.00 V, VBAT 4.16 V: D = 0.189; ripple 0.83 A (41 % of 2.0 A; L -20 %, f min), peak 2.41 A
- Inductor XAL6060-103: Isat 7.6 A (30 % drop) vs cycle-by-cycle limit 4.0 A; DCR loss 119 mW
- Output LC: L 10 uH, C 10 uF [ASSUMPTION effective] -> f0 = 15.9 kHz (datasheet target 12-17 kHz)
    L x0.8, C x0.8: 19.9 kHz
    L x0.8, C x1.2: 16.2 kHz
    L x1.2, C x0.8: 16.2 kHz
    L x1.2, C x1.2: 13.3 kHz
- Input RMS current 0.85 A (D = 0.233)
- Input current 0.52 A at 17.8 V [ASSUMPTION eta 0.9]; SS34 loss <= 259 mW
- high-side FET conduction 13 mW (RDS(on) max at VGS 5 V; gate drive ~6 V from REGN, VGS max 10.0 V)
- low-side FET conduction 43 mW (RDS(on) max at VGS 5 V; gate drive ~6 V from REGN, VGS max 10.0 V)
- Gate-drive power ~ 2 x Qg x 6 V x f = 81 mW from REGN

## Input protection
- TVS SMAJ24A: VR 24.0 V > Voc 22.0 V; VC 38.9 V at Ipp vs BQ24650 VCC abs max 33.0 V and PH abs max 36.0 V

## TS window (103AT, B-model)
- NTC from B = 3435 K: R(0 C) = 28.70k, R(45 C) = 4.85k
- Exact (B-model) RT1 = 4.34k, RT2 = 20.8k
- CHOSEN 4.32k / 20.5k (E96 nearest): charging allowed -0.1 C to 45.1 C, cut-off 48.8 C
- TI example 5.23k / 30.1k: charging allowed 0.5 C to 40.7 C, cut-off 44.2 C
    T (C)   TS % of VREF (chosen)
       -5    75.2
        0    73.5
       10    69.2
       25    60.9
       40    51.0
       45    47.6
       50    44.2
       55    40.8
       60    37.6
  [ASSUMPTION] B-parameter model with B25/85; the Semitec R-T table was not readable,
  so the real window can differ by a few degrees. Recompute with the table before use.
