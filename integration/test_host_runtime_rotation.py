"""Synthetic raw closure and durable handoff checks; no game/Win32 actions."""
import copy
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from host_runtime import runtime_rotation as rotation
from host_runtime.contracts import ContractError
from host_runtime.journal import CommandJournal
import test_host_runtime_runtime_evidence as evidence_fixtures
from test_host_runtime_tactical_adapter import uid


class RotationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.report,self.binding,self.l=evidence_fixtures.fixture()
        self.report.update(diagnostic=False,field_scope_admitted=True,field_evidence_id='synthetic-only')
        header=rotation._decode(self.l.SharedChannel,self.report['header_before_hex'],self.l.SharedChannel.events.offset)
        header.native_last_sequence=2
        self.report['header_before_hex']=self.report['header_after_hex']=bytes(header)[:self.l.SharedChannel.events.offset].hex()
        self.capture={k:copy.deepcopy(self.report[k]) for k in ('header_before_hex','header_after_hex','events','hook_traces','trace_counters_before_hex','trace_counters_after_hex','traces_written')}
        self.capture.update(native_writes=0,sdk_game_calls=0)
        self.build=patch.object(rotation,'verify_build_artifacts',return_value={'TacticoreRuntime1.dll':'d'*64,'runtime_host.exe':'e'*64})
        self.build.start();self.addCleanup(self.build.stop)
        self.journal=CommandJournal(self.root/'ledger.sqlite3');self.oldrun=uid()
        self.journal.register_run(self.oldrun,self.binding.public())
        for i in range(2):
            row=self.journal.reserve_command(self.oldrun,uid(),'synthetic_native',{})
            self.journal.mark_dispatching(self.oldrun,row['request_id'])
            self.journal.reserve_native_sequence(self.oldrun,row['command_id'],0)
            self.journal.record_outcome(self.oldrun,row['request_id'],'completed',{})

    def tearDown(self):self.journal.close();self.temp.cleanup()

    def deferred(self):
        facts=rotation.assess_retirement(self.report,self.capture,self.binding)
        previous=self.root/'previous.json';previous.write_text(json.dumps(self.report),encoding='utf-8')
        digest=hashlib.sha256(previous.read_bytes()).hexdigest()
        owner=SimpleNamespace(run_id=self.oldrun)
        with patch.object(rotation,'_closed_channel',return_value=(self.journal,self.binding,previous,previous.read_bytes(),self.capture,digest,facts)):
            return rotation.retire_for_later(owner,session_path=self.root/'session.json',capture_path=self.root/'deferred-capture.json',manifest_path=self.root/'closed.json')

    def test_deferred_close_grants_no_successor_until_one_later_fixed_authorization(self):
        retired=self.deferred();record=rotation.validate_retirement(retired)
        self.assertFalse(record['successor_authorized']);self.assertNotIn('next_binding',record)
        self.assertEqual([r['operation']for r in self.journal.commands_for_run(self.oldrun)][-1],'runtime_channel_retire')
        chosen=uid();h=rotation.authorize_deferred_successor(retired,producer_command_id=chosen,manifest_path=self.root/'late-handoff.json')
        self.assertEqual(rotation.validate_handoff(h,h.binding,chosen)['successor_actor']['producer_command_id'],chosen)
        self.assertNotEqual(h.binding.host_id,self.binding.host_id)
        with self.assertRaisesRegex(ContractError,'already_authorized'):
            rotation.authorize_deferred_successor(retired,producer_command_id=chosen,manifest_path=self.root/'second-handoff.json')
        self.assertFalse((self.root/'second-handoff.json').exists())

    def test_late_authorization_uses_current_durable_high_water_after_new_production(self):
        retired=self.deferred();request=uid();row=self.journal.reserve_command(self.oldrun,request,'produce',{})
        self.journal.mark_dispatching(self.oldrun,request)
        self.journal.reserve_native_sequence(self.oldrun,row['command_id'],0)
        self.journal.record_outcome(self.oldrun,request,'completed',{})
        h=rotation.authorize_deferred_successor(retired,producer_command_id=row['command_id'],manifest_path=self.root/'later.json')
        self.assertEqual(h.persisted_sequence,3)
        rotation.claim_handoff(h,h.binding,row['command_id'])
        with self.assertRaisesRegex(ContractError,'prior_commands_unresolved'):rotation.claim_handoff(h,h.binding,row['command_id'])

    def test_unknown_pending_production_or_edited_closure_refuses_later_authorization(self):
        retired=self.deferred();request=uid();self.journal.reserve_command(self.oldrun,request,'produce',{})
        self.journal.mark_dispatching(self.oldrun,request)
        with self.assertRaisesRegex(ContractError,'prior_commands_unresolved'):
            rotation.authorize_deferred_successor(retired,producer_command_id=uid(),manifest_path=self.root/'blocked.json')
        self.journal.record_outcome(self.oldrun,request,'rejected',{})
        retired.manifest_path.write_text('{}')
        with self.assertRaisesRegex(ContractError,'retirement_manifest_changed'):
            rotation.authorize_deferred_successor(retired,producer_command_id=uid(),manifest_path=self.root/'changed.json')

    def test_retirement_object_is_not_a_handoff_and_failed_authorization_never_retries(self):
        retired=self.deferred()
        with self.assertRaisesRegex(ContractError,'sealed_handoff_required'):rotation.claim_handoff(retired,self.binding,uid())
        with patch.object(rotation,'_write_once',side_effect=OSError('synthetic publication failure')):
            with self.assertRaises(OSError):rotation.authorize_deferred_successor(retired,producer_command_id=uid(),manifest_path=self.root/'failed.json')
        row=self.journal.commands_for_run(self.oldrun,operation='runtime_channel_successor_authorize')[0]
        self.assertEqual(row['status'],'uncertain')
        with self.assertRaisesRegex(ContractError,'prior_commands_unresolved'):
            rotation.authorize_deferred_successor(retired,producer_command_id=uid(),manifest_path=self.root/'retry.json')

    def handoff(self,*,next_paid=None):
        if next_paid is not None:
            _,Header=rotation._producer_types(self.l)
            header=rotation._decode(Header,self.report['producer_receipt']['native_header_hex']);header.total_budget=305
            self.report['producer_receipt']['native_header_hex']=bytes(header).hex()
        facts=rotation.assess_retirement(self.report,self.capture,self.binding)
        next_binding=replace(self.binding,host_id=uid());run_id=uid()
        previous=self.root/'previous.json';captured=self.root/'capture.json'
        previous.write_text(json.dumps(self.report),encoding='utf-8');captured.write_text(json.dumps(self.capture),encoding='utf-8')
        value=dict(next_binding=next_binding.public(),next_run_id=run_id,persisted_sequence=2,facts=facts,
            previous_report=str(previous),previous_report_sha256=hashlib.sha256(previous.read_bytes()).hexdigest(),
            previous_capture=str(captured),previous_capture_sha256=hashlib.sha256(captured.read_bytes()).hexdigest())
        if next_paid is not None:value['successor_actor']=dict(mode='new_paid_conscript',producer_command_id=next_paid)
        path=self.root/'handoff.json';path.write_text(json.dumps(value),encoding='utf-8')
        self.journal.register_run(run_id,next_binding.public())
        return rotation.RuntimeHandoff(next_binding,run_id,2,path,hashlib.sha256(path.read_bytes()).hexdigest(),self.journal,rotation._SEAL)

    def actor_and_client(self,handoff):
        value=json.loads(handoff.manifest_path.read_text(encoding='utf-8'));actor=rotation._decode(self.l.Actor,value['facts']['previous_actor_hex'])
        actor.born_frame=value['facts']['retirement_frame']+10
        runtime=SimpleNamespace(binding=handoff.binding,producer_command_id=value['facts']['producer_command_id'],
            actor_bytes=bytes(actor),token=value['facts']['previous_token']+1,
            shared=SimpleNamespace(bootstrap=SimpleNamespace(persisted_sequence=2)),output=self.root/'successor.json')
        return SimpleNamespace(identity=SimpleNamespace(object_id=actor.object_id)),runtime

    def fresh_actor_and_client(self,handoff):
        record=json.loads(handoff.manifest_path.read_text(encoding='utf-8'));selected=record['successor_actor']['producer_command_id']
        actor,runtime=self.actor_and_client(handoff)
        current=self.l.Actor.from_buffer_copy(runtime.actor_bytes);current.object_id+=1;current.thing+=0x1000;current.update+=0x1000
        boot=rotation._decode(self.l.Bootstrap,self.report['bootstrap_hex']);boot.actor=current;boot.actor.generation=boot.actor.born_frame=0
        boot.binding.host[:]=self.l.uuid_words(handoff.binding.host_id);boot.binding.binding_hash[:]=self.l.digest_words(handoff.binding.binding_hash)
        boot.producer.command[:]=self.l.uuid_words(selected);boot.producer.sequence+=1;boot.producer.receipt_index+=1;boot.persisted_sequence=2
        Receipt,Header=rotation._producer_types(self.l)
        paid=rotation._decode(Receipt,self.report['producer_receipt']['raw_hex'])
        paid.command.id[:]=self.l.uuid_words(selected);paid.command.seq=boot.producer.sequence;paid.object=current.thing;paid.object_id=current.object_id
        header=rotation._decode(Header,self.report['producer_receipt']['native_header_hex']);header.count+=1;header.spent+=85
        runtime.producer_command_id=selected;runtime.actor_bytes=bytes(current);runtime.bootstrap_bytes=bytes(boot)
        runtime.producer_receipt=dict(raw_hex=bytes(paid).hex(),native_header_hex=bytes(header).hex())
        return SimpleNamespace(identity=SimpleNamespace(object_id=current.object_id)),runtime

    def test_new_paid_actor_requires_explicit_selection_and_monotone_original_payment(self):
        h=self.handoff(next_paid=uid());actor,runtime=self.fresh_actor_and_client(h)
        request,_=rotation.claim_handoff(h,h.binding,runtime.producer_command_id)
        rotation.finish_handoff(h,request,runtime,actor)
        receipt=self.journal.get_command(h.run_id,request)['receipt']
        self.assertEqual(receipt['actor_selection_mode'],'new_paid_conscript')
        self.assertEqual(receipt['producer_command_id'],runtime.producer_command_id)
        self.assertFalse(receipt['mission_effect_verified'])
        self.assertEqual(self.journal.native_sequence_high_water(h.binding.public()),2)

    def test_new_paid_selection_does_not_reset_spend_or_accept_an_unselected_command(self):
        h=self.handoff(next_paid=uid());actor,runtime=self.fresh_actor_and_client(h)
        request,_=rotation.claim_handoff(h,h.binding,runtime.producer_command_id)
        _,Header=rotation._producer_types(self.l);header=rotation._decode(Header,runtime.producer_receipt['native_header_hex'])
        header.spent=85;runtime.producer_receipt['native_header_hex']=bytes(header).hex()
        with self.assertRaisesRegex(ContractError,'producer_sequence_and_budget'):
            rotation.finish_handoff(h,request,runtime,actor)
        old=json.loads(h.manifest_path.read_text())['facts']['producer_command_id']
        with self.assertRaisesRegex(ContractError,'binding_or_paid_actor_changed'):
            rotation.validate_handoff(h,h.binding,old)
        self.assertEqual(self.journal.get_command(h.run_id,request)['status'],'dispatching')

    def test_fresh_paid_selection_cannot_relabel_the_previous_actor(self):
        h=self.handoff(next_paid=uid());actor,runtime=self.fresh_actor_and_client(h)
        request,_=rotation.claim_handoff(h,h.binding,runtime.producer_command_id)
        old=rotation._decode(self.l.Actor,json.loads(h.manifest_path.read_text())['facts']['previous_actor_hex'])
        old.born_frame=self.l.Actor.from_buffer_copy(runtime.actor_bytes).born_frame
        runtime.actor_bytes=bytes(old);actor.identity.object_id=old.object_id
        with self.assertRaisesRegex(ContractError,'new_native_incarnation_unverified'):
            rotation.finish_handoff(h,request,runtime,actor)

    def test_closed_bound_capture_does_not_grant_mission_success(self):
        result=rotation.assess_retirement(self.report,self.capture,self.binding)
        self.assertEqual(result['previous_native_sequence'],2)
        self.assertTrue(result['control_released'])
        self.assertFalse(result['mission_effect_granted'])

    def test_held_actor_missing_entry_and_diagnostic_channel_refused(self):
        for change in ('held','entry','diagnostic'):
            report=copy.deepcopy(self.report);capture=copy.deepcopy(self.capture)
            if change=='held':
                h=rotation._decode(self.l.SharedChannel,report['header_before_hex'],self.l.SharedChannel.events.offset);h.receipt.held=1
                raw=bytes(h)[:self.l.SharedChannel.events.offset].hex()
                report['header_before_hex']=report['header_after_hex']=capture['header_before_hex']=capture['header_after_hex']=raw
            elif change=='entry':report['terminal_entries'].pop()
            else:report['diagnostic']=True
            with self.subTest(change=change),self.assertRaises(ContractError):rotation.assess_retirement(report,capture,self.binding)

    def test_lost_or_edited_original_rows_cannot_be_retired(self):
        for change in ('counter','event'):
            capture=copy.deepcopy(self.capture)
            if change=='counter':capture['trace_counters_after_hex']='00'*8
            else:capture['events'][0]['raw_hex']=capture['events'][-1]['raw_hex']
            with self.subTest(change=change),self.assertRaises(ContractError):rotation.assess_retirement(self.report,capture,self.binding)

    def test_only_new_host_epoch_same_game_paid_actor_and_pinned_evidence(self):
        h=self.handoff();record=rotation.validate_handoff(h,h.binding,json.loads(h.manifest_path.read_text(encoding='utf-8'))['facts']['producer_command_id'])
        self.assertNotEqual(h.binding.host_id,self.binding.host_id)
        self.assertEqual(self.journal.native_sequence_high_water(h.binding.public()),2)
        with self.assertRaises(ContractError):rotation.validate_handoff(h,self.binding,record['facts']['producer_command_id'])
        with self.assertRaises(ContractError):rotation.validate_handoff(h,h.binding,uid())
        Path(record['previous_capture']).write_text('{}')
        with self.assertRaisesRegex(ContractError,'retired_evidence_changed'):
            rotation.validate_handoff(h,h.binding,record['facts']['producer_command_id'])

    def test_attach_claim_persists_across_process_owner_reopen_and_never_retries(self):
        h=self.handoff();paid=json.loads(h.manifest_path.read_text(encoding='utf-8'))['facts']['producer_command_id']
        request,_=rotation.claim_handoff(h,h.binding,paid)
        self.assertEqual(self.journal.get_command(h.run_id,request)['status'],'dispatching')
        self.journal.close();self.journal=CommandJournal(self.root/'ledger.sqlite3');h=replace(h,journal=self.journal)
        with self.assertRaisesRegex(ContractError,'prior_commands_unresolved'):rotation.claim_handoff(h,h.binding,paid)

    def test_native_rebind_finishes_without_resetting_global_command_sequence(self):
        h=self.handoff();actor,runtime=self.actor_and_client(h)
        request,_=rotation.claim_handoff(h,h.binding,runtime.producer_command_id)
        rotation.finish_handoff(h,request,runtime,actor)
        row=self.journal.get_command(h.run_id,request)
        self.assertEqual(row['status'],'completed');self.assertFalse(row['receipt']['mission_effect_verified'])
        self.assertEqual(self.journal.unresolved_for_session(h.binding.public()),[])
        next_command=self.journal.reserve_command(h.run_id,uid(),'synthetic_native',{})
        self.journal.mark_dispatching(h.run_id,next_command['request_id'])
        self.assertEqual(self.journal.reserve_native_sequence(h.run_id,next_command['command_id'],2),3)

    def test_changed_actor_or_stale_native_registration_never_finishes_handoff(self):
        h=self.handoff();actor,runtime=self.actor_and_client(h)
        request,_=rotation.claim_handoff(h,h.binding,runtime.producer_command_id)
        changed=self.l.Actor.from_buffer_copy(runtime.actor_bytes);changed.thing+=4;runtime.actor_bytes=bytes(changed)
        with self.assertRaisesRegex(ContractError,'new_native_incarnation_unverified'):rotation.finish_handoff(h,request,runtime,actor)
        self.assertEqual(self.journal.get_command(h.run_id,request)['status'],'dispatching')

    def test_client_attach_exception_retains_unknown_once_without_native_retry(self):
        path=Path(__file__).resolve().parents[1]/'tactical/runtime/client.py'
        spec=importlib.util.spec_from_file_location('rotation_native_client_test',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        h=self.handoff();_,example=self.actor_and_client(h)
        runtime=module.NativeRuntimeClient.__new__(module.NativeRuntimeClient)
        runtime.handoff=h;runtime.binding=h.binding;runtime.producer_command_id=example.producer_command_id
        runtime._field_admission=lambda _:None
        with patch.object(runtime,'_attach',side_effect=TimeoutError('synthetic')) as attach:
            with self.assertRaises(TimeoutError):runtime.attach()
            with self.assertRaisesRegex(ContractError,'prior_commands_unresolved'):runtime.attach()
        self.assertEqual(attach.call_count,1)
        self.assertEqual(self.journal.unresolved(h.run_id)[0]['status'],'uncertain')


if __name__=='__main__':unittest.main()
