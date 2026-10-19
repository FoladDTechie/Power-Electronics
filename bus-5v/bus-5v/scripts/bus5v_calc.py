#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Design calculations for the 5 V bus reference design.

Variant A: 9-24 V in -> fuse -> reverse P-FET -> TVS -> LMR33630A buck -> 5 V
Variant B: 1S Li-ion -> fuse -> reverse P-FET -> TVS -> MT3608 boost -> 5 V

Every datasheet number is in DS with its source; anything else is in
ASSUME and is labelled [ASSUMPTION] in the output. Run:
    python3 bus5v_calc.py
"""
import math

DS = {
    # TI LMR33630 SNVSAN3F (Nov 2020)
    "lmr_vfb": (0.985, 1.000, 1.015),
    "lmr_fsw_A": (340e3, 400e3, 460e3),
    "lmr_ihs_lim_min": 3.85, "lmr_ihs_lim_max": 5.05,     # high-side peak limit
    "lmr_ils_lim_min": 2.90,                              # low-side valley limit
    "lmr_rds_hs_max": 0.160, "lmr_rds_ls_max": 0.110,     # DDA package
    "lmr_ton_min": 108e-9,  "lmr_toff_min": 85e-9,        # larger of the two listed values
    "lmr_en_rise": (1.200, 1.231, 1.260), "lmr_en_hyst": 0.100,
    "lmr_vin_absmax": 38.0, "lmr_vin_max_op": 36.0,
    "lmr_pg_vol_max_at_50uA": 0.2,
    # Aerosemi MT3608 V1.0
    "mt_vfb": (0.588, 0.600, 0.612),
    "mt_fsw_typ": 1.2e6,       # typical only, no min/max given
    "mt_ilim_typ": 4.0,        # typical only
    "mt_isw_peak_absmax": 4.0,
    "mt_dmax_typ": 0.90,
    "mt_vin_absmax": 26.0,
    "mt_uvlo_typ": 1.98,
    # Coilcraft XAL6060-103 (doc 887-1): 10 uH +-20 %, DCR max, Isat (30 % drop, typ)
    "l_a": 10e-6, "l_a_tol": 0.20, "l_a_dcr_max": 0.02982, "l_a_isat": 7.6, "l_a_irms20": 5.0,
    # Coilcraft XAL5030-472 (doc 908-1)
    "l_b": 4.7e-6, "l_b_tol": 0.20, "l_b_dcr_max": 0.040, "l_b_isat": 6.7, "l_b_irms20": 4.3,
    # Vishay SiS443DN (63253 rev C): RDS(on) max at -4.5 V and -10 V
    "q_a_rds_4v5": 0.0160, "q_a_rds_10v": 0.0117, "q_a_vgs_max": 20.0, "q_a_vds": 40.0,
    # AOS AON6411 rev 1.1: RDS(on) max at -2.5 V, VGS(th) max
    "q_b_rds_2v5": 0.0036, "q_b_vth_max": 1.3, "q_b_vgs_max": 12.0, "q_b_vds": 20.0,
    # Nexperia BZX84-C12: VZ at 5 mA
    "vz": (11.40, 12.70),
    # Vishay SS34: VF max at 3 A, 25 C
    "ss34_vf_3A": 0.50,
    # Littelfuse 466 series (rev 12/19/13)
    "fuse_derate_cont": 0.75, "fuse_derate_70C": 0.80,   # 0.75 x 0.80 at 70 C (datasheet example)
    "fuse_3A_i2t": 0.5760, "fuse_4A_i2t": 1.024, "fuse_interrupt_A": 50.0, "fuse_vmax_3A_4A": 32.0,
    # Littelfuse SMAJ series (BA.10/21/20)
    "smaj24_vr": 24.0, "smaj24_vc": 38.9,
    "smaj85_vr": 8.5, "smaj85_vc": 14.4, "smaj85_ir": 20e-6,
    "smaj50_ir": 800e-6,
}

ASSUME = {
    "eta_a": 0.85,          # buck efficiency for input-current sizing (datasheet: curves only)
    "eta_b": 0.85,          # boost efficiency incl. SS34 drop (datasheet: curves only)
    "iout_a": 2.5,          # continuous rating chosen for margin to the 3.85 A min peak limit
    "iout_b": 1.0,
    "vbat_min": 3.0, "vbat_max": 4.2,
    "c_out_a_eff": 70e-6,   # 4 x 22 uF 16 V X7R after DC-bias derating at 5 V (not read from Murata)
    "c_out_b_eff": 35e-6,   # 2 x 22 uF at 5 V, same caveat
}


def line(s=""):
    print(s)


def buck():
    line("## Variant A: LMR33630A buck, 9-24 V -> 5 V")
    rt, rb = 100e3, 24.9e3
    vo = [v * (1 + rt / rb) for v in DS["lmr_vfb"]]
    # resistor tolerance 1 % on both, worst case
    vo_lo = DS["lmr_vfb"][0] * (1 + rt * 0.99 / (rb * 1.01))
    vo_hi = DS["lmr_vfb"][2] * (1 + rt * 1.01 / (rb * 0.99))
    line(f"- Feedback 100k / 24.9k: Vout typ {vo[1]:.3f} V; worst case (VFB +-1.5 %, R +-1 %) "
         f"{vo_lo:.3f}-{vo_hi:.3f} V")
    io = ASSUME["iout_a"]
    for vin in (9.0, 12.0, 24.0):
        d = 5.0 / vin
        for f, lt, tag in ((DS["lmr_fsw_A"][1], DS["l_a"], "typ"),
                           (DS["lmr_fsw_A"][0], DS["l_a"] * (1 - DS["l_a_tol"]), "worst")):
            di = (vin - 5.0) * d / (lt * f)
            pk = io + di / 2
            vl = io - di / 2
            if tag == "worst":
                line(f"- Vin {vin:4.1f} V: D = {d:.3f}, ton = {d/f*1e9:.0f} ns, toff = {(1-d)/f*1e9:.0f} ns; "
                     f"ripple {di:.2f} A (L-20 %, f min) -> peak {pk:.2f} A, valley {vl:.2f} A")
    line(f"  High-side limit min {DS['lmr_ihs_lim_min']} A; min on-time {DS['lmr_ton_min']*1e9:.0f} ns, "
         f"min off-time {DS['lmr_toff_min']*1e9:.0f} ns")
    line(f"- Inductor XAL6060-103: Isat {DS['l_a_isat']} A (30 % drop, typ) vs current-limit max "
         f"{DS['lmr_ihs_lim_max']} A; DCR loss at {io} A = {io**2*DS['l_a_dcr_max']*1e3:.0f} mW")
    # conduction loss of the IC at 24 V and 9 V
    for vin in (9.0, 24.0):
        d = 5.0 / vin
        pc = io**2 * (DS["lmr_rds_hs_max"] * d + DS["lmr_rds_ls_max"] * (1 - d))
        line(f"- IC conduction loss at {vin:.0f} V, {io} A (RDS max): {pc:.2f} W "
             f"(switching loss not included; datasheet gives curves only)")
    di_w = (24 - 5) * (5 / 24) / (DS["l_a"] * 0.8 * DS["lmr_fsw_A"][0])
    dv = di_w / (8 * DS["lmr_fsw_A"][0] * ASSUME["c_out_a_eff"])
    line(f"- Output ripple (capacitive term, 24 V worst ripple, Ceff {ASSUME['c_out_a_eff']*1e6:.0f} uF "
         f"[ASSUMPTION]): {dv*1e3:.1f} mV")
    irms = io * 0.5
    line(f"- Input RMS ripple current, worst at D = 0.5: {irms:.2f} A")
    # UVLO
    ru, rl = 100e3, 18.2e3
    on = [v * (1 + ru / rl) for v in DS["lmr_en_rise"]]
    off = (DS["lmr_en_rise"][1] - DS["lmr_en_hyst"]) * (1 + ru / rl)
    line(f"- EN divider 100k / 18.2k: start {on[0]:.2f}-{on[2]:.2f} V (typ {on[1]:.2f}), stop typ {off:.2f} V; "
         f"EN at 24 V = {24*rl/(ru+rl):.2f} V")
    # input current and fuse
    pin = 5.0 * io / ASSUME["eta_a"]
    iin = pin / 9.0
    need = iin / (DS["fuse_derate_cont"] * DS["fuse_derate_70C"])
    line(f"- Input current at 9 V [ASSUMPTION eta {ASSUME['eta_a']}]: {iin:.2f} A -> fuse rating "
         f">= {need:.2f} A (0.75 x 0.80 derating at 70 C) -> 3 A fuse, 32 V")
    pq = iin**2 * DS["q_a_rds_4v5"]
    line(f"- Reverse FET SiS443DN loss at {iin:.2f} A: {pq*1e3:.0f} mW; |VGS| at 9 V = 9 V, "
         f"at 24 V clamped to {DS['vz'][0]}-{DS['vz'][1]} V by BZX84-C12 (VGS max {DS['q_a_vgs_max']} V)")
    line(f"- Zener current at 24 V: {(24-DS['vz'][0])/100e3*1e3:.2f} mA (through 100 k)")
    line(f"- TVS SMAJ24A: VR {DS['smaj24_vr']} V, VC {DS['smaj24_vc']} V at Ipp vs LMR33630 VIN abs max "
         f"{DS['lmr_vin_absmax']} V -> exceeds by {DS['smaj24_vc']-DS['lmr_vin_absmax']:.1f} V at full rated pulse")
    line(f"- PG pull-up 100 k from 5 V: {5/100e3*1e6:.0f} uA sink when low (VOL <= 0.2 V specified at 50 uA)")
    line()


def boost():
    line("## Variant B: MT3608 boost, 1S Li-ion (3.0-4.2 V) -> 5 V")
    r1, r2 = 73.2e3, 10.0e3
    vo = [v * (1 + r1 / r2) for v in DS["mt_vfb"]]
    vo_lo = DS["mt_vfb"][0] * (1 + r1 * 0.99 / (r2 * 1.01))
    vo_hi = DS["mt_vfb"][2] * (1 + r1 * 1.01 / (r2 * 0.99))
    line(f"- Feedback 73.2k / 10k: Vout typ {vo[1]:.3f} V; worst case (VFB +-2 %, R +-1 %) {vo_lo:.3f}-{vo_hi:.3f} V")
    io = ASSUME["iout_b"]
    vd = DS["ss34_vf_3A"]
    f = DS["mt_fsw_typ"]
    for vin in (ASSUME["vbat_min"], 3.7, ASSUME["vbat_max"]):
        d = 1 - vin / (5.0 + vd)
        iin = 5.0 * io / (ASSUME["eta_b"] * vin)
        di = vin * d / (DS["l_b"] * (1 - DS["l_b_tol"]) * f)
        pk = iin + di / 2
        line(f"- Vbat {vin:.1f} V: D = {d:.3f}, Iin [ASSUMPTION eta {ASSUME['eta_b']}] = {iin:.2f} A, "
             f"ripple {di:.2f} A (L-20 %), peak {pk:.2f} A")
    line(f"  vs MT3608 switch current limit {DS['mt_ilim_typ']} A typ (no minimum given) and "
         f"4 A peak abs max; inductor Isat {DS['l_b_isat']} A")
    iin = 5.0 * io / (ASSUME["eta_b"] * ASSUME["vbat_min"])
    line(f"- Diode SS34: average {io:.1f} A, peak {iin + 0.15:.1f} A; loss <= {vd*io:.2f} W "
         f"(VF <= 0.5 V bound from the 3 A point)")
    d = 1 - ASSUME["vbat_min"] / (5.0 + vd)
    dv = io * d / (f * ASSUME["c_out_b_eff"])
    line(f"- Output ripple (capacitive term) at 3.0 V, {io} A: {dv*1e3:.1f} mV "
         f"[ASSUMPTION Ceff {ASSUME['c_out_b_eff']*1e6:.0f} uF]")
    need = iin / (DS["fuse_derate_cont"] * DS["fuse_derate_70C"])
    line(f"- Battery current {iin:.2f} A -> fuse rating >= {need:.2f} A -> 4 A fuse, 32 V. "
         f"Interrupting rating {DS['fuse_interrupt_A']:.0f} A: a Li-ion cell short can exceed this")
    pq = iin**2 * DS["q_b_rds_2v5"]
    line(f"- Reverse FET AON6411 at |VGS| = Vbat >= 3.0 V (spec at 2.5 V): RDS <= {DS['q_b_rds_2v5']*1e3:.1f} mOhm, "
         f"loss {pq*1e3:.0f} mW")
    line(f"- TVS SMAJ8.5A: VR {DS['smaj85_vr']} V, IR <= {DS['smaj85_ir']*1e6:.0f} uA at VR "
         f"(SMAJ5.0A would be up to {DS['smaj50_ir']*1e6:.0f} uA); VC {DS['smaj85_vc']} V < MT3608 IN abs max "
         f"{DS['mt_vin_absmax']} V")
    line(f"- MT3608 UVLO {DS['mt_uvlo_typ']} V typ: it will run a cell far below a safe Li-ion cut-off; "
         f"the pack must have its own protection")
    line()


if __name__ == "__main__":
    buck()
    boost()
