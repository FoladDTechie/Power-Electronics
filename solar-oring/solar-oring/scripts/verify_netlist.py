#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Check the netlist KiCad exports against the intended connectivity.

    kicad-cli sch export netlist --format kicadsexpr -o net.net solar-oring.kicad_sch
    python3 verify_netlist.py net.net

The EXPECTED table is the design intent, written by hand from the design
note. Pin numbers are the physical SOT-23 pin numbers, which were checked
against each datasheet's pinning table (see README, "Pin-by-pin check").
Exit status is non-zero on any mismatch.
"""
import sys

from sexpr import find, find_all, parse

EXPECTED = {
    # SiS443DN: pin 5 = drain (pads 5-8 + exposed pad), pins 1-3 = source, pin 4 = gate
    "SOLAR_IN": {"J1.1", "TP1.1", "D2.1", "C1.1", "Q1.5", "U1.1"},   # D2.1 = TVS cathode, U1.1 = VIN
    "VLOAD": {"Q1.1", "Q1.2", "Q1.3", "U1.6", "D1.1", "TP3.1", "C3.1", "J3.1"},  # U1.6 = SENSE, D1.1 = SS34 cathode
    "GATE": {"U1.5", "Q1.4", "TP4.1"},
    "AUX_IN": {"J2.1", "C2.1", "TP2.1", "D1.2"},                     # D1.2 = SS34 anode
    "STAT": {"U1.4", "R1.2", "TP5.1", "J4.2"},
    "CTL": {"U1.3", "R2.1", "J4.3"},
    "+3V3": {"R1.1", "J4.1"},
    "GND": {"J1.2", "J2.2", "J3.2", "J4.4", "D2.2", "C1.2", "C2.2", "C3.2",
            "U1.2", "R2.2", "TP6.1"},
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
