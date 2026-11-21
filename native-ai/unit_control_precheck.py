"""Round 2 R0: offline check that the unit-control addresses fit this machine's game file. Reads files only.

Usage (Windows):
    python -X utf8 native-ai/unit_control_precheck.py --game <RA3_1.12.game> --copilot <Ra3-Copilot clone>

Prints one JSON report and exits 0 on PASS, 1 on BLOCKED, 2 on bad arguments.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "integration"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from host_runtime.native_runtime_contract import GAME_SHA  # noqa: E402
import unit_control_addresses as addresses  # noqa: E402

ENTRY_SHAPE_LEN = 24
PADDING_BYTES = (0xCC, 0x90)


def parse_pe(data):
    """Return (image_base, size_of_image, sections) of a 32-bit PE image."""
    if data[:2] != b"MZ":
        raise ValueError("not_mz")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe : pe + 4] != b"PE\0\0":
        raise ValueError("not_pe")
    count = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    optional = pe + 24
    image_base = struct.unpack_from("<I", data, optional + 28)[0]
    size_of_image = struct.unpack_from("<I", data, optional + 56)[0]
    sections = []
    for index in range(count):
        at = optional + optional_size + index * 40
        vsize, vaddr, raw_size, raw_ptr = struct.unpack_from("<IIII", data, at + 8)
        sections.append((vaddr, max(vsize, raw_size), raw_ptr, raw_size))
    return image_base, size_of_image, sections


def read_va(data, image_base, sections, va, length):
    """Bytes of the file image at a virtual address, or None when the address has no file content."""
    rva = va - image_base
    for vaddr, span, raw_ptr, raw_size in sections:
        if vaddr <= rva < vaddr + span:
            offset = rva - vaddr
            if offset + length > raw_size:
                return None
            return data[raw_ptr + offset : raw_ptr + offset + length]
    return None


def build_name(size_of_image):
    if size_of_image == addresses.RETAIL_SIZE_OF_IMAGE:
        return "retail"
    if size_of_image == addresses.STEAM_SIZE_OF_IMAGE:
        return "steam"
    return "unknown"


def check_function(data, image_base, sections, entry):
    """Pinned bytes must match; unpinned ones must at least look like a function start."""
    got = read_va(data, image_base, sections, entry["va"], ENTRY_SHAPE_LEN)
    result = dict(va=hex(entry["va"]), bytes=got.hex() if got else None)
    if got is None:
        return dict(result, ok=False, reason="address_outside_file")
    if entry["entry_bytes"] is not None:
        matches = got[: len(entry["entry_bytes"])] == entry["entry_bytes"]
        return dict(result, ok=matches, reason="pinned_bytes_match" if matches else "pinned_bytes_mismatch")
    starts_function = _follows_function_end(data, image_base, sections, entry["va"])
    reason = "function_start_shape_pin_these_bytes" if starts_function else "not_a_function_start"
    return dict(result, ok=starts_function, reason=reason)


def _follows_function_end(data, image_base, sections, va):
    """Compilers start functions after padding, `ret` or `ret n`."""
    tail = read_va(data, image_base, sections, va - 3, 3)
    return tail is not None and (tail[2] in PADDING_BYTES or tail[2] == 0xC3 or tail[0] == 0xC2)


def check_thing_vtable(data, image_base, sections):
    """The vtable shape Ra3-Copilot relies on: [1]==[2], [3]==[4], [8]==-4, [9]==0x490, code pointers in module."""
    raw = read_va(data, image_base, sections, addresses.THING_VTABLE["va"], 40)
    if raw is None:
        return dict(va=hex(addresses.THING_VTABLE["va"]), ok=False, reason="address_outside_file")
    words = struct.unpack("<10I", raw)
    in_module = all(image_base <= words[i] < image_base + 0x1000000 for i in (0, 1, 3, 5))
    shape = words[1] == words[2] and words[3] == words[4] and words[8] == 0xFFFFFFFC and words[9] == 0x490
    return dict(
        va=hex(addresses.THING_VTABLE["va"]),
        words=[hex(w) for w in words],
        ok=in_module and shape,
        reason="vtable_shape_match" if in_module and shape else "vtable_shape_mismatch",
    )


def run_copilot_precheck(copilot, game):
    """Ra3-Copilot's own hook check (its overlay hooks); informational: it shows whether its tool will load."""
    script = Path(copilot) / "ra3-copilot" / "tools" / "precheck_aob.py"
    if not script.is_file():
        return dict(ran=False, reason="precheck_aob_missing")
    done = subprocess.run(
        [sys.executable, "-X", "utf8", str(script), "--game", str(game)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    found = re.search(r"结果: (\d+)/(\d+)", done.stdout)
    passed, total = (int(found.group(1)), int(found.group(2))) if found else (None, None)
    return dict(ran=True, exit_code=done.returncode, passed=passed, total=total, tail=done.stdout[-1500:])


def precheck(game, copilot=None):
    data = Path(game).read_bytes()
    image_base, size_of_image, sections = parse_pe(data)
    game_sha = hashlib.sha256(data).hexdigest()
    checks = dict(
        game_sha_is_bound=game_sha == GAME_SHA,
        build=build_name(size_of_image),
        functions={name: check_function(data, image_base, sections, e) for name, e in addresses.FUNCTIONS.items()},
        thing_vtable=check_thing_vtable(data, image_base, sections),
    )
    blockers = []
    if not checks["game_sha_is_bound"]:
        blockers.append("game_sha_not_bound")
    if checks["build"] != "retail" or image_base != addresses.IMAGE_BASE:
        blockers.append("not_retail_layout")
    blockers += [name + ":" + c["reason"] for name, c in checks["functions"].items() if not c["ok"]]
    if not checks["thing_vtable"]["ok"]:
        blockers.append("thing_vtable:" + checks["thing_vtable"]["reason"])
    return dict(
        verdict="PASS" if not blockers else "BLOCKED",
        blockers=blockers,
        game=str(game),
        game_sha256=game_sha,
        same_file_as_ra3_copilot=game_sha == addresses.RA3_COPILOT_GAME_SHA,
        size=len(data),
        size_of_image=hex(size_of_image),
        checks=checks,
        ra3_copilot_precheck=run_copilot_precheck(copilot, game) if copilot else None,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--game", required=True, type=Path)
    parser.add_argument("--copilot", type=Path, help="Ra3-Copilot clone at the pinned commit (optional)")
    args = parser.parse_args(argv)
    if not args.game.is_file():
        print("error: game file not found: " + str(args.game), file=sys.stderr)
        return 2
    report = precheck(args.game, args.copilot)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
