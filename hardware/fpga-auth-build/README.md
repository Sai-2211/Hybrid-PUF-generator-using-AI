# First hardware phase: FPGA PUF authentication

Experimental reference for **Tang Nano 1K + ESP32-C3 SuperMini + laptop**. Start with the [detailed build guide](BUILD_GUIDE.md), [external wiring diagram](circuit.png), [internal circuit diagram](internal-circuit.png), and [verification status](VALIDATION.md).

## How this fits the project

The existing [simulation](../../source/prototype.py) and [Review-II guide](../../source/REVIEW_2_GUIDE.md) implement the educational 64-stage additive-delay Arbiter and 3-XOR comparison with a PyTorch logistic-regression attacker. Its 16,000 synthetic challenges are split into 10,000 training, 2,000 validation, and 4,000 test examples. Those experiments demonstrate modelling vulnerability, not measured silicon security. The AI model is currently an attacker; an AI reliability enhancement remains to be defined and compared with non-AI baselines.

This hardware reference is the next experiment: instantiate one physical Arbiter PUF, collect real repeated CRPs, and demonstrate trusted enrollment and server comparison. It does not implement the full hybrid, a ring-oscillator contribution, a fuzzy extractor, or HMAC key authentication. The latter is a different protocol discussed in the project context, not an implicit feature of this build.

The boards were selected as budget candidates for a ₹2,000 total prototype using an existing laptop and reused equipment. Selection is not evidence that they have been purchased or qualified. A second identical FPGA, preferably borrowed, is needed for inter-chip uniqueness and impostor experiments.

## What is included

- `fpga/`: Gowin LUT-based experimental PUF, UART/parser/controller, verified external pin assignments, and system clock constraint. The default build has PUF evaluation disabled so communication checks cannot be mistaken for identity measurements.
- `esp32_bridge/`: native-USB to UART firmware; GPIO0 TX, GPIO1 RX, optional GPIO3 verdict display.
- `server.py`: actual serial measurements, SQLite enrollment, majority voting, fresh-CRP consumption, authentication decisions, characterization, and CSV export. There is no mock-response fallback.
- `PROTOCOL.md`: packet format, byte order, statuses, CRC, and USB commands.
- `tests/`: explicitly synthetic server tests, a desktop firmware API stub, and Verilog serial-wire integration tests using ideal primitive models. They do not validate physical PUF behaviour.

## Run the software checks

The server test needs only Python's standard library:

```sh
python3 tests/test_server.py
```

The firmware helper test needs a C++17 compiler. Its output goes outside the repository:

```sh
c++ -std=c++17 -Wall -Wextra -I tests/firmware_api_stub tests/firmware_api_stub/check.cpp -o /tmp/puf-firmware-check
/tmp/puf-firmware-check
```

With [Icarus Verilog](https://steveicarus.github.io/iverilog/usage/installation.html) installed and `iverilog`/`vvp` on your PATH:

```sh
python3 tests/run_hdl.py
```

This compiles both FPGA modes and checks LUT switch truth tables, UART framing, packets, CRC, challenge byte order, repeated evaluation control, disabled-PUF rejection, malformed requests, timeout recovery, and reset. `IVERILOG` and `VVP` environment variables can select alternate executable paths. Primitive models are ideal and contain no process variation; simulated bits are not device fingerprints. Do not add `tests/gowin_functional_models.v` to a Gowin hardware project.

Compile/upload the firmware separately using the actual Espressif board package. Synthesize and physically constrain the FPGA separately in Gowin. Desktop checks do not substitute for those steps.

## Connect actual hardware

ESP GPIO0 → Tang package-pin pad 27; Tang pad 28 → ESP GPIO1; GND → GND. Power each board through its own USB data cable and leave power rails unconnected. The FPGA numbers identify package pins rather than header ordinal positions. Follow the manufacturer pin map and full build guide.

Install the server dependency in a virtual environment and discover the ESP port:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py ports
```

On Windows use `.venv\Scripts\python.exe`. The build guide provides commands for PING/LOOP, repeated measurements, enrollment, later characterization, authentication, and export. Default records are stored locally under `records/`, which is ignored by Git.

## Required remaining evidence

No matched PUF floorplan/routing constraints, qualified bitstream, or physical response dataset is supplied. Preserve all 128 stage LUTs plus launch buffers, inspect terminal routes into D/CLK, pass ordinary controller/UART timing, and measure repeatability and differences between real chips before claiming device discrimination.

Plain Arbiter PUF responses can be modelled. Fresh challenge use and a successful login do not establish general resistance to impersonation. This protocol identifies access to the attached FPGA under laboratory assumptions; it does not independently attest the MCU identity/firmware or prevent relay to the genuine FPGA.
