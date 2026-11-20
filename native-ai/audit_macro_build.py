"""Freeze exact-PE macro construction/production consumer evidence, no process opens."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import xml.etree.ElementTree as E

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "native-ai")]
from macro_build_observation import PINS, verify_pins

CALLS = {
    0x8C5462: 0x8B6DD0,
    0x8C554E: 0x8C53C0,
    0x8D7C58: 0x8C5490,
    0x8D7DC4: 0x8D5BB0,
    0x8D5CE1: 0x8D2BE0,
    0x8D2C1E: 0x880E90,
    0x8D2D0D: 0x880E90,
    0x8CB7F3: 0x53CB30,
}
RANGES = {
    "compiled_build_entries": (0x894EB0, 0x894FB8),
    "normal_entry_evaluation": (0x8B6DD0, 0x8B6E93),
    "entry_and_state_weighting": (0x8C53C0, 0x8C56F7),
    "native_select_and_submit": (0x8D7B5F, 0x8D7DC9),
    "native_funds_and_submit": (0x8D5BB0, 0x8D5D88),
    "construction_and_production_messages": (0x8D2BE0, 0x8D2E20),
    "own_job_registration": (0x8CB770, 0x8CB850),
    "job_map_layout": (0x53CB30, 0x53CBAD),
    "producer_category_getter": (0x6DA6B0, 0x6DA6B7),
}

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT / "reports"):
        raise ValueError("fresh_macro_builder_audit_required")
    game = Path("E:/RedRar3/Data/RA3_1.12.game")
    raw = game.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != "ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165":
        raise ValueError("exact_game_required")
    pe = struct.unpack_from("<I", raw, 0x3C)[0]
    base = struct.unpack_from("<I", raw, pe + 24 + 28)[0]
    section = pe + 24 + struct.unpack_from("<H", raw, pe + 20)[0]
    count = struct.unpack_from("<H", raw, pe + 6)[0]

    def read(at, size):
        for i in range(count):
            vs, va, n, offset = struct.unpack_from("<IIII", raw, section + i * 40 + 8)
            if va <= at - base and at - base + size <= va + min(vs, n):
                return raw[offset + at - base - va : offset + at - base - va + size]
        raise ValueError("unbacked_macro_builder_range")

    verify_pins(read)
    for address, target in CALLS.items():
        value = read(address, 5)
        if value[0] != 0xE8 or address + 5 + struct.unpack_from("<i", value, 1)[0] != target:
            raise ValueError("macro_builder_call_changed")
    out.mkdir(parents=True)
    sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    compiler = ROOT / "toolchain/w64devkit/bin/objdump.exe"
    disassembly = []
    for name, (start, end) in RANGES.items():
        text = subprocess.check_output(
            [str(compiler), "-d", "--start-address=" + hex(start), "--stop-address=" + hex(end), str(game)]
        )
        path = out / (name + ".txt")
        path.write_bytes(text)
        disassembly.append(dict(path=str(path), sha256=sha(path)))
    schemas = []
    for name in ["AssetTypeAIBuilderDefinition.xsd", "AssetTypeAIStateDefinition.xsd", "AIBank.xsd"]:
        path = Path("E:/RA3Modding/SDK/Schemas/xsd/SkirmishAI") / name
        tree = E.parse(path)
        schemas.append(dict(path=str(path), sha256=sha(path), xml_parsed=True))
    source = out / "source"
    source.mkdir()
    source_rows = []
    for i, path in enumerate([Path(__file__), ROOT / "native-ai/macro_build_observation.py"]):
        target = source / (str(i) + "-" + path.name)
        target.write_bytes(path.read_bytes())
        source_rows.append(dict(path=str(path), copy=target.name, sha256=sha(target)))
    result = dict(
        kind="native_macro_builder_static_audit",
        executable_sha256=digest,
        byte_checks=[dict(address=hex(address), bytes=value) for address, value in PINS.items()],
        direct_calls=[dict(address=hex(address), target=hex(target)) for address, target in CALLS.items()],
        disassembly=disassembly,
        schemas=schemas,
        sources=source_rows,
        native_processes_opened=0,
        native_calls=0,
        process_writes=0,
        capability_granted=False,
        limitations=[
            "Static consumer chain is not a live native submission receipt.",
            "Builder vector holds production interfaces and producer Thing IDs, not created objects.",
            "Factory category is kept raw until its full enum is qualified.",
            "Queue fields retain provisional semantics until correlated with native acceptance/payment/completion.",
            "Desired production counts and macro region deployment remain unqualified.",
        ],
    )
    with (out / "audit.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(
        json.dumps(
            dict(
                output=str(out),
                byte_checks=len(PINS),
                calls=len(CALLS),
                disassembly=len(disassembly),
                capability_granted=False,
            )
        )
    )
