from pathlib import Path
import tempfile
import unittest
import uuid

from host_runtime.capabilities import CapabilityCatalog, VerifiedGrant
from host_runtime.contracts import SessionBinding
from host_runtime.gateway import AdmissionRefused, ExecutionGateway, NativeReceipt
from host_runtime.journal import CommandJournal, RequestConflict


def uid():
    return str(uuid.uuid4())


class Adapter:
    def __init__(self, mode='success'):
        self.mode = mode; self.calls = []

    def preflight(self, command, binding):
        if self.mode == 'refuse':
            raise AdmissionRefused('current_game_identity_changed')

    def dispatch(self, command, binding):
        self.calls.append(command)
        if self.mode == 'crash':
            raise OSError('private provider response must not be logged')
        if self.mode == 'cancel':
            raise KeyboardInterrupt()
        return NativeReceipt(command['command_id'],
                             '0' * 64 if self.mode == 'wrong_binding' else binding.binding_hash,
                             'completed', {'paid_verified': True, 'object_id': 123})


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.journal = CommandJournal(Path(self.tmp.name) / 'journal.sqlite')
        self.binding = SessionBinding(1, uid(), 3, uid(), 1234,
                                      '2026-10-26T00:00:00+00:00', uid(), 'a'*64, 'b'*64)
        self.run = uid()
        self.catalog = CapabilityCatalog.verify(self.binding, ['production.infantry'],
            lambda candidate, binding: VerifiedGrant(candidate, 'evidence', 'c'*64, 'd'*64, 'conscript-only'))

    def tearDown(self):
        self.journal.close(); self.tmp.cleanup()

    def gateway(self, adapter, catalog=None):
        return ExecutionGateway(self.run, self.binding, self.journal,
                                self.catalog if catalog is None else catalog, adapter)

    def test_exact_duplicate_does_not_call_adapter_again(self):
        adapter = Adapter(); gateway = self.gateway(adapter); request = uid()
        one = gateway.submit(request, 'produce', {'unit': 'conscript'})
        two = gateway.submit(request, 'produce', {'unit': 'conscript'})
        self.assertEqual(one['status'], 'completed')
        self.assertEqual(one['command_id'], two['command_id'])
        self.assertEqual(len(adapter.calls), 1)
        with self.assertRaises(RequestConflict):
            gateway.submit(request, 'produce', {'unit': 'flak'})

    def test_missing_capability_and_unknown_operation_are_audited(self):
        adapter = Adapter(); gateway = self.gateway(adapter, CapabilityCatalog())
        missing = gateway.submit(uid(), 'produce', {'unit': 'conscript'})
        unknown = gateway.submit(uid(), 'shell', {'command': 'not allowed'})
        self.assertEqual(missing['status'], 'rejected')
        self.assertEqual(unknown['status'], 'rejected')
        self.assertEqual(unknown['receipt']['reason_code'], 'operation_unsupported')
        self.assertEqual(adapter.calls, [])

    def test_preflight_refusal_means_no_dispatch(self):
        adapter = Adapter('refuse'); result = self.gateway(adapter).submit(uid(), 'produce', {'unit': 'conscript'})
        self.assertEqual(result['status'], 'rejected')
        self.assertEqual(adapter.calls, [])

    def test_single_actor_reserve_never_inherits_combined_force_authority(self):
        adapter = Adapter()
        combined = CapabilityCatalog.verify(self.binding, ['tactics.coordinate_force'],
            lambda candidate, binding: VerifiedGrant(candidate, 'pair-evidence', 'c'*64, 'd'*64, 'two-role-only'))
        refused = self.gateway(adapter, combined).submit(uid(), 'reserve', {'purpose': 'move_hold_return'})
        self.assertEqual('rejected', refused['status'])
        self.assertEqual([], adapter.calls)
        move = CapabilityCatalog.verify(self.binding, ['tactics.move_hold_return'],
            lambda candidate, binding: VerifiedGrant(candidate, 'movement-evidence', 'c'*64, 'd'*64, 'single-actor-only'))
        accepted = self.gateway(adapter, move).submit(uid(), 'reserve', {'purpose': 'move_hold_return'})
        self.assertEqual('completed', accepted['status'])
        self.assertEqual(1, len(adapter.calls))

    def test_delivery_unknown_is_not_retried(self):
        adapter = Adapter('crash'); gateway = self.gateway(adapter); request = uid()
        first = gateway.submit(request, 'produce', {'unit': 'conscript'})
        retry = gateway.submit(request, 'produce', {'unit': 'conscript'})
        self.assertEqual(first['status'], 'uncertain')
        self.assertEqual(retry['status'], 'uncertain')
        self.assertEqual(len(adapter.calls), 1)
        self.assertNotIn('private provider', str(self.journal.events(self.run)))

    def test_cancellation_after_dispatch_is_persisted_uncertain(self):
        adapter = Adapter('cancel'); gateway = self.gateway(adapter); request = uid()
        with self.assertRaises(KeyboardInterrupt):
            gateway.submit(request, 'produce', {'unit': 'conscript'})
        self.assertEqual(self.journal.get_command(self.run, request)['status'], 'uncertain')

    def test_mismatched_receipt_becomes_unknown_not_success(self):
        result = self.gateway(Adapter('wrong_binding')).submit(uid(), 'produce', {'unit': 'conscript'})
        self.assertEqual(result['status'], 'uncertain')

    def test_return_can_release_even_with_no_current_capability(self):
        adapter = Adapter(); gateway = self.gateway(adapter, CapabilityCatalog())
        result = gateway.submit(uid(), 'return', {'lease_id': uid()})
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(result['status'], 'completed')
        # This command receipt is not a claim that a mission succeeded.
        self.assertNotIn('mission_completed', result)


if __name__ == '__main__':
    unittest.main()
