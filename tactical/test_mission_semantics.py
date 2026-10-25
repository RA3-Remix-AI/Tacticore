"""Semantic boundary tests; mocked native verifier never represents field proof."""
import copy
from dataclasses import replace
import unittest
from unittest.mock import patch
import uuid

import mission_qualification as semantics


class HarassSemantics(unittest.TestCase):
    def setUp(self):
        route=semantics.TrustedHarassRoute(str(uuid.uuid4()),123,3,str(uuid.uuid4()),str(uuid.uuid4()),str(uuid.uuid4()),11,'contact_refinery',22,'0xc45aaeab','economy',1000,4000,'home_base','own_actor_history',(100.,200.,210.))
        child_command=str(uuid.uuid5(uuid.UUID(route.command_id),'11'));child_task=str(uuid.uuid5(uuid.UUID(route.mission_id),'11'))
        binding=dict(session_id=route.session_id,commander_id=route.commander_id)
        request=dict(command_id=child_command,task_id=child_task,seq=1,target_role='economy',target_object_id=22,target_contact_id='contact_refinery',mission_protocol='continuous_tactical_v1',expires_frame=4000,mission=dict(expires_frame=4000,retreat_point=dict(source='own_actor_history',xyz=[100.,200.,210.])))
        self.route=route;self.report=dict(session_id=route.session_id,native_binary_sha256=semantics.NATIVE_BUILDS['mission-combat'][1],preflight=dict(**binding,pid=123,player_id=3,selected=dict(object_id=11,type_hash='0x19ab11af')),native=dict(**binding,command_id=child_command,task_id=child_task,seq=1,mission_deadline_frame=4000,issued_frame=1005,returned_frame=3000,retreat_goal=[100.,200.,210.]),request=request,private_target=dict(object_id=22,type_hash='0xc45aaeab',owner_player_id=4))
        self.native=dict(status='continuous_ak_combat_mission_verified',checks={'all_native_checks':True},effect_verified=True,harass_economy_verified=True,source_damage_amount=5,approach_verified=True,retreat_verified=True,restoration_verified=True)
        self.receipt=dict(module='raid',purpose='harass_economy',session_id=route.session_id,commander_id=route.commander_id,player_id=3,task_id=route.mission_id,command_id=route.command_id,status='completed',completed=True,goal_observed=True,restoration_verified=True,object_ids=[11],target_contact_id='contact_refinery')

    def assess(self,report=None,route=None,receipt=None,base=None):
        with patch.object(semantics.native,'qualify',return_value=base if base is not None else self.native):
            return semantics.qualify(report or self.report,route or self.route,receipt)

    def test_exact_economy_chain_stays_separate_from_formal_model_task_provenance(self):
        calibration=self.assess();self.assertTrue(calibration['harass_economy_verified']);self.assertIsNone(calibration['formal_harass_verified'])
        formal=self.assess(receipt=self.receipt);self.assertTrue(formal['formal_harass_verified'])

    def test_main_attack_label_cannot_replace_formal_harassment_receipt(self):
        receipt=dict(self.receipt,module='attack',purpose='main_attack')
        self.assertFalse(self.assess(receipt=receipt)['formal_harass_verified'])
        self.assertFalse(self.assess(route=replace(self.route,module='attack',purpose='main_attack'))['harass_economy_verified'])

    def test_structure_cannot_be_renamed_economy(self):
        report=copy.deepcopy(self.report);report['private_target']['type_hash']='0x21c3a734'
        self.assertFalse(self.assess(report=report)['harass_economy_verified'])
        route=replace(self.route,target_type_hash='0x21c3a734')
        self.assertFalse(self.assess(report,route)['harass_economy_verified'])

    def test_contact_actor_and_child_command_are_frozen(self):
        for parent,key,value in [('request','target_contact_id','contact_other'),('private_target','object_id',23),('native','command_id',str(uuid.uuid4())),('native','task_id',str(uuid.uuid4()))]:
            report=copy.deepcopy(self.report);report[parent][key]=value
            with self.subTest(key=key):self.assertFalse(self.assess(report=report)['harass_economy_verified'])
        self.assertFalse(self.assess(route=replace(self.route,actor_id=12))['harass_economy_verified'])

    def test_other_session_commander_or_pid_cannot_reuse_effect(self):
        for key,value in [('session_id',str(uuid.uuid4())),('commander_id',str(uuid.uuid4())),('pid',124)]:
            with self.subTest(key=key):self.assertFalse(self.assess(route=replace(self.route,**{key:value}))['harass_economy_verified'])

    def test_retreat_cannot_be_missing_retargeted_or_sourced_from_model(self):
        for source,xyz in [('model',(100.,200.,210.)),('own_actor_history',(101.,200.,210.))]:
            self.assertFalse(self.assess(route=replace(self.route,retreat_source=source,retreat_xyz=xyz))['harass_economy_verified'])
        report=copy.deepcopy(self.report);report['request']['mission'].pop('retreat_point')
        self.assertFalse(self.assess(report=report)['harass_economy_verified'])

    def test_plan_refresh_cannot_extend_deadline(self):
        report=copy.deepcopy(self.report);report['native']['mission_deadline_frame']=4100
        self.assertFalse(self.assess(report=report)['harass_economy_verified'])

    def test_damage_summary_without_native_chain_or_retreat_does_not_pass(self):
        for base in [dict(self.native,checks={'raw_return':False}),dict(self.native,checks={'raw_return':1}),dict(self.native,retreat_verified=False),dict(self.native,approach_verified=False),dict(self.native,effect_verified=False,source_damage_amount=999),dict(self.native,source_damage_amount=0)]:
            with self.subTest(base=base):self.assertFalse(self.assess(base=base)['harass_economy_verified'])

    def test_receipt_wrong_task_actor_or_boolean_claim_is_not_formal_success(self):
        for key,value in [('task_id',str(uuid.uuid4())),('object_ids',[12]),('completed',1),('restoration_verified',False)]:
            self.assertFalse(self.assess(receipt=dict(self.receipt,**{key:value}))['formal_harass_verified'])

    def test_untrusted_dictionary_is_not_a_host_route(self):
        with self.assertRaisesRegex(ValueError,'trusted_harass_route_required'):semantics.qualify(self.report,dict(module='raid'))

    def test_reviewed_v1_v2_v3_use_only_their_exact_qualifier(self):
        for directory,spec in semantics.NATIVE_BUILDS.items():
            route=replace(self.route,executor_directory=directory)
            report=dict(self.report,native_binary_sha256=spec[1])
            backend=semantics.native_backend(report,route)
            self.assertIsNotNone(backend)
            with self.subTest(directory=directory),patch.object(backend,'qualify',return_value=self.native) as selected:
                result=semantics.qualify(report,route,self.receipt)
                self.assertTrue(result['formal_harass_verified']);selected.assert_called_once_with(report)
                self.assertEqual(result['native_executor_directory'],directory)

    def test_unknown_bin_and_cross_version_directory_never_call_v1(self):
        cases=[(dict(self.report,native_binary_sha256='0'*64),self.route),
               (self.report,replace(self.route,executor_directory='unknown')),
               (self.report,replace(self.route,executor_directory='mission-combat-v3')),
               (dict(self.report,executor_directory='mission-combat-v2'),self.route)]
        for report,route in cases:
            with self.subTest(directory=route.executor_directory),patch.object(semantics.native,'qualify') as fallback:
                result=semantics.qualify(report,route)
                self.assertFalse(result['harass_economy_verified']);fallback.assert_not_called()

    def test_runtime_dll_or_qualifier_drift_fails_closed(self):
        original=semantics.Path.read_bytes
        def altered(path):return b'drift' if path.name=='mission_combat_qualification.py' else original(path)
        with patch.object(semantics.Path,'read_bytes',altered),patch.object(semantics.native,'qualify') as delegated:
            self.assertFalse(semantics.qualify(self.report,self.route)['harass_economy_verified']);delegated.assert_not_called()


if __name__=='__main__':unittest.main()
