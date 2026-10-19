#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Generate hardware/drone-pdb.kicad_sch: 4S/6S drone power board with XT60
input, low-side anti-spark switch with precharge, INA226 current sense,
5 V and 12 V BECs (TPS54360) and a low-voltage buzzer, from stock KiCad 9
library symbols.

    python3 gen_schematic.py --symdir /usr/share/kicad/symbols
"""
import argparse
import os

import kicadgen as kg
from kicadgen import Q, Sheet

FP_R0603 = "Resistor_SMD:R_0603_1608Metric"
FP_R0805 = "Resistor_SMD:R_0805_2012Metric"
FP_R2512 = "Resistor_SMD:R_2512_6332Metric"
FP_C0603 = "Capacitor_SMD:C_0603_1608Metric"
FP_C0805 = "Capacitor_SMD:C_0805_2012Metric"
FP_C1210 = "Capacitor_SMD:C_1210_3225Metric"
FP_CBULK = "Capacitor_THT:CP_Radial_D12.5mm_P5.00mm"
FP_TP = "TestPoint:TestPoint_Keystone_5000-5004_Miniature"
FP_ESC = "Connector_Wire:SolderWire-2.5sqmm_1x02_P7.2mm_D2.4mm_OD3.6mm"
FP_OUT = "Connector_Wire:SolderWire-0.5sqmm_1x02_P4.6mm_D0.9mm_OD2.1mm"
FP_SOD123 = "Diode_SMD:D_SOD-123"

DS = {
    "xt60": "https://mrsdprojects.ri.cmu.edu/2025teamb/wp-content/uploads/sites/84/2025/05/xt60.pdf",
    "wsk": "https://www.mouser.lt/pdfDocs/wsk2512.pdf",
    "smcj": "https://prod-parts-data.s3.amazonaws.com/SMCJ30A/datasheet/1_SMCJ30A-Littelfuse-datasheet-34142008.pdf",
    "fr": "https://docs.rs-online.com/5f62/0900766b80e4e9bf.pdf",
    "ipt": "http://www.infineon.com/dgdl/Infineon-IPT012N08N5-DS-v02_01-EN.pdf?fileId=5546d4624a75e5f1014aca59127a1eb9",
    "buk": "https://assets.nexperia.com/documents/data-sheet/BUK7M42-60E.pdf",
    "crgp": "https://4donline.ihs.com/images/VipMasterIC/IC/TYEL/TYEL-S-A0005460475/TYEL-S-A0005460475-1.pdf?hkey=52A5661711E402568146F3353EA87419",
    "bzx": "https://assets.nexperia.com/documents/data-sheet/BZX84_SER.pdf",
    "1n4148w": "https://datasheet.ciiva.com/1201/1726056-1201861.pdf",
    "jstgh": "https://www.mouser.com/datasheet/2/564/eGH-3476810.pdf",
    "ina": "https://www.ti.com/lit/ds/symlink/ina226.pdf",
    "tps": "https://www.ti.com/lit/ds/symlink/tps54360.pdf",
    "fuse": "https://4donline.ihs.com/images/VipMasterIC/IC/LFSI/LFSIS12645/LFSIS12645-1.pdf",
    "xal60": "https://www.coilcraft.com/pdfs/xal60xx.pdf",
    "ss36": "https://www.vishay.com/docs/88751/ss32.pdf",
    "mcp": "https://www.electro-tech-online.com/custompdfs/2013/06/22269A.pdf",
    "2n7002": "https://prod-parts-data.s3.amazonaws.com/2N7002,215/datasheet/1_2N70022C215-Nexperia-datasheet-10741796.pdf",
    "buz": "https://www.sameskydevices.com/product/resource/cmi-1295ic-0585t.pdf",
    "rc": "https://www.yageogroup.com/component-documentation/download/specsheet/RC0805FR-0712KL",
}


def mfr(m, mpn, extra=None):
    d = {"Manufacturer": m, "MPN": mpn}
    d.update(extra or {})
    return d


def yageo(val):
    """Yageo RC-series value code for a value string like '22k', '1M', '10R', '38.3k'."""
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
    mpn = mpn or f"RC{'0603' if fp == FP_R0603 else '0805'}FR-07{yageo(val)}L"
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
    """Connect a horizontal pin end to a net: label, GND or a power rail, on the left or right."""
    d = -2.54 if side == "L" else 2.54
    end = (round(p[0] + d, 2), p[1])
    if net == "GND":
        s.wire(p, end)
        gnd(s, end, 270 if side == "L" else 90)
    elif net in ("+5V", "+12V"):
        s.wire(p, end)
        s.power(f"power:{net}", *end, 90 if side == "L" else 270)
    else:
        s.wire(p, end)
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


def conn2(s, ref, x, y, value, fp, top, bot="GND", fields=None, ds=""):
    """Two-pin connector with pins on its left at (x - 5.08, y) and (x - 5.08, y + 2.54)."""
    j = s.part(ref, "Connector_Generic:Conn_01x02", x, y, value=value, footprint=fp, datasheet=ds,
               fields=fields or {"Manufacturer": "none", "MPN": "PCB solder pads (no part)"},
               ref_at=(round(x + 2.54, 2), y), val_at=(round(x + 2.54, 2), round(y + 2.54, 2)), just="left")
    tie_h(s, j["1"], top, "L")
    tie_h(s, j["2"], bot, "L")
    return j


def bec(s, ox, oy, n, tag, vout_net, parts):
    """One TPS54360 BEC band. n maps roles to references; tag is '5' or '12'."""
    VIN, EN, RT, BOOT, SW, COMP, FB, CZ = (f"{x}{tag}" for x in ("VIN", "EN", "RT", "BOOT", "SW", "COMP", "FB", "CZ"))
    ux, uy = ox + 25.4, oy + 16.51
    u = s.part(n["U"], "Regulator_Switching:TPS54360DDA", ux, uy, footprint="Package_SO:TI_SO-PowerPAD-8_ThermalVias",
               datasheet=DS["tps"], fields=mfr("Texas Instruments", "TPS54360DDAR"),
               ref_at=(ox + 1.27, oy + 29.21), val_at=(ox + 1.27, oy + 31.75))
    fl = (round(u["2"][0] - 2.54, 2), u["2"][1])
    vend = (round(u["2"][0] - 5.08, 2), u["2"][1])
    s.wire(u["2"], fl, vend)
    s.label(VIN, vend, 180)
    s.power("power:PWR_FLAG", *fl)
    stub(s, u["4"], -5.08, 0, RT, 180)
    stub(s, u["3"], -5.08, 0, EN, 180)
    for pin, net in (("1", BOOT), ("8", SW), ("6", COMP), ("5", FB)):
        stub(s, u[pin], 5.08, 0, net, 0)
    s.wire(u["7"], u["9"])
    gnd(s, u["9"])

    xs = [ox + 63.5 + 27.94 * j for j in range(4)]
    ys = [oy + 6.35 + 5.08 * k for k in range(6)]
    slots = [(x, y) for x in xs for y in ys]
    it = iter(slots)

    def nxt():
        return next(it)

    def r_(ref, val, a, b):
        x, y = nxt()
        hrow(s, R(s, ref, x, y, val, **rowtext(x, y, 90)), a, b)

    def c_(ref, val, volt, mpn, fp, a, b, diel="X7R"):
        x, y = nxt()
        hrow(s, C(s, ref, x, y, val, volt, mpn, fp, diel=diel, **rowtext(x, y, 90)), a, b)

    x, y = nxt()
    hrow(s, s.part(n["F"], "Device:Fuse", x, y, rot=90, value="3A 32V", footprint="Fuse:Fuse_1206_3216Metric",
                   datasheet=DS["fuse"], fields=mfr("Littelfuse", "0466003.NRHF", {"Type": "Very fast-acting, 1206"}),
                   **rowtext(x, y, 90)), "VBAT", VIN)
    for ref in n["CIN"]:
        c_(ref, "10u", "50V", "GRM32ER71H106KA12L", FP_C1210, VIN, "GND")
    c_(n["CHF"], "100n", "50V", "GRM188R71H104KA93D", FP_C0603, VIN, "GND")
    r_(n["RUV1"], "294k", VIN, EN)
    r_(n["RUV2"], "38.3k", EN, "GND")
    for ref in n["CEN"]:
        c_(ref, "22u", "16V", "GRM32ER71C226KE18L", FP_C1210, EN, "GND")
    r_(n["RRT"], "162k", RT, "GND")
    c_(n["CBOOT"], "100n", "50V", "GRM188R71H104KA93D", FP_C0603, BOOT, SW)
    x, y = nxt()
    hrow(s, s.part(n["D"], "Diode:SS36", x, y, footprint="Diode_SMD:D_SMC", datasheet=DS["ss36"],
                   fields=mfr("Vishay", "SS36-E3/57T", {"Note": "Vishay SS36 is SMC (DO-214AB); library default D_SMA overridden"}),
                   **rowtext(x, y, 0)), SW, "GND")
    x, y = nxt()
    hrow(s, s.part(n["L"], "Device:L", x, y, rot=90, value=parts["l"], footprint="Inductor_SMD:L_Coilcraft_XAL6060-XXX",
                   datasheet=DS["xal60"], fields=mfr("Coilcraft", parts["l_mpn"], parts["l_fields"]),
                   **rowtext(x, y, 90)), SW, vout_net)
    for ref in n["COUT"]:
        c_(ref, parts["cout"], parts["cout_v"], parts["cout_mpn"], FP_C1210, vout_net, "GND")
    r_(n["RFB1"], parts["rfb1"], vout_net, FB)
    r_(n["RFB2"], parts["rfb2"], FB, "GND")
    r_(n["RC"], parts["rc"], COMP, CZ)
    c_(n["CC"], parts["cc"], "50V", parts["cc_mpn"], FP_C0603, CZ, "GND")
    c_(n["CHF2"], "68p", "50V", "GRM1885C1H680JA01D", FP_C0603, COMP, "GND", diel="C0G")
    x, y = nxt()
    TProw(s, n["TP"], vout_net, x - 3.81, y)
    x, y = nxt()
    TProw(s, n["TPEN"], EN, x - 3.81, y)
    x, y = nxt()
    j = conn2(s, n["J"], x + 1.27, y, f"{parts['name']} out", FP_OUT, vout_net)
    if tag == "12":
        # +12V has no power output pin on it (it is fed through L2): flag it here
        p = (ox + 40.64, oy + 29.21)
        s.power(f"power:{vout_net}", *p)
        s.wire(p, (p[0], p[1] + 2.54))
        s.power("power:PWR_FLAG", p[0], p[1] + 2.54, 90)


def build(symdir):
    s = Sheet(symdir)

    # =================== region 1: input, shunt, anti-spark ===================
    Y1 = 45.72
    j1 = s.part("J1", "Connector_Generic:Conn_01x02", 20.32, Y1, mirror="y", value="XT60-M",
                footprint="Connector_AMASS:AMASS_XT60-M_1x02_P7.20mm_Vertical", datasheet=DS["xt60"],
                fields=mfr("AMASS", "XT60-M", {"Rating": "30 A cont, 60 A burst", "Note": "pin 1 = BAT+: check pad 1 vs housing marking"}),
                ref_at=(15.24, 52.07), val_at=(15.24, 54.61), just="")
    r1 = s.part("R1", "Device:R_Shunt", 38.1, Y1, rot=90, value="0.5m",
                footprint="Resistor_SMD:R_Shunt_Vishay_WSK2512_6332Metric_T2.66mm", datasheet=DS["wsk"],
                fields=mfr("Vishay Dale", "WSK25120L500FEA", {"Tolerance": "1%", "Power": "1W @70C",
                                                               "Note": "MPN built from datasheet numbering rule"}),
                ref_at=(38.1, 50.8), val_at=(38.1, 53.34), just="")
    s.wire(j1["1"], r1["1"])
    s.label("BAT_IN", (26.67, Y1))
    s.wire(r1["2"], (r1["2"][0], 39.37), (33.02, 39.37))
    s.label("SENSE_P", (33.02, 39.37), 180)
    s.wire(r1["3"], (r1["3"][0], 39.37), (43.18, 39.37))
    s.label("SENSE_N", (43.18, 39.37))
    d1 = s.part("D1", "Diode:1.5SMCxxA", 55.88, 49.53, rot=270, value="SMCJ26A", footprint="Diode_SMD:D_SMC",
                datasheet=DS["smcj"], fields=mfr("Littelfuse", "SMCJ26A"), ref_at=(58.42, 48.26), val_at=(58.42, 50.8))
    c1 = s.part("C1", "Device:C_Polarized", 68.58, 49.53, value="470u", footprint=FP_CBULK, datasheet=DS["fr"],
                fields=mfr("Panasonic", "EEU-FR1H471", {"Voltage": "50V", "Type": "Al electrolytic, FR"}),
                ref_at=(71.12, 48.26), val_at=(71.12, 50.8))
    c2 = s.part("C2", "Device:C_Polarized", 78.74, 49.53, value="470u", footprint=FP_CBULK, datasheet=DS["fr"],
                fields=mfr("Panasonic", "EEU-FR1H471", {"Voltage": "50V", "Type": "Al electrolytic, FR"}),
                ref_at=(81.28, 48.26), val_at=(81.28, 50.8))
    c3 = C(s, "C3", 88.9, 49.53, "10u", "50V", "GRM32ER71H106KA12L", FP_C1210, rot=0,
           ref_at=(91.44, 48.26), val_at=(91.44, 50.8))
    tp1 = s.part("TP1", "Connector:TestPoint", 50.8, Y1, value="VBAT", footprint=FP_TP, hide_value=True,
                 fields=mfr("Keystone Electronics", "5000"), ref_at=(52.07, 41.91))
    rail = [r1["4"], tp1["1"], d1["1"], c1["1"], c2["1"], c3["1"]]
    s.wire(*rail)
    for p in rail[1:-1]:
        s.junction(p)
    s.label("VBAT", (44.45, Y1))
    for c in (d1, c1, c2, c3):
        gnd(s, c["2"])

    for ref, x, y, name in (("J3", 109.22, 36.83, "ESC1"), ("J4", 109.22, 43.18, "ESC2"),
                            ("J5", 137.16, 36.83, "ESC3"), ("J6", 137.16, 43.18, "ESC4")):
        conn2(s, ref, x, y, name, FP_ESC, "VBAT")

    Y2 = 63.5
    fx = {"Q1": 55.88, "Q2": 86.36, "Q3": 106.68}
    s.wire(j1["2"], (29.21, 48.26), (29.21, Y2), (fx["Q1"] + 2.54, Y2), (fx["Q2"] + 2.54, Y2), (fx["Q3"] + 2.54, Y2))
    s.label("BAT_N", (31.75, Y2))
    fets = []
    for ref, rg_ref in (("Q1", "R2"), ("Q2", "R3")):
        x = fx[ref]
        q = s.part(ref, "Transistor_FET:IPT012N08N5", x, Y2 + 5.08, rot=180, mirror="y",
                   footprint="Package_TO_SOT_SMD:Infineon_PG-HSOF-8-1", datasheet=DS["ipt"],
                   fields=mfr("Infineon", "IPT012N08N5ATMA1"),
                   ref_at=(x + 5.08, Y2 + 12.7), val_at=(x + 5.08, Y2 + 15.24))
        fets.append(q)
        s.junction(q["2"])
        gnd(s, q["3"])
        gxp = q["1"][0]
        rg = R(s, rg_ref, gxp - 3.81, Y2 + 5.08, "10R", **rowtext(gxp - 3.81, Y2 + 5.08, 90))
        stub(s, rg["1"], -2.54, 0, "GATE_M", 180)
    s.power("power:PWR_FLAG", fets[0]["3"][0], fets[0]["3"][1], 270)
    x = fx["Q3"]
    q3 = s.part("Q3", "Transistor_FET:BUK7M42-60EX", x, Y2 + 5.08, rot=180, mirror="y",
                footprint="Package_TO_SOT_SMD:LFPAK33", datasheet=DS["buk"], fields=mfr("Nexperia", "BUK7M42-60EX"),
                ref_at=(x + 5.08, Y2 + 12.7), val_at=(x + 5.08, Y2 + 15.24))
    stub(s, q3["5"], 0, 2.54, "PRE_D", 270)
    stub(s, q3["4"], -2.54, 0, "GATE_P", 180)
    for (ra, rb), y in ((("R4", "R5"), 88.9), (("R6", "R7"), 93.98)):
        a = R(s, ra, 104.14, y, "10R", fp=FP_R2512, mpn="CRGP2512F10R", m="TE Connectivity", ds=DS["crgp"],
              **rowtext(104.14, y, 90))
        b = R(s, rb, 114.3, y, "10R", fp=FP_R2512, mpn="CRGP2512F10R", m="TE Connectivity", ds=DS["crgp"],
              **rowtext(114.3, y, 90))
        s.wire(a["2"], b["1"])
        tie_h(s, a["1"], "PRE_D", "L")
        tie_h(s, b["2"], "GND", "R")

    gx, gy = 137.16, [52.07 + 5.08 * k for k in range(7)]
    hrow(s, R(s, "R9", gx, gy[0], "22k", **rowtext(gx, gy[0], 90)), "VBAT", "GSUP")
    d2 = s.part("D2", "Diode:BZX84Cxx", gx, gy[1], value="BZX84-C12", footprint="Package_TO_SOT_SMD:SOT-23",
                datasheet=DS["bzx"], fields=mfr("Nexperia", "BZX84-C12,215"), **rowtext(gx, gy[1], 0))
    hrow(s, {"1": d2["3"], "2": d2["1"]}, "GSUP", "BAT_N")
    hrow(s, R(s, "R8", gx, gy[2], "10k", **rowtext(gx, gy[2], 90)), "GSUP", "GATE_P")
    hrow(s, R(s, "R10", gx, gy[3], "1M", **rowtext(gx, gy[3], 90)), "GSUP", "GATE_M")
    hrow(s, C(s, "C4", gx, gy[4], "1u", "50V", "GRM21BR71H105KA12L", FP_C0805, **rowtext(gx, gy[4], 90)),
         "GATE_M", "BAT_N")
    d3 = s.part("D3", "Diode:1N4148W", gx, gy[5], footprint=FP_SOD123, datasheet=DS["1n4148w"],
                fields=mfr("Vishay", "1N4148W-V-GS08"), **rowtext(gx, gy[5], 0))
    hrow(s, d3, "GX", "GATE_M")
    hrow(s, R(s, "R11", gx, gy[6], "100R", **rowtext(gx, gy[6], 90)), "GX", "GSUP")
    conn2(s, "J2", gx + 3.81, 88.9, "DISARM", "Connector_JST:JST_GH_SM02B-GHS-TB_1x02-1MP_P1.25mm_Horizontal",
          "GSUP", "BAT_N", fields=mfr("JST", "SM02B-GHS-TB(LF)(SN)", {"Note": "plug = disarmed (remove before flight)"}),
          ds=DS["jstgh"])
    for ref, net, x in (("TP2", "BAT_N", 38.1), ("TP3", "GSUP", 55.88), ("TP4", "GATE_M", 73.66)):
        TProw(s, ref, net, x, 92.71, "5001" if net == "BAT_N" else "5000")

    # =================== region 2: INA226 and flight-controller port ===================
    ux, uy = 185.42, 62.23
    u1 = s.part("U1", "Sensor_Energy:INA226", ux, uy, footprint="Package_SO:VSSOP-10_3x3mm_P0.5mm",
                datasheet=DS["ina"], fields=mfr("Texas Instruments", "INA226AIDGSR"),
                ref_at=(ux + 2.54, uy + 16.51), val_at=(ux + 2.54, uy + 19.05))
    stub(s, u1["8"], -5.08, 0, "VBAT", 180)
    stub(s, u1["10"], -5.08, 0, "INA_P", 180)
    stub(s, u1["9"], -5.08, 0, "INA_N", 180)
    s.wire(u1["6"], (ux, 46.99), (ux, 44.45))
    s.label("3V3_FC", (ux, 44.45), 90)
    s.power("power:PWR_FLAG", ux, 46.99, 90)
    gnd(s, u1["7"])
    for pin in ("1", "2"):
        s.wire(u1[pin], (u1[pin][0] + 2.54, u1[pin][1]))
        gnd(s, (u1[pin][0] + 2.54, u1[pin][1]), 90)
    stub(s, u1["4"], 5.08, 0, "SDA", 0)
    stub(s, u1["5"], 5.08, 0, "SCL", 0)
    stub(s, u1["3"], 5.08, 0, "ALERT", 0)
    ix, iy = 228.6, [46.99 + 5.08 * k for k in range(5)]
    hrow(s, R(s, "R12", ix, iy[0], "10R", **rowtext(ix, iy[0], 90)), "SENSE_P", "INA_P")
    hrow(s, R(s, "R13", ix, iy[1], "10R", **rowtext(ix, iy[1], 90)), "SENSE_N", "INA_N")
    hrow(s, C(s, "C5", ix, iy[2], "100n", "50V", "GRM188R71H104KA93D", FP_C0603, **rowtext(ix, iy[2], 90)),
         "INA_P", "INA_N")
    hrow(s, C(s, "C6", ix, iy[3], "100n", "50V", "GRM188R71H104KA93D", FP_C0603, **rowtext(ix, iy[3], 90)),
         "3V3_FC", "GND")
    hrow(s, R(s, "R14", ix, iy[4], "10k", **rowtext(ix, iy[4], 90)), "3V3_FC", "ALERT")
    j7 = s.part("J7", "Connector_Generic:Conn_01x06", 274.32, 55.88, value="FC port",
                footprint="Connector_JST:JST_GH_SM06B-GHS-TB_1x06-1MP_P1.25mm_Horizontal", datasheet=DS["jstgh"],
                fields=mfr("JST", "SM06B-GHS-TB(LF)(SN)", {"Rating": "1 A per contact, 50 V"}),
                ref_at=(271.78, 45.72), val_at=(271.78, 66.04), just="")
    s.wire(j7["1"], (j7["1"][0] - 2.54, j7["1"][1]))
    s.power("power:+5V", j7["1"][0] - 2.54, j7["1"][1])
    for pin, net in (("2", "3V3_FC"), ("3", "SCL"), ("4", "SDA"), ("5", "ALERT")):
        stub(s, j7[pin], -5.08, 0, net, 180)
    tie_h(s, j7["6"], "GND", "L")

    # =================== BEC bands ===================
    bec(s, 12.7, 99.06, {"U": "U2", "F": "F1", "CIN": ("C7", "C8"), "CHF": "C9", "RUV1": "R15", "RUV2": "R16",
                         "CEN": ("C10", "C11"), "RRT": "R17", "CBOOT": "C12", "D": "D4", "L": "L1",
                         "COUT": ("C13", "C14"), "RFB1": "R18", "RFB2": "R19", "RC": "R20", "CC": "C15",
                         "CHF2": "C16", "TP": "TP5", "TPEN": "TP6", "J": "J8"},
        "5", "+5V",
        {"name": "5V", "l": "10u", "l_mpn": "XAL6060-103MEC", "l_fields": {"Isat": "7.6A (30% drop)", "DCR_max": "29.8mOhm"},
         "cout": "22u", "cout_v": "16V", "cout_mpn": "GRM32ER71C226KE18L",
         "rfb1": "53.6k", "rfb2": "10.2k", "rc": "7.15k", "cc": "10n", "cc_mpn": "GRM188R71H103KA01D"})
    bec(s, 12.7, 133.35, {"U": "U3", "F": "F2", "CIN": ("C17", "C18"), "CHF": "C19", "RUV1": "R21", "RUV2": "R22",
                          "CEN": ("C20", "C21"), "RRT": "R23", "CBOOT": "C22", "D": "D5", "L": "L2",
                          "COUT": ("C23", "C24", "C25"), "RFB1": "R24", "RFB2": "R25", "RC": "R26", "CC": "C26",
                          "CHF2": "C27", "TP": "TP7", "TPEN": "TP8", "J": "J9"},
        "12", "+12V",
        {"name": "12V", "l": "22u", "l_mpn": "XAL6060-223MEC", "l_fields": {"Isat": "5.6A (30% drop)", "DCR_max": "60.6mOhm"},
         "cout": "10u", "cout_v": "50V", "cout_mpn": "GRM32ER71H106KA12L",
         "rfb1": "140k", "rfb2": "10.0k", "rc": "8.25k", "cc": "22n", "cc_mpn": "GRM188R71H223KA01D"})

    # =================== low-voltage alarm ===================
    ax, ay = 176.53, 99.06
    ux, uy = ax + 22.86, ay + 22.86
    u4 = s.part("U4", "Comparator:MCP65R41", ux, uy, footprint="Package_TO_SOT_SMD:SOT-23-6",
                datasheet=DS["mcp"], fields=mfr("Microchip", "MCP65R41T-1202E/CHY", {"VREF": "1.21 V, 2 %"}),
                ref_at=(ux + 2.54, uy + 6.35), val_at=(ux + 2.54, uy + 8.89))
    s.wire(u4["6"], (u4["6"][0], u4["6"][1] - 2.54), (u4["6"][0], u4["6"][1] - 5.08))
    s.power("power:+5V", u4["6"][0], u4["6"][1] - 5.08)
    s.power("power:PWR_FLAG", u4["6"][0], u4["6"][1] - 2.54, 90)
    s.wire(u4["5"], (u4["5"][0], u4["5"][1] - 2.54), (u4["5"][0] + 5.08, u4["5"][1] - 2.54))
    s.label("LV_REF", (u4["5"][0] + 5.08, u4["5"][1] - 2.54))
    gnd(s, u4["2"])
    stub(s, u4["3"], -5.08, 0, "LV_HYS", 180)
    stub(s, u4["4"], -5.08, 0, "LV_SENSE", 180)
    stub(s, u4["1"], 5.08, 0, "ALARM", 0)
    q4 = s.part("Q4", "Transistor_FET:2N7002", ax + 30.48, ay + 48.26, footprint="Package_TO_SOT_SMD:SOT-23",
                datasheet=DS["2n7002"], fields=mfr("Nexperia", "2N7002,215"),
                ref_at=(ax + 36.83, ay + 46.99), val_at=(ax + 36.83, ay + 49.53))
    stub(s, q4["1"], -5.08, 0, "ALARM", 180)
    stub(s, q4["3"], 0, -2.54, "BUZ_N", 90)
    gnd(s, q4["2"])
    bz = s.part("BZ1", "Device:Buzzer", ax + 22.86, ay + 59.69, value="CMI-1295IC-0585T",
                footprint="Buzzer_Beeper:Buzzer_12x9.5RM7.6", datasheet=DS["buz"],
                fields=mfr("Same Sky", "CMI-1295IC-0585T", {"Note": "5 V self-drive; 7.6 mm pitch not confirmed in datasheet text"}),
                ref_at=(ax + 26.67, ay + 58.42), val_at=(ax + 26.67, ay + 60.96))
    tie_h(s, bz["1"], "+5V", "L")
    stub(s, bz["2"], -5.08, 0, "BUZ_N", 180)

    lx = [ax + 60.96, ax + 91.44]
    ly = [ay + 6.35 + 5.08 * k for k in range(12)]
    hrow(s, R(s, "R27", lx[0], ly[0], "2M", **rowtext(lx[0], ly[0], 90)), "VBAT", "LV_SENSE")
    hrow(s, R(s, "R28", lx[0], ly[1], "187k", **rowtext(lx[0], ly[1], 90)), "LV_SENSE", "GND")
    hrow(s, R(s, "R29", lx[0], ly[2], "340k", **rowtext(lx[0], ly[2], 90)), "LV_SENSE", "LV_6S")
    jp = s.part("JP1", "Jumper:SolderJumper_2_Open", lx[0], ly[3], value="6S",
                footprint="Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm",
                fields={"Manufacturer": "none", "MPN": "PCB solder jumper (no part)", "Note": "close for 6S"},
                **rowtext(lx[0], ly[3], 0))
    hrow(s, jp, "LV_6S", "GND")
    hrow(s, C(s, "C28", lx[0], ly[4], "1u", "50V", "GRM21BR71H105KA12L", FP_C0805, **rowtext(lx[0], ly[4], 90)),
         "LV_SENSE", "GND")
    hrow(s, R(s, "R30", lx[0], ly[5], "10k", **rowtext(lx[0], ly[5], 90)), "LV_REF", "LV_HYS")
    hrow(s, R(s, "R31", lx[0], ly[6], "1M", **rowtext(lx[0], ly[6], 90)), "ALARM", "LV_HYS")
    hrow(s, R(s, "R32", lx[1], ly[0], "100k", **rowtext(lx[1], ly[0], 90)), "ALARM", "GND")
    hrow(s, C(s, "C29", lx[1], ly[1], "100n", "50V", "GRM188R71H104KA93D", FP_C0603, **rowtext(lx[1], ly[1], 90)),
         "+5V", "GND")
    d6 = s.part("D6", "Diode:1N4148W", lx[1], ly[2], footprint=FP_SOD123, datasheet=DS["1n4148w"],
                fields=mfr("Vishay", "1N4148W-V-GS08"), **rowtext(lx[1], ly[2], 0))
    hrow(s, d6, "+5V", "BUZ_N")
    TProw(s, "TP9", "LV_SENSE", lx[1] - 3.81, ly[3])
    TProw(s, "TP10", "ALARM", lx[1] - 3.81, ly[4])
    TProw(s, "TP11", "GND", lx[1] - 3.81, ly[5], "5001")

    # =================== annotations ===================
    s.rect(11.43, 30.48, 153.67, 97.79)
    s.text("BATTERY IN -> 0.5 mOhm SHUNT -> BUS (TVS, 2 x 470 uF, ESC pads)", 12.7, 31.75, 1.2, True)
    s.text("LOW-SIDE ANTI-SPARK: Q3 + 10 Ohm precharge, then Q1 || Q2", 12.7, 34.29, 1.2, True)
    s.text("All loads return through GND (PGND); nothing may connect to BAT_N.", 12.7, 95.25, 1.2)
    s.rect(156.21, 30.48, 285.75, 97.79)
    s.text("INA226 MONITOR (I2C 0x40, powered by the FC's 3.3 V) AND FC PORT", 157.48, 31.75, 1.2, True)
    s.text("CAL = 5120 (0x1400) for Current_LSB 2 mA. I2C pull-ups are on the FC.", 157.48, 93.98, 1.2)
    s.rect(11.43, 99.06, 175.26, 133.35)
    s.text("5 V BEC: TPS54360, 2 A, 600 kHz. EN RC delays start 0.35-2.5 s after the bus comes up.", 12.7, 100.33, 1.2, True)
    s.rect(11.43, 133.35, 175.26, 167.64)
    s.text("12 V BEC: TPS54360, 1.5 A, 600 kHz. On 4S it follows VIN below about 12.4 V (dropout).", 12.7, 134.62, 1.2, True)
    s.rect(175.26, 99.06, 285.75, 165.1)
    s.text("LOW-VOLTAGE BUZZER, 3.5 V/cell. JP1 open = 4S, closed = 6S", 176.53, 100.33, 1.2, True)

    s.text("WARNING: Reference design. Test first with a current-limited supply and protection. "
           "Not for unattended use.", 12.7, 21.59, 1.8, True)
    s.text("Design only, not fabricated, not bench-tested. LiPo/Li-ion drone packs: this board has no BMS function; "
           "use packs with their own protection. Never charge or store a pack through this board.", 12.7, 25.4, 1.4)
    notes = [
        "KEY VALUES (README has the derivations and sources)",
        "30 A continuous / 60 A burst (XT60). Q1 || Q2 0.6 mOhm max at VGS 10 V. Shunt 0.5 mOhm, 1 W.",
        "Precharge 10 Ohm x 2200 uF (assumed) = 22 ms; 2.5 A peak, 0.70 J in R4-R7 at 25.2 V (pulse rating unverified).",
        "Main FETs: R10 1M x C4 1u, VGS(th) after 174-465 ms, 10 V after about 1.9 s. BECs start after the main FETs conduct.",
        "J2 DISARM plug shorts GSUP: Q1-Q3 off. Disarm only with motors stopped. Disarmed draw about 1.2 mA at 25 V.",
        "SMCJ26A clamps at 42.1 V at full Ipp: above INA226 40 V abs max (TPS54360 65 V is fine).",
        "LV alarm ON below 14.0 V (4S) / 21.1 V (6S), OFF above 14.6 / 21.9 V; worst case +-0.7 / +-1.0 V.",
        "XT60 pin 1 = BAT+ is assumed: check footprint pad 1 against the housing before layout.",
    ]
    for i, t in enumerate(notes):
        s.text(t, 12.7, 170.18 + i * 3.3, 1.2, bold=(i == 0))

    tb = ["title_block",
          ["title", Q("Drone power board: 4S/6S, anti-spark, INA226, BECs")],
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
