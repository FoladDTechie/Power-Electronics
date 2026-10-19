#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Small library for writing KiCad 9 schematics from stock library symbols.
Every symbol is copied (and, for derived symbols, flattened) from the
installed KiCad libraries; nothing is drawn by hand. Pin positions are
computed from the library so wires and labels land exactly on pins.
"""
import argparse
import copy
import math
import os
import uuid as uuidlib

from sexpr import Q, dump, find, find_all, parse

PROJECT = "bms-6s"
NS = uuidlib.UUID("6f1c2a52-1d1e-4c55-9a3b-1b7f0a2c0006")


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
             hide_ref=False, just="left", ref_just=None, val_just=None):
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
        node.append(prop("Reference", ref, ra[0], ra[1], fa, hide=hide_ref,
                         justify=just if ref_just is None else ref_just))
        node.append(prop("Value", value, va[0], va[1], fa, hide=hide_value,
                         justify=just if val_just is None else val_just))
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

    def no_connect(self, p):
        self.items.append(["no_connect", ["at", p[0], p[1]], ["uuid", U(f"nc:{p}")]])

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


