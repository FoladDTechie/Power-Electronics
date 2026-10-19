#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Design calculations for the BQ24650 solar charger (1S Li-ion).

Change PANEL / BATTERY below for another panel or cell, then rerun:
    python3 charger_calc.py

Datasheet numbers are in DS with their source; anything else is in ASSUME
and is printed with [ASSUMPTION].
"""
import math

# ---- design inputs (edit these) -------------------------------------------
PANEL = {"voc_max": 22.0, "vmp": 18.0}       # 36-cell "12 V" panel [ASSUMPTION: your panel]
BATTERY = {"cells": 1, "v_target": 4.16, "i_chg": 2.0, "v_min": 3.0}

DS = {
    # TI BQ24650 SLUSA75B (Jan 2020)
    "vreg": 2.1, "vreg_tol": 0.005,           # 0-85 C
    "vfb_leak": 100e-9,
    "vsense_fs": 0.040, "vsense_tol": 0.03,
    "vsense_pre": 0.004, "vsense_term": 0.004, "pre_term_tol": 0.25,
    "vmpp": 1.2, "vmpp_tol": 0.006, "mpp_leak_max": 1e-6,   # leakage spec'd at 7 V only
    "fsw": (510e3, 600e3, 690e3),
    "ocp_sense": 0.080,
    "vref": 3.3,
    "ts_cold": 0.735, "ts_hot": 0.475, "ts_cutoff": 0.45,
    "vcc_absmax": 33.0, "vcc_max_op": 28.0, "ph_absmax": 36.0,
    "i_bat_sleep": 15e-6,
    "lc_f0": (12e3, 17e3),                    # target range quoted in sections 8.3.9 / 9.2.2.3
    "ripple_frac": (0.2, 0.4),
    # Nexperia BUK9M14-40E: RDS(on) max at VGS = 5 V, 25 C; VGS max DC
    "q_rds_5v": 0.014, "q_vgs_max": 10.0, "q_qg_5v": 11.3e-9,
    # Coilcraft XAL6060-103
    "l": 10e-6, "l_tol": 0.2, "l_dcr": 0.02982, "l_isat": 7.6,
    # Vishay SS34: VF max 0.5 V at 3 A
    "ss34_vf_3A": 0.5,
    # Littelfuse SMAJ24A
    "tvs_vr": 24.0, "tvs_vc": 38.9,
    # Vishay WSL1206: 0.25 W at 70 C
    "rsr_p": 0.25,
    # Semitec 103AT-2: R25 = 10 k, B25/85 = 3435 K (R-T table not read)
    "ntc_r25": 10e3, "ntc_b": 3435.0,
}

ASSUME = {
    "eta": 0.90,          # charger efficiency for input-current estimate (datasheet: curves only)
    "c_out_eff": 10e-6,   # 10 uF 50 V X7R at ~4 V bias: little derating assumed
    "t_cold": 0.0, "t_hot": 45.0,   # Li-ion charge window [ASSUMPTION: check your cell]
}


def ntc(t_c):
    t = t_c + 273.15
    return DS["ntc_r25"] * math.exp(DS["ntc_b"] * (1 / t - 1 / 298.15))


def ts_ratio(rt1, rt2, t_c):
    rp = 1 / (1 / rt2 + 1 / ntc(t_c))
    return rp / (rt1 + rp)


def main():
    print("## Charge voltage (VFB divider)")
    r_top, r_bot = 100e3, 102e3
    v = DS["vreg"] * (1 + r_top / r_bot)
    tol = 0.001
    lo = DS["vreg"] * (1 - DS["vreg_tol"]) * (1 + r_top * (1 - tol) / (r_bot * (1 + tol)))
    hi = DS["vreg"] * (1 + DS["vreg_tol"]) * (1 + r_top * (1 + tol) / (r_bot * (1 - tol)))
    rth = r_top * r_bot / (r_top + r_bot)
    dv_leak = DS["vfb_leak"] * rth * (1 + r_top / r_bot)
    print(f"- R_top {r_top/1e3:.0f}k / R_bot {r_bot/1e3:.0f}k (0.1 %): VBAT = {v:.3f} V; "
          f"worst case (VREG +-0.5 %, R +-0.1 %) {lo:.3f}-{hi:.3f} V; VFB leakage <= {dv_leak*1e3:.1f} mV more")
    print(f"- Highest possible charge voltage {hi + dv_leak:.3f} V (target: never above 4.20 V)")
    print(f"- Divider drain on the battery: {v/(r_top+r_bot)*1e6:.1f} uA, plus IC sleep current "
          f"{DS['i_bat_sleep']*1e6:.0f} uA (datasheet, single value)")
    print()

    print("## Charge current (sense resistor)")
    i = BATTERY["i_chg"]
    rsr = DS["vsense_fs"] / i
    print(f"- RSR = 40 mV / {i} A = {rsr*1e3:.0f} mOhm -> 20 mOhm WSL1206 (1 %)")
    print(f"- Fast charge {i:.2f} A +-3 % (plus 1 % resistor); precharge and termination "
          f"{DS['vsense_pre']/rsr:.2f} A +-25 %")
    print(f"- RSR dissipation {i**2*rsr*1e3:.0f} mW vs {DS['rsr_p']*1e3:.0f} mW rating; "
          f"cycle-by-cycle limit {DS['ocp_sense']/rsr:.1f} A")
    print()

    print("## MPP (input voltage regulation)")
    r3, r4 = 499e3, 36.0e3
    vin_reg = DS["vmpp"] * (1 + r3 / r4)
    vf = 0.4  # [ASSUMPTION] SS34 drop at ~0.5 A input, below the 0.5 V / 3 A max point
    print(f"- R3 499k / R4 36.0k: VCC-side regulation {vin_reg:.2f} V (+-0.6 % ref, +-1 % R -> "
          f"{vin_reg*(1-0.006-0.02):.2f}-{vin_reg*(1+0.006+0.02):.2f} V)")
    print(f"- Panel held at about {vin_reg + vf:.1f} V including the input Schottky [ASSUMPTION VF ~{vf} V] "
          f"vs panel Vmp {PANEL['vmp']} V [ASSUMPTION]")
    rth = r3 * r4 / (r3 + r4)
    print(f"- MPPSET leakage bound 1 uA (spec'd at 7 V) x {rth/1e3:.1f}k = {rth*1e-6*1e3:.1f} mV "
          f"-> up to {rth*1e-6*(1+r3/r4):.2f} V shift at the input (worst case, unverified at 1.2 V)")
    print()

    print("## Power stage")
    for vin in (vin_reg, PANEL["voc_max"]):
        for vbat in (BATTERY["v_min"], BATTERY["v_target"]):
            d = vbat / vin
            for f, lt, tag in ((DS["fsw"][1], DS["l"], "typ"), (DS["fsw"][0], DS["l"] * (1 - DS["l_tol"]), "worst")):
                dI = vin * d * (1 - d) / (f * lt)
                if tag == "worst":
                    print(f"- VIN {vin:5.2f} V, VBAT {vbat:.2f} V: D = {d:.3f}; ripple {dI:.2f} A "
                          f"({dI/i*100:.0f} % of {i} A; L -20 %, f min), peak {i + dI/2:.2f} A")
    print(f"- Inductor XAL6060-103: Isat {DS['l_isat']} A (30 % drop) vs cycle-by-cycle limit "
          f"{DS['ocp_sense']/rsr:.1f} A; DCR loss {i**2*DS['l_dcr']*1e3:.0f} mW")
    c = ASSUME["c_out_eff"]
    f0 = 1 / (2 * math.pi * math.sqrt(DS["l"] * c))
    print(f"- Output LC: L 10 uH, C {c*1e6:.0f} uF [ASSUMPTION effective] -> f0 = {f0/1e3:.1f} kHz "
          f"(datasheet target {DS['lc_f0'][0]/1e3:.0f}-{DS['lc_f0'][1]/1e3:.0f} kHz)")
    for lf in (0.8, 1.2):
        for cf in (0.8, 1.2):
            f = 1 / (2 * math.pi * math.sqrt(DS['l'] * lf * c * cf))
            print(f"    L x{lf}, C x{cf}: {f/1e3:.1f} kHz")
    d = BATTERY["v_target"] / vin_reg
    print(f"- Input RMS current {i*math.sqrt(d*(1-d)):.2f} A (D = {d:.3f})")
    pin = BATTERY["v_target"] * i / ASSUME["eta"]
    print(f"- Input current {pin/vin_reg:.2f} A at {vin_reg:.1f} V [ASSUMPTION eta {ASSUME['eta']}]; "
          f"SS34 loss <= {DS['ss34_vf_3A']*pin/vin_reg*1e3:.0f} mW")
    for name, dd in (("high-side", d), ("low-side", 1 - d)):
        print(f"- {name} FET conduction {i**2*DS['q_rds_5v']*dd*1e3:.0f} mW (RDS(on) max at VGS 5 V; "
              f"gate drive ~6 V from REGN, VGS max {DS['q_vgs_max']} V)")
    print(f"- Gate-drive power ~ 2 x Qg x 6 V x f = {2*DS['q_qg_5v']*6*DS['fsw'][1]*1e3:.0f} mW from REGN")
    print()

    print("## Input protection")
    print(f"- TVS SMAJ24A: VR {DS['tvs_vr']} V > Voc {PANEL['voc_max']} V; VC {DS['tvs_vc']} V at Ipp "
          f"vs BQ24650 VCC abs max {DS['vcc_absmax']} V and PH abs max {DS['ph_absmax']} V")
    print()

    print("## TS window (103AT, B-model)")
    rc, rh = ntc(ASSUME["t_cold"]), ntc(ASSUME["t_hot"])
    rc_ratio, rh_ratio = DS["ts_cold"], DS["ts_hot"]
    x = (1 / rh - 1 / rc) / (1 / rh_ratio - 1 / rc_ratio)
    y = (1 / rc_ratio - 1) * x - 1 / rc
    rt1, rt2 = 1 / x, 1 / y
    print(f"- NTC from B = {DS['ntc_b']:.0f} K: R(0 C) = {rc/1e3:.2f}k, R(45 C) = {rh/1e3:.2f}k")
    print(f"- Exact (B-model) RT1 = {rt1/1e3:.2f}k, RT2 = {rt2/1e3:.1f}k")

    def cross(a, b, target):
        lo, hi = -40.0, 100.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if ts_ratio(a, b, mid) > target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    for name, a, b in (("CHOSEN 4.32k / 20.5k (E96 nearest)", 4.32e3, 20.5e3),
                       ("TI example 5.23k / 30.1k", 5.23e3, 30.1e3)):
        print(f"- {name}: charging allowed {cross(a, b, DS['ts_cold']):.1f} C to "
              f"{cross(a, b, DS['ts_hot']):.1f} C, cut-off {cross(a, b, DS['ts_cutoff']):.1f} C")
    print("    T (C)   TS % of VREF (chosen)")
    for t in (-5, 0, 10, 25, 40, 45, 50, 55, 60):
        print(f"    {t:5d}   {ts_ratio(4.32e3, 20.5e3, t)*100:5.1f}")
    print("  [ASSUMPTION] B-parameter model with B25/85; the Semitec R-T table was not readable,")
    print("  so the real window can differ by a few degrees. Recompute with the table before use.")


if __name__ == "__main__":
    main()
