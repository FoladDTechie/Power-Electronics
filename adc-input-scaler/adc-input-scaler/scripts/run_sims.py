#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
Run the ngspice decks in sim/, collect the .meas results into
sim/results.txt and draw docs/sim_*.png.

    NGSPICE="ngspice" python3 scripts/run_sims.py

NGSPICE may be a wrapper command; it is run with the sim/ directory as cwd
and the deck file name as its last argument.
"""
import glob
import os
import re
import shlex
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(HERE, "..", "sim")
DOCS = os.path.join(HERE, "..", "docs")
DECKS = ["dc_transfer", "switched_tran", "filter_ac"]
INK, MUTED, GRID = "#1f2933", "#6b7785", "#d8dde3"
SERIES = ["#2563a6", "#c2410c", "#15803d"]


def run():
    cmd = shlex.split(os.environ.get("NGSPICE", "ngspice"))
    stale = set(glob.glob(os.path.join(SIM, "*.txt")) + glob.glob(os.path.join(SIM, "switched_*")))
    for f in stale:
        if not f.endswith(".cir"):
            os.remove(f)
    out = {}
    for d in DECKS:
        p = subprocess.run(cmd + ["-b", d + ".cir"], cwd=SIM, capture_output=True, text=True)
        log = p.stdout + p.stderr
        open(os.path.join(SIM, d + ".log"), "w").write(log)
        if re.search(r"^Error", log, re.M):
            raise SystemExit(f"ngspice error in {d}, see sim/{d}.log")
        out[d] = re.findall(r"^(\w+)\s+=\s+([-+0-9.eE]+)", log, re.M)
    for v in ("4.2", "12", "30"):
        src = os.path.join(SIM, "switched_" + v)
        if os.path.exists(src):
            os.replace(src, src + ".txt")
    return out


def load(name):
    with open(os.path.join(SIM, name)) as f:
        head = f.readline().split()
        rows = [list(map(float, ln.split())) for ln in f if ln.strip()]
    return {h: [r[i] for r in rows] for i, h in enumerate(head)}


def style(ax, title, xl, yl):
    ax.set_title(title, loc="left", fontsize=11, color=INK)
    ax.set_xlabel(xl, color=MUTED)
    ax.set_ylabel(yl, color=MUTED)
    ax.grid(True, color=GRID, linewidth=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED)


def plots():
    # 1. DC transfer
    a = load("dc_normal.txt")
    b = load("dc_r2open.txt")
    fig, ax = plt.subplots(figsize=(7, 4), dpi=130)
    ax.plot(a["v-sweep"], a["v(adc_out)"], color=SERIES[0], lw=2, label="Normal (R2 = 10k)")
    ax.plot(b["v-sweep"], b["v(adc_out)"], color=SERIES[1], lw=2, label="Fault: R2 open")
    ax.axhline(3.6, color=INK, lw=1, ls="--")
    ax.text(1, 3.65, "ESP32-S3 VIH max = VDD + 0.3 V = 3.6 V", fontsize=8, color=INK)
    ax.axhline(1.6, color=MUTED, lw=1, ls=":")
    ax.text(1, 1.65, "ATTEN2 calibrated range top, 1.6 V", fontsize=8, color=MUTED)
    ax.axvline(30, color=GRID, lw=1)
    style(ax, "ADC pin voltage vs VIN (variant A, behavioural models)", "VIN (V)", "V(ADC_OUT) (V)")
    ax.set_ylim(0, 4.0)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(os.path.join(DOCS, "sim_dc_transfer.png"))
    plt.close(fig)

    # 2. Switched transient
    fig, ax = plt.subplots(figsize=(7, 4), dpi=130)
    for c, v in zip(SERIES, ("4.2", "12", "30")):
        d = load(f"switched_{v}.txt")
        t = [x * 1e3 for x in d["time"]]
        ax.plot(t, [y * 21 for y in d["v(adc_div)"]], color=c, lw=2, label=f"VIN = {v} V")
    ax.axvspan(2, 22, color=GRID, alpha=0.35, lw=0)
    ax.text(2.3, 31.5, "SENSE_EN high (2-22 ms)", fontsize=8, color=MUTED)
    style(ax, "Variant B: reading referred to input (21 x V(ADC_DIV))", "time (ms)", "VIN estimate (V)")
    ax.set_ylim(0, 34)
    ax.legend(frameon=False, fontsize=8, loc="center right")
    fig.tight_layout()
    fig.savefig(os.path.join(DOCS, "sim_switched_tran.png"))
    plt.close(fig)

    # 3. AC
    d = load("filter_ac.txt")
    fig, ax = plt.subplots(figsize=(7, 3.4), dpi=130)
    ax.semilogx(d["frequency"], d["g"], color=SERIES[0], lw=2)
    ax.axvline(167, color=MUTED, lw=1, ls=":")
    ax.text(180, -32, "-3 dB at ~167 Hz", fontsize=8, color=MUTED)
    style(ax, "VIN to ADC_DIV gain (R1, R2, C1)", "frequency (Hz)", "gain (dB)")
    fig.tight_layout()
    fig.savefig(os.path.join(DOCS, "sim_filter_ac.png"))
    plt.close(fig)


def main():
    res = run()
    with open(os.path.join(SIM, "results.txt"), "w") as f:
        f.write("# ngspice .meas results (behavioural models, see sim/models.lib)\n")
        for d, kv in res.items():
            f.write(f"\n[{d}]\n")
            for k, v in kv:
                f.write(f"{k} = {v}\n")
    plots()
    print(open(os.path.join(SIM, "results.txt")).read())


if __name__ == "__main__":
    main()
