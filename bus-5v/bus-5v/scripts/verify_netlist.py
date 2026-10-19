#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Check the netlist KiCad exports against the intended connectivity.

    kicad-cli sch export netlist --format kicadsexpr -o net.net bus-5v.kicad_sch
    python3 verify_netlist.py net.net

The EXPECTED table is the design intent, written by hand from the design
note. Pin numbers are the physical SOT-23 pin numbers, which were checked
against each datasheet's pinning table (see README, "Pin-by-pin check").
Exit status is non-zero on any mismatch.
"""
import sys

from sexpr import find, find_all, parse

EXPECTED = {
    # ---- variant A ----
    "VIN_A": {"J1.1", "F1.1"},
    "VIN_A_F": {"F1.2", "Q1.5"},                       # SiS443DN drain (pins 5-8 + pad)
    "VIN_A_P": {"Q1.1", "Q1.2", "Q1.3", "D3.3", "TP1.1", "D1.1", "C1.1", "C2.1", "C3.1",
                "C4.1", "U1.2", "R4.1"},                  # Q1 source, zener cathode, TVS cathode, U1 VIN
    "Q1_G": {"Q1.4", "D3.1", "R3.1"},                  # gate, zener anode, pull-down
    "EN_A": {"U1.3", "R4.2", "R5.1"},
    "VCC_A": {"U1.6", "C5.1"},
    "BOOT_A": {"U1.7", "C6.1"},
    "SW_A": {"U1.8", "C6.2", "TP2.1", "L1.1"},
    "FB_A": {"U1.5", "R6.2", "R7.1"},
    "PG_A": {"U1.4", "R8.2", "J5.1"},
    "5V_A": {"L1.2", "C7.1", "C8.1", "C9.1", "C10.1", "TP3.1", "J2.1", "R6.1", "R8.1"},
    # ---- variant B ----
    "VBAT": {"J3.1", "F2.1"},
    "VBAT_F": {"F2.2", "Q2.5"},                        # AON6411 drain (pins 5-8 + pad)
    "VBAT_P": {"Q2.1", "Q2.2", "Q2.3", "TP4.1", "D4.1", "C11.1", "L2.1", "U2.5", "R12.1"},
    "Q2_G": {"Q2.4", "R9.1"},
    "SW_B": {"L2.2", "TP5.1", "D5.2", "U2.1"},         # D5.2 = SS34 anode, U2.1 = MT3608 SW
    "FB_B": {"U2.3", "R10.2", "R11.1"},
    "EN_B": {"U2.4", "R12.2", "J5.2"},
    "5V_B": {"D5.1", "C12.1", "C13.1", "TP6.1", "J4.1", "R10.1"},
    "GND": {"J1.2", "J2.2", "J3.2", "J4.2", "J5.3", "R3.2", "D1.2", "C1.2", "C2.2", "C3.2", "C4.2",
            "U1.1", "U1.9", "C5.2", "C7.2", "C8.2", "C9.2", "C10.2", "R5.2", "R7.2",
            "R9.2", "D4.2", "C11.2", "U2.2", "C12.2", "C13.2", "R11.2", "TP7.1"},
}
MUST_BE_UNCONNECTED = {"D3.2", "U2.6"}   # BZX84 n.c. pin; MT3608 NC pin


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
