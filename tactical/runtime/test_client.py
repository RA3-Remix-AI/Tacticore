"""Transport ABI and input boundaries only. Never creates a mapping or game IO."""
import ctypes as c
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch
import tempfile
import uuid
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('runtime_test_layout', HERE / 'layout.py')
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)
sys.path.insert(0, str(HERE.parents[1] / 'integration'))
client_spec = importlib.util.spec_from_file_location('runtime_test_client', HERE / 'client.py')
client = importlib.util.module_from_spec(client_spec)
client_spec.loader.exec_module(client)


class LayoutTests(unittest.TestCase):
    def test_actual_no_borrow_ungrounded_sample_is_planning_unavailable_not_command_admission(self):
        source=HERE.parents[1]/'acceptance/runs/20261027-120917-desktop-match/complete-channel-readonly.json'
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),'d26068a103e25c19b80b46ae6222ea7741f9b5b7a610807faada848dcb9ced8d')
        data=json.loads(source.read_text(encoding='utf-8-sig'))
        h=client.layout.SharedChannel.from_buffer_copy(bytes.fromhex(data['header_before_hex'])+bytes(c.sizeof(client.layout.SharedChannel)-len(bytes.fromhex(data['header_before_hex']))))
        t=client.NativeRuntimeClient.__new__(client.NativeRuntimeClient)
        t.binding=object();t._check=lambda:None;t.shared=h;t.actor_bytes=bytes(h.admitted_actor)
        t._stable=lambda *a:h.current_observation
        self.assertEqual(h.native_last_sequence,0);self.assertFalse(h.current_observation.grounded)
        self.assertFalse(t.observe_planning_actor(t.binding)['grounded'])
        with self.assertRaisesRegex(ValueError,'not_admissible'):t.observe_actor(t.binding)
        h.current_observation.current_thread+=1
        with self.assertRaisesRegex(ValueError,'binding_changed'):t.observe_planning_actor(t.binding)

    def test_planning_actor_is_independent_exact_native_birth_copy(self):
        t=client.NativeRuntimeClient.__new__(client.NativeRuntimeClient)
        actor=client.layout.Actor();actor.object_id=781;actor.generation=1
        t._check=lambda:None;t._actor=object();t.actor_bytes=bytes(actor)
        t.shared=SimpleNamespace(admitted_actor=actor)
        copy=t.planning_actor();self.assertEqual(bytes(copy),t.actor_bytes)
        copy.object_id=782;self.assertEqual(t.shared.admitted_actor.object_id,781)
        actor.generation=2
        with self.assertRaisesRegex(ValueError,'incarnation_changed'):t.planning_actor()

    def test_controlled_fault_constructor_requires_both_owned_recovery_and_separate_mode(self):
        for value in (True,1,'true'):
            with self.assertRaisesRegex(ValueError,'controlled_fault_requires_separate_owned_recovery_experiment'):
                client.NativeRuntimeClient(None,None,None,None,None,controlled_fault_experiment=value)
        with self.assertRaisesRegex(ValueError,'controlled_fault_requires_separate_owned_recovery_experiment'):
            client.NativeRuntimeClient(None,None,None,None,None,diagnostic=True,reconcile_return_experiment=True,yield_abort_experiment=True,controlled_fault_experiment=True)

    def test_ordinary_fault_transport_refuses_before_mapping_or_actor_access(self):
        for diagnostic,fault,recovery in ((False,True,True),(True,False,True),(True,True,False),(1,True,True)):
            t=client.NativeRuntimeClient.__new__(client.NativeRuntimeClient)
            t.diagnostic=diagnostic;t.controlled_fault_experiment=fault;t.reconcile_return_experiment=recovery
            t._check=lambda:(_ for _ in ()).throw(AssertionError('No mapping access'))
            with self.assertRaisesRegex(ValueError,'controlled_fault_requires_separate_owned_recovery_experiment'):
                t.submit(dict(operation='diagnostic_foreign_move'))

    def test_first_home_recovery_constructor_requires_explicit_owned_diagnostic(self):
        for value in (True,1,'true'):
            with self.assertRaisesRegex(ValueError,'recovery_return_requires_explicit_owned_diagnostic'):
                client.NativeRuntimeClient(None,None,None,None,None,reconcile_return_experiment=value)

    def test_ordinary_transport_refuses_new_home_operation_before_mapping_access(self):
        for diagnostic,experiment in ((False,False),(False,True),(True,False),(1,True)):
            transport=client.NativeRuntimeClient.__new__(client.NativeRuntimeClient)
            transport.diagnostic=diagnostic;transport.reconcile_return_experiment=experiment
            transport._check=lambda:(_ for _ in ()).throw(AssertionError('No native mapping access allowed'))
            with self.assertRaisesRegex(ValueError,'recovery_return_requires_explicit_owned_diagnostic'):
                transport.submit(dict(operation='reconcile_return_home'))

    def test_verified_first_home_scope_is_separate_from_basic_move_scope(self):
        from test_host_runtime_tactical_adapter import TacticalAdapterTests
        from host_runtime.capabilities import CapabilityCatalog,VerifiedGrant
        from host_runtime.contracts import canonical_json
        fixture=TacticalAdapterTests();fixture.setUp()
        try:
            t=client.NativeRuntimeClient.__new__(client.NativeRuntimeClient)
            t.binding=fixture.binding;t.executor_sha256='d'*64;t.native_host_sha256='e'*64
            t.diagnostic=False;t.reconcile_return_experiment=False
            t._check=lambda:(_ for _ in ()).throw(RuntimeError('authority passed; mapping not opened in test'))
            t._field_admission(fixture.catalog)
            with self.assertRaisesRegex(ValueError,'capability_unsupported'):t.submit(dict(operation='reconcile_return_home'))
            t.diagnostic=True;t.reconcile_return_experiment=True
            with self.assertRaisesRegex(ValueError,'capability_unsupported'):t.submit(dict(operation='reconcile_return_home'))
            base=fixture.catalog.require('tactics.move_hold_return',fixture.binding)
            scope=dict(base.public()['execution_constraints'],purpose='reconcile_return_home',module='runtime_first_home_recovery_v1',evidence_id='synthetic-first-home')
            grant=VerifiedGrant('tactics.reconcile_return_home','synthetic-first-home','a'*64,'d'*64,'test-only first home',canonical_json(scope))
            catalog=CapabilityCatalog.verify(fixture.binding,[base,grant],lambda candidate,binding:candidate)
            t._field_admission(catalog)
            with self.assertRaisesRegex(RuntimeError,'authority passed'):t.submit(dict(operation='reconcile_return_home'))
            self.assertEqual(t.first_home_field_evidence_id,'synthetic-first-home')
            with self.assertRaisesRegex(ValueError,'controlled_fault_requires_separate_owned_recovery_experiment'):t.submit(dict(operation='diagnostic_foreign_move'))
        finally:fixture.tearDown()

    def test_first_home_scope_cannot_cross_binary_or_native_host(self):
        from test_host_runtime_tactical_adapter import TacticalAdapterTests
        from host_runtime.capabilities import CapabilityCatalog,VerifiedGrant
        from host_runtime.contracts import canonical_json
        fixture=TacticalAdapterTests();fixture.setUp()
        try:
            base=fixture.catalog.require('tactics.move_hold_return',fixture.binding)
            scope=dict(base.public()['execution_constraints'],purpose='reconcile_return_home',module='runtime_first_home_recovery_v1',evidence_id='synthetic-first-home')
            grant=VerifiedGrant('tactics.reconcile_return_home','synthetic-first-home','a'*64,'d'*64,'test-only first home',canonical_json(scope))
            catalog=CapabilityCatalog.verify(fixture.binding,[base,grant],lambda candidate,binding:candidate)
            for executor,native in (('f'*64,'e'*64),('d'*64,'f'*64)):
                t=client.NativeRuntimeClient.__new__(client.NativeRuntimeClient)
                t.binding=fixture.binding;t.executor_sha256=executor;t.native_host_sha256=native;t._field_capabilities=catalog
                t.diagnostic=False;t.reconcile_return_experiment=False
                t._check=lambda:(_ for _ in ()).throw(AssertionError('No mapping access'))
                with self.assertRaisesRegex(ValueError,'runtime_first_home_scope_unverified'):t.submit(dict(operation='reconcile_return_home'))
        finally:fixture.tearDown()

    def test_report_publication_retries_same_fsynced_bytes_only(self):
        with tempfile.TemporaryDirectory() as directory:
            pending=Path(directory)/'report.pending';output=Path(directory)/'report.json'
            pending.write_bytes(b'new immutable capture');output.write_bytes(b'old capture')
            replace=client.os.replace;calls=[]
            def brief_reader_lock(source,target):
                calls.append((source,target,pending.read_bytes(),output.read_bytes()))
                if len(calls)==1:raise PermissionError('reader temporarily denies delete sharing')
                replace(source,target)
            with patch.object(client.os,'replace',side_effect=brief_reader_lock),patch.object(client.time,'sleep') as sleep:
                client._replace_saved_report(pending,output)
            self.assertEqual(len(calls),2)
            self.assertEqual(calls[0],calls[1])
            self.assertEqual(output.read_bytes(),b'new immutable capture')
            self.assertFalse(pending.exists())
            sleep.assert_called_once_with(.02)

    def test_persistent_report_lock_preserves_old_and_pending_then_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            pending=Path(directory)/'report.pending';output=Path(directory)/'report.json'
            pending.write_bytes(b'new capture');output.write_bytes(b'old capture')
            with patch.object(client.os,'replace',side_effect=PermissionError('persistent denial')) as replace,patch.object(client.time,'sleep') as sleep:
                with self.assertRaises(PermissionError):client._replace_saved_report(pending,output)
            self.assertEqual(replace.call_count,25)
            self.assertEqual(sleep.call_count,24)
            self.assertEqual(output.read_bytes(),b'old capture')
            self.assertEqual(pending.read_bytes(),b'new capture')

    def test_actual_x86_helper_inventory_matches_ctypes(self):
        actual = json.loads(subprocess.check_output([str(HERE / 'bin/runtime_host.exe'), '--layout'], text=True, timeout=5))
        self.assertEqual(layout.inventory(), actual)

    def test_uuids_and_hashes_have_unambiguous_byte_encoding(self):
        value = str(uuid.uuid4())
        self.assertEqual(layout.uuid_text(layout.uuid_words(value)), value)
        for bad in ('0'*32, '00000000-0000-0000-0000-000000000000', 'bad'):
            with self.assertRaises(ValueError):layout.uuid_words(bad)
        self.assertEqual(bytes(layout.DIGEST(*layout.digest_words('ab'*32))), bytes.fromhex('ab'*32))
        for bad in ('AB'*32, 'z'*64, 'a'):
            with self.assertRaises(ValueError):layout.digest_words(bad)

    def test_native_structures_have_no_process_sized_pointers(self):
        self.assertEqual(c.sizeof(layout.Actor), 40)
        self.assertEqual(c.sizeof(layout.Point), 12)
        self.assertEqual(c.sizeof(layout.WireReceipt), 216)
        self.assertEqual(layout.SharedChannel.events.offset, 2032)

    def test_yield_experiment_cannot_enter_ordinary_client(self):
        for value in (True, 1, 'true'):
            with self.assertRaisesRegex(ValueError, 'requires_explicit_owned_diagnostic'):
                client.NativeRuntimeClient(None, None, None, None, None, yield_abort_experiment=value)

    def test_actual_target_decoder_passes_real_adapter_commit_contract(self):
        from test_host_runtime_tactical_adapter import TacticalAdapterTests
        fixture = TacticalAdapterTests()
        fixture.setUp()
        try:
            transport = client.NativeRuntimeClient.__new__(client.NativeRuntimeClient)
            transport._check = lambda: None
            transport.shared = client.layout.SharedChannel()
            transport.shared.targets_generation = 2
            transport.shared.targets_count = 1
            transport.shared.approved_targets[0] = client.layout.Point(100, 0, 0)
            points = transport.targets()
            point_id = next(iter(points))
            self.assertEqual(str(uuid.UUID(point_id)), point_id)
            self.assertEqual(transport.targets(), points)
            fixture.transport.point = point_id
            self.assertEqual(fixture.reserve()['status'], 'completed')
            result = fixture.gateway.submit(str(uuid.uuid4()), 'commit', fixture.payload('commit'))
            self.assertEqual(result['status'], 'released')
            self.assertEqual(fixture.transport.calls[-1]['payload']['target_point_id'], point_id)
            self.assertFalse(result['receipt']['facts']['field_evidence_eligible'])
        finally:
            fixture.tearDown()

    def test_actual_wire_rejection_cannot_inherit_ready_or_released_success(self):
        transport = client.NativeRuntimeClient.__new__(client.NativeRuntimeClient)
        transport.binding = SimpleNamespace(binding_hash='a'*64)
        transport.output = Path('offline-test.json')
        transport.shared = client.layout.SharedChannel()
        receipt = client.layout.WireReceipt()
        observation = client.layout.Sample()
        for phase in (4, 12, 13):
            receipt.phase, receipt.accepted = phase, 0
            self.assertEqual(transport._raw_receipt(receipt, observation)['status'], 'rejected')
        receipt.phase, receipt.accepted = 13, 1
        self.assertEqual(transport._raw_receipt(receipt, observation)['status'], 'uncertain')

    def test_private_home_uses_exact_reserve_event_not_current_actor_position(self):
        transport = client.NativeRuntimeClient.__new__(client.NativeRuntimeClient)
        transport._check = lambda:None
        transport.output = Path('offline-test.json')
        transport.shared = client.layout.SharedChannel()
        native_actor = client.layout.Actor(object_id=55, generation=1)
        transport.actor_bytes = bytes(native_actor)
        task, lease = str(uuid.uuid4()), str(uuid.uuid4())
        event = client.layout.WireEvent()
        event.ticket, event.event_type = 1, b'phase'
        event.receipt.task[:] = client.layout.uuid_words(task)
        event.receipt.lease[:] = client.layout.uuid_words(lease)
        event.receipt.accepted, event.receipt.phase, event.receipt.frame = 1, 1, 100
        event.observation.frame = 100
        event.observation.actor = native_actor
        event.observation.identity = event.observation.actor_birth_verified = True
        event.observation.live_list_member = event.observation.grounded = True
        event.observation.xyz = client.layout.Point(12,34,0)
        transport.event_rows = [dict(ticket=1,raw_hex=bytes(event).hex())]
        transport._stable = lambda *args:(_ for _ in ()).throw(AssertionError('Ambient sample is not home'))
        self.assertEqual([12,34,0],transport.reserved_home(task,lease)['xyz'])
        # Exact identity, frame and uniqueness remain required even when the
        # supplied record's free-form projected fields look plausible.
        event.observation.actor.object_id = 56
        transport.event_rows = [dict(ticket=1,raw_hex=bytes(event).hex())]
        with self.assertRaisesRegex(ValueError,'event_unverified'):
            transport.reserved_home(task,lease)
        event.observation.actor.object_id = 55
        transport.event_rows = [dict(ticket=1,raw_hex=bytes(event).hex())]*2
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            transport.reserved_home(task,lease)

    def test_actual_host_atomic_bridge_concurrent_aligned_word_exchange(self):
        client.verify_build()
        transport = client.NativeRuntimeClient.__new__(client.NativeRuntimeClient)
        channel = client.layout.SharedChannel()
        transport.shared, transport.view = channel, c.addressof(channel)
        transport.atomic = c.WinDLL(str(HERE / 'bin/atomic_publish.dll'))
        transport.atomic.runtime_exchange.argtypes = [c.POINTER(c.c_int32), c.c_int32]
        transport.atomic.runtime_exchange.restype = c.c_int32
        rows = [[] for _ in range(8)]
        def exchange(worker):
            for value in range(worker * 1000 + 1, worker * 1000 + 1001):
                rows[worker].append(transport._exchange('command_generation', value))
        threads = [threading.Thread(target=exchange, args=(i,)) for i in range(8)]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        observed = [value for row in rows for value in row] + [channel.command_generation]
        self.assertEqual(sorted(observed), list(range(8001)))
        self.assertEqual(transport._exchange('stop_requested', 1), 0)
        self.assertEqual(channel.stop_requested, 1)
        with self.assertRaisesRegex(ValueError, 'unreviewed'):
            transport._exchange('command_acknowledged', 1)

    def test_native_hook_trace_decoder_retains_raw_and_refuses_overflow(self):
        transport = client.NativeRuntimeClient.__new__(client.NativeRuntimeClient)
        transport._check = transport.save = lambda: None
        transport.binding = SimpleNamespace(binding_hash='a'*64)
        transport.output = Path('offline-test.json')
        transport.shared = client.layout.SharedChannel()
        transport.event_cursor = transport.trace_cursor = 0
        transport.event_rows, transport.trace_rows = [], []
        transport.shared.receipt_generation = transport.shared.observation_generation = 2
        transport.shared.traces_written = 1
        slot = transport.shared.traces[0]
        slot.ticket, slot.trace.kind, slot.trace.caller = 1, 7, 0x838877
        slot.trace.word_count, slot.trace.words[23] = 24, 0xfeed
        transport.poll()
        self.assertEqual(transport.trace_rows, [dict(ticket=1, raw_hex=bytes(slot).hex())])
        transport.shared.traces_overwritten = 1
        with self.assertRaisesRegex(ValueError, 'trace_lost'):
            transport.poll()

    def _released_transport(self, *, include_effect_event):
        transport = client.NativeRuntimeClient.__new__(client.NativeRuntimeClient)
        transport._check = transport.save = lambda: None
        transport.binding = SimpleNamespace(binding_hash='a'*64)
        transport.output = Path('offline-test.json')
        transport.shared = client.layout.SharedChannel()
        transport.event_cursor = transport.trace_cursor = 0
        transport.event_rows, transport.trace_rows = [], []
        transport.shared.receipt_generation = transport.shared.observation_generation = 2
        receipt = transport.shared.receipt
        for name in ('command', 'task', 'lease'):
            getattr(receipt, name)[:] = client.layout.uuid_words(str(uuid.uuid4()))
        receipt.phase, receipt.accepted, receipt.frame, receipt.monotonic_ms = 12, 1, 100, 1000
        receipt.control_released = receipt.stance_restored = receipt.physical_home = 1
        receipt.reason = b'native_control_release_observed'
        # Native AI has already recruited the actor after its verified return.
        transport.shared.current_observation.team = 20
        transport.shared.current_observation.default_team = 10
        transport.shared.current_observation.frame = 101
        transport.shared.bootstrap.binding.thread = 20
        transport.shared.current_observation.binding = transport.shared.bootstrap.binding
        transport.shared.current_observation.current_thread = 20
        transport.shared.current_observation.identity = True
        transport.shared.current_observation.actor_birth_verified = True
        transport.shared.current_observation.live_list_member = True
        transport.shared.current_observation.grounded = True
        transport.actor_bytes = bytes(transport.shared.current_observation.actor)
        if include_effect_event:
            transport.shared.events_written = 1
            event = transport.shared.events[0]
            event.ticket, event.event_type, event.receipt = 1, b'phase', receipt
            event.observation.team = event.observation.default_team = 10
            event.observation.frame = 100
        return transport

    def test_release_uses_its_own_effect_observation_before_native_recruitment(self):
        transport = self._released_transport(include_effect_event=True)
        result = transport.poll()
        self.assertEqual('released', result['status'])
        self.assertEqual(10, result['observation']['team'])
        self.assertEqual(100, result['observation']['frame'])
        self.assertEqual(20, transport.shared.current_observation.team)

    def test_release_without_matching_native_effect_observation_stays_pending(self):
        transport = self._released_transport(include_effect_event=False)
        result = transport.poll()
        self.assertEqual('started', result['status'])
        self.assertEqual('terminal_event_observation_pending', result['reason_code'])

    def test_planning_observes_current_actor_instead_of_prior_release_effect(self):
        transport = self._released_transport(include_effect_event=True)
        self.assertEqual(10, transport.poll()['observation']['team'])
        fresh = transport.observe_actor(transport.binding)
        self.assertEqual(20, fresh['team'])
        self.assertEqual(101, fresh['frame'])
        transport.shared.current_observation.identity = False
        with self.assertRaisesRegex(ValueError, 'not_admissible'):
            transport.observe_actor(transport.binding)


if __name__ == '__main__':
    unittest.main()
