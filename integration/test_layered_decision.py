"""Layered decision framework, offline: fake model backends, no game, network or key."""

import asyncio
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for folder in ("strategy", "integration", "agent_runtime/src"):
    if str(ROOT / folder) not in sys.path:
        sys.path.insert(0, str(ROOT / folder))

from host_runtime import layered_decision as ld  # noqa: E402
from host_runtime.contracts import ContractError  # noqa: E402
from host_runtime.decision_log import DecisionLogWriter, read_run_log  # noqa: E402
from host_runtime.habit_audit import HabitAudit  # noqa: E402
from host_runtime.opening_book import OpeningExecutor, choose_opening, eligible_openings  # noqa: E402
from host_runtime.personality_rules import PersonalityRules, review_tactical  # noqa: E402
from host_runtime.profiles import persona_text, preset_personality  # noqa: E402
from host_runtime.world_state import EventDetector, build_world_state  # noqa: E402
import layered_contract as contract  # noqa: E402

HAMMER = preset_personality("hammer")
TIMID = dict(HAMMER, aggression=1, risk=1, preserve=5, bait_awareness=1, adaptability=1, persistence=1, grudge=1)
SESSION = "45b37922-a953-4d54-bc3b-4a34804c1c56"
COMMANDER = "5cfc416a-8b8f-405a-9832-c163f8c1792b"
ALL_ACTIONS = [
    "advanceconstruction",
    "advanceproduction",
    "attackenemy",
    "budgetarmy",
    "budgeteconomy",
    "budgettech",
    "deploydefense",
    "expand",
    "focusenemy4",
    "focusenemy5",
    "pauseconstruction",
    "pauseproduction",
    "raideconomy",
    "regroup",
    "reinforce",
    "scout",
    "withdraw",
]


def context(
    at=100.0,
    *,
    mobile=12,
    collectors=4,
    yards=1,
    refineries=2,
    near_home=0,
    enemy_groups=(),
    defeated=(),
    tech=(),
    actions=ALL_ACTIONS,
):
    buildings = dict(construction_yard=yards, refinery=refineries, power_plant=3, war_factory=1)
    for name in tech:
        buildings[name] = 1
    return dict(
        commander_id=COMMANDER,
        session_id=SESSION,
        player_id=3,
        snapshot_id=int(at),
        game_time_seconds=at,
        allowed_macro_actions=list(actions),
        macro_policy_catalog=dict(deploydefense=dict(domain="deployment", target_region="region_7_1")),
        own_forces=dict(
            mobile_role_counts=dict(infantry=mobile // 2, armor=mobile - mobile // 2),
            building_presence_counts=buildings,
            economic_unit_presence_counts=dict(ore_collector=collectors),
            regions=[dict(region_id="region_7_1", mobile=mobile, construction_yards=yards)],
        ),
        battlefield_summary=dict(
            home_region="region_7_1",
            nearby_home_enemy_mobile_observations=near_home,
            mining_regions=[
                dict(region_id="region_7_2", ore_collectors=collectors, nearby_enemy_mobile_observations=0)
            ],
        ),
        working_memory=dict(
            economy=dict(credits=2500.0, power_balance=20.0),
            battlefield=dict(contact_groups=[dict(row) for row in enemy_groups], regions=[]),
            match_state=dict(opponent_player_ids=[4, 5], defeated_opponent_ids=list(defeated)),
        ),
    )


def group(region, role, count=1, *, owner=4, seen=100.0, visible=True):
    return dict(
        region_id=region,
        role=role,
        relation="enemy",
        currently_visible=visible,
        observations=count,
        oldest_game_seconds=seen,
        newest_game_seconds=seen,
        owner_player_id=owner,
    )


def directive(**changes):
    value = dict(
        route="steady_growth",
        resource_split=dict(economy=0.5, army=0.3, tech=0.1, reserve=0.1),
        primary_enemy=4,
        overrides=[],
        reasoning="先看清战线，再集中突破。",
        valid_for_s=120,
        review_when=["base_under_attack"],
    )
    value.update(changes)
    return value


ECONOMY = dict(
    expand="now",
    construction="advance",
    production=None,
    tech_timing="after_expansion",
    capacity_target=dict(war_factory=2, ore_collector=6),
    protocol_pick_preference=["cash_bounty"],
    composition_answer=None,
    reasoning="矿车领先，趁现在扩张。",
    valid_for_s=60,
)
TACTICAL = dict(
    posture="attack",
    target=dict(enemy=4, region=None),
    composition_need=["anti_air"],
    doctrine=None,
    power_usage=None,
    reasoning="他的主力离家了，压上去。",
    valid_for_s=30,
)


class FakeBackend:
    """Async model stand-in: one canned reply per layer; records every request."""

    def __init__(self, replies=None, fail=()):
        self.replies = replies or dict(commander=directive(), economy=ECONOMY, tactical=TACTICAL)
        self.fail = set(fail)
        self.calls = []

    def input_size(self, value):
        return len(json.dumps(value, ensure_ascii=False).encode()) + 2048

    async def __call__(self, value):
        self.calls.append(copy.deepcopy(value))
        layer = value["decision_layer"]
        if layer in self.fail:
            raise RuntimeError("provider down")
        return copy.deepcopy(self.replies[layer])


def decider(personality=HAMMER, backend=None, log=None, scenario=None):
    return ld.LayeredDecider(
        backend=backend or FakeBackend(),
        binding=dict(commander_id=COMMANDER, session_id=SESSION, player_id=3),
        commander=dict(id="hammer", name="铁锤"),
        personality=personality,
        scenario=scenario or dict(map_id="map_mp_2_rao1", enemy_player_ids=[4], opponent_difficulty="medium"),
        log=log,
    )


async def settle(value, ctx, now):
    """Tick, let fake calls finish, tick again to collect them."""
    value.tick(ctx, now)
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    value.tick(ctx, now)


class WorldStateTests(unittest.TestCase):
    def test_world_state_reads_only_the_lawful_context(self):
        world = build_world_state(
            context(enemy_groups=[group("region_2_2", "structure"), group("region_3_3", "armor", 5)])
        )
        self.assertEqual(world.own_mobile, 12)
        self.assertEqual(world.ore_collectors, 4)
        self.assertEqual(world.bases, 1)
        self.assertEqual(world.home_region, "region_7_1")
        self.assertEqual(world.enemies[4]["bases"], ["region_2_2"])
        self.assertEqual(world.enemy_visible_combat, 5)
        self.assertEqual(world.force_ratio(), 2.4)
        self.assertEqual(world.remaining_enemies, (4, 5))
        self.assertIn("ore_collectors", world.economy_slice())
        self.assertIn("enemy_info_age_s", world.tactical_slice())

    def test_events_fire_once_per_occurrence(self):
        detector = EventDetector()
        first = detector.detect(build_world_state(context(at=60)))
        self.assertEqual(first, [])
        hit = context(
            at=70,
            collectors=3,
            yards=2,
            near_home=4,
            defeated=[5],
            tech=["battle_lab"],
            enemy_groups=[group("region_2_2", "structure"), group("region_2_3", "economy"), group("r", "armor", 8)],
        )
        kinds = sorted(row["kind"] for row in detector.detect(build_world_state(hit)))
        self.assertEqual(
            kinds,
            [
                "base_under_attack",
                "enemy_defeated",
                "enemy_main_force_contact",
                "expansion_changed",
                "ore_collector_lost",
                "scouting_report",
                "scouting_report",
                "tech_unlocked",
            ],
        )
        again = detector.detect(build_world_state(dict(hit, game_time_seconds=71)))
        self.assertEqual(again, [])


class ContractAndPromptTests(unittest.TestCase):
    def test_directive_schema_and_all_in_overrides(self):
        value = contract.validate_directive(directive(route="all_in"), enemies=[4])
        self.assertEqual(set(value["overrides"]), {"no_expansion", "no_tech"})
        for bad in (
            dict(route="win"),
            dict(primary_enemy=9),
            dict(resource_split=dict(economy=0.9, army=0.9, tech=0, reserve=0)),
            dict(valid_for_s=10),
            dict(overrides=["no_fun"]),
            dict(extra=1),
        ):
            with self.subTest(bad=bad), self.assertRaises(contract.LayerContractError):
                contract.validate_directive(directive(**bad), enemies=[4])
        long = contract.validate_directive(directive(reasoning="很" * 400), enemies=[4])
        self.assertLessEqual(len(long["reasoning"]), 300)

    def test_economy_and_tactical_schema_and_record_only_fields(self):
        economy = contract.validate_economy_intent(ECONOMY)
        self.assertEqual(
            contract.economy_actions(economy), dict(expansion="expand", construction_gate="advanceconstruction")
        )
        self.assertEqual(
            contract.recorded_only("economy", economy), ["tech_timing", "capacity_target", "protocol_pick_preference"]
        )
        tactical = contract.validate_tactical_intent(dict(TACTICAL, doctrine="air_ground_combined"), enemies=[4])
        self.assertEqual(contract.recorded_only("tactical", tactical), ["target", "composition_need", "doctrine"])
        for bad in (dict(expand="maybe"), dict(capacity_target=dict(silo=1)), dict(valid_for_s=5)):
            with self.subTest(bad=bad), self.assertRaises(contract.LayerContractError):
                contract.validate_economy_intent(dict(ECONOMY, **bad))
        for bad in (dict(posture="charge"), dict(target=dict(enemy=7)), dict(composition_need=["lasers"])):
            with self.subTest(bad=bad), self.assertRaises(contract.LayerContractError):
                contract.validate_tactical_intent(dict(TACTICAL, **bad), enemies=[4])

    def test_every_layer_prompt_fits_the_input_budget_on_every_qualified_grammar(self):
        import test_native_delegation_prompt_v2_budget as budget
        from engine import Snapshot
        from fixtures import binding
        from host_runtime import model_capacity as capacity
        from http_adapter import system_prompt
        from tacticore_agent_runtime.factory import NetworkBackend

        effective = budget.effective(binding(), traits="中" * 100)
        profile = SimpleNamespace(personality=effective.style_index, traits=effective.traits)
        measure = NetworkBackend.__new__(NetworkBackend)
        measure._prompt = lambda value: system_prompt(profile, value)
        sizes = {}
        for name, raw, catalog in budget.grammar_cases():
            envelope = capacity._capacity_envelope(effective, Snapshot.from_dict(raw), dict(catalog))
            # Worst case lawful view: many enemy groups, bases and mining regions per enemy.
            groups = [
                group("region_%d_%d" % (i, j), role, 50, owner=4 + i % 2)
                for i in range(8)
                for j, role in enumerate(("structure", "economy", "armor", "infantry"))
            ]
            envelope["working_memory"]["battlefield"]["contact_groups"] = groups
            subject = decider(scenario=dict(map_id="x" * 128, enemy_player_ids=[4, 5], opponent_difficulty="brutal"))
            subject.world = build_world_state(envelope)
            subject.context = envelope
            for row in subject.detector.detect(subject.world):
                subject.recent_events.append(row)
            for index in range(10):
                subject.habits.record(index * 20.0, ["attackenemy", "focusenemy4"], region="region_1_1")
            for layer in ld.LAYERS:
                value = subject._layer_context(layer, 100.0, prematch=layer == "commander")
                size = measure.input_size(value)
                sizes[(name, layer)] = size
                self.assertLessEqual(size, capacity.LIMIT, (name, layer))
        self.assertLess(max(sizes.values()), capacity.LIMIT // 2, sizes)

    def test_prompts_carry_the_commander_voice(self):
        from layered_prompts import system_prompt

        profile = SimpleNamespace(traits=persona_text("hammer", tuple(HAMMER.values()), "窗口太整齐了。"))
        for layer in ld.LAYERS:
            text = system_prompt(profile, dict(decision_layer=layer, player_id=3, options=dict(enemies=[4])))
            self.assertIn("铁锤", text)
            self.assertIn("first person", text)


class ComposerTests(unittest.TestCase):
    def intents(self, now=100.0, **expiry):
        tactical = contract.validate_tactical_intent(TACTICAL, enemies=[4])
        economy = contract.validate_economy_intent(ECONOMY)
        command = contract.validate_directive(directive(), enemies=[4])
        return dict(
            commander=ld.LayerIntent(
                "commander", command, contract.directive_actions(command), now, expiry.get("commander", now + 120)
            ),
            economy=ld.LayerIntent(
                "economy", economy, contract.economy_actions(economy), now, expiry.get("economy", now + 60)
            ),
            tactical=ld.LayerIntent(
                "tactical", tactical, contract.tactical_actions(tactical), now, expiry.get("tactical", now + 30)
            ),
        )

    def test_one_owner_per_domain_merges_into_one_native_plan(self):
        from native_unified_contract_v5 import split_native7_intents

        result = ld.PlanComposer().compose(self.intents(), directive(), ALL_ACTIONS, 100.0)
        self.assertEqual(
            result.actions, ["budgeteconomy", "focusenemy4", "expand", "advanceconstruction", "attackenemy"]
        )
        self.assertEqual(result.valid_until, 130.0)
        flags, gates, focus = split_native7_intents(result.actions)
        self.assertEqual(focus, 4)
        self.assertEqual(gates, {0: True})

    def test_overrides_unavailable_and_expired_intents_are_dropped_with_reasons(self):
        rule = directive(overrides=["no_expansion"])
        rows = self.intents(tactical=103.0)
        result = ld.PlanComposer().compose(rows, rule, [a for a in ALL_ACTIONS if a != "advanceconstruction"], 100.0)
        reasons = {row["intent"]: row["reason"] for row in result.dropped}
        self.assertEqual(reasons["expand"], "directive_override_no_expansion")
        self.assertEqual(reasons["advanceconstruction"], "action_unavailable")
        self.assertEqual(reasons["attackenemy"], "intent_expired")
        self.assertEqual(result.actions, ["budgeteconomy", "focusenemy4"])
        legacy = ld.PlanComposer().compose(self.intents(), directive(), ALL_ACTIONS, 100.0, independent=False)
        self.assertIn(dict(intent="expand", reason="single_work_slot_taken_by_military"), legacy.dropped)

    def test_opening_owns_its_domains_and_revalidation_sees_a_changed_directive(self):
        rows = self.intents()
        rows["opening"] = ld.LayerIntent("opening", {}, dict(budget="budgettech", military="scout"), 100.0, 160.0)
        result = ld.PlanComposer().compose(rows, directive(), ALL_ACTIONS, 100.0)
        self.assertIn("budgettech", result.actions)
        self.assertIn("scout", result.actions)
        self.assertIn(dict(intent="budgeteconomy", reason="domain_owned_by_opening"), result.dropped)
        conflicts = ld.PlanComposer.conflicts(
            ["budgeteconomy", "focusenemy4", "expand"], directive(primary_enemy=5, overrides=["no_expansion"])
        )
        self.assertEqual(
            {row["reason"] for row in conflicts}, {"directive_primary_enemy_changed", "directive_override_no_expansion"}
        )
        subject = decider()
        subject.directive = directive()
        self.assertEqual(subject.revalidate(["budgetarmy"], 100.0)[0]["reason"], "directive_budget_changed")
        subject.intents["opening"] = rows["opening"]
        self.assertEqual(subject.revalidate(["budgettech", "scout"], 100.0), [])


class PersonalityTests(unittest.TestCase):
    def test_hammer_and_a_timid_custom_commander_decide_differently_on_the_same_situation(self):
        world = build_world_state(context(mobile=12, enemy_groups=[group("region_3_3", "armor", 10, seen=95.0)]))
        intent = contract.validate_tactical_intent(TACTICAL, enemies=[4])
        args = dict(directive=directive(), streak=None, loss_fraction=0.0, habits={})
        hammer, vetoes = review_tactical(intent, PersonalityRules.from_personality(HAMMER), world, **args)
        self.assertEqual((hammer["posture"], vetoes), ("attack", []))
        timid, vetoes = review_tactical(intent, PersonalityRules.from_personality(TIMID), world, **args)
        self.assertEqual(timid["posture"], "regroup")
        self.assertEqual(vetoes[0]["reason"], "force_ratio_below_threshold")

    def test_rules_are_explicit_numbers_per_parameter(self):
        hammer = PersonalityRules.from_personality(HAMMER)
        timid = PersonalityRules.from_personality(TIMID)
        self.assertLess(hammer.tactical_interval_s, timid.tactical_interval_s)
        self.assertLess(hammer.commander_interval_s, timid.commander_interval_s)
        self.assertGreater(hammer.harass_window_s, timid.harass_window_s)
        self.assertLess(hammer.bait_max_info_age_s, timid.bait_max_info_age_s)
        self.assertGreater(hammer.primary_enemy_hold_s, timid.primary_enemy_hold_s)
        self.assertIn("enemy_expansion_seen", hammer.punish_events)
        self.assertTrue(hammer.habit_enforced)
        self.assertFalse(timid.habit_enforced)

    def test_bait_losses_and_time_boxes_modify_staff_intents(self):
        rules = PersonalityRules.from_personality(HAMMER)
        stale = build_world_state(context(enemy_groups=[group("region_3_3", "armor", 2, seen=60.0)]))
        intent = contract.validate_tactical_intent(TACTICAL, enemies=[4])
        args = dict(directive=directive(), streak=None, loss_fraction=0.0, habits={})
        self.assertEqual(review_tactical(intent, rules, stale, **args)[1][0]["reason"], "bait_check_scout_first")
        fresh = build_world_state(context(enemy_groups=[group("region_3_3", "armor", 2, seen=99.0)]))
        lossy = dict(args, loss_fraction=0.6)
        self.assertEqual(review_tactical(intent, rules, fresh, **lossy)[0]["posture"], "withdraw")
        boxed = dict(args, streak=("attack", 100.0 - rules.attack_window_s))
        self.assertEqual(review_tactical(intent, rules, fresh, **boxed)[1][0]["reason"], "attack_time_box")
        harass = dict(intent, posture="harass")
        boxed = dict(args, streak=("harass", 100.0 - rules.harass_window_s))
        self.assertEqual(review_tactical(harass, rules, fresh, **boxed)[0]["posture"], "scout")
        habit = dict(
            args, habits=dict(flags=[dict(pattern="military_action")], top=dict(military_action="attackenemy"))
        )
        self.assertEqual(review_tactical(intent, rules, fresh, **habit)[0]["posture"], "harass")


class HabitTests(unittest.TestCase):
    def test_repeated_patterns_are_flagged_for_the_commander(self):
        audit = HabitAudit()
        for at in (100, 160, 220):
            audit.record(at, ["attackenemy", "focusenemy4"], region="region_1_1")
            audit.record(at + 20, ["regroup", "focusenemy4"])
        summary = audit.summary(0.7)
        patterns = {row["pattern"] for row in summary["flags"]}
        self.assertEqual(summary["top"]["focus_target"], "focusenemy4")
        self.assertIn("focus_target", patterns)
        self.assertIn("attack_region", patterns)
        self.assertIn("attack_timing", patterns)
        self.assertNotIn("military_action", patterns)


class OpeningTests(unittest.TestCase):
    def test_variants_are_chosen_from_scenario_and_personality(self):
        duel = dict(enemy_player_ids=[4], opponent_difficulty="medium")
        self.assertEqual(choose_opening(HAMMER, duel), "hammer_scout_raid")
        self.assertEqual(choose_opening(dict(HAMMER, risk=4), duel), "hammer_fast_expand")
        self.assertEqual(choose_opening(HAMMER, dict(enemy_player_ids=[4, 5])), "hammer_safe_tech")
        self.assertNotIn("hammer_fast_expand", eligible_openings(TIMID, duel))

    def test_timeline_harass_time_box_and_handover(self):
        executor = OpeningExecutor("hammer_scout_raid", harass_window_s=40)
        self.assertEqual(executor.step(5)["actions"], ["budgeteconomy"])
        self.assertIn("war_bear_scout_enemy_base", executor.step(6)["intended"])
        self.assertFalse(executor.step(6)["changed"])
        self.assertEqual(executor.step(80)["actions"], ["budgeteconomy", "raideconomy"])
        stopped = executor.step(115)
        self.assertEqual(stopped["actions"], ["budgeteconomy", "scout"])
        self.assertEqual(stopped["note"], "harass_stopped:harass_time_box")
        self.assertIsNone(executor.step(120, [dict(kind="scouting_report")]))
        self.assertEqual(executor.handover_reason, "scouting_report")
        other = OpeningExecutor("hammer_scout_raid", harass_window_s=40)
        other.step(75)
        self.assertEqual(other.step(76, [dict(kind="base_under_attack")])["note"], "harass_stopped:base_under_attack")
        self.assertIsNone(OpeningExecutor("hammer_safe_tech", 40).step(180))


class SchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_prematch_commander_then_opening_then_layers_on_cadence(self):
        backend = FakeBackend(replies=dict(commander=dict(directive(), opening_variant="hammer_fast_expand")))
        backend.replies.update(economy=ECONOMY, tactical=TACTICAL)
        subject = decider(backend=backend)
        await settle(subject, context(at=2.0), 2.0)
        self.assertEqual([c["decision_layer"] for c in backend.calls], ["commander"])
        self.assertEqual(backend.calls[0]["phase"], "pre_match")
        self.assertIn("hammer_fast_expand", backend.calls[0]["options"]["opening_variants"])
        self.assertEqual(subject.opening.variant_id, "hammer_fast_expand")
        await settle(subject, context(at=40.0), 40.0)
        self.assertEqual(len(backend.calls), 1)  # the opening makes no model calls
        self.assertEqual(subject.intents["opening"].actions["expansion"], "expand")
        seen = context(at=60.0, enemy_groups=[group("region_2_2", "structure", seen=60.0)])
        await settle(subject, seen, 60.0)
        self.assertTrue(subject.opening.done)
        self.assertEqual(sorted(c["decision_layer"] for c in backend.calls[1:]), ["commander", "economy", "tactical"])
        count = len(backend.calls)
        await settle(subject, seen, 65.0)
        self.assertEqual(len(backend.calls), count)
        await settle(subject, seen, 60.0 + subject.rules.tactical_interval_s)
        self.assertEqual(backend.calls[-1]["decision_layer"], "tactical")

    async def test_in_flight_layer_is_never_duplicated(self):
        gate = asyncio.Event()

        class Slow(FakeBackend):
            async def __call__(self, value):
                self.calls.append(value)
                await gate.wait()
                return directive()

        backend = Slow()
        subject = decider(backend=backend)
        for now in (2.0, 3.0, 200.0):
            subject.tick(context(at=now), now)
            await asyncio.sleep(0)
        self.assertEqual(len(backend.calls), 1)
        gate.set()
        await subject.drain()

    async def test_unknown_delivery_stops_composition_and_failed_commander_uses_fallback(self):
        subject = decider(backend=FakeBackend(fail={"commander"}))
        await settle(subject, context(at=2.0), 2.0)
        self.assertEqual(subject.directive_source, "fallback")
        self.assertEqual(subject.directive["route"], "tech_pressure")
        subject.dirty = True
        self.assertTrue(subject.wants_composition(40.0))
        subject.not_dispatched("macro_dispatch_outcome_unknown")
        self.assertFalse(subject.wants_composition(400.0))

    async def test_commander_grudge_and_economy_veto(self):
        replies = dict(commander=directive(), economy=ECONOMY, tactical=dict(TACTICAL, posture="scout"))
        subject = decider(backend=FakeBackend(replies=replies), scenario=dict(enemy_player_ids=[4, 5]))
        await settle(subject, context(at=2.0), 2.0)
        replies["commander"] = directive(primary_enemy=5)
        subject._start("commander", ["cadence"], 30.0)
        await asyncio.sleep(0)
        subject.tick(context(at=30.0), 30.0)
        self.assertEqual(subject.directive["primary_enemy"], 4)
        self.assertEqual(subject.intents["commander"].vetoes[0]["reason"], "grudge_hold_primary_enemy")
        timid = decider(personality=TIMID, backend=FakeBackend(replies=replies))
        await settle(timid, context(at=2.0, near_home=2), 2.0)
        timid.opening.done = True
        await settle(timid, context(at=200.0, near_home=2), 200.0)
        self.assertNotIn("expansion", timid.intents["economy"].actions)


class EndToEndTests(unittest.TestCase):
    def test_composed_policy_passes_the_unchanged_native_path_and_is_logged_per_layer(self):
        import test_delegation_boundary as base
        from host_runtime.macro_policy_runtime import MacroRequestAudit

        case = base.RoutingTests(methodName="runTest")
        case.setUp()
        self.addCleanup(case.doCleanups)
        host = case.host()
        log = DecisionLogWriter(
            host.output, host.run_id, commander=dict(id="hammer", name="铁锤"), decision_mode="layered"
        )
        host.decision_log = log
        subject = decider(log=log)
        subject._record_opening_variant()
        host.layered = subject
        now = case.view["game_time_seconds"]
        command = contract.validate_directive(
            directive(resource_split=dict(economy=0.2, army=0.6, tech=0.1, reserve=0.1)), enemies=[4]
        )
        subject.directive = command
        subject.intents["commander"] = ld.LayerIntent(
            "commander", command, contract.directive_actions(command), now, now + 120
        )
        subject.world = build_world_state(context(at=now))
        subject.context = context(at=now)
        entry = subject._entry("commander", now, intents=["budgetarmy"], reasoning="压上去。", directive=command)
        log.layer_decided(entry)
        audit = MacroRequestAudit(ld.ComposerBackend(subject, max_input_bytes=16384), host.event, strategic_only=True)
        decision = asyncio.run(case.agent.decide(case.view, audit))
        self.assertEqual(decision.status, "accepted", decision.reason_code)
        log.decided(decision)
        self.assertEqual(list(decision.plan.macro_actions), ["budgetarmy"])
        self.assertTrue(host.dispatch_plan(decision.plan))
        self.assertEqual(host.controller.calls, [["budgetarmy"]])
        log.finish(reason_code="user_stop")
        run = read_run_log(host.output)
        self.assertEqual(run["run"]["decision_mode"], "layered")
        self.assertEqual(run["run"]["commander"], dict(id="hammer", name="铁锤"))
        self.assertEqual(run["run"]["opening_variant"], "hammer_scout_raid")
        self.assertEqual(run["run"]["opening_variant_name"], "战熊侦察 + 恐怖机器人骚扰")
        record = run["decisions"][0]
        self.assertEqual(record["layer"], "commander")
        self.assertEqual(record["outcome"]["status"], "applied")
        self.assertEqual(record["directive"]["route"], "steady_growth")
        self.assertEqual(record["composer"]["applied_intents"], ["budgetarmy"])
        self.assertIn("focusenemy4", [row["intent"] for row in record["composer"]["dropped"]])
        self.assertEqual(record["decision"]["recorded_only"], [])

    def test_directive_change_before_dispatch_blocks_the_composed_plan(self):
        import test_delegation_boundary as base

        case = base.RoutingTests(methodName="runTest")
        case.setUp()
        self.addCleanup(case.doCleanups)
        plan = case.decide().plan
        host = case.host()
        host.layered = decider()
        host.layered.directive = directive(resource_split=dict(economy=0.6, army=0.2, tech=0.1, reserve=0.1))
        self.assertFalse(host.dispatch_plan(plan))
        self.assertEqual(host.controller.calls, [])
        self.assertTrue(host.layered.dirty)


class DecisionLogTests(unittest.TestCase):
    def test_rejected_layer_and_single_mode_records_carry_the_new_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            log = DecisionLogWriter(folder, "run", commander=dict(id="hammer", name="铁锤"), decision_mode="layered")
            subject = decider(log=log)
            subject.context = context()
            entry = subject._entry("tactical", 100.0, model=dict(latency_ms=5, input_bytes=900, error="bad"))
            log.layer_rejected(entry, "tactical_posture")
            opening = subject._entry(
                "opening", 30.0, intents=["scout"], objective="战熊侦察", recorded=["war_bear_scout_enemy_base"]
            )
            log.layer_decided(opening)
            log.finish(reason_code="user_stop")
            run = read_run_log(folder)
            first, second = run["decisions"]
            self.assertEqual((first["layer"], first["outcome"]["reason_code"]), ("tactical", "tactical_posture"))
            self.assertEqual(first["composer"], dict(applied_intents=[], dropped=[]))
            self.assertEqual(second["layer"], "opening")
            self.assertEqual(second["decision"]["recorded_only"], ["war_bear_scout_enemy_base"])
            self.assertEqual(second["outcome"]["reason_code"], "host_stopped_before_composition")
            self.assertEqual(run["run"]["opening_variant"], "hammer_scout_raid")

    def test_single_mode_records_are_commander_layer(self):
        import test_macro_host_decision_log as single

        case = single.HostDecisionLogTests(methodName="test_accepted_plan_dispatched_by_the_host_is_logged_as_applied")
        case.setUp()
        self.addCleanup(case.doCleanups)
        host = case.host_with_log()
        decision = case.decide_through(host)
        host.dispatch_plan(decision.plan)
        record = read_run_log(host.output)["decisions"][0]
        self.assertEqual(record["layer"], "commander")
        self.assertEqual(record["composer"]["applied_intents"], list(decision.plan.macro_actions))
        self.assertEqual(record["decision"]["recorded_only"], [])
        self.assertEqual(read_run_log(host.output)["run"]["decision_mode"], "single")


class ModeTests(unittest.TestCase):
    def test_layered_is_default_and_single_keeps_the_v2_call(self):
        with patch.dict(os.environ, {ld.ENVIRONMENT_VARIABLE: ""}):
            self.assertEqual(ld.decision_mode(), "layered")
            self.assertEqual(ld.decision_mode("single"), "single")
        with patch.dict(os.environ, {ld.ENVIRONMENT_VARIABLE: "single"}):
            self.assertEqual(ld.decision_mode(), "single")
        with patch.dict(os.environ, {ld.ENVIRONMENT_VARIABLE: "triple"}):
            with self.assertRaises(ContractError):
                ld.decision_mode()

    def test_host_cli_accepts_the_flag(self):
        import macro_host

        with patch.object(sys, "argv", ["macro_host.py", "--help"]), patch("sys.stdout"):
            with self.assertRaises(SystemExit):
                macro_host.main()
        self.assertEqual(ld.MODES, ("layered", "single"))


if __name__ == "__main__":
    unittest.main()
