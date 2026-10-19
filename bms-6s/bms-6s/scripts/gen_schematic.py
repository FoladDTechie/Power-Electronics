#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Generate hardware/bms-6s.kicad_sch: 6S Li-ion protection board around the
TI BQ76930 analogue front end, with low-side CHG/DSG MOSFETs, a 1 mOhm
sense resistor and a host-MCU port, from stock KiCad 9 library symbols.

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
FP_PADS = "Connector_Wire:SolderWire-2.5sqmm_1x02_P7.2mm_D2.4mm_OD3.6mm"
FP_SOD123 = "Diode_SMD:D_SOD-123"
FP_TOLL = "Package_TO_SOT_SMD:Infineon_PG-HSOF-8-1"

DS = {
    "bq": "https://www.ti.com/lit/ds/symlink/bq76930.pdf",
    "wsk": "https://www.mouser.lt/pdfDocs/wsk2512.pdf",
    "smcj": "https://prod-parts-data.s3.amazonaws.com/SMCJ30A/datasheet/1_SMCJ30A-Littelfuse-datasheet-34142008.pdf",
    "ipt": "http://www.infineon.com/dgdl/Infineon-IPT012N08N5-DS-v02_01-EN.pdf?fileId=5546d4624a75e5f1014aca59127a1eb9",
    "bzx": "https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/other/4977/1/datasheet.pdf",
    "1n4148w": "https://datasheet.ciiva.com/1201/1726056-1201861.pdf",
    "2n7002": "https://prod-parts-data.s3.amazonaws.com/2N7002,215/datasheet/1_2N70022C215-Nexperia-datasheet-10741796.pdf",
    "jstgh": "https://www.mouser.com/datasheet/2/564/eGH-3476810.pdf",
    "jstxh": "https://www.pololu.com:444/file/0J372/JST_eXH.pdf",
    "b3u": "https://nl.farnell.com/omron/b3u-1000p-b/switch-spst-no-0-05a-12v-smd-boss/dp/1333654",
    "rc": "https://www.yageogroup.com/component-documentation/download/specsheet/RC0805FR-0712KL",
}


def mfr(m, mpn, extra=None):
    d = {"Manufacturer": m, "MPN": mpn}
    d.update(extra or {})
    return d


def yageo(val):
    """Yageo RC-series value code for a value string like '22k', '1M', '10R', '499k'."""
    code = val.upper()
    if code[-1] in "KM":
        unit, num = code[-1], code[:-1]
        if "." in num:
            a, b = num.split(".")
            b = b.rstrip("0")
            code = f"{a}{unit}{b}" if b else f"{a}{unit}"
        else:
            code = f"{num}{unit}"
    return code


def R(s, ref, x, y, val, rot=90, fp=FP_R0603, mpn=None, tol="1%", ds=None, m="Yageo", **kw):
    mpn = mpn or f"RC0603FR-07{yageo(val)}L"
    return s.part(ref, "Device:R", x, y, rot=rot, value=val, footprint=fp, datasheet=ds or DS["rc"],
                  fields=mfr(m, mpn, {"Tolerance": tol}), **kw)


def C(s, ref, x, y, val, volt, mpn, fp, rot=90, diel="X7R", **kw):
    return s.part(ref, "Device:C", x, y, rot=rot, value=val, footprint=fp,
                  fields=mfr("Murata", mpn, {"Voltage": volt, "Dielectric": diel}), **kw)


def rowtext(x, y, rot):
    """Reference left of centre and value right of centre, one line above a horizontal part."""
    j = ("left", "right") if rot == 90 else ("right", "left")
    return {"ref_at": (round(x - 0.64, 2), round(y - 2.54, 2)), "val_at": (round(x + 0.64, 2), round(y - 2.54, 2)),
            "ref_just": j[0], "val_just": j[1]}


def stub(s, p, dx, dy, name, angle):
    end = (round(p[0] + dx, 2), round(p[1] + dy, 2))
    s.wire(p, end)
    s.label(name, end, angle)


def gnd(s, p, rot=0):
    s.power("power:GND", *p, rot)


def tie_h(s, p, net, side):
    """Connect a horizontal pin end to a net (label or GND) on the left or right."""
    d = -2.54 if side == "L" else 2.54
    end = (round(p[0] + d, 2), p[1])
    s.wire(p, end)
    if net == "GND":
        gnd(s, end, 270 if side == "L" else 90)
    else:
        s.label(net, end, 180 if side == "L" else 0)


def hrow(s, part, left, right):
    """Tie the left and right pins of a horizontal two-pin part."""
    pts = sorted((v for k, v in part.items() if k in ("1", "2")), key=lambda q: q[0])
    tie_h(s, pts[0], left, "L")
    tie_h(s, pts[1], right, "R")


def TProw(s, ref, net, x, y, mpn="5000"):
    """Test point in a row: pin at (x, y), wire to the right, then the net."""
    tp = s.part(ref, "Connector:TestPoint", x, y, value=net, footprint=FP_TP,
                fields=mfr("Keystone Electronics", mpn), hide_value=True,
                ref_at=(round(x - 1.27, 2), round(y - 1.27, 2)), ref_just="right")
    s.wire(tp["1"], (round(x + 3.81, 2), y))
    tie_h(s, (round(x + 3.81, 2), y), net, "R")
    return tp


class Rows:
    """Column of horizontal parts at x, rows every 5.08 mm from y0."""

    def __init__(self, s, x, y0):
        self.s, self.x, self.y = s, x, y0

    def nxt(self):
        y = self.y
        self.y = round(self.y + 5.08, 2)
        return self.x, y

    def r(self, ref, val, a, b, **kw):
        x, y = self.nxt()
        hrow(self.s, R(self.s, ref, x, y, val, **kw, **rowtext(x, y, 90)), a, b)

    def c(self, ref, val, volt, mpn, fp, a, b, diel="X7R"):
        x, y = self.nxt()
        hrow(self.s, C(self.s, ref, x, y, val, volt, mpn, fp, diel=diel, **rowtext(x, y, 90)), a, b)

    def d(self, ref, lib, value, mpn, m, fp, ds, k_net, a_net, kpin="1", apin="2"):
        x, y = self.nxt()
        p = self.s.part(ref, lib, x, y, value=value, footprint=fp, datasheet=ds, fields=mfr(m, mpn),
                        **rowtext(x, y, 0))
        hrow(self.s, {"1": p[kpin], "2": p[apin]}, k_net, a_net)

    def tp(self, ref, net, mpn="5000"):
        x, y = self.nxt()
        TProw(self.s, ref, net, x - 3.81, y, mpn)


C1U = ("1u", "16V", "GRM188R71C105KA12D", FP_C0603)
C10U = ("10u", "50V", "GRM32ER71H106KA12L", FP_C1210)
C100N = ("100n", "50V", "GRM188R71H104KA93D", FP_C0603)


def build(symdir):
    s = Sheet(symdir)

    # =================== region A: current path and FET drive ===================
    Y0, Y = 45.72, 81.28
    j1 = s.part("J1", "Connector_Generic:Conn_01x02", 17.78, 58.42, mirror="y", value="BATT",
                footprint=FP_PADS, fields={"Manufacturer": "none", "MPN": "PCB solder pads (no part)"},
                ref_at=(17.78, 53.34), val_at=(17.78, 66.04), just="")
    j2 = s.part("J2", "Connector_Generic:Conn_01x02", 139.7, 58.42, value="PACK",
                footprint=FP_PADS, fields={"Manufacturer": "none", "MPN": "PCB solder pads (no part)"},
                ref_at=(137.16, 54.61), val_at=(132.08, 66.04), just="left")
    s.wire(j1["1"], (25.4, 58.42), (25.4, Y0), (119.38, Y0), (127.0, Y0), (127.0, 58.42), j2["1"])
    s.label("PACK_P", (30.48, Y0))
    d1 = s.part("D1", "Diode:1.5SMCxxA", 119.38, 49.53, rot=270, value="SMCJ26A", footprint="Diode_SMD:D_SMC",
                datasheet=DS["smcj"], fields=mfr("Littelfuse", "SMCJ26A"), ref_at=(121.92, 48.26), val_at=(121.92, 50.8))
    s.junction(d1["1"])
    stub(s, d1["2"], 0, 2.54, "PACK_N", 270)

    s.wire(j1["2"], (27.94, 60.96), (27.94, Y), (33.02, Y))
    gnd(s, (27.94, Y))
    s.power("power:PWR_FLAG", 27.94, 60.96, 270)
    r1 = s.part("R1", "Device:R_Shunt", 38.1, Y, rot=90, value="1m",
                footprint="Resistor_SMD:R_Shunt_Vishay_WSK2512_6332Metric_T2.21mm", datasheet=DS["wsk"],
                fields=mfr("Vishay Dale", "WSK25121L000FEA", {"Tolerance": "1%", "Power": "1W @70C",
                                                               "Note": "MPN built from datasheet numbering rule"}),
                ref_at=(38.1, Y + 3.81), val_at=(38.1, Y + 6.35), just="")
    stub(s, r1["2"], 0, -2.54, "SH_P", 90)
    stub(s, r1["3"], 0, -2.54, "SH_N", 90)
    q1 = s.part("Q1", "Transistor_FET:IPT012N08N5", 55.88, Y - 2.54, rot=270, value="IPT012N08N5 (DSG)",
                footprint=FP_TOLL, datasheet=DS["ipt"], fields=mfr("Infineon", "IPT012N08N5ATMA1"),
                ref_at=(55.88, Y + 3.81), val_at=(55.88, Y + 6.35), just="")
    q2 = s.part("Q2", "Transistor_FET:IPT012N08N5", 73.66, Y + 2.54, rot=90, value="IPT012N08N5 (CHG)",
                footprint=FP_TOLL, datasheet=DS["ipt"], fields=mfr("Infineon", "IPT012N08N5ATMA1"),
                ref_at=(81.28, Y + 6.35), val_at=(81.28, Y + 8.89), just="left")
    s.wire(r1["4"], q1["2"])
    s.label("SNS", (45.72, Y))
    s.wire(q1["3"], q2["3"])
    s.label("MID", (63.5, Y))
    s.wire(q2["2"], (129.54, Y), (129.54, 60.96), j2["2"])
    s.label("PACK_N", (83.82, Y))
    stub(s, q1["1"], 0, -2.54, "GDSG", 90)
    stub(s, q2["1"], 0, 2.54, "GCHG", 270)

    ga = Rows(s, 58.42, 50.8)
    ga.r("R2", "100R", "DSG", "GDSG")
    ga.r("R3", "1M", "GDSG", "SNS")
    ga.d("D2", "Diode:1N4148W", "1N4148W", "1N4148W-V-GS08", "Vishay", FP_SOD123, DS["1n4148w"], "CHGD", "CHG")
    gb = Rows(s, 96.52, 50.8)
    gb.r("R4", "1k", "CHGD", "GCHG")
    gb.r("R5", "100k", "GCHG", "PACK_N")
    gb.d("D3", "Diode:BZX84Cxx", "BZX84-C15", "BZX84-C15,215", "Nexperia", "Package_TO_SOT_SMD:SOT-23",
         DS["bzx"], "GCHG", "PACK_N", kpin="3", apin="1")
    for ref, net, x, mpn in (("TP1", "GND", 33.02, "5001"), ("TP2", "GDSG", 50.8, "5000"),
                             ("TP3", "GCHG", 93.98, "5000"), ("TP4", "PACK_N", 114.3, "5000")):
        TProw(s, ref, net, x, 96.52, mpn)

    # =================== region B: REGSRC cascode, host port, boot, NTC ===================
    q3 = s.part("Q3", "Transistor_FET:2N7002", 177.8, 60.96, footprint="Package_TO_SOT_SMD:SOT-23",
                datasheet=DS["2n7002"], fields=mfr("Nexperia", "2N7002,215"),
                ref_at=(183.52, 59.69), val_at=(183.52, 62.23))
    stub(s, q3["1"], -5.08, 0, "GCAS", 180)
    stub(s, q3["3"], 0, -2.54, "PACK_P", 90)
    fl = (q3["2"][0], round(q3["2"][1] + 1.27, 2))
    s.wire(q3["2"], fl, (q3["2"][0], round(q3["2"][1] + 2.54, 2)))
    s.label("REGSRC", (q3["2"][0], round(q3["2"][1] + 2.54, 2)), 270)
    s.power("power:PWR_FLAG", *fl, 90)
    b1 = Rows(s, 205.74, 40.64)
    b1.r("R6", "1M", "PACK_P", "GCAS")
    b1.d("D4", "Diode:BZX84Cxx", "BZX84-C18", "BZX84-C18,215", "Nexperia", "Package_TO_SOT_SMD:SOT-23",
         DS["bzx"], "GCAS", "GND", kpin="3", apin="1")
    b1.c("C1", *C10U, "REGSRC", "GND")
    b1.r("R7", "1k", "TAP1", "BOOTSW")
    x, y = b1.nxt()
    sw = s.part("SW1", "Switch:SW_Push", x, y, value="BOOT", footprint="Button_Switch_SMD:SW_SPST_B3U-1000P",
                datasheet=DS["b3u"], fields=mfr("Omron", "B3U-1000P", {"Rating": "50 mA, 12 V (distributor listing)"}),
                **rowtext(x, y, 0))
    hrow(s, sw, "BOOTSW", "TS1")
    b1.r("R8", "1k", "BOOT", "TS1")
    b2 = Rows(s, 238.76, 40.64)
    b2.r("R9", "10k", "REGOUT", "SDA")
    b2.r("R10", "10k", "REGOUT", "SCL")
    b2.r("R11", "499k", "ALERT", "GND")
    b2.c("C2", "470p", "50V", "GRM1885C1H471JA01D", FP_C0603, "ALERT", "GND", diel="C0G")
    j5 = s.part("J5", "Connector_Generic:Conn_01x06", 274.32, 50.8, value="HOST (I2C)",
                footprint="Connector_JST:JST_GH_SM06B-GHS-TB_1x06-1MP_P1.25mm_Horizontal", datasheet=DS["jstgh"],
                fields=mfr("JST", "SM06B-GHS-TB(LF)(SN)", {"Rating": "1 A per contact, 50 V"}),
                ref_at=(271.78, 40.64), val_at=(271.78, 60.96), just="")
    for pin, net in (("1", "REGOUT"), ("2", "SDA"), ("3", "SCL"), ("4", "ALERT"), ("5", "BOOT")):
        stub(s, j5[pin], -5.08, 0, net, 180)
    tie_h(s, j5["6"], "GND", "L")
    j4 = s.part("J4", "Connector_Generic:Conn_01x02", 274.32, 76.2, value="NTC 103AT",
                footprint="Connector_JST:JST_GH_SM02B-GHS-TB_1x02-1MP_P1.25mm_Horizontal", datasheet=DS["jstgh"],
                fields=mfr("JST", "SM02B-GHS-TB(LF)(SN)", {"Note": "10k 103AT NTC on the cells, off-board"}),
                ref_at=(271.78, 71.12), val_at=(271.78, 81.28), just="")
    stub(s, j4["1"], -5.08, 0, "TS1", 180)
    tie_h(s, j4["2"], "GND", "L")

    # =================== region C: BQ76930 and cell filters ===================
    ux, uy = 88.9, 133.35
    u1 = s.part("U1", "Battery_Management:BQ76930DBT", ux, uy, value="BQ7693002DBT",
                footprint="Package_SO:TSSOP-30_4.4x7.8mm_P0.5mm", datasheet=DS["bq"],
                fields=mfr("Texas Instruments", "BQ7693002DBT", {"Variant": "REGOUT 3.3 V, I2C 0x08, no CRC"}),
                ref_at=(ux + 2.54, uy + 30.48), val_at=(ux + 2.54, uy + 33.02))
    s.wire(u1["9"], (ux + 5.08, u1["9"][1]))
    s.label("REGSRC", (ux + 5.08, u1["9"][1]))
    gnd(s, u1["3"])
    for pin, net in (("4", "SDA"), ("5", "SCL"), ("30", "ALERT"), ("13", "TS2"), ("10", "VC5X"),
                     ("6", "TS1"), ("7", "CAP1"), ("1", "DSG"), ("2", "CHG")):
        stub(s, u1[pin], -5.08, 0, net, 180)
    # CAP2 with the two NC pins that the datasheet says to short to CAP2
    xt = round(u1["14"][0] - 2.54, 2)
    s.wire(u1["14"], (xt, u1["14"][1]), (round(u1["14"][0] - 5.08, 2), u1["14"][1]))
    s.label("CAP2", (round(u1["14"][0] - 5.08, 2), u1["14"][1]), 180)
    s.wire((xt, u1["14"][1]), (xt, u1["11"][1]), (xt, u1["12"][1]))
    s.wire(u1["11"], (xt, u1["11"][1]))
    s.wire(u1["12"], (xt, u1["12"][1]))
    s.junction((xt, u1["14"][1]))
    s.junction((xt, u1["11"][1]))
    for pin, net in (("8", "REGOUT"), ("15", "BATF"), ("16", "IN6"), ("20", "IN4"), ("21", "IN3B"),
                     ("22", "IN3"), ("26", "IN1"), ("27", "IN0"), ("28", "SRP"), ("29", "SRN")):
        stub(s, u1[pin], 5.08, 0, net, 0)
    # unused inputs for 6 cells (datasheet Table 9-3): VC7=VC8=VC9 and VC2=VC3=VC4
    xr = round(u1["16"][0] + 2.54, 2)
    for top, mid, bot, net in (("17", "18", "19", "IN5"), ("23", "24", "25", "IN2")):
        for p in (top, mid, bot):
            s.wire(u1[p], (xr, u1[p][1]))
        s.wire((xr, u1[top][1]), (xr, u1[mid][1]), (xr, u1[bot][1]))
        s.junction((xr, u1[mid][1]))
        stub(s, (xr, u1[mid][1]), 2.54, 0, net, 0)

    ca = Rows(s, 33.02, 109.22)
    ca.c("C3", *C10U, "CAP1", "GND")
    ca.c("C4", *C10U, "CAP2", "VC5X")
    ca.r("R12", "10k", "TS2", "VC5X")
    ca.c("C5", *C1U, "REGOUT", "GND")
    ca.c("C6", *C1U, "REGOUT", "GND")
    ca.r("R13", "100R", "SH_P", "SRP")
    ca.r("R14", "100R", "SH_N", "SRN")
    ca.c("C7", *C100N, "SRP", "SRN")
    ca.tp("TP5", "VC5X")
    ca.tp("TP6", "TS1")
    ca.tp("TP7", "REGOUT")

    cr = Rows(s, 133.35, 106.68)
    for i, (ref, tap, net) in enumerate((("R15", "TAP0", "IN0"), ("R16", "TAP1", "IN1"), ("R17", "TAP2", "IN2"),
                                          ("R18", "TAP3", "IN3"), ("R19", "TAP3", "IN3B"), ("R20", "TAP4", "IN4"),
                                          ("R21", "TAP5", "IN5"), ("R22", "TAP6", "IN6"))):
        cr.r(ref, "1k", tap, net)
    cc = Rows(s, 161.29, 106.68)
    for ref, a, b in (("C8", "IN0", "GND"), ("C9", "IN1", "IN0"), ("C10", "IN2", "IN1"), ("C11", "IN3", "IN2"),
                      ("C12", "IN3B", "VC5X"), ("C13", "IN4", "IN3B"), ("C14", "IN5", "IN4"), ("C15", "IN6", "IN5")):
        cc.c(ref, *C1U, a, b)
    cp = Rows(s, 189.23, 106.68)
    cp.r("R23", "100R", "TAP3", "VC5X")
    cp.c("C16", *C10U, "VC5X", "GND")
    cp.d("D5", "Diode:1N4148W", "1N4148W", "1N4148W-V-GS08", "Vishay", FP_SOD123, DS["1n4148w"], "VC5X", "IN3")
    cp.r("R24", "100R", "PACK_P", "BATF")
    cp.c("C17", *C10U, "BATF", "GND")
    cp.d("D6", "Diode:1N4148W", "1N4148W", "1N4148W-V-GS08", "Vishay", FP_SOD123, DS["1n4148w"], "BATF", "IN6")
    cp.tp("TP8", "REGSRC")
    cp.tp("TP9", "ALERT")

    j3 = s.part("J3", "Connector_Generic:Conn_01x07", 236.22, 129.54, value="BALANCE (6S)",
                footprint="Connector_JST:JST_XH_B7B-XH-A_1x07_P2.50mm_Vertical", datasheet=DS["jstxh"],
                fields=mfr("JST", "B7B-XH-A(LF)(SN)", {"Rating": "3 A, 250 V", "Note": "pin 1 = B- (black): check your pack lead"}),
                ref_at=(238.76, 119.38), val_at=(238.76, 140.97), just="left")
    for i in range(7):
        stub(s, j3[str(i + 1)], -5.08, 0, f"TAP{i}", 180)

    # =================== annotations ===================
    s.rect(11.43, 30.48, 153.67, 100.33)
    s.text("CURRENT PATH (low side): B- -> R1 1 mOhm -> Q1 DSG -> Q2 CHG -> P-. B+ = P+.", 12.7, 31.75, 1.2, True)
    s.text("GND = cell-stack negative (B-, BQ76930 VSS). PACK_N is NOT ground.", 12.7, 34.29, 1.2)
    s.rect(156.21, 30.48, 285.75, 100.33)
    s.text("REGSRC CASCODE, HOST PORT (I2C 0x08, REGOUT 3.3 V <= 10 mA), BOOT, NTC", 157.48, 31.75, 1.2, True)
    s.text("Boot: press SW1 (cell 1+ via R7 to TS1) or drive J5 BOOT high (<= 5 V).", 157.48, 92.71, 1.2)
    s.rect(11.43, 102.87, 285.75, 167.64)
    s.text("BQ76930 AFE AND CELL FILTERS", 12.7, 104.14, 1.2, True)

    s.text("WARNING: Reference design. Test first with a current-limited supply and protection. "
           "Not for unattended use.", 12.7, 21.59, 1.8, True)
    s.text("Design only, not fabricated, not bench-tested. Protection board that needs a programmed host MCU on J5: "
           "it does nothing useful on its own. Not certified.", 12.7, 25.4, 1.4)
    notes = [
        "KEY VALUES (README has the derivations and sources)",
        "Host writes: PROTECT1 0x0C (SCD 66.6 mV = 66.6 A, 100 us), PROTECT2 0x58 (OCD 30.6 A, 320 ms), OV_TRIP 0xB7 (4.25 V), UV_TRIP 0xEA (3.0 V), PROTECT3 0x50.",
        "Q1/Q2 1.2 mOhm max each; 20 A continuous design target. No hardware over-temperature or charge over-current: the host must do both.",
        "CHG: D2 + R5 100k keep Q2 off (VGS <= 1.2 V) when a charger pulls PACK_N below GND with CHG disabled.",
        "REGSRC = 2N7002 cascode, BZX84-C18 gate: 12.1-14.9 V simulated for a 15-25.2 V pack.",
        "Balancing is internal only: about 1.9 mA through 2 x 1 kOhm (TI recommends external balancing for BQ76930).",
        "6-cell map (datasheet Table 9-3): VC2=VC3=VC4 and VC7=VC8=VC9 tied. Connect B- first, then the balance lead, then B+.",
    ]
    for i, t in enumerate(notes):
        s.text(t, 12.7, 170.18 + i * 3.3, 1.2, bold=(i == 0))

    tb = ["title_block",
          ["title", Q("6S BMS: BQ76930 protection board")],
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
