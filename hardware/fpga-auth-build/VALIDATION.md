# Verification status — 14 October 2026

This package is a reference laboratory build, not a hardware-qualified PUF implementation.

| Item | Status |
|---|---|
| Tang Nano 1K external signal assignments | Checked against manufacturer pin map and examples: RX 27, TX 28, clock 47, KEY_A reset 13 |
| ESP32-C3 external UART and native USB | Checked against primary documentation; reference assigns Serial1 RX 1 / TX 0 and enables USB CDC |
| Python syntax | Passed on Python 3.13; uses Python 3.10+ syntax |
| Enrollment and raw-record persistence | Passed with explicitly synthetic transport |
| Matching and different responses | Passed software acceptance/rejection checks with synthetic transport |
| Failed communication | Produces ERROR and retains consumption of reserved challenges |
| Exhausted challenge pool | Fails without consuming extra CRPs |
| Communication-only response | Rejected as a source for enrollment/authentication |
| Echoed challenge and response length | Validated; malformed reply rejected |
| Later characterization | Passed with synthetic transport |
| Changed bitstream hash | Rejected under existing device ID |
| CSV export | Four files generated and checked |
| MCU helper code | Desktop C++ compile/test against an Arduino API stub passed CRC check vector, frame exchange, READ/LOOP parsing, invalid arguments, verdict output, disabled-PUF and corrupt-response cases |
| Actual Espressif SDK compile/upload | Not performed; installed CLI and cross-compiler are x86_64 executables that cannot run in this arm64 environment; no board attached |
| FPGA HDL functional compilation and simulation | Passed with Icarus Verilog 12.0: both top modes, switch truth tables, serial-wire packets, challenge loading and repeated evaluation control, CRC, disabled-PUF and unknown-command rejection, packet timeout, and reset |
| FPGA vendor synthesis/place-and-route/timing | Not performed; Gowin toolchain not attached |
| Matched physical PUF constraints | Not supplied; choose and verify in Gowin |
| Physical response statistics and authentication | Not measured; actual boards required |

The desktop MCU test does not emulate ESP hardware, cross-compile for its processor, or validate USB/UART operation on a board. Synthetic software test records are kept outside this deliverable and are not represented as measured results. No mock-response fallback exists in server.py or the FPGA READ protocol.

The HDL test uses ideal LUT1/LUT4/DFFC models supplied under `tests/` only. It does not simulate manufacturing variation, metastability, matched routing, or reliable silicon identity. Its result bits must not be used as a CRP dataset. Use actual Gowin primitive libraries for vendor implementation.

Reproducible checks are included under `tests/`; see the package README for the Python and C++ commands. Generated test records and compiled test binaries are not committed.
