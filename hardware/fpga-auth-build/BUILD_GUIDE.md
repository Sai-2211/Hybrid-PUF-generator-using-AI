# Detailed circuit build: Tang Nano 1K + ESP32-C3 SuperMini

This is a concrete laboratory reference design: external wiring, experimental FPGA RTL, ESP firmware, and a laptop server. It has not been run on these boards. The PUF's matched placement and routing remain a required implementation step; no qualified bitstream is supplied. The Python workflow has been checked with synthetic transport, which is not evidence of real PUF performance.

Use **Sipeed Tang Nano 1K, GW1NZ-LV1QN48C6/I5**, and **ESP32-C3 SuperMini with native USB-C**. Earlier Basys 3 or ESP32-WROOM pin assignments do not apply. Identify the SuperMini pads by their GPIO labels because third-party board layouts can vary.

## Complete external circuit

Open `circuit.png` for the wiring diagram and `internal-circuit.png` for the FPGA logic.

| Connection | From | To |
|---|---|---|
| Commands / challenges | ESP pad **0 / GPIO0**, configured UART TX | Tang pad **27**, IO_R7A, configured UART RX |
| Measured responses | Tang pad **28**, IO_R6T1, configured UART TX | ESP pad **1 / GPIO1**, configured UART RX |
| Common ground | ESP **G / GND** | Tang **GND** |
| Laptop cable 1 | Laptop USB | ESP USB-C: power, firmware upload, server data |
| Laptop cable 2 | Laptop USB | Tang USB-C: power and FPGA programming |
| Optional LED | ESP **GPIO3** → **1 kΩ resistor** → LED anode (+) | LED cathode (−) → ESP GND |

The FPGA labels **27 and 28 are package-pin numbers, not header ordinal positions**. In Sipeed's manufacturer pin-map top view, with USB at the top, these are the bottom two signal pads on the left: 27 above 28. They also correspond to the LCD G1/G0 signals; leave the LCD connector unused. Check the actual board against the manufacturer's map before connecting. Use a pad labelled GND.

Both interfaces use **3.3 V logic**. UART is **115200 baud, 8 data bits, no parity, 1 stop bit**. Power each board through its own USB cable and leave the boards' 5 V and 3.3 V rails unconnected. No level shifter is needed between these two 3.3 V interfaces. No off-board clock, regulator, external multiplexer IC, or separate FPGA programmer is required.

Fit the supplied header strips with lab soldering equipment if necessary. With power disconnected, connect the three short jumper wires; start with lengths around 10–15 cm. Use two USB-C data cables, not charge-only cables. Reuse cables and lab equipment to preserve the ₹2,000 budget. The optional LED is not required.

The ESP native USB uses GPIO18/19 internally. Our external UART uses GPIO0/1 through Serial1. GPIO2/8/9 are boot-strapping pins and are not used by this wiring. The Tang board already has the oscillator on package pin **47** and KEY_A on package pin **13**; those are internal board connections, not new jumper wires. KEY_A is the reference controller reset input, with a pull-up configured.

For power-cycle measurements, power-cycle both boards together. If cycling the FPGA alone, disconnect its TX/RX jumper connections before removing its USB power, then restore power/configuration before reconnecting the signal wires. A powered MCU can otherwise supply current through an unpowered FPGA's I/O protection circuitry.

## Internal FPGA circuit

The source creates UART RX → frame parser → challenge register / evaluation controller → 64 switch stages → arbiter → synchronizer / held result → UART TX.

For each stage i:

```
upper[i+1] = C[i] ? lower[i] : upper[i]
lower[i+1] = C[i] ? upper[i] : lower[i]
```

C[i]=0 keeps the paths straight; C[i]=1 crosses them. Both multiplexers share that select bit. C[0] controls the first stage, C[63] the last. The challenge travels as eight bytes and is stored in a 64-bit register, so only one UART wire is needed to send it.

Each stage uses two Gowin LUT4 primitives. The reference assigns INIT=CACA to the upper LUT and ACAC to the lower LUT, with I0=upper, I1=lower, I2=challenge, I3=0. Two separate LUT1 launch buffers feed the paths. Thus the physical PUF core has **128 stage LUT4s + 2 launch LUT1s + 1 arbiter flip-flop**, plus the controller and communication logic. Verify all these cells survive synthesis and implementation.

The arbiter is a **DFFC**, providing asynchronous clear:

| Arbiter input/output | Connection |
|---|---|
| D | Final upper path, upper[64] |
| CLK | Final lower path, lower[64] |
| CLEAR | Evaluation controller |
| Q | Two registers clocked by the 27 MHz system clock, then the held result |

An upper transition sufficiently earlier than the lower captures 1; an upper transition sufficiently later captures 0. A close race can be unstable. Gowin **DFFR has synchronous reset**, so it is not a substitute for DFFC here. The race-path signal feeding CLK is intentionally asynchronous to the system clock.

Evaluation sequence:

1. Latch the challenge, hold launch low, and assert arbiter clear.
2. Wait 256 system clocks, approximately 9.48 μs at 27 MHz.
3. Release clear and wait another 256 clocks.
4. Drive launch high and allow the two paths to propagate through all stages.
5. Wait another 256 clocks and capture the synchronized output into the result register.
6. Hold the result for UART transmission, then bring launch low and clear the arbiter for the next evaluation.

These waits are starting values, not measured hardware margins. Compare them with implemented path delays and adjust if needed. Synchronization reduces propagation of metastability into the controller; it does not guarantee a repeatable PUF response. The system clock sequences measurements rather than counting cycles to decide the faster path.

**One 64-bit challenge produces one response bit.** A 128-bit response requires 128 different challenges. Seven repetitions of one challenge are seven observations of the same identity bit; the server votes them into one bit.

## Program the ESP32-C3

1. Install Arduino IDE and Espressif ESP32 board support using Boards Manager.
2. Open `esp32_bridge/esp32_bridge.ino`.
3. Select **ESP32C3 Dev Module** for a generic SuperMini. Set **USB CDC On Boot → Enabled**.
4. Select the ESP native USB port and upload. For the first upload, if necessary hold BOOT, tap RESET, release BOOT, then choose the newly appeared port. Reset after first flashing if necessary.
5. The code uses `Serial` for laptop USB and `Serial1.begin(115200, SERIAL_8N1, 1, 0)` for the FPGA. The last arguments mean RX=1, TX=0.
6. After programming the FPGA, use Arduino Serial Monitor with newline ending to test the commands below. Close Serial Monitor before running the server; only one application should own the port.

```
PING
LOOP 0123456789ABCDEF
READ 0123456789ABCDEF 7
VERDICT 1
VERDICT 0
```

READ takes an odd repetition count 1–31 and returns every raw bit. An illustrative reply is `OK READ 0123456789ABCDEF 1110111`. The firmware checks FPGA reply sequence and CRC; it does not store expected responses or decide identity. VERDICT controls only the optional external LED on GPIO3. The onboard boot LED is not used.

## Program the FPGA and qualify the PUF

Install Gowin EDA Education with GW1NZ-1 support, following Sipeed's installation guide for your operating system. Use the exact GW1NZ-LV1 QN48 C6/I5 part fitted to the board. If the included programmer does not detect the board, follow Sipeed's recommended programmer/driver procedure.

Create a project, set **top** as the top module, and add:

```
fpga/top.v
fpga/uart.v
fpga/puf64.v
fpga/pins.cst
fpga/timing.sdc
```

The supplied CST assigns clk=47, reset_n=13, uart_rx_pin=27, uart_tx_pin=28, all using LVCMOS33, with pull-ups on reset and RX. The SDC defines the 27 MHz clock with period 37.037 ns. Gowin supplies LUT1/LUT4/DFFC primitives; no extra hardware is needed for them.

**First compile with ENABLE_PUF=0.** Run synthesis and place-and-route, review the reports, generate the `.fs` bitstream, and program it through the board's USB-JTAG connection. Start with SRAM programming for easy changes. In this build:

```
PING → OK PING LINK_ONLY 64
LOOP 0123456789ABCDEF → OK LOOP EF
READ ... → ERR PUF_DISABLED
```

These checks verify wiring and the whole communication path. A loopback byte is never used as a PUF response.

Then set **ENABLE_PUF=1** and implement the experimental physical core. Before interpreting responses as chip identity:

- Inspect synthesized and implemented netlists for all 128 stage LUT4s, two launch LUT1s, and the arbiter. Net attributes are not sufficient evidence of preservation.
- Choose and record paired LUT placements, LUT input mappings, launch-buffer placement, and arbiter placement using Gowin floorplanning and physical constraints for this device. The supplied CST constrains only externally verified board pins. **It does not supply a balanced PUF floorplan or matched routing.**
- Inspect straight and cross routes and especially the two terminal routes to D and CLK. Consider and inspect an appropriate local/fabric route to the arbiter clock input. A global-clock route on only one race path can create large systematic bias. Use the constraints supported by your installed release rather than copying another FPGA family's settings.
- Review clock, CDC, and timing warnings. Ordinary UART/controller timing must pass; document the intentional race path and synchronizer. No blanket timing waiver is supplied.
- Measure many challenges repeatedly. Almost constant responses, very noisy responses, or nearly identical responses across chips indicate a design problem to investigate.

This is the difficult part of a physical FPGA arbiter PUF. Resource capacity alone does not guarantee good delay behaviour. If routing bias dominates device variation, modify the physical design and repeat measurement. Preserve each build's constraints, reports, bitstream, and measurements; do not generate a software fingerprint to conceal an unsuitable circuit.

After the PUF-enabled build, PING reports `OK PING PUF 64`; READ returns measurements. Once the design is qualified, freeze the exact bitstream. A new routing solution may change the fingerprint and require new enrollment. SRAM programming is lost after power removal; reload the identical `.fs` after power cycling, or configure nonvolatile boot using Sipeed's documented procedure.

## Use the laptop as the server

The Python process on your laptop owns the enrollment database and makes the authentication decision. It connects to the ESP through USB serial; there is no website, network listener, paid hosting, or Internet requirement for runtime operation. Initial software downloads need Internet access. Colab can model the process but is not the default host for the laptop's physical USB connection.

Install Python 3.10 or newer. Open a terminal in the extracted `fpga-auth-build` folder:

```
python3 -m venv .venv
```

On macOS/Linux activate with `source .venv/bin/activate`. On Windows, use `py -3 -m venv .venv`, then `.venv\Scripts\Activate.ps1` in PowerShell, or call `.venv\Scripts\python.exe` directly if activation is restricted. Then:

```
python -m pip install -r requirements.txt
python server.py ports
```

Identify the ESP port, for example COM5 on Windows, /dev/cu.usbmodem... on macOS, or /dev/ttyACM0 on Linux. If two devices appear, unplug/reconnect only the ESP to identify it. The server uses **the ESP port, not the FPGA programmer port**. Replace YOUR_ESP_PORT in every following command.

```
python server.py ping --port YOUR_ESP_PORT
python server.py loop --port YOUR_ESP_PORT --challenge 0123456789ABCDEF
```

After enabling and implementing the physical PUF, explore repeatability:

```
python server.py probe --port YOUR_ESP_PORT --challenge 0123456789ABCDEF --repeats 31
```

Probe prints raw bits and majority for one challenge. Try many distinct challenges; this exploratory command does not automatically enroll or save them.

Enroll the genuine device through a trusted connection, with the exact `.fs` file you programmed:

```
python server.py enroll --port YOUR_ESP_PORT --device FPGA_A --bitstream YOUR_PROGRAMMED_FILE.fs --challenges 1024 --repeats 31 --min-agreement 30
```

This saves all raw samples and reference CRPs, including unstable CRPs. A challenge is initially eligible when at least 30 of 31 measurements agree. That cutoff is an illustrative screening choice, not a prediction of lifetime reliability. The program reports eligible count and reference-ones percentage. The file hash identifies the enrollment artifact; it does not automatically read back the programmed FPGA or attest the ESP firmware.

Repeating enrollment with the same ID and identical bitstream hash adds distinct challenges. A different hash requires a new ID. 1,024 initial challenges permit at most eight 128-bit authentication sessions, fewer after filtering or characterization. One hundred fresh sessions require at least 12,800 usable CRPs, plus records reserved for characterization.

Measure later repeatability under a separately recorded condition:

```
python server.py characterize --port YOUR_ESP_PORT --device FPGA_A --challenges 128 --repeats 31 --condition "genuine A; power cycle 1; temperature and voltage not measured"
```

Characterization compares later raw samples against enrollment. Its deliberately reused challenges are permanently excluded from the fresh authentication pool. Repeat the command for further conditions.

Authenticate:

```
python server.py auth --port YOUR_ESP_PORT --device FPGA_A --bits 128 --repeats 7 --max-errors 6 --condition "genuine A; ambient"
```

The server randomly selects unused eligible CRPs, commits their consumption before transmission, obtains seven raw observations per challenge, majority-votes each bit, and compares the 128 resulting bits with the reference. At most six mismatches gives ACCEPT in this illustrative configuration. Timeouts or malformed/incomplete replies give ERROR. Challenges remain consumed after failure; there is no fallback to stored or generated responses.

Select the mismatch threshold from separate same-device and different-device measurements, then evaluate on held-out trials. Six mismatches out of 128 is only a starting example.

The optional LED receives VERDICT 1 or 0 after the decision. It clears on another command or MCU reset. The LED is a display and does not enforce access control; the authoritative decision is the server record.

## Records and demonstration

The database is `records/auth.sqlite` under your current folder. Tables:

| Table | Contents |
|---|---|
| devices | Claimed ID, enrollment bitstream SHA-256, timestamp |
| crps | Challenge, majority reference, ones/trials, consistency, eligible and consumed flags |
| samples | Every complete raw measurement, challenge, trial index, session, receipt timestamp |
| sessions | Mode, claimed ID, condition label, state, mismatch count, threshold, elapsed time, error |

Sample timestamps are server receipt/storage timestamps, not FPGA capture-time measurements. Conditions are annotations: this build does not automatically measure temperature or supply voltage. Interrupted sessions remain visible; failures are not recorded as successful authentication.

Export:

```
python server.py export --directory records/csv
```

This creates devices.csv, crps.csv, samples.csv, and sessions.csv. Import hexadecimal challenges as text in spreadsheet software to preserve leading zeros. Timestamps are UTC with an offset. Add known physical board identity to the condition annotation when testing impostors.

Measure reference-ones percentage (ideal near 50%), raw later match percentage, match after voting, same-chip Hamming distance, same-challenge pairwise different-chip Hamming distance (ideal near 50%), observed false rejection and false acceptance with trial counts, latency, and post-implementation resource use. Report raw and voted results separately. End-to-end latency includes USB, UART, all repetitions, database writes, and host scheduling; it is not propagation delay through the PUF.

For the different-chip experiment, disconnect power and replace A with a second **identical Tang Nano 1K**, programmed with the **same bitstream**, on the same ESP connection. Ask the server to authenticate FPGA_A, and annotate the session:

```
python server.py auth --port YOUR_ESP_PORT --device FPGA_A --bits 128 --repeats 7 --max-errors 6 --condition "impostor B claiming A; ambient"
```

Do not enroll B under A's identity. Preserve unexpected acceptances as experimental results. One physical board cannot establish inter-chip uniqueness; borrow a second identical board. Multiple differently routed cores on one chip are not substitutes for independent physical chips.

This authenticates the attached FPGA under a laboratory protocol. It does not independently prove ESP silicon identity, verify MCU firmware, or stop a relay to the genuine FPGA. Plain arbiter PUFs can be modelled from exposed CRPs. Consuming challenges addresses response reuse, not all modelling or relay attacks. Treat this as a first-phase experimental demonstration.

## Troubleshooting and verification limits

| Symptom | Check |
|---|---|
| ESP port missing | Data cable; USB CDC setting; first-flash BOOT/RESET sequence |
| Port busy | Close Serial Monitor and other serial programs |
| ERR LINK | Both boards powered, bitstream loaded, GND connected, GPIO0→27 and 28→GPIO1, 115200 8N1, reset not held |
| PUF_DISABLED | Communication-only FPGA build; physical PUF build still needs implementation |
| Constant / unstable outputs | Netlist preservation, stage and terminal routing, launch/reset sequencing, operating conditions |
| Genuine rejection | Exact bitstream and chip, independent repeatability, calibrated threshold |
| CRP pool exhausted | Add trusted enrollment for the same chip and bitstream; never recycle exposed authentication CRPs |
| FPGA stops after power cycle | SRAM configuration was volatile; reload the same bitstream or configure nonvolatile boot |

The Python server was exercised using synthetic transport for enrollment, genuine/impostor comparison, failure recording, challenge consumption, echo validation, link-only rejection, characterization, bitstream mismatch handling, and CSV export. FPGA RTL passed Icarus Verilog 12.0 functional compilation/simulation in both modes, including serial-wire requests/replies, CRC, challenge loading, repeated evaluation control, timeout recovery, and reset. That simulation uses ideal primitive models and provides no silicon-identity or physical-delay evidence. These are software and logic tests, not hardware results. FPGA RTL has not been synthesized with Gowin, timing-verified, or tested on a board here. MCU code passed desktop helper tests but still needs an actual Espressif board-package compile and hardware upload; installed x86_64 compiler tools cannot run in this arm64 environment. No qualified placement/routing constraints or bitstream are supplied. See `VALIDATION.md` and the reproducible checks in the package README.

## Primary references

- [Sipeed board documentation](https://en.wiki.sipeed.com/hardware/en/tang/Tang-Nano-1K/Nano-1k.html)
- [Manufacturer pin map](https://en.wiki.sipeed.com/hardware/en/tang/Tang-Nano-1K/assets/1k-pin.png)
- [Sipeed LCD pin assignment example](https://github.com/sipeed/sipeed_wiki/blob/main/docs/hardware/en/tang/Tang-Nano-1K/examples/lcd.md)
- [Sipeed Gowin installation guide](https://github.com/sipeed/sipeed_wiki/blob/main/docs/hardware/en/tang/common-doc/get_started/install-the-ide.md)
- [Gowin primitive reference: LUT4 and DFFC](https://www.gowinsemi.com/upload/database_doc/39/document/5bfcff2ce0b72.pdf)
- [ESP32-C3 datasheet](https://documentation.espressif.com/esp32-c3_datasheet_en.html)
- [Espressif Arduino UART API](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/serial.html)
- [Espressif native USB programming instructions](https://docs.espressif.com/projects/arduino-esp32/en/latest/tutorials/cdc_dfu_flash.html)
- [SuperMini board documentation in Apache NuttX](https://github.com/apache/nuttx/blob/master/Documentation/platforms/risc-v/esp32c3/boards/esp32c3-supermini/index.rst)
- [FPGA PUF implementation bias and metastability research](https://arxiv.org/html/1703.10725)
- [PUF modelling attacks research](https://eprint.iacr.org/2010/251)
