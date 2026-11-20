"""Live public start markers are read for any map without decoding other names."""

import struct
import unittest

from public_start_waypoints import LIST_PINS, WAYPOINT_LIST_HEAD, owned_object_points, public_start_waypoints


class FakeMemory:
    def __init__(self):
        self.bytes = {}
        for address, value in LIST_PINS.items():
            self.put(address, value)

    def put(self, address, value):
        for offset, byte in enumerate(value):
            self.bytes[address + offset] = byte

    def read(self, address, size):
        return bytes(self.bytes.get(address + offset, 0) for offset in range(size))

    def u32(self, address):
        return struct.unpack("<I", self.read(address, 4))[0]


def waypoint_list(names, *, base=0x100000):
    memory = FakeMemory()
    nodes = [base + 0x100 * index for index in range(len(names))]
    memory.put(WAYPOINT_LIST_HEAD, struct.pack("<I", nodes[0] if nodes else 0))
    for index, (node, name) in enumerate(zip(nodes, names)):
        text = base + 0x10000 + 0x100 * index + 4
        encoded = name.encode("ascii")
        memory.put(text - 4, struct.pack("<H", len(encoded)))
        memory.put(text, encoded)
        following = nodes[index + 1] if index + 1 < len(nodes) else 0
        raw = struct.pack("<II", 0, 0) + struct.pack("<I", text) + struct.pack("<fff", 512.0 * index, 100.0, 0.0)
        raw += struct.pack("<I", 0) + struct.pack("<I", following)
        memory.put(node, raw)
    return memory


class PublicStartTests(unittest.TestCase):
    def test_every_start_marker_is_returned(self):
        names = ["Player_3_Start", "SecretTarget", "Player_1_Start", "Player_2_Start", "Player_4_Start"]
        rows = public_start_waypoints(waypoint_list(names).read)
        self.assertEqual(
            [row["name"] for row in rows], ["Player_1_Start", "Player_2_Start", "Player_3_Start", "Player_4_Start"]
        )
        self.assertEqual(rows[0]["xyz"], [1024.0, 100.0, 0.0])

    def test_same_length_non_start_names_are_ignored(self):
        rows = public_start_waypoints(waypoint_list(["Player_1_Start", "Player_X_Start"]).read)
        self.assertEqual([row["name"] for row in rows], ["Player_1_Start"])

    def test_duplicate_marker_is_rejected(self):
        with self.assertRaises(ValueError):
            public_start_waypoints(waypoint_list(["Player_1_Start", "Player_1_Start"]).read)

    def test_changed_native_code_is_rejected(self):
        memory = waypoint_list(["Player_1_Start"])
        memory.put(next(iter(LIST_PINS)), b"\x90")
        with self.assertRaises(ValueError):
            public_start_waypoints(memory.read)

    def test_cycle_is_rejected(self):
        memory = waypoint_list(["Player_1_Start", "Player_2_Start"])
        memory.put(0x100100 + 28, struct.pack("<I", 0x100000))
        with self.assertRaises(ValueError):
            public_start_waypoints(memory.read)


class OwnedObjectTests(unittest.TestCase):
    def test_only_the_requested_owner_is_returned(self):
        memory = FakeMemory()
        logic, things = 0x200000, [0x300000, 0x300800]
        memory.put(logic + 0xB4, struct.pack("<I", things[0]))
        for index, (thing, owner) in enumerate(zip(things, (0x5000, 0x6000))):
            memory.put(thing, struct.pack("<I", 0xC4DB60))
            memory.put(thing + 0x7C, struct.pack("<I", things[index + 1] if index + 1 < len(things) else 0))
            memory.put(thing + 0x418, struct.pack("<I", owner))
            memory.put(thing + 0x38, struct.pack("<fff", 100.0 * (index + 1), 200.0, 0.0))
        self.assertEqual(owned_object_points(memory, logic, 0x6000), [(200.0, 200.0)])


if __name__ == "__main__":
    unittest.main()
