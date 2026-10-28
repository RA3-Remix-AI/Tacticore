"""Damage raw paired censuses; synthetic packets never grant field scope."""
import struct
import json
from pathlib import Path
import subprocess
import unittest
from types import SimpleNamespace as NS

from host_runtime import runtime_home_evidence as review


def bits(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


class HomeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.actor = NS(thing=0x5000, update=0x6000, object_id=55, owner=0x2000)

    def proof(self, group=1, frame=100, *, occupied=False):
        h = [0] * 24
        h[:2] = group, 2 if occupied else 1
        h[2:5] = map(bits, (0, 0, 210))
        h[5:11] = 0x1000, 0x5000, 2, 1, 1, 0x7000 if occupied else 0
        h[11:18] = 55, 0x5000, 0x2000, 0x4000, 0x4000, 1, 1
        h[18:24] = 2, 20000, 20, 2, 2, 0 if occupied else 2
        nodes = [(0x5000, 0xc4db60, 55, 0x2000, 0x7000, *map(bits, (40, 0, 210))),
                 (0x7000, 0xc4db60, 77, 0x2000, 0, *map(bits, (0 if occupied else 80, 0, 210)))]
        def row(kind, words):
            return NS(kind=kind, words=words, word_count=24, self=0x6000, target=0x5000,
                      frame=frame, caller=0, operation=0, scope=0, source=0)
        result = [row(32, h)]
        if not occupied:
            world=[]
            for n in nodes:
                a=(n[0],n[4],n[3]);world.extend((*a,*a))
            result.append(row(33,[group,0,*world,*([0]*10)]))
        for i, n in enumerate(nodes):
            if not occupied or i==1:
                result.append(row(34, [group, i, *n, *n, *([0] * 6)]))
        return result

    def groups(self, rows):
        return review.groups(rows, self.actor, 0x1000, 0x4000)

    def samples(self, frames):
        return [NS(frame=f, settled=True, team=0x4000, stance=2, state_id=94,
                   state_vtable=0xc551a0, command_source=1, path=0, state_flags=0,
                   xyz=NS(x=40, y=0, z=210)) for f in frames]

    def test_clear_and_occupied_are_recomputed(self):
        self.assertTrue(self.groups(self.proof())[0]['clear'])
        self.assertFalse(self.groups(self.proof(occupied=True))[0]['clear'])

    def test_summary_cannot_hide_original_blocker(self):
        rows = self.proof(occupied=True)
        rows[0].words[10] = 0
        self.assertIsNone(self.groups(rows))

    def test_changed_paired_coordinates_fail(self):
        rows = self.proof()
        rows[-1].words[15] = bits(0)
        self.assertIsNone(self.groups(rows))

    def test_missing_node_or_broken_closure_fail(self):
        rows = self.proof()
        self.assertIsNone(self.groups(rows[:-1]))
        rows[1].words[9] = rows[1].words[12] = 0x9000
        self.assertIsNone(self.groups(rows))

    def test_actor_identity_and_owner_are_independent(self):
        rows = self.proof()
        rows[2].words[5] = rows[2].words[13] = 0x9999
        self.assertIsNone(self.groups(rows))

    def test_return_requires_three_distinct_frames_and_current_proof(self):
        rows = sum((self.proof(i + 1, 100 + i) for i in range(3)), [])
        proofs = self.groups(rows)
        samples = self.samples((100, 101, 102))
        self.assertTrue(review.has_return_proof(proofs, (0, 0, 210), 102, samples, 0x4000))
        self.assertFalse(review.has_return_proof(proofs, (0, 0, 210), 103, samples, 0x4000))
        same = sum((self.proof(i + 1, 100) for i in range(3)), [])
        self.assertFalse(review.has_return_proof(self.groups(same), (0, 0, 210), 100, samples, 0x4000))

    def test_occupied_transition_and_missing_stop_reset_clearance(self):
        rows = self.proof(1, 100) + self.proof(2, 101, occupied=True) + self.proof(3, 102)
        proofs = self.groups(rows)
        samples = self.samples((100, 101, 102))
        self.assertFalse(review.has_return_proof(proofs, (0, 0, 210), 102, samples, 0x4000))
        rows = sum((self.proof(i + 1, 100 + i) for i in range(3)), [])
        samples[1].state_id = 16
        self.assertFalse(review.has_return_proof(self.groups(rows), (0, 0, 210), 102, samples, 0x4000))

    def test_stale_binding_and_dropped_group_fail(self):
        rows = self.proof()
        rows[0].words[5] = 0x9999
        self.assertIsNone(self.groups(rows))
        self.assertIsNone(self.groups(self.proof(2)))

    def test_actual_cpp_reader_closes_751_thing_roster_and_compact_pairs(self):
        exe=Path(__file__).resolve().parents[1]/'tactical/runtime/bin/test_controller.exe'
        fixture=json.loads(subprocess.check_output([str(exe),'--home-clearance-fixture'],text=True,timeout=10))
        self.assertFalse(fixture['game_access'])
        rows=[NS(**r,word_count=24,caller=0,operation=0,scope=0,source=0) for r in fixture['traces']]
        proof=self.groups(rows)
        self.assertIsNotNone(proof)
        self.assertEqual(751,proof[0]['global_count'])
        self.assertTrue(proof[0]['clear'])
        self.assertEqual(253,len(rows))


if __name__ == '__main__':
    unittest.main()
