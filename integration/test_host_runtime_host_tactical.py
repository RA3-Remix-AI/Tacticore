"""Actual Host methods -> journal -> single-actor owner; no game/model I/O."""
import asyncio
from dataclasses import replace
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

from host_runtime.capabilities import CapabilityCatalog,VerifiedGrant
from host_runtime.contracts import ContractError,canonical_json
from host_runtime.host_tactical import from_host,renew_from_host,suspend_from_host,resume_from_host
import test_host_runtime_host_production as production_fixtures
import test_host_runtime_tactical_adapter as tactical_fixtures
from test_host_runtime_tactical_adapter import Transport, uid


class HostTacticalCompositionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = production_fixtures.HostProductionTests()
        self.fixture.setUp()
        self.host, self.runtime = self.fixture.host, self.fixture.runtime
        self.host.runtime_tactical = None
        self.host.runtime_tactical_transport = None
        self.host.runtime_tactical_attach_attempted = False
        tactical = tactical_fixtures.TacticalAdapterTests()
        tactical.binding = self.fixture.binding
        grant = tactical.catalog_for()._grants[0]
        self.runtime.evidence = replace(self.runtime.evidence, catalog=CapabilityCatalog.verify(
            self.fixture.binding, [*self.runtime.evidence.catalog._grants, grant], lambda grant,binding:grant))
        self.transport = Transport(self.fixture.binding)
        self.transport.actor = replace(self.transport.actor,identity=replace(self.transport.actor.identity,object_id=801))
        submit = self.transport.submit
        def correlated_submit(wire):
            raw = submit(wire);raw['object_id'] = 801
            return raw
        self.transport.submit = correlated_submit
        self.transport.poll = lambda: self.transport.raw[-1]
        self.transport.closed = False
        self.transport.close = lambda: setattr(self.transport, 'closed', True)
        self.factory = lambda host,request: from_host(host,request,test_transport=self.transport)

    def tearDown(self):self.fixture.tearDown()

    def paid(self):
        asyncio.run(self.host.dispatch())
        self.fixture.executor.mode = 'completed'
        asyncio.run(self.host.receive_receipts())
        self.transport.actor = replace(self.transport.actor,producer_command_id=self.host.sent[self.fixture.task]['command_id'])
        return self.host.sent[self.fixture.task]['request_id']

    def test_actual_host_paid_production_reserve_commit_poll_and_repeat(self):
        self.paid()
        with patch('host_runtime.host_tactical.from_host',side_effect=self.factory):
            first = uid()
            ready = self.host.reserve_runtime_task(first,self.fixture.task)
            self.assertEqual(ready['status'],'completed')
            done = self.host.commit_runtime_task(first,target_point_id=self.transport.point)
            self.assertEqual(done['status'],'released')
            self.assertTrue(done['receipt']['facts']['mission_effect_verified'])
            self.assertFalse(done['receipt']['facts']['field_evidence_eligible'])
            asyncio.run(self.host.receive_runtime_tactical())
            second = uid()
            self.assertEqual(self.host.reserve_runtime_task(second,self.fixture.task)['status'],'completed')
            self.assertEqual(self.host.commit_runtime_task(second,target_point_id=self.transport.point)['status'],'released')
        self.assertEqual([row['operation'] for row in self.transport.calls],['reserve','commit','reserve','commit'])
        self.assertEqual(len({row['command_id'] for row in self.transport.calls}),4)
        self.assertEqual(self.runtime.journal.unresolved(self.runtime.run_id),[])
        asyncio.run(self.host.stop_runtime_tactical())
        self.assertTrue(self.transport.closed)
        self.assertEqual(self.host.runtime_tactical.snapshot()['tasks'][0]['control']['state'],'released')

    def test_unpaid_or_unverified_runtime_never_attaches(self):
        asyncio.run(self.host.dispatch())
        request = self.host.sent[self.fixture.task]['request_id']
        with self.assertRaisesRegex(ContractError,'runtime_completed_conscript_required'):
            from_host(self.host,request,test_transport=self.transport)
        self.paid()
        with self.assertRaisesRegex(ContractError,'runtime_field_evidence_required'):
            from_host(self.host,request)
        self.assertEqual(self.transport.calls,[])

    def test_unknown_attach_is_not_recreated_and_paused_tasks_refuse(self):
        self.paid()
        with patch('host_runtime.host_tactical.from_host',side_effect=TimeoutError()) as factory:
            with self.assertRaises(TimeoutError):self.host.reserve_runtime_task(uid(),self.fixture.task)
            with self.assertRaisesRegex(ContractError,'explicit_recovery'):self.host.reserve_runtime_task(uid(),self.fixture.task)
            self.assertEqual(factory.call_count,1)
        self.host.last_snapshot['paused'] = True
        with self.assertRaisesRegex(ContractError,'runtime_tactical_not_ready'):
            self.host.reserve_runtime_task(uid(),self.fixture.task)

    def test_unknown_send_remains_unknown_on_poll_and_cleanup(self):
        self.paid(); self.transport.mode = 'error'
        with patch('host_runtime.host_tactical.from_host',side_effect=self.factory):
            result = self.host.reserve_runtime_task(uid(),self.fixture.task)
        self.assertEqual(result['status'],'uncertain')
        # Polling unknown evidence does not retry or reconcile it.
        self.transport.poll = lambda: dict(command_id=result['command_id'])
        with self.assertRaisesRegex(ContractError,'requires_reconciliation'):
            asyncio.run(self.host.receive_runtime_tactical())
        with self.assertRaisesRegex(ContractError,'requires_reconciliation'):
            asyncio.run(self.host.stop_runtime_tactical())
        self.assertTrue(self.transport.closed)
        self.assertEqual(len(self.transport.calls),1)
        self.assertEqual(self.runtime.journal.get_command(self.runtime.run_id,result['request_id'])['status'],'uncertain')

    def completed_owner(self):
        self.paid();task=uid()
        with patch('host_runtime.host_tactical.from_host',side_effect=self.factory):
            self.host.reserve_runtime_task(task,self.fixture.task)
        self.host.commit_runtime_task(task,target_point_id=self.transport.point)
        self.host.session={'run_directory':str(self.fixture.root)}
        self.host.args.session=self.fixture.root/'session.json'
        return task

    def test_actual_host_lifecycle_entry_rebinds_only_after_release_keeps_old_task_revoked(self):
        old_task=self.completed_owner();previous=self.host.runtime_tactical
        binding=replace(self.fixture.binding,host_id=uid());next_transport=Transport(binding)
        next_transport.actor=replace(self.transport.actor)
        submit=next_transport.submit
        def correlated(wire):
            raw=submit(wire);raw['object_id']=801
            return raw
        next_transport.submit=correlated;next_transport.poll=lambda:next_transport.raw[-1]
        next_transport.close=lambda:None
        def retired(owner,**paths):
            owner.shutdown()
            return SimpleNamespace(binding=binding,run_id=uid(),manifest_sha256='f'*64)
        with patch('host_runtime.runtime_rotation.retire_channel',side_effect=retired),\
                patch('host_runtime.host_tactical.renew_from_host',side_effect=lambda host:renew_from_host(host,test_transport=next_transport)):
            status=self.host.renew_runtime_tactical()
        self.assertTrue(self.transport.closed)
        self.assertNotEqual(previous.binding.binding_hash,status['binding_hash'])
        self.assertFalse(self.host.runtime_tactical_rotation_attempted)
        self.assertEqual(len(self.host.runtime_tactical_epochs),1)
        with self.assertRaisesRegex(ContractError,'unknown_tactical_task'):
            self.host.commit_runtime_task(old_task,target_point_id=next_transport.point)
        second=uid();self.host.reserve_runtime_task(second,self.fixture.task)
        done=self.host.commit_runtime_task(second,target_point_id=next_transport.point)
        self.assertEqual(done['status'],'released');self.assertFalse(done['receipt']['facts']['field_evidence_eligible'])
        sequences=[row['seq'] for row in self.transport.calls+next_transport.calls]
        self.assertEqual(sequences,list(range(sequences[0],sequences[0]+4)))

    def test_failed_renewal_never_restarts_and_stop_closes_old_and_pending_transports(self):
        self.completed_owner();pending=SimpleNamespace(closed=False)
        pending.close=lambda:setattr(pending,'closed',True)
        def failed(owner,**paths):
            self.host.runtime_tactical_transport=pending
            raise TimeoutError('synthetic successor attach unknown')
        with patch('host_runtime.runtime_rotation.retire_channel',side_effect=failed),\
                patch('host_runtime.host_tactical.renew_from_host',side_effect=lambda host:renew_from_host(host,test_transport=self.transport)):
            with self.assertRaises(TimeoutError):self.host.renew_runtime_tactical()
        self.assertTrue(self.host.runtime_tactical_rotation_attempted)
        with self.assertRaisesRegex(ContractError,'explicit_recovery'):
            self.host.reserve_runtime_task(uid(),self.fixture.task)
        asyncio.run(self.host.stop_runtime_tactical())
        self.assertTrue(pending.closed);self.assertTrue(self.transport.closed)
        self.assertEqual(len(self.transport.calls),2)

    def first_home_handoff_fixture(self):
        self.completed_owner();previous=self.host.runtime_tactical
        self.host.runtime_tactical_rotation_attempted=False
        base=previous.adapter.catalog.require('tactics.move_hold_return',previous.binding)
        scope=dict(base.public()['execution_constraints'],purpose='reconcile_return_home',module='runtime_first_home_recovery_v1',evidence_id='test-first-home')
        recovery=VerifiedGrant('tactics.reconcile_return_home','test-first-home','c'*64,base.executor_sha256,'synthetic wiring only',canonical_json(scope))
        def catalog(binding):return CapabilityCatalog.verify(binding,[base,recovery],lambda grant,current:grant)
        previous.adapter.catalog=catalog(previous.binding)
        # This test patches the raw verifier and native factory explicitly; it
        # exercises order/bindings only and cannot supply field evidence.
        previous.adapter.test_only=False;self.runtime.evidence=replace(self.runtime.evidence,test_only=False)
        source=self.fixture.root/'baseline.json';source.write_text('{}')
        proof=self.fixture.root/'recovery.json';proof.write_text('{}')
        self.host.args.runtime_report=source;self.host.args.runtime_sha256='a'*64
        self.host.args.runtime_recovery_report=proof;self.host.args.runtime_recovery_sha256='b'*64
        binding=replace(previous.binding,host_id=uid());handoff=SimpleNamespace(binding=binding,run_id=uid(),manifest_sha256='f'*64)
        return previous,catalog,handoff

    def test_recovery_handoff_verifies_before_retire_and_again_for_new_binding_before_attach(self):
        previous,catalog,handoff=self.first_home_handoff_fixture();steps=[];seen=[]
        def verify(binding,*args,**kwargs):steps.append(('verify',binding.binding_hash));return catalog(binding)
        def retired(owner,**kwargs):steps.append(('retire',owner.binding.binding_hash));owner.shutdown();return handoff
        def client(*args,**kwargs):
            def attach(*,capabilities):
                steps.append(('attach',capabilities.binding_hash));seen.append(capabilities);return previous.actor
            return SimpleNamespace(attach=attach)
        def owner(journal,run_id,binding,catalog,**kwargs):return SimpleNamespace(binding=binding,catalog=catalog,run_id=run_id)
        with patch('host_runtime.host_tactical._handoff_catalog',side_effect=verify),patch('host_runtime.runtime_rotation.retire_channel',side_effect=retired),\
                patch('tactical_bridge.module',return_value=SimpleNamespace(NativeRuntimeClient=client)),patch('host_runtime.host_tactical.HostTactical',side_effect=owner):
            successor=renew_from_host(self.host)
        self.assertEqual(steps,[('verify',previous.binding.binding_hash),('retire',previous.binding.binding_hash),('verify',handoff.binding.binding_hash),('attach',handoff.binding.binding_hash)])
        self.assertEqual(successor.catalog.require('tactics.reconcile_return_home',handoff.binding).evidence_id,'test-first-home')
        with self.assertRaisesRegex(ContractError,'binding_mismatch'):seen[0].require('tactics.reconcile_return_home',previous.binding)
        self.assertTrue(self.transport.closed)
        evidence=[e for run in (previous.run_id,handoff.run_id)for e in self.runtime.journal.events(run)if e['event_type']=='tactical_handoff_scope_reverified']
        self.assertEqual([e['payload']['phase']for e in evidence],['before_retire','before_successor_attach'])

    def test_invalid_recovery_scope_before_retirement_leaves_old_owner_open(self):
        self.first_home_handoff_fixture()
        with patch('host_runtime.host_tactical._handoff_catalog',side_effect=ContractError('synthetic_changed_pin')),patch('host_runtime.runtime_rotation.retire_channel')as retire:
            with self.assertRaisesRegex(ContractError,'synthetic_changed_pin'):renew_from_host(self.host)
            retire.assert_not_called()
        self.assertFalse(self.transport.closed);self.assertFalse(self.host.runtime_tactical_rotation_attempted)

    def suspend_fixture(self):
        previous,catalog,handoff=self.first_home_handoff_fixture()
        retired=SimpleNamespace(run_id=previous.run_id,manifest_sha256='f'*64,supervisor=None)
        def close(owner,**kwargs):owner.shutdown();return retired
        with patch('host_runtime.host_tactical._handoff_catalog',side_effect=lambda binding,*a,**kw:catalog(binding)),\
                patch('host_runtime.runtime_rotation.retire_for_later',side_effect=close),patch('tactical_bridge.module')as native:
            self.assertIs(suspend_from_host(self.host),retired);native.assert_not_called()
        return previous,catalog,handoff,retired

    def test_deferred_close_does_not_attach_and_later_reverifies_new_binding(self):
        previous,catalog,handoff,retired=self.suspend_fixture();steps=[]
        paid=self.host.sent[self.fixture.task]['request_id']
        def qualify(binding,*a,**kw):steps.append(('verify',binding.binding_hash));return catalog(binding)
        def authorize(*a,**kw):steps.append(('authorize',kw['producer_command_id']));return handoff
        successor=SimpleNamespace(run_id=handoff.run_id)
        with patch('host_runtime.host_tactical._handoff_catalog',side_effect=qualify),\
                patch('host_runtime.runtime_rotation.authorize_deferred_successor',side_effect=authorize),\
                patch('host_runtime.host_tactical._attach_successor',return_value=successor)as attach:
            self.assertIs(resume_from_host(self.host,production_request_id=paid),successor)
        self.assertEqual([s[0]for s in steps],['verify','authorize','verify'])
        self.assertIsNone(self.host.runtime_tactical_retirement)
        self.assertEqual(attach.call_args.args[3].binding,handoff.binding)
        self.assertTrue(self.transport.closed)

    def test_failed_late_requalification_keeps_closed_channel_and_forbids_second_attach_attempt(self):
        previous,catalog,handoff,retired=self.suspend_fixture();paid=self.host.sent[self.fixture.task]['request_id']
        with patch('host_runtime.host_tactical._handoff_catalog',side_effect=[catalog(previous.binding),ContractError('synthetic_scope_changed')]),\
                patch('host_runtime.runtime_rotation.authorize_deferred_successor',return_value=handoff),\
                patch('host_runtime.host_tactical._attach_successor')as attach:
            with self.assertRaisesRegex(ContractError,'scope_changed'):resume_from_host(self.host,production_request_id=paid)
            with self.assertRaisesRegex(ContractError,'explicit_recovery'):resume_from_host(self.host,production_request_id=paid)
            attach.assert_not_called()
        self.assertIs(self.host.runtime_tactical_retirement,retired)

    def test_host_receive_while_deferred_never_polls_closed_transport(self):
        self.suspend_fixture()
        with patch.object(self.host.runtime_tactical,'poll',side_effect=AssertionError('Closed native IO must stay closed')):
            asyncio.run(self.host.receive_runtime_tactical())

    def test_deferred_older_paid_actor_refused_before_authorizing_or_attaching(self):
        previous,catalog,handoff,retired=self.suspend_fixture()
        older=self.host.sent[self.fixture.task]['request_id'];request=uid()
        row=self.runtime.journal.reserve_command(self.runtime.run_id,request,'produce',dict(unit='conscript'))
        self.runtime.journal.mark_dispatching(self.runtime.run_id,request)
        self.runtime.journal.reserve_native_sequence(self.runtime.run_id,row['command_id'],0)
        self.runtime.journal.record_outcome(self.runtime.run_id,request,'completed',dict(facts=dict(object_id=802,paid=85)))
        previous.producer_command_id=row['command_id']
        with patch('host_runtime.runtime_rotation.authorize_deferred_successor')as authorize,\
                patch('host_runtime.host_tactical._attach_successor')as attach:
            with self.assertRaisesRegex(ContractError,'requires_later_paid_producer'):
                resume_from_host(self.host,production_request_id=older)
            authorize.assert_not_called();attach.assert_not_called()
        self.assertFalse(self.host.runtime_tactical_resume_attempted)
        self.assertIs(self.host.runtime_tactical_retirement,retired)

    def test_changed_scope_after_retire_never_attaches_or_restarts_successor(self):
        previous,catalog,handoff=self.first_home_handoff_fixture()
        def retired(owner,**kwargs):owner.shutdown();return handoff
        with patch('host_runtime.host_tactical._handoff_catalog',side_effect=[catalog(previous.binding),ContractError('synthetic_changed_after_retire')]),\
                patch('host_runtime.runtime_rotation.retire_channel',side_effect=retired),patch('tactical_bridge.module')as native:
            with self.assertRaisesRegex(ContractError,'synthetic_changed_after_retire'):renew_from_host(self.host)
            native.assert_not_called()
        self.assertTrue(self.transport.closed);self.assertTrue(self.host.runtime_tactical_rotation_attempted)
        with self.assertRaisesRegex(ContractError,'explicit_recovery'):renew_from_host(self.host)

    def test_missing_recovery_pin_cannot_silently_downgrade_handoff(self):
        self.first_home_handoff_fixture();self.host.args.runtime_recovery_report=None;self.host.args.runtime_recovery_sha256=None
        with patch('host_runtime.runtime_rotation.retire_channel')as retire:
            with self.assertRaisesRegex(ContractError,'first_home_handoff_pin_required'):renew_from_host(self.host)
            retire.assert_not_called()
        self.assertFalse(self.transport.closed)

    def test_host_renewal_selects_only_the_explicit_completed_new_paid_actor(self):
        old_task=self.completed_owner();request=uid()
        row=self.runtime.journal.reserve_command(self.runtime.run_id,request,'produce',dict(unit='conscript'))
        self.runtime.journal.mark_dispatching(self.runtime.run_id,request)
        self.runtime.journal.record_outcome(self.runtime.run_id,request,'completed',dict(facts=dict(object_id=802,paid=85)))
        binding=replace(self.fixture.binding,host_id=uid());transport=Transport(binding)
        transport.actor=replace(transport.actor,producer_command_id=row['command_id'],identity=replace(transport.actor.identity,object_id=802))
        transport.close=lambda:None
        transport.poll=lambda:transport.raw[-1]
        selected=[]
        def retired(owner,**paths):
            selected.append(paths['successor_producer_command_id']);owner.shutdown()
            return SimpleNamespace(binding=binding,run_id=uid(),manifest_sha256='f'*64)
        with patch('host_runtime.runtime_rotation.retire_channel',side_effect=retired),\
                patch('host_runtime.host_tactical.renew_from_host',side_effect=lambda host,**kwargs:renew_from_host(host,test_transport=transport,**kwargs)):
            self.host.renew_runtime_tactical(production_request_id=request)
        self.assertEqual(selected,[row['command_id']])
        self.assertEqual(self.host.runtime_tactical.producer_command_id,row['command_id'])
        self.assertEqual(self.host.runtime_tactical.actor.identity.object_id,802)
        self.assertTrue(self.host.runtime_tactical.adapter.test_only)
        with self.assertRaisesRegex(ContractError,'unknown_tactical_task'):
            self.host.runtime_tactical.commit(old_task,target_point_id=transport.point,hold_frames=15)

    def test_new_actor_selection_of_wrong_unit_leaves_the_previous_owner_open(self):
        self.completed_owner();request=uid()
        self.runtime.journal.reserve_command(self.runtime.run_id,request,'produce',dict(unit='flak'))
        self.runtime.journal.mark_dispatching(self.runtime.run_id,request)
        self.runtime.journal.record_outcome(self.runtime.run_id,request,'completed',dict(facts=dict(object_id=802)))
        with patch('host_runtime.runtime_rotation.retire_channel') as retire:
            with self.assertRaisesRegex(ContractError,'completed_conscript_required'):
                renew_from_host(self.host,test_transport=self.transport,production_request_id=request)
            retire.assert_not_called()
        self.assertFalse(self.transport.closed)

    def test_client_stop_state_refuses_new_native_borrow_or_renewal(self):
        self.paid();self.host.phase='stopping'
        with self.assertRaisesRegex(ContractError,'not_ready'):self.host.reserve_runtime_task(uid(),self.fixture.task)
        with self.assertRaisesRegex(ContractError,'not_ready'):self.host.renew_runtime_tactical()
        self.assertEqual(self.transport.calls,[])

    def test_macro_host_refuses_runtime_report_with_or_without_legacy_pins(self):
        from battle_host import Host, parser
        path = self.fixture.root/'empty-session.json'; path.write_text('{}')
        for flags in (['--runtime-report','proof.json'], ['--runtime-sha256','a'*64],
                      ['--runtime-report','proof.json','--runtime-sha256','a'*64]):
            args=parser().parse_args(['--session',str(path),'--commander',uid(),*flags])
            with patch('battle_host.load_profile',side_effect=AssertionError('credentials must remain untouched')):
                with self.assertRaisesRegex(ContractError,'macro_mode_rejects_unit_control_evidence'):Host(args)


class NativeFieldAdmissionTests(unittest.TestCase):
    def test_original_client_field_gate_checks_binding_and_exact_movement_scope(self):
        # Import definitions only. No constructor/Win32/attach/SDK is executed.
        path=Path(__file__).resolve().parents[1]/'tactical/runtime/client.py'
        spec=importlib.util.spec_from_file_location('test_original_tactical_client',path)
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        fixture=tactical_fixtures.TacticalAdapterTests()
        from host_runtime.contracts import SessionBinding
        fixture.binding=SessionBinding(1,uid(),3,uid(),1234,'2026-10-26T00:00:00+00:00',uid(),'a'*64,'b'*64)
        native=module.NativeRuntimeClient.__new__(module.NativeRuntimeClient)
        native.binding=fixture.binding;native.executor_sha256='d'*64;native.native_host_sha256='e'*64
        with self.assertRaisesRegex(ValueError,'capability_required'):native._field_admission(None)
        for changes in (dict(execution_ready=False),dict(actor_roles=['infantry','anti_air']),
                        dict(purpose='main_attack'),dict(executor_directory='tactical/mission-formation-v18'),
                        dict(native_host_sha256='f'*64)):
            with self.assertRaisesRegex(ValueError,'scope_unverified'):native._field_admission(fixture.catalog_for(**changes))
        native._field_admission(fixture.catalog_for())
        self.assertEqual(native.field_evidence_id,'test-proof')
        self.assertNotIn('tactics.attack',[g.capability_id for g in fixture.catalog_for()._grants])


if __name__=='__main__':unittest.main()
