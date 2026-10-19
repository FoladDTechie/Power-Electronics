#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Generate hardware/solar-charger.kicad_sch: BQ24650 MPPT-style solar charger
for one Li-ion cell, from stock KiCad 9 library symbols.

    python3 gen_schematic.py --symdir /usr/share/kicad/symbols
"""
import argparse
import os

import kicadgen as kg
from kicadgen import Q, Sheet

FP_R0603 = "Resistor_SMD:R_0603_1608Metric"
FP_C0603 = "Capacitor_SMD:C_0603_1608Metric"
FP_C0805 = "Capacitor_SMD:C_0805_2012Metric"
FP_C1210 = "Capacitor_SMD:C_1210_3225Metric"
FP_TP = "TestPoint:TestPoint_Keystone_5000-5004_Miniature"
FP_TERM = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal"
FP_LFPAK = "Package_TO_SOT_SMD:LFPAK33"

DS = {
    "bq": "https://www.ti.com/lit/ds/symlink/bq24650.pdf",
    "buk": "https://assets.nexperia.com/documents/data-sheet/BUK9M14-40E.pdf",
    "bss138": "https://www.onsemi.com/download/data-sheet/pdf/bss138-d.pdf",
    "bat54j": "https://assets.nexperia.com/documents/data-sheet/BAT54J.pdf",
    "ss34": "https://www.vishay.com/docs/88751/ss32.pdf",
    "smaj": "https://4donline.ihs.com/images/VipMasterIC/IC/LFSI/LFSI-S-A0011271570/LFSI-S-A0011345017-1.pdf",
    "fuse": "https://4donline.ihs.com/images/VipMasterIC/IC/LFSI/LFSIS12645/LFSIS12645-1.pdf",
    "xal60": "https://www.coilcraft.com/pdfs/xal60xx.pdf",
    "wsl": "https://www.vishay.com/docs/30100/wsl.pdf",
    "rc": "https://www.yageogroup.com/component-documentation/download/specsheet/RC0805FR-0712KL",
    "rt": "https://www.yageo.com/upload/media/product/productsearch/datasheet/rchip/PYu-RT_1-to-0.01_RoHS_L_11.pdf",
}


def mfr(m, mpn, extra=None):
    d = {"Manufacturer": m, "MPN": mpn}
    d.update(extra or {})
    return d


def R(s, ref, x, y, val, mpn, rot=0, fp=FP_R0603, tol="1%", ds=None, m="Yageo", **kw):
    return s.part(ref, "Device:R", x, y, rot=rot, value=val, footprint=fp, datasheet=ds or DS["rc"],
                  fields=mfr(m, mpn, {"Tolerance": tol}), **kw)


def C(s, ref, x, y, val, volt, mpn, fp, rot=0, **kw):
    return s.part(ref, "Device:C", x, y, rot=rot, value=val, footprint=fp,
                  fields=mfr("Murata", mpn, {"Voltage": volt, "Dielectric": "X7R"}), **kw)


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


def vpair(s, x, ytop, top, bot, top_net, mid_net, bot_net="GND"):
    """Two resistors stacked vertically: top_net - top - mid_net - bot - bot_net."""
    stub(s, top["1"], 0, -2.54, top_net, 90)
    s.wire(top["2"], bot["1"])
    s.label(mid_net, (x, round((top["2"][1] + bot["1"][1]) / 2, 2)))
    if bot_net == "GND":
        gnd(s, bot["2"])
    else:
        stub(s, bot["2"], 0, 2.54, bot_net, 270)


def build(symdir):
    s = Sheet(symdir)
    Y = 50.8   # VIN rail
    YB = 67.31  # PH / SRP / SRN / BAT line

    # ======================= input =======================
    j1 = s.part("J1", "Connector:Screw_Terminal_01x02", 20.32, Y, mirror="y",
                value="PANEL", footprint=FP_TERM, fields=mfr("Phoenix Contact", "1715721", {"Rating": "Voc <= 22 V"}),
                ref_at=(17.78, 44.45), val_at=(17.78, 46.99), just="")
    d1 = s.part("D1", "Diode:SS34", 35.56, Y, rot=180, footprint="Diode_SMD:D_SMC", datasheet=DS["ss34"],
                fields=mfr("Vishay", "SS34-E3/57T",
                           {"Note": "Vishay SS34 is SMC (DO-214AB); library default D_SMA overridden"}),
                ref_at=(35.56, 46.99), val_at=(35.56, 54.61), just="")
    d2 = s.part("D2", "Diode:SMAJ24A", 45.72, 54.61, rot=270, footprint="Diode_SMD:D_SMA",
                datasheet=DS["smaj"], fields=mfr("Littelfuse", "SMAJ24A"),
                ref_at=(46.99, 60.96), val_at=(46.99, 63.5))
    c1 = C(s, "C1", 55.88, 54.61, "10u", "50V", "GRM32ER71H106KA12L", FP_C1210)
    c2 = C(s, "C2", 66.04, 54.61, "10u", "50V", "GRM32ER71H106KA12L", FP_C1210)
    r1 = R(s, "R1", 76.2, 54.61, "10R", "RC0603FR-0710RL", ref_at=(77.47, 52.07), val_at=(77.47, 54.61))
    c3 = C(s, "C3", 76.2, 62.23, "1u", "50V", "GRM21BR71H105KA12L", FP_C0805,
           ref_at=(74.93, 62.23), val_at=(74.93, 64.77), just="right")
    tp1 = TP(s, "TP1", "VIN", 86.36, Y)

    s.wire(j1["1"], d1["2"])
    s.label("PANEL", j1["1"])
    rail = [d1["1"], d2["1"], c1["1"], c2["1"], r1["1"], tp1["1"], (99.06, Y), (104.14, Y)]
    s.wire(*rail)
    for p in rail[1:-1]:
        s.junction(p)
    s.power("power:PWR_FLAG", 99.06, Y)
    s.label("VIN", (40.64, Y))
    s.wire(j1["2"], (27.94, 53.34), (27.94, 55.88), (27.94, 58.42))
    gnd(s, (27.94, 58.42))
    s.power("power:PWR_FLAG", 27.94, 55.88, 90)
    s.junction((27.94, 55.88))
    for c in (d2, c1, c2):
        gnd(s, c["2"])
    s.wire(r1["2"], (78.74, 58.42))
    s.junction(r1["2"])
    s.label("VCC", (78.74, 58.42))
    gnd(s, c3["2"])

    # ======================= power stage =======================
    q1 = s.part("Q1", "Transistor_FET:BUK9M14-40EX", 101.6, 58.42, footprint=FP_LFPAK,
                datasheet=DS["buk"], fields=mfr("Nexperia", "BUK9M14-40EX"),
                ref_at=(99.06, 62.23), val_at=(99.06, 64.77), just="right")
    q2 = s.part("Q2", "Transistor_FET:BUK9M14-40EX", 101.6, 76.2, footprint=FP_LFPAK,
                datasheet=DS["buk"], fields=mfr("Nexperia", "BUK9M14-40EX"),
                ref_at=(99.06, 80.01), val_at=(99.06, 82.55), just="right")
    s.wire((104.14, Y), q1["5"])
    s.wire(q1["1"], (104.14, YB), q2["5"])
    s.junction((104.14, YB))
    stub(s, q1["4"], -2.54, 0, "HIDRV", 180)
    stub(s, q2["4"], -2.54, 0, "LODRV", 180)
    gnd(s, q2["1"])
    c4 = C(s, "C4", 111.76, 63.5, "100n", "50V", "GRM188R71H104KA93D", FP_C0603,
           ref_at=(110.49, 62.23), val_at=(110.49, 64.77), just="right")
    stub(s, c4["1"], 0, -2.54, "BTST", 90)
    d3 = s.part("D3", "Diode:BAT54J", 125.73, 53.34, rot=180, footprint="Diode_SMD:D_SOD-323F",
                datasheet=DS["bat54j"], fields=mfr("Nexperia", "BAT54J,115"),
                ref_at=(125.73, 49.53), val_at=(125.73, 57.15), just="")
    stub(s, d3["2"], -2.54, 0, "REGN", 180)
    stub(s, d3["1"], 2.54, 0, "BTST", 0)
    l1 = s.part("L1", "Device:L", 123.19, YB, rot=90, value="10u",
                footprint="Inductor_SMD:L_Coilcraft_XAL6060-XXX", datasheet=DS["xal60"],
                fields=mfr("Coilcraft", "XAL6060-103MEC", {"Isat": "7.6A (30% drop)", "DCR_max": "29.8mOhm"}),
                ref_at=(123.19, 71.12), val_at=(123.19, 73.66), just="")
    tp2 = TP(s, "TP2", "PH", 116.84, YB)
    s.wire((104.14, YB), c4["2"], tp2["1"], l1["1"])
    s.junction(c4["2"])
    s.junction(tp2["1"])
    s.label("PH", (106.68, YB))
    r4 = R(s, "R4", 143.51, YB, "20m", "WSL1206R0200FEA", rot=90, fp="Resistor_SMD:R_1206_3216Metric",
           ds=DS["wsl"], m="Vishay Dale", ref_at=(143.51, 71.12), val_at=(143.51, 73.66), just="")
    c8 = C(s, "C8", 133.35, 71.12, "100n", "50V", "GRM188R71H104KA93D", FP_C0603)
    c7 = C(s, "C7", 143.51, 58.42, "100n", "50V", "GRM188R71H104KA93D", FP_C0603, rot=90,
           ref_at=(143.51, 52.07), val_at=(143.51, 54.61), just="")
    s.wire(l1["2"], c8["1"], (138.43, YB), r4["1"])
    s.junction(c8["1"])
    s.junction((138.43, YB))
    s.wire((138.43, YB), (138.43, 58.42), c7["1"])
    s.label("SRP", (129.54, YB))
    gnd(s, c8["2"])
    c9 = C(s, "C9", 160.02, 71.12, "10u", "50V", "GRM32ER71H106KA12L", FP_C1210)
    tp3 = TP(s, "TP3", "SRN", 154.94, YB)
    f1 = s.part("F1", "Device:Fuse", 175.26, YB, rot=90, value="4A 32V", footprint="Fuse:Fuse_1206_3216Metric",
                datasheet=DS["fuse"], fields=mfr("Littelfuse", "0466004.NRHF", {"Type": "Very fast-acting, 1206"}),
                ref_at=(175.26, 63.5), val_at=(175.26, 71.12), just="")
    s.wire(r4["2"], (148.59, YB), tp3["1"], c9["1"], f1["1"])
    for p in ((148.59, YB), tp3["1"], c9["1"]):
        s.junction(p)
    s.wire((148.59, YB), (148.59, 58.42), c7["2"])
    s.label("SRN", (165.1, YB))
    gnd(s, c9["2"])
    j2 = s.part("J2", "Connector:Screw_Terminal_01x02", 200.66, YB,
                value="1S cell", footprint=FP_TERM, fields=mfr("Phoenix Contact", "1715721"),
                ref_at=(203.2, 72.39), val_at=(203.2, 74.93), just="left")
    tp4 = TP(s, "TP4", "BAT", 187.96, YB)
    s.wire(f1["2"], tp4["1"], j2["1"])
    s.junction(tp4["1"])
    s.label("BAT", (180.34, YB))
    s.wire(j2["2"], (193.04, 69.85), (193.04, 74.93))
    gnd(s, (193.04, 74.93))

    # ======================= controller =======================
    UX, UY = 50.8, 119.38
    u1 = s.part("U1", "Battery_Management:BQ24650", UX, UY, value="BQ24650",
                footprint="Package_DFN_QFN:Texas_RVA_VQFN-16-1EP_3.5x3.5mm_P0.5mm_EP2.14x2.14mm_ThermalVias",
                datasheet=DS["bq"], fields=mfr("Texas Instruments", "BQ24650RVAR"),
                ref_at=(UX + 3.81, UY + 22.86), val_at=(UX + 3.81, UY + 25.4))
    s.wire(u1["1"], (UX, UY - 24.13), (UX, UY - 25.4))
    s.junction((UX, UY - 24.13))
    s.power("power:PWR_FLAG", UX, UY - 24.13, 270)
    s.label("VCC", (UX, UY - 25.4), 90)
    gnd(s, u1["11"])
    stub(s, u1["6"], -5.08, 0, "VREF", 180)
    stub(s, u1["7"], -5.08, 0, "VREF", 180)     # TERM_EN tied to VREF: termination enabled
    stub(s, u1["2"], -5.08, 0, "MPPSET", 180)
    for num, net in (("15", "HIDRV"), ("14", "PH"), ("16", "BTST"), ("12", "REGN"), ("13", "LODRV"),
                     ("10", "SRP"), ("9", "SRN"), ("8", "VFB"), ("4", "TS"), ("3", "STAT1"), ("5", "STAT2")):
        stub(s, u1[num], 5.08, 0, net, 0)

    # ======================= networks =======================
    YN = 104.14
    # REGN and VREF capacitors
    c5 = C(s, "C5", 86.36, YN + 3.81, "1u", "16V", "GRM188R71C105KA12D", FP_C0603)
    stub(s, c5["1"], 0, -2.54, "REGN", 90)
    gnd(s, c5["2"])
    c6 = C(s, "C6", 96.52, YN + 3.81, "1u", "16V", "GRM188R71C105KA12D", FP_C0603)
    stub(s, c6["1"], 0, -2.54, "VREF", 90)
    gnd(s, c6["2"])
    # MPPSET divider + disable FET
    r2 = R(s, "R2", 111.76, YN, "499k", "RC0603FR-07499KL")
    r3 = R(s, "R3", 111.76, YN + 12.7, "36.0k", "RC0603FR-0736KL")
    vpair(s, 111.76, YN, r2, r3, "VIN", "MPPSET")
    q3 = s.part("Q3", "Transistor_FET:BSS138", 124.46, YN + 12.7, footprint="Package_TO_SOT_SMD:SOT-23",
                datasheet=DS["bss138"], fields=mfr("onsemi", "BSS138"),
                ref_at=(129.54, YN + 11.43), val_at=(129.54, YN + 13.97))
    stub(s, q3["3"], 0, -2.54, "MPPSET", 90)
    gnd(s, q3["2"])
    r10 = R(s, "R10", 116.84, YN + 21.59, "100k", "RC0603FR-07100KL")
    s.wire(q3["1"], (116.84, YN + 12.7), r10["1"])
    s.label("CHG_DIS", r10["1"])
    gnd(s, r10["2"])
    # VFB divider (0.1 %)
    r5 = R(s, "R5", 142.24, YN, "100k", "RT0603BRD07100KL", tol="0.1%", ds=DS["rt"])
    r6 = R(s, "R6", 142.24, YN + 12.7, "102k", "RT0603BRD07102KL", tol="0.1%", ds=DS["rt"])
    vpair(s, 142.24, YN, r5, r6, "SRN", "VFB")
    # TS network + NTC connector
    rt1 = R(s, "R7", 157.48, YN, "4.32k", "RC0603FR-074K32L")
    rt2 = R(s, "R11", 157.48, YN + 12.7, "20.5k", "RC0603FR-0720K5L")
    vpair(s, 157.48, YN, rt1, rt2, "VREF", "TS")
    j3 = s.part("J3", "Connector_Generic:Conn_01x02", 177.8, YN + 6.35, value="NTC 103AT",
                footprint="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
                fields={"Manufacturer": "generic", "MPN": "2.54 mm 1x02 header (pack NTC)"},
                ref_at=(177.8, YN + 1.27), val_at=(177.8, YN + 12.7), just="")
    stub(s, j3["1"], -5.08, 0, "TS", 180)
    s.wire(j3["2"], (170.18, YN + 8.89), (170.18, YN + 11.43))
    gnd(s, (170.18, YN + 11.43))
    # status LEDs
    for i, (ref_r, ref_d, x, net) in enumerate((("R8", "D4", 193.04, "STAT1"), ("R9", "D5", 203.2, "STAT2"))):
        rr = R(s, ref_r, x, YN, "1k", "RC0603FR-071KL")
        dd = s.part(ref_d, "Device:LED", x, YN + 10.16, rot=90, value="green",
                    footprint="LED_SMD:LED_0603_1608Metric",
                    ref_at=(x + 2.54, YN + 5.08), val_at=(x + 2.54, YN + 7.62),
                    fields=mfr("Lite-On", "LTST-C190GKT", {"Note": "VF 2.1 V per TI BQ24650 BOM; LED datasheet not read"}))
        stub(s, rr["1"], 0, -2.54, "VREF", 90)
        s.wire(rr["2"], dd["2"])
        stub(s, dd["1"], 0, 2.54, net, 270)
    # header
    j4 = s.part("J4", "Connector_Generic:Conn_01x04", 236.22, YN + 6.35, value="Status/control",
                footprint="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
                fields={"Manufacturer": "generic", "MPN": "2.54 mm 1x04 male header"},
                ref_at=(236.22, YN - 1.27), val_at=(236.22, YN + 15.24), just="")
    stub(s, j4["1"], -5.08, 0, "STAT1", 180)
    stub(s, j4["2"], -5.08, 0, "STAT2", 180)
    stub(s, j4["3"], -5.08, 0, "CHG_DIS", 180)
    s.wire(j4["4"], (226.06, YN + 11.43), (226.06, YN + 13.97))
    gnd(s, (226.06, YN + 13.97))
    tp5 = TP(s, "TP5", "GND", 251.46, YN + 6.35, "5001")
    gnd(s, tp5["1"])

    # ======================= annotations =======================
    s.rect(12.7, 38.1, 212.09, 85.09)
    s.text("INPUT (panel) -> SS34 blocking -> SMAJ24A -> SYNC BUCK (BUK9M14 x2, 10 uH, 600 kHz) -> 20 mOhm SENSE -> FUSE -> 1S CELL",
           13.97, 39.37, 1.4, True)
    s.rect(12.7, 90.17, 260.35, 151.13)
    s.text("BQ24650 CONTROLLER AND SET-POINT NETWORKS", 13.97, 147.32, 1.4, True)
    s.text("WARNING: Reference design. Test first with a current-limited supply and protection. "
           "Not for unattended use.", 12.7, 25.4, 1.8, True)
    s.text("Design only, not fabricated, not bench-tested. Li-ion: use a cell or pack with its own "
           "protection circuit and a 103AT NTC on J3.", 12.7, 29.21, 1.5)
    notes = [
        "KEY VALUES (README has the derivations and sources)",
        "Charge voltage = 2.1 V x (1 + 100k/102k) = 4.159 V; worst case 4.134-4.194 V incl. VFB leakage (never above 4.20 V).",
        "Charge current = 40 mV / 20 mOhm = 2.0 A (+-3 %); precharge and termination 0.2 A (+-25 %). Cycle-by-cycle limit 4 A.",
        "MPP: VCC-side regulation = 1.2 V x (1 + 499k/36.0k) = 17.83 V (panel ~18.2 V with D1). Set to your panel's Vmp at operating temperature.",
        "L1 10 uH: ripple <= 0.83 A worst case (41 % of 2 A). Output LC f0 = 15.9 kHz with 10 uF (datasheet 12-17 kHz).",
        "TS: R7 4.32k / R11 20.5k with 103AT (B-model): charge 0-45 C, cut-off ~49 C. Recompute from the Semitec R-T table.",
        "SMAJ24A clamps at 38.9 V at full pulse, above BQ24650 VCC abs max 33 V. Panel Voc must stay <= 22 V.",
        "CHG_DIS high pulls MPPSET below 75 mV and stops charging. STAT1 low = charging, STAT2 low = done.",
    ]
    for i, t in enumerate(notes):
        s.text(t, 12.7, 156.21 + i * 3.3, 1.2, bold=(i == 0))

    tb = ["title_block",
          ["title", Q("Solar charger: BQ24650 for one Li-ion cell")],
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
