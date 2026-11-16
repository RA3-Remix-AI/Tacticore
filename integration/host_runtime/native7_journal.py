"""Independent fixed-i386 Native7 decoder, including enemy-focus ownership.

Decode is read-only evidence. Admission and fresh independent restoration
checks remain mandatory. Native6 certificates keep their original decoder.
"""
import struct

from .native6_journal import BINDING_SIZE, JOURNAL_BINDING, wire_binding

MAGIC = 0x53434737
VERSION = 7
SHARED_SIZE = 4672
JOURNAL_SIZE = 4592
JOURNAL_FOCUS = 4504
JOURNAL_END = 4584
FOCUS_SIZE = 80
FOCUS_FIELDS = ('phase', 'baseline_captured', 'selector', 'baseline_scheme',
                'target_player', 'request', 'manual', 'isolated', 'priority_p4',
                'priority_p5', 'alive_mask', 'frame', 'callback', 'deadline_frame',
                'call_reservations', 'ms', 'deadline_ms')


def decode_focus(raw):
    if type(raw) is not bytes or len(raw) != FOCUS_SIZE:
        raise ValueError('native7_focus_wire_size')
    value = dict(zip(FOCUS_FIELDS, struct.unpack('<15I4x2Q', raw)))
    if value['baseline_captured'] != 1 or value['phase'] not in range(1, 7):
        raise ValueError('native7_focus_owned_phase')
    if (value['selector'] < 0x10000 or value['selector'] % 4 or value['baseline_scheme'] != 2
            or value['target_player'] not in (4, 5) or not 1 <= value['request'] <= 2048
            or value['manual'] not in (0, 1) or value['isolated'] not in (0, 1)
            or value['priority_p4'] > 10 or value['priority_p5'] > 10 or value['alive_mask'] > 3
            or not value['frame'] or not value['callback'] or value['call_reservations'] > 4096):
        raise ValueError('native7_focus_wire_values')
    priorities = (value['priority_p4'], value['priority_p5'])
    alive = tuple(int(bool(value['alive_mask'] & (1 << index))) for index in range(2))
    if value['phase'] == 1:
        target = value['target_player'] - 4
        if (value['manual'] != 1 or value['isolated'] != 0 or not alive[target]
                or priorities[target] != 10 or priorities[1 - target] != alive[1 - target]
                or not value['frame'] < value['deadline_frame'] <= value['frame'] + 900
                or not value['ms'] < value['deadline_ms'] <= value['ms'] + 60000):
            raise ValueError('native7_focus_held_contract')
    if value['phase'] == 4:
        if (value['manual'] or value['isolated'] or priorities != alive
                or value['deadline_frame'] or value['deadline_ms']):
            raise ValueError('native7_focus_baseline_contract')
    return value


def decode(raw, expected_binding):
    if type(raw) is not bytes or len(raw) % JOURNAL_SIZE or len(raw) > 4096 * JOURNAL_SIZE:
        raise ValueError('native7_journal_truncated_or_unbounded')
    binding = wire_binding(expected_binding)
    records = []
    focus_selector = None
    focus_request = 0
    focus_reservations = 0
    last_callback = 0
    for index in range(len(raw) // JOURNAL_SIZE):
        row = raw[index * JOURNAL_SIZE:(index + 1) * JOURNAL_SIZE]
        magic, version, sequence, size, kind, callback, intent = struct.unpack_from('<7I', row)
        if ((magic, version, sequence, size) != (MAGIC, VERSION, index + 1, JOURNAL_SIZE)
                or kind not in (1, 2, 3) or not max(1, last_callback) <= callback < 0xffffffff
                or row[JOURNAL_BINDING:JOURNAL_BINDING + BINDING_SIZE] != binding
                or struct.unpack_from('<I', row, JOURNAL_END)[0] != 0x454e4437):
            raise ValueError('native7_journal_identity_or_sequence')
        last_callback = callback
        record = dict(sequence=sequence, kind=kind, callback_serial=callback,
                      intent_not_after_frame=intent)
        if kind == 3:
            focus = decode_focus(row[JOURNAL_FOCUS:JOURNAL_FOCUS + FOCUS_SIZE])
            if (focus['callback'] != callback or focus['deadline_frame'] != intent
                    or focus['request'] < focus_request or focus['call_reservations'] < focus_reservations
                    or focus_selector is not None and focus['selector'] != focus_selector):
                raise ValueError('native7_focus_journal_regression')
            focus_selector = focus['selector']
            focus_request = focus['request']
            focus_reservations = focus['call_reservations']
            record['focus'] = focus
        elif any(row[JOURNAL_FOCUS:JOURNAL_FOCUS + FOCUS_SIZE]):
            raise ValueError('native7_untyped_focus_journal_payload')
        records.append(record)
    return records


def verified(raw, native):
    try:
        if (type(native) is not dict or any(type(native.get(key)) is not int for key in ('magic', 'version', 'size'))
                or native.get('magic') != MAGIC or native.get('version') != VERSION
                or native.get('size') != SHARED_SIZE or type(native.get('journal_records')) is not int
                or not 0 <= native['journal_records'] <= 4096):
            return False
        return len(decode(raw, native['binding'])) == native['journal_records']
    except (KeyError, TypeError, ValueError, OverflowError, struct.error, UnicodeError):
        return False
