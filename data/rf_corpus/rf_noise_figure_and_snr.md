# Noise Figure and SNR Notes

Thermal noise floor in 1 Hz at room temperature is approximately -174 dBm/Hz.

Noise power over bandwidth B:
N(dBm) = -174 + 10log10(B_Hz) + NF(dB)

SNR(dB) = Pr(dBm) - N(dBm)

Example for 20 MHz channel with NF=6 dB:
N = -174 + 10log10(20,000,000) + 6
N = -174 + 73.0 + 6 = -95 dBm

If Pr = -72 dBm, then SNR ≈ 23 dB.
Higher-order modulation requires higher SNR; practical thresholds depend on coding, implementation losses, and interference.
