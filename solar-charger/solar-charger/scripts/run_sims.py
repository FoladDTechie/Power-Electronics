#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
ngspice checks for the BQ24650 solar charger. Writes decks into sim/, runs them, saves
sim/results.txt and docs/sim_*.png.

    NGSPICE="ngspice" python3 scripts/run_sims.py

What this simulation is: the synchronous buck power stage, open loop, with
ideal switches at the BUK9M14-40E maximum RDS(on), the worst-case inductor
(10 uH -20 %) and the minimum switching frequency (510 kHz), driving a
resistor that draws 2 A at the 4.16 V charge voltage. It checks inductor
ripple, peak current and output ripple. It does NOT model the BQ24650 control
loop, MPPT behaviour, charge phases, a real cell, or switching losses.
"""
import math
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
CMD = shlex.split(os.environ.get("NGSPICE", "ngspice"))
INK, MUTED, GRID = "#1f2933", "#6b7785", "#d8dde3"
SERIES = ["#2563a6", "#c2410c", "#15803d", "#7c3aed"]

BUCK = """* BQ24650 power stage, open loop
.include models.lib
.param vin={vin} fsw=510k lval=8u
.param per={{1/fsw}} ton={{{dfrac}*per}}
VIN VIN 0 {{vin}}
VG G 0 PULSE(0 1 0 1n 1n {{ton}} {{per}})
VGN GN 0 PULSE(1 0 0 1n 1n {{ton}} {{per}})
SHS VIN PH G 0 SWQ
SLS PH 0 GN 0 SWQ
DB 0 PH DBODY
VIL PH PHX 0
L1 PHX LX {{lval}}
RDCR LX SRP 0.0298
RSR SRP SRN 0.020
C9 SRN CX 10u
RESR CX 0 3m
RF SRN BAT 0.014
RL BAT 0 2.08
.ic v(SRN)=4.16
.control
set wr_singlescale
set wr_vecnames
tran 10n 3m 0 10n uic
meas tran vbat AVG v(BAT) FROM=2.5m TO=3m
meas tran ibat AVG i(VIL) FROM=2.5m TO=3m
meas tran vpp PP v(SRN) FROM=2.5m TO=3m
meas tran ipp PP i(VIL) FROM=2.5m TO=3m
meas tran ipk MAX i(VIL) FROM=2.5m TO=3m
linearize v(SRN) i(VIL)
wrdata {tag}.txt v(SRN) i(VIL)
quit
.endc
.end
"""


def run(name, text):
    path = os.path.join(SIM, name + ".cir")
    open(path, "w").write(text)
    p = subprocess.run(CMD + ["-b", name + ".cir"], cwd=SIM, capture_output=True, text=True)
    log = p.stdout + p.stderr
    open(os.path.join(SIM, name + ".log"), "w").write(log)
    if re.search(r"^Error", log, re.M):
        raise SystemExit(f"ngspice error in {name}, see sim/{name}.log")
    return {k: float(v) for k, v in re.findall(r"^(\w+)\s+=\s+([-+0-9.eE]+)", log, re.M)}


def load(name):
    with open(os.path.join(SIM, name)) as f:
        head = f.readline().split()
        rows = [list(map(float, ln.split())) for ln in f if ln.strip()]
    return {h.lower(): [r[i] for r in rows] for i, h in enumerate(head)}


def style(ax, title, xl, yl):
    ax.set_title(title, loc="left", fontsize=10, color=INK)
    ax.set_xlabel(xl, color=MUTED)
    ax.set_ylabel(yl, color=MUTED)
    ax.grid(True, color=GRID, linewidth=0.6)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(colors=MUTED)


def ntc(t):
    return 10e3 * math.exp(3435 * (1 / (t + 273.15) - 1 / 298.15))


def ts(t, rt1=4.32e3, rt2=20.5e3):
    rp = 1 / (1 / rt2 + 1 / ntc(t))
    return rp / (rt1 + rp)


def main():
    res = []
    for vin in (17.83, 22.0):
        tag = f"buck_{vin:.0f}V"
        d = (4.16 + 2.0 * (0.014 + 0.0298 + 0.020 + 0.014 + 0.003)) / vin
        for _ in range(4):
            r = run(tag, BUCK.format(vin=vin, dfrac=f"{d:.5f}", tag=tag))
            if abs(r["vbat"] - 4.16) < 0.01:
                break
            d *= 4.16 / r["vbat"]
        r["duty"] = d
        res.append((tag, r))
    with open(os.path.join(SIM, "results.txt"), "w") as f:
        f.write("# ngspice results: open-loop power stage, behavioural switches (sim/models.lib)\n")
        for tag, r in res:
            f.write(f"\n[{tag}]\n")
            for k, v in r.items():
                f.write(f"{k} = {v:.6g}\n")
    print(open(os.path.join(SIM, "results.txt")).read())

    fig, axs = plt.subplots(1, 2, figsize=(9, 3.6), dpi=130)
    for c, tag in zip(SERIES, ("buck_18V", "buck_22V")):
        d = load(tag + ".txt")
        t = [x * 1e6 for x in d["time"]]
        sel = [i for i, x in enumerate(t) if 2994 <= x <= 3000]
        axs[0].plot([t[i] - 2994 for i in sel], [d["i(vil)"][i] for i in sel], color=c, lw=1.8,
                    label=tag.replace("buck_", "VIN = ").replace("18V", "17.8 V").replace("22V", "22 V"))
    style(axs[0], "Inductor current, 2 A charge, L = 8 uH, 510 kHz", "time (us)", "I(L1) (A)")
    axs[0].legend(frameon=False, fontsize=8, loc="lower right")
    temps = [x / 2 for x in range(-20, 141)]
    axs[1].plot(temps, [ts(t) * 100 for t in temps], color=SERIES[0], lw=2, label="4.32k / 20.5k (chosen)")
    axs[1].plot(temps, [ts(t, 5.23e3, 30.1e3) * 100 for t in temps], color=SERIES[1], lw=1.5, ls="--",
                label="5.23k / 30.1k (TI example)")
    for y, txt in ((73.5, "cold 73.5 %"), (47.5, "hot 47.5 %"), (45.0, "cut-off 45 %")):
        axs[1].axhline(y, color=MUTED, lw=0.8, ls=":")
        axs[1].text(52, y + 0.6, txt, fontsize=7, color=MUTED)
    style(axs[1], "TS voltage vs cell temperature (103AT, B-model)", "temperature (C)", "TS (% of VREF)")
    axs[1].legend(frameon=False, fontsize=7, loc="lower left")
    fig.tight_layout()
    fig.savefig(os.path.join(DOCS, "sim_charger.png"))
    plt.close(fig)


if __name__ == "__main__":
    main()
