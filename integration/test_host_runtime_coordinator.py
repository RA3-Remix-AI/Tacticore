from pathlib import Path
import tempfile
import unittest
import uuid

from host_runtime.capabilities import CapabilityCatalog, VerifiedGrant
from host_runtime.contracts import ContractError, SessionBinding
from host_runtime.coordinator import HostCoordinator
from host_runtime.gateway import ExecutionGateway, NativeReceipt
from host_runtime.journal import CommandJournal
from host_runtime.orchestration import OrchestrationConfig


def uid():
    return str(uuid.uuid4())


class SyntheticAdapter:
    test_only = True
    def __init__(self):
        self.commands = []

    def preflight(self, command, binding):
        pass

    def dispatch(self, command, binding):
        self.commands.append(command)
        body = command['payload']; op = command['operation']
        if op == 'produce':
            front = body['unit'] == 'conscript'
            facts = dict(object_id=801 if front else 802, actor_generation=11 if front else 12,
                         paid_verified=True, created=True, paid=85 if front else 220,
                         enqueue_frame=body['observed_frame'])
            status = 'completed'
        elif op == 'reserve':
            facts = dict(lease_issued_frame=body['observed_frame']); status = 'accepted'
        else:
            facts = {}; status = 'accepted'
        return NativeReceipt(command['command_id'], binding.binding_hash, status, facts)


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.journal = CommandJournal(Path(self.tmp.name) / 'ledger.sqlite')
        self.binding = SessionBinding(1, uid(), 3, uid(), 1234,
                                     '2026-10-26T00:00:00+00:00', uid(), 'a'*64, 'b'*64)
        self.run = uid(); self.task = uid(); self.plan = uid()
        catalog = CapabilityCatalog.verify(self.binding,
            ['production.infantry', 'production.anti_air', 'tactics.coordinate_force'],
            lambda name, _: VerifiedGrant(name, 'synthetic-only', 'c'*64, 'd'*64, 'offline-test-only'))
        self.adapter = SyntheticAdapter()
        self.gateway = ExecutionGateway(self.run, self.binding, self.journal, catalog, self.adapter)
        self.coordinator = HostCoordinator(self.gateway, config=OrchestrationConfig(production_gap_frames=0))
        self.coordinator.create_task(self.task)

    def tearDown(self):
        self.journal.close(); self.tmp.cleanup()

    def obs(self, frame=100, **changes):
        row = dict(session_id=self.binding.session_id, session_binding_hash=self.binding.binding_hash,
                   game_frame=frame, monotonic_ms=(frame-100)*10, source='simulated', own_view_verified=True,
                   contacts=[dict(contact_id='target', object_id=900, owner_player_id=4, relation='enemy',
                                  currently_visible=True, observed_frame=frame, xyz=[600,0,0], hp=1000,
                                  role='structure', type_hash='0x123', template='Barracks')],
                   anchors=[[0,0,0]], actors=[],
                   plan=dict(session_id=self.binding.session_id, plan_id=self.plan, task_id=self.task,
                             generation=1, expires_frame=10000, valid_until_monotonic_ms=100000))
        row.update(changes); return row

    def actors(self, held=False):
        lease = self.coordinator.snapshot()['tasks'][0]['lease_id']
        return [dict(role=role, object_id=ident, generation=gen, owner_player_id=3,
                     alive=True, ground_ready=True, held=held, ready=held, lease_id=lease)
                for role, ident, gen in [('infantry',801,11),('anti_air',802,12)]]

    def test_full_orchestration_goes_through_durable_gateway(self):
        one = self.coordinator.tick(self.obs())
        self.assertEqual(one['command_results'][0]['status'], 'completed')
        self.coordinator.tick(self.obs(101, actors=self.actors()))
        self.coordinator.tick(self.obs(102, actors=self.actors()))
        self.coordinator.tick(self.obs(103, actors=self.actors(True)))
        running = self.coordinator.tick(self.obs(104, actors=self.actors(True)))
        self.assertEqual(running['task']['state'], 'executing')
        self.assertEqual([c['operation'] for c in self.adapter.commands], ['produce','produce','reserve','commit'])
        for command in self.adapter.commands:
            stored = self.journal.get_command(self.run, command['request_id'])
            self.assertEqual(stored['command_id'], command['command_id'])
        events = self.journal.events(self.run)
        kinds = [event['event_type'] for event in events]
        self.assertIn('orchestration_step', kinds)
        self.assertIn('dispatch_intent_committed', kinds)
        self.assertFalse(running['physical_evidence_granted'])

    def test_no_opportunity_never_reaches_real_transport(self):
        result = self.coordinator.tick(self.obs(contacts=[]))
        self.assertEqual(self.adapter.commands, [])
        self.assertEqual(result['command_results'], [])
        self.assertTrue(any(row['event_type']=='orchestration_step' for row in self.journal.events(self.run)))

    def test_observation_other_game_binding_cannot_dispatch(self):
        with self.assertRaisesRegex(ContractError, 'observation_binding_mismatch'):
            self.coordinator.tick(self.obs(session_binding_hash='0'*64))
        self.assertEqual(self.adapter.commands, [])

    def test_second_task_cannot_start_while_first_holds_lifecycle(self):
        self.coordinator.tick(self.obs())
        with self.assertRaisesRegex(ContractError, 'active_task_not_released'):
            self.coordinator.create_task(uid())

    def test_simulation_cannot_reach_non_test_adapter(self):
        self.adapter.test_only = False
        with self.assertRaisesRegex(ContractError, 'simulated_observation'):
            self.coordinator.tick(self.obs())
        self.assertEqual(self.adapter.commands, [])


if __name__ == '__main__':
    unittest.main()
