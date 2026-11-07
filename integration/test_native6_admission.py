"""Authority and lawful-view rejection tests; no Game/model access."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from host_runtime import native6_qualification as q
from host_runtime import native6_visibility as visibility
from host_runtime.contracts import ContractError
from host_runtime.native6_no_attachment import verified_capture,KIND


class Admission(unittest.TestCase):
    def test_map_scope_uses_its_own_regions_and_preserves_original_descriptors(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'trial.json'
            path.write_text(json.dumps(dict(schema_version=14,kind=q.KIND,
                runtime_root=str(root),runtime_manifest_sha256='a'*64)))
            authority=(root,'a'*64,dict(files={}),{}, {})
            scenario=dict(map_id=q.MAP_ID,commander_id=q.COMMANDER,computer_player_index=3,
                opponent_player_index=4,observer_player_index=2,participant_count=2)
            session=dict(mod_sha256=q.PACKAGE_SHA,registry=str(root/'qualification/registry.json'),scenario=scenario)
            with patch.object(q,'current',return_value=authority):
                _,old=q.load(path,session)
                self.assertEqual(old.required_origin_region,'region_8_3')
                self.assertEqual(old.region_pairs,q.REGIONS)
                scenario.update(map_id='map_mp_2_rao1',origin_region='region_7_4',faction='Soviet')
                _,new=q.load(path,session)
                self.assertEqual(new.required_origin_region,'region_7_4')
                self.assertEqual(new.regional_action_regions['deployattack'],'region_2_3')
                self.assertEqual(new.regional_action_regions['withdraw'],'region_7_4')
                catalog=new.model_catalog_overrides()
                self.assertEqual(catalog['withdraw']['target_region'],'region_7_4')
                self.assertEqual(catalog['deploydefense']['target_region'],'region_7_4')
                self.assertNotIn('eastern',catalog['reinforce']['region_semantics'])
                self.assertEqual(new.available_actions,old.available_actions)
                self.assertFalse(new.public()['product_model_and_client_acceptance_verified'])
                self.assertEqual(new.public()['formal_natural_games'],0)
                for change in ({'origin_region':'region_8_3'},{'faction':'Allied'},
                               {'map_id':'map_mp_2_other'},{'computer_player_index':True}):
                    with self.subTest(change=change):
                        bad=copy.deepcopy(session);bad['scenario'].update(change)
                        with self.assertRaises(ContractError):q.load(path,bad)
                for missing in ('faction','origin_region'):
                    bad=copy.deepcopy(session);bad['scenario'].pop(missing)
                    with self.assertRaises(ContractError):q.load(path,bad)

    def test_sdk_additional_map_requires_explicit_matching_origin_and_faction(self):
        root=Path('C:/runtime');manifest={'fixture':True}
        session=dict(mod_sha256=q.PACKAGE_SHA,scenario=dict(map_id='map_mp_2_rao1',
            commander_id=q.COMMANDER,computer_player_index=3,origin_region='region_7_4',faction='Soviet'))
        with patch.object(q,'current',return_value=(root,'a'*64,{},manifest,{})):
            self.assertEqual(q.admit_sdk(root/'native/strategic6',session),manifest)
            session['scenario']['origin_region']='region_8_3'
            with self.assertRaises(ContractError):q.admit_sdk(root/'native/strategic6',session)

    def test_developer_tree_and_inherited_pin_cannot_create_authority(self):
        with patch.dict(os.environ,TACTICORE_RUNTIME_MANIFEST_SHA256='a'*64):
            with self.assertRaises(ContractError):q.current()

    def test_descriptor_fields_and_manifest_pin_rechecked_each_load(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'trial.json'
            descriptor=dict(schema_version=14,kind=q.KIND,runtime_root=str(root),runtime_manifest_sha256='a'*64)
            inventory=dict(files={});manifest={}
            authority=(root,'a'*64,inventory,manifest,{})
            with patch.object(q,'current',return_value=authority) as current:
                path.write_text(json.dumps(descriptor),encoding='utf-8')
                _,scope=q.load(path)
                self.assertEqual(scope.native_transport_protocol,6)
                self.assertEqual(len(scope.available_actions),14)
                current.return_value=(root,'b'*64,inventory,manifest,{})
                with self.assertRaises(ContractError):q.load(path)
                current.return_value=authority
                for change in ({'product_acceptance_verified':True},{'schema_version':13},{'runtime_root':str(root/'other')}):
                    path.write_text(json.dumps(dict(descriptor,**change)),encoding='utf-8')
                    with self.assertRaises(ContractError):q.load(path)

    def test_missing_pin_rejected_before_reading_inventory_or_build(self):
        with patch.object(q,'verify_inventory') as inventory:
            for pin in (None,'','A'*64,True):
                with self.assertRaises(ContractError):q.verify_qualification(Path('C:/unused'),pin)
            inventory.assert_not_called()

    def test_observer_or_wrong_package_denied_before_memory_reads(self):
        memory=SimpleNamespace(read=lambda *_:self.fail('unqualified memory read'))
        for viewer in (2,4,True,'3'):
            with self.assertRaises(ValueError):visibility.bind_session(memory,{},viewer)
        with patch.object(visibility,'current',return_value=(Path('C:/runtime'),'a'*64,{}, {},dict(package_sha256=q.PACKAGE_SHA))):
            with self.assertRaises(ValueError):visibility.bind_session(memory,dict(mod_sha256='b'*64,registry='C:/other'),3)

    def test_native_signature_drift_rejected_before_world_or_shroud_reads(self):
        session=dict(mod_sha256=q.PACKAGE_SHA,registry='C:/runtime/qualification/registry.json',pid=123)
        memory=SimpleNamespace(pid=123,read=lambda *_:b'\x01'*24,u32=lambda *_:self.fail('world read after signature mismatch'))
        cap=dict(package_sha256=q.PACKAGE_SHA,safety={},expected_signatures={'0x992130':'00'*24})
        with patch.object(visibility,'current',return_value=(Path('C:/runtime'),'a'*64,{}, {},cap)):
            with self.assertRaisesRegex(ValueError,'signature changed'):visibility.bind_session(memory,session,3)

    def test_no_attachment_requires_native6_mapping_both_times(self):
        binding=SimpleNamespace(game_process_id=123,game_sha256='a'*64,public=lambda:dict(epoch='fixture'))
        session=dict(game='C:/Game/RA3_1.12.game',process_creation_filetime=456)
        objects=dict(source='win32_read_only_macro_channel_and_semaphore_v1',mapping_name='Local\\RA3StrategicCommanderV6_123',
            semaphore_name='Local\\RA3MacroPolicyLease_123',mapping_status='absent',semaphore_status='absent',
            mapping_open_error=2,semaphore_open_error=2,native_writes=0,acquire_or_wait_calls=0)
        proof=dict(kind=KIND,schema_version=1,run_id='run',binding=binding.public(),actual_OS_before=dict(pid=123,process_creation_filetime=456),
            actual_OS_after=dict(pid=123,process_creation_filetime=456),policy_modules_before=[],policy_modules_after=[],
            no_control_acquired=True,manager_restoration_claimed=False,mission_effect_verified=False,
            image_before=str(Path(session['game']).resolve()),image_after=str(Path(session['game']).resolve()),image_sha256='a'*64,
            started_monotonic_ns=1,ended_monotonic_ns=10,objects_before=objects,objects_after=copy.deepcopy(objects))
        self.assertTrue(verified_capture(proof,session,binding,'run'))
        for side in ('objects_before','objects_after'):
            wrong=copy.deepcopy(proof);wrong[side]['mapping_name']='Local\\RA3StrategicCommanderV5_123'
            self.assertFalse(verified_capture(wrong,session,binding,'run'))
        proof['policy_modules_after']=['manager_native.dll']
        self.assertFalse(verified_capture(proof,session,binding,'run'))


class ModelEntry(unittest.IsolatedAsyncioTestCase):
    def scopes(self):
        from host_runtime.native6_scenarios import TEMPLE_PRIME, INFINITY_ISLE
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            trial = root/'trial.json'
            trial.write_text(json.dumps(dict(schema_version=14, kind=q.KIND,
                runtime_root=str(root), runtime_manifest_sha256='a'*64)))
            with patch.object(q, 'current', return_value=(root, 'a'*64, dict(files={}), {}, {})):
                result = []
                for scenario in (TEMPLE_PRIME, INFINITY_ISLE):
                    session = dict(mod_sha256=q.PACKAGE_SHA, registry=str(root/'qualification/registry.json'),
                        scenario=dict(map_id=scenario.map_id, origin_region=scenario.own_region, faction='Soviet',
                            commander_id=q.COMMANDER, computer_player_index=3, opponent_player_index=4,
                            observer_player_index=2, participant_count=2))
                    result.append(q.load(trial, session)[1])
                return result

    def audit(self, scope, backend=None, strategy=None):
        from host_runtime.strategic_unified_feedback_v5 import UnifiedRequestAuditV5
        feedback = dict(status='native_delegation_observed', selected_policy=None, actions=[],
            observed_frame=1500, native_effect_verified=False)
        unified = dict(source='bound_native_strategy_v5', observed_frame=1500,
            details_owner='native_ai', observations=[])
        return UnifiedRequestAuditV5(backend, lambda *a, **k: None,
            feedback_supplier=lambda: feedback, unified_supplier=lambda: unified,
            catalog_supplier=scope.model_catalog_overrides, strategy_supplier=strategy, strategic_only=True)

    async def test_both_loaded_scopes_reach_normal_prepared_agent_and_backend(self):
        from battle_agent import BattleAgent
        from engine import StrategyEngine
        from fixtures import binding, policy, snapshot
        from macro_policy import restore_public_defaults
        from macro_strategy import MacroStrategyMemory
        from test_macro_strategy import declaration
        from test_macro_strategy_integration import encoder
        from host_runtime.macro_prepared_request_v1 import prepare_macro_request_v1, decide_prepared_macro_request_v1

        for scope in self.scopes():
            with self.subTest(home=scope.required_origin_region):
                identity = binding(commander=q.COMMANDER)
                raw = snapshot(capabilities=dict(production_focus=['native_baseline'],
                    regions=sorted(set(scope.regional_action_regions.values()))),
                    macro_control=dict(mode='macro_native', available_actions=list(scope.available_actions),
                        production_counts={}, region_targets=scope.regional_action_regions))
                agent = BattleAgent(StrategyEngine(identity), context_budget_bytes=16384)
                agent.observe(raw)
                memory = MacroStrategyMemory(session_id=identity.session_id, commander_id=q.COMMANDER,
                    player_id=3, profile_revision=1, effective_hash='a'*64)
                wire = encoder()
                class Backend:
                    def input_size(self, context):
                        return wire.input_size(context)
                    async def __call__(self, context):
                        self.sent = copy.deepcopy(context)
                        return policy(context, production_focus='native_baseline',
                            objective_region=scope.required_origin_region, macro_actions=['regroup'],
                            macro_strategy=declaration(objective='hold', phase='prepare'))
                backend = Backend()
                audit = self.audit(scope, backend, memory.context)
                prepared = prepare_macro_request_v1(agent, audit, agent.latest)
                result = await decide_prepared_macro_request_v1(agent, agent.latest, prepared)
                self.assertEqual(result.status, 'accepted', result)
                context = restore_public_defaults(backend.sent)
                self.assertEqual(set(context['macro_policy_catalog']), set(scope.available_actions))
                for action in ('deploydefense', 'regroup', 'withdraw', 'reinforce'):
                    self.assertEqual(context['macro_policy_catalog'][action]['target_region'], scope.required_origin_region)
                self.assertEqual(context['macro_policy_catalog']['deployattack']['target_region'],
                    scope.regional_action_regions['deployattack'])
                self.assertEqual(context['allowed_production_focus'], ['native_baseline'])
                self.assertLessEqual(wire.input_size(backend.sent), 16384)
                self.assertEqual(audit.request_context_for(result.plan), backend.sent)
                self.assertEqual(agent.engine.metrics['requests'], 1)

    def test_wrong_anchor_changed_definition_and_non_strategic_entry_are_refused(self):
        from macro_policy import public_descriptions
        for scope in self.scopes():
            context = dict(game_time_seconds=100., allowed_macro_actions=list(scope.available_actions),
                macro_policy_catalog=public_descriptions(scope.available_actions,
                    region_targets=scope.regional_action_regions.items()))
            for wrong in ('region_0_0', 'region_7_4' if scope.required_origin_region=='region_8_3' else 'region_8_3'):
                for action in ('deploydefense', 'regroup', 'withdraw', 'reinforce'):
                    changed = copy.deepcopy(context)
                    changed['macro_policy_catalog'][action]['target_region'] = wrong
                    with self.subTest(home=scope.required_origin_region, wrong=wrong, action=action):
                        with self.assertRaisesRegex(ContractError, 'region_binding'):
                            self.audit(scope).prepare(changed)
            for field, value in (('maximum_duration_seconds', 3600), ('target_region', 'region_0_0')):
                audit = self.audit(scope)
                changed = scope.model_catalog_overrides()
                changed['regroup'][field] = value
                audit.catalog_supplier = lambda: changed
                with self.assertRaisesRegex(ContractError, 'catalog_invalid'):
                    audit.prepare(context)
            audit = self.audit(scope)
            audit.strategic_only = False
            with self.assertRaisesRegex(ContractError, 'catalog_invalid'):
                audit.prepare(context)


if __name__=='__main__':unittest.main()
