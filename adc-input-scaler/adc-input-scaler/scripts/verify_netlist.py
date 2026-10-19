#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Check the netlist KiCad exports against the intended connectivity.

    kicad-cli sch export netlist --format kicadsexpr -o net.net adc-input-scaler.kicad_sch
    python3 verify_netlist.py net.net

The EXPECTED table is the design intent, written by hand from the design
note. Pin numbers are the physical SOT-23 pin numbers, which were checked
against each datasheet's pinning table (see README, "Pin-by-pin check").
Exit status is non-zero on any mismatch.
"""
import sys

from sexpr import find, find_all, parse

EXPECTED = {
    "VIN": {"J1.1", "TP1.1", "D2.3", "R4.1", "Q1.2", "R7.1"},   # Q1.2 = BSS84 source
    "VSW": {"Q1.3", "R7.2", "TP2.1", "R1.1"},                   # Q1.3 = BSS84 drain
    "Q1_G": {"Q1.1", "R4.2", "D2.1", "R5.1", "TP5.1"},          # D2.1 = zener anode
    "Q2_D": {"R5.2", "Q2.3"},                                   # Q2.3 = BSS138 drain
    "SENSE_EN": {"Q2.1", "R6.1", "TP4.1", "J2.3"},              # Q2.1 = BSS138 gate
    "ADC_DIV": {"R1.2", "R2.1", "C1.1", "R3.1", "TP3.1", "D1.3"},  # D1.3 = BAT54S common
    "ADC_OUT": {"R3.2", "J2.2"},
    "+3V3": {"D1.2", "J2.1"},                                   # D1.2 = cathode of upper diode
    "GND": {"J1.2", "Q2.2", "R6.2", "R2.2", "C1.2", "D1.1",     # D1.1 = anode of lower diode
            "TP6.1", "J2.4"},
}
# D2 pin 2 is "n.c." in the BZX84 datasheet and a hidden no_connect pin in
# the KiCad symbol; it must stay unconnected.
MUST_BE_UNCONNECTED = {"D2.2"}


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
