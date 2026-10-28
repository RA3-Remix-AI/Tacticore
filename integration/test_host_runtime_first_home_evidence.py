"""Offline mutations of immutable field packets. Never opens a game mapping."""
import copy,hashlib,json,tempfile,unittest,uuid
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from host_runtime import runtime_first_home_evidence as r
from host_runtime.contracts import SessionBinding,ContractError
from host_runtime.evidence_adapter import build_catalog,EvidenceVerifiers

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'acceptance/runs/20261027-d168-first-home-evidence.json'
PIN='20c63ebdea0444bbc890000502b01e478505583407b6ced4ad11d4155c082f44'


class FirstHomeEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original,cls.paths,_=r._load_bundle(BUNDLE,PIN)
        cls.layout=r._layout();cls.binding=SessionBinding.from_dict(cls.original['native']['binding'])
    def setUp(self):self.data=copy.deepcopy(self.original)
    def result(self):return r.qualify_first_home_recovery(self.data)
    def denied(self):
        result=self.result();self.assertEqual(result['status'],'not_passed',result)
        self.assertFalse(result['ordinary_execution_granted'])
    def trace(self,kind,change):
        for i,row in enumerate(self.data['native']['hook_traces']):
            wire=r._decode(self.layout.WireHookTrace,row['raw_hex'])
            if wire.trace.kind==kind:
                change(wire.trace);value=bytes(wire).hex()
                self.data['native']['hook_traces'][i]['raw_hex']=value
                self.data['capture']['hook_traces'][i]['raw_hex']=value
                return
        self.fail('field trace kind missing')
    def event(self,phase,change):
        for i,row in enumerate(self.data['native']['events']):
            event=r._decode(self.layout.WireEvent,row['raw_hex'])
            if event.event_type==b'phase'and event.receipt.phase==phase:
                change(event);value=bytes(event).hex()
                self.data['native']['events'][i]['raw_hex']=value;self.data['capture']['events'][i]['raw_hex']=value
                return
        self.fail('field phase missing')

    def test_complete_original_inputs_qualify_only_first_home_no_goal_or_ordinary_grant(self):
        result=self.result();self.assertEqual(result['status'],'passed',result)
        self.assertTrue(all(result['checks'].values()))
        self.assertTrue(result['physical_home']);self.assertTrue(result['control_released'])
        self.assertTrue(result['original_task_failed']);self.assertFalse(result['goal_effect_verified'])
        self.assertFalse(result['ordinary_execution_granted']);self.assertFalse(result['natural_AI_interference_claimed'])

    def test_paid_actor_cannot_be_replaced_by_summary_flags(self):
        Receipt,_=r._producer_types(self.layout)
        paid=r._decode(Receipt,self.data['native']['producer_receipt']['raw_hex']);paid.paid=84
        self.data['native']['producer_receipt']['raw_hex']=bytes(paid).hex();self.denied()

    def test_missing_or_changed_independent_capture_is_not_accepted(self):
        self.data['capture']['events'].pop();self.denied()

    def test_unknown_prefix_remains_required_after_successful_recovery(self):
        self.data['prior']['commands'].pop();self.denied()

    def test_lagged_observation_highwater_requires_its_separate_diagnostic_ack(self):
        h=r._decode(self.layout.SharedChannel,self.data['prior']['header_before_hex'],self.layout.SharedChannel.events.offset)
        self.assertEqual(h.native_last_sequence,2);self.assertEqual(h.command_receipt.sequence,3)
        h.command_receipt.sequence=2
        value=bytes(h)[:self.layout.SharedChannel.events.offset].hex()
        self.data['prior']['header_before_hex']=self.data['prior']['header_after_hex']=value;self.denied()

    def test_unknown_snapshot_cannot_already_have_consumed_recovery_sequence(self):
        h=r._decode(self.layout.SharedChannel,self.data['prior']['header_before_hex'],self.layout.SharedChannel.events.offset)
        h.native_last_sequence=4;value=bytes(h)[:self.layout.SharedChannel.events.offset].hex()
        self.data['prior']['header_before_hex']=self.data['prior']['header_after_hex']=value;self.denied()

    def test_fault_marker_must_name_the_actual_independent_command(self):
        self.trace(35,lambda t:t.words.__setitem__(1,t.words[1]^1));self.denied()

    def test_real_foreign_move_cannot_be_changed_into_an_owned_scope(self):
        for i,row in enumerate(self.data['native']['hook_traces']):
            wire=r._decode(self.layout.WireHookTrace,row['raw_hex'])
            if wire.trace.kind==1 and wire.trace.scope==0:
                wire.trace.scope=1;raw=bytes(wire).hex()
                self.data['native']['hook_traces'][i]['raw_hex']=raw;self.data['capture']['hook_traces'][i]['raw_hex']=raw
                break
        self.denied()

    def test_duplicate_host_quiescent_frame_is_not_four_independent_frames(self):
        self.data['trial']['recovery_quiescent_frames'][1]=self.data['trial']['recovery_quiescent_frames'][0];self.denied()

    def test_native_paired_empty_slot_is_required_independent_of_host_booleans(self):
        frame=self.data['trial']['recovery_quiescent_frames'][0]
        for i,row in enumerate(self.data['native']['hook_traces']):
            wire=r._decode(self.layout.WireHookTrace,row['raw_hex'])
            if wire.trace.kind==16 and wire.trace.frame==frame:
                wire.trace.words[0]=123;raw=bytes(wire).hex()
                self.data['native']['hook_traces'][i]['raw_hex']=raw;self.data['capture']['hook_traces'][i]['raw_hex']=raw
                break
        self.denied()

    def test_physical_home_flag_does_not_replace_actual_home_position(self):
        self.event(10,lambda e:setattr(e.observation.xyz,'x',e.observation.xyz.x+100));self.denied()

    def test_native_pool_return_is_required_after_actual_home(self):
        self.event(12,lambda e:setattr(e.observation,'team',e.observation.script_team));self.denied()

    def test_producer_summary_cannot_hide_live_callbacks_in_original_bytes(self):
        _,Header=r._producer_types(self.layout)
        h=r._decode(Header,self.data['cleanup']['header_before_hex']);h.active=1
        self.data['cleanup']['header_before_hex']=self.data['cleanup']['header_after_hex']=bytes(h).hex();self.denied()

    def test_missing_original_entry_bytes_cannot_be_replaced_by_restore_mask(self):
        self.data['cleanup']['entries'].pop();self.denied()

    def test_new_intent_must_match_original_wire_and_immutable_hash(self):
        self.data['home_intent']['wire']['command_id']=str(uuid.uuid4());self.denied()

    def test_json_audit_wire_cannot_hide_a_different_binary_command(self):
        self.data['native']['commands'][3]['wire']['command_id']=str(uuid.uuid4());self.denied()

    def test_mixed_bootstrap_mode_is_refused(self):
        boot=r._decode(self.layout.Bootstrap,self.data['native']['bootstrap_hex']);boot.experimental_flags=3
        self.data['native']['bootstrap_hex']=bytes(boot).hex();self.denied()

    def test_current_build_change_refuses_historical_report(self):
        with patch.object(r,'verify_build_artifacts',side_effect=r.EvidenceError('built_source_changed')):
            self.assertEqual(self.result()['reason_code'],'built_source_changed')

    def test_pinned_registration_requalifies_both_sources_and_grants_only_operation7(self):
        binding=replace(self.binding,host_id=str(uuid.uuid4()),game_process_id=99999)
        grant=r.verify_pinned_first_home(BUNDLE,PIN,binding,baseline_report=self.paths['baseline'],baseline_sha256=self.original['_digests']['baseline'])
        self.assertEqual(grant.capability_id,'tactics.reconcile_return_home')
        self.assertEqual(grant.executor_sha256,self.original['native']['executor_sha256'])
        self.assertEqual(grant.public()['execution_constraints']['module'],'runtime_first_home_recovery_v1')

    def test_registration_cannot_cross_commander_or_mod(self):
        for binding in (replace(self.binding,commander_id=str(uuid.uuid4())),replace(self.binding,mod_sha256='f'*64)):
            with self.subTest(binding=binding.binding_hash),self.assertRaises(ContractError):r.verify_pinned_first_home(BUNDLE,PIN,binding)

    def test_handoff_catalog_requalifies_real_inputs_for_the_new_host_identity(self):
        from host_runtime.host_tactical import _handoff_catalog
        binding=replace(self.binding,host_id=str(uuid.uuid4()))
        catalog=_handoff_catalog(binding,self.paths['baseline'],self.original['_digests']['baseline'],recovery_source=BUNDLE,recovery_digest=PIN)
        self.assertEqual(catalog.binding,binding)
        self.assertEqual(catalog.require('tactics.reconcile_return_home',binding).evidence_id,PIN)
        with self.assertRaisesRegex(ContractError,'binding_mismatch'):catalog.require('tactics.reconcile_return_home',self.binding)

    def test_handoff_half_pin_refuses_before_even_basic_source_verification(self):
        from host_runtime.host_tactical import _handoff_catalog
        with patch('host_runtime.runtime_evidence.verify_pinned_runtime',side_effect=AssertionError('No verifier access')):
            with self.assertRaisesRegex(ContractError,'first_home_evidence_pin_required'):
                _handoff_catalog(self.binding,self.paths['baseline'],self.original['_digests']['baseline'],recovery_source=BUNDLE)

    def test_wrong_bundle_or_baseline_pin_is_refused(self):
        with self.assertRaisesRegex(ContractError,'pin_mismatch'):r.verify_pinned_first_home(BUNDLE,'a'*64,self.binding)
        with self.assertRaisesRegex(ContractError,'baseline_reference_mismatch'):
            r.verify_pinned_first_home(BUNDLE,PIN,self.binding,baseline_report=self.paths['baseline'],baseline_sha256='a'*64)

    def temporary_bundle(self,payload):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        path=Path(temp.name)/'evidence.json';path.write_text(payload,encoding='utf-8')
        return path,hashlib.sha256(path.read_bytes()).hexdigest()

    def test_duplicate_keys_and_checkpoint_success_flags_are_not_authority(self):
        for payload in ('{"schema_version":1,"schema_version":1}',json.dumps(dict(schema_version=1,protocol='tactical_first_home_recovery_evidence_v1',inputs={},passed=True))):
            path,pin=self.temporary_bundle(payload)
            with self.assertRaises(ContractError):r.verify_pinned_first_home(path,pin,self.binding)

    def test_path_escape_is_refused_before_any_input_selected_code_can_run(self):
        bundle=json.loads(BUNDLE.read_text(encoding='utf-8'))
        bundle['inputs']['baseline']['file']='../outside.py'
        path,pin=self.temporary_bundle(json.dumps(bundle))
        with self.assertRaisesRegex(ContractError,'path_invalid'):r.verify_pinned_first_home(path,pin,self.binding)

    def test_build_catalog_opt_in_needs_current_baseline_and_both_explicit_pins(self):
        session=copy.deepcopy(self.original['session']);verifiers=EvidenceVerifiers(session=lambda binding,session:None)
        with self.assertRaisesRegex(ContractError,'first_home_evidence_pin_required'):
            build_catalog(self.binding,session,runtime_recovery_report=BUNDLE,verifiers=verifiers)
        with self.assertRaisesRegex(ContractError,'first_home_requires_baseline_scope'):
            build_catalog(self.binding,session,runtime_recovery_report=BUNDLE,runtime_recovery_sha256=PIN,verifiers=verifiers)
        evidence=build_catalog(self.binding,session,runtime_report=self.paths['baseline'],runtime_sha256=self.original['_digests']['baseline'],
            runtime_recovery_report=BUNDLE,runtime_recovery_sha256=PIN,verifiers=verifiers)
        self.assertTrue(evidence.test_only)
        self.assertEqual({g['capability_id']for g in evidence.catalog.describe()['grants']},{'tactics.move_hold_return','tactics.reconcile_return_home'})
        self.assertEqual(evidence.public()['first_home_recovery_evidence_id'],PIN)
        self.assertEqual(evidence.catalog.describe_axes()['risk']['mode'],'advisory')

if __name__=='__main__':unittest.main()
