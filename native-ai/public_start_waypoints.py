"""Read public map facts used to derive a match scenario on any map.

* ``public_start_waypoints`` walks the live waypoint list and returns every
  ``Player_N_Start`` marker. It is the list walk of
  read_public_region_targets.lookup_public (head 0xce8f64, node +8 name
  pointer, +12 position, +28 next), generalised from two fixed names to all
  start markers. Names of any other length are never decoded.
* ``owned_object_points`` returns map positions of one player's live objects,
  with the owner (+0x418) and position (+0x38) offsets used by
  macro_observation.own_census. Callers use it only for allied players,
  whose bases are shared vision.

No process writes, native calls or enemy object reads.
"""
import math
from pathlib import Path
import re
import struct
import sys

VISIBILITY = str(Path(__file__).resolve().parents[1] / 'visibility')
if VISIBILITY not in sys.path:
    sys.path.append(VISIBILITY)

WAYPOINT_LIST_HEAD = 0xce8f64
# Native lookup code that reads the same list (read_public_region_targets.PINS).
LIST_PINS = {0x85f69b: bytes.fromhex('8b1d648fce00'), 0x85f6b7: bytes.fromhex('8b4308'),
             0x85f6ef: bytes.fromhex('8b5b1c')}
START_NAME = re.compile(r'Player_([1-8])_Start')
START_NAME_LENGTH = len('Player_1_Start')
MAX_WAYPOINTS = 8192


def _pointer(value, size=4):
    if value % 4 or not 0x10000 <= value <= 0x100000000 - size:
        raise ValueError('invalid_waypoint_pointer')
    return value


def public_start_waypoints(read):
    """All Player_N_Start markers of the loaded map, sorted by name."""
    for address, expected in LIST_PINS.items():
        if read(address, len(expected)) != expected:
            raise ValueError('public_waypoint_native_pin')

    def word(address):
        return struct.unpack('<I', read(address, 4))[0]

    head = word(WAYPOINT_LIST_HEAD)
    at = head
    seen = set()
    links = []
    found = {}
    while at:
        _pointer(at, 32)
        if at in seen or len(seen) >= MAX_WAYPOINTS:
            raise ValueError('public_waypoint_list_bound')
        seen.add(at)
        raw = read(at, 32)
        name_pointer = struct.unpack_from('<I', raw, 8)[0]
        name = None
        if name_pointer:
            size = struct.unpack('<H', read(_pointer(name_pointer) - 4, 2))[0]
            if size > 256:
                raise ValueError('public_waypoint_name_bound')
            if size == START_NAME_LENGTH:
                name = read(name_pointer, size).decode('ascii', errors='replace')
        if name is not None and START_NAME.fullmatch(name):
            if name in found:
                raise ValueError('duplicate_public_waypoint')
            xyz = list(struct.unpack_from('<fff', raw, 12))
            if not all(math.isfinite(value) and abs(value) < 1e7 for value in xyz):
                raise ValueError('public_waypoint_position')
            found[name] = xyz
        links.append((at, raw))
        at = struct.unpack_from('<I', raw, 28)[0]
    if word(WAYPOINT_LIST_HEAD) != head or any(read(address, 32) != raw for address, raw in links):
        raise ValueError('public_waypoint_list_changed')
    return [dict(name=name, xyz=found[name]) for name in sorted(found)]


def owned_object_points(memory, logic, owner, limit=4096):
    """(x, y) of an allied player's live objects; nothing else is read."""
    from native_read import walk_live_things
    points = []
    for thing in walk_live_things(memory, logic):
        if memory.u32(thing + 0x418) != owner:
            continue
        x, y, _ = struct.unpack('<fff', memory.read(thing + 0x38, 12))
        if math.isfinite(x) and math.isfinite(y):
            points.append((x, y))
        if len(points) >= limit:
            break
    return points
