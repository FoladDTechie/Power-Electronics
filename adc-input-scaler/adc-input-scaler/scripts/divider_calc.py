#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Divider calculator for the ADC input scaler reference design.

Prints:
  1. E24/E96 candidate pairs for a given input full scale and ADC window.
  2. Worst-case ratio error of the chosen pair at 1 % and 0.1 % tolerance,
     with and without temperature coefficient.
  3. Thevenin source impedance, divider drain, RC filter corner and settling.
  4. Error contributions from leakage currents (datasheet maxima).

All datasheet numbers used here are listed in DATASHEET below with their
source so they can be checked. Anything that is NOT from a datasheet is
listed in ASSUMPTION.

Usage:  python3 divider_calc.py            (default design values)
        python3 divider_calc.py --vin-max 24 --adc-max 1.6
"""
import argparse
import math

# --- Values copied from datasheets (see README "Sources") -------------------
DATASHEET = {
    # ESP32-S3-PICO-1 datasheet v1.1, Table 3-6 "ADC Calibration Results"
    # (same ADC as the ESP32-S3 die; confirm against the ESP32-S3 datasheet
    # revision you build against).
    "adc_range_mV": {"ATTEN0": 850, "ATTEN1": 1100, "ATTEN2": 1600, "ATTEN3": 2900},
    "adc_total_err_mV": {"ATTEN0": 5, "ATTEN1": 6, "ATTEN2": 10, "ATTEN3": 50},
    # ESP32-S3 DC characteristics: IIH / IIL max 50 nA (3.3 V, 25 C)
    "esp_pin_leak_A": 50e-9,
    # Nexperia BAT54 series rev 5, Table 7: IR max 2 uA at VR = 25 V
    # (only tabulated point; real leakage at VR < 3.6 V is lower but not
    # specified numerically).
    "bat54_ir_max_A_at_25V": 2e-6,
    # Yageo RC (thick film, 1 %): TCR +/-100 ppm/K
    "tcr_1pct_ppm": 100,
    # Yageo RT (thin film, 0.1 %, "D" TCR code): +/-25 ppm/K
    "tcr_0p1pct_ppm": 25,
}

# --- Things that are NOT in a datasheet --------------------------------------
ASSUMPTION = {
    # Operating ambient range used for the TCR line (design choice).
    "t_min_C": 0.0,
    "t_max_C": 70.0,
    "t_ref_C": 25.0,
}

E24 = [1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0,
       3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1]


# Published IEC 60063 E96 values (hard-coded rather than computed, so no
# rounding surprises).
E96 = [v / 100 for v in (
    100, 102, 105, 107, 110, 113, 115, 118, 121, 124, 127, 130, 133, 137, 140, 143,
    147, 150, 154, 158, 162, 165, 169, 174, 178, 182, 187, 191, 196, 200, 205, 210,
    215, 221, 226, 232, 237, 243, 249, 255, 261, 267, 274, 280, 287, 294, 301, 309,
    316, 324, 332, 340, 348, 357, 365, 374, 383, 392, 402, 412, 422, 432, 442, 453,
    464, 475, 487, 499, 511, 523, 536, 549, 562, 576, 590, 604, 619, 634, 649, 665,
    681, 698, 715, 732, 750, 768, 787, 806, 825, 845, 866, 887, 909, 931, 953, 976)]
assert len(E96) == 96


def decade_values(series, lo=1e3, hi=1e6):
    out = []
    d = 1.0
    while d <= hi:
        for v in series:
            r = v * d
            if lo <= r <= hi:
                out.append(round(r, 6))
        d *= 10
    return sorted(set(out))


def ratio(rt, rb):
    return rb / (rt + rb)


def worst_ratio(rt, rb, tol, tcr_ppm=0.0, dT=0.0):
    """Return (k_min, k_max) with tolerance and (optionally) opposing TCR drift."""
    d = tol + tcr_ppm * 1e-6 * dT
    k_hi = ratio(rt * (1 - d), rb * (1 + d))
    k_lo = ratio(rt * (1 + d), rb * (1 - d))
    return k_lo, k_hi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vin-max", type=float, default=30.0, help="input full scale, V")
    ap.add_argument("--atten", default="ATTEN2", choices=DATASHEET["adc_range_mV"].keys())
    ap.add_argument("--headroom-mV", type=float, default=50.0,
                    help="margin below the calibrated ADC range at worst case")
    ap.add_argument("--rtot-min", type=float, default=150e3)
    ap.add_argument("--rtot-max", type=float, default=300e3)
    ap.add_argument("--rt", type=float, default=200e3, help="chosen top resistor")
    ap.add_argument("--rb", type=float, default=10e3, help="chosen bottom resistor")
    ap.add_argument("--c", type=float, default=100e-9, help="filter capacitor")
    a = ap.parse_args()

    adc_max = DATASHEET["adc_range_mV"][a.atten] / 1000.0
    v_limit = adc_max - a.headroom_mV / 1000.0
    dT = max(ASSUMPTION["t_max_C"] - ASSUMPTION["t_ref_C"],
             ASSUMPTION["t_ref_C"] - ASSUMPTION["t_min_C"])

    print(f"== Window: {a.atten} calibrated range 0..{adc_max*1000:.0f} mV, "
          f"worst-case node limit {v_limit*1000:.0f} mV at Vin = {a.vin_max} V")

    # 1. Candidate search ------------------------------------------------------
    for name, series in (("E24", E24), ("E96", E96)):
        vals = decade_values(series)
        cands = []
        for rt in vals:
            for rb in vals:
                if not (a.rtot_min <= rt + rb <= a.rtot_max):
                    continue
                _, khi = worst_ratio(rt, rb, 0.01, DATASHEET["tcr_1pct_ppm"], dT)
                if a.vin_max * khi > v_limit:
                    continue
                cands.append((a.vin_max * ratio(rt, rb), rt, rb))
        cands.sort(reverse=True)
        print(f"\n-- Top {name} pairs (Rtop+Rbot {a.rtot_min/1e3:.0f}..{a.rtot_max/1e3:.0f} k, "
              f"worst case 1 %/100 ppm stays under limit):")
        print("   Rtop      Rbot      Vnode@Vin_max   ratio 1/k")
        for v, rt, rb in cands[:6]:
            print(f"   {rt/1e3:7.2f}k  {rb/1e3:7.3f}k   {v*1000:8.1f} mV     {1/ratio(rt, rb):8.4f}")

    # 2. Chosen pair -----------------------------------------------------------
    rt, rb = a.rt, a.rb
    k = ratio(rt, rb)
    print(f"\n== Chosen: Rtop = {rt/1e3:g} k, Rbot = {rb/1e3:g} k, "
          f"k = {k:.6f} (Vin = {1/k:.4f} x Vadc)")
    print(f"   Vnode at Vin_max = {a.vin_max*k*1000:.1f} mV; "
          f"Vin that reaches {adc_max*1000:.0f} mV = {adc_max/k:.2f} V")
    print("\n   Worst-case ratio error (resistors only):")
    print("   case                               k_min      k_max     error")
    rows = [
        ("1 % tolerance, 25 C", 0.01, 0, 0),
        ("1 % + 100 ppm/K over 0..70 C", 0.01, DATASHEET["tcr_1pct_ppm"], dT),
        ("0.1 % tolerance, 25 C", 0.001, 0, 0),
        ("0.1 % + 25 ppm/K over 0..70 C", 0.001, DATASHEET["tcr_0p1pct_ppm"], dT),
    ]
    for label, tol, tcr, dt in rows:
        klo, khi = worst_ratio(rt, rb, tol, tcr, dt)
        e_hi = (khi / k - 1) * 100
        e_lo = (klo / k - 1) * 100
        print(f"   {label:34s} {klo:.6f}  {khi:.6f}  {e_lo:+.3f} % / {e_hi:+.3f} %"
              f"  (= {e_lo/100*a.vin_max*1000:+.0f} / {e_hi/100*a.vin_max*1000:+.0f} mV at {a.vin_max} V)")

    # 3. Dynamics and drain ----------------------------------------------------
    rth = rt * rb / (rt + rb)
    tau = rth * a.c
    print(f"\n== Thevenin source resistance seen by C1/ADC: {rth/1e3:.3f} k")
    print(f"   tau = {tau*1e3:.3f} ms, -3 dB corner = {1/(2*math.pi*tau):.1f} Hz")
    for bits in (10, 12):
        n = math.log(2 ** (bits + 1))
        print(f"   settle to 1/2 LSB of {bits}-bit: {n:.2f} tau = {n*tau*1e3:.2f} ms")
    for vin in (4.2, 12.0, 24.0, 30.0):
        i = vin / (rt + rb)
        print(f"   always-on divider drain at {vin:5.1f} V: {i*1e6:7.1f} uA "
              f"({i*8760:.3f} Ah per year)")

    # 4. Leakage error ---------------------------------------------------------
    il = DATASHEET["esp_pin_leak_A"]
    print("\n== Leakage-induced offset at the ADC node (datasheet maxima, 25 C):")
    print(f"   ESP32-S3 pin leakage 50 nA into Rth + 1k series: "
          f"{il*(rth+1e3)*1e3:.3f} mV -> {il*(rth+1e3)/k*1e3:.1f} mV at Vin")
    ir = DATASHEET["bat54_ir_max_A_at_25V"]
    print(f"   BAT54S IR bound 2 uA (spec'd at VR=25 V, not at <=3.6 V): "
          f"{ir*rth*1e3:.1f} mV -> {ir*rth/k:.3f} V at Vin  (upper bound, see README)")

    # 5. ADC error referred to input ------------------------------------------
    print("\n== ESP32-S3 calibrated total error referred to Vin (x 1/k):")
    for at, err in DATASHEET["adc_total_err_mV"].items():
        print(f"   {at}: +/-{err} mV at pin -> +/-{err/k/1000:.3f} V at Vin")


if __name__ == "__main__":
    main()
