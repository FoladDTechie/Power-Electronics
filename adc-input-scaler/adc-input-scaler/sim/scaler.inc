* SPDX-License-Identifier: CERN-OHL-P-2.0
* ADC input scaler, net names match hardware/adc-input-scaler.kicad_sch.
* Parameters: rbyp (R7: 1m = variant A fitted, 1T = variant B, DNP)
*             r2val (R2, set to 1T to simulate an open bottom resistor)
.include models.lib
* --- high-side switch (variant B) ---
* Q1 BSS84: D G S B  (SOT-23 pins 3,1,2)
MQ1 VSW Q1_G VIN VIN BSS84M W=1u L=1u
CQ1 VIN Q1_G 30p
R4 VIN Q1_G 100k
* D2 BZX84-C12: anode (pin 1) = Q1_G, cathode (pin 3) = VIN
DD2 Q1_G VIN BZX84C12
R5 Q1_G Q2_D 22k
* Q2 BSS138: D G S B  (SOT-23 pins 3,1,2)
MQ2 Q2_D SENSE_EN 0 0 BSS138M W=1u L=1u
CQ2 SENSE_EN 0 27p
R6 SENSE_EN 0 100k
R7 VIN VSW {rbyp}
* --- divider / filter / clamp ---
R1 VSW ADC_DIV 200k
R2 ADC_DIV 0 {r2val}
C1 ADC_DIV 0 100n
* D1 BAT54S: pin1 = A (lower diode anode) = GND, pin3 = COM = ADC_DIV, pin2 = K = +3V3
DD1L 0 ADC_DIV BAT54
DD1H ADC_DIV P3V3 BAT54
R3 ADC_DIV ADC_OUT 1k
* --- ESP32-S3 pin (assumed) ---
CPIN ADC_OUT 0 2p
DESDH ADC_OUT P3V3 ESD_SI
DESDL 0 ADC_OUT ESD_SI
V3V3 P3V3 0 3.3
