"""Native journal decoding, including the 16-player enemy-focus record. No Game or native IO."""

import copy
import struct
import unittest

from host_runtime import native_journal as codec


def binding():
    value = {name: index + 1 for index, name in enumerate(codec.WORDS)}
    value.update({name: [index + 1] * size for index, (name, size) in enumerate(codec.ARRAYS)})
    value.update(
        deployment=r"C:\Users\tester\Documents\Red Alert 3\Mods\qualified.big",
        game_image=r"D:\Installed Game\Data\RA3_1.12.game",
        runtime_root=r"D:\Tacticore\runtime",
        journal_root=r"C:\Users\tester\AppData\Local\Tacticore\desktop-runtime\native7\journals",
    )
    return value


def record(
    sequence,
    callback,
    phase,
    *,
    target=4,
    selector=0x10000,
    request=1,
    reservations=1,
    enemies=(4, 5),
    alive=(3, 4, 5),
    own=3,
):
    """One focus journal row for own player ``own`` against ``enemies``."""
    row = bytearray(codec.JOURNAL_SIZE)
    deadline = 900 if phase != 4 else 0
    struct.pack_into("<7I", row, 0, codec.MAGIC, 7, sequence, codec.JOURNAL_SIZE, 3, callback, deadline)
    row[codec.JOURNAL_BINDING : codec.JOURNAL_BINDING + codec.BINDING_SIZE] = codec.wire_binding(binding())
    enemy_mask = sum(1 << player for player in enemies)
    alive_mask = sum(1 << player for player in alive)
    priority = [int(bool(enemy_mask & alive_mask & (1 << player))) for player in range(16)]
    if phase != 4 and target < 16:
        priority[target] = 10
    fields = [
        phase,
        1,
        selector,
        2,
        target,
        request,
        int(phase != 4),
        0,
        own,
        enemy_mask,
        alive_mask,
        *priority,
        100 + callback,
        callback,
        deadline,
        reservations,
        0,
        1000 + callback,
        30000 if phase != 4 else 0,
    ]
    struct.pack_into(codec.FOCUS_FORMAT, row, codec.JOURNAL_FOCUS, *fields)
    struct.pack_into("<I", row, codec.JOURNAL_END, 0x454E4437)
    return bytes(row)


class NativeJournal(unittest.TestCase):
    def test_layout_matches_the_compiled_structures(self):
        self.assertEqual(struct.calcsize(codec.FOCUS_FORMAT), codec.FOCUS_SIZE)
        self.assertEqual(codec.FOCUS_SIZE, 144)
        self.assertEqual(codec.JOURNAL_END, codec.JOURNAL_FOCUS + codec.FOCUS_SIZE)
        self.assertEqual(codec.JOURNAL_SIZE, codec.JOURNAL_END + 8)
        self.assertEqual(codec.SHARED_SIZE, 4592 + codec.FOCUS_SIZE)

    def test_decode_held_and_restored_with_full_binding(self):
        raw = record(1, 10, 1) + record(2, 11, 4, reservations=2)
        rows = codec.decode(raw, binding())
        self.assertEqual(rows[-1]["focus"]["phase"], 4)
        self.assertEqual(rows[-1]["focus"]["call_reservations"], 2)
        self.assertEqual(rows[0]["focus"]["target_player"], 4)
        self.assertEqual(rows[0]["focus"]["priority"][4], 10)
        native = dict(magic=codec.MAGIC, version=7, size=codec.SHARED_SIZE, journal_records=2, binding=binding())
        self.assertTrue(codec.verified(raw, native))
        self.assertFalse(codec.verified(raw, native | {"focus": {"phase": 0}}))
        self.assertTrue(codec.verified(raw, native | {"focus": {"phase": 4}}))
        native["journal_records"] = 1
        self.assertFalse(codec.verified(raw, native))

    def test_any_enemy_ids_allies_and_own_seat_decode(self):
        cases = (
            dict(target=12, enemies=(0, 7, 12), alive=(0, 3, 5, 7, 12)),
            dict(target=0, enemies=(0, 7, 12), alive=(0, 3, 5, 12)),
            dict(target=2, enemies=(1, 2), alive=(1, 2, 3, 6), own=6),
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                raw = record(1, 10, 1, **kwargs) + record(2, 11, 4, reservations=2, **kwargs)
                rows = codec.decode(raw, binding())
                self.assertEqual(rows[0]["focus"]["target_player"], kwargs["target"])
                self.assertEqual(rows[1]["focus"]["priority"], codec.baseline_priorities(rows[1]["focus"]))

    def test_binding_and_record_identity_cannot_be_reused(self):
        raw = record(1, 10, 1)
        for key in ("pid", "thread", "start_low", "owner", "ai", "game", "engine"):
            changed = copy.deepcopy(binding())
            changed[key] += 1
            with self.subTest(key=key), self.assertRaises(ValueError):
                codec.decode(raw, changed)
        for offset in (0, 4, 8, 12, 16, codec.JOURNAL_END):
            changed = bytearray(raw)
            changed[offset] ^= 0xFF
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                codec.decode(bytes(changed), binding())
        with self.assertRaises(ValueError):
            codec.decode(raw[:-1], binding())

    def test_foreign_target_selector_and_baseline_claims_fail(self):
        for kwargs in (
            dict(target=3),
            dict(target=6),
            dict(target=16),
            dict(selector=0x10001),
            dict(request=0),
            dict(reservations=4097),
            dict(target=5, alive=(3, 4)),
            dict(enemies=(3, 4)),
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                codec.decode(record(1, 10, 1, **kwargs), binding())
        # manual flag, a raised priority and a deadline on a restored baseline
        for field, value in ((6, 1), (11 + 4, 10), (27 + 2, 500)):
            changed = bytearray(record(1, 10, 4))
            struct.pack_into("<I", changed, codec.JOURNAL_FOCUS + 4 * field, value)
            with self.subTest(field=field), self.assertRaises(ValueError):
                codec.decode(bytes(changed), binding())

    def test_monotonic_owner_requests_callbacks_and_reservations(self):
        first = record(1, 10, 1, request=2, reservations=2)
        for second in (
            record(2, 9, 4, request=2, reservations=2),
            record(2, 11, 4, selector=0x20000, request=2, reservations=2),
            record(2, 11, 4, request=1, reservations=2),
            record(2, 11, 4, request=2, reservations=1),
        ):
            with self.assertRaises(ValueError):
                codec.decode(first + second, binding())


if __name__ == "__main__":
    unittest.main()
