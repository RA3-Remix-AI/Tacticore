"""Diagnostic context cannot manufacture route proof or alter native outcomes."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'integration'))


def load(name):
    spec = importlib.util.spec_from_file_location('test_context_' + name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


environment = load('environment')
trial = load('journaled_trial')


class Memory:
    def __init__(self):
        self.frame = 100
        self.reads = 0

    def u32(self, address):
        self.reads += 1
        return {0xcd8ce4: 0x10000, 0x10050: self.frame}[address]


def census(frame=100):
    return dict(frame_start=frame, frame_end=frame, candidate_count=1, candidates=[dict(
        object_id=780, type_hash='0x80d4ea1e', xyz=[10, 20, 0])])


class EnvironmentTests(unittest.TestCase):
    def make(self, **kwargs):
        memory, record = Memory(), {}
        reader = environment.OwnEnvironmentRecorder(memory, 3, {}, 780, record, **kwargs)
        return memory, record, reader

    def test_frame_spanning_inventory_remains_diagnostic_and_throttles_unchanged_phase(self):
        memory, record, reader = self.make()
        def spanning(*args):
            memory.frame += 2
            return census(memory.frame)
        with patch.object(environment, 'own_candidates', side_effect=spanning) as sample:
            reader.capture('moving', [30, 20, 0])
            reader.capture('moving', [30, 20, 0])
            reader.capture('returning', [30, 20, 0])
        context = record['own_environment']
        self.assertEqual(2, sample.call_count)
        self.assertEqual([(100, 102), (102, 104)], [(x['frame_start'], x['frame_end']) for x in context['samples']])
        self.assertFalse(context['atomic_snapshot'])
        self.assertFalse(context['route_or_clearance_verified'])

    def test_read_failure_does_not_hide_unknown_native_outcome_or_request_a_command(self):
        memory, record, reader = self.make()
        class Owner:
            def poll(self):
                return dict(command_id='native-command', status='uncertain', receipt=dict(facts=dict(phase='uncertain')))
        with patch.object(environment, 'own_candidates', side_effect=RuntimeError('read unavailable')):
            with self.assertRaisesRegex(ValueError, 'unexpected_terminal_uncertain'):
                trial.await_outcome(Owner(), {}, 'released', 1, reader.capture)
        self.assertTrue(record['own_environment']['incomplete'])
        self.assertEqual([], record['own_environment']['samples'])
        reads = memory.reads
        reader.capture('released')
        self.assertEqual(reads, memory.reads)

    def test_capacity_and_lifecycle_failures_are_explicit_without_success_credit(self):
        memory, record, reader = self.make(capacity=1)
        with patch.object(environment, 'own_candidates', return_value=census()):
            reader.capture('moving')
            reader.capture('returning')
        self.assertEqual('sample_capacity_reached', record['own_environment']['reason'])
        self.assertTrue(record['own_environment']['incomplete'])
        self.assertFalse(record['own_environment']['route_or_clearance_verified'])
        memory, record, reader = self.make()
        with patch.object(environment, 'own_candidates', return_value=census()):
            reader.capture('moving')
            memory.frame = 99
            reader.capture('returning')
        self.assertTrue(record['own_environment']['incomplete'])
        self.assertEqual(1, len(record['own_environment']['samples']))
        self.assertIn('frame_regressed', record['own_environment']['detail'])

    def test_changed_conscript_incarnation_does_not_leave_a_plausible_inventory(self):
        memory, record, reader = self.make()
        row = census()
        row['candidates'][0].update(type_hash='0x19ab11af', address='0x20000', ai_address='0x30000', owner_address='0x40000')
        original = memory.u32
        memory.u32 = lambda address: 999 if address == 0x200dc else original(address)
        with patch.object(environment, 'own_candidates', return_value=copy.deepcopy(row)):
            reader.capture('holding')
        self.assertTrue(record['own_environment']['incomplete'])
        self.assertEqual([], record['own_environment']['samples'])
        self.assertIn('actor_changed', record['own_environment']['detail'])


if __name__ == '__main__':
    unittest.main()
