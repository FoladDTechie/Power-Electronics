#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Check the netlist KiCad exports against the intended connectivity.

    kicad-cli sch export netlist --format kicadsexpr -o net.net drone-pdb.kicad_sch
    python3 verify_netlist.py net.net

EXPECTED is the design intent, written by hand from the design note. Pin
numbers are the physical package pins, checked against each datasheet's
pinning table (README, "Pin-by-pin check"). ANONYMOUS lists nets that have
no label (two-part junctions); they are matched by their pin sets.
Exit status is non-zero on any mismatch.
"""
import sys

from sexpr import find, find_all, parse


def bec(t, u, f, cin, chf, ruv1, ruv2, cen, rrt, cboot, d, l_, rfb1, rfb2, rc, cc, chf2, tpen):
    return {
        f"VIN{t}": {f"{f}.2", *(f"{c}.1" for c in cin), f"{chf}.1", f"{ruv1}.1", f"{u}.2"},
        f"EN{t}": {f"{ruv1}.2", f"{ruv2}.1", *(f"{c}.1" for c in cen), f"{u}.3", f"{tpen}.1"},
        f"RT{t}": {f"{u}.4", f"{rrt}.1"},
        f"BOOT{t}": {f"{u}.1", f"{cboot}.1"},
        f"SW{t}": {f"{u}.8", f"{cboot}.2", f"{d}.1", f"{l_}.1"},      # D.1 = SS36 cathode
        f"COMP{t}": {f"{u}.6", f"{rc}.1", f"{chf2}.1"},
        f"CZ{t}": {f"{rc}.2", f"{cc}.1"},
        f"FB{t}": {f"{u}.5", f"{rfb1}.2", f"{rfb2}.1"},
    }


EXPECTED = {
    "BAT_IN": {"J1.1", "R1.1"},                                     # R1.1/R1.4 = shunt current pins
    "SENSE_P": {"R1.2", "R12.1"},                                   # R1.2/R1.3 = Kelvin sense pins
    "SENSE_N": {"R1.3", "R13.1"},
    "VBAT": {"R1.4", "TP1.1", "D1.1", "C1.1", "C2.1", "C3.1", "J3.1", "J4.1", "J5.1", "J6.1",
             "R9.1", "U1.8", "F1.1", "F2.1", "R27.1"},             # D1.1 = TVS cathode, U1.8 = VBUS
    "BAT_N": {"J1.2", "Q1.2", "Q2.2", "Q3.1", "Q3.2", "Q3.3", "D2.1", "C4.2", "J2.2", "TP2.1"},
    "PRE_D": {"Q3.5", "R4.1", "R6.1"},                              # Q3.5 = BUK7M42 drain (tab)
    "GATE_M": {"R2.1", "R3.1", "R10.2", "C4.1", "D3.2", "TP4.1"},   # D3.2 = 1N4148W anode
    "GATE_P": {"Q3.4", "R8.2"},
    "GSUP": {"R9.2", "D2.3", "R8.1", "R10.1", "R11.2", "J2.1", "TP3.1"},  # D2.3 = BZX84 cathode
    "GX": {"D3.1", "R11.1"},
    "INA_P": {"R12.2", "C5.1", "U1.10"},
    "INA_N": {"R13.2", "C5.2", "U1.9"},
    "3V3_FC": {"U1.6", "C6.1", "R14.1", "J7.2"},
    "SDA": {"U1.4", "J7.4"},
    "SCL": {"U1.5", "J7.3"},
    "ALERT": {"U1.3", "R14.2", "J7.5"},
    "+5V": {"J7.1", "L1.2", "C13.1", "C14.1", "R18.1", "TP5.1", "J8.1", "U4.6", "C29.1", "D6.1", "BZ1.1"},
    "+12V": {"L2.2", "C23.1", "C24.1", "C25.1", "R24.1", "TP7.1", "J9.1"},
    "LV_SENSE": {"R27.2", "R28.1", "R29.1", "C28.1", "U4.4", "TP9.1"},
    "LV_6S": {"R29.2", "JP1.1"},
    "LV_REF": {"U4.5", "R30.1"},
    "LV_HYS": {"R30.2", "R31.2", "U4.3"},
    "ALARM": {"U4.1", "R31.1", "R32.1", "Q4.1", "TP10.1"},
    "BUZ_N": {"Q4.3", "BZ1.2", "D6.2"},
    "GND": {"Q1.3", "Q2.3", "R5.2", "R7.2", "D1.2", "C1.2", "C2.2", "C3.2", "J3.2", "J4.2", "J5.2", "J6.2",
            "U1.7", "U1.1", "U1.2", "C6.2", "J7.6",
            "U2.7", "U2.9", "C7.2", "C8.2", "C9.2", "R16.2", "C10.2", "C11.2", "R17.2", "D4.2", "C13.2", "C14.2",
            "R19.2", "C15.2", "C16.2", "J8.2",
            "U3.7", "U3.9", "C17.2", "C18.2", "C19.2", "R22.2", "C20.2", "C21.2", "R23.2", "D5.2", "C23.2",
            "C24.2", "C25.2", "R25.2", "C26.2", "C27.2", "J9.2",
            "U4.2", "R28.2", "JP1.2", "C28.2", "R32.2", "C29.2", "Q4.2", "TP11.1"},
}
EXPECTED.update(bec("5", "U2", "F1", ("C7", "C8"), "C9", "R15", "R16", ("C10", "C11"), "R17", "C12", "D4", "L1",
                    "R18", "R19", "R20", "C15", "C16", "TP6"))
EXPECTED.update(bec("12", "U3", "F2", ("C17", "C18"), "C19", "R21", "R22", ("C20", "C21"), "R23", "C22", "D5", "L2",
                    "R24", "R25", "R26", "C26", "C27", "TP8"))
ANONYMOUS = [
    {"Q1.1", "R2.2"},       # gate stopper to Q1 gate
    {"Q2.1", "R3.2"},
    {"R4.2", "R5.1"},       # 2S2P precharge string midpoints
    {"R6.2", "R7.1"},
]
MUST_BE_UNCONNECTED = {"D2.2"}   # BZX84 pin 2 is not connected inside the part


def main(path):
    root = parse(open(path).read())[0]
    nets = {}
    for net in find_all(find(root, "nets"), "net"):
        name = str(find(net, "name")[1]).lstrip("/")
        nodes = {f"{find(n, 'ref')[1]}.{find(n, 'pin')[1]}" for n in find_all(net, "node")}
        nets[name] = nodes
    ok = True
    for name, want in EXPECTED.items():
        got = nets.get(name)
        if got != want:
            ok = False
            print(f"MISMATCH {name}: expected {sorted(want)} got {sorted(got or [])}")
            if got:
                print(f"    missing {sorted(want - got)}, extra {sorted(got - want)}")
        else:
            print(f"ok  {name:9s} {len(want):2d} pins")
    seen = set(EXPECTED)
    for want in ANONYMOUS:
        hit = [n for n, nodes in nets.items() if nodes == want]
        if hit:
            seen.add(hit[0])
            print(f"ok  {hit[0]} = {' '.join(sorted(want))}")
        else:
            ok = False
            print(f"MISSING anonymous net {sorted(want)}")
    for name, nodes in nets.items():
        if name in seen:
            continue
        if len(nodes) == 1 and nodes <= MUST_BE_UNCONNECTED:
            print(f"ok  {sorted(nodes)[0]} unconnected (net '{name}')")
        else:
            ok = False
            print(f"UNEXPECTED net {name}: {sorted(nodes)}")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
