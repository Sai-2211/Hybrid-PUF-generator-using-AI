"""Run functional Verilog tests; no chip timing or identity is emulated."""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="puf-hdl-") as temporary:
    output = str(Path(temporary) / "protocol.vvp")
    subprocess.run([
        os.environ.get("IVERILOG", "iverilog"), "-g2012", "-s", "tb_protocol",
        "-o", output, "fpga/uart.v", "fpga/puf64.v", "fpga/top.v",
        "tests/gowin_functional_models.v", "tests/tb_protocol.v",
    ], cwd=root, check=True)
    subprocess.run([os.environ.get("VVP", "vvp"), output], cwd=root, check=True)
