#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Check the netlist KiCad exports against the intended connectivity.

    kicad-cli sch export netlist --format kicadsexpr -o net.net solar-charger.kicad_sch
    python3 verify_netlist.py net.net

The EXPECTED table is the design intent, written by hand from the design
note. Pin numbers are the physical SOT-23 pin numbers, which were checked
against each datasheet's pinning table (see README, "Pin-by-pin check").
Exit status is non-zero on any mismatch.
"""
import sys

from sexpr import find, find_all, parse

EXPECTED = {
    "PANEL": {"J1.1", "D1.2"},                                    # D1.2 = SS34 anode
    "VIN": {"D1.1", "D2.1", "C1.1", "C2.1", "R1.1", "TP1.1", "Q1.5", "R2.1"},  # Q1.5 = high-side drain
    "VCC": {"R1.2", "C3.1", "U1.1"},
    "MPPSET": {"R2.2", "R3.1", "Q3.3", "U1.2"},                   # Q3.3 = BSS138 drain
    "CHG_DIS": {"Q3.1", "R10.1", "J4.3"},
    "HIDRV": {"U1.15", "Q1.4"},
    "LODRV": {"U1.13", "Q2.4"},
    "PH": {"U1.14", "Q1.1", "Q1.2", "Q1.3", "Q2.5", "C4.2", "TP2.1", "L1.1"},  # Q1 source, Q2 drain
    "BTST": {"U1.16", "C4.1", "D3.1"},                            # D3.1 = BAT54J cathode
    "REGN": {"U1.12", "C5.1", "D3.2"},                            # D3.2 = BAT54J anode
    "SRP": {"U1.10", "L1.2", "R4.1", "C7.1", "C8.1"},
    "SRN": {"U1.9", "R4.2", "C7.2", "C9.1", "TP3.1", "F1.1", "R5.1"},
    "BAT": {"F1.2", "TP4.1", "J2.1"},
    "VFB": {"U1.8", "R5.2", "R6.1"},
    "VREF": {"U1.6", "U1.7", "C6.1", "R7.1", "R8.1", "R9.1"},     # U1.7 = TERM_EN tied high
    "TS": {"U1.4", "R7.2", "R11.1", "J3.1"},
    "STAT1": {"U1.3", "D4.1", "J4.1"},                            # LED cathodes on open-drain pins
    "STAT2": {"U1.5", "D5.1", "J4.2"},
    "Net-(D4-A)": {"D4.2", "R8.2"},
    "Net-(D5-A)": {"D5.2", "R9.2"},
    "GND": {"J1.2", "J2.2", "J3.2", "J4.4", "D2.2", "C1.2", "C2.2", "C3.2", "C5.2", "C6.2", "C8.2",
            "C9.2", "Q2.1", "Q2.2", "Q2.3", "Q3.2", "R10.2", "R3.2", "R6.2", "R11.2", "TP5.1",
            "U1.11", "U1.17"},
}
MUST_BE_UNCONNECTED = set()


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
        else:
            print(f"ok  {name:9s} {' '.join(sorted(want))}")
    for name, nodes in nets.items():
        if name not in EXPECTED:
            real = nodes & MUST_BE_UNCONNECTED
            if real and len(nodes) == 1:
                print(f"ok  {sorted(nodes)[0]} unconnected (net '{name}')")
            else:
                ok = False
                print(f"UNEXPECTED net {name}: {sorted(nodes)}")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
