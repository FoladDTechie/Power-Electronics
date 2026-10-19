#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Design calculations for the 4S/6S drone power board.

    python3 pdb_calc.py

Datasheet numbers live in DS with their source. Anything that is not from a
datasheet lives in ASSUME and is printed with [ASSUMPTION]. Change the design
inputs at the top and rerun.
"""
import math

# ---- design inputs ----------------------------------------------------------
PACKS = {"4S": (12.0, 14.8, 16.8), "6S": (18.0, 22.2, 25.2)}   # 3.0 / 3.7 / 4.2 V per cell
I_CONT, I_BURST = 30.0, 60.0          # set by the XT60 rating below
BEC = {
    "5V": {"vout": 5.0, "iout": 2.0, "l": 10e-6, "l_dcr": 0.02982, "l_isat": 7.6,
           "rtop": 53.6e3, "rbot": 10.2e3, "cout_n": 2, "cout_nom": 22e-6},
    "12V": {"vout": 12.0, "iout": 1.5, "l": 22e-6, "l_dcr": 0.0606, "l_isat": 5.6,
            "rtop": 140e3, "rbot": 10.0e3, "cout_n": 3, "cout_nom": 10e-6},
}

DS = {
    # AMASS XT60 datasheet V1.2
    "xt60_i": 30.0, "xt60_burst": 60.0, "xt60_rc": 0.55e-3,
    # Infineon IPT012N08N5 (two in parallel)
    "q_rds10": 1.2e-3, "q_rds6": 1.7e-3, "q_vth": (2.2, 3.0, 3.8), "q_vgs_max": 20.0,
    "q_qg": 178e-9, "q_ciss": 13e-9, "q_rthja": 40.0, "q_vds": 80.0,
    # Nexperia BUK7M42-60E (precharge switch)
    "qp_rds10": 42e-3, "qp_vth": (2.4, 3.0, 4.0), "qp_vgs_max": 20.0,
    # Nexperia BZX84-C12
    "vz": (11.4, 12.0, 12.7),
    # Vishay WSK2512, 0.5 mOhm
    "rs": 0.5e-3, "rs_tol": 0.01, "rs_p": 1.0, "rs_tcr": 350e-6,
    # TI INA226
    "ina_fs": 81.92e-3, "ina_lsb_shunt": 2.5e-6, "ina_vos": 10e-6, "ina_gain": 0.001,
    "ina_in_absmax": 40.0, "ina_in_op": 36.0, "ina_vbus_z": 830e3,
    # Littelfuse SMCJ26A
    "tvs_vr": 26.0, "tvs_vbr": (28.9, 31.9), "tvs_vc": 42.1, "tvs_ipp": 35.7,
    # TI TPS54360
    "vref": (0.792, 0.800, 0.808), "en": (1.1, 1.2, 1.3), "en_i1": 1.2e-6,
    "en_ihys": (2.2e-6, 3.4e-6, 4.5e-6), "en_absmax": 8.4, "vin_absmax": 65.0, "vin_op": 60.0,
    "ilim": (4.5, 5.5, 6.8), "rds_hs_max": 0.190, "ton_min": 135e-9,
    "gmps": 12.0, "gmea": 350e-6,
    # Vishay SS36
    "d_vf3a": 0.75, "d_rthja": 55.0,
    # Microchip MCP65R41T-1202E/CHY
    "cmp_vref": (1.185, 1.21, 1.234), "cmp_vos": 10e-3, "cmp_iin_max": 2e-3, "cmp_ref_i": 500e-6,
    # Same Sky CMI-1295IC-0585T
    "buz_v": (4.0, 5.0, 7.0), "buz_i": 30e-3,
    # Nexperia 2N7002 (RDS(on) max at VGS 4.5 V)
    "qb_rds": 5.3,
    # Littelfuse 466 3 A
    "fuse_i": 3.0, "fuse_derate": 0.75 * 0.8, "fuse_v": 32.0,
}

ASSUME = {
    "c_load": 2200e-6,     # 2 x 470 uF on board + ~4 x 330 uF in the ESCs
    "i_esc_idle": 0.2,     # all ESCs together, before arming
    "rds_hot": 1.7,        # RDS(on) multiplier at Tj ~100 C (curve not read)
    "eta": 0.88,           # BEC efficiency for input-current estimates
    "mlcc_5v": 0.70,       # 22 uF 16 V 1210 X7R retained at 5 V bias
    "mlcc_12v": 0.75,      # 10 uF 50 V 1210 X7R retained at 12 V bias
    "esr_mlcc": 3e-3,
    "c_en_eff": 0.9,       # 22 uF 16 V X7R at ~3 V bias
}


def e96(x):
    base = [100, 102, 105, 107, 110, 113, 115, 118, 121, 124, 127, 130, 133, 137, 140, 143, 147, 150,
            154, 158, 162, 165, 169, 174, 178, 182, 187, 191, 196, 200, 205, 210, 215, 221, 226, 232,
            237, 243, 249, 255, 261, 267, 274, 280, 287, 294, 301, 309, 316, 324, 332, 340, 348, 357,
            365, 374, 383, 392, 402, 412, 422, 432, 442, 453, 464, 475, 487, 499, 511, 523, 536, 549,
            562, 576, 590, 604, 619, 634, 649, 665, 681, 698, 715, 732, 750, 768, 787, 806, 825, 845,
            866, 887, 909, 931, 953, 976]
    d = 10 ** math.floor(math.log10(x) - 2)
    return min((b * d for b in base + [1000]), key=lambda v: abs(v - x))


def par(*r):
    return 1 / sum(1 / x for x in r)


def h(t):
    print(f"\n## {t}")


def main():
    vmax = PACKS["6S"][2]

    h("Main current path")
    print(f"- XT60: {DS['xt60_i']:.0f} A continuous, {DS['xt60_burst']:.0f} A burst, contact "
          f"{DS['xt60_rc']*1e3:.2f} mOhm -> design target {I_CONT:.0f} A / {I_BURST:.0f} A")
    rq = DS["q_rds10"] / 2
    for i, tag in ((I_CONT, "continuous"), (I_BURST, "burst")):
        p25 = i ** 2 * rq
        ph = p25 * ASSUME["rds_hot"]
        print(f"- 2 x IPT012N08N5 at {i:.0f} A ({tag}): {p25:.2f} W at RDS(on) max 25 C, "
              f"{ph:.2f} W with x{ASSUME['rds_hot']} hot [ASSUMPTION]; per FET {ph/2:.2f} W -> "
              f"+{ph/2*DS['q_rthja']:.0f} K at RthJA {DS['q_rthja']:.0f} K/W (6 cm2 copper)")
    for i in (I_CONT, I_BURST):
        print(f"- Shunt 0.5 mOhm at {i:.0f} A: {i**2*DS['rs']:.2f} W vs {DS['rs_p']:.1f} W rating "
              f"(continuous limit from P: {math.sqrt(DS['rs_p']/DS['rs']):.1f} A)")
    rpath = 2 * DS["xt60_rc"] + DS["rs"] + rq
    print(f"- Board path without copper: {rpath*1e3:.2f} mOhm -> {rpath*I_CONT*1e3:.0f} mV drop at "
          f"{I_CONT:.0f} A (PCB copper not included)")

    h("INA226 scaling")
    fs = DS["ina_fs"] / DS["rs"]
    i_lsb = 2e-3
    cal = 0.00512 / (i_lsb * DS["rs"])
    print(f"- Shunt full scale {DS['ina_fs']*1e3:.2f} mV / {DS['rs']*1e3:.1f} mOhm = {fs:.1f} A; "
          f"shunt LSB {DS['ina_lsb_shunt']/DS['rs']*1e3:.0f} mA")
    print(f"- Current_LSB = 2 mA -> CAL = 0.00512 / (2 mA x 0.5 mOhm) = {cal:.0f} (0x{int(cal):04X}); "
          f"register limit {2**15*i_lsb:.1f} A; power LSB {25*i_lsb*1e3:.0f} mW")
    print(f"- Offset {DS['ina_vos']*1e6:.0f} uV max = {DS['ina_vos']/DS['rs']*1e3:.0f} mA; gain "
          f"{DS['ina_gain']*100:.1f} % + shunt {DS['rs_tol']*100:.0f} % + TCR "
          f"{DS['rs_tcr']*1e6:.0f} ppm/K (x 50 K self-heating = {DS['rs_tcr']*50*100:.2f} %) [ASSUMPTION 50 K]")
    print(f"- At 30 A: worst case about +-{(DS['ina_gain']+DS['rs_tol']+DS['rs_tcr']*50)*30+0.02:.2f} A")
    print(f"- INA226 is powered from the flight controller's 3.3 V: SDA/SCL VIH = 0.7 x VS, so a 5 V "
          f"supply would not accept 3.3 V logic")

    h("Anti-spark: gate supply")
    r_sup = 22e3
    for v in (PACKS["4S"][0], PACKS["4S"][2], vmax):
        if v <= DS["vz"][0]:
            state = "zener not conducting, gate node follows VBAT (R_SUP only charges the gate network)"
        else:
            state = f"zener current up to {(v - DS['vz'][0]) / r_sup * 1e3:.2f} mA"
        print(f"- VBAT {v:4.1f} V: {state}; DISARM short draws {v/r_sup*1e3:.2f} mA, "
              f"{v**2/r_sup*1e3:.0f} mW in R_SUP")
    print(f"- Gate node <= {DS['vz'][2]} V (BZX84-C12 max at 5 mA) vs VGS max {DS['q_vgs_max']:.0f} V. "
          f"[ASSUMPTION] at 0.1-0.6 mA the zener sits a little below its 5 mA value")
    print(f"- Disarmed but plugged in: {vmax/r_sup*1e3:.2f} mA at 25.2 V = {vmax/r_sup*24*1e3:.0f} mAh/day")

    h("Anti-spark: precharge")
    rpre, c = 10.0, ASSUME["c_load"]
    tau = rpre * c
    print(f"- R_PRE = 2S2P of 10 Ohm CRGP2512 = {rpre:.0f} Ohm; C_LOAD {c*1e6:.0f} uF [ASSUMPTION] -> "
          f"tau {tau*1e3:.0f} ms, 99 % at {4.6*tau*1e3:.0f} ms")
    e = 0.5 * c * vmax ** 2
    print(f"- At {vmax} V: peak {vmax/rpre:.2f} A, peak power {vmax**2/rpre:.1f} W "
          f"({vmax**2/rpre/4:.1f} W per resistor), energy {e:.2f} J ({e/4:.3f} J per resistor)")
    print(f"- CRGP2512 has a pulse graph only (2 W, 500 V); 0.18 J in ~{tau*1e3:.0f} ms is NOT checked against it")
    print(f"- ESC idle {ASSUME['i_esc_idle']} A [ASSUMPTION] leaves {ASSUME['i_esc_idle']*rpre:.1f} V across "
          f"R_PRE when the main FETs close")
    print(f"- Without precharge the plug-in current is limited only by lead and capacitor impedance "
          f"(see sim/results.txt)")

    h("Anti-spark: main FET delay")
    rg, cg = 1e6, 1e-6
    ceff = cg + 2 * DS["q_qg"] / 10.0
    for name, rr, cc, vz, vth in (("nominal", rg, ceff, DS["vz"][1], DS["q_vth"][1]),
                                  ("earliest", rg * 0.99, (cg * 0.9 + 2 * DS["q_ciss"]), DS["vz"][2], DS["q_vth"][0]),
                                  ("latest", rg * 1.01, cg * 1.1 + 2 * DS["q_qg"] / 10, DS["vz"][0], DS["q_vth"][2])):
        t = rr * cc
        t_th = t * math.log(vz / (vz - vth))
        t_10 = t * math.log(vz / (vz - 10.0))
        print(f"- {name:8s}: tau {t:.2f} s, VGS reaches VTH {vth} V at {t_th*1e3:.0f} ms, 10 V at {t_10:.2f} s")
    print(f"- Precharge 99 % ({4.6*tau*1e3:.0f} ms) comes before the earliest VTH crossing")
    print(f"- The BECs must not start before the latest VTH crossing, or their load lands on R_PRE:"
          f" see the EN delay below (C_EN -10 % included there)")
    print(f"- Turn-off on DISARM: 1 uF through 100 Ohm + 1N4148W -> tau 0.1 ms; peak "
          f"{DS['vz'][2]/100*1e3:.0f} mA (1N4148W IFSM 500 mA)")
    print(f"- Disarming under load would run the FETs through their linear region for ~0.1 ms: "
          f"only disarm with motors stopped")

    h("Transient clamp vs ratings")
    print(f"- SMCJ26A: VR {DS['tvs_vr']} V > {vmax} V; VBR {DS['tvs_vbr'][0]}-{DS['tvs_vbr'][1]} V at 1 mA; "
          f"VC {DS['tvs_vc']} V at {DS['tvs_ipp']} A")
    for part, lim in (("TPS54360 VIN abs max", DS["vin_absmax"]), ("IPT012N08N5 VDS", DS["q_vds"]),
                      ("BUK7M42-60E VDS", 60.0), ("INA226 IN+/IN-/VBUS abs max", DS["ina_in_absmax"]),
                      ("Panasonic FR 50 V bulk", 50.0), ("MLCC 50 V", 50.0)):
        ok = "OK" if DS["tvs_vc"] < lim else "EXCEEDED at full Ipp"
        print(f"    {part:28s} {lim:5.1f} V  {ok}")
    print(f"- Littelfuse 466 is a {DS['fuse_v']:.0f} V fuse: OK at 25.2 V, but its breaking rating does not "
          f"cover a fault during a clamp event")

    h("BEC enable (TPS54360 EN): UVLO and start-up delay")
    v_start, v_stop = 10.0, 9.0
    r1 = e96((v_start - v_stop) / DS["en_ihys"][1])
    r2 = e96(r1 * DS["en"][1] / (v_stop - DS["en"][1] + r1 * (DS["en_i1"] + DS["en_ihys"][1])))
    print(f"- Target start {v_start} V / stop {v_stop} V -> RUVLO1 {r1/1e3:.0f}k, RUVLO2 {r2/1e3:.1f}k")

    def thr(ven, ihys, rise):
        i = DS["en_i1"] + (0 if rise else ihys)
        return ven + r1 * (ven / r2 - i)

    lo = min(thr(DS["en"][0], DS["en_ihys"][2], True), thr(DS["en"][0], DS["en_ihys"][0], True))
    hi = max(thr(DS["en"][2], DS["en_ihys"][0], True), thr(DS["en"][2], DS["en_ihys"][2], True))
    flo = thr(DS["en"][0], DS["en_ihys"][2], False)
    fhi = thr(DS["en"][2], DS["en_ihys"][0], False)
    print(f"- Start {thr(1.2, 3.4e-6, True):.2f} V (range {lo:.2f}-{hi:.2f} V), stop "
          f"{thr(1.2, 3.4e-6, False):.2f} V (range {flo:.2f}-{fhi:.2f} V); I1 is typical only")
    cen = 2 * 22e-6 * ASSUME["c_en_eff"]
    rth = par(r1, r2)
    for v in (PACKS["4S"][0], PACKS["4S"][1], PACKS["4S"][2], PACKS["6S"][1], vmax, DS["tvs_vc"]):
        vth = v * r2 / (r1 + r2) + DS["en_i1"] * rth
        if vth > DS["en"][1]:
            t = rth * cen * math.log(vth / (vth - DS["en"][1]))
            ts = f"enables after {t*1e3:.0f} ms ({t*0.9*1e3:.0f} ms with C_EN -10 %)"
        else:
            ts = "stays off"
        print(f"- VIN {v:4.1f} V: EN settles at {vth:.2f} V (abs max {DS['en_absmax']} V), {ts} "
              f"(C_EN 2 x 22 uF x {ASSUME['c_en_eff']} [ASSUMPTION])")

    h("BEC power stages (TPS54360, f = 600 kHz)")
    rt = 162e3
    print(f"- RT 162k: Eq. 7 gives {92417*(rt/1e3)**-0.991:.0f} kHz; datasheet example 162k = 600 kHz")
    f = 600e3
    for name, b in BEC.items():
        vo, io, l = b["vout"], b["iout"], b["l"]
        vout = [DS["vref"][k] * (1 + b["rtop"] / b["rbot"]) for k in range(3)]
        print(f"\n### {name} BEC: {vo} V / {io} A")
        print(f"- FB {b['rtop']/1e3:.1f}k / {b['rbot']/1e3:.1f}k -> {vout[1]:.3f} V "
              f"({vout[0]*(1-0.02/1.0):.2f}-{vout[2]*(1+0.02):.2f} V with VREF +-1 % and 1 % resistors)")
        lmin = vo * (vmax - vo) / (io * 0.3 * vmax * f)
        print(f"- Eq. 28 L(min) at KIND 0.3, VIN {vmax} V: {lmin*1e6:.1f} uH -> {l*1e6:.0f} uH XAL6060")
        for v in (PACKS["4S"][0], PACKS["4S"][2], vmax):
            if v < vo + 0.5:
                print(f"    VIN {v:4.1f} V: below regulation, output follows VIN (dropout)")
                continue
            d = vo / v
            ripple = vo * (v - vo) / (v * l * f)
            ripple_w = vo * (v - vo) / (v * l * 0.8 * f)
            print(f"    VIN {v:4.1f} V: D {d:.2f}, on-time {d/f*1e9:.0f} ns, ripple {ripple:.2f} A "
                  f"({ripple_w:.2f} A at L -20 %), peak {io+ripple_w/2:.2f} A; diode avg "
                  f"{io*(1-d):.2f} A -> <= {io*(1-d)*DS['d_vf3a']:.2f} W (VF 0.75 V bound)")
        ton = vo / (DS["tvs_vc"] * f)
        print(f"- On-time at the TVS clamp {DS['tvs_vc']} V: {ton*1e9:.0f} ns vs min {DS['ton_min']*1e9:.0f} ns typ")
        print(f"- Inductor Isat {b['l_isat']} A (30 % drop) vs current limit {DS['ilim'][0]}-{DS['ilim'][2]} A; "
              f"DCR loss {io**2*b['l_dcr']*1e3:.0f} mW")
        k = ASSUME["mlcc_5v"] if vo < 10 else ASSUME["mlcc_12v"]
        cout = b["cout_n"] * b["cout_nom"] * k
        esr = ASSUME["esr_mlcc"] / b["cout_n"]
        ripple = vo * (vmax - vo) / (vmax * l * f)
        vr = ripple / (8 * f * cout) + ripple * esr
        print(f"- Cout {b['cout_n']} x {b['cout_nom']*1e6:.0f} uF -> {cout*1e6:.1f} uF effective [ASSUMPTION]; "
              f"ripple ~{vr*1e3:.1f} mV p-p at {vmax} V")
        print(f"- Eq. 32 for a {io/2:.2f} A step and 4 % dip: Cout >= {2*(io/2)/(f*0.04*vo)*1e6:.1f} uF")
        fp = io / (2 * math.pi * vo * cout)
        fz = 1 / (2 * math.pi * esr * cout)
        fco = min(math.sqrt(fp * fz), math.sqrt(fp * f / 2))
        r4 = 2 * math.pi * cout * vo * fco / (DS["gmps"] * DS["vref"][1] * DS["gmea"])
        r4s = e96(r4)
        c5 = 1 / (2 * math.pi * r4s * fp)
        c8 = max(1 / (math.pi * r4s * f), cout * esr / r4s)
        print(f"- Compensation (Eq. 44-51): fp {fp:.0f} Hz, fz {fz/1e3:.0f} kHz, fco {fco/1e3:.1f} kHz; "
              f"R4 {r4/1e3:.2f}k -> {r4s/1e3:.2f}k, C5 {c5*1e9:.1f} nF, C8 {c8*1e12:.0f} pF")
        if vo > 10:
            vmin = vo + io * (DS["rds_hs_max"] + b["l_dcr"])
            print(f"- Dropout: needs VIN >= ~{vmin:.2f} V at {io} A [ASSUMPTION near-100 % duty, "
                  f"datasheet gives no max duty]; on 4S that is {vmin/4:.2f} V per cell")
        pin = vo * io / ASSUME["eta"]
        print(f"- Input current at full load: {pin/PACKS['4S'][0]:.2f} A at 12.0 V, {pin/vmax:.2f} A at "
              f"{vmax} V [ASSUMPTION eta {ASSUME['eta']}]; 466 3 A fuse derated to "
              f"{DS['fuse_i']*DS['fuse_derate']:.1f} A at 70 C")

    h("Low-voltage alarm (MCP65R41, VREF 1.21 V)")
    rtop, rbot, rx, rh1, rh2, vdd = 2.0e6, 187e3, 340e3, 10e3, 1.0e6, 5.0
    for tag, rb in (("4S (JP1 open)", rbot), ("6S (JP1 closed)", par(rbot, rx))):
        res = {}
        for corner in ("nom", "lo", "hi"):
            vr = {"nom": DS["cmp_vref"][1], "lo": DS["cmp_vref"][0], "hi": DS["cmp_vref"][2]}[corner]
            vos = {"nom": 0, "lo": -DS["cmp_vos"], "hi": DS["cmp_vos"]}[corner]
            rt_ = rtop * {"nom": 1, "lo": 0.99, "hi": 1.01}[corner]
            rb_ = rb * {"nom": 1, "lo": 1.01, "hi": 0.99}[corner]
            v_low = vr * rh2 / (rh1 + rh2) + vos
            v_high = (vr * rh2 + vdd * rh1) / (rh1 + rh2) + vos
            res[corner] = (v_low * (1 + rt_ / rb_), v_high * (1 + rt_ / rb_))
        cells = 4 if tag.startswith("4") else 6
        on, off = res["nom"]
        print(f"- {tag}: alarm ON below {on:.2f} V ({on/cells:.2f} V/cell, worst case "
              f"{res['lo'][0]:.2f}-{res['hi'][0]:.2f} V), OFF above {off:.2f} V ({off/cells:.2f} V/cell)")
        print(f"    filter: 1 uF x {par(rtop, rb)/1e3:.0f}k = {par(rtop, rb)*1e-6*1e3:.0f} ms")
    print(f"- With the 5 V rail off and 25.2 V on the bus, VIN- input current = "
          f"{(25.2-0.3)/rtop*1e6:.1f} uA vs {DS['cmp_iin_max']*1e3:.0f} mA abs max input current")
    print(f"- VREF load {(1.21)/(rh1+rh2)*1e6:.1f} uA vs +-{DS['cmp_ref_i']*1e6:.0f} uA; no capacitor on VREF "
          f"(datasheet: > 2000 pF may oscillate)")
    vb = vdd - DS["buz_i"] * DS["qb_rds"]
    print(f"- Buzzer: {DS['buz_i']*1e3:.0f} mA through 2N7002 ({DS['qb_rds']} Ohm max at 4.5 V) -> "
          f"{vb:.2f} V across it (operating {DS['buz_v'][0]}-{DS['buz_v'][2]} V)")

    h("Quiescent drain")
    i_arm = (vmax - DS["vz"][1]) / r_sup + vmax / (rtop + rbot) + vmax / DS["ina_vbus_z"] + 2 * vmax / (r1 + r2)
    print(f"- Armed, before BEC load, at {vmax} V: about {i_arm*1e3:.2f} mA from dividers and gate supply, "
          f"plus BEC no-load current (not computed)")


if __name__ == "__main__":
    main()
