"""Strategic export privacy, immutable bounds, exact source bytes and replay.

All receipts/events/files below are explicitly synthetic and never native or
provider qualification. No game, network, registry or credentials are read.
"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid
import sys
import contextlib
import io

import macro_host
from host_runtime.contracts import ContractError,content_hash,SessionBinding
from host_runtime.diagnostics import project_event
from host_runtime.macro_strategy_diagnostics import (StrategyEvidence,journal_receipts,native_receipts,
    project_strategy_event,read_strategy_state,prepare_strategy_extension)
import test_host_runtime_macro_strategy_public as public_fixture
import test_host_runtime_diagnostics as diagnostics_fixture

public_state=public_fixture.public_state

SESSION='d341591e-2ad2-4562-95ca-da20b79fb5b1'
COMMANDER='57e668b4-4d89-43bd-bc92-0dd436f046ef'


def strategy_fixture(binding=None):
    bound=binding or SimpleNamespace(session_id=SESSION,commander_id=COMMANDER,player_id=3)
    p,s,c=[str(uuid.uuid4()) for _ in range(3)]
    base=dict(session_id=bound.session_id,commander_id=bound.commander_id,player_id=bound.player_id)
    declared=dict(strategy_id=None,objective='build_force',phase='prepare',public_fact_refs=['own.credits'],
        expected_observation='production_queue',continue_conditions=['capability_available'],replan_conditions=['facts_changed'],
        resource_priorities=dict(economy=.2,army=.5,tech=.1,reserve=.2))
    plan=dict(**base,plan_id=p,snapshot_id=1,based_on_game_time_seconds=100.,expires_at_game_seconds=130.,
        macro_actions=['budgetarmy'],macro_production=None,macro_strategy=declared,origin='model',
        stance='defend',production_focus='native_baseline',economy_policy='stabilize',tech_policy='hold_current_tier',
        reason_code='balanced_default',budget=dict(economy=.2,army=.5,tech=.1,reserve=.2),tactical_tasks=[])
    def event(kind,frame,**facts):
        return dict(seq=1,event_type=kind,created_at='2026-10-28T00:00:00Z',game_frame=frame,
            command_id=None,payload=dict(base,**facts))
    events=[event('model_macro_request_context',1500,context=dict(game_time_seconds=100.)),
        event('macro_strategy_review',1500,plan_id=p,strategy_id=s,allowed=True,reason_code='strategy_allowed'),
        event('model_macro_dispatch_prepared',1500,plan_id=p,command_id=c,actions=['budgetarmy'],duration_frames=450),
        event('macro_strategy_declared',1500,plan_id=p,strategy_id=s,command_id=c,delivery_unknown=False),
        event('plan_applied',1500,plan_id=p,snapshot_id=1,plan=plan),
        event('macro_strategy_outcome',1530,plan_id=p,command_id=c,outcome='effect_observed',reason_code='bounded_native_fact',
            observed_game_seconds=101.,native_release_verified=False,effect_observed=True)]
    for index,row in enumerate(events):row['seq']=index+1
    proof=dict(seq=1,native_gate_acknowledged=True,native_start_frame=1500,native_deadline_frame=1950)
    return bound,events,{c:proof},p,s,c


class StrategyEventProjectionTests(unittest.TestCase):
    def test_strategic_payloads_never_export_private_command_or_extras(self):
        binding,events,receipts,p,s,c=strategy_fixture();evidence=StrategyEvidence(events,receipts,binding)
        event=copy.deepcopy(events[-1]);event['payload'].update(provider_text='PRIVATE_MODEL',native_address='0xPRIVATE',
            command_payload={'token':'PRIVATE_TOKEN'},extra='PRIVATE_EXTRA')
        projected=project_event(event,binding=binding,strategy_evidence=evidence)
        self.assertTrue(projected['facts']['effect_observed']);self.assertTrue(projected['facts']['effect_window_verified'])
        self.assertEqual(projected['facts']['effect_window_start_seconds'],100)
        self.assertNotIn(c,json.dumps(projected));self.assertNotIn('PRIVATE',json.dumps(projected))
        self.assertFalse(projected['facts']['global_native_release_verified'])
        self.assertEqual(projected['payload_sha256'],content_hash(event['payload']))

    def test_frozen_native_deadline_or_new_attempt_prevents_backfilling_old_success(self):
        binding,events,receipts,p,s,c=strategy_fixture()
        late=copy.deepcopy(events[-1]);late['payload']['observed_game_seconds']=111;late['game_frame']=1800
        short=copy.deepcopy(receipts);short[c]['native_deadline_frame']=1650
        facts=project_event(late,binding=binding,strategy_evidence=StrategyEvidence(events,short,binding))['facts']
        self.assertFalse(facts['effect_observed']);self.assertEqual(facts['outcome'],'unknown')
        new=copy.deepcopy(events[-1]);new.update(event_type='model_macro_dispatch_prepared',game_frame=1605)
        new['payload'].update(plan_id=str(uuid.uuid4()),command_id=str(uuid.uuid4()),duration_frames=450,actions=[])
        changed=events[:-1]+[new,late]
        facts=project_event(late,binding=binding,strategy_evidence=StrategyEvidence(changed,receipts,binding))['facts']
        self.assertEqual(facts['effect_window_end_seconds'],107)
        self.assertFalse(facts['effect_window_verified'])
        # Later mutable telemetry and the saved latest goal are deliberately
        # irrelevant to this old command's immutable effect interval.
        changed.append(dict(event_type='macro_native_feedback',payload={'observed_frame':99999}))
        self.assertFalse(project_event(late,binding=binding,strategy_evidence=StrategyEvidence(changed,receipts,binding))['facts']['effect_observed'])

    def test_ack_or_missing_model_definition_never_promotes_an_effect(self):
        binding,events,receipts,_,_,_=strategy_fixture()
        for evidence in (None,StrategyEvidence(events,{},binding),StrategyEvidence([events[-1]],receipts,binding)):
            value=project_event(events[-1],binding=binding,strategy_evidence=evidence)['facts']
            self.assertFalse(value['effect_observed']);self.assertEqual(value['outcome'],'unknown')

    def test_declared_command_and_binding_must_match_before_any_effect_can_be_qualified(self):
        binding,events,receipts,p,s,c=strategy_fixture()
        for changes in ({'command_id':str(uuid.uuid4())},{'command_id':None},{'delivery_unknown':True},
                {'delivery_unknown':1},{'commander_id':str(uuid.uuid4())}):
            changed=copy.deepcopy(events);changed[3]['payload'].update(changes)
            facts=project_event(changed[-1],binding=binding,strategy_evidence=StrategyEvidence(changed,receipts,binding))['facts']
            self.assertFalse(facts['effect_observed']);self.assertEqual(facts['outcome'],'unknown')
        changed=copy.deepcopy(events);changed[-1]['payload']['command_id']={'private':'PRIVATE'}
        projected=project_event(changed[-1],binding=binding,strategy_evidence=StrategyEvidence(events,receipts,binding))
        self.assertFalse(projected['payload_projected']);self.assertEqual(projected['facts'],{})

    def test_declared_goal_is_from_matching_model_plan_not_arbitrary_event_text(self):
        binding,events,receipts,p,s,c=strategy_fixture();evidence=StrategyEvidence(events,receipts,binding)
        raw=copy.deepcopy(events[3]);raw['payload']['objective']='PRIVATE_INVENTED'
        facts=project_event(raw,binding=binding,strategy_evidence=evidence)['facts']
        self.assertEqual(facts['declaration']['objective'],'build_force')
        self.assertEqual(facts['declaration']['strategy_id'],s);self.assertTrue(facts['intent_command_present'])
        self.assertNotIn(c,json.dumps(facts));self.assertNotIn('PRIVATE',json.dumps(facts))

    def test_ending_an_intent_is_not_a_full_native_release_claim(self):
        binding,events,receipts,_,_,_=strategy_fixture();event=copy.deepcopy(events[-1])
        event['payload'].update(outcome='expired',observed_game_seconds=None,native_release_verified=True,effect_observed=True)
        facts=project_event(event,binding=binding,strategy_evidence=StrategyEvidence(events,receipts,binding))['facts']
        self.assertTrue(facts['intent_end_verified']);self.assertFalse(facts['global_native_release_verified'])
        self.assertNotIn('native_release_verified',facts)

    def test_bad_binding_unknown_kind_and_invalid_core_values_are_refused_without_payload(self):
        binding,events,receipts,_,_,_=strategy_fixture()
        for change in ({'plan_id':'PRIVATE_PLAN'},{'outcome':'complete_all_units'},{'reason_code':'raw PRIVATE'},
            {'observed_game_seconds':-1},{'effect_observed':1},{'commander_id':str(uuid.uuid4())}):
            row=copy.deepcopy(events[-1]);row['payload'].update(change)
            result=project_event(row,binding=binding)
            self.assertFalse(result['payload_projected']);self.assertEqual(result['facts'],{})
        with self.assertRaises(ContractError):project_strategy_event('macro_strategy_private_future',{})
        row=copy.deepcopy(events[-1]);row['payload']['observed_game_seconds']=float('inf')
        with self.assertRaises(ContractError):project_event(row,binding=binding)


class StrategyStateSourceTests(unittest.TestCase):
    def test_actual_source_bytes_hash_is_not_replaced_with_reencoded_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'macro-strategy-state.json';state=public_state()
            private=copy.deepcopy(state);private['raw_provider']='PRIVATE_PROVIDER'
            raw=('\ufeff'+json.dumps(private,indent=3)+'\n  ').encode('utf8');path.write_bytes(raw)
            projected,index,reason=read_strategy_state(path,root)
            self.assertIsNone(reason);self.assertEqual(index['sha256'],hashlib.sha256(raw).hexdigest())
            self.assertEqual(index['bytes'],len(raw));self.assertEqual(projected,state)
            self.assertNotIn('PRIVATE',json.dumps(projected));self.assertFalse(index['content_included'])

    def test_change_during_single_snapshot_read_does_not_mix_content_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'macro-strategy-state.json';raw=json.dumps(public_state()).encode();path.write_bytes(raw)
            original=Path.open
            class Reader:
                def __init__(self,stream):self.stream=stream
                def __enter__(self):return self
                def __exit__(self,*args):self.stream.close()
                def read(self,count):
                    result=self.stream.read(count)
                    with original(path,'wb') as output:output.write(raw+b' ')
                    return result
            def opened(candidate,*args,**kwargs):
                stream=original(candidate,*args,**kwargs)
                return Reader(stream) if candidate==path and args and args[0]=='rb' else stream
            with patch.object(Path,'open',opened):state,index,reason=read_strategy_state(path,root)
            self.assertIsNone(state);self.assertEqual(reason,'strategy_state_changed')
            self.assertEqual(index['sha256'],hashlib.sha256(raw).hexdigest());self.assertFalse(index['stable_during_read'])

    def test_duplicate_json_and_outside_source_are_not_projected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);allowed=root/'allowed';allowed.mkdir();path=root/'macro-strategy-state.json'
            path.write_text('{"schema_version":1,"schema_version":1}')
            self.assertIsNone(read_strategy_state(path,root)[0])
            self.assertIsNone(read_strategy_state(path,allowed)[0])


class StrategyExportChainTests(unittest.TestCase):
    setUp=diagnostics_fixture.DiagnosticsTests.setUp;tearDown=diagnostics_fixture.DiagnosticsTests.tearDown
    new_backend=diagnostics_fixture.DiagnosticsTests.new_backend;ready=diagnostics_fixture.DiagnosticsTests.ready;start_args=diagnostics_fixture.DiagnosticsTests.start_args
    start=diagnostics_fixture.DiagnosticsTests.start;status_file=diagnostics_fixture.DiagnosticsTests.status_file;export=diagnostics_fixture.DiagnosticsTests.export
    macro_start=public_fixture.DesktopStrategyStatusTests.macro_start

    def prepare(self):
        result,run_id,runtime=self.macro_start();state=public_state();output=self.run/'battle-host'
        self.status_file(result,runtime_macro=runtime,macro_strategy=state,latest_snapshot={'game_time_seconds':135.})
        raw=(json.dumps(dict(state,private_payload='PRIVATE_STATE'),indent=2)+'\n').encode('utf8')
        (output/'macro-strategy-state.json').write_bytes(raw)
        row=self.backend._launch(run_id);binding=SessionBinding.from_dict(json.loads(row['binding_json']))
        _,events,proofs,p,s,c=strategy_fixture(binding)
        for event in events:
            if event['event_type']=='model_macro_dispatch_prepared':
                self.backend.journal.append_event(run_id,event['event_type'],event['payload'],game_frame=event['game_frame'])
                self.backend.journal.reserve_command(run_id,c,'macro_policy',dict(native_command_id=c,actions=['budgetarmy'],duration_frames=450))
                self.backend.journal.mark_dispatching(run_id,c);self.backend.journal.record_outcome(run_id,c,'completed',proofs[c])
            else:self.backend.journal.append_event(run_id,event['event_type'],event['payload'],game_frame=event['game_frame'])
        return run_id,raw,state

    def test_actual_export_contains_only_public_strategy_and_exact_source_index(self):
        run_id,state_bytes,state=self.prepare();receipt,document,raw=self.export(run_id)
        extension=document['macro_strategy_extension']
        self.assertEqual(document['schema_version'],1);self.assertTrue(extension['state_available'])
        self.assertEqual(extension['state'],state)
        self.assertEqual(extension['state_source']['sha256'],hashlib.sha256(state_bytes).hexdigest())
        indexed=[r for r in document['raw_file_index'] if r['label']=='macro_strategy_state']
        self.assertEqual(len(indexed),1);self.assertEqual(indexed[0],extension['state_source'])
        self.assertNotIn('PRIVATE_STATE',raw.decode());self.assertFalse(document['native_release_verified'])
        effects=[row['facts'] for row in document['timeline'] if row['event_type']=='macro_strategy_outcome']
        self.assertTrue(effects[0]['effect_window_verified']);self.assertTrue(effects[0]['effect_observed'])
        self.assertNotIn('command_id',effects[0])

    def test_later_state_file_does_not_rewrite_same_export_or_backfill_a_window(self):
        run_id,state_bytes,state=self.prepare();request_id=str(uuid.uuid4())
        receipt,doc,raw=self.export(run_id,request_id)
        changed=copy.deepcopy(state);changed['current_strategy']['updated_game_seconds']=800
        (self.run/'battle-host/macro-strategy-state.json').write_text(json.dumps(changed))
        repeated,document,again=self.export(run_id,request_id)
        self.assertEqual(receipt,repeated);self.assertEqual(raw,again)
        new_receipt,new_document,new_raw=self.export(run_id)
        self.assertFalse(new_document['macro_strategy_extension']['state_available'])
        self.assertEqual(new_document['macro_strategy_extension']['state_reason_code'],'strategy_state_snapshot_changed')

    def test_actual_downloaded_export_becomes_offline_html_with_source_byte_hash(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'acceptance'))
        import export_macro_timeline as timeline
        run_id,_,_=self.prepare();_,document,raw=self.export(run_id)
        source=self.root/'download.json';source.write_bytes(raw);out=self.root/'reports'/'offline-playable'
        with patch.object(timeline,'ROOT',self.root),contextlib.redirect_stdout(io.StringIO()):
            timeline.export_diagnostics(source,out,hashlib.sha256(raw).hexdigest())
        package=json.loads((out/'macro-timeline.json').read_text(encoding='utf8'))
        self.assertEqual(package['sources'][0]['sha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(package['sources'][0]['bytes'],len(raw))
        self.assertTrue((out/'macro-timeline.html').is_file());self.assertFalse(package['native_release_verified'])
        self.assertFalse(package['formal_goal_complete']);self.assertNotIn('PRIVATE',json.dumps(package))
        effects=[r for r in package['events'] if r.get('stage')=='outcome']
        self.assertTrue(effects[0]['facts']['effect_window_verified'])
        checkpoints=[r for r in package['events'] if r['type']=='strategy_state']
        self.assertEqual(checkpoints[0]['t'],135);self.assertTrue(checkpoints[0]['checkpoint_only'])


if __name__=='__main__':unittest.main()
