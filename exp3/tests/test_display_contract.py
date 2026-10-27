"""Check displayed geometry against schematic nets, independently of RTL bit order."""

import re

import pytest

from common.project import ROOT

# DaVinci V2.1 schematic: FPGA bank pins -> LEDSEG_A..DOT (not inferred from RTL).
PIN_SEGMENT = {
    "H15": "a",
    "G16": "b",
    "L13": "c",
    "G15": "d",
    "K13": "e",
    "G13": "f",
    "H14": "g",
    "J14": "dp",
}
DIGIT_SHAPE = [
    "abcdef",
    "bc",
    "abdeg",
    "abcdg",
    "bcfg",
    "acdfg",
    "acdefg",
    "abc",
    "abcdefg",
    "abcdfg",
]


@pytest.mark.parametrize("digit,shape", enumerate(DIGIT_SHAPE))
def test_digit_lights_correct_physical_segments(digit: int, shape: str) -> None:
    rtl = (ROOT / "rtl/seven_segment.v").read_text(encoding="utf-8")
    xdc = (ROOT / "constraints/exp3.xdc").read_text(encoding="utf-8")
    codes = {
        int(d): int(code, 16) for d, code in re.findall(r"(\d+):\s*segments=8'h([0-9a-fA-F]+)", rtl)
    }
    mapping = re.findall(
        r"PACKAGE_PIN\s+(\w+)\s+IOSTANDARD LVCMOS33\} \[get_ports \{seg_led\[(\d)\]\}\]", xdc
    )
    assert len(mapping) == 8
    lit = {PIN_SEGMENT[pin] for pin, bit in mapping if not (codes[digit] >> int(bit)) & 1}
    assert lit == set(shape), f"digit={digit}, physical lit={lit}, expected={set(shape)}"
