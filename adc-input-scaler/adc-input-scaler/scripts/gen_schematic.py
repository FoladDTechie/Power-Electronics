#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Generate hardware/adc-input-scaler.kicad_sch from stock KiCad 9 library
symbols. Every symbol is copied (and, for derived symbols, flattened) from
the installed KiCad libraries; nothing is drawn by hand.

Usage:
    python3 gen_schematic.py --symdir /usr/share/kicad/symbols \
        --out ../hardware/adc-input-scaler.kicad_sch
"""
import argparse
import copy
import math
import os
import uuid as uuidlib

from sexpr import Q, dump, find, find_all, parse

PROJECT = "adc-input-scaler"
NS = uuidlib.UUID("6f1c2a52-1d1e-4c55-9a3b-1b7f0a2c0001")


def U(tag):
    """Deterministic UUID so regenerating gives a stable file."""
    return Q(str(uuidlib.uuid5(NS, tag)))


ROOT_UUID = U("root")

# ---------------------------------------------------------------------------
# Library access
# ---------------------------------------------------------------------------
_lib_cache = {}


def load_lib(symdir, lib):
    if lib not in _lib_cache:
        with open(os.path.join(symdir, lib + ".kicad_sym")) as f:
            _lib_cache[lib] = parse(f.read())[0]
    return _lib_cache[lib]


def lib_symbol(symdir, lib_id):
    """Return a flattened copy of library symbol `lib_id` named for embedding."""
    lib, name = lib_id.split(":")
    root = load_lib(symdir, lib)
    syms = {s[1]: s for s in find_all(root, "symbol")}
    sym = copy.deepcopy(syms[name])
    ext = find(sym, "extends")
    if ext is not None:
        parent = copy.deepcopy(syms[ext[1]])
        assert find(parent, "extends") is None, "nested extends not handled"
        child_props = {p[1]: p for p in find_all(sym, "property")}
        flat = [parent[0], Q(name)]
        for item in parent[2:]:
            if isinstance(item, list) and item[0] == "property":
                flat.append(child_props.pop(item[1], item))
            elif isinstance(item, list) and item[0] == "symbol":
                unit = copy.deepcopy(item)
                unit[1] = Q(item[1].replace(ext[1] + "_", name + "_", 1))
                flat.append(unit)
            else:
                flat.append(item)
        # child-only properties go after the parent's properties
        insert_at = max(i for i, x in enumerate(flat)
                        if isinstance(x, list) and x[0] == "property") + 1
        for p in child_props.values():
            flat.insert(insert_at, p)
            insert_at += 1
        sym = flat
    sym[1] = Q(lib_id)
    return sym


def lib_pins(sym):
    """{number: (x, y)} pin connection points in library coordinates (y up)."""
    pins = {}
    for unit in find_all(sym, "symbol"):
        for p in find_all(unit, "pin"):
            at = find(p, "at")
            num = find(p, "number")[1]
            pins[str(num)] = (float(at[1]), float(at[2]))
    return pins


# ---------------------------------------------------------------------------
# Geometry: library (y up) -> schematic (y down).
# KiCad applies the rotation first, then the mirror (verified against the
# exported netlist by verify_netlist.py).
# ---------------------------------------------------------------------------
def xform(px, py, x, y, rot, mirror):
    r = math.radians(rot)
    rx = px * math.cos(r) - py * math.sin(r)
    ry = px * math.sin(r) + py * math.cos(r)
    sx, sy = rx, -ry  # to screen coordinates
    if mirror == "y":
        sx = -sx
    elif mirror == "x":
        sy = -sy
    return (round(x + sx, 3), round(y + sy, 3))


# ---------------------------------------------------------------------------
# Schematic builder
# ---------------------------------------------------------------------------
def font(size=1.27, bold=False, italic=False):
    f = ["font", ["size", size, size]]
    if bold:
        f.append(["bold", "yes"])
    if italic:
        f.append(["italic", "yes"])
    return f


def prop(name, value, x, y, angle=0, hide=False, justify=None, size=1.27):
    eff = ["effects", font(size)]
    if justify:
        eff.append(["justify"] + justify.split())
    if hide:
        eff.append(["hide", "yes"])
    return ["property", Q(name), Q(value), ["at", x, y, angle], eff]


class Sheet:
    def __init__(self, symdir):
        self.symdir = symdir
        self.libsyms = {}
        self.items = []
        self.parts = {}
        self.pwr_n = 0
        self.flg_n = 0

    def _lib(self, lib_id):
        if lib_id not in self.libsyms:
            self.libsyms[lib_id] = lib_symbol(self.symdir, lib_id)
        return self.libsyms[lib_id]

    def part(self, ref, lib_id, x, y, rot=0, mirror=None, value=None,
             footprint="", datasheet="", fields=None, ref_at=None, val_at=None,
             dnp=False, in_bom=True, on_board=True, hide_value=False,
             hide_ref=False, just="left"):
        sym = self._lib(lib_id)
        lpins = lib_pins(sym)
        pins = {n: xform(px, py, x, y, rot, mirror) for n, (px, py) in lpins.items()}
        self.parts[ref] = pins
        if value is None:
            value = find_all(sym, "property")[1][2]
        ra = ref_at or (x + 2.54, y - 1.27)
        va = val_at or (x + 2.54, y + 1.27)
        node = ["symbol", ["lib_id", Q(lib_id)], ["at", x, y, rot]]
        if mirror:
            node.append(["mirror", mirror])
        node += [["unit", 1], ["exclude_from_sim", "no"],
                 ["in_bom", "yes" if in_bom else "no"],
                 ["on_board", "yes" if on_board else "no"],
                 ["dnp", "yes" if dnp else "no"],
                 ["uuid", U("sym:" + ref)]]
        # KiCad applies the symbol rotation to field text; cancel it so that
        # reference/value always read horizontally.
        fa = 90 if rot in (90, 270) else 0
        node.append(prop("Reference", ref, ra[0], ra[1], fa, hide=hide_ref, justify=just))
        node.append(prop("Value", value, va[0], va[1], fa, hide=hide_value, justify=just))
        node.append(prop("Footprint", footprint, x, y, hide=True))
        node.append(prop("Datasheet", datasheet, x, y, hide=True))
        desc = find(sym, "property") and [p for p in find_all(sym, "property")
                                          if p[1] == "Description"]
        node.append(prop("Description", desc[0][2] if desc else "", x, y, hide=True))
        for k, v in (fields or {}).items():
            node.append(prop(k, v, x, y, hide=True))
        for n in sorted(lpins):
            node.append(["pin", Q(n), ["uuid", U(f"pin:{ref}:{n}")]])
        node.append(["instances", ["project", Q(PROJECT),
                                   ["path", Q("/" + ROOT_UUID),
                                    ["reference", Q(ref)], ["unit", 1]]]])
        self.items.append(node)
        return pins

    def power(self, lib_id, x, y, rot=0):
        if lib_id == "power:PWR_FLAG":
            self.flg_n += 1
            ref = f"#FLG0{self.flg_n}"
        else:
            self.pwr_n += 1
            ref = f"#PWR0{self.pwr_n:02d}"
        sym = self._lib(lib_id)
        value = [p for p in find_all(sym, "property") if p[1] == "Value"][0][2]
        # value text placed on the far side of the symbol body
        off = {0: (0, -3.81), 180: (0, 3.81), 90: (-3.81, 0), 270: (3.81, 0)}
        if lib_id == "power:GND":
            off = {0: (0, 3.81), 180: (0, -3.81), 90: (3.81, 0), 270: (-3.81, 0)}
        if lib_id == "power:PWR_FLAG":
            off = {0: (0, -3.81), 180: (0, 3.81), 90: (-8.89, 0), 270: (8.89, 0)}
        ox, oy = off[rot]
        node = ["symbol", ["lib_id", Q(lib_id)], ["at", x, y, rot], ["unit", 1],
                ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"],
                ["dnp", "no"], ["uuid", U(f"pwr:{ref}")],
                prop("Reference", ref, x, y + 2.54, hide=True),
                prop("Value", value, x + ox, y + oy, 90 if rot in (90, 270) else 0),
                prop("Footprint", "", x, y, hide=True),
                prop("Datasheet", "", x, y, hide=True),
                prop("Description", "", x, y, hide=True),
                ["pin", Q("1"), ["uuid", U(f"pin:{ref}:1")]],
                ["instances", ["project", Q(PROJECT),
                               ["path", Q("/" + ROOT_UUID),
                                ["reference", Q(ref)], ["unit", 1]]]]]
        self.items.append(node)

    def wire(self, *pts):
        for a, b in zip(pts, pts[1:]):
            self.items.append(["wire", ["pts", ["xy", a[0], a[1]], ["xy", b[0], b[1]]],
                               ["stroke", ["width", 0], ["type", "default"]],
                               ["uuid", U(f"w:{a}:{b}")]])

    def junction(self, p):
        self.items.append(["junction", ["at", p[0], p[1]], ["diameter", 0],
                           ["color", 0, 0, 0, 0], ["uuid", U(f"j:{p}")]])

    def label(self, name, p, angle=0):
        just = {0: "left bottom", 90: "left bottom", 180: "right bottom",
                270: "right bottom"}[angle]
        self.items.append(["label", Q(name), ["at", p[0], p[1], angle],
                           ["effects", font(), ["justify"] + just.split()],
                           ["uuid", U(f"l:{name}:{p}")]])

    def text(self, s, x, y, size=1.27, bold=False):
        self.items.append(["text", Q(s.replace('"', "'")), ["exclude_from_sim", "no"],
                           ["at", x, y, 0],
                           ["effects", font(size, bold), ["justify", "left", "top"]],
                           ["uuid", U(f"t:{x}:{y}")]])

    def rect(self, x1, y1, x2, y2):
        self.items.append(["rectangle", ["start", x1, y1], ["end", x2, y2],
                           ["stroke", ["width", 0], ["type", "dash"]],
                           ["fill", ["type", "none"]], ["uuid", U(f"r:{x1}:{y1}")]])

    def serialize(self, title_block):
        root = ["kicad_sch", ["version", 20250114], ["generator", Q("eeschema")],
                ["generator_version", Q("9.0")], ["uuid", ROOT_UUID],
                ["paper", Q("A4")], title_block,
                ["lib_symbols"] + list(self.libsyms.values())]
        root += self.items
        root.append(["sheet_instances", ["path", Q("/"), ["page", Q("1")]]])
        root.append(["embedded_fonts", "no"])
        return dump(root) + "\n"


# ---------------------------------------------------------------------------
# The design
# ---------------------------------------------------------------------------
FP_R0805 = "Resistor_SMD:R_0805_2012Metric"
FP_R0603 = "Resistor_SMD:R_0603_1608Metric"
FP_C0603 = "Capacitor_SMD:C_0603_1608Metric"
FP_SOT23 = "Package_TO_SOT_SMD:SOT-23"
FP_TP = "TestPoint:TestPoint_Keystone_5000-5004_Miniature"

DS_BAT54 = "https://assets.nexperia.com/documents/data-sheet/BAT54_SER.pdf"
DS_BZX84 = "https://assets.nexperia.com/documents/data-sheet/BZX84_SER.pdf"
DS_BSS84 = "https://assets.nexperia.com/documents/data-sheet/BSS84.pdf"
DS_BSS138 = "https://www.onsemi.com/download/data-sheet/pdf/bss138-d.pdf"
DS_RT = "https://www.yageo.com/upload/media/product/productsearch/datasheet/rchip/PYu-RT_1-to-0.01_RoHS_L_11.pdf"
DS_RC = "https://www.yageogroup.com/component-documentation/download/specsheet/RC0805FR-0712KL"
DS_GRM = "https://search.murata.co.jp/Ceramy/image/img/A01X/G101/ENG/GRM188R71H104KA93-01.pdf"


def mfr(m, mpn, extra=None):
    d = {"Manufacturer": m, "MPN": mpn}
    if extra:
        d.update(extra)
    return d


def build(symdir):
    s = Sheet(symdir)
    Y = 66.04          # VIN / VSW rail
    G = 73.66          # Q1 gate node
    NODE = 78.74       # ADC_DIV node

    # --- Input connector -----------------------------------------------------
    j1 = s.part("J1", "Connector:Screw_Terminal_01x02", 22.86, Y, mirror="y",
                value="VIN 0-30 V",
                footprint="TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
                fields=mfr("Phoenix Contact", "1715721"),
                ref_at=(22.86, 62.23), val_at=(22.86, 72.39), just="")
    # --- High-side switch (variant B) ---------------------------------------
    q1 = s.part("Q1", "Transistor_FET:BSS84", 78.74, Y + 2.54, rot=90, mirror="y",
                footprint=FP_SOT23, datasheet=DS_BSS84,
                fields=mfr("Nexperia", "BSS84,215"),
                ref_at=(83.82, 72.39), val_at=(83.82, 74.93))
    r4 = s.part("R4", "Device:R", 66.04, 69.85, value="100k",
                footprint=FP_R0603, datasheet=DS_RC,
                fields=mfr("Yageo", "RC0603FR-07100KL", {"Tolerance": "1%"}))
    d2 = s.part("D2", "Diode:BZX84Cxx", 55.88, 69.85, rot=270, value="BZX84-C12",
                footprint=FP_SOT23, datasheet=DS_BZX84,
                fields=mfr("Nexperia", "BZX84-C12,215"),
                ref_at=(53.34, 68.58), val_at=(53.34, 71.12), just="right")
    r5 = s.part("R5", "Device:R", 78.74, 81.28, value="22k",
                footprint=FP_R0805, datasheet=DS_RC,
                fields=mfr("Yageo", "RC0805FR-0722KL", {"Tolerance": "1%"}))
    q2 = s.part("Q2", "Transistor_FET:BSS138", 76.2, 93.98,
                footprint=FP_SOT23, datasheet=DS_BSS138,
                fields=mfr("onsemi", "BSS138"),
                ref_at=(81.28, 92.71), val_at=(81.28, 95.25))
    r6 = s.part("R6", "Device:R", 63.5, 97.79, value="100k",
                footprint=FP_R0603, datasheet=DS_RC,
                fields=mfr("Yageo", "RC0603FR-07100KL", {"Tolerance": "1%"}))
    r7 = s.part("R7", "Device:R", 78.74, 55.88, rot=90, value="0R",
                footprint=FP_R0805, datasheet=DS_RC, dnp=True,
                fields=mfr("Yageo", "RC0805JR-070RL",
                           {"Note": "Fit ONLY for variant A (always-on); then omit Q1,Q2,D2,R4,R5,R6"}),
                ref_at=(78.74, 52.07), val_at=(78.74, 59.69), just="")

    # --- Divider, filter, clamp ---------------------------------------------
    r1 = s.part("R1", "Device:R", 111.76, 69.85, value="200k 0.1%",
                footprint=FP_R0805, datasheet=DS_RT,
                fields=mfr("Yageo", "RT0805BRD07200KL",
                           {"Tolerance": "0.1%", "TCR": "25ppm/K",
                            "Alt_1pct": "RC0805FR-07200KL"}))
    r2 = s.part("R2", "Device:R", 111.76, 86.36, value="10k 0.1%",
                footprint=FP_R0805, datasheet=DS_RT,
                fields=mfr("Yageo", "RT0805BRD0710KL",
                           {"Tolerance": "0.1%", "TCR": "25ppm/K",
                            "Alt_1pct": "RC0805FR-0710KL"}))
    c1 = s.part("C1", "Device:C", 127.0, 82.55, value="100n",
                footprint=FP_C0603, datasheet=DS_GRM,
                fields=mfr("Murata", "GRM188R71H104KA93D",
                           {"Dielectric": "X7R", "Voltage": "50V"}))
    r3 = s.part("R3", "Device:R", 137.16, 82.55, value="1k",
                footprint=FP_R0603, datasheet=DS_RC,
                fields=mfr("Yageo", "RC0603FR-071KL", {"Tolerance": "1%"}))
    d1 = s.part("D1", "Diode:BAT54S", 157.48, NODE, rot=90, mirror="y",
                footprint=FP_SOT23, datasheet=DS_BAT54,
                fields=mfr("Nexperia", "BAT54S,215"),
                ref_at=(160.02, 77.47), val_at=(160.02, 80.01))
    j2 = s.part("J2", "Connector_Generic:Conn_01x04", 205.74, NODE,
                value="To ESP32-S3",
                footprint="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
                fields={"Manufacturer": "generic", "MPN": "2.54 mm 1x04 male header"},
                ref_at=(203.2, 72.39), val_at=(200.66, 90.17))

    # --- Test points --------------------------------------------------------
    tp = {}
    for ref, net, x, y, rot, mpn in (
            ("TP1", "VIN", 35.56, Y, 0, "5000"),
            ("TP2", "VSW", 96.52, Y, 0, "5000"),
            ("TP3", "ADC_DIV", 144.78, NODE, 0, "5000"),
            ("TP4", "SENSE_EN", 55.88, 93.98, 0, "5000"),
            ("TP5", "Q1_G", 71.12, G, 180, "5000"),
            ("TP6", "GND", 20.32, 99.06, 0, "5001")):
        tp[ref] = s.part(ref, "Connector:TestPoint", x, y, rot=rot, value=net,
                         footprint=FP_TP,
                         fields=mfr("Keystone Electronics", mpn),
                         ref_at=(x + 1.27, y - 6.35) if rot == 0 else (x + 1.27, y + 5.08),
                         val_at=(x + 1.27, y - 3.81) if rot == 0 else (x + 1.27, y + 7.62))

    # ======================= wiring =========================================
    # VIN rail: J1.1 -> TP1 -> FLAG -> D2.K -> R4.1 -> R7 tap -> Q1.S
    s.wire(j1["1"], tp["TP1"]["1"], (45.72, Y), d2["3"], r4["1"], (68.58, Y), q1["2"])
    for p in (tp["TP1"]["1"], (45.72, Y), d2["3"], r4["1"], (68.58, Y)):
        s.junction(p)
    s.power("power:PWR_FLAG", 45.72, Y)
    s.label("VIN", j1["1"])
    # bypass R7 across Q1 (variant A)
    s.wire((68.58, Y), (68.58, 55.88), r7["1"])
    s.wire(r7["2"], (88.9, 55.88), (88.9, Y))
    # VSW: Q1.D -> R7 tap -> TP2 -> R1.1
    s.wire(q1["3"], (88.9, Y), tp["TP2"]["1"], r1["1"])
    s.junction((88.9, Y))
    s.junction(tp["TP2"]["1"])
    s.label("VSW", (101.6, Y))
    # Gate node Q1_G: D2.A, R4.2, TP5, Q1.G, R5.1
    s.wire(d2["1"], r4["2"], tp["TP5"]["1"], q1["1"], r5["1"])
    s.junction(r4["2"])
    s.junction(tp["TP5"]["1"])
    s.junction(q1["1"])
    s.label("Q1_G", (58.42, G))
    # Q2 drain node
    s.wire(r5["2"], q2["3"])
    s.label("Q2_D", (78.74, 87.63))
    # Q2 gate / SENSE_EN: label -> TP4 -> R6 -> Q2.G
    s.wire((48.26, 93.98), tp["TP4"]["1"], r6["1"], q2["1"])
    s.junction(tp["TP4"]["1"])
    s.junction(r6["1"])
    s.label("SENSE_EN", (48.26, 93.98), 180)
    s.power("power:GND", *q2["2"])
    s.power("power:GND", *r6["2"])
    # J1.2 ground with PWR_FLAG
    s.wire(j1["2"], (30.48, 68.58), (30.48, 76.2), (30.48, 81.28))
    s.power("power:PWR_FLAG", 30.48, 76.2, 270)
    s.junction((30.48, 76.2))
    s.power("power:GND", 30.48, 81.28)
    # TP6 ground test point
    s.power("power:GND", *tp["TP6"]["1"])

    # Divider node ADC_DIV: R1.2/R2.1 -> C1 -> R3 tap -> TP3 -> D1.COM
    s.wire(r1["2"], (111.76, NODE), r2["1"])
    s.junction((111.76, NODE))
    s.wire((111.76, NODE), c1["1"], r3["1"], tp["TP3"]["1"], d1["3"])
    s.junction(c1["1"])
    s.junction(r3["1"])
    s.junction(tp["TP3"]["1"])
    s.label("ADC_DIV", (114.3, NODE))
    s.power("power:GND", *r2["2"])
    s.power("power:GND", *c1["2"])
    s.power("power:GND", *d1["1"])
    s.power("power:+3V3", *d1["2"])
    # R3 -> ADC_OUT
    s.wire(r3["2"], (137.16, 92.71))
    s.label("ADC_OUT", (137.16, 92.71), 270)
    # J2: 1 = +3V3 (PWR_FLAG), 2 = ADC_OUT, 3 = SENSE_EN, 4 = GND
    s.wire(j2["1"], (195.58, 76.2), (195.58, 71.12), (187.96, 71.12))
    s.power("power:+3V3", 195.58, 71.12)
    s.power("power:PWR_FLAG", 187.96, 71.12)
    s.wire(j2["2"], (193.04, NODE))
    s.label("ADC_OUT", (193.04, NODE), 180)
    s.wire(j2["3"], (193.04, 81.28))
    s.label("SENSE_EN", (193.04, 81.28), 180)
    s.wire(j2["4"], (195.58, 83.82), (195.58, 86.36))
    s.power("power:GND", 195.58, 86.36)

    # ======================= blocks =========================================
    s.rect(12.7, 45.72, 100.33, 107.95)
    s.text("INPUT + HIGH-SIDE SWITCH (variant B, default fit)", 13.97, 46.99, 1.5, True)
    s.rect(102.87, 45.72, 170.18, 107.95)
    s.text("DIVIDER / FILTER / CLAMP", 104.14, 46.99, 1.5, True)
    s.rect(172.72, 45.72, 222.25, 107.95)
    s.text("TO ESP32-S3 (use an ADC1 pin)", 173.99, 46.99, 1.5, True)

    # ======================= annotations ====================================
    s.text("WARNING: Reference design. Test first with a current-limited supply and "
           "protection. Not for unattended use.", 12.7, 31.75, 1.8, True)
    s.text("Design only, not fabricated, not bench-tested.", 12.7, 35.56, 1.5)

    notes = [
        "KEY VALUES (see README for derivations and sources)",
        "Divider k = R2/(R1+R2) = 10k/210k = 1/21. Vin = 21 x V(ADC_DIV). 30 V -> 1.4286 V.",
        "Use ESP32-S3 ADC1, ATTEN2 (6 dB): calibrated range 0-1600 mV, total error +/-10 mV (= +/-0.21 V at Vin).",
        "Measurable up to 33.6 V (1600 mV x 21). Do not use ADC2 (shared with Wi-Fi).",
        "Rth = R1||R2 = 9.52k. C1 = 100 nF (Espressif suggestion). tau = 0.95 ms, fc = 167 Hz, 12-bit settle 8.6 ms.",
        "Worst-case ratio error: 1% parts +/-1.9% (+/-2.8% with 100 ppm/K, 0-70 C); 0.1% parts +/-0.19% (+/-0.41%).",
        "D1 BAT54S clamps ADC_DIV to -VF..3V3+VF. VF max 240 mV @ 0.1 mA, 320 mV @ 1 mA. ESP32-S3 VIH max = VDD+0.3 V.",
        "Worst fault (R2 open): clamp current = (Vin - ~3.55 V)/200k = 0.13 mA at 30 V. It flows INTO the 3V3 rail.",
        "Variant B: drive SENSE_EN high, wait >= 12 ms (ngspice: 10.5 ms to 0.2 mV at 30 V), sample, drive low. Off drain <= 0.2 uA (datasheet max, 25 C).",
        "Q1 |VGS| = 0.82 x Vin, clamped by D2 to 11.4-12.7 V (BSS84 VGS max 20 V). Switch needs Vin >= ~3 V.",
        "Variant A (always-on): fit R7 (0R), omit Q1, Q2, D2, R4, R5, R6. Drain = Vin/210k (143 uA at 30 V).",
        "Max VIN: 30 V operating. Q1 VDS max 50 V, R1 0805 working voltage 150 V.",
    ]
    for i, line in enumerate(notes):
        s.text(line, 12.7, 114.3 + i * 3.81, 1.27, bold=(i == 0))

    tb = ["title_block",
          ["title", Q("ADC input scaler: 0-30 V to ESP32-S3 ADC")],
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
                                                  "hardware", PROJECT + ".kicad_sch"))
    a = ap.parse_args()
    s, tb = build(a.symdir)
    with open(a.out, "w") as f:
        f.write(s.serialize(tb))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
