#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Drop and heat comparison: LTC4412 + SiS443DN ideal diode vs SS34 Schottky.

Every datasheet number is in DATASHEET with its source. Anything not in a
datasheet is in ASSUMPTION and is labelled in the output.

    python3 oring_calc.py              # markdown tables to stdout
"""

DATASHEET = {
    # Analog Devices LTC4412 Rev B: forward regulation voltage VFR max
    "ltc4412_vfr_max_V": 0.032,
    "ltc4412_vfr_typ_V": 0.020,
    # LTC4412: gate clamp VG(ON) min (VIN - VGATE)
    "ltc4412_vgon_min_V": 6.3,
    # LTC4412: quiescent current max, forward regulation, VIN = 28 V
    "ltc4412_iq_max_A": 26e-6,
    # LTC4412: VIN/SENSE leakage, magnitude of the min/max limits
    "ltc4412_ileak_max_A": 3e-6,
    # Vishay SiS443DN doc 63253 rev C: RDS(on) max at VGS = -4.5 V, 25 C
    "sis443_rds_max_4v5_ohm": 0.0160,
    # SiS443DN: RDS(on) max at VGS = -10 V
    "sis443_rds_max_10v_ohm": 0.0117,
    # SiS443DN: RthJA steady state, max (datasheet mounting conditions)
    "sis443_rthja_CW": 81.0,
    # SiS443DN: IDSS max at -40 V: 25 C and 55 C
    "sis443_idss_25_A": 1e-6,
    "sis443_idss_55_A": 5e-6,
    # Vishay SS32..SS36 doc 88751 (23-Apr-2020): SS34 VF max at 3 A, 25 C
    "ss34_vf_max_3A_V": 0.50,
    # SS34: RthJA typical, 14 x 14 mm copper pads
    "ss34_rthja_CW": 55.0,
    # SS34: IR max at rated VR: 25 C and 100 C
    "ss34_ir_25_A": 0.5e-3,
    "ss34_ir_100_A": 20e-3,
    "tj_max_C": 150.0,  # both parts
}

ASSUMPTION = {
    # RDS(on) rise at a hot junction. Only a graph exists in the datasheet;
    # 1.5x is a typical trench-MOSFET figure at about 125 C, NOT read from it.
    "rds_hot_factor": 1.5,
    # Bus voltage used to express loss as a percentage.
    "bus_V": 12.0,
    # Ambient for the junction-temperature column.
    "t_amb_C": 40.0,
}

CURRENTS = [0.5, 1.0, 2.0, 3.0]


def ideal_drop(i, rds):
    # The LTC4412 regulates VIN - VSENSE to VFR until the MOSFET is fully on;
    # after that the drop is I * RDS(on).
    return max(DATASHEET["ltc4412_vfr_max_V"], i * rds)


def main():
    rds = DATASHEET["sis443_rds_max_4v5_ohm"]
    rds_hot = rds * ASSUMPTION["rds_hot_factor"]
    ta = ASSUMPTION["t_amb_C"]
    print("### Forward drop and dissipation (worst-case datasheet limits, 25 C parts)\n")
    print("| Load | Ideal diode drop | Ideal diode heat | Ideal ΔT (81 °C/W) "
          "| SS34 drop | SS34 heat | SS34 ΔT (55 °C/W) | Loss at 12 V: ideal / Schottky |")
    print("|---|---|---|---|---|---|---|---|")
    for i in CURRENTS:
        vd = ideal_drop(i, rds)
        pd = vd * i
        vs = DATASHEET["ss34_vf_max_3A_V"]  # upper bound for every I <= 3 A
        ps = vs * i
        pin = ASSUMPTION["bus_V"] * i
        print(f"| {i:.1f} A | {vd*1e3:.0f} mV | {pd*1e3:.0f} mW | {pd*DATASHEET['sis443_rthja_CW']:.1f} K "
              f"| ≤ {vs*1e3:.0f} mV | ≤ {ps:.2f} W | ≤ {ps*DATASHEET['ss34_rthja_CW']:.0f} K "
              f"| {pd/pin*100:.2f} % / ≤ {ps/pin*100:.1f} % |")
    print()
    i = 3.0
    pd_hot = ideal_drop(i, rds_hot) * i
    ps = DATASHEET["ss34_vf_max_3A_V"] * i
    print(f"At 3 A, {ta:.0f} °C ambient [ASSUMPTION]:")
    print(f"- Ideal diode, RDS(on) x{ASSUMPTION['rds_hot_factor']} hot [ASSUMPTION]: "
          f"{ideal_drop(i, rds_hot)*1e3:.0f} mV, {pd_hot*1e3:.0f} mW, "
          f"TJ ≈ {ta + pd_hot*DATASHEET['sis443_rthja_CW']:.0f} °C")
    print(f"- SS34 at VF max: {ps:.2f} W, TJ ≈ {ta + ps*DATASHEET['ss34_rthja_CW']:.0f} °C "
          f"(TJ max {DATASHEET['tj_max_C']:.0f} °C; VF falls when hot, so this is pessimistic for drop)")
    print(f"- Quiescent cost of the ideal diode: LTC4412 ≤ {DATASHEET['ltc4412_iq_max_A']*1e6:.0f} µA "
          f"(= {DATASHEET['ltc4412_iq_max_A']*ASSUMPTION['bus_V']*1e3:.2f} mW at 12 V)")
    print()
    print("### Reverse leakage (blocking direction)\n")
    print("| Condition | Ideal diode (SiS443DN IDSS + LTC4412 leakage) | SS34 IR |")
    print("|---|---|---|")
    print(f"| 25 °C | ≤ {(DATASHEET['sis443_idss_25_A']+DATASHEET['ltc4412_ileak_max_A'])*1e6:.0f} µA "
          f"(IDSS at −40 V) | ≤ {DATASHEET['ss34_ir_25_A']*1e3:.1f} mA (at 40 V) |")
    print(f"| Hot | ≤ {(DATASHEET['sis443_idss_55_A']+DATASHEET['ltc4412_ileak_max_A'])*1e6:.0f} µA "
          f"(IDSS at 55 °C) | ≤ {DATASHEET['ss34_ir_100_A']*1e3:.0f} mA (at 100 °C) |")
    print()
    print("### Gate drive check")
    print(f"- LTC4412 VG(ON) min = {DATASHEET['ltc4412_vgon_min_V']} V once VIN ≥ 6.3 V, "
          f"above the -4.5 V at which RDS(on) max = {rds*1e3:.0f} mΩ is specified.")
    print(f"- Full gate drive is limited to VIN below 6.3 V; RDS(on) is not specified for |VGS| < 4.5 V,"
          f" so the 16 mΩ figure holds only for VIN ≥ 4.5 V.")
    print(f"- MOSFET fully on above I = VFR / RDS = {DATASHEET['ltc4412_vfr_max_V']/rds:.1f} A "
          f"(below that the drop is held at VFR, 10-32 mV).")


if __name__ == "__main__":
    main()
