"""Independent fixed-i386 Native6 durable journal decoder; no ctypes/game IO.

An intact journal is audit evidence, never a certificate that ownership was
returned. The helper incarnation and fresh own-baseline/lease reads remain
separate obligations for the future product recovery integration.
"""
from pathlib import PureWindowsPath
import re
import struct

MAGIC = 0x53434736
VERSION = 6
BINDING_SIZE = 4332
SHARED_SIZE = 4592
JOURNAL_SIZE = 4512
JOURNAL_BINDING = 28
JOURNAL_AUDIT = 4360
JOURNAL_FLAGS = 4448
JOURNAL_END = 4504
WORDS = ('pid', 'thread', 'start_low', 'start_high', 'owner', 'ai', 'personality', 'personality_data', 'player_template', 'game', 'engine')
ARRAYS = (('session', 16), ('lease', 16), ('package', 32), ('sources', 32), ('runtime_manifest', 32))
PATHS = ('deployment', 'game_image', 'runtime_root', 'journal_root')


def wire_binding(binding):
    if type(binding) is not dict or set(binding) != set(WORDS) | {name for name, _ in ARRAYS} | set(PATHS):
        raise ValueError('native6_complete_binding_required')
    if any(type(binding[name]) is not int or not 0 <= binding[name] <= 0xffffffff for name in WORDS):
        raise ValueError('native6_binding_word_invalid')
    raw = struct.pack('<11I', *(binding[name] for name in WORDS))
    for name, size in ARRAYS:
        values = binding[name]
        if (type(values) not in (list, bytes) or len(values) != size or
                any(type(v) is not int or not 0 <= v <= 255 for v in values) or not any(values)):
            raise ValueError('native6_binding_digest_or_epoch_invalid')
        raw += bytes(values)
    for name in PATHS:
        path = binding[name]
        if (type(path) is not str or '\x00' in path or re.match(r'^[A-Za-z]:\\', path) is None
                or str(PureWindowsPath(path)) != path or '..' in PureWindowsPath(path).parts
                or any(part.endswith((' ', '.')) for part in PureWindowsPath(path).parts)):
            raise ValueError('native6_binding_path_invalid')
        encoded = path.encode('utf-16-le') + b'\0\0'
        if len(encoded) > 1040:
            raise ValueError('native6_binding_path_unbounded')
        raw += encoded.ljust(1040, b'\0')
    if len(raw) != BINDING_SIZE:
        raise ValueError('native6_binding_size_mismatch')
    return raw


def decode(raw, expected_binding):
    if not isinstance(raw, bytes) or len(raw) % JOURNAL_SIZE or len(raw) > 4096 * JOURNAL_SIZE:
        raise ValueError('native6_journal_truncated_or_unbounded')
    expected = wire_binding(expected_binding)
    records = []
    for index in range(len(raw) // JOURNAL_SIZE):
        row = raw[index * JOURNAL_SIZE:(index + 1) * JOURNAL_SIZE]
        magic, version, sequence, size, kind, callback, intent = struct.unpack_from('<7I', row)
        if ((magic, version, sequence, size) != (MAGIC, VERSION, index + 1, JOURNAL_SIZE)
                or kind not in (1, 2) or row[JOURNAL_BINDING:JOURNAL_BINDING + BINDING_SIZE] != expected
                or struct.unpack_from('<I', row, JOURNAL_END)[0] != 0x454e4436):
            raise ValueError('native6_journal_identity_or_sequence')
        records.append(dict(sequence=sequence, kind=kind, callback_serial=callback, intent_not_after_frame=intent))
    return records


def verified(raw, native):
    try:
        if (type(native.get('magic')) is not int or native['magic'] != MAGIC
                or type(native.get('version')) is not int or native['version'] != VERSION
                or type(native.get('size')) is not int or native['size'] != SHARED_SIZE
                or type(native.get('journal_records')) is not int or not 0 <= native['journal_records'] <= 4096):
            return False
        return len(decode(raw, native['binding'])) == native['journal_records']
    except (KeyError, TypeError, ValueError, OverflowError, struct.error, UnicodeError):
        return False
