"""Four-player navigation must retain both additional public start markers."""

import struct
import unittest

from read_map_waypoints import starting_waypoints


def map_fixture(start_names):
    dictionary = {"ObjectsList": 1, "Object": 2, "waypointName": 3, "waypointID": 4}
    header = b"CkMp" + struct.pack("<I", len(dictionary))
    for name, ident in dictionary.items():
        encoded = name.encode("ascii")
        header += bytes([len(encoded)]) + encoded + struct.pack("<I", ident)
    objects = b""
    for index, name in enumerate(start_names, 1):
        template = b"*Waypoints/Waypoint"
        encoded = name.encode("ascii")
        payload = struct.pack("<fff", index * 512.0, 512.0, 0.0) + b"\0" * 8
        payload += struct.pack("<H", len(template)) + template + struct.pack("<H", 2)
        payload += struct.pack("<IH", (3 << 8) | 3, len(encoded)) + encoded
        payload += struct.pack("<Ii", (4 << 8) | 1, index)
        objects += struct.pack("<IHI", 2, 3, len(payload)) + payload
    return header + struct.pack("<IHI", 1, 3, len(objects)) + objects


class PublicStartTests(unittest.TestCase):
    def test_original_two_player_reader(self):
        rows = starting_waypoints(map_fixture(["Player_1_Start", "Player_2_Start"]))
        self.assertEqual([row["name"] for row in rows], ["Player_1_Start", "Player_2_Start"])

    def test_all_four_starts_are_retained(self):
        names = [f"Player_{index}_Start" for index in range(1, 5)]
        rows = starting_waypoints(map_fixture(names), player_count=4)
        self.assertEqual([row["name"] for row in rows], names)

    def test_missing_or_duplicate_start_is_rejected(self):
        for names in (
            ["Player_1_Start", "Player_2_Start"],
            ["Player_1_Start", "Player_2_Start", "Player_3_Start", "Player_3_Start"],
        ):
            with self.subTest(names=names), self.assertRaises(ValueError):
                starting_waypoints(map_fixture(names), player_count=4)

    def test_non_start_waypoints_are_excluded(self):
        names = [f"Player_{index}_Start" for index in range(1, 5)]
        rows = starting_waypoints(map_fixture(names + ["SecretObjective"]), player_count=4)
        self.assertEqual(len(rows), 4)

    def test_unsupported_count_is_rejected(self):
        for count in (True, 0, 3, 8):
            with self.subTest(count=count), self.assertRaises(ValueError):
                starting_waypoints(b"", player_count=count)


if __name__ == "__main__":
    unittest.main()
