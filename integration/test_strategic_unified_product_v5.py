"""Artificial transport with real durable ledger; no game/model capability."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import uuid

from host_runtime.contracts import ContractError
from host_runtime.journal import CommandJournal
from host_runtime.strategic_unified_controller_v5 import UnifiedStrategicControllerV5
from host_runtime.strategic_unified_release_v5 import verified_proof,verified_journal
from host_runtime.strategic_unified_feedback_v5 import project_unified_feedback
from strategy.native_unified_contract_v5 import FLAG_ACTIONS,GATE_ACTIONS

ROOT=Path(__file__).resolve().parents[1]

class Dispatch(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.journal=CommandJournal(Path(self.tmp.name)/'ledger.sqlite');self.addCleanup(self.journal.close)
        self.session=str(uuid.uuid4());self.run=str(uuid.uuid4());self.journal.register_run(self.run,dict(session_id=self.session))
        self.calls=[];self.components=[1,1,1]
        def empty_gate():
            return dict(phase=0,baseline_captured=0,baseline=[0,0,0],observed=[0,0,0],frame=0,deadline_frame=0,
                attempted=0,requested_enabled=0,operation_enabled=0,already_satisfied=0)
        self.native=dict(last_frame=1500,request=0,ack=0,phase=1,active=0,error=0,result=0,
            gates=[empty_gate(),empty_gate()],applied_mask=0,flag_phase=0,flag_deadline=0)
        def call(kind,gate,enabled,frames,ident,not_after_frame,release=False,actions=None):
            self.calls.append(dict(kind=kind,gate=gate,enabled=enabled,absolute=not_after_frame,actions=actions,duration_frames=frames))
            if getattr(self,'fail_gate',None)==gate and kind=='manager':raise RuntimeError('artificial unknown after physical publish')
            self.native['last_frame']+=1;self.native['ack']+=1;self.native['request']=self.native['ack']
            frame=self.native['last_frame']
            if kind=='manager':
                state=self.native['gates'][gate];indices=(0,) if gate==0 else (1,2)
                if not state['baseline_captured']:state.update(baseline_captured=1,baseline=list(self.components))
                desired=state['baseline'][indices[0]] if release else int(enabled)
                satisfied=all(self.components[i]==desired for i in indices)
                for i in indices:self.components[i]=desired
                state.update(phase=4 if release else 1,observed=list(self.components),frame=frame,
                    requested_enabled=desired,operation_enabled=desired,already_satisfied=int(satisfied),attempted=int(not satisfied))
                if not release:state['deadline_frame']=min(frame+frames,not_after_frame)
                self.native['result']=3 if release else 7 if satisfied and desired else 6 if desired else 2
            else:
                mask=sum(1<<FLAG_ACTIONS.index(a) for a in actions)
                self.native.update(applied_mask=mask,flag_phase=1 if mask else 4,
                    flag_deadline=min(frame+frames,not_after_frame) if mask else 0,result=8)
            return dict(seq=self.native['ack'],native_gate_acknowledged=True,native_effect_verified=False,native=copy.deepcopy(self.native))
        transport=SimpleNamespace(native_status=lambda:copy.deepcopy(self.native),
            manager=lambda gate,enabled,frames,ident,**kwargs:call('manager',gate,enabled,frames,ident,**kwargs),
            apply=lambda actions,frames,ident,**kwargs:call('flags',None,None,frames,ident,actions=actions,**kwargs))
        scope=SimpleNamespace(available_actions=FLAG_ACTIONS+tuple(GATE_ACTIONS),action_flags=dict(zip(FLAG_ACTIONS,FLAG_ACTIONS)))
        self.controller=UnifiedStrategicControllerV5(transport,self.journal,self.run,scope,self.session,'a'*64,lambda *a,**k:None)
    def plan(self,actions):
        p=SimpleNamespace(plan_id=str(uuid.uuid4()),origin='model',session_id=self.session,
            commander_id='57e668b4-4d89-43bd-bc92-0dd436f046ef',player_id=3,
            based_on_game_time_seconds=100,expires_at_game_seconds=140,macro_actions=tuple(actions))
        p.public=lambda:dict(macro_actions=list(p.macro_actions),macro_production=None,
            production_focus='native_baseline',tactical_tasks=[],runtime_task=None)
        return p
    def test_four_domains_share_original_absolute_deadline_and_duplicate_never_renews(self):
        plan=self.plan(['scout','budgetarmy','pauseconstruction','advanceproduction'])
        first=self.controller.dispatch(plan,101,effective_hash='a'*64)
        self.assertEqual([r['absolute'] for r in self.calls],[2100,2100,2100]);self.assertEqual(first['native_start_frame'],1501)
        self.assertEqual(first['action_domain_windows']['scout']['start_frame'],1503)
        self.assertEqual(first['action_domain_windows']['pauseconstruction']['start_frame'],1501)
        self.assertEqual(first['native_window_semantics'],'owned_domain_envelope_not_continuous_per_action')
        self.assertEqual(first,self.controller.dispatch(plan,102,effective_hash='a'*64));self.assertEqual(len(self.calls),3)
        self.assertEqual(self.journal.unresolved(self.run),[])
        self.assertTrue(all(set(r['payload'])<=set(('actions','plan_id','native_command_id','duration_frames','not_after_frame','unit_operation_policy','parent_command_id','gate','enabled','release'))
            for r in self.journal.commands_for_run(self.run)))
    def test_native_900_frame_cap_is_not_expanded_to_model_3000(self):
        plan=self.plan(['scout']);plan.expires_at_game_seconds=200
        receipt=self.controller.dispatch(plan,101,effective_hash='a'*64)
        self.assertEqual([call['duration_frames'] for call in self.calls],[900])
        self.assertEqual((self.native['last_frame'],self.native['flag_deadline']),(1501,2401))
        self.assertEqual(receipt['native_deadline_frame'],2401)
        self.assertEqual(receipt['action_domain_windows']['scout']['end_frame'],2401)
        self.assertLess(receipt['native_deadline_frame'],3000)
        self.assertEqual(receipt,self.controller.dispatch(plan,102,effective_hash='a'*64))
        self.assertEqual(len(self.calls),1)

    def test_empty_replacement_releases_held_managers_before_new_empty_flag_ack(self):
        self.controller.dispatch(self.plan(['pauseconstruction','pauseproduction']),101,effective_hash='a'*64)
        receipt=self.controller.dispatch(self.plan([]),102,effective_hash='a'*64)
        self.assertEqual(receipt['actions'],[]);self.assertEqual([g['phase'] for g in self.native['gates']],[4,4])
        self.assertEqual(len(self.calls),6);self.assertEqual(self.calls[-1]['actions'],[])
    def test_partial_unknown_never_reports_batch_success_or_retries_native(self):
        self.fail_gate=1;plan=self.plan(['pauseconstruction','pauseproduction','scout'])
        with self.assertRaisesRegex(ContractError,'outcome_unknown'):self.controller.dispatch(plan,101,effective_hash='a'*64)
        self.assertEqual(len(self.calls),2);self.assertEqual(self.controller.current_actions,())
        self.assertEqual(len(self.journal.unresolved(self.run)),2)
        with self.assertRaisesRegex(ContractError,'already_claimed'):self.controller.dispatch(plan,102,effective_hash='a'*64)
        self.assertEqual(len(self.calls),2)
    def test_expired_and_detailed_or_opposing_intents_have_no_native_effect(self):
        for actions in (['produceconscript'],['pauseconstruction','advanceconstruction'],['expand','scout']):
            with self.assertRaises(ContractError):self.controller.dispatch(self.plan(actions),101,effective_hash='a'*64)
        with self.assertRaises(ContractError):self.controller.dispatch(self.plan(['scout']),140,effective_hash='a'*64)
        self.assertEqual(self.calls,[])

# These exact retained research artifacts are not source-distribution assets.
RETURN_PROOF_SOURCE=ROOT/'reports/strategic-unified-natural-terminal-52600-20261029-v1/independent-release.json'
RETURN_JOURNAL_SOURCE=ROOT/'reports/strategic-unified-native-journal/ebec29bd400f44838a2dec0fcba71a0a.bin'
RETURN_ARCHIVE_FILES=(RETURN_PROOF_SOURCE,RETURN_JOURNAL_SOURCE)

@unittest.skipUnless(all(path.is_file() for path in RETURN_ARCHIVE_FILES),
    'requires unpublished terminal-52600 proof and matching Native5 journal')
class ReturnProof(unittest.TestCase):
    def setUp(self):
        self.proof=json.loads(RETURN_PROOF_SOURCE.read_text())
        b=self.proof['native']['binding'];sid=str(uuid.UUID(bytes=bytes(b['session'])))
        self.args=dict(pid=b['pid'],ticks=b['start_low']|b['start_high']<<32,session_id=sid,package=bytes(b['package']).hex(),
            flags=[r['name'] for r in self.proof['flags']['flags']],closure=bytes(b['sources']).hex())
        self.raw=(ROOT/'reports/strategic-unified-native-journal'/(uuid.UUID(sid).hex+'.bin')).read_bytes()
    def test_actual_research_proof_and_binary_layout_agree_without_claiming_formal(self):
        self.assertTrue(verified_proof(self.proof,**self.args));self.assertTrue(verified_journal(self.raw,self.proof['native']))
        self.assertFalse(verified_journal(self.raw[:-1],self.proof['native']))
        corrupt=bytearray(self.raw);corrupt[28]^=1;self.assertFalse(verified_journal(bytes(corrupt),self.proof['native']))
    def test_current_identity_or_one_unrestored_component_or_clock_rejected(self):
        for mutate in (lambda p:p['actual_OS_after'].update(pid=1),lambda p:p['components'][2].update(enabled=0),
            lambda p:p['native'].update(hook_held=1),lambda p:p.update(frame_after=p['frame']+3),
            lambda p:p['current_own_identity'].update(ai_player='0x10000')):
            proof=copy.deepcopy(self.proof);mutate(proof);self.assertFalse(verified_proof(proof,**self.args))

class Feedback(unittest.TestCase):
    # Pure feedback validation never requires a retained field archive.
    def test_feedback_cannot_invent_mission_success_or_drop_original_component_time(self):
        row=dict(action='advanceconstruction',status='native_manager_state_observed',observed_frame=1500,
            preference_active=True,component_state_adopted=True,state_already_satisfied=False,active_native_task_observed=False,
            movement_observed=False,mission_success_verified=False,exclusive_attribution_verified=False)
        value=dict(source='bound_native_strategy_v5',details_owner='native_ai',observed_frame=1501,observations=[row])
        self.assertEqual(project_unified_feedback(value,game_seconds=100.1)['observations'][0]['observed_frame'],1500)
        row['mission_success_verified']=True
        with self.assertRaises(ContractError):project_unified_feedback(value)

if __name__=='__main__':unittest.main()
