#!/bin/sh
# SPDX-License-Identifier: MIT
# Regenerate the schematic and every derived file. Needs kicad-cli (KiCad 9),
# python3 and pdftoppm. Run from the project root:
#   KICAD_CLI=kicad-cli SYMDIR=/usr/share/kicad/symbols sh scripts/build.sh
set -e
KICAD_CLI=${KICAD_CLI:-kicad-cli}
SYMDIR=${SYMDIR:-/usr/share/kicad/symbols}
P=bms-6s
python3 scripts/gen_schematic.py --symdir "$SYMDIR" --out hardware/$P.kicad_sch
(cd hardware && $KICAD_CLI sch erc --severity-all --output ../docs/erc.rpt $P.kicad_sch)
(cd hardware && $KICAD_CLI sch export netlist --format kicadsexpr -o ../docs/$P.net $P.kicad_sch)
python3 scripts/verify_netlist.py docs/$P.net
(cd hardware && $KICAD_CLI sch export pdf -o ../docs/$P-schematic.pdf $P.kicad_sch)
(cd hardware && $KICAD_CLI sch export bom -o ../docs/$P-bom.csv --fields 'Reference,Value,Footprint,Manufacturer,MPN,Voltage,Tolerance,${DNP},${QUANTITY}' --labels 'Refs,Value,Footprint,Manufacturer,MPN,Voltage,Tolerance,DNP,Qty' --group-by 'Value,Footprint,MPN,${DNP}' --ref-range-delimiter '' $P.kicad_sch)
pdftoppm -r 150 -png -singlefile docs/$P-schematic.pdf docs/$P-schematic
