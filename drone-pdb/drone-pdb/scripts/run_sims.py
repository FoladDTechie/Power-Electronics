#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""
ngspice checks for the drone power board. Writes decks into sim/, runs them,
saves sim/results.txt and docs/sim_*.png.

    NGSPICE="ngspice" python3 scripts/run_sims.py

What these simulations are:
  * plug-in: the battery is connected at t = 0 through an assumed pack
    resistance and lead inductance. With the anti-spark circuit, the run covers
    precharge, main-FET turn-on and the delayed BEC start (each BEC is a
    constant-power load switched on by its EN network). Without it, the bus
    capacitance is connected straight to the battery.
  * BEC power stages: TPS54360 power stage, open loop, ideal high-side switch at
    the datasheet maximum RDS(on), a Schottky fitted to one datasheet point.

They do NOT model the TPS54360 control loop, soft-start or current limit, the
MOSFET SOA, avalanche, contact arcing, or the real ESC input stages. MOSFETs
are level-1 models fitted to RDS(on) max and VGS(th) typ (sim/models.lib).
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

# Assumptions shared by both plug-in decks
RPACK = "15m"     # pack internal resistance [ASSUMPTION]
LLEAD = "150n"    # battery leads + XT60 [ASSUMPTION]
CLOAD = "2200u"   # 2 x 470 uF on board + ESC input capacitors [ASSUMPTION]
RESR = "20m"      # combined ESR of CLOAD [ASSUMPTION]
PBEC = 32         # W drawn by both BECs at full load (5 V 2 A + 12 V 1.5 A, eta 0.88)

PLUG_AS = """* Plug-in WITH the anti-spark circuit. Node 0 = BAT_N (battery negative)
.include models.lib
VB BSRC 0 PWL(0 0 1u {vb})
RPACK BSRC BL {rpack}
LLEAD BL BL2 {llead}
VIB BL2 BAT_P 0
* R1: WSK2512 0.5 mOhm high-side shunt
RSH BAT_P BUS 0.5m
* bus capacitance and loads, all returning to PGND
C1 BUS CX {cload}
RESR CX PGND {resr}
RESC BUS PGND {resc}
* BEC enable network (one BEC's divider; both are identical) and BEC load
R1 BUS EN 294k
R2 EN PGND 38.3k
CEN EN PGND 39.6u
BBEC BUS PGND I = {pbec}/max(v(BUS,PGND),8) * 0.5*(1+tanh(40*(v(EN,PGND)-1.2)))
* gate supply: R_SUP, zener to BAT_N
RSUP BAT_P GSUP 22k
DZ 0 GSUP BZX84C12
* precharge switch Q3 + R_PRE (2S2P of 10 ohm = 10 ohm)
RGP GSUP GP 10k
CGP GP 0 0.6n
VIPRE PGND PRE1 0
RPRE PRE1 DPRE 10
MQ3 DPRE GP 0 0 BUK7M42
DQ3 0 DPRE DBODYP
* main switch Q1 || Q2, gate delay R_GM / C_GM, fast discharge D + 100 ohm
RGM GSUP GM 1meg
CGM GM 0 1u
CISS GM 0 26n
DGM GM GX D1N4148W
RGX GX GSUP 100
VIM PGND DM 0
MQ1 DM GM 0 0 IPT012X2
DQ1 0 DM DBODYM
.control
set wr_singlescale
set wr_vecnames
tran 2u 3 0 20u
let ibat = i(VIB)
let vds = v(PGND)
let vbus = v(BUS) - v(PGND)
let ven = v(EN) - v(PGND)
let ppre = i(VIPRE)*i(VIPRE)*10
let pmain = v(PGND)*i(VIM)
meas tran ipk MAX ibat FROM=0 TO=0.05
meas tran ppre_pk MAX ppre FROM=0 TO=0.05
meas tran epre INTEG ppre FROM=0 TO=3
meas tran t_main WHEN i(VIM)=0.5 RISE=1
meas tran vds_main FIND vds WHEN i(VIM)=0.5 RISE=1
meas tran t_bec WHEN ven=1.2 RISE=1
meas tran vgs_bec FIND v(GM) WHEN ven=1.2 RISE=1
meas tran vds_bec FIND vds WHEN ven=1.2 RISE=1
meas tran pmain_pk MAX pmain FROM=0 TO=3
meas tran emain INTEG pmain FROM=0 TO=3
meas tran vds_end FIND vds AT=2.99
meas tran vgs_end FIND v(GM) AT=2.99
meas tran ibat_end FIND ibat AT=2.99
linearize ibat vds vbus ven v(GM)
wrdata {tag}.txt ibat vds vbus ven v(GM)
quit
.endc
.end
"""

PLUG_DIRECT = """* Plug-in WITHOUT anti-spark: bus capacitance straight onto the battery
.include models.lib
VB BSRC 0 PWL(0 0 1u {vb})
RPACK BSRC BL {rpack}
LLEAD BL BL2 {llead}
VIB BL2 BAT_P 0
RSH BAT_P BUS 0.5m
C1 BUS CX {cload}
RESR CX PGND {resr}
RESC BUS PGND {resc}
* closed main switch (2 x 1.2 mOhm max in parallel)
RQ PGND 0 0.6m
.control
set wr_singlescale
set wr_vecnames
tran 0.2u 5m 0 0.2u
let ibat = i(VIB)
meas tran ipk MAX ibat FROM=0 TO=5m
meas tran t_pk WHEN ibat=ipk_val CROSS=1
linearize ibat
wrdata {tag}.txt ibat
quit
.endc
.end
"""

BUCK = """* TPS54360 power stage, open loop
.include models.lib
.param vin={vin} fsw=600k lval={lval}
.param per={{1/fsw}} ton={{{dfrac}*per}}
VIN VIN 0 {{vin}}
VG G 0 PULSE(0 1 0 1n 1n {{ton}} {{per}})
SHS VIN SW G 0 SWHS
DCATCH 0 SW SS36
VIL SW SWX 0
L1 SWX LX {{lval}}
RDCR LX OUT {dcr}
COUT OUT CX {cout}
RESR CX 0 {esr}
RL OUT 0 {rload}
.ic v(OUT)={vout}
.control
set wr_singlescale
set wr_vecnames
tran 10n 2m 0 10n uic
meas tran vout AVG v(OUT) FROM=1.7m TO=2m
meas tran vpp PP v(OUT) FROM=1.7m TO=2m
meas tran ipp PP i(VIL) FROM=1.7m TO=2m
meas tran ipk MAX i(VIL) FROM=1.7m TO=2m
meas tran iin AVG i(VIN) FROM=1.7m TO=2m
linearize v(OUT) i(VIL)
wrdata {tag}.txt v(OUT) i(VIL)
quit
.endc
.end
"""

STAGES = {
    "5V": {"vout": 5.0, "iout": 2.0, "lval": "8u", "dcr": 0.02982, "cout": "30.8u", "esr": "1.5m",
           "vins": (12.0, 25.2)},
    "12V": {"vout": 12.0, "iout": 1.5, "lval": "17.6u", "dcr": 0.0606, "cout": "22.5u", "esr": "1m",
            "vins": (16.8, 25.2)},
}


def run(name, text):
    path = os.path.join(SIM, name + ".cir")
    open(path, "w").write(text)
    p = subprocess.run(CMD + ["-b", name + ".cir"], cwd=SIM, capture_output=True, text=True)
    log = p.stdout + p.stderr
    open(os.path.join(SIM, name + ".log"), "w").write(log)
    if re.search(r"^Error", log, re.M) or "failed" in log.lower():
        raise SystemExit(f"ngspice problem in {name}, see sim/{name}.log")
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
    common = {"rpack": RPACK, "llead": LLEAD, "cload": CLOAD, "resr": RESR, "pbec": PBEC}
    for vb in (16.8, 25.2):
        resc = f"{vb/0.2:.0f}"          # ESC idle 0.2 A at full charge [ASSUMPTION]
        tag = f"plug_antispark_{vb:.1f}V".replace(".", "p")
        res.append((tag, run(tag, PLUG_AS.format(vb=vb, resc=resc, tag=tag, **common))))
        tag = f"plug_direct_{vb:.1f}V".replace(".", "p")
        deck = PLUG_DIRECT.format(vb=vb, resc=resc, tag=tag, **common).replace(
            "meas tran t_pk WHEN ibat=ipk_val CROSS=1\n", "")
        res.append((tag, run(tag, deck)))

    for name, s in STAGES.items():
        for vin in s["vins"]:
            d = s["vout"] / vin
            tag = f"bec{name}_{vin:.1f}V".replace(".", "p")
            for _ in range(6):
                r = run(tag, BUCK.format(vin=vin, dfrac=f"{d:.5f}", tag=tag, rload=s["vout"] / s["iout"],
                                         **{k: s[k] for k in ("lval", "dcr", "cout", "esr", "vout")}))
                if abs(r["vout"] - s["vout"]) < 0.02 * s["vout"] / 5:
                    break
                d *= s["vout"] / r["vout"]
            r["duty"] = d
            r["eta_stage"] = (r["vout"] ** 2 / (s["vout"] / s["iout"])) / (vin * -r["iin"])
            res.append((tag, r))

    with open(os.path.join(SIM, "results.txt"), "w") as f:
        f.write("# ngspice results: behavioural models (sim/models.lib)\n")
        f.write(f"# plug-in assumptions: pack {RPACK} ohm, leads {LLEAD}H, C_LOAD {CLOAD}F, "
                f"ESR {RESR} ohm, ESC idle 0.2 A, BEC load {PBEC} W\n")
        f.write("# BEC stages: worst-case L (-20 %), open loop, duty iterated to hit Vout\n")
        for tag, r in res:
            f.write(f"\n[{tag}]\n")
            for k, v in r.items():
                f.write(f"{k} = {v:.6g}\n")
    print(open(os.path.join(SIM, "results.txt")).read())

    # plug-in plots
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.8), dpi=130)
    a = load("plug_antispark_25p2V.txt")
    b = load("plug_direct_25p2V.txt")
    ta = [x * 1e3 for x in a["time"]]
    tb = [x * 1e3 for x in b["time"]]
    axs[0].plot(tb, b["ibat"], color=SERIES[1], lw=1.8, label="no anti-spark")
    sel = [i for i, t in enumerate(ta) if t <= 5]
    axs[0].plot([ta[i] for i in sel], [a["ibat"][i] for i in sel], color=SERIES[0], lw=1.8,
                label="with precharge")
    axs[0].set_yscale("symlog", linthresh=1)
    style(axs[0], "Battery current at plug-in, 6S 25.2 V", "time (ms)", "I battery (A)")
    axs[0].legend(frameon=False, fontsize=8)
    ts = [x for x in a["time"]]
    axs[1].plot(ts, a["vbus"], color=SERIES[0], lw=1.6, label="bus (BAT+ to PGND)")
    axs[1].plot(ts, a["vds"], color=SERIES[1], lw=1.6, label="main FET VDS")
    axs[1].plot(ts, a["v(gm)"], color=SERIES[2], lw=1.6, label="main FET VGS")
    axs[1].plot(ts, [x * 5 for x in a["ven"]], color=SERIES[3], lw=1.2, ls="--", label="BEC EN x5")
    style(axs[1], "Start-up sequence, 6S 25.2 V", "time (s)", "V")
    axs[1].legend(frameon=False, fontsize=7, loc="center right")
    fig.tight_layout()
    fig.savefig(os.path.join(DOCS, "sim_antispark.png"))
    plt.close(fig)

    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6), dpi=130)
    for ax, name in zip(axs, STAGES):
        for c, vin in zip(SERIES, STAGES[name]["vins"]):
            tag = f"bec{name}_{vin:.1f}V".replace(".", "p")
            d = load(tag + ".txt")
            t = [x * 1e6 for x in d["time"]]
            sel = [i for i, x in enumerate(t) if 1990 <= x <= 2000]
            ax.plot([t[i] - 1990 for i in sel], [d["i(vil)"][i] for i in sel], color=c, lw=1.8,
                    label=f"VIN {vin} V")
        ax.axhline(4.5, color=INK, ls="--", lw=1)
        ax.text(0.2, 4.55, "current limit min 4.5 A", fontsize=7, color=INK)
        ax.set_ylim(0, 5)
        style(ax, f"{name} BEC inductor current, L -20 %", "time (us)", "I(L) (A)")
        ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(os.path.join(DOCS, "sim_bec.png"))
    plt.close(fig)


if __name__ == "__main__":
    main()
