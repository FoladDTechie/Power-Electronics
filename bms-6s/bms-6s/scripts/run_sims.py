#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
ngspice checks for the 6S BMS. Writes decks into sim/, runs them, saves
sim/results.txt and docs/sim_*.png.

    NGSPICE="ngspice" python3 scripts/run_sims.py

What these simulations are:
  * scd: a short across PACK+/PACK- through an assumed 1 uH / 0.3 Ohm loop.
    The DSG driver is switched off at t = 50 us (the SCD delay is not modelled,
    only the turn-off that follows it). Shows FET energy, VDS and the TVS.
  * chg_off: a 25.2 V charger is connected to a 15 / 18 / 22.2 V pack while CHG
    is disabled (CHG pin pull-down at its 750 kOhm minimum). Shows that the CHG
    FET stays off: PACK- is pulled below VSS and VGS must stay below VGS(th).
  * cascode: DC sweep of the pack voltage with a 10 mA REGSRC load.

They do NOT model the BQ76930 itself (its comparators, delays, ADC or the
CHG/DSG driver internals beyond the datasheet's pull-up/pull-down values),
MOSFET SOA or avalanche, or cell chemistry. MOSFETs are level-1 models
fitted to RDS(on) max and VGS(th) typ (sim/models.lib).
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

# Shared assumptions
RINT = "50m"     # pack internal resistance [ASSUMPTION]

SCD = """* Short circuit at PACK+/PACK-, DSG switched off at 50 us. Node 0 = VSS (B-)
.include models.lib
VB BSRC 0 {vb}
RINT BSRC PACKP {rint}
* short-circuit loop [ASSUMPTION]
LSC PACKP SC1 1u
RSC SC1 PACKN {rsc}
* TVS D1 across the pack terminals
DTVS PACKN PACKP SMCJ26A
* CHG FET Q2: drain MID, source PACKN; gate held by D3 + R13 from the CHG pin (12 V) and R14 to PACKN
VCHG CHGPIN 0 12
RCHGPU CHGPIN CHGP2 5k
DCHG CHGP2 CHGA D1N4148W
RCHG CHGA GQ2 1k
RGS2 GQ2 PACKN 100k
MQ2 MID GQ2 PACKN PACKN IPT012
CGS2 GQ2 PACKN 13n
CGD2 GQ2 MID 0.5n
DB2 PACKN MID DBODYM
* DSG FET Q1: drain MID, source SNS; driven from the DSG pin through R11 100 ohm
VDSG DSGX 0 PWL(0 12 50u 12 50.1u 0)
RDRV DSGX DSGPIN 2.5k
RG1 DSGPIN GQ1 100
RGS1 GQ1 SNS 1meg
VIQ1 MID MIDQ 0
MQ1 MIDQ GQ1 SNS SNS IPT012
CGS1 GQ1 SNS 13n
CGD1 GQ1 MIDQ 0.5n
DB1 SNS MIDQ DBODYM
* sense resistor R1 1 mOhm
RSNS SNS 0 1m
.ic v(GQ1)=12 v(GQ2)=11
.control
set wr_singlescale
set wr_vecnames
tran 20n 400u 0 20n uic
let isc = i(VIQ1)
let vds = v(MIDQ) - v(SNS)
let pq1 = vds*isc
let vpack = v(PACKP) - v(PACKN)
meas tran i_before FIND isc AT=49u
meas tran vds_pk MAX vds FROM=50u TO=400u
meas tran pq1_pk MAX pq1 FROM=50u TO=400u
meas tran eq1 INTEG pq1 FROM=50u TO=400u
meas tran t_off WHEN isc=1 FALL=1
meas tran vpack_min MIN vpack FROM=50u TO=400u
linearize isc vds v(GQ1) pq1
wrdata {tag}.txt isc vds v(GQ1) pq1
quit
.endc
.end
"""

CHG_OFF = """* Charger connected, CHG disabled, DSG enabled. Node 0 = VSS (B-)
.include models.lib
VB BSRC 0 {vb}
RINT BSRC PACKP {rint}
* charger: {vchg} V behind 0.5 ohm [ASSUMPTION]
VCHGR CHPLUS CHMINUS {vchg}
RCH CHPLUS PACKP 0.5
VIM CHMINUS PACKN 0
DTVS PACKN PACKP SMCJ26A
* CHG pin disabled: internal pull-down {rchg} to VSS (datasheet 750k-1.25M)
RCHGOFF CHGPIN 0 {rchg}
DCHG CHGPIN CHGA D1N4148W
RCHG CHGA GQ2 1k
RGS2 GQ2 PACKN 100k
DZ PACKN GQ2 BZX84C15
MQ2 MID GQ2 PACKN PACKN IPT012
DB2 PACKN MID DBODYM
VDSG GQ1 0 12
MQ1 MID GQ1 SNS SNS IPT012
DB1 SNS MID DBODYM
RSNS SNS 0 1m
.control
op
print v(GQ2)-v(PACKN) v(PACKN) i(VIM)
quit
.endc
.end
"""

CASCODE = """* REGSRC cascode: 2N7002 source follower, BZX84-C18 gate clamp, 1 MOhm bias
.include models.lib
VP PACKP 0 25.2
RBIAS PACKP GC 1meg
DZ 0 GC BZX84C18
MC PACKP GC REGSRC 0 N2N7002
CREG REGSRC 0 10u
IL REGSRC 0 10m
.control
set wr_singlescale
set wr_vecnames
dc VP 15 25.2 0.1
let pd = (v(PACKP) - v(REGSRC)) * 0.01
meas dc regsrc_15 FIND v(REGSRC) AT=15
meas dc regsrc_22 FIND v(REGSRC) AT=22.2
meas dc regsrc_25 FIND v(REGSRC) AT=25.1
meas dc gate_25 FIND v(GC) AT=25.1
meas dc pd_25 FIND pd AT=25.1
wrdata cascode.txt v(REGSRC) v(GC) pd
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
    if re.search(r"^Error", log, re.M) or "failed" in log.lower():
        raise SystemExit(f"ngspice problem in {name}, see sim/{name}.log")
    vals = {k: float(v) for k, v in re.findall(r"^(\w+)\s+=\s+([-+0-9.eE]+)", log, re.M)}
    for k, v in re.findall(r"^(v\(gq2\)-v\(packn\)|v\(packn\)|i\(vim\))\s+=\s+([-+0-9.eE]+)", log, re.M):
        vals[{"v(gq2)-v(packn)": "vgs_chg", "v(packn)": "v_packn", "i(vim)": "i_charge"}[k]] = float(v)
    return vals


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
    for vb, rsc in ((25.2, "0.3"), (25.2, "0.05"), (22.2, "0.3")):
        tag = f"scd_{vb:.1f}V_{rsc}ohm".replace(".", "p")
        res.append((tag, run(tag, SCD.format(vb=vb, rsc=rsc, rint=RINT, tag=tag))))
    for vb in (15.0, 18.0, 22.2):
        tag = f"chg_off_pack{vb:.1f}V".replace(".", "p")
        res.append((tag, run(tag, CHG_OFF.format(vb=vb, vchg=25.2, rchg="750k", rint=RINT))))
    res.append(("cascode", run("cascode", CASCODE)))

    with open(os.path.join(SIM, "results.txt"), "w") as f:
        f.write("# ngspice results: behavioural models (sim/models.lib)\n")
        f.write(f"# pack Rint {RINT} ohm; short loop 1 uH; DSG driver 12 V / 2.5 kOhm off at 50 us\n")
        for tag, r in res:
            f.write(f"\n[{tag}]\n")
            for k, v in r.items():
                f.write(f"{k} = {v:.6g}\n")
    print(open(os.path.join(SIM, "results.txt")).read())

    fig, axs = plt.subplots(1, 2, figsize=(10, 3.8), dpi=130)
    for c, tag, lab in ((SERIES[0], "scd_25p2V_0p3ohm", "0.3 ohm short"), (SERIES[1], "scd_25p2V_0p05ohm", "0.05 ohm short")):
        d = load(tag + ".txt")
        t = [x * 1e6 for x in d["time"]]
        axs[0].plot(t, d["isc"], color=c, lw=1.8, label=f"I, {lab}")
        axs[1].plot(t, d["vds"], color=c, lw=1.8, label=f"VDS Q1, {lab}")
    style(axs[0], "Short-circuit current, DSG off at 50 us (6S full)", "time (us)", "A")
    axs[0].legend(frameon=False, fontsize=8)
    axs[1].axhline(42.1, color=INK, ls="--", lw=1)
    axs[1].text(55, 43.5, "SMCJ26A VC at full Ipp", fontsize=7, color=INK)
    style(axs[1], "Discharge FET Q1 drain-source voltage", "time (us)", "V")
    axs[1].legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(os.path.join(DOCS, "sim_scd.png"))
    plt.close(fig)


if __name__ == "__main__":
    main()
