import hashlib
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import unit_control_addresses as addresses
import unit_control_precheck as precheck

TEXT_RVA = 0x1000
DATA_RVA = 0x84D000
RAW_TEXT = 0x400
RAW_DATA = 0x400 + 0x700000


def fake_game(*, size_of_image=addresses.RETAIL_SIZE_OF_IMAGE, move_bytes=None, attack_prefix=b"\xcc"):
    """A minimal PE whose sections cover the table's addresses."""
    text_size = 0x700000
    data_size = 0x1000
    image = bytearray(RAW_DATA + data_size)
    image[0:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x80)
    image[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HH", image, 0x84, 0x14C, 2)
    struct.pack_into("<H", image, 0x84 + 16, 0xE0)
    optional = 0x98
    struct.pack_into("<H", image, optional, 0x10B)
    struct.pack_into("<I", image, optional + 28, addresses.IMAGE_BASE)
    struct.pack_into("<I", image, optional + 56, size_of_image)
    sections = optional + 0xE0
    struct.pack_into("<8sIIII", image, sections, b".text", text_size, TEXT_RVA, text_size, RAW_TEXT)
    struct.pack_into("<8sIIII", image, sections + 40, b".rdata", data_size, DATA_RVA, data_size, RAW_DATA)

    def put(va, raw):
        offset = va - addresses.IMAGE_BASE - TEXT_RVA + RAW_TEXT
        image[offset : offset + len(raw)] = raw

    move = addresses.FUNCTIONS["move_to_position"]
    put(move["va"] - 1, b"\xcc" + (move_bytes or move["entry_bytes"]))
    put(addresses.FUNCTIONS["attack_object"]["va"] - 1, attack_prefix + bytes(range(1, 25)))
    code = addresses.IMAGE_BASE + 0x100000
    words = [code, code + 4, code + 4, code + 8, code + 8, code + 12, 0, 0, 0xFFFFFFFC, 0x490]
    vt_offset = addresses.THING_VTABLE["va"] - addresses.IMAGE_BASE - DATA_RVA + RAW_DATA
    struct.pack_into("<10I", image, vt_offset, *words)
    return bytes(image)


class PrecheckTest(unittest.TestCase):
    def run_precheck(self, data):
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder) / "RA3_1.12.game"
            game.write_bytes(data)
            with mock.patch.object(precheck, "GAME_SHA", hashlib.sha256(data).hexdigest()):
                return precheck.precheck(game)

    def test_passes_on_matching_layout(self):
        report = self.run_precheck(fake_game())
        self.assertEqual(report["verdict"], "PASS", report["blockers"])
        self.assertEqual(
            report["checks"]["functions"]["attack_object"]["reason"], "function_start_shape_pin_these_bytes"
        )

    def test_blocks_on_moved_function(self):
        report = self.run_precheck(fake_game(move_bytes=b"\x90" * 24))
        self.assertIn("move_to_position:pinned_bytes_mismatch", report["blockers"])

    def test_blocks_when_attack_is_mid_function(self):
        report = self.run_precheck(fake_game(attack_prefix=b"\x8b"))
        self.assertIn("attack_object:not_a_function_start", report["blockers"])

    def test_blocks_on_steam_layout(self):
        report = self.run_precheck(fake_game(size_of_image=addresses.STEAM_SIZE_OF_IMAGE))
        self.assertIn("not_retail_layout", report["blockers"])

    def test_blocks_on_unbound_game(self):
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder) / "RA3_1.12.game"
            game.write_bytes(fake_game())
            report = precheck.precheck(game)
        self.assertIn("game_sha_not_bound", report["blockers"])


if __name__ == "__main__":
    unittest.main()
