"""Project-local workaround for the confirmed HLS 2018.3 core_revision overflow.

Only the generated packaging script is copied and its revision replaced. No system
clock, tool installation, model, generated RTL or ROM contents are changed.
"""

import argparse
import re
import zipfile

from common.project import ROOT, sha256, write_json
from scripts.run_logged import run_logged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=["baseline", "serialized"], default="baseline")
    args = parser.parse_args()
    folder = ROOT / f"build/hls_{args.variant}/solution1/impl/ip"
    original = folder / "run_ippack.tcl"
    text = original.read_text(encoding="utf-8")
    pattern = r'(?m)^set Revision\s+"(\d+)"$'
    match = re.search(pattern, text)
    if match is None:
        raise ValueError("Generated packer has changed; inspect before adapting it")
    updated, count = re.subn(pattern, 'set Revision "1"', text)
    if count != 1:
        raise ValueError("Expected exactly one core revision assignment")
    compatible = folder / "run_ippack_compatible.tcl"
    compatible.write_text(updated, encoding="utf-8")
    code = run_logged(
        f"g5-ip-repack-{args.variant}",
        [
            "D:/HLS/software/Xilinx/Vivado/2018.3/bin/vivado.bat",
            "-mode",
            "batch",
            "-source",
            str(compatible),
        ],
        cwd=folder,
    )
    if code:
        return code
    archive = folder / "xilinx_com_hls_nn_infer_1_0.zip"
    with zipfile.ZipFile(archive) as stream:
        if not any(name.endswith("component.xml") for name in stream.namelist()):
            raise ValueError("IP archive lacks metadata")
    write_json(
        f"evidence/environment/ip_repack_{args.variant}.json",
        {
            "reason": "HLS Y2K22 core_revision signed-integer overflow",
            "reference": "https://docs.amd.com/r/en-US/76960",
            "original_revision": match.group(1),
            "replacement_revision": 1,
            "scope": "project-local generated packaging metadata only",
            "original_script_sha256": sha256(original),
            "patched_script_sha256": sha256(compatible),
            "archive": str(archive.relative_to(ROOT)),
            "archive_sha256": sha256(archive),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
