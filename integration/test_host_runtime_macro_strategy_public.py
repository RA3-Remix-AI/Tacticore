"""UI privacy and field-isolated status projection, without a game/provider."""
import copy
from dataclasses import replace
import json
import unittest
import uuid

import macro_host  # Establish the same immutable strategy import root as Host.
from macro_strategy import MacroStrategyMemory
from test_macro_strategy import SESSION,COMMANDER,context,declaration,plan
from host_runtime.contracts import ContractError,SessionBinding
from host_runtime.macro_strategy_public import project_macro_strategy_state
import test_host_runtime_desktop_backend as fixture


def public_state():
    memory=MacroStrategyMemory(session_id=SESSION,commander_id=COMMANDER,player_id=3,
        profile_revision=21,effective_hash='a'*64)
    p=plan();review=memory.review(p,declaration(),context())
    memory.record_dispatch(review,command_id='PRIVATE_COMMAND',game_seconds=10)
    memory.record_outcome(command_id='PRIVATE_COMMAND',plan_id=p['plan_id'],outcome='effect_observed',
        game_seconds=12,observed_game_seconds=11,effect_verified=True)
    return memory.public_state()


class StrategyProjectionTests(unittest.TestCase):
    def test_only_whitelisted_public_fields_cross_and_result_is_detached(self):
        raw=public_state()
        raw.update(raw_model_response='PRIVATE_RESPONSE',commands={'PRIVATE_COMMAND':{'api_key':'PRIVATE_KEY'}})
        raw['current_strategy'].update(native_address='PRIVATE_ADDRESS',notes='PRIVATE_NOTES')
        raw['current_strategy']['last_outcome'].update(native_release_verified=True,payment_verified=True,raw_hex='PRIVATE_HEX')
        projected=project_macro_strategy_state(raw)
        self.assertNotIn('PRIVATE',json.dumps(projected))
        self.assertNotIn('native_release_verified',projected['current_strategy']['last_outcome'])
        self.assertTrue(projected['current_strategy']['last_outcome']['effect_verified'])
        projected['current_strategy']['public_fact_refs'].append('changed')
        projected['recent_outcomes'][0]['outcome']='changed'
        self.assertEqual(raw['current_strategy']['public_fact_refs'],['own.credits'])
        self.assertEqual(raw['recent_outcomes'][0]['outcome'],'effect_observed')

    def test_invalid_top_level_values_cannot_be_cast_to_truth_or_counts(self):
        for changes in ({'schema_version':True},{'kind':'future_unvalidated_state'},{'stopped':1},
            {'unknown_command_count':True},{'unknown_command_count':-1},{'unreleased_command_count':65},
            {'unknown_command_count':2,'unreleased_command_count':1},{'recent_outcomes':[{}]*5},
            {'last_guard_reason':'provider payload PRIVATE'},{'current_strategy':[]}):
            with self.subTest(changes=changes),self.assertRaises(ContractError):
                project_macro_strategy_state(dict(public_state(),**changes))
        raw=public_state();del raw['last_guard_reason']
        with self.assertRaises(ContractError):project_macro_strategy_state(raw)

    def test_current_strategy_enums_uuid_and_fact_refs_are_strict(self):
        for changes in ({'objective':'PRIVATE_GOAL'},{'phase':'raw_native_control'},{'strategy_id':None},
            {'expected_observation':'guaranteed_victory'},{'public_fact_refs':['hidden_enemy.positions']},
            {'public_fact_refs':['own.private_address']},{'public_fact_refs':['enemy.visible.armor.age_seconds']},
            {'updated_game_seconds':float('inf')},{'resource_priorities':{'army':1}}):
            raw=public_state();raw['current_strategy'].update(changes)
            with self.subTest(changes=changes),self.assertRaises(ContractError):project_macro_strategy_state(raw)

    def test_outcome_code_pattern_time_and_effect_claim_are_checked(self):
        for changes in ({'plan_id':'PRIVATE_PLAN'},{'outcome':'all_units_home'},{'reason_code':'https://PRIVATE'},
            {'reason_code':'x'*65},{'at_game_seconds':True},{'effect_verified':1},
            {'outcome':'effect_observed','effect_verified':False},{'outcome':'no_effect','effect_verified':True}):
            raw=public_state();raw['current_strategy']['last_outcome'].update(changes)
            with self.subTest(changes=changes),self.assertRaises(ContractError):project_macro_strategy_state(raw)

    def test_public_fact_refs_include_only_explicit_own_and_lawful_enemy_vocabulary(self):
        raw=public_state()
        refs=['own.unit.bullfrog','own.present.power_plant','production.producesickle.observed_new_queue_count',
              'enemy.last_seen.armor.age_seconds']
        raw['current_strategy']['public_fact_refs']=refs
        self.assertEqual(project_macro_strategy_state(raw)['current_strategy']['public_fact_refs'],refs)

    def test_unknown_and_stopped_stay_visible_without_granting_global_release(self):
        raw=public_state();raw.update(stopped=True,unknown_command_count=1,unreleased_command_count=1,
            last_guard_reason='strategy_unknown_outcome')
        raw['current_strategy']['last_outcome'].update(outcome='unknown',effect_verified=False)
        value=project_macro_strategy_state(raw)
        self.assertTrue(value['stopped']);self.assertEqual(value['unknown_command_count'],1)
        self.assertNotIn('native_release_verified',value)
        self.assertEqual(value['current_strategy']['last_outcome']['outcome'],'unknown')


class DesktopStrategyStatusTests(unittest.TestCase):
    setUp=fixture.DesktopBackendTests.setUp
    tearDown=fixture.DesktopBackendTests.tearDown
    new_backend=fixture.DesktopBackendTests.new_backend
    ready=fixture.DesktopBackendTests.ready
    start_args=fixture.DesktopBackendTests.start_args
    start=fixture.DesktopBackendTests.start
    status_file=fixture.DesktopBackendTests.status_file

    def macro_start(self):
        original=self.checks.check
        self.checks.check=lambda *a,**k:replace(original(*a,**k),capabilities=dict(native_macro=True,available_macro_actions=['budgetarmy']))
        result,run_id,_=self.start()
        row=self.backend._launch(run_id);bound=SessionBinding.from_dict(json.loads(row['binding_json']))
        return result,run_id,dict(run_id=run_id,binding_hash=bound.binding_hash)

    def test_status_projects_strategy_and_drops_private_extras(self):
        result,run_id,runtime=self.macro_start();value=public_state();value['commands']={'PRIVATE':'PRIVATE_KEY'}
        self.status_file(result,runtime_macro=runtime,macro_strategy=value)
        status=self.backend.run_status(dict(run_id=run_id),str(uuid.uuid4()))
        self.assertEqual(status['state'],'running')
        self.assertEqual(status['macro_strategy']['current_strategy']['objective'],'build_force')
        self.assertNotIn('PRIVATE',json.dumps(status))

    def test_bad_optional_strategy_does_not_erase_other_host_status_or_leak_raw(self):
        result,run_id,runtime=self.macro_start();value=public_state()
        value['current_strategy']['public_fact_refs']=['PRIVATE_RAW_ADDRESS']
        self.status_file(result,runtime_macro=runtime,macro_strategy=value,metrics={'requests':4})
        status=self.backend.run_status(dict(run_id=run_id),str(uuid.uuid4()))
        self.assertEqual(status['state'],'running');self.assertEqual(status['metrics']['requests'],4)
        self.assertTrue(status['macro_strategy_unavailable'])
        self.assertNotIn('macro_strategy',status);self.assertNotIn('PRIVATE',json.dumps(status))

    def test_legacy_status_without_strategy_remains_compatible(self):
        result,run_id,runtime=self.macro_start();self.status_file(result,runtime_macro=runtime)
        status=self.backend.run_status(dict(run_id=run_id),str(uuid.uuid4()))
        self.assertEqual(status['state'],'running')
        self.assertNotIn('macro_strategy',status);self.assertNotIn('macro_strategy_unavailable',status)


if __name__=='__main__':unittest.main()
