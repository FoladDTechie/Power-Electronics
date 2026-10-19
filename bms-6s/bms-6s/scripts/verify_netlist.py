#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Check the netlist KiCad exports against the intended connectivity.

    kicad-cli sch export netlist --format kicadsexpr -o net.net bms-6s.kicad_sch
    python3 verify_netlist.py net.net

EXPECTED is the design intent, written by hand from the design note. Pin
numbers are the physical package pins, checked against each datasheet's
pinning table (README, "Pin-by-pin check"). Exit status is non-zero on any
mismatch.
"""
import sys

from sexpr import find, find_all, parse

EXPECTED = {
    # current path
    "PACK_P": {"J1.1", "J2.1", "D1.1", "Q3.3", "R6.1", "R24.1"},          # D1.1 = TVS cathode, Q3.3 = 2N7002 drain
    "GND": {"J1.2", "R1.1", "U1.3", "J5.6", "J4.2", "D4.1", "C1.2", "R11.2", "C2.2", "C3.2", "C5.2", "C6.2",
            "C8.2", "C16.2", "C17.2", "TP1.1"},                          # R1.1 = shunt current pin, battery side
    "SH_P": {"R1.2", "R13.1"},                                           # R1.2/R1.3 = Kelvin sense pins
    "SH_N": {"R1.3", "R14.1"},
    "SNS": {"R1.4", "Q1.2", "R3.2"},                                     # Q1.2 = DSG FET source
    "MID": {"Q1.3", "Q2.3"},                                             # both drains (tabs)
    "PACK_N": {"Q2.2", "J2.2", "D1.2", "R5.2", "D3.1", "TP4.1"},         # Q2.2 = CHG FET source, D3.1 = zener anode
    "GDSG": {"Q1.1", "R2.2", "R3.1", "TP2.1"},
    "GCHG": {"Q2.1", "R4.2", "R5.1", "D3.3", "TP3.1"},                   # D3.3 = zener cathode
    "DSG": {"U1.1", "R2.1"},
    "CHG": {"U1.2", "D2.2"},                                             # D2.2 = 1N4148W anode
    "CHGD": {"D2.1", "R4.1"},
    # supplies
    "GCAS": {"Q3.1", "R6.2", "D4.3"},
    "REGSRC": {"Q3.2", "C1.1", "U1.9", "TP8.1"},
    "REGOUT": {"U1.8", "R9.1", "R10.1", "J5.1", "C5.1", "C6.1", "TP7.1"},
    "BATF": {"R24.2", "C17.1", "D6.1", "U1.15"},
    "VC5X": {"U1.10", "C4.2", "R12.2", "C12.2", "R23.2", "C16.1", "D5.1", "TP5.1"},
    "CAP1": {"U1.7", "C3.1"},
    "CAP2": {"U1.14", "U1.11", "U1.12", "C4.1"},                         # NC pins 11/12 shorted to CAP2 per datasheet
    # host, boot, thermistors
    "SDA": {"U1.4", "R9.2", "J5.2"},
    "SCL": {"U1.5", "R10.2", "J5.3"},
    "ALERT": {"U1.30", "R11.1", "C2.1", "J5.4", "TP9.1"},
    "BOOT": {"J5.5", "R8.1"},
    "BOOTSW": {"R7.2", "SW1.1"},
    "TS1": {"U1.6", "SW1.2", "R8.2", "J4.1", "TP6.1"},
    "TS2": {"U1.13", "R12.1"},
    # sense filter
    "SRP": {"U1.28", "R13.2", "C7.1"},
    "SRN": {"U1.29", "R14.2", "C7.2"},
    # cell taps (balance connector) and filtered inputs
    "TAP0": {"J3.1", "R15.1"},
    "TAP1": {"J3.2", "R16.1", "R7.1"},
    "TAP2": {"J3.3", "R17.1"},
    "TAP3": {"J3.4", "R18.1", "R19.1", "R23.1"},
    "TAP4": {"J3.5", "R20.1"},
    "TAP5": {"J3.6", "R21.1"},
    "TAP6": {"J3.7", "R22.1"},
    "IN0": {"R15.2", "U1.27", "C8.1", "C9.2"},
    "IN1": {"R16.2", "U1.26", "C9.1", "C10.2"},
    "IN2": {"R17.2", "U1.25", "U1.24", "U1.23", "C10.1", "C11.2"},       # VC2 = VC3 = VC4
    "IN3": {"R18.2", "U1.22", "C11.1", "D5.2"},                          # VC5; D5.2 = 1N4148W anode
    "IN3B": {"R19.2", "U1.21", "C12.1", "C13.2"},                        # VC5B
    "IN4": {"R20.2", "U1.20", "C13.1", "C14.2"},                         # VC6
    "IN5": {"R21.2", "U1.19", "U1.18", "U1.17", "C14.1", "C15.2"},       # VC7 = VC8 = VC9
    "IN6": {"R22.2", "U1.16", "C15.1", "D6.2"},                          # VC10
}
MUST_BE_UNCONNECTED = {"D3.2", "D4.2"}   # BZX84 pin 2 is not connected inside the part


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
            print(f"ok  {name:8s} {len(want):2d} pins")
    for name, nodes in nets.items():
        if name in EXPECTED:
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
