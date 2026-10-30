"""Actual Host adapters over the offline raw transport/journal V4 fixture."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import macro_host
from macro_host import MacroHost
from host_runtime.macro_expansion_runtime import MacroExpansionController
from host_runtime.macro_expansion_runtime_v4 import MacroExpansionControllerV4
from host_runtime.macro_admission_feedback_v4 import compact_admission_feedback_v4
import test_macro_expansion_runtime_v4 as expansion_fixture


class HostAdmissionV4Tests(unittest.TestCase):
    def setUp(self):
        self.f=expansion_fixture.ExpansionV4Tests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        f=self.f;host=MacroHost.__new__(MacroHost);self.host=host
        host.sampler=SimpleNamespace(scope=f.scope);host.transport=f.raw
        # Controller V4 still uses the qualified Native protocol-2 transport.
        host.transport_config=dict(protocol_version=f.scope.native_transport_protocol)
        host.journal=f.journal;host.run_id=f.run;host.expected_hash='e'*64
        host.binding=f.binding;host.session=dict(process_creation_filetime=f.session.process_creation_filetime)
        host.output=f.directory/'battle-host';host.output.mkdir();host.event=Mock()
        host.host_pid=999;host.host_start='offline';host.controller=None
        host.latest=dict(game_time_seconds=f.frame/15);host.strategy_runtime=None

    def test_verified_session_selects_v4_even_when_price_is_disabled(self):
        f=self.f;self.host.cost_boot=SimpleNamespace(session=f.session,cost_supplier=None,financial_supplier=None)
        fake_publisher=SimpleNamespace(create_raw_admission_publisher_v4=lambda *args:SimpleNamespace(apply=f.artificial_guarded_apply))
        with patch.dict(sys.modules,{'read_script_flags':SimpleNamespace(inspect_flags=lambda *args:f.port.flags_reader()),
                'host_runtime.raw_admission_publisher_v4':fake_publisher}):
            controller=self.host.create_controller()
        self.host.controller=controller
        self.assertIs(type(controller),MacroExpansionControllerV4)
        self.assertIs(controller.port.transport.delegate.transport,f.raw)
        self.assertTrue((self.host.output/'active-preference-buffers-v4.json').exists())
        self.assertFalse((self.host.output/'resource-reservations.json').exists())
        self.assertNotIn('producesickle',controller.available_actions(100.))
        self.assertIn('budgetarmy',controller.available_actions(100.))
        self.assertEqual(f.raw.calls,[])

    def test_unverified_boot_keeps_legacy_thirteen_and_new_preferences_disabled(self):
        self.host.cost_boot=SimpleNamespace(session=None,cost_supplier=None,financial_supplier=None)
        controller=self.host.create_controller()
        self.assertIs(type(controller),MacroExpansionController)
        self.assertIsNone(controller.cost_supplier)
        self.assertTrue((self.host.output/'resource-reservations.json').exists())
        self.assertFalse((self.host.output/'active-preference-buffers-v4.json').exists())

    def test_pre_attach_publication_selector_binds_current_sources_and_exact_session(self):
        from host_runtime import raw_admission_publisher_v4 as publisher
        f=self.f;self.host.cost_boot=SimpleNamespace(session=f.session)
        # This unit checks identity/hash binding, not Native build qualification.
        # Keep its manifest synthetic instead of requiring a local build output.
        build=self.host.output/'synthetic-native-build';build.mkdir()
        manifest=build/'build-manifest.json'
        manifest.write_text('{"offline_fixture":true}',encoding='utf8')
        self.host.sampler.bundle=dict(build=str(build))
        source=self.host.output/'sources.json';source.write_text('{"offline_fixture":true}',encoding='utf8')
        self.host.freeze_publication_contract()
        path=self.host.output/'publication-v4-contract.json'
        marker=json.loads(path.read_text(encoding='utf8'))
        self.assertEqual(marker['kind'],'guarded_admission_publication_contract_v4')
        self.assertEqual(marker['session']['session_id'],f.session.session_id)
        self.assertEqual(marker['session']['process_creation_filetime'],f.session.process_creation_filetime)
        self.assertEqual(marker['binding_hash'],f.binding.binding_hash)
        self.assertEqual(marker['pre_execution_sources_sha256'],macro_host.digest(source))
        self.assertEqual(marker['publisher_source_sha256'],publisher.SOURCE_SHA)
        self.assertEqual(marker['native_build_manifest_sha256'],macro_host.digest(manifest))
        self.assertFalse(marker['native_constructor_started'])
        self.assertTrue(self.host.publication_v4_selected)
        self.host.event.assert_called_once_with('macro_admission_publication_contract_frozen',
            contract_sha256=macro_host.digest(path),publisher_source_sha256=publisher.SOURCE_SHA,native_constructor_started=False)

    def _assert_final_stop_keeps_pending_ledger_and_proves_release(self):
        f=self.f;f.dispatch();self.host.controller=f.controller
        target=f.directory/'reports'/('macro-desktop-'+f.run);target.mkdir(parents=True)
        final=dict(session_id=f.session.session_id,pid=f.session.pid,
            process_creation_filetime=f.session.process_creation_filetime,mod_sha256=f.session.package_sha256,
            cleanup_verified=True,host_returncode=0,unknown_command_ids=[],
            native=dict(phase=2,error=0,active=0,applied_mask=0,cleanup_verified=1,self_hook_installed=0,lease_held=0,last_frame=f.frame+2),
            independent_flags=dict(flags=[dict(name=flag,present=True,value=False) for flag in f.raw.manifest['flags']]))
        (target/'final-state.json').write_text(json.dumps(final),encoding='utf8')
        # Any financial read while macro-stop is dispatching would violate the
        # complete ledger gate. Final native release must not claim it closed.
        f.controller.financial_supplier=Mock(side_effect=AssertionError('final stop must not reconcile'))
        with patch.object(macro_host,'ROOT',f.directory):self.host.finish_transport()
        self.assertTrue(f.raw.closed)
        f.controller.financial_supplier.assert_not_called()
        self.assertEqual(f.journal.get_command(f.run,'macro-stop')['status'],'released')
        public=f.controller.resource_feedback()
        self.assertEqual(public['status'],'preference_cleared');self.assertEqual(public['active_buffer_amount'],850)
        self.assertFalse(public['current_state_reconciliation_verified'])
        self.assertEqual(self.host.last_resource_feedback,compact_admission_feedback_v4(public))
        self.assertTrue(json.loads((self.host.output/'macro-release.json').read_text())['native_release_verified'])
        self.assertEqual(len(f.raw.calls),2)

    def test_actual_host_final_stop_keeps_pending_ledger_and_still_proves_native_release(self):
        contract=self.host.output/'publication-v4-contract.json';contract.write_text('{"offline_selector":true}',encoding='utf8')
        def review(directory,**unused):
            path=self.host.output/'publication-v4-release-review.json';path.write_text('{"offline_review":true}',encoding='utf8')
            final=json.loads((directory/'final-state.json').read_text(encoding='utf8'))
            return path,macro_host.digest(path),(None,final,None,[],{})
        with patch('host_runtime.macro_release_review_v4.write_release_review_v4',side_effect=review):
            self._assert_final_stop_keeps_pending_ledger_and_proves_release()

    def test_host_tick_keeps_schema4_feedback_after_known_queue_clear_and_reconciliation(self):
        from host_runtime.test_macro_expansion_feedback import sample
        from host_runtime.resource_admission_reservations_v4 import CLOSED
        f=self.f;f.dispatch();self.host.controller=f.controller
        f.frame+=1;f.raw.state['last_frame']=f.frame
        self.host.latest=dict(game_time_seconds=f.frame/15,battlefield={})
        self.assertTrue(self.host.production_tick(sample('producesickle',f.frame,queues=[(18,17)])))
        self.assertEqual(self.host.last_resource_feedback['schema_version'],4)
        self.assertEqual(self.host.last_resource_feedback['status'],CLOSED)
        self.assertFalse(self.host.last_resource_feedback['dispatch_authorized'])
        self.assertIn('latent_work_cancelled',self.host.last_resource_feedback['unverified_outcomes'])
        self.assertEqual(f.controller.resource_feedback()['active_buffer_amount'],0)

    def test_dispatch_and_deferred_pair_publish_current_held_store_instead_of_old_closed_cache(self):
        from host_runtime.test_macro_expansion_feedback import sample
        from host_runtime.macro_admission_feedback_v4 import MacroRequestAuditV4
        f=self.f;f.dispatch();f.queue_and_tick();self.host.controller=f.controller
        old=self.host.compact_resource_feedback(f.controller.resource_feedback())
        self.assertEqual(old['status'],'closed_after_current_state_reconciliation')
        self.host.last_resource_feedback=old
        f.plan.plan_id='next-after-closed';f.plan.snapshot_id=2
        f.plan.public=lambda:dict(plan_id=f.plan.plan_id,macro_actions=list(f.plan.macro_actions))
        f.controller.refresh(sample('producesickle',f.frame))
        self.host.latest=dict(snapshot_id=2,game_time_seconds=f.frame/15,paused=False,resources={'credits':f.cash})
        self.assertTrue(self.host.dispatch_plan(f.plan))
        self.assertEqual(self.host.last_resource_feedback['status'],'acknowledged')
        self.assertEqual(self.host.last_resource_feedback['active_buffer_amount'],850)
        # Simulate a stale cache left by an earlier optional/native sample.
        # Publishing must obtain the current durable store even when the
        # following native builder pair cannot be consumed at all.
        self.host.last_resource_feedback=old
        bad=sample('producesickle',f.frame);bad['build_observation']['frame']=f.frame+31
        f.raw.native_status=Mock(side_effect=AssertionError('pure store refresh must not read native'))
        f.raw.memory.u32=Mock(side_effect=AssertionError('pure store refresh must not RPM'))
        f.raw.memory.read=Mock(side_effect=AssertionError('pure store refresh must not RPM'))
        self.assertFalse(self.host.production_tick(bad))
        self.host.session.update(pid=f.session.pid,start_time=f.binding.game_process_start)
        self.host.phase='sampling_wait';self.host.reason='macro_native_pair_pending'
        self.host.agent=None;self.host.application=None;self.host.backend=None
        self.host.publish()
        published=json.loads((self.host.output/'host-status.json').read_text(encoding='utf8'))
        current=published['macro_resource_feedback']
        self.assertEqual(current['status'],'acknowledged');self.assertEqual(current['active_buffer_amount'],850)
        self.assertIsNone(current['reconciled_frames']);self.assertIsNone(current['reconciled_credits'])
        audit=MacroRequestAuditV4(None,Mock(),resource_supplier=self.host.current_resource_feedback)
        supplied=audit._expansion_context({'game_time_seconds':f.frame/15})['macro_resource_feedback']
        self.assertEqual(supplied,current)
        f.raw.native_status.assert_not_called();f.raw.memory.u32.assert_not_called();f.raw.memory.read.assert_not_called()

    def test_known_before_native_expiry_refreshes_aborted_row_instead_of_previous_closed(self):
        from host_runtime.test_macro_expansion_feedback import sample
        f=self.f;f.dispatch();f.queue_and_tick();self.host.controller=f.controller
        self.host.last_resource_feedback=self.host.compact_resource_feedback(f.controller.resource_feedback())
        f.plan.plan_id='expires-while-preparing';f.plan.expires_at_game_seconds=f.frame/15+5
        f.controller.refresh(sample('producesickle',f.frame))
        self.host.latest=dict(paused=False,game_time_seconds=f.frame/15)
        def event(kind,**unused):
            if kind=='model_macro_expansion_prepared':f.frame+=100;f.raw.state['last_frame']=f.frame
        f.controller.event=event
        self.assertFalse(self.host.dispatch_plan(f.plan))
        self.assertEqual(len(f.raw.calls),2)
        self.assertEqual(self.host.last_resource_feedback['status'],'aborted_before_delivery')
        self.assertEqual(self.host.last_resource_feedback['active_buffer_amount'],0)
        self.assertIsNone(self.host.last_resource_feedback['reconciled_frames'])

    def test_marked_host_release_requires_and_binds_new_independent_review(self):
        contract=self.host.output/'publication-v4-contract.json';contract.write_text('{"offline_selector":true}',encoding='utf8')
        def review(directory,**kwargs):
            self.assertEqual(kwargs,dict(contract_path=contract,expected=self.f.raw.manifest,
                expected_binding=self.f.binding,expected_run_id=self.f.run))
            path=self.host.output/'publication-v4-release-review.json';path.write_text('{"offline_review":true}',encoding='utf8')
            final=json.loads((directory/'final-state.json').read_text(encoding='utf8'))
            return path,macro_host.digest(path),(None,final,None,[],{})
        with patch('host_runtime.macro_release_review_v4.write_release_review_v4',side_effect=review) as verifier:
            self._assert_final_stop_keeps_pending_ledger_and_proves_release()
        verifier.assert_called_once()
        proof=json.loads((self.host.output/'macro-release.json').read_text(encoding='utf8'))
        receipt=self.f.journal.get_command(self.f.run,'macro-stop')['receipt']
        for value in (proof,receipt):
            self.assertEqual(value['native_release_contract'],'guarded_admission_publication_contract_v4')
            self.assertEqual(value['publication_v4_contract_sha256'],macro_host.digest(contract))
            self.assertEqual(value['publication_v4_release_review_sha256'],macro_host.digest(self.host.output/'publication-v4-release-review.json'))

    def test_marked_release_review_failure_retains_uncertain_stop(self):
        from host_runtime.contracts import ContractError
        (self.host.output/'publication-v4-contract.json').write_text('{"offline_selector":true}',encoding='utf8')
        with patch('host_runtime.macro_release_review_v4.write_release_review_v4',side_effect=ContractError('macro_release_v4_unverified')):
            with self.assertRaisesRegex(ContractError,'macro_release_v4_unverified'):
                self._assert_final_stop_keeps_pending_ledger_and_proves_release()
        self.assertTrue(self.f.raw.closed)
        self.assertEqual(self.f.journal.get_command(self.f.run,'macro-stop')['status'],'uncertain')
        self.assertFalse((self.host.output/'macro-release.json').exists())

    def test_missing_v4_selector_cannot_downgrade_to_legacy_release(self):
        from host_runtime.contracts import ContractError
        with self.assertRaisesRegex(ContractError,'macro_release_v4_contract_missing'):
            self._assert_final_stop_keeps_pending_ledger_and_proves_release()
        self.assertTrue(self.f.raw.closed)
        self.assertEqual(self.f.journal.get_command(self.f.run,'macro-stop')['status'],'uncertain')
        self.assertFalse((self.host.output/'macro-release.json').exists())

    def test_explicit_before_native_refusal_does_not_fault_host_but_unknown_still_propagates(self):
        from host_runtime.contracts import ContractError
        self.host.latest=dict(paused=False,game_time_seconds=100)
        self.host.controller=Mock();plan=Mock(expires_at_game_seconds=110,plan_id='plan')
        self.host.controller.dispatch.side_effect=ContractError('macro_admission_v4_refused_before_native')
        self.assertFalse(self.host.dispatch_plan(plan))
        self.host.controller.dispatch.side_effect=ContractError('macro_dispatch_outcome_unknown')
        with self.assertRaisesRegex(ContractError,'macro_dispatch_outcome_unknown'):self.host.dispatch_plan(plan)


if __name__=='__main__':unittest.main()
