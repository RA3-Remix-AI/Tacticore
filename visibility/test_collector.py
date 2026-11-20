import copy, struct, unittest
from unittest.mock import patch
from native_read import read_player_relation
from collector import VisibilityCollector
from projection import VisibilityProjection
from test_native_read import FakeMemory


class CollectorTests(unittest.TestCase):
    def setUp(self):
        m = self.m = FakeMemory()
        self.session = {"session_id": "s", "mod_sha256": "sha"}
        for p, n in [
            (0xCD8CE4, 0x150000),
            (0x150000, 0xBEB630),
            (0x150050, 100),
            (0xCE8C9C, 0x200000),
            (0x20003C, 0x130000),
            (0x130000, 0xC5BCE0),
            (0x130020, 3),
            (0x130090, 0x210000),
            (0x210000, 0xC60F60),
            (0x140000, 0xC5BCE0),
            (0x140020, 4),
            (0x1500B4, 0x160000),
        ]:
            m.u(p, n)
        for ob, owner, template, body, record, oid, xyz, nxt in [
            (0x160000, 0x140000, 0x180000, 0x190000, 0x1A0000, 17, (105.0, 205.0, 0.0), 0x170000),
            (0x170000, 0x130000, 0x181000, 0x191000, 0x1A1000, 18, (115.0, 205.0, 0.0), 0),
        ]:
            for off, value in [
                (0, 0xC4DB60),
                (4, template),
                (0x33C, body),
                (0x9C, record),
                (0xDC, oid),
                (0x418, owner),
                (0x7C, nxt),
                (0xC8, 0),
            ]:
                m.u(ob + off, value)
            m.u(template + 8, 0x123)
            m.put(body + 4, struct.pack("<f", 100))
            m.put(ob + 0x38, struct.pack("<fff", *xyz))
            m.u(record + 0x30, 1)
            m.u(record, 0x110000)
            m.u(record + 0x1C, 0x1B0000 + (0 if oid == 17 else 0x1000))
            m.u(record + 0x20, 1)
            m.u(0x1B0000 + (0 if oid == 17 else 0x1000), 0x120000 + (0 if oid == 17 else 0x34))
            m.put(record + 0xF8, b"\0\0")
        m.counter(0, 0, 3, 1)
        m.counter(1, 0, 3, 1)
        for p, n in [
            (0x1300FC, 0x1D0000),
            (0x1D0010, 1),
            (0x1D0008, 0x1E0000),
            (0x1D000C, 4),
            (0x1E0000, 0x1F0000),
            (0x1F0000, 4),
            (0x1F0004, 0),
            (0x1F0008, 0),
        ]:
            m.u(p, n)
        m.put(0x992130, bytes.fromhex("8b4928e9b8f1ffff"))
        m.put(0x990379, bytes.fromhex("8b448124c20400"))
        m.put(0x6FDA40, bytes.fromhex("8b81c8000000"))
        self.proof = dict(
            schema_version=2,
            object_visibility_method="native_footprint_reconstruction",
            footprint_live_verified=True,
            session_id="s",
            target_player_id=3,
            package_sha256="sha",
            terrain_view_live_verified=True,
            object_view_live_verified=True,
            conservative_stealth_exclusion_reviewed=True,
            no_observer_fallback=True,
        )
        self.safety = {
            "package_sha256": "sha",
            "templates": {"0x123": {"role": "infantry", "source_audited_no_intrinsic_stealth": True}},
        }
        self.projection = VisibilityProjection("s", 3, "sha", self.proof, self.safety)
        self.c = VisibilityCollector(m, self.session, 3, self.projection)

    def sample(self, t):
        self.m.u(0x150050, int(t * 15))
        return self.c.collect(t)

    def test_clock_parameter_rejects_stale_sample(self):
        with self.assertRaises(ValueError):
            self.c.collect(0)

    def test_public_private_boundary(self):
        r = self.sample(1)
        self.assertEqual(len(r["contacts"]), 1)
        cid = r["contacts"][0]["contact_id"]
        self.assertEqual(self.c.private_targets[cid]["address"], 0x160000)
        self.assertEqual(r["viewer_player_id"], 3)
        self.assertNotIn("xyz", str(r))
        self.assertNotIn("object_id", str(r))

    def test_hidden_target_removed_private_and_memory_frozen(self):
        self.sample(1)
        self.m.u(0x1A0030, 4)
        self.m.counter(0, 0, 3, 0)
        r = self.sample(2)
        self.assertEqual(self.c.private_targets, {})
        self.assertFalse(r["contacts"][0]["currently_visible"])
        self.assertEqual(r["contacts"][0]["observed_at_game_seconds"], 1)

    def test_active_invisible_excluded(self):
        self.m.u(0x1600C8, 1 << 11)
        self.assertEqual(self.sample(1)["contacts"], [])

    def test_camo_excluded(self):
        self.m.u(0x1600C8, 1 << 12)
        self.assertEqual(self.sample(1)["contacts"], [])

    def test_template_unknown_excluded(self):
        self.safety["templates"] = {}
        self.assertEqual(self.sample(1)["contacts"], [])

    def test_false_proof_own_points_only(self):
        self.proof["object_view_live_verified"] = False
        r = self.sample(1)
        self.assertFalse(r["visibility_verified"])
        self.assertEqual(r["contacts"], [])
        self.assertTrue(self.c.region_points)
        self.assertFalse(self.c.private_targets)

    def test_ally_excluded(self):
        self.m.u(0x1F0004, 2)
        self.assertEqual(self.sample(1)["contacts"], [])

    def test_unknown_relation_excluded(self):
        self.m.u(0x1F0004, 7)
        self.assertEqual(self.sample(1)["contacts"], [])

    def test_invalidated_cache_reconstructed(self):
        self.m.u(0x1A0030, 0)
        self.assertEqual(len(self.sample(1)["contacts"]), 1)

    def test_grid_fog_blocks_cached_clear(self):
        self.m.counter(0, 0, 3, 0)
        self.assertEqual(self.sample(1)["contacts"], [])

    def test_own_region_points_no_hidden_truth(self):
        self.m.u(0x1A0030, 4)
        self.m.counter(0, 0, 3, 0)
        self.sample(1)
        self.assertEqual(list(self.c.region_points.values()), [[115.0, 205.0, 0.0]])

    def test_failure_discards_old_private_targets(self):
        self.sample(1)
        self.m.u(0x150000, 0)
        with self.assertRaises(ValueError):
            self.sample(2)
        self.assertEqual(self.c.private_targets, {})

    def test_list_cycle_fails_closed(self):
        self.m.u(0x17007C, 0x160000)
        with self.assertRaises(ValueError):
            self.sample(1)
        self.assertEqual(self.c.private_targets, {})

    def test_relation_enemy(self):
        self.assertEqual(read_player_relation(self.m, 0x130000, 4), "enemy")

    def test_relation_missing_is_neutral(self):
        self.m.u(0x1D0010, 0)
        self.assertEqual(read_player_relation(self.m, 0x130000, 4), "neutral")

    def test_relation_self(self):
        self.assertEqual(read_player_relation(self.m, 0x130000, 3), "self")

    def test_relation_cycle_rejects(self):
        self.m.u(0x1F0000, 8)
        self.m.u(0x1F0008, 0x1F0000)
        with self.assertRaises(ValueError):
            read_player_relation(self.m, 0x130000, 4)

    def test_relationship_change_during_sample_discards_all_contacts(self):
        original = read_player_relation
        calls = 0

        def changing(memory, player, index):
            nonlocal calls
            if index == 4:
                calls += 1
                if calls == 3:
                    return "ally"
            return original(memory, player, index)

        with patch("collector.read_player_relation", side_effect=changing):
            with self.assertRaisesRegex(ValueError, "relationship changed"):
                self.sample(1)
        self.assertEqual(self.c.private_targets, {})
        self.assertEqual(self.projection.seen, {})

    def test_player_identity_change_during_sample_discards_all_contacts(self):
        original = self.m.u32
        reads = 0

        def changing(address):
            nonlocal reads
            if address == 0x140020:
                reads += 1
                if reads == 2:
                    return 5
            return original(address)

        with patch.object(self.m, "u32", side_effect=changing):
            with self.assertRaisesRegex(ValueError, "relationship changed"):
                self.sample(1)
        self.assertEqual(self.c.private_targets, {})

    def test_player_metadata_is_read_once_per_sample_and_revalidated(self):
        with patch("collector.read_player_relation", wraps=read_player_relation) as read:
            self.sample(1)
        self.assertEqual(sum(call.args[2] == 4 for call in read.call_args_list), 3)


if __name__ == "__main__":
    unittest.main()
