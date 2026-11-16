"""Independent Native7 focus-journal negative fixtures. No Game or native IO."""
import copy
import struct
import unittest

from host_runtime import native7_journal as codec
from host_runtime.native6_journal import ARRAYS, WORDS, decode as decode_native6


def binding():
    value = {name: index + 1 for index, name in enumerate(WORDS)}
    value.update({name: [index + 1] * size for index, (name, size) in enumerate(ARRAYS)})
    value.update(deployment=r'C:\Users\tester\Documents\Red Alert 3\Mods\qualified.big',
                 game_image=r'D:\Installed Game\Data\RA3_1.12.game', runtime_root=r'D:\Tacticore\runtime',
                 journal_root=r'C:\Users\tester\AppData\Local\Tacticore\desktop-runtime\native7\journals')
    return value


def record(sequence, callback, phase, *, target=4, selector=0x10000, request=1, reservations=1):
    row = bytearray(codec.JOURNAL_SIZE)
    deadline = 900 if phase != 4 else 0
    struct.pack_into('<7I', row, 0, codec.MAGIC, 7, sequence, codec.JOURNAL_SIZE, 3, callback, deadline)
    row[codec.JOURNAL_BINDING:codec.JOURNAL_BINDING + codec.BINDING_SIZE] = codec.wire_binding(binding())
    priorities = (10, 1) if phase != 4 else (1, 1)
    fields = [phase, 1, selector, 2, target, request, int(phase != 4), 0, *priorities,
              3, 100 + callback, callback, deadline, reservations, 1000 + callback,
              30000 if phase != 4 else 0]
    struct.pack_into('<15I4x2Q', row, codec.JOURNAL_FOCUS, *fields)
    struct.pack_into('<I', row, codec.JOURNAL_END, 0x454e4437)
    return bytes(row)


class Native7Journal(unittest.TestCase):
    def test_decode_held_and_restored_with_full_binding(self):
        raw = record(1, 10, 1) + record(2, 11, 4, reservations=2)
        rows = codec.decode(raw, binding())
        self.assertEqual(rows[-1]['focus']['phase'], 4)
        self.assertEqual(rows[-1]['focus']['call_reservations'], 2)
        self.assertEqual(rows[0]['focus']['target_player'], 4)
        native = dict(magic=codec.MAGIC, version=7, size=codec.SHARED_SIZE,
                      journal_records=2, binding=binding())
        self.assertTrue(codec.verified(raw, native))
        native['journal_records'] = 1
        self.assertFalse(codec.verified(raw, native))
        with self.assertRaises(ValueError):
            decode_native6(raw, binding())

    def test_binding_and_record_identity_cannot_be_reused(self):
        raw = record(1, 10, 1)
        for key in ('pid', 'thread', 'start_low', 'owner', 'ai', 'game', 'engine'):
            changed = copy.deepcopy(binding())
            changed[key] += 1
            with self.subTest(key=key), self.assertRaises(ValueError):
                codec.decode(raw, changed)
        for offset in (0, 4, 8, 12, 16, codec.JOURNAL_END):
            changed = bytearray(raw)
            changed[offset] ^= 0xff
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                codec.decode(bytes(changed), binding())
        with self.assertRaises(ValueError):
            codec.decode(raw[:-1], binding())

    def test_foreign_target_selector_and_baseline_claims_fail(self):
        for kwargs in (dict(target=3), dict(target=6), dict(selector=0x10001),
                       dict(request=0), dict(reservations=4097)):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                codec.decode(record(1, 10, 1, **kwargs), binding())
        for field, value in ((6, 1), (8, 10), (13, 500)):
            changed = bytearray(record(1, 10, 4))
            struct.pack_into('<I', changed, codec.JOURNAL_FOCUS + 4 * field, value)
            with self.subTest(field=field), self.assertRaises(ValueError):
                codec.decode(bytes(changed), binding())

    def test_monotonic_owner_requests_callbacks_and_reservations(self):
        first = record(1, 10, 1, request=2, reservations=2)
        for second in (record(2, 9, 4, request=2, reservations=2),
                       record(2, 11, 4, selector=0x20000, request=2, reservations=2),
                       record(2, 11, 4, request=1, reservations=2),
                       record(2, 11, 4, request=2, reservations=1)):
            with self.assertRaises(ValueError):
                codec.decode(first + second, binding())


if __name__ == '__main__':
    unittest.main()
