#!/bin/sh
# SPDX-License-Identifier: MIT
# Regenerate the schematic and every derived output.
# KICAD_CLI may point at a wrapper; default is kicad-cli on PATH.
# SYMDIR is the KiCad 9 symbol library directory.
set -e
cd "$(dirname "$0")/.."
KICAD_CLI=${KICAD_CLI:-kicad-cli}
SYMDIR=${SYMDIR:-/usr/share/kicad/symbols}
python3 scripts/gen_schematic.py --symdir "$SYMDIR" --out hardware/solar-charger.kicad_sch
(cd hardware && $KICAD_CLI sch erc --severity-all --output ../docs/erc.rpt solar-charger.kicad_sch)
(cd hardware && $KICAD_CLI sch export netlist --format kicadsexpr -o ../docs/solar-charger.net solar-charger.kicad_sch)
python3 scripts/verify_netlist.py docs/solar-charger.net
(cd hardware && $KICAD_CLI sch export pdf -o ../docs/solar-charger-schematic.pdf solar-charger.kicad_sch)
(cd hardware && $KICAD_CLI sch export bom -o ../docs/solar-charger-bom.csv \
  --fields 'Reference,Value,Footprint,Manufacturer,MPN,Voltage,Tolerance,${DNP},${QUANTITY}' \
  --labels 'Refs,Value,Footprint,Manufacturer,MPN,Voltage,Tolerance,DNP,Qty' \
  --group-by 'Value,Footprint,MPN,${DNP}' --ref-range-delimiter '' \
  solar-charger.kicad_sch)
# PNG preview of the schematic for the README (needs poppler-utils)
if command -v pdftoppm >/dev/null 2>&1; then
  pdftoppm -r 150 -png -singlefile docs/solar-charger-schematic.pdf docs/solar-charger-schematic
fi
