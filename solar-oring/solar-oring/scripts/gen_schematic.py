#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Generate hardware/solar-oring.kicad_sch (LTC4412 ideal diode vs Schottky
OR-ing) from stock KiCad 9 library symbols.

    python3 gen_schematic.py --symdir /usr/share/kicad/symbols
"""
import argparse
import os

import kicadgen as kg
from kicadgen import Q, Sheet

FP_R0603 = "Resistor_SMD:R_0603_1608Metric"
FP_C0603 = "Capacitor_SMD:C_0603_1608Metric"
FP_TP = "TestPoint:TestPoint_Keystone_5000-5004_Miniature"
FP_TERM = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal"

DS_LTC4412 = "https://www.analog.com/media/en/technical-documentation/data-sheets/4412fb.pdf"
DS_SIS443 = "https://www.vishay.com/docs/63253/sis443dn.pdf"
DS_SS34 = "https://www.vishay.com/docs/88751/ss32.pdf"
DS_SMAJ = "https://4donline.ihs.com/images/VipMasterIC/IC/LFSI/LFSI-S-A0011271570/LFSI-S-A0011345017-1.pdf"
DS_RC = "https://www.yageogroup.com/component-documentation/download/specsheet/RC0805FR-0712KL"
DS_GRM = "https://search.murata.co.jp/Ceramy/image/img/A01X/G101/ENG/GRM188R71H104KA93-01.pdf"


def mfr(m, mpn, extra=None):
    d = {"Manufacturer": m, "MPN": mpn}
    d.update(extra or {})
    return d


def build(symdir):
    s = Sheet(symdir)
    YS = 69.85   # SOLAR_IN / VLOAD rail
    YA = 45.72   # AUX_IN rail

    # ---------------- connectors ----------------
    j1 = s.part("J1", "Connector:Screw_Terminal_01x02", 25.4, YS, mirror="y",
                value="SOLAR 0-22 V", footprint=FP_TERM,
                fields=mfr("Phoenix Contact", "1715721"),
                ref_at=(22.86, 66.04), val_at=(22.86, 76.2), just="")
    j2 = s.part("J2", "Connector:Screw_Terminal_01x02", 25.4, YA, mirror="y",
                value="AUX 10-15 V", footprint=FP_TERM,
                fields=mfr("Phoenix Contact", "1715721"),
                ref_at=(22.86, 41.91), val_at=(22.86, 52.07), just="")
    j3 = s.part("J3", "Connector:Screw_Terminal_01x02", 142.24, YS,
                value="LOAD 3 A max", footprint=FP_TERM,
                fields=mfr("Phoenix Contact", "1715721"),
                ref_at=(144.78, 66.04), val_at=(144.78, 76.2), just="")
    j4 = s.part("J4", "Connector_Generic:Conn_01x04", 165.1, 100.33,
                value="Control/status",
                footprint="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
                fields={"Manufacturer": "generic", "MPN": "2.54 mm 1x04 male header"},
                ref_at=(162.56, 93.98), val_at=(167.64, 109.22), just="left")

    # ---------------- solar path ----------------
    d2 = s.part("D2", "Diode:SMAJ24A", 48.26, 73.66, rot=270,
                footprint="Diode_SMD:D_SMA", datasheet=DS_SMAJ,
                fields=mfr("Littelfuse", "SMAJ24A"),
                ref_at=(45.72, 76.2), val_at=(45.72, 78.74), just="right")
    c1 = s.part("C1", "Device:C", 55.88, 73.66, value="100n 50V",
                footprint=FP_C0603, datasheet=DS_GRM,
                fields=mfr("Murata", "GRM188R71H104KA93D", {"Dielectric": "X7R"}))
    q1 = s.part("Q1", "Transistor_FET:SiS443DN", 76.2, 72.39, rot=90,
                footprint="Package_SO:Vishay_PowerPAK_1212-8_Single", datasheet=DS_SIS443,
                fields=mfr("Vishay Siliconix", "SiS443DN-T1-GE3"),
                ref_at=(76.2, 62.23), val_at=(76.2, 64.77), just="")
    u1 = s.part("U1", "Power_Management:LTC4412xS6", 76.2, 97.79, value="LTC4412",
                footprint="Package_TO_SOT_SMD:TSOT-23-6", datasheet=DS_LTC4412,
                fields=mfr("Analog Devices", "LTC4412ES6#TRMPBF"),
                ref_at=(80.01, 106.68), val_at=(80.01, 109.22))
    r2 = s.part("R2", "Device:R", 55.88, 104.14, value="100k",
                footprint=FP_R0603, datasheet=DS_RC,
                fields=mfr("Yageo", "RC0603FR-07100KL", {"Tolerance": "1%"}))
    r1 = s.part("R1", "Device:R", 96.52, 96.52, value="470k",
                footprint=FP_R0603, datasheet=DS_RC,
                fields=mfr("Yageo", "RC0603FR-07470KL", {"Tolerance": "1%"}))

    # ---------------- aux path ----------------
    c2 = s.part("C2", "Device:C", 40.64, 49.53, value="100n 50V",
                footprint=FP_C0603, datasheet=DS_GRM,
                fields=mfr("Murata", "GRM188R71H104KA93D", {"Dielectric": "X7R"}))
    d1 = s.part("D1", "Diode:SS34", 96.52, YA, rot=180,
                footprint="Diode_SMD:D_SMC", datasheet=DS_SS34,
                fields=mfr("Vishay", "SS34-E3/57T",
                           {"Note": "Vishay SS34 is SMC (DO-214AB); library default D_SMA overridden"}),
                ref_at=(96.52, 41.91), val_at=(96.52, 49.53), just="")

    # ---------------- load ----------------
    c3 = s.part("C3", "Device:C_Polarized", 124.46, 73.66, value="47u 35V",
                footprint="Capacitor_SMD:CP_Elec_6.3x5.8",
                fields=mfr("Panasonic", "EEE-FK1V470P", {"Type": "Aluminium electrolytic"}))

    # ---------------- test points ----------------
    tp = {}
    for ref, net, x, y, rot, mpn in (
            ("TP1", "SOLAR_IN", 35.56, YS, 0, "5000"),
            ("TP2", "AUX_IN", 48.26, YA, 0, "5000"),
            ("TP3", "VLOAD", 116.84, YS, 0, "5000"),
            ("TP4", "GATE", 76.2, 82.55, 90, "5000"),
            ("TP5", "STAT", 104.14, 100.33, 0, "5000"),
            ("TP6", "GND", 25.4, 109.22, 0, "5001")):
        ra = (x + 1.27, y - 6.35) if rot == 0 else (x - 7.62, y - 1.27)
        va = (x + 1.27, y - 3.81) if rot == 0 else (x - 7.62, y + 1.27)
        tp[ref] = s.part(ref, "Connector:TestPoint", x, y, rot=rot, value=net,
                         footprint=FP_TP, fields=mfr("Keystone Electronics", mpn),
                         ref_at=ra, val_at=va, just="left" if rot == 0 else "right")

    # ================= wiring =================
    # SOLAR_IN rail
    s.wire(j1["1"], tp["TP1"]["1"], d2["1"], c1["1"], (60.96, YS), (63.5, YS), q1["5"])
    for p in (tp["TP1"]["1"], d2["1"], c1["1"], (60.96, YS), (63.5, YS)):
        s.junction(p)
    s.power("power:PWR_FLAG", 60.96, YS)
    s.label("SOLAR_IN", j1["1"])
    s.wire((63.5, YS), (63.5, 95.25), u1["1"])
    s.power("power:GND", *d2["2"])
    s.power("power:GND", *c1["2"])
    # J1 ground + PWR_FLAG
    s.wire(j1["2"], (33.02, 72.39), (33.02, 76.2), (33.02, 78.74))
    s.junction((33.02, 76.2))
    s.power("power:PWR_FLAG", 33.02, 76.2, 270)
    s.power("power:GND", 33.02, 78.74)

    # GATE
    s.wire(u1["5"], tp["TP4"]["1"], q1["4"])
    s.junction(tp["TP4"]["1"])
    s.label("GATE", (76.2, 85.09))

    # VLOAD rail: Q1.S -> SENSE tap -> D1 tap -> TP3 -> C3 -> J3
    s.wire(q1["1"], (88.9, YS), (106.68, YS), tp["TP3"]["1"], c3["1"], j3["1"])
    for p in ((88.9, YS), (106.68, YS), tp["TP3"]["1"], c3["1"]):
        s.junction(p)
    s.label("VLOAD", (91.44, YS))
    s.wire((88.9, YS), (88.9, 95.25), u1["6"])
    s.power("power:GND", *c3["2"])
    s.wire(j3["2"], (134.62, 72.39), (134.62, 78.74))
    s.power("power:GND", 134.62, 78.74)

    # U1 ground
    s.power("power:GND", *u1["2"])
    # CTL with R2 pull-down
    s.wire(u1["3"], r2["1"], (50.8, 100.33))
    s.junction(r2["1"])
    s.label("CTL", (50.8, 100.33), 180)
    s.power("power:GND", *r2["2"])
    # STAT with R1 pull-up to +3V3
    s.wire(u1["4"], r1["2"], tp["TP5"]["1"], (109.22, 100.33))
    s.junction(r1["2"])
    s.junction(tp["TP5"]["1"])
    s.label("STAT", (109.22, 100.33))
    s.power("power:+3V3", *r1["1"])

    # AUX_IN rail: J2 -> C2 -> TP2 -> FLAG -> D1.A ; D1.K -> VLOAD
    s.wire(j2["1"], c2["1"], tp["TP2"]["1"], (63.5, YA), d1["2"])
    for p in (c2["1"], tp["TP2"]["1"], (63.5, YA)):
        s.junction(p)
    s.power("power:PWR_FLAG", 63.5, YA)
    s.label("AUX_IN", j2["1"])
    s.power("power:GND", *c2["2"])
    s.wire(d1["1"], (106.68, YA), (106.68, YS))
    s.wire(j2["2"], (33.02, 48.26), (33.02, 53.34))
    s.power("power:GND", 33.02, 53.34)

    # J4: 1 +3V3 (PWR_FLAG), 2 STAT, 3 CTL, 4 GND
    s.wire(j4["1"], (157.48, 97.79), (157.48, 95.25), (157.48, 92.71))
    s.junction((157.48, 95.25))
    s.power("power:+3V3", 157.48, 92.71)
    s.power("power:PWR_FLAG", 157.48, 95.25, 90)
    s.wire(j4["2"], (154.94, 100.33))
    s.label("STAT", (154.94, 100.33), 180)
    s.wire(j4["3"], (154.94, 102.87))
    s.label("CTL", (154.94, 102.87), 180)
    s.wire(j4["4"], (157.48, 105.41), (157.48, 107.95))
    s.power("power:GND", 157.48, 107.95)
    # GND test point
    s.power("power:GND", *tp["TP6"]["1"])

    # ================= annotations =================
    s.rect(12.7, 33.02, 113.03, 58.42)
    s.text("AUX INPUT -> SCHOTTKY (SS34)", 13.97, 34.29, 1.5, True)
    s.rect(12.7, 59.69, 113.03, 121.92)
    s.text("SOLAR INPUT -> IDEAL DIODE (LTC4412 + SiS443DN)", 13.97, 118.11, 1.5, True)
    s.rect(114.3, 33.02, 152.4, 85.09)
    s.text("LOAD (OR-ed)", 115.57, 34.29, 1.5, True)
    s.rect(140.97, 86.36, 185.42, 121.92)
    s.text("CONTROL / STATUS", 142.24, 118.11, 1.5, True)

    s.text("WARNING: Reference design. Test first with a current-limited supply and "
           "protection. Not for unattended use.", 12.7, 21.59, 1.8, True)
    s.text("Design only, not fabricated, not bench-tested.", 12.7, 25.4, 1.5)

    notes = [
        "KEY VALUES (see README for derivations and sources)",
        "Ideal diode: LTC4412 holds VIN - VSENSE at VFR = 10-32 mV until Q1 is fully on; then drop = I x RDS(on).",
        "Q1 SiS443DN: RDS(on) <= 16 mOhm at VGS = -4.5 V. LTC4412 gate clamp 6.3-7.7 V (VIN >= 6.3 V). 3 A -> <= 48 mV, <= 0.14 W.",
        "D1 SS34: VF <= 0.5 V at 3 A, 25 C -> <= 1.5 W at 3 A, about 82 K rise (55 C/W). IR <= 0.5 mA (25 C), 20 mA (100 C).",
        "Solar input: LTC4412 VIN operating 2.5-28 V, abs max 36 V. Panel Voc must stay <= 22 V. D2 SMAJ24A: VR 24 V, VC 38.9 V @ 10.3 A (> 36 V!).",
        "STAT sinks 6-17 uA when the solar path is off (VLOAD > SOLAR_IN + 10..32 mV). R1 470k -> high >= 2.8 V, low <= 0.5 V at 3.3 V.",
        "CTL high (>= 0.9 V) forces Q1 off (e.g. to read panel Voc). R2 keeps it low if the header is open.",
        "C3: LTC4412 suggests 1-47 uF on the load; electrolytic ESR damps the MLCC hot-plug ringing the datasheet warns about.",
        "No load fuse and no panel reverse-polarity protection: use a keyed panel connector (see README Known limitations).",
    ]
    for i, line in enumerate(notes):
        s.text(line, 12.7, 128.27 + i * 3.81, 1.27, bold=(i == 0))

    tb = ["title_block",
          ["title", Q("Solar OR-ing: LTC4412 ideal diode vs Schottky")],
          ["date", Q("2026-10-18")],
          ["rev", Q("A")],
          ["company", Q("Abdulazeez Bello")],
          ["comment", 1, Q("Design only, not fabricated, not bench-tested")],
          ["comment", 2, Q("Hardware licence: CERN-OHL-P-2.0")],
          ["comment", 3, Q("Generated from stock KiCad 9 library symbols by scripts/gen_schematic.py")]]
    return s, tb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symdir", default="/usr/share/kicad/symbols")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..",
                                                  "hardware", kg.PROJECT + ".kicad_sch"))
    a = ap.parse_args()
    s, tb = build(a.symdir)
    with open(a.out, "w") as f:
        f.write(s.serialize(tb))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
