"""Exercise normal Native7 admission surfaces without opening a Game."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from host_runtime.contracts import ContractError
from host_runtime.native6_presence import query_macro_objects
from host_runtime.native7_qualification import Native7Scope
from host_runtime.native7_runtime_contract import PACKAGE_SHA,FLAG_ACTIONS,FLAGS,FIELD_KIND
from host_runtime.strategic_unified_controller_v5 import UnifiedStrategicControllerV5
from macro_host import MacroHost,is_unified_scope,native_transport_config


class Native7Entrypoints(unittest.TestCase):
    def test_full_prepared_request_runs_the_real_catalog_and_six_domain_feedback_checks(self):
        scope=Native7Scope(PACKAGE_SHA,tuple(zip(FLAG_ACTIONS,FLAGS)),
            (('deploydefense','region_7_1'),),(),required_origin_region='region_7_1')
        self.check_prepared_scope(scope)

    def test_duel_prepared_request_has_one_opponent_and_no_enemy_focus_actions(self):
        scope=Native7Scope(PACKAGE_SHA,tuple(zip(FLAG_ACTIONS,FLAGS)),
            (('deploydefense','region_7_4'),),(),required_origin_region='region_7_4',opponent_player_ids=(4,))
        self.assertEqual(len(scope.available_actions),15)
        self.assertFalse({'focusenemy4','focusenemy5'}&set(scope.available_actions))
        self.check_prepared_scope(scope)

    def check_prepared_scope(self,scope):
        from fixtures import binding,snapshot
        from engine import StrategyEngine,ContractError as StrategyContractError
        from battle_agent import BattleAgent
        from macro_strategy import MacroStrategyMemory
        from macro_policy import ACTIONS
        from host_runtime.strategic_unified_feedback_v5 import UnifiedRequestAuditV5
        from host_runtime.macro_prepared_request_v1 import prepare_macro_request_v1,encoded
        identity=binding();engine=StrategyEngine(identity)
        agent=BattleAgent(engine,context_budget_bytes=32768)
        raw=snapshot(macro_control=dict(mode='macro_native',available_actions=list(scope.available_actions),
            region_targets={action:scope.required_origin_region for action in scope.available_actions if ACTIONS[action]=='deployment'},
            intent_contract=scope.intent_contract))
        raw['capabilities']=dict(production_focus=['native_baseline'],regions=[scope.required_origin_region])
        agent.observe(raw)
        class Backend:
            max_input_bytes=32768
            def input_size(self,context):return len(encoded(context))
        memory=MacroStrategyMemory(session_id=identity.session_id,commander_id=identity.commander_id,
            player_id=3,profile_revision=1,effective_hash='a'*64)
        actions=('deploydefense','expand','budgetarmy','focusenemy4','advanceconstruction','advanceproduction')
        actions=tuple(action for action in actions if action in scope.available_actions)
        rows=[dict(action=action,status='native_waiting_or_no_effect',observed_frame=1500,
            preference_active=True,active_native_task_observed=False,movement_observed=False,
            component_state_adopted=False,state_already_satisfied=False,mission_success_verified=False,
            exclusive_attribution_verified=False) for action in actions]
        audit=UnifiedRequestAuditV5(Backend(),lambda *args,**kwargs:None,strategic_only=True,
            feedback_supplier=lambda:dict(status='native_delegation_observed',selected_policy=None,actions=[],
                observed_frame=1500,native_effect_verified=False),catalog_supplier=scope.model_catalog_overrides,
            unified_supplier=lambda:dict(source='bound_native_strategy_v7',observed_frame=1500,
                details_owner='native_ai',observations=rows),strategy_supplier=memory.context)
        prepared=prepare_macro_request_v1(agent,audit,agent.latest)
        context=agent.context(agent.latest.model_context(identity),commit=False)
        result=prepared.measure.prepare(context)
        self.assertIn('raideconomy',result['macro_policy_catalog'])
        self.assertEqual(len(result['macro_unified_feedback']['observations']),len(actions))
        self.assertEqual(result['macro_intent_contract'],scope.intent_contract)
        self.assertLess(prepared.measure.input_size(context),32768)
        changed=scope.model_catalog_overrides();changed['raideconomy']['target_policy']='invented_target'
        audit.catalog_supplier=lambda:changed
        with self.assertRaises(StrategyContractError):prepare_macro_request_v1(agent,audit,agent.latest)

    def test_observer_binding_and_receipt_validation_accept_the_qualified_raid_flag(self):
        from host_runtime.native7_strategic_observer import FLAGS as observer_flags
        from host_runtime.native7_observation import bind_transport,validate_sample
        self.assertEqual(observer_flags,FLAGS)
        own=dict(ai_player='0x20000',personality_wrapper='0x30000',player_template='0x40000')
        state=dict(magic=0x53434737,version=7,size=4672,pid=1234,start_low=9,start_high=0,
            owner=0x10000,engine=0x50000,ai=0x20000,personality=0x30000,player_template=0x40000,
            raw_binding={},phase=1,error=0,hook_held=1,lease_held=1,request=1,ack=1,
            applied_mask=1<<10,gates=[],active=0,flag_phase=1,flag_deadline=300,focus={})
        transport=SimpleNamespace(native_status=lambda:state,native=own,creation=9,owner=0x10000,
            memory=SimpleNamespace(u32=lambda address:0x50000),
            manifest=dict(protocol_version=7,flags=list(FLAGS)))
        bound=bind_transport(transport,dict(pid=1234,process_creation_filetime=9))
        sample=dict(unified_native=state,observation=dict(observation_complete=False))
        self.assertIsNone(validate_sample(sample,None,transport,bound))
        state['applied_mask']=1<<11
        with self.assertRaises(ContractError):validate_sample(sample,None,transport,bound)
        transport.manifest['flags']=list(FLAGS[:-1])
        with self.assertRaises(ContractError):bind_transport(transport,dict(pid=1234,process_creation_filetime=9))

    def test_request_audit_enforces_the_backend_input_limit_in_actual_send_path(self):
        import asyncio
        from host_runtime.macro_policy_runtime import MacroRequestAudit
        class Backend:
            max_input_bytes=32768
            def input_size(self,context):return 19000
            async def __call__(self,context):return dict(received=True)
        backend=Backend()
        audit=MacroRequestAudit(backend,lambda *args,**kwargs:None)
        context=dict(control_mode='macro_native',padding='x'*18000)
        self.assertEqual(asyncio.run(audit(context)),dict(received=True))
        self.assertEqual(audit.sequence,1)
        backend.max_input_bytes=16384
        with self.assertRaisesRegex(ContractError,'bounds'):asyncio.run(audit(context))
        self.assertEqual(audit.sequence,1)

    def test_new_catalog_reaches_the_actual_capacity_admission(self):
        from fixtures import binding,snapshot
        from engine import Snapshot
        from macro_policy import ACTIONS,public_descriptions
        from host_runtime.profiles import normalize_profile
        from host_runtime.native5_capacity_preflight_v1 import check_native5_capacity,INDEPENDENT_ACTIONS
        scope=Native7Scope(PACKAGE_SHA,tuple(zip(FLAG_ACTIONS,FLAGS)),(),(),required_origin_region='region_7_1')
        identity=binding()
        raw=snapshot()
        raw['capabilities']['regions']=['region_7_1']
        raw['macro_control']=dict(mode='macro_native',available_actions=['budgetarmy'],region_targets={},
            intent_contract=scope.intent_contract)
        observed=Snapshot.from_dict(raw)
        targets={a:'region_7_1' for a in scope.available_actions if ACTIONS[a]=='deployment'}
        catalog=public_descriptions(scope.available_actions,region_targets=targets)
        catalog.update(scope.model_catalog_overrides())
        self.assertEqual(set(catalog),INDEPENDENT_ACTIONS)
        effective=normalize_profile(dict(schema_version=1,profile_id=identity.commander_id,name='Offline',
            revision=31,connection_id=identity.connection_id,model='fixture-model',doctrine='defense',custom_traits=''))
        result=check_native5_capacity(effective,'DeepSeek',raw,catalog)
        self.assertTrue(result['fits'],result)
        self.assertEqual(result['catalog_action_count'],17)
        self.assertEqual(result['maximum_bytes'],scope.maximum_model_input_bytes)
        self.assertFalse(result['native_authority_granted'])

    def test_same_qualified_scope_reaches_host_and_observation_capabilities(self):
        scope=Native7Scope(PACKAGE_SHA,tuple(zip(FLAG_ACTIONS,FLAGS)),(('deploydefense','region_7_1'),),(),
            required_origin_region='region_7_1',runtime_manifest_sha256='a'*64)
        manifest=dict(kind=FIELD_KIND,protocol_version=7,package_sha256=PACKAGE_SHA,
            admission_ready=True,compile_only=False,flags=list(FLAGS))
        self.assertTrue(is_unified_scope(scope))
        self.assertEqual(native_transport_config(scope,manifest)['protocol_version'],7)
        controller=UnifiedStrategicControllerV5.__new__(UnifiedStrategicControllerV5)
        controller.scope=scope;controller.stopped=False
        host=MacroHost.__new__(MacroHost)
        host.sampler=SimpleNamespace(scope=scope);host.controller=controller
        host.latest=dict(paused=False);host.strategic_only=True
        host.update_macro_control(1.)
        control=host.latest['macro_control']
        self.assertIn('raideconomy',control['available_actions'])
        self.assertIn('expand',control['available_actions'])
        self.assertIn('deploydefense',control['available_actions'])
        self.assertEqual(control['intent_contract'],'native7_independent_development_v1')
        self.assertEqual(control['region_targets'],{'deploydefense':'region_7_1'})

    def test_native7_mapping_prefix_is_supported_by_independent_readonly_query(self):
        kernel=SimpleNamespace(OpenFileMappingW=Mock(return_value=0),OpenSemaphoreW=Mock(return_value=0),CloseHandle=Mock())
        ntdll=SimpleNamespace(NtQuerySemaphore=Mock())
        result=query_macro_objects(1234,'Local\\RA3StrategicCommanderV7_',kernel=kernel,
            ntdll=ntdll,last_error=lambda:2)
        self.assertEqual(result['mapping_name'],'Local\\RA3StrategicCommanderV7_1234')
        self.assertEqual(result['mapping_status'],'absent')
        self.assertEqual(result['semaphore_status'],'absent')
        self.assertEqual(result['acquire_or_wait_calls'],0)
        with self.assertRaises(ContractError):query_macro_objects(1234,'Local\\RA3StrategicCommanderV8_')


class ScenarioScopes(unittest.TestCase):
    """Runtime scopes follow the derived scenario instead of a per-map table."""
    def scenario(self,others,alliances=(),own=(3700.,800.)):
        from host_runtime.scenario import derive_scenario
        starts=[dict(name='Player_%d_Start'%index,xyz=[x,y,0.]) for index,(x,y) in
                enumerate(((700.,700.),(3800.,700.),(700.,3800.),(3800.,3800.)),1)]
        rows=[dict(player_id=3,kind='model_ai',relation='self')]+[dict(player_id=index,kind=kind,relation=relation)
            for index,kind,relation in others]
        return derive_scenario(map_id='any map',model_player_id=3,participants=rows,alliances=alliances,
            own_point=own,starts=starts)

    def test_focus_actions_follow_actual_enemies_the_lease_can_prefer(self):
        scope=Native7Scope(PACKAGE_SHA,tuple(zip(FLAG_ACTIONS,FLAGS)),(),(),required_origin_region='region_7_1',
            opponent_player_ids=(4,5))
        self.assertEqual(scope.focus_actions,('focusenemy4','focusenemy5'))
        self.assertEqual(scope.model_catalog_overrides()['focusenemy5']['target_player_id'],5)
        for enemies in ((4,),(2,4),(4,6)):
            with self.subTest(enemies=enemies):
                scope=Native7Scope(PACKAGE_SHA,tuple(zip(FLAG_ACTIONS,FLAGS)),(),(),
                    required_origin_region='region_7_1',opponent_player_ids=enemies)
                self.assertEqual(scope.focus_actions,())
                self.assertFalse({a for a in scope.available_actions if a.startswith('focusenemy')})

    def test_withheld_home_waypoint_actions_are_not_offered(self):
        from host_runtime.native6_qualification import Native6Scope
        from host_runtime.native6_runtime_contract import ACTIONS as N6_ACTIONS,FLAGS as N6_FLAGS
        scope=Native6Scope(PACKAGE_SHA,tuple(zip(N6_ACTIONS,N6_FLAGS)),(),(),required_origin_region='region_1_7',
            withheld_actions=('regroup','withdraw'))
        self.assertNotIn('regroup',scope.available_actions)
        self.assertIn('deploydefense',scope.available_actions)

    def test_native7_participant_support_mirrors_the_compiled_focus_snapshot(self):
        from host_runtime.native7_qualification import native7_participants_supported
        supported=[self.scenario(((4,'native_ai','enemy'),)),
                   self.scenario(((4,'native_ai','enemy'),(5,'native_ai','enemy')),alliances=[[4,5]])]
        unsupported=[self.scenario(((2,'human','ally'),(4,'native_ai','enemy'))),
                     self.scenario(((2,'human','enemy'),)),
                     self.scenario(((4,'native_ai','enemy'),(5,'native_ai','enemy'))),
                     self.scenario(((5,'native_ai','enemy'),))]
        self.assertTrue(all(native7_participants_supported(value) for value in supported))
        self.assertFalse(any(native7_participants_supported(value) for value in unsupported))

    def test_strategic_catalog_audit_rebuilds_from_the_named_home_region(self):
        from host_runtime.macro_policy_runtime import strategic_catalogs
        from host_runtime.strategic_contract_v5 import INDEPENDENT_DEVELOPMENT_CONTRACT
        scope=Native7Scope(PACKAGE_SHA,tuple(zip(FLAG_ACTIONS,FLAGS)),(),(),required_origin_region='region_0_12')
        overrides=scope.model_catalog_overrides()
        context=dict(macro_intent_contract=INDEPENDENT_DEVELOPMENT_CONTRACT)
        self.assertIn(overrides,strategic_catalogs(overrides,context))
        changed=dict(overrides,regroup=dict(overrides['regroup'],target_region='region_1_1'))
        self.assertNotIn(changed,strategic_catalogs(changed,context))
        self.assertEqual(strategic_catalogs({},context),())


if __name__=='__main__':unittest.main()
