#!/bin/sh
# SPDX-License-Identifier: MIT
# Regenerate the schematic and every derived output.
# KICAD_CLI may point at a wrapper; default is kicad-cli on PATH.
# SYMDIR is the KiCad 9 symbol library directory.
set -e
cd "$(dirname "$0")/.."
KICAD_CLI=${KICAD_CLI:-kicad-cli}
SYMDIR=${SYMDIR:-/usr/share/kicad/symbols}
python3 scripts/gen_schematic.py --symdir "$SYMDIR" --out hardware/adc-input-scaler.kicad_sch
(cd hardware && $KICAD_CLI sch erc --severity-all --output ../docs/erc.rpt adc-input-scaler.kicad_sch)
(cd hardware && $KICAD_CLI sch export netlist --format kicadsexpr -o ../docs/adc-input-scaler.net adc-input-scaler.kicad_sch)
python3 scripts/verify_netlist.py docs/adc-input-scaler.net
(cd hardware && $KICAD_CLI sch export pdf -o ../docs/adc-input-scaler-schematic.pdf adc-input-scaler.kicad_sch)
(cd hardware && $KICAD_CLI sch export bom -o ../docs/adc-input-scaler-bom.csv \
  --fields 'Reference,Value,Footprint,Manufacturer,MPN,Tolerance,${DNP},${QUANTITY}' \
  --labels 'Refs,Value,Footprint,Manufacturer,MPN,Tolerance,DNP,Qty' \
  --group-by 'Value,Footprint,MPN,${DNP}' --ref-range-delimiter '' \
  adc-input-scaler.kicad_sch)
# PNG preview of the schematic for the README (needs poppler-utils)
if command -v pdftoppm >/dev/null 2>&1; then
  pdftoppm -r 150 -png -singlefile docs/adc-input-scaler-schematic.pdf docs/adc-input-scaler-schematic
fi
