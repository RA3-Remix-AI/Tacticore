"""Offline behavior and adversarial lifecycle tests; no game or provider access."""
import copy
import json
import unittest
import uuid

from macro_strategy import MacroStrategyMemory, StrategyError, STRATEGY_DECLARATION_SCHEMA

SESSION = 'd341591e-2ad2-4562-95ca-da20b79fb5b1'
COMMANDER = '5cfc416a-8b8f-405a-9832-c163f8c1792b'


def context(at=10, **economy):
    return dict(session_id=SESSION, commander_id=COMMANDER, player_id=3,
        game_time_seconds=at, paused=False, control_mode='macro_native',
        allowed_macro_actions=['budgeteconomy', 'budgetarmy', 'produceconscript', 'regroup'],
        working_memory=dict(economy=dict(credits=5000, power_balance=100, queued_count=0,
            idle_producers=1, own_roles={'infantry': 3}, **economy),
            verified_enemy_facts=[], battlefield={'visibility_verified': True}))


def declaration(ident=None, **changes):
    result = dict(strategy_id=ident, objective='build_force', phase='prepare',
        public_fact_refs=['own.credits'], expected_observation='production_queue',
        continue_conditions=['capability_available'], replan_conditions=['facts_changed'],
        resource_priorities=dict(economy=.2, army=.5, tech=.1, reserve=.2))
    result.update(changes)
    return result


def plan(at=10, actions=None, **changes):
    result = dict(plan_id=str(uuid.uuid4()), session_id=SESSION, commander_id=COMMANDER,
        player_id=3, origin='model', based_on_game_time_seconds=at, expires_at_game_seconds=at+20,
        macro_actions=['budgetarmy'] if actions is None else actions,
        macro_production=None, objective_region=None, tactical_tasks=[], runtime_task=None)
    result.update(changes)
    return result


class StrategyTests(unittest.TestCase):
    def setUp(self):
        self.memory = MacroStrategyMemory(session_id=SESSION, commander_id=COMMANDER, player_id=3,
            profile_revision=21, effective_hash='a'*64)

    def start(self, *, at=10, actions=None, **changes):
        payload = context(at)
        current_plan = plan(at, actions, **changes)
        review = self.memory.review(current_plan, declaration(), payload)
        self.assertTrue(review.allowed, review.reason_code)
        self.memory.record_dispatch(review, command_id='command-one', game_seconds=at)
        return current_plan, review

    def finish(self, p, *, at=31, outcome='no_effect', **changes):
        self.memory.record_outcome(command_id='command-one', plan_id=p['plan_id'], outcome=outcome,
            game_seconds=at, release_verified=True, **changes)

    def test_state_survives_short_plan_expiry_and_only_declared_goal_is_kept(self):
        p, review = self.start()
        result = self.memory.context(context(100))
        state = result['current_strategy']
        self.assertEqual(state['objective'], 'build_force')
        self.assertEqual(state['strategy_id'], review.strategy_id)
        self.assertNotIn('expires_at_game_seconds', state)
        self.assertEqual(state['public_fact_refs'], ['own.credits'])
        self.assertEqual(state['resource_priorities'], declaration()['resource_priorities'])

    def test_review_does_not_change_state_or_dispatch(self):
        self.memory.review(plan(), declaration(), context())
        self.assertIsNone(self.memory.context(context())['current_strategy'])
        self.assertEqual(self.memory._commands, {})

    def test_no_action_wait_records_strategy_without_native_command(self):
        review = self.memory.review(plan(actions=[]), declaration(objective='hold', phase='wait'), context())
        self.memory.record_dispatch(review, command_id=None, game_seconds=10)
        self.assertEqual(self.memory.context(context())['current_strategy']['objective'], 'hold')
        self.assertEqual(self.memory._commands, {})

    def test_unknown_empty_gate_clear_keeps_actual_id_and_global_barrier_visible(self):
        p=plan(actions=[])
        review=self.memory.review(p,declaration(objective='hold',phase='wait'),context())
        self.memory.record_dispatch(review,command_id='uncertain-clear',game_seconds=10,outcome='unknown')
        self.assertEqual(self.memory._commands['uncertain-clear']['plan_id'],p['plan_id'])
        self.assertEqual(self.memory._commands['uncertain-clear']['outcome'],'unknown')
        public=self.memory.context(context(11))
        self.assertEqual(public['current_strategy']['last_outcome']['outcome'],'unknown')
        self.assertEqual(public['last_guard_reason'],'strategy_unknown_outcome')
        later=self.memory.review(plan(200,['regroup']),declaration(review.strategy_id,objective='hold'),context(200))
        self.assertEqual(later.reason_code,'strategy_unknown_outcome')
        with self.assertRaisesRegex(StrategyError,'release_required'):
            self.memory.record_outcome(command_id='uncertain-clear',plan_id=p['plan_id'],outcome='cancelled',game_seconds=201)
        self.memory.record_outcome(command_id='uncertain-clear',plan_id=p['plan_id'],outcome='cancelled',
            game_seconds=201,release_verified=True)
        self.assertTrue(self.memory.review(plan(202,['regroup']),
            declaration(review.strategy_id,objective='hold'),context(202)).allowed)

    def test_empty_clear_id_rules_are_atomic_and_differ_for_known_and_unknown(self):
        r=self.memory.review(plan(actions=[]),declaration(),context())
        with self.assertRaisesRegex(StrategyError,'command_id'):
            self.memory.record_dispatch(r,command_id=None,game_seconds=10,outcome='unknown')
        self.assertIsNone(self.memory.context(context())['current_strategy'])
        with self.assertRaisesRegex(StrategyError,'wait_has_no_command'):
            self.memory.record_dispatch(r,command_id='known-clear',game_seconds=10)
        self.memory.record_dispatch(r,command_id=None,game_seconds=10)
        self.assertEqual(self.memory._commands,{})

    def test_state_serialization_cannot_mutate_authoritative_memory(self):
        self.start()
        exposed = self.memory.context(context())
        exposed['current_strategy']['public_fact_refs'].append('PRIVATE')
        exposed['fact_catalog']['own.credits'] = -1
        self.assertEqual(self.memory.context(context())['current_strategy']['public_fact_refs'], ['own.credits'])
        self.assertEqual(self.memory.context(context())['fact_catalog']['own.credits'], 5000)

    def test_model_does_not_gain_arbitrary_facts_or_free_text(self):
        payload = context()
        payload.update(enemy_hidden_objects=[{'secret': 'PRIVATE_ADDRESS'}], api_key='PRIVATE_KEY')
        payload['working_memory']['economy']['native_pointer'] = 'PRIVATE_POINTER'
        public = json.dumps(self.memory.context(payload))
        self.assertNotIn('PRIVATE', public)
        for changes in ({'public_fact_refs': ['enemy_hidden_objects']}, {'objective': 'read PRIVATE_KEY'},
                        {'phase': 'issue_native_move'}, {'expected_observation': 'all_units_home'}):
            with self.subTest(changes=changes), self.assertRaises(StrategyError):
                self.memory.review(plan(), declaration(**changes), payload)

    def test_fact_ref_must_have_been_in_offered_catalog_and_be_current(self):
        payload = context()
        payload['macro_strategy'] = self.memory.context(payload)
        del payload['macro_strategy']['fact_catalog']['own.power_balance']
        with self.assertRaisesRegex(StrategyError, 'public_fact_refs'):
            self.memory.review(plan(), declaration(public_fact_refs=['own.power_balance']), payload)
        payload['macro_strategy']['fact_catalog']['own.credits'] = 999999
        with self.assertRaisesRegex(StrategyError, 'fact_catalog_changed'):
            self.memory.review(plan(), declaration(), payload)

    def test_hidden_or_expired_enemy_information_is_never_reintroduced(self):
        payload = context(200)
        payload['working_memory']['verified_enemy_facts'] = [dict(role='armor', count=2,
            observed_at_game_seconds=10, currently_visible=False)]
        self.assertFalse(any(k.startswith('enemy.') for k in self.memory.context(payload)['fact_catalog']))
        payload['working_memory']['verified_enemy_facts'][0]['observed_at_game_seconds'] = 190
        catalog = self.memory.context(payload)['fact_catalog']
        self.assertEqual(catalog['enemy.last_seen.armor.count'], 2)
        self.assertEqual(catalog['enemy.last_seen.armor.age_seconds'], 10)
        self.assertNotIn('enemy.visible.armor.count', catalog)
        payload['working_memory']['battlefield']['visibility_verified'] = False
        self.assertFalse(any(k.startswith('enemy.') for k in self.memory.context(payload)['fact_catalog']))

    def test_own_presence_does_not_become_building_completion_or_recruitability(self):
        payload = context()
        payload['own_infrastructure'] = dict(own_perspective=True, enemy_details_read=False,
            builder_frame=150, own_census_frame=150, own_template_presence_counts={'battle_lab': 1},
            completed_technology_verified=False, native_address='PRIVATE')
        payload['own_forces'] = dict(own_perspective=True, enemy_details_read=False, observed_frame=150,
            named_unit_counts={'hammer_tank': 2}, recruitability_verified=False)
        catalog = self.memory.context(payload)['fact_catalog']
        self.assertEqual(catalog['own.present.battle_lab'], 1)
        self.assertEqual(catalog['own.unit.hammer_tank'], 2)
        self.assertFalse(any('completed' in k or 'recruit' in k for k in catalog))
        payload['own_forces']['observed_frame'] = 100
        with self.assertRaisesRegex(StrategyError, 'own_stale'):
            self.memory.context(payload)

    def test_current_strategy_changes_require_minimum_hold_without_new_facts(self):
        p, review = self.start()
        self.finish(p, at=11, outcome='cancelled')
        result = self.memory.review(plan(12, ['budgeteconomy']),
            declaration(objective='expand_economy'), context(12))
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason_code, 'strategy_minimum_hold')
        continued = self.memory.review(plan(12, ['budgeteconomy']),
            declaration(review.strategy_id), context(12))
        self.assertTrue(continued.allowed)

    def test_new_basis_fact_or_trusted_urgency_allows_early_replan(self):
        p, _ = self.start()
        self.finish(p, at=11, outcome='cancelled')
        changed = context(12)
        changed['working_memory']['economy']['credits'] = 200
        self.assertTrue(self.memory.review(plan(12, ['budgeteconomy']),
            declaration(objective='economic_stability'), changed).allowed)
        self.assertTrue(self.memory.review(plan(12, ['regroup']),
            declaration(objective='defend_base'), context(12), urgent=True).allowed)
        with self.assertRaisesRegex(StrategyError, 'urgent_assertion'):
            self.memory.review(plan(12), declaration(), context(12), urgent='model_says_urgent')

    def test_changing_objective_under_same_id_is_refused(self):
        _, review = self.start()
        with self.assertRaisesRegex(StrategyError, 'requires_new_id'):
            self.memory.review(plan(40), declaration(review.strategy_id, objective='scout'), context(40))

    def test_unknown_delivery_survives_expiry_and_blocks_other_actions_too(self):
        p = plan()
        review = self.memory.review(p, declaration(), context())
        self.memory.record_dispatch(review, command_id='command-one', game_seconds=10, outcome='unknown')
        for actions in (['budgetarmy'], ['regroup'], ['budgeteconomy']):
            result = self.memory.review(plan(200, actions), declaration(review.strategy_id), context(200))
            self.assertFalse(result.allowed)
            self.assertEqual(result.reason_code, 'strategy_unknown_outcome')
        with self.assertRaisesRegex(StrategyError, 'release_required'):
            self.memory.record_outcome(command_id='command-one', plan_id=p['plan_id'], outcome='failed', game_seconds=201)
        self.finish(p, at=201, outcome='cancelled')
        self.assertTrue(self.memory.review(plan(202, ['regroup']), declaration(review.strategy_id), context(202)).allowed)

    def test_ack_and_pending_cannot_be_asserted_as_effect(self):
        p, _ = self.start()
        self.assertIsNone(self.memory.context(context())['current_strategy']['last_outcome'])
        with self.assertRaisesRegex(StrategyError, 'effect_window'):
            self.memory.record_outcome(command_id='command-one', plan_id=p['plan_id'], outcome='effect_observed',
                game_seconds=12, observed_game_seconds=11, effect_verified=False)
        self.assertFalse(self.memory._commands['command-one']['had_effect'])

    def test_effect_requires_matching_command_plan_and_strict_effect_window(self):
        p, _ = self.start()
        for seen, at in ((9, 12), (30, 31), (31, 31), (13, 12)):
            with self.subTest(seen=seen), self.assertRaisesRegex(StrategyError, 'effect_window'):
                self.memory.record_outcome(command_id='command-one', plan_id=p['plan_id'], outcome='effect_observed',
                    game_seconds=at, observed_game_seconds=seen, effect_verified=True)
        with self.assertRaisesRegex(StrategyError, 'outcome_binding'):
            self.memory.record_outcome(command_id='command-one', plan_id='another-plan', outcome='effect_observed',
                game_seconds=12, observed_game_seconds=11, effect_verified=True)
        self.memory.record_outcome(command_id='command-one', plan_id=p['plan_id'], outcome='effect_observed',
            game_seconds=12, observed_game_seconds=11, effect_verified=True)
        self.assertTrue(self.memory.context(context(12))['current_strategy']['last_outcome']['effect_verified'])

    def test_later_command_attempt_is_effect_boundary_without_faking_release(self):
        p, first = self.start()
        p2 = plan(12, ['regroup'])
        review = self.memory.review(p2, declaration(first.strategy_id), context(12))
        self.memory.record_dispatch(review, command_id='command-two', game_seconds=12, outcome='unknown')
        with self.assertRaisesRegex(StrategyError, 'effect_window'):
            self.memory.record_outcome(command_id='command-one', plan_id=p['plan_id'], outcome='effect_observed',
                game_seconds=14, observed_game_seconds=13, effect_verified=True)
        self.assertIsNone(self.memory._commands['command-one']['released_at'])

    def test_no_effect_cooldown_uses_original_basis_not_new_selected_refs(self):
        p, review = self.start()
        self.finish(p)
        proposed = declaration(review.strategy_id, public_fact_refs=['own.power_balance'])
        result = self.memory.review(plan(32), proposed, context(32))
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason_code, 'strategy_no_effect_cooldown')
        changed = context(32)
        changed['working_memory']['economy']['credits'] = 6000
        self.assertTrue(self.memory.review(plan(32), proposed, changed).allowed)
        self.assertTrue(self.memory.review(plan(77), proposed, context(77)).allowed)

    def test_pending_intent_does_not_silently_become_known_after_ttl(self):
        p, review = self.start()
        result = self.memory.review(plan(90), declaration(review.strategy_id), context(90))
        self.assertEqual(result.reason_code, 'strategy_intent_in_flight')
        self.finish(p, at=90, outcome='expired')
        result = self.memory.review(plan(91), declaration(review.strategy_id), context(91))
        self.assertEqual(result.reason_code, 'strategy_no_effect_cooldown')

    def test_successful_production_requires_new_facts_or_bounded_renewal_wait(self):
        p, first = self.start(actions=['produceconscript'], macro_production={'action': 'produceconscript', 'additional_count': 1})
        self.memory.record_outcome(command_id='command-one', plan_id=p['plan_id'], outcome='effect_observed',
            game_seconds=12, observed_game_seconds=11, effect_verified=True)
        self.finish(p, at=12, outcome='cancelled')
        proposal = lambda at: plan(at, ['produceconscript'], macro_production={'action': 'produceconscript', 'additional_count': 1})
        waiting = self.memory.review(proposal(13), declaration(first.strategy_id), context(13))
        self.assertEqual(waiting.reason_code, 'strategy_production_renewal_wait')
        changed = context(13)
        changed['working_memory']['economy']['queued_count'] = 1
        self.assertTrue(self.memory.review(proposal(13), declaration(first.strategy_id), changed).allowed)
        self.assertTrue(self.memory.review(proposal(33), declaration(first.strategy_id), context(33)).allowed)

    def test_context_is_bounded_with_long_conditions_and_outcome_history(self):
        p, review = self.start()
        self.memory.record_outcome(command_id='command-one', plan_id=p['plan_id'], outcome='effect_observed',
            game_seconds=12, observed_game_seconds=11, effect_verified=True)
        self.finish(p, at=13, outcome='cancelled')
        payload = context(50)
        payload['working_memory']['verified_enemy_facts'] = [dict(role=role, count=300,
            observed_at_game_seconds=49, currently_visible=True)
            for role in ('anti_air', 'anti_armor', 'infantry', 'naval', 'air', 'armor')]
        continued = declaration(review.strategy_id, public_fact_refs=['own.credits', 'own.power_balance',
            'own.queued_count', 'own.idle_producers'], continue_conditions=['capability_available', 'resources_sufficient', 'prerequisite_met'],
            replan_conditions=['facts_changed', 'goal_unobserved', 'effect_observed'])
        r2 = self.memory.review(plan(50, []), continued, payload)
        self.memory.record_dispatch(r2, command_id=None, game_seconds=50)
        result = self.memory.context(payload)
        self.assertLessEqual(len(json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode('utf8')), 1536)
        self.assertEqual(result['current_strategy']['public_fact_refs'], continued['public_fact_refs'])
        self.assertTrue(set(continued['public_fact_refs']) <= set(result['fact_catalog']))

    def test_every_feasible_wire_boundary_retains_strategy_and_basis(self):
        p, review = self.start()
        self.memory.record_outcome(command_id='command-one', plan_id=p['plan_id'], outcome='effect_observed',
            game_seconds=12, observed_game_seconds=11, effect_verified=True)
        self.finish(p, at=13, outcome='cancelled')
        payload=context(50)
        payload['allowed_macro_actions']=['regroup','scout','withdraw','reinforce','budgeteconomy',
            'budgetarmy','budgettech','deployattack','deploydefense','expand','pauseconstruction',
            'advanceconstruction','pauseproduction','advanceproduction']
        refs=['capabilities.actions','own.credits','own.power_balance']
        proposed=declaration(review.strategy_id,public_fact_refs=refs,
            continue_conditions=['capability_available','resources_sufficient','no_new_threat'],
            replan_conditions=['facts_changed','goal_unobserved','effect_observed'])
        next_review=self.memory.review(plan(50,[]),proposed,payload)
        self.assertTrue(next_review.allowed,next_review.reason_code)
        self.memory.record_dispatch(next_review,command_id=None,game_seconds=50)
        self.memory.maximum_context_bytes=3072
        full=self.memory.context(payload)
        core=copy.deepcopy(full);core['recent_outcomes']=[]
        core['fact_catalog']={key:value for key,value in core['fact_catalog'].items() if key in refs}
        encode=lambda value:json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf8')
        minimum=max(1024,len(encode(core)))
        self.assertLessEqual(minimum,1536)
        for bound in range(minimum,1537):
            with self.subTest(bound=bound):
                self.memory.maximum_context_bytes=bound
                result=self.memory.context(payload)
                self.assertLessEqual(len(encode(result)),bound)
                self.assertEqual(result['current_strategy'],full['current_strategy'])
                self.assertTrue(set(refs)<=set(result['fact_catalog']))
                self.assertEqual(result['missing_basis_refs'],[])

    def test_unknown_is_not_falsely_resolved_by_effect_or_pending(self):
        p = plan()
        r = self.memory.review(p, declaration(), context())
        self.memory.record_dispatch(r, command_id='command-one', game_seconds=10, outcome='unknown')
        with self.assertRaisesRegex(StrategyError, 'unknown_requires_resolution'):
            self.memory.record_outcome(command_id='command-one', plan_id=p['plan_id'], outcome='effect_observed',
                game_seconds=12, observed_game_seconds=11, effect_verified=True)

    def test_stop_invalidates_a_prepared_review_and_rejects_new_dispatch(self):
        r = self.memory.review(plan(), declaration(), context())
        self.memory.stop()
        with self.assertRaisesRegex(StrategyError, 'strategy_stopped'):
            self.memory.record_dispatch(r, command_id='command-one', game_seconds=10)
        self.assertEqual(self.memory.review(plan(), declaration(), context()).reason_code, 'strategy_stopped')
        self.assertEqual(self.memory.context(context())['guard'], 'stopped')

    def test_outcome_update_invalidates_review_awaiting_commit(self):
        p, first = self.start()
        r = self.memory.review(plan(12, ['regroup']), declaration(first.strategy_id), context(12))
        self.finish(p, at=12, outcome='cancelled')
        with self.assertRaisesRegex(StrategyError, 'review_not_current'):
            self.memory.record_dispatch(r, command_id='command-two', game_seconds=12)

    def test_expired_or_old_request_or_newly_unavailable_action_is_refused(self):
        for p, request, latest in ((plan(10), context(10), context(31)),
                                  (plan(11), context(10), context(11)),
                                  (plan(10), context(10), context(9))):
            with self.subTest(p=p), self.assertRaisesRegex(StrategyError, 'plan_time'):
                self.memory.review(p, declaration(), request, latest)
        latest = context(11)
        latest['allowed_macro_actions'] = ['regroup']
        with self.assertRaisesRegex(StrategyError, 'plan_capabilities'):
            self.memory.review(plan(), declaration(), context(), latest)

    def test_profile_and_session_binding_are_not_implicitly_migrated(self):
        for changes in ({'session_id': str(uuid.uuid4())}, {'player_id': True}, {'profile_revision': 22},
                        {'effective_hash': 'b'*64}):
            with self.subTest(changes=changes), self.assertRaises(StrategyError):
                self.memory.context(dict(context(), **changes))

    def test_schema_and_scalar_validation_reject_oversized_or_untrusted_values(self):
        self.assertTrue(STRATEGY_DECLARATION_SCHEMA['advisory_only'])
        for changes in ({'public_fact_refs': ['own.credits']*5}, {'continue_conditions': ['facts_changed']*2},
                        {'resource_priorities': {'economy': float('nan'), 'army': .5, 'tech': .2, 'reserve': .3}},
                        {'resource_priorities': {'economy': 1, 'army': 1, 'tech': 1, 'reserve': 1}},
                        {'secret': 'PRIVATE'}):
            with self.subTest(changes=changes), self.assertRaises(StrategyError):
                self.memory.review(plan(), declaration(**changes), context())
        bad = context()
        bad['allowed_macro_actions'] = [{}]
        with self.assertRaisesRegex(StrategyError, 'context_capabilities'):
            self.memory.context(bad)

    def test_model_mutation_after_review_cannot_modify_accepted_candidate(self):
        raw = declaration()
        r = self.memory.review(plan(), raw, context())
        raw['continue_conditions'].append('PRIVATE')
        raw['resource_priorities']['army'] = 99
        self.memory.record_dispatch(r, command_id='command-one', game_seconds=10)
        state = self.memory.context(context())['current_strategy']
        self.assertEqual(state['continue_conditions'], ['capability_available'])
        self.assertEqual(state['resource_priorities']['army'], .5)

    def test_invalid_outcome_is_atomic_and_does_not_leave_fake_effect(self):
        p, _ = self.start()
        before = copy.deepcopy(self.memory._commands)
        with self.assertRaisesRegex(StrategyError, 'release_outcome'):
            self.memory.record_outcome(command_id='command-one', plan_id=p['plan_id'], outcome='effect_observed',
                game_seconds=12, observed_game_seconds=11, effect_verified=True, release_verified=True)
        self.assertEqual(self.memory._commands, before)
        self.assertIsNone(self.memory.context(context())['current_strategy']['last_outcome'])

    def test_continuing_strategy_keeps_last_outcome_across_next_plan(self):
        p, first = self.start()
        self.finish(p, at=11, outcome='cancelled')
        last = self.memory.context(context(12))['current_strategy']['last_outcome']
        r = self.memory.review(plan(12, []), declaration(first.strategy_id), context(12))
        self.memory.record_dispatch(r, command_id=None, game_seconds=12)
        self.assertEqual(self.memory.context(context(13))['current_strategy']['last_outcome'], last)

    def test_early_expiry_and_effect_erasure_are_refused(self):
        p, _ = self.start()
        with self.assertRaisesRegex(StrategyError, 'expiry_before_deadline'):
            self.finish(p, at=11, outcome='expired')
        self.memory.record_outcome(command_id='command-one', plan_id=p['plan_id'], outcome='effect_observed',
            game_seconds=12, observed_game_seconds=11, effect_verified=True)
        with self.assertRaisesRegex(StrategyError, 'effect_cannot_be_erased'):
            self.finish(p, at=13, outcome='no_effect')

    def test_stale_production_feedback_cannot_unlock_repeat(self):
        payload = context()
        payload['macro_production_feedback'] = dict(source='native_production_observation', action='produceconscript',
            observed_new_queue_count=1, builder_frame=100, own_census_frame=100)
        with self.assertRaisesRegex(StrategyError, 'own_stale'):
            self.memory.context(payload)

    def test_rejected_dispatch_after_expiry_never_commits_strategy(self):
        r = self.memory.review(plan(), declaration(), context())
        with self.assertRaisesRegex(StrategyError, 'dispatch_time_or_outcome'):
            self.memory.record_dispatch(r, command_id='command-one', game_seconds=30)
        self.assertIsNone(self.memory.context(context())['current_strategy'])

    def test_command_and_plan_ids_cannot_be_reused_as_new_deliveries(self):
        p, first = self.start()
        self.finish(p, at=11, outcome='cancelled')
        same = dict(p, based_on_game_time_seconds=40, expires_at_game_seconds=60)
        self.assertEqual(self.memory.review(same, declaration(first.strategy_id), context(40)).reason_code,
                         'strategy_plan_already_dispatched')
        r = self.memory.review(plan(40, ['regroup']), declaration(first.strategy_id), context(40))
        with self.assertRaisesRegex(StrategyError, 'command_reused'):
            self.memory.record_dispatch(r, command_id='command-one', game_seconds=40)

    def test_public_state_is_a_detached_read_without_a_context_or_version_change(self):
        p,_=self.start()
        self.memory.record_outcome(command_id='command-one',plan_id=p['plan_id'],outcome='effect_observed',
            game_seconds=12,observed_game_seconds=11,effect_verified=True)
        version=self.memory._version
        original=self.memory.public_state()
        exposed=self.memory.public_state()
        exposed['current_strategy']['public_fact_refs'].append('PRIVATE')
        exposed['current_strategy']['resource_priorities']['army']=99
        exposed['recent_outcomes'][0]['outcome']='invented_success'
        exposed['unknown_command_count']=999
        self.assertEqual(self.memory.public_state(),original)
        self.assertEqual(self.memory._version,version)
        self.assertNotIn('fact_catalog',original)
        self.assertNotIn('commands',original)
        self.assertNotIn('command-one',json.dumps(original))

    def test_public_state_exposes_unknown_empty_clear_and_stop_without_faking_release(self):
        p=plan(actions=[])
        r=self.memory.review(p,declaration(objective='hold',phase='wait'),context())
        self.memory.record_dispatch(r,command_id='private-clear-id',game_seconds=10,outcome='unknown')
        value=self.memory.public_state()
        self.assertEqual(value['unknown_command_count'],1)
        self.assertEqual(value['unreleased_command_count'],1)
        self.assertEqual(value['current_strategy']['last_outcome']['outcome'],'unknown')
        self.assertEqual(value['last_guard_reason'],'strategy_unknown_outcome')
        self.assertFalse(value['stopped'])
        self.assertNotIn('private-clear-id',json.dumps(value))
        self.memory.stop()
        version=self.memory._version
        stopped=self.memory.public_state()
        self.assertTrue(stopped['stopped'])
        self.assertEqual(stopped['unknown_command_count'],1)
        self.assertEqual(stopped['unreleased_command_count'],1)
        self.assertEqual(self.memory._version,version)


    @staticmethod
    def _work_context(at, *, seen=0, count=2, power=100, credits=5000):
        value = context(at)
        value['allowed_macro_actions'] += ['expand', 'advanceconstruction']
        value['working_memory']['economy'].update(power_balance=power, credits=credits)
        value['working_memory']['verified_enemy_facts'] = [dict(role='armor', count=count,
            observed_at_game_seconds=seen, currently_visible=False)]
        return value

    def _failed_expansion(self, *, actions=None, power=100):
        memory = MacroStrategyMemory(session_id=SESSION, commander_id=COMMANDER, player_id=3,
            profile_revision=21, effective_hash='a'*64)
        p = plan(100, ['expand'] if actions is None else actions)
        proposed = declaration(public_fact_refs=['capabilities.actions'])
        first = memory.review(p, proposed, self._work_context(100, power=power))
        self.assertTrue(first.allowed)
        memory.record_dispatch(first, command_id='failed-expansion', game_seconds=100)
        memory.record_outcome(command_id='failed-expansion', plan_id=p['plan_id'], outcome='no_effect',
            game_seconds=102, release_verified=True)
        return memory, declaration(first.strategy_id, public_fact_refs=['capabilities.actions'])

    def test_failed_work_cannot_restart_by_adding_or_switching_budget_or_gate(self):
        for old, actions in ((['expand'], ['expand', 'budgetarmy']),
                             (['expand', 'budgeteconomy'], ['expand', 'budgetarmy']),
                             (['expand'], ['expand', 'advanceconstruction'])):
            with self.subTest(old=old, actions=actions):
                memory, proposed = self._failed_expansion(actions=old)
                decision = memory.review(plan(103, actions), proposed, self._work_context(103))
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.reason_code, 'strategy_no_effect_cooldown')

    def test_failed_work_count_age_expiry_does_not_unlock_retry(self):
        memory, proposed = self._failed_expansion()
        for at in (119.999, 120, 120.001, 121):
            with self.subTest(at=at):
                decision = memory.review(plan(at, ['expand', 'budgetarmy']), proposed, self._work_context(at))
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.reason_code, 'strategy_no_effect_cooldown')

    def test_failed_work_known_to_unknown_and_fresh_equal_count_still_wait(self):
        for at, changes in ((103, dict(power=None)), (121, dict(seen=121))):
            with self.subTest(changes=changes):
                memory, proposed = self._failed_expansion()
                decision = memory.review(plan(at, ['expand', 'budgetarmy']), proposed,
                    self._work_context(at, **changes))
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.reason_code, 'strategy_no_effect_cooldown')

    def test_failed_work_real_new_value_zero_or_completed_cooldown_allows_reassessment(self):
        for at, old_power, changes in ((103, 100, dict(credits=6000)),
                                       (121, 100, dict(seen=121, count=0)),
                                       (103, None, dict(power=100)), (147, 100, {})):
            with self.subTest(at=at, old_power=old_power, changes=changes):
                memory, proposed = self._failed_expansion(power=old_power)
                decision = memory.review(plan(at, ['expand', 'budgetarmy']), proposed,
                    self._work_context(at, **changes))
                self.assertTrue(decision.allowed, decision.reason_code)
                self.assertFalse(memory.public_state()['current_strategy']['last_outcome']['effect_verified'])



if __name__ == '__main__':
    unittest.main()
