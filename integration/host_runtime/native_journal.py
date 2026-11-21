"""Decoder for the native companion's durable journal (fixed i386 layout).

The journal is audit evidence written by the DLL before every native call.
Decoding never touches the game. Field offsets mirror shared.h.
"""

from pathlib import PureWindowsPath
import re
import struct

MAGIC = 0x53434737
VERSION = 7
MAX_PLAYERS = 16
BINDING_SIZE = 4332
SHARED_SIZE = 4736
JOURNAL_SIZE = 4656
JOURNAL_BINDING = 28
JOURNAL_FOCUS = 4504
JOURNAL_END = 4648
FOCUS_SIZE = 144
FOCUS_FORMAT = "<11I16I5I2Q"
FOCUS_FIELDS = (
    "phase",
    "baseline_captured",
    "selector",
    "baseline_scheme",
    "target_player",
    "request",
    "manual",
    "isolated",
    "own_player",
    "enemy_mask",
    "alive_mask",
    "priority",
    "frame",
    "callback",
    "deadline_frame",
    "call_reservations",
    "reserved",
    "ms",
    "deadline_ms",
)
WORDS = (
    "pid",
    "thread",
    "start_low",
    "start_high",
    "owner",
    "ai",
    "personality",
    "personality_data",
    "player_template",
    "game",
    "engine",
)
ARRAYS = (("session", 16), ("lease", 16), ("package", 32), ("sources", 32), ("runtime_manifest", 32))
PATHS = ("deployment", "game_image", "runtime_root", "journal_root")


def wire_binding(binding):
    """The exact BindingWire bytes for a projected binding dictionary."""
    if type(binding) is not dict or set(binding) != set(WORDS) | {name for name, _ in ARRAYS} | set(PATHS):
        raise ValueError("native_complete_binding_required")
    if any(type(binding[name]) is not int or not 0 <= binding[name] <= 0xFFFFFFFF for name in WORDS):
        raise ValueError("native_binding_word_invalid")
    raw = struct.pack("<11I", *(binding[name] for name in WORDS))
    for name, size in ARRAYS:
        values = binding[name]
        if (
            type(values) not in (list, bytes)
            or len(values) != size
            or any(type(v) is not int or not 0 <= v <= 255 for v in values)
            or not any(values)
        ):
            raise ValueError("native_binding_digest_or_epoch_invalid")
        raw += bytes(values)
    for name in PATHS:
        path = binding[name]
        if (
            type(path) is not str
            or "\x00" in path
            or re.match(r"^[A-Za-z]:\\", path) is None
            or str(PureWindowsPath(path)) != path
            or ".." in PureWindowsPath(path).parts
            or any(part.endswith((" ", ".")) for part in PureWindowsPath(path).parts)
        ):
            raise ValueError("native_binding_path_invalid")
        encoded = path.encode("utf-16-le") + b"\0\0"
        if len(encoded) > 1040:
            raise ValueError("native_binding_path_unbounded")
        raw += encoded.ljust(1040, b"\0")
    if len(raw) != BINDING_SIZE:
        raise ValueError("native_binding_size_mismatch")
    return raw


def focusable(value):
    """Bit mask of hostile, alive players (the native selector's entries)."""
    return value["enemy_mask"] & value["alive_mask"]


def baseline_priorities(value):
    """Automatic selection: priority 1 for each focusable player, else 0."""
    mask = focusable(value)
    return [int(bool(mask & (1 << player))) for player in range(MAX_PLAYERS)]


def held_priorities(value, target):
    """A held preference: priority 10 for the target, others automatic."""
    result = baseline_priorities(value)
    result[target] = 10
    return result


def decode_focus(raw):
    if type(raw) is not bytes or len(raw) != FOCUS_SIZE:
        raise ValueError("native_focus_wire_size")
    words = struct.unpack(FOCUS_FORMAT, raw)
    value = dict(zip(FOCUS_FIELDS[:11], words[:11]))
    value["priority"] = list(words[11:27])
    value.update(zip(FOCUS_FIELDS[12:], words[27:]))
    if value["baseline_captured"] != 1 or value["phase"] not in range(1, 7):
        raise ValueError("native_focus_owned_phase")
    if (
        value["selector"] < 0x10000
        or value["selector"] % 4
        or value["baseline_scheme"] != 2
        or value["target_player"] >= MAX_PLAYERS
        or not 1 <= value["request"] <= 2048
        or value["manual"] not in (0, 1)
        or value["isolated"] not in (0, 1)
        or value["own_player"] >= MAX_PLAYERS
        or value["enemy_mask"] >> MAX_PLAYERS
        or value["alive_mask"] >> MAX_PLAYERS
        or value["enemy_mask"] & (1 << value["own_player"])
        or any(priority > 10 for priority in value["priority"])
        or value["reserved"]
        or not value["frame"]
        or not value["callback"]
        or value["call_reservations"] > 4096
    ):
        raise ValueError("native_focus_wire_values")
    target = value["target_player"]
    if value["phase"] == 1:
        if (
            value["manual"] != 1
            or value["isolated"] != 0
            or not focusable(value) & (1 << target)
            or value["priority"] != held_priorities(value, target)
            or not value["frame"] < value["deadline_frame"] <= value["frame"] + 900
            or not value["ms"] < value["deadline_ms"] <= value["ms"] + 60000
        ):
            raise ValueError("native_focus_held_contract")
    if value["phase"] == 4:
        if (
            value["manual"]
            or value["isolated"]
            or value["priority"] != baseline_priorities(value)
            or value["deadline_frame"]
            or value["deadline_ms"]
        ):
            raise ValueError("native_focus_baseline_contract")
    return value


def decode(raw, expected_binding):
    if type(raw) is not bytes or len(raw) % JOURNAL_SIZE or len(raw) > 4096 * JOURNAL_SIZE:
        raise ValueError("native_journal_truncated_or_unbounded")
    binding = wire_binding(expected_binding)
    records = []
    focus_selector = None
    focus_request = 0
    focus_reservations = 0
    last_callback = 0
    for index in range(len(raw) // JOURNAL_SIZE):
        row = raw[index * JOURNAL_SIZE : (index + 1) * JOURNAL_SIZE]
        magic, version, sequence, size, kind, callback, intent = struct.unpack_from("<7I", row)
        if (
            (magic, version, sequence, size) != (MAGIC, VERSION, index + 1, JOURNAL_SIZE)
            or kind not in (1, 2, 3)
            or not max(1, last_callback) <= callback < 0xFFFFFFFF
            or row[JOURNAL_BINDING : JOURNAL_BINDING + BINDING_SIZE] != binding
            or struct.unpack_from("<I", row, JOURNAL_END)[0] != 0x454E4437
        ):
            raise ValueError("native_journal_identity_or_sequence")
        last_callback = callback
        record = dict(sequence=sequence, kind=kind, callback_serial=callback, intent_not_after_frame=intent)
        payload = row[JOURNAL_FOCUS : JOURNAL_FOCUS + FOCUS_SIZE]
        if kind == 3:
            focus = decode_focus(payload)
            if (
                focus["callback"] != callback
                or focus["deadline_frame"] != intent
                or focus["request"] < focus_request
                or focus["call_reservations"] < focus_reservations
                or focus_selector is not None
                and focus["selector"] != focus_selector
            ):
                raise ValueError("native_focus_journal_regression")
            focus_selector = focus["selector"]
            focus_request = focus["request"]
            focus_reservations = focus["call_reservations"]
            record["focus"] = focus
        elif any(payload):
            raise ValueError("native_untyped_focus_journal_payload")
        records.append(record)
    return records


def verified(raw, native):
    """Whether the journal decodes and has exactly the published record count."""
    try:
        if (
            type(native) is not dict
            or native.get("magic") != MAGIC
            or native.get("version") != VERSION
            or native.get("size") != SHARED_SIZE
            or type(native.get("journal_records")) is not int
            or not 0 <= native["journal_records"] <= 4096
        ):
            return False
        records = decode(raw, native["binding"])
        focus = native.get("focus")
        return len(records) == native["journal_records"] and not (
            focus is not None and focus["phase"] == 0 and any(row["kind"] == 3 for row in records)
        )
    except (KeyError, TypeError, ValueError, OverflowError, struct.error, UnicodeError):
        return False
