# RF Link Budget Basics

A received signal level can be approximated with:

Pr(dBm) = Pt(dBm) + Gt(dBi) + Gr(dBi) - FSPL(dB) - Lmisc(dB)

Free-space path loss (FSPL):

FSPL(dB) = 32.44 + 20log10(f_MHz) + 20log10(d_km)

Example:
- Frequency: 2400 MHz
- Distance: 5 km
- Transmit power: 20 dBm
- Tx gain: 12 dBi
- Rx gain: 12 dBi
- Misc losses: 2 dB

FSPL = 32.44 + 20log10(2400) + 20log10(5) ≈ 114.0 dB
Pr = 20 + 12 + 12 - 114 - 2 = -72 dBm

If receiver sensitivity for required data rate is -84 dBm, link margin is 12 dB.
Typical design target for stable outdoor links is at least 10 dB margin.
