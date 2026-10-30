"""Synthetic real Host/controller routing and strict optional queue-race scope."""
import asyncio
import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'strategy'),str(ROOT/'native-ai'),str(ROOT/'integration'),str(ROOT)]
import test_macro_delegation_independent_v1 as independent
from host_runtime import test_macro_regions as regional
from host_runtime.test_macro_production_feedback import sample
from host_runtime.macro_durable import DurableMacroTransport
from host_runtime.macro_policy_runtime import MacroRequestAudit
from host_runtime.macro_optional_builder_gap_v1 import assess_optional_builder_gap_v1,CONTROL,IDENTITY
from host_runtime.contracts import ContractError
from acceptance.strategic_optional_builder_candidate_v1 import candidate_production_tick_v1
from tactical_fixtures import tactical_snapshot
from fixtures import SESSION


def artificial():
    obs,_=regional.regional_sample();_,census=sample(1500);obs['construction_feedback']=census
    identity=dict(zip(IDENTITY,(1297100850,2,101,100,200,300,400,500,600)),process_creation_filetime=134000000000000000)
    obs['native']=dict(player='0x64',ai_player='0xc8',personality_wrapper='0x12c',instance_id='0x190',
        player_template='0x1f4',player_index=3,store_membership_verified=True,side_matches_player=True,mutations=False)
    for runtime in obs['runtimes']:
        for group in runtime['owned_groups']:
            for member in group['members']:member['owner']='0x64'
    status=dict(identity);status.pop('process_creation_filetime')
    status.update(start_high=identity['process_creation_filetime']>>32,start_low=identity['process_creation_filetime']&0xffffffff,
        request=0,ack=0,phase=1,active=0,error=0,self_hook_installed=1,lease_held=1,last_frame=1500,applied_mask=0,
        deadline_frame=0,cleanup_verified=1)
    names=tuple('artificial-flag-'+str(i) for i in range(20))
    view=tactical_snapshot();view['battlefield']['formations']=[]
    view['capabilities']['regions'].append('region_1_3')
    view['macro_control']=dict(mode='macro_native',available_actions=[],production_counts={},region_targets={})
    args=dict(controller_state=dict.fromkeys(CONTROL,False),journal_rows=[],transport_ledger={},pending=False,
        native_state=status,native_identity=identity,flags=dict(flags=[dict(name=name,present=False,value=None) for name in names]),
        flag_names=names,lawful_view=view)
    return dict(observation=obs,build_observation_error='macro_builder_queue_changed'),args


class OptionalBuilderGapTests(unittest.TestCase):
    def test_only_explicit_optional_race_is_unknown_never_fake_builder_or_grant(self):
        native,args=artificial();result=assess_optional_builder_gap_v1(native,strategic_only=True,**args)
        self.assertEqual(result.builder_status,'unknown');self.assertEqual(result.observed_frames,(1500,1500))
        self.assertFalse(result.dispatch_authority_granted);self.assertFalse(result.queue_effect_verified)
        self.assertNotIn('build_observation',native)

    def test_missing_reason_and_all_non_queue_source_faults_refuse(self):
        for code in (None,'macro_builder_header_changed','macro_session_identity_changed','signature_changed',
                     'macro_flag_readback_unknown','macro_native_command_unknown','macro_builder_queue_changed '):
            native,args=artificial();native['build_observation_error']=code
            with self.subTest(code=code),self.assertRaises(ContractError):assess_optional_builder_gap_v1(native,strategic_only=True,**args)

    def test_all_precision_activity_unknown_and_stopped_states_refuse(self):
        for key in CONTROL:
            native,args=artificial();args['controller_state'][key]=True
            with self.subTest(key=key),self.assertRaises(ContractError):assess_optional_builder_gap_v1(native,strategic_only=True,**args)

    def test_durable_and_transport_unsettled_ledgers_refuse(self):
        for status in ('reserved','dispatching','uncertain','unknown','failed'):
            native,args=artificial();args['journal_rows']=[dict(status=status)]
            with self.subTest(status=status),self.assertRaises(ContractError):assess_optional_builder_gap_v1(native,strategic_only=True,**args)
        for key,value in (('pending',True),('transport_ledger',{'id':dict(status='unknown')})):
            native,args=artificial();args[key]=value
            with self.subTest(key=key),self.assertRaises(ContractError):assess_optional_builder_gap_v1(native,strategic_only=True,**args)

    def test_native_identity_protocol_flags_unknown_and_incarnation_refuse(self):
        for key,value in (('pid',102),('version',1),('owner',999),('start_low',0),('ack',1),
                          ('active',1),('error',1),('self_hook_installed',0),('lease_held',0),('applied_mask',4)):
            native,args=artificial();args['native_state'][key]=value
            with self.subTest(key=key),self.assertRaises(ContractError):assess_optional_builder_gap_v1(native,strategic_only=True,**args)
        native,args=artificial();args['flags']['flags'][0].update(present=True,value=True)
        with self.assertRaises(ContractError):assess_optional_builder_gap_v1(native,strategic_only=True,**args)

    def test_missing_lawful_view_source_foreign_owner_and_stale_frames_refuse(self):
        changes=(lambda n,a:a['lawful_view']['battlefield'].update(visibility_verified=False),
            lambda n,a:n['observation'].update(source='foreign'),
            lambda n,a:n['observation']['native'].update(player='0x99'),
            lambda n,a:n['observation']['construction_feedback'].update(enemy_details_read=True),
            lambda n,a:n['observation'].update(frame=1450),lambda n,a:n.update(read_error='identity_changed'))
        for change in changes:
            native,args=artificial();change(native,args)
            with self.assertRaises(ContractError):assess_optional_builder_gap_v1(native,strategic_only=True,**args)

    def test_native_deadlines_never_extend_or_masquerade_as_clear(self):
        for mask,deadline,cleanup in ((0,1501,1),(0,0,0),(2,1499,0),(2,2851,0),(2,0,0)):
            native,args=artificial();args['native_state'].update(applied_mask=mask,deadline_frame=deadline,cleanup_verified=cleanup)
            if mask:args['flags']['flags'][1].update(present=True,value=True)
            with self.subTest(mask=mask,deadline=deadline),self.assertRaises(ContractError):
                assess_optional_builder_gap_v1(native,strategic_only=True,**args)

    def test_candidate_core_refusal_never_calls_controller_tick_or_model_or_native(self):
        native,args=artificial();args['native_state']['ack']=1;calls=[]
        host=SimpleNamespace(strategic_only=True,controller=SimpleNamespace(tick=lambda *a:calls.append('tick')))
        with self.assertRaises(ContractError):candidate_production_tick_v1(host,native,gate_arguments=args)
        self.assertEqual(calls,[])

    def test_candidate_real_host_controller_model_and_final_dispatch_remain_high_level(self):
        for action in ('budgetarmy','scout','deployattack'):
            with self.subTest(action=action):
                outer=independent.StrategicDelegationIndependentTests();case=outer.case();self.addCleanup(outer.doCleanups)
                host=case.host();test=regional.RegionalControllerTests();test.setUp()
                host.controller=test.controller;host.controller.session_id=SESSION;host.controller.budget.session_id=SESSION
                durable=DurableMacroTransport(host.transport,host.journal,host.run_id)
                host.controller.transport=durable;host.controller.budget.transport=durable
                host.sampler=SimpleNamespace(scope=test.scope);native,args=artificial();host.latest=args['lawful_view']
                host.production_tick=lambda n,**kwargs:candidate_production_tick_v1(host,n,gate_arguments=args,**kwargs)
                self.assertTrue(host.consume_observation(native))
                self.assertTrue({'budgetarmy','scout','deployattack'}<=set(host.latest['macro_control']['available_actions']))
                self.assertTrue(set(host.latest['macro_control']['available_actions'])<=independent.STRATEGIC_ACTIONS)
                self.assertEqual(host.latest['macro_control']['production_counts'],{})
                calls=[]
                async def model(context):
                    calls.append(context)
                    result=independent.base.model_policy(context)
                    result.update(macro_actions=[action],objective_region='region_1_3' if action=='deployattack' else None)
                    return result
                audit=MacroRequestAudit(model,lambda *args,**kwargs:None,strategic_only=True)
                decision=asyncio.run(host.agent.decide(host.latest,audit))
                self.assertEqual(decision.status,'accepted',decision.reason_code)
                self.assertTrue(host.dispatch_plan(decision.plan))
                self.assertEqual(host.transport.calls[0][0],[action])
                self.assertEqual(len(host.journal.commands_for_run(host.run_id)),1)
                self.assertNotIn('macro_production_feedback',calls[0]);self.assertIsNone(host.last_infrastructure)
                self.assertEqual(host.capability_sample_kind,'strategic_optional_builder_queue_race_v1')


if __name__=='__main__':unittest.main()
