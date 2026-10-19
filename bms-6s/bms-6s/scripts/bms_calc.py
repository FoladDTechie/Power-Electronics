#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Design calculations for the 6S BQ76930 protection board.

    python3 bms_calc.py

Datasheet numbers live in DS with their source. Anything not from a
datasheet lives in ASSUME and is printed with [ASSUMPTION]. Register values
are what the host should write; the board has no host of its own.
"""
import math

CELLS = 6
V_CELL = {"min": 2.5, "nom": 3.7, "max": 4.2}      # LiPo/Li-ion NMC [ASSUMPTION: check your cells]
I_DSG_CONT, I_CHG_MAX = 20.0, 5.0                # design targets
OCD_TARGET, SCD_TARGET = 30.0, 60.0              # A
OV_TARGET, UV_TARGET = 4.25, 3.00                # V per cell

DS = {
    # TI BQ769x0 (SLUSBK2I), BQ76930 rows
    "grp_vmin": 6.0, "grp_vmax": 25.0,            # recommended, per group (BAT-VC5x, VC5x-VSS)
    "cell_diff_max": 9.0, "cell_in_min": 2.0, "cell_in_max": 5.0,
    "srp_rec": 0.010, "srn_rec": 0.200,
    "rc": (500, 1000, 1000), "cc": (0.1e-6, 1e-6, 10e-6),
    "rf": (40, 100, 1000), "cf": (1e-6, 10e-6, 40e-6),
    "rfilt_min": 100,
    "vfeton_hi": (10.0, 12.0, 14.0),              # REGSRC >= 12 V
    "rdsg_off": (1750, 2500, 4250), "rchg_off": (750e3, 1e6, 1.25e6),
    "tdsg_off_10nF": 60e-6, "vchg_clamp": (18.0, 20.0, 22.0),
    "dsg_absmax": 20.0,
    "ocd_step": {0: 2.78e-3, 1: 5.56e-3}, "scd_step": {0: 11.1e-3, 1: 22.2e-3},
    "ocd_scale": 0.10, "ocd_offset": 2.5e-3,
    "adc_gain": 382e-6, "cell_acc_25C": 0.010,
    "regout": (3.20, 3.30, 3.40), "regout_10mA": 3.15, "regout_ilim": (0.030, 0.038, 0.045),
    "rbal": (1.0, 5.0, 10.0), "icb_max": 5e-3,
    "i_ship": (0.6e-6, 1.8e-6), "i_normal": (40e-6, 195e-6),
    "vboot": (0.3, 1.0), "ts1_pre_por_max": 5.0,
    "rts": (9.85e3, 10e3, 10.15e3),
    # Infineon IPT012N08N5
    "q_rds10": 1.2e-3, "q_rds6": 1.7e-3, "q_rthja": 40.0, "q_ciss": 13e-9, "q_ciss_max": 17e-9,
    # Vishay WSK2512 1 mOhm
    "rs": 1.0e-3, "rs_p": 1.0, "rs_tol": 0.01,
    # Nexperia 2N7002 (cascode)
    "qc_vth": (1.0, 2.0, 2.5), "qc_ptot": 0.83,
    # BZX84-C15 (CHG gate clamp) and BZX84-C18 (cascode gate), Philips/Nexperia BZX84 series
    "vz15": (13.8, 15.6), "vz18": (16.8, 19.1),
    # Littelfuse SMCJ26A
    "tvs_vr": 26.0, "tvs_vc": 42.1,
    # Omron B3U-1000P (distributor listing)
    "sw_rating": (0.05, 12.0),
}

ASSUME = {
    "rds_hot": 1.7,
    "regout_load": 10e-3,          # host MCU + pull-ups drawn from REGOUT
    "vgs_cascode": 2.5,            # 2N7002 VGS at ~10 mA (curve not read)
    "vz_low_current": (15.5, 19.1),  # BZX84-C18 at ~10 uA bias, below its 5 mA spec
    "l_load": 1e-6,
}


def h(t):
    print(f"\n## {t}")


def main():
    vmin, vnom, vmax = (CELLS * V_CELL[k] for k in ("min", "nom", "max"))

    h("Pack and groups")
    print(f"- 6S: {vmin:.1f} / {vnom:.1f} / {vmax:.1f} V (2.5 / 3.7 / 4.2 V per cell)")
    print(f"- BQ76930 6-cell map (datasheet Table 9-3): lower group cells on VC1-VC0, VC2-VC1, VC5-VC4 "
          f"(VC2=VC3=VC4 shorted); upper group on VC6-VC5B, VC7-VC6, VC10-VC9 (VC7=VC8=VC9 shorted)")
    for g in ("lower (VC5X-VSS)", "upper (BAT-VC5X)"):
        print(f"- {g}: 3 cells = {3*V_CELL['min']:.1f}-{3*V_CELL['max']:.1f} V vs recommended "
              f"{DS['grp_vmin']}-{DS['grp_vmax']} V per group: OK")
    print(f"- In-use cell differential {V_CELL['min']}-{V_CELL['max']} V vs recommended "
          f"{DS['cell_in_min']}-{DS['cell_in_max']} V, abs max {DS['cell_diff_max']} V")

    h("Current path")
    r_path = 2 * DS["q_rds10"] + DS["rs"]
    for i, tag in ((I_DSG_CONT, "continuous"), (OCD_TARGET, "OCD threshold")):
        pq = i ** 2 * DS["q_rds10"]
        print(f"- {i:.0f} A ({tag}): per FET {pq:.2f} W at RDS(on) max, {pq*ASSUME['rds_hot']:.2f} W hot "
              f"[ASSUMPTION x{ASSUME['rds_hot']}] -> +{pq*ASSUME['rds_hot']*DS['q_rthja']:.0f} K; "
              f"shunt {i**2*DS['rs']:.2f} W vs {DS['rs_p']} W")
    print(f"- Path FET + FET + shunt = {r_path*1e3:.1f} mOhm -> {r_path*I_DSG_CONT*1e3:.0f} mV at "
          f"{I_DSG_CONT:.0f} A (copper excluded)")
    print(f"- SRN at {I_DSG_CONT:.0f} A discharge: {I_DSG_CONT*DS['rs']*1e3:.0f} mV; at {I_CHG_MAX:.0f} A charge: "
          f"{-I_CHG_MAX*DS['rs']*1e3:.0f} mV (recommended +-{DS['srn_rec']*1e3:.0f} mV)")
    print(f"- Coulomb counter: 8.44 uV LSB / 1 mOhm = 8.44 mA; range +-200 mV = +-200 A")

    h("Current protection (host writes PROTECT1/PROTECT2)")
    print("  Code tables reconstructed from the datasheet range, step and its worked example "
          "(RSNS=1: SCD 0x03 = 111 mV, 0x04 = 133 mV; OCD 0x0A = 72 mV, 0x0B = 78 mV)")
    rsns = 0
    scd = [22.2e-3 + DS["scd_step"][rsns] * k for k in range(8)]
    ocd = [8.33e-3 + DS["ocd_step"][rsns] * k for k in range(16)]
    ks = min(range(8), key=lambda k: abs(scd[k] - SCD_TARGET * DS["rs"]) if scd[k] >= SCD_TARGET * DS["rs"] else 1)
    ko = min(range(16), key=lambda k: abs(ocd[k] - OCD_TARGET * DS["rs"]))
    for name, v, k in (("SCD", scd[ks], ks), ("OCD", ocd[ko], ko)):
        lo = (v * (1 - DS["ocd_scale"]) - DS["ocd_offset"]) / (DS["rs"] * (1 + DS["rs_tol"]))
        hi = (v * (1 + DS["ocd_scale"]) + DS["ocd_offset"]) / (DS["rs"] * (1 - DS["rs_tol"]))
        print(f"- {name}: RSNS=0 code {k} = {v*1e3:.1f} mV -> {v/DS['rs']:.1f} A nominal, {lo:.1f}-{hi:.1f} A "
              f"with +-10 % scale, +-2.5 mV offset, 1 % shunt")
    p1 = (rsns << 7) | (0x1 << 3) | ks
    p2 = (0x5 << 4) | ko
    print(f"- PROTECT1 = 0x{p1:02X} (RSNS=0, SCD delay 100 us = code 1, threshold code {ks})")
    print(f"- PROTECT2 = 0x{p2:02X} (OCD delay 320 ms = code 5, threshold code {ko})")
    print("  [CHECK] the datasheet example's text and its PROTECT2 value disagree by one threshold code; "
          "confirm the bit layout in the register map before writing")

    h("Voltage protection (host writes OV_TRIP/UV_TRIP/PROTECT3)")
    for name, target, top, low in (("OV", OV_TARGET, 0b10, 0b1000), ("UV", UV_TARGET, 0b01, 0b0000)):
        code = round(target / DS["adc_gain"])
        reg = (code >> 4) & 0xFF
        back = (top << 12) | (reg << 4) | low
        print(f"- {name} {target} V: ADC {code} (0x{code:04X}) -> {name}_TRIP = 0x{reg:02X} -> "
              f"actual {back*DS['adc_gain']:.3f} V (GAIN 382 uV/LSB, OFFSET 0 assumed; read ADCGAIN/ADCOFFSET)")
    print("- Datasheet check of the method: 4.30 V -> 0xBF and 2.5 V -> 0x99 as in its example: "
          f"{(round(4.30/DS['adc_gain'])>>4)&0xFF:#04x}, {(round(2.5/DS['adc_gain'])>>4)&0xFF:#04x}")
    print("- PROTECT3 = 0x50: OV delay 2 s, UV delay 4 s (datasheet example value)")
    print("- No hardware over-temperature or charge over-current: the host must do both from TS1 and CC")

    h("Cell input and supply filters")
    rc, cc = 1000, 1e-6
    print(f"- Rc {rc} Ohm (range {DS['rc'][0]}-{DS['rc'][2]}), Cc {cc*1e6:.0f} uF differential "
          f"(range 0.1-10 uF): tau {rc*cc*1e3:.1f} ms per side")
    rf, cf = 100, 10e-6
    print(f"- BAT and VC5X power filters: Rf {rf} Ohm, Cf {cf*1e6:.0f} uF (typ values) -> tau {rf*cf*1e3:.1f} ms")
    ibal = 3.7 / (2 * rc + DS["rbal"][1])
    ibal_max = V_CELL["max"] / (2 * rc + DS["rbal"][0])
    print(f"- Internal balancing through 2 x Rc: {ibal*1e3:.2f} mA at 3.7 V ({ibal_max*1e3:.2f} mA max at 4.2 V) "
          f"vs {DS['icb_max']*1e3:.0f} mA limit; ~{ibal*0.7*24*1e3:.0f} mAh/day at 70 % duty")
    print("- External balancing (recommended by TI for BQ76930) is NOT fitted: see README")
    print(f"- SRP/SRN filter: 100 Ohm + 100 Ohm, 100 nF differential -> tau {200*100e-9*1e6:.0f} us "
          f"(SCD delay options 70-400 us)")

    h("REGSRC cascode (2N7002 source follower) and REGOUT")
    rbias = 1e6
    for vp in (vmin, vnom, vmax):
        vz = min(vp - 0.0, ASSUME["vz_low_current"][1])
        vz_lo = min(vp, ASSUME["vz_low_current"][0])
        reg_lo, reg_hi = vz_lo - ASSUME["vgs_cascode"], vz - DS["qc_vth"][0]
        iq = ASSUME["regout_load"] + DS["i_normal"][1]
        print(f"- Pack {vp:.1f} V: gate {vz_lo:.1f}-{vz:.1f} V -> REGSRC ~{reg_lo:.1f}-{reg_hi:.1f} V "
              f"[ASSUMPTION zener at ~10 uA, VGS ~2.5 V]; 2N7002 {(vp-reg_lo)*iq*1e3:.0f} mW at "
              f"{iq*1e3:.1f} mA (Ptot {DS['qc_ptot']} W at Tsp 25 C)")
    print(f"- Bias: (25.2 - 17) V / 1 MOhm = {(vmax-17)/rbias*1e6:.0f} uA, also drawn in SHIP mode")
    print(f"- VFETON is 10-14 V when REGSRC >= 12 V (otherwise REGSRC-2 V to REGSRC). The BZX84-C18 keeps "
          f"REGSRC at or above about 12 V down to a 15 V pack (sim: 12.1 V), so the FETs see >= 10 V gate drive")
    print(f"- REGOUT 3.3 V version: {DS['regout'][0]}-{DS['regout'][2]} V unloaded, >= {DS['regout_10mA']} V "
          f"at 10 mA; current limit {DS['regout_ilim'][0]*1e3:.0f}-{DS['regout_ilim'][2]*1e3:.0f} mA. "
          f"Host budget {ASSUME['regout_load']*1e3:.0f} mA [ASSUMPTION]")

    h("FET drive")
    for name, c in (("typ", DS["q_ciss"]), ("max", DS["q_ciss_max"])):
        print(f"- DSG turn-off: (2.5k internal + 100 Ohm) x Ciss {c*1e9:.0f} nF = "
              f"{(DS['rdsg_off'][1]+100)*c*1e6:.0f} us ({name}); worst RDSG_OFF 4.25k: "
              f"{(DS['rdsg_off'][2]+100)*c*1e6:.0f} us")
    print(f"- CHG turn-off: the gate discharges through R14 100 kOhm to PACK- (D3 blocks the CHG pin): "
          f"tau {100e3*DS['q_ciss']*1e3:.1f}-{100e3*DS['q_ciss_max']*1e3:.1f} ms")
    for exc in (3.0, 7.2, 10.2):
        vgs = exc * 100e3 / (100e3 + DS["rchg_off"][0])
        print(f"- CHG disabled, charger {exc:.1f} V above the pack: PACK- sits {exc:.1f} V below VSS; the CHG pin's "
              f">= 750 kOhm pull-down and R14 100 kOhm divide it to VGS = {vgs:.2f} V (VGS(th) min 2.2 V)")
    print(f"- CHG gate clamp BZX84-C15 ({DS['vz15'][0]}-{DS['vz15'][1]} V) to PACK-: off at normal drive "
          f"({DS['vfeton_hi'][2]} V max - 0.6 V diode)")
    e_lin = 0.5 * vmax * SCD_TARGET * (DS["rdsg_off"][2] + 100) * DS["q_ciss_max"] * math.log(10 / 3)
    print(f"- SCD turn-off at {SCD_TARGET:.0f} A, 25.2 V: rough linear-mode energy 1/2 V I t over the "
          f"threshold crossing = {e_lin*1e3:.0f} mJ (hand estimate; ngspice gives 8 mJ at 71 A, 50 mJ at 243 A). SOA is a graph only")

    h("Pack-terminal transient")
    print(f"- SMCJ26A across PACK+/PACK-: VR {DS['tvs_vr']} V > {vmax:.1f} V; VC {DS['tvs_vc']} V at full Ipp vs "
          f"IPT012N08N5 80 V")
    print("- The BQ76930 is on the cell side; its pins see pack-terminal transients only through the FETs")

    h("Boot and thermistor")
    print(f"- Boot: SW1 connects cell 1+ (2.5-4.2 V) through 1 kOhm to TS1: above VBOOT max {DS['vboot'][1]} V, "
          f"below the 5 V pre-POR limit; {V_CELL['max']/1e3*1e3:.1f} mA through the switch "
          f"(B3U-1000P rated {DS['sw_rating'][0]*1e3:.0f} mA, {DS['sw_rating'][1]:.0f} V)")
    print(f"- TS1: 103AT NTC to VSS against the internal {DS['rts'][1]/1e3:.0f}k pull-up; TS2: fixed 10k to VC5X "
          f"(reads as 25 C; the host must ignore TS2)")

    h("Quiescent current")
    i_bias = (vmax - 17) / rbias
    print(f"- SHIP: IC {DS['i_ship'][0]*1e6:.1f}-{DS['i_ship'][1]*1e6:.1f} uA + cascode bias ~{i_bias*1e6:.0f} uA "
          f"-> {(DS['i_ship'][1]+i_bias)*24*1e3:.2f} mAh/day")
    print(f"- NORMAL: IC {DS['i_normal'][0]*1e6:.0f}-{DS['i_normal'][1]*1e6:.0f} uA + host load "
          f"(REGOUT, {ASSUME['regout_load']*1e3:.0f} mA budget)")


if __name__ == "__main__":
    main()
