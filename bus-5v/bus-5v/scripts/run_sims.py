#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
ngspice checks for the 5 V bus. Writes decks into sim/, runs them, saves
sim/results.txt and docs/sim_*.png.

    NGSPICE="ngspice" python3 scripts/run_sims.py

What these simulations are: open-loop power stages with ideal switches whose
on-resistance is the datasheet maximum, plus the input-protection networks
with behavioural MOSFET/diode models (sim/models.lib). They check ripple,
peak current, protection behaviour and VGS clamping. They do NOT model the
LMR33630 or MT3608 control loops, soft-start, current limit or switching
losses; no vendor model is used.
"""
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

PROTECT_A = """* Variant A input protection: DC sweep VIN -24..+24 V into a 10 ohm load
.include models.lib
VIN VIN_A 0 0
* F1 0466003: nominal cold resistance 0.020 ohm (Littelfuse 466 series)
RF1 VIN_A VIN_A_F 0.020
* Q1 SiS443DN: D G S B  (drain on the input side)
MQ1 VIN_A_F Q1_G VIN_A_P VIN_A_P SIS443 W=1 L=1
* D3 BZX84-C12: anode = Q1_G, cathode = VIN_A_P
DD3 Q1_G VIN_A_P BZX84C12
R3 Q1_G 0 100k
* D1 SMAJ24A: anode = GND, cathode = VIN_A_P
DD1 0 VIN_A_P SMAJ24A
RLOAD VIN_A_P 0 10
.control
set wr_singlescale
set wr_vecnames
dc VIN -24 24 0.05
let iin = -i(VIN)
let vgs = v(Q1_G) - v(VIN_A_P)
let vdrop = v(VIN_A) - v(VIN_A_P)
meas dc a_iin_at_m24 FIND iin AT=-23.95
meas dc a_vout_at_m24 FIND v(VIN_A_P) AT=-23.95
meas dc a_vdrop_at_9 FIND vdrop AT=9
meas dc a_vdrop_at_24 FIND vdrop AT=23.95
meas dc a_vgs_at_9 FIND vgs AT=9
meas dc a_vgs_at_24 FIND vgs AT=23.95
wrdata protect_a.txt v(VIN_A_P) iin vgs
quit
.endc
.end
"""

PROTECT_B = """* Variant B input protection: DC sweep VBAT -4.2..+4.2 V into a 2 ohm load
.include models.lib
VB VBAT 0 0
* F2 0466004: nominal cold resistance 0.014 ohm
RF2 VBAT VBAT_F 0.014
MQ2 VBAT_F Q2_G VBAT_P VBAT_P AON6411 W=1 L=1
R9 Q2_G 0 100k
DD4 0 VBAT_P SMAJ85A
RLOAD VBAT_P 0 2
.control
set wr_singlescale
set wr_vecnames
dc VB -4.2 4.2 0.01
let iin = -i(VB)
let vdrop = v(VBAT) - v(VBAT_P)
meas dc b_iin_at_m42 FIND iin AT=-4.19
meas dc b_vdrop_at_3 FIND vdrop AT=3.0
meas dc b_vdrop_at_42 FIND vdrop AT=4.19
meas dc b_iin_at_3 FIND iin AT=3.0
wrdata protect_b.txt v(VBAT_P) iin
quit
.endc
.end
"""

BUCK = """* Variant A power stage, open loop, ideal switches with datasheet RDS(on) max
.include models.lib
.param vin={vin} fsw=340k lval={lval}
.param per={{1/fsw}} ton={{{dfrac}*per}}
VIN VIN_A_P 0 {{vin}}
VG G 0 PULSE(0 1 0 1n 1n {{ton}} {{per}})
VGN GN 0 PULSE(1 0 0 1n 1n {{ton}} {{per}})
SHS VIN_A_P SW G 0 SWHS
SLS SW 0 GN 0 SWLS
DB 0 SW DBODY
VIL SW SWX 0
L1 SWX LX {{lval}}
RDCR LX OUT 0.0298
C7 OUT CX 70u
RESR CX 0 3m
RL OUT 0 2
.ic v(OUT)=5
.control
set wr_singlescale
set wr_vecnames
tran 20n 3m 0 20n uic
meas tran vout AVG v(OUT) FROM=2.5m TO=3m
meas tran vpp PP v(OUT) FROM=2.5m TO=3m
meas tran ipp PP i(VIL) FROM=2.5m TO=3m
meas tran ipk MAX i(VIL) FROM=2.5m TO=3m
linearize v(OUT) i(VIL)
wrdata {tag}.txt v(OUT) i(VIL)
quit
.endc
.end
"""

BOOST = """* Variant B power stage, open loop
.include models.lib
.param vin={vin} fsw=1.2meg lval={lval}
.param per={{1/fsw}} ton={{{dfrac}*per}}
VB VBAT_P 0 {{vin}}
VIL VBAT_P LA 0
L2 LA LB {{lval}}
RDCR LB SW 0.040
S1 SW 0 G 0 SWMT
VG G 0 PULSE(0 1 0 1n 1n {{ton}} {{per}})
DD5 SW OUT SS34
C12 OUT CX 35u
RESR CX 0 3m
RL OUT 0 5
.ic v(OUT)=5
.control
set wr_singlescale
set wr_vecnames
tran 10n 1.5m 0 10n uic
meas tran vout AVG v(OUT) FROM=1.2m TO=1.5m
meas tran vpp PP v(OUT) FROM=1.2m TO=1.5m
meas tran ipp PP i(VIL) FROM=1.2m TO=1.5m
meas tran ipk MAX i(VIL) FROM=1.2m TO=1.5m
meas tran iin AVG i(VIL) FROM=1.2m TO=1.5m
linearize v(OUT) i(VIL)
wrdata {tag}.txt v(OUT) i(VIL)
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


def main():
    res = []
    r = run("protect_a", PROTECT_A)
    res.append(("protect_a", r))
    r = run("protect_b", PROTECT_B)
    res.append(("protect_b", r))

    # buck: duty set from the conduction-loss estimate, so Vout lands near 5 V
    buck = {}
    for vin in (9.0, 24.0):
        for lval, ltag in ((10e-6, "10u"), (8e-6, "8u")):
            dfrac = (5.0 + 2.5 * (0.11 + 0.0298 + 0.003)) / vin
            tag = f"buck_{int(vin)}V_{ltag}"
            r = run(tag, BUCK.format(vin=vin, lval=lval, dfrac=f"{dfrac:.5f}", tag=tag))
            buck[tag] = r
            res.append((tag, r))

    # boost: iterate the open-loop duty until Vout is within 20 mV of 5 V
    boost = {}
    for vin in (3.0, 4.2):
        d = 1 - vin / 5.5
        for _ in range(5):
            tag = f"boost_{vin:.1f}V"
            r = run(tag, BOOST.format(vin=vin, lval=3.76e-6, dfrac=f"{d:.5f}", tag=tag))
            if abs(r["vout"] - 5.0) < 0.02:
                break
            d = 1 - (1 - d) * r["vout"] / 5.0
        r["duty"] = d
        r["pin"] = vin * r["iin"]
        r["eta_stage"] = (r["vout"] ** 2 / 5.0) / r["pin"]
        boost[tag] = r
        res.append((tag, r))

    with open(os.path.join(SIM, "results.txt"), "w") as f:
        f.write("# ngspice results: behavioural models (sim/models.lib), open-loop power stages\n")
        for tag, r in res:
            f.write(f"\n[{tag}]\n")
            for k, v in r.items():
                f.write(f"{k} = {v:.6g}\n")
    print(open(os.path.join(SIM, "results.txt")).read())

    # plots
    a = load("protect_a.txt")
    b = load("protect_b.txt")
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.6), dpi=130)
    axs[0].plot(a["v-sweep"], [x * 1e3 for x in a["iin"]], color=SERIES[0], lw=2)
    style(axs[0], "Variant A: input current vs VIN (10 ohm load)", "VIN (V)", "input current (mA)")
    axs[1].plot(b["v-sweep"], [x * 1e3 for x in b["iin"]], color=SERIES[1], lw=2)
    style(axs[1], "Variant B: input current vs VBAT (2 ohm load)", "VBAT (V)", "input current (mA)")
    fig.tight_layout()
    fig.savefig(os.path.join(DOCS, "sim_reverse_protection.png"))
    plt.close(fig)

    fig, axs = plt.subplots(1, 2, figsize=(9, 3.6), dpi=130)
    for c, tag in zip(SERIES, ("buck_9V_8u", "buck_24V_8u")):
        d = load(tag + ".txt")
        t = [x * 1e6 for x in d["time"]]
        sel = [i for i, x in enumerate(t) if 2990 <= x <= 3000]
        axs[0].plot([t[i] - 2990 for i in sel], [d["i(vil)"][i] for i in sel], color=c, lw=1.8,
                    label=tag.replace("buck_", "").replace("_8u", ", L = 8 uH"))
    style(axs[0], "Buck inductor current, 2.5 A load, f = 340 kHz", "time (us)", "I(L1) (A)")
    axs[0].axhline(3.85, color=INK, ls="--", lw=1)
    axs[0].text(0.2, 3.9, "high-side limit min 3.85 A", fontsize=7, color=INK)
    axs[0].legend(frameon=False, fontsize=8, loc="lower right")
    for c, tag in zip(SERIES, ("boost_3.0V", "boost_4.2V")):
        d = load(tag + ".txt")
        t = [x * 1e6 for x in d["time"]]
        sel = [i for i, x in enumerate(t) if 1495 <= x <= 1500]
        axs[1].plot([t[i] - 1495 for i in sel], [d["i(vil)"][i] for i in sel], color=c, lw=1.8,
                    label=tag.replace("boost_", "VBAT = "))
    style(axs[1], "Boost inductor current, 1 A load, L = 3.76 uH", "time (us)", "I(L2) (A)")
    axs[1].axhline(4.0, color=INK, ls="--", lw=1)
    axs[1].text(0.1, 3.85, "MT3608 limit 4 A (typ only)", fontsize=7, color=INK)
    axs[1].set_ylim(0, 4.5)
    axs[1].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(DOCS, "sim_power_stages.png"))
    plt.close(fig)


if __name__ == "__main__":
    main()
