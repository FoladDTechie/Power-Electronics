#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Generate hardware/bus-5v.kicad_sch: a 5 V bus with two input variants
(9-24 V buck, 1S Li-ion boost) from stock KiCad 9 library symbols.

    python3 gen_schematic.py --symdir /usr/share/kicad/symbols
"""
import argparse
import os

import kicadgen as kg
from kicadgen import Q, Sheet

FP_R0603 = "Resistor_SMD:R_0603_1608Metric"
FP_C0603 = "Capacitor_SMD:C_0603_1608Metric"
FP_C1210 = "Capacitor_SMD:C_1210_3225Metric"
FP_TP = "TestPoint:TestPoint_Keystone_5000-5004_Miniature"
FP_TERM = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal"
FP_FUSE = "Fuse:Fuse_1206_3216Metric"
FP_PPAK = "Package_SO:Vishay_PowerPAK_1212-8_Single"

DS = {
    "lmr": "http://www.ti.com/lit/ds/symlink/lmr33630.pdf",
    "mt": "https://www.olimex.com/Products/Breadboarding/BB-PWR-3608/resources/MT3608.pdf",
    "sis443": "https://www.vishay.com/docs/63253/sis443dn.pdf",
    "aon6411": "http://www.aosmd.com/res/data_sheets/AON6411.pdf",
    "bzx84": "https://assets.nexperia.com/documents/data-sheet/BZX84_SER.pdf",
    "ss34": "https://www.vishay.com/docs/88751/ss32.pdf",
    "smaj": "https://4donline.ihs.com/images/VipMasterIC/IC/LFSI/LFSI-S-A0011271570/LFSI-S-A0011345017-1.pdf",
    "fuse": "https://4donline.ihs.com/images/VipMasterIC/IC/LFSI/LFSIS12645/LFSIS12645-1.pdf",
    "xal60": "https://www.coilcraft.com/pdfs/xal60xx.pdf",
    "xal50": "https://mfgdatasheets.nlight.net/Coilcraft%20XAL50xx%20Shielded%20Power%20Inductors.pdf",
    "rc": "https://www.yageogroup.com/component-documentation/download/specsheet/RC0805FR-0712KL",
}


def mfr(m, mpn, extra=None):
    d = {"Manufacturer": m, "MPN": mpn}
    d.update(extra or {})
    return d


def R(s, ref, x, y, val, mpn, rot=0, fp=FP_R0603, **kw):
    return s.part(ref, "Device:R", x, y, rot=rot, value=val, footprint=fp, datasheet=DS["rc"],
                  fields=mfr("Yageo", mpn, {"Tolerance": "1%"}), **kw)


def C(s, ref, x, y, val, m, mpn, fp, extra=None, lib="Device:C", **kw):
    return s.part(ref, lib, x, y, value=val, footprint=fp, fields=mfr(m, mpn, extra), **kw)


def TP(s, ref, net, x, y, mpn="5000"):
    return s.part(ref, "Connector:TestPoint", x, y, value=net, footprint=FP_TP,
                  fields=mfr("Keystone Electronics", mpn),
                  ref_at=(x + 1.27, y - 6.35), val_at=(x + 1.27, y - 3.81))


def stub(s, p, dx, dy, name, angle):
    end = (round(p[0] + dx, 2), round(p[1] + dy, 2))
    s.wire(p, end)
    s.label(name, end, angle)


def gnd(s, p):
    s.power("power:GND", *p)


def build(symdir):
    s = Sheet(symdir)

    # =================== VARIANT A: 9-24 V -> buck -> 5 V ===================
    YA = 50.8
    j1 = s.part("J1", "Connector:Screw_Terminal_01x02", 20.32, YA, mirror="y",
                value="VIN 9-24 V", footprint=FP_TERM, fields=mfr("Phoenix Contact", "1715721"),
                ref_at=(17.78, 44.45), val_at=(17.78, 46.99), just="")
    f1 = s.part("F1", "Device:Fuse", 35.56, YA, rot=90, value="3A 32V",
                footprint=FP_FUSE, datasheet=DS["fuse"],
                fields=mfr("Littelfuse", "0466003.NRHF", {"Type": "Very fast-acting, 1206"}),
                ref_at=(35.56, 46.99), val_at=(35.56, 54.61), just="")
    q1 = s.part("Q1", "Transistor_FET:SiS443DN", 55.88, YA + 2.54, rot=90,
                footprint=FP_PPAK, datasheet=DS["sis443"],
                fields=mfr("Vishay Siliconix", "SiS443DN-T1-GE3"),
                ref_at=(55.88, 43.18), val_at=(55.88, 45.72), just="")
    d3 = s.part("D3", "Diode:BZX84Cxx", 66.04, 54.61, rot=270, value="BZX84-C12",
                footprint="Package_TO_SOT_SMD:SOT-23", datasheet=DS["bzx84"],
                fields=mfr("Nexperia", "BZX84-C12,215"),
                ref_at=(67.31, 60.96), val_at=(67.31, 63.5))
    r3 = R(s, "R3", 55.88, 62.23, "100k", "RC0603FR-07100KL")
    d1 = s.part("D1", "Diode:SMAJ24A", 78.74, 54.61, rot=270,
                footprint="Diode_SMD:D_SMA", datasheet=DS["smaj"],
                fields=mfr("Littelfuse", "SMAJ24A"),
                ref_at=(80.01, 60.96), val_at=(80.01, 63.5))
    c1 = C(s, "C1", 93.98, 54.61, "47u", "Panasonic", "EEE-FK1H470P",
           "Capacitor_SMD:CP_Elec_6.3x7.7", {"Voltage": "50V", "Type": "Aluminium electrolytic"},
           lib="Device:C_Polarized")
    c2 = C(s, "C2", 104.14, 54.61, "10u", "Murata", "GRM32ER71H106KA12L", FP_C1210, {"Voltage": "50V", "Dielectric": "X7R"})
    c3 = C(s, "C3", 114.3, 54.61, "10u", "Murata", "GRM32ER71H106KA12L", FP_C1210, {"Voltage": "50V", "Dielectric": "X7R"})
    c4 = C(s, "C4", 124.46, 54.61, "220n", "Murata", "GRM188R71H224KAC4D", FP_C0603, {"Voltage": "50V", "Dielectric": "X7R"})
    UX = 154.94
    u1 = s.part("U1", "Regulator_Switching:LMR33630ADDA", UX, 55.88, value="LMR33630A",
                footprint="Package_SO:Texas_HSOP-8-1EP_3.9x4.9mm_P1.27mm_ThermalVias",
                datasheet=DS["lmr"], fields=mfr("Texas Instruments", "LMR33630ADDAR"),
                ref_at=(UX + 2.54, 69.85), val_at=(UX + 2.54, 72.39))
    c5 = C(s, "C5", UX - 13.97, 64.77, "1u", "Murata", "GRM188R71C105KA12D", FP_C0603, {"Voltage": "16V", "Dielectric": "X7R"},
           ref_at=(UX - 16.51, 66.04), val_at=(UX - 16.51, 68.58), just="right")
    c6 = C(s, "C6", UX + 15.24, 49.53, "100n", "Murata", "GRM188R71H104KA93D", FP_C0603, {"Voltage": "50V", "Dielectric": "X7R"})
    l1 = s.part("L1", "Device:L", UX + 27.94, 53.34, rot=90, value="10u",
                footprint="Inductor_SMD:L_Coilcraft_XAL6060-XXX", datasheet=DS["xal60"],
                fields=mfr("Coilcraft", "XAL6060-103MEC", {"Isat": "7.6A (30% drop)", "DCR_max": "29.8mOhm"}),
                ref_at=(UX + 27.94, 57.15), val_at=(UX + 27.94, 59.69), just="")
    couts = [C(s, f"C{n}", x, 57.15, "22u", "Murata", "GRM32ER71C226KE18L", FP_C1210,
               {"Voltage": "16V", "Dielectric": "X7R"}) for n, x in ((7, 195.58), (8, 205.74), (9, 215.9), (10, 226.06))]
    j2 = s.part("J2", "Connector:Screw_Terminal_01x02", 246.38, 53.34,
                value="5V_A out 2.5 A", footprint=FP_TERM, fields=mfr("Phoenix Contact", "1715721"),
                ref_at=(246.38, 59.69), val_at=(246.38, 62.23), just="")
    r4 = R(s, "R4", 256.54, 46.99, "100k", "RC0603FR-07100KL")
    r5 = R(s, "R5", 256.54, 62.23, "18.2k", "RC0603FR-0718K2L")
    r6 = R(s, "R6", 266.7, 46.99, "100k", "RC0603FR-07100KL")
    r7 = R(s, "R7", 266.7, 62.23, "24.9k", "RC0603FR-0724K9L")
    r8 = R(s, "R8", 276.86, 46.99, "100k", "RC0603FR-07100KL")

    tp1 = TP(s, "TP1", "VIN_A_P", 71.12, YA)
    tp2 = TP(s, "TP2", "SW_A", UX + 20.32, 53.34)
    tp3 = TP(s, "TP3", "5V_A", 233.68, 53.34)

    # ---- wiring A ----
    s.wire(j1["1"], f1["1"])
    s.label("VIN_A", j1["1"])
    s.wire(f1["2"], q1["5"])
    s.label("VIN_A_F", (40.64, YA))
    s.wire(j1["2"], (27.94, 53.34), (27.94, 55.88), (27.94, 58.42))
    gnd(s, (27.94, 58.42))
    s.power("power:PWR_FLAG", 27.94, 55.88, 90)
    s.junction((27.94, 55.88))
    rail = [q1["1"], d3["3"], tp1["1"], d1["1"], (86.36, YA), c1["1"], c2["1"], c3["1"], c4["1"], u1["2"]]
    s.wire(*rail)
    for p in rail[1:-1]:
        s.junction(p)
    s.power("power:PWR_FLAG", 86.36, YA)
    s.label("VIN_A_P", (127.0, YA))
    s.wire(q1["4"], r3["1"])
    s.wire(q1["4"], d3["1"])
    s.junction(q1["4"])
    s.label("Q1_G", (58.42, 58.42))
    for p in (d1["2"], c1["2"], c2["2"], c3["2"], c4["2"], r3["2"]):
        gnd(s, p)
    stub(s, u1["3"], -2.54, 0, "EN_A", 180)
    s.wire(u1["6"], c5["1"])
    s.label("VCC_A", (UX - 13.97, 60.96))
    gnd(s, c5["2"])
    gnd(s, u1["1"])
    s.wire(u1["7"], (UX + 12.7, 50.8), (UX + 12.7, 45.72), c6["1"])
    s.label("BOOT_A", (UX + 12.7, 45.72), 90)
    s.wire(u1["8"], c6["2"], tp2["1"], l1["1"])
    s.junction(c6["2"])
    s.junction(tp2["1"])
    s.label("SW_A", (UX + 10.16, 53.34))
    stub(s, u1["5"], 5.08, 0, "FB_A", 0)
    stub(s, u1["4"], 5.08, 0, "PG_A", 0)
    out = [l1["2"]] + [c["1"] for c in couts] + [tp3["1"], j2["1"]]
    s.wire(*out)
    for p in out[1:-1]:
        s.junction(p)
    s.label("5V_A", (187.96, 53.34))
    for c in couts:
        gnd(s, c["2"])
    s.wire(j2["2"], (238.76, 55.88), (238.76, 60.96))
    gnd(s, (238.76, 60.96))
    stub(s, r4["1"], 0, -2.54, "VIN_A_P", 90)
    s.wire(r4["2"], r5["1"])
    s.label("EN_A", (256.54, 54.61))
    gnd(s, r5["2"])
    stub(s, r6["1"], 0, -2.54, "5V_A", 90)
    s.wire(r6["2"], r7["1"])
    s.label("FB_A", (266.7, 54.61))
    gnd(s, r7["2"])
    stub(s, r8["1"], 0, -2.54, "5V_A", 90)
    stub(s, r8["2"], 0, 2.54, "PG_A", 270)

    # =================== VARIANT B: 1S Li-ion -> boost -> 5 V ===================
    YB = 104.14
    j3 = s.part("J3", "Connector:Screw_Terminal_01x02", 20.32, YB, mirror="y",
                value="1S Li-ion 3.0-4.2 V", footprint=FP_TERM, fields=mfr("Phoenix Contact", "1715721"),
                ref_at=(17.78, 97.79), val_at=(20.32, 100.33), just="")
    f2 = s.part("F2", "Device:Fuse", 35.56, YB, rot=90, value="4A 32V",
                footprint=FP_FUSE, datasheet=DS["fuse"],
                fields=mfr("Littelfuse", "0466004.NRHF", {"Type": "Very fast-acting, 1206"}),
                ref_at=(35.56, 100.33), val_at=(35.56, 107.95), just="")
    q2 = s.part("Q2", "Transistor_FET:AON6411", 55.88, YB + 2.54, rot=90,
                footprint="Package_DFN_QFN:AO_DFN-8-1EP_5.55x5.2mm_P1.27mm_EP4.12x4.6mm",
                datasheet=DS["aon6411"], fields=mfr("Alpha & Omega Semiconductor", "AON6411"),
                ref_at=(55.88, 96.52), val_at=(55.88, 99.06), just="")
    r9 = R(s, "R9", 55.88, 118.11, "100k", "RC0603FR-07100KL")
    d4 = s.part("D4", "Diode:SMAJ8.5A", 73.66, 107.95, rot=270,
                footprint="Diode_SMD:D_SMA", datasheet=DS["smaj"], fields=mfr("Littelfuse", "SMAJ8.5A"),
                ref_at=(74.93, 114.3), val_at=(74.93, 116.84))
    c11 = C(s, "C11", 88.9, 107.95, "22u", "Murata", "GRM32ER71C226KE18L", FP_C1210, {"Voltage": "16V", "Dielectric": "X7R"})
    l2 = s.part("L2", "Device:L", 111.76, YB, rot=90, value="4.7u",
                footprint="Inductor_SMD:L_Coilcraft_XAL5030-XXX", datasheet=DS["xal50"],
                fields=mfr("Coilcraft", "XAL5030-472MEC", {"Isat": "6.7A (30% drop)", "DCR_max": "40mOhm"}),
                ref_at=(111.76, 100.33), val_at=(111.76, 107.95), just="")
    u2 = s.part("U2", "Regulator_Switching:MT3608", 111.76, 119.38, value="MT3608",
                footprint="Package_TO_SOT_SMD:SOT-23-6", datasheet=DS["mt"],
                fields=mfr("Aerosemi", "MT3608"), ref_at=(114.3, 129.54), val_at=(114.3, 132.08))
    d5 = s.part("D5", "Diode:SS34", 132.08, YB, rot=180,
                footprint="Diode_SMD:D_SMC", datasheet=DS["ss34"],
                fields=mfr("Vishay", "SS34-E3/57T",
                           {"Note": "Vishay SS34 is SMC (DO-214AB); library default D_SMA overridden"}),
                ref_at=(132.08, 100.33), val_at=(132.08, 107.95), just="")
    c12 = C(s, "C12", 144.78, 107.95, "22u", "Murata", "GRM32ER71C226KE18L", FP_C1210, {"Voltage": "16V", "Dielectric": "X7R"})
    c13 = C(s, "C13", 154.94, 107.95, "22u", "Murata", "GRM32ER71C226KE18L", FP_C1210, {"Voltage": "16V", "Dielectric": "X7R"})
    j4 = s.part("J4", "Connector:Screw_Terminal_01x02", 177.8, YB,
                value="5V_B out 1 A", footprint=FP_TERM, fields=mfr("Phoenix Contact", "1715721"),
                ref_at=(177.8, 97.79), val_at=(177.8, 100.33), just="")
    r10 = R(s, "R10", 200.66, 100.33, "73.2k", "RC0603FR-0773K2L")
    r11 = R(s, "R11", 200.66, 115.57, "10k", "RC0603FR-0710KL")
    r12 = R(s, "R12", 215.9, 100.33, "100k", "RC0603FR-07100KL")
    j5 = s.part("J5", "Connector_Generic:Conn_01x03", 251.46, 104.14, value="Status/control",
                footprint="Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
                fields={"Manufacturer": "generic", "MPN": "2.54 mm 1x03 male header"},
                ref_at=(251.46, 97.79), val_at=(251.46, 113.03), just="")
    tp4 = TP(s, "TP4", "VBAT_P", 66.04, YB)
    tp5 = TP(s, "TP5", "SW_B", 121.92, YB)
    tp6 = TP(s, "TP6", "5V_B", 162.56, YB)
    tp7 = TP(s, "TP7", "GND", 266.7, 104.14, "5001")

    # ---- wiring B ----
    s.wire(j3["1"], f2["1"])
    s.label("VBAT", j3["1"])
    s.wire(f2["2"], q2["5"])
    s.label("VBAT_F", (40.64, YB))
    s.wire(j3["2"], (27.94, 106.68), (27.94, 111.76))
    gnd(s, (27.94, 111.76))
    railb = [q2["1"], tp4["1"], d4["1"], (81.28, YB), c11["1"], (104.14, YB), l2["1"]]
    s.wire(*railb)
    for p in railb[1:-1]:
        s.junction(p)
    s.power("power:PWR_FLAG", 81.28, YB)
    s.label("VBAT_P", (91.44, YB))
    s.wire(q2["4"], (55.88, 111.76), r9["1"])
    s.label("Q2_G", (55.88, 111.76), 180)
    gnd(s, r9["2"])
    gnd(s, d4["2"])
    gnd(s, c11["2"])
    s.wire((104.14, YB), (104.14, 116.84), u2["5"])
    stub(s, u2["4"], -5.08, 0, "EN_B", 180)
    gnd(s, u2["2"])
    s.no_connect(u2["6"])
    s.wire(l2["2"], tp5["1"], d5["2"])
    s.junction(tp5["1"])
    s.wire(u2["1"], (121.92, 116.84), tp5["1"])
    s.label("SW_B", (121.92, 113.03), 90)
    stub(s, u2["3"], 5.08, 0, "FB_B", 0)
    outb = [d5["1"], c12["1"], c13["1"], tp6["1"], j4["1"]]
    s.wire(*outb)
    for p in outb[1:-1]:
        s.junction(p)
    s.label("5V_B", (137.16, YB))
    gnd(s, c12["2"])
    gnd(s, c13["2"])
    s.wire(j4["2"], (170.18, 106.68), (170.18, 111.76))
    gnd(s, (170.18, 111.76))
    stub(s, r10["1"], 0, -2.54, "5V_B", 90)
    s.wire(r10["2"], r11["1"])
    s.label("FB_B", (200.66, 107.95))
    gnd(s, r11["2"])
    stub(s, r12["1"], 0, -2.54, "VBAT_P", 90)
    stub(s, r12["2"], 0, 2.54, "EN_B", 270)
    stub(s, j5["1"], -5.08, 0, "PG_A", 180)
    stub(s, j5["2"], -5.08, 0, "EN_B", 180)
    s.wire(j5["3"], (241.3, 106.68), (241.3, 111.76))
    gnd(s, (241.3, 111.76))
    gnd(s, tp7["1"])

    # =================== annotations ===================
    s.rect(12.7, 36.83, 283.21, 81.28)
    s.text("VARIANT A: 9-24 V IN -> FUSE -> REVERSE P-FET -> TVS -> LMR33630A BUCK (400 kHz) -> 5 V, 2.5 A",
           13.97, 38.1, 1.5, True)
    s.rect(12.7, 86.36, 283.21, 137.16)
    s.text("VARIANT B: 1S LI-ION -> FUSE -> REVERSE P-FET -> TVS -> MT3608 BOOST (1.2 MHz) -> 5 V, 1 A",
           13.97, 87.63, 1.5, True)
    s.text("WARNING: Reference design. Test first with a current-limited supply and protection. "
           "Not for unattended use.", 12.7, 25.4, 1.8, True)
    s.text("Design only, not fabricated, not bench-tested. Variant B: the Li-ion pack MUST have its own "
           "protection (over-discharge, short circuit).", 12.7, 29.21, 1.5)
    notes = [
        "KEY VALUES (README has the derivations and sources)",
        "A: Vout = 1.0 V x (1 + 100k/24.9k) = 5.02 V (4.86-5.17 V worst case). L1 10 uH: ripple <= 1.46 A, peak <= 3.23 A at 2.5 A (HS limit >= 3.85 A).",
        "A: EN divider 100k/18.2k starts at 7.8-8.2 V. Q1 |VGS| = VIN up to ~11.4 V, then D3 clamps (VGS max 20 V). F1 3 A covers 1.63 A at 9 V with 70 C derating.",
        "A: SMAJ24A clamps at 38.9 V at full pulse, above the LMR33630 VIN abs max of 38 V. Input 9-24 V only.",
        "B: Vout = 0.6 V x (1 + 73.2k/10k) = 4.99 V. Battery 1.96 A at 3.0 V / 1 A out (eta 0.85 assumed). MT3608 limit 4 A typ, no minimum given.",
        "B: EN_B low stops switching but does NOT disconnect: VBAT - VF still reaches 5V_B. MT3608 UVLO is ~2 V: pack protection required.",
        "B: SMAJ8.5A chosen over SMAJ5.0A for leakage (20 uA vs 800 uA max at VR). F2 4 A; a Li-ion short can exceed its 50 A interrupting rating.",
    ]
    for i, t in enumerate(notes):
        s.text(t, 12.7, 143.51 + i * 3.81, 1.27, bold=(i == 0))

    tb = ["title_block",
          ["title", Q("5 V bus: 9-24 V buck and 1S Li-ion boost variants")],
          ["date", Q("2026-10-18")], ["rev", Q("A")], ["company", Q("Abdulazeez Bello")],
          ["comment", 1, Q("Design only, not fabricated, not bench-tested")],
          ["comment", 2, Q("Hardware licence: CERN-OHL-P-2.0")],
          ["comment", 3, Q("Generated from stock KiCad 9 library symbols by scripts/gen_schematic.py")]]
    return s, tb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symdir", default="/usr/share/kicad/symbols")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "hardware",
                                                  kg.PROJECT + ".kicad_sch"))
    a = ap.parse_args()
    s, tb = build(a.symdir)
    with open(a.out, "w") as f:
        f.write(s.serialize(tb))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
