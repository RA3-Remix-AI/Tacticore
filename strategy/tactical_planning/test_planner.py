"""Synthetic planner/real-contract integration. No native, HTTP or credentials."""
import copy
import asyncio
from dataclasses import asdict, replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid

from battle_agent import BattleAgent, TacticalEvidence
from battlefield import validate_intents
from engine import Binding, ContractError, Snapshot, StrategyEngine
from fixtures import binding
from missions import Mission, MissionObservations, MissionProgress
from tactical_fixtures import tactical_snapshot, tactical_policy
from tactical_planning import (Limits, context_hints, memory_for_mission, plan_batch_for_agent,
                               plan_for_agent, plan_for_snapshot, replay)


ALL = ("main_attack", "harass_economy", "coordinate_force")
ROLES = ("infantry", "anti_air")


def snap(at=100, ident=1):
    raw = tactical_snapshot(ident, at)
    raw["battlefield"]["contacts"].append(dict(contact_id="contact_base", owner_player_id=4,
        relation="enemy", role="structure", region_id="east_ore", observed_at_game_seconds=at,
        currently_visible=True, stealth_state="visible"))
    return Snapshot.from_dict(raw)


def plan(purpose="main_attack", snapshot=None, memory=None, **kwargs):
    return plan_for_snapshot(binding(), snapshot or snap(), purpose, game_frame=kwargs.pop("game_frame", 1500),
        monotonic_ms=kwargs.pop("monotonic_ms", 1000), capability_purposes=kwargs.pop("capability_purposes", ALL),
        allowed_roles=kwargs.pop("allowed_roles", ROLES if purpose == "coordinate_force" else ("infantry",)),
        memory=memory, **kwargs)


def telemetry(memory, phase, seq=1, at=101, **facts):
    obs = MissionObservations(target_currently_visible=True, **facts)
    return MissionProgress(memory.session_id, memory.player_id, memory.commander_id, memory.source,
        memory.task_id, memory.task_id, seq, at, phase, memory.target_contact_id,
        memory.formation_versions, "a" * 64, obs)


class PlannerTests(unittest.TestCase):
    def test_three_purposes_produce_existing_validated_tactical_intent(self):
        for purpose in ALL:
            with self.subTest(purpose=purpose):
                result = plan(purpose)
                self.assertEqual(result.action, "propose")
                validated = validate_intents([result.intent.public()], snap(), snap())
                self.assertEqual(validated[0], result.intent)
                self.assertFalse(result.public()["execution_authorized"])
                self.assertFalse(result.public()["mission_completed"])
        self.assertEqual(plan().memory.target_contact_id, "contact_base")
        self.assertEqual(plan("harass_economy").memory.target_contact_id, "contact_ore")

    def test_missing_capability_or_roles_wait_without_task(self):
        self.assertEqual(plan(capability_purposes=()).reason_code, "capability_unavailable")
        self.assertEqual(plan("coordinate_force", allowed_roles=("infantry",)).reason_code, "capability_unavailable")
        field = snap().to_dict()
        field["battlefield"]["formations"][0]["roles"] = {"armor": 2}
        self.assertEqual(plan(snapshot=Snapshot.from_dict(field)).reason_code, "roles_unavailable")

    def test_harass_never_targets_non_economic_object(self):
        value = snap().to_dict()
        value["battlefield"]["contacts"] = [value["battlefield"]["contacts"][1]]
        self.assertEqual(plan("harass_economy", Snapshot.from_dict(value)).reason_code, "no_current_target")

    def test_hidden_and_expired_contacts_are_not_selected(self):
        value = snap().to_dict()
        for contact in value["battlefield"]["contacts"]:
            contact.update(currently_visible=False, observed_at_game_seconds=90)
        self.assertEqual(plan(snapshot=Snapshot.from_dict(value)).reason_code, "no_current_target")

    def test_contact_age_policy_can_be_stricter_than_wire_maximum(self):
        value = snap().to_dict()
        for contact in value["battlefield"]["contacts"]:contact["observed_at_game_seconds"] = 98
        self.assertEqual(plan(snapshot=Snapshot.from_dict(value), limits=Limits(max_contact_age_seconds=1)).reason_code,
                         "no_current_target")

    def test_stable_task_target_and_deadline_across_refresh_and_reorder(self):
        initial = plan()
        raw = snap(101, 2).to_dict()
        raw["battlefield"]["contacts"].reverse()
        raw["battlefield"]["formations"].reverse()
        result = plan(snapshot=Snapshot.from_dict(raw), memory=initial.memory, game_frame=1515, monotonic_ms=2000)
        self.assertEqual(result.action, "continue")
        self.assertIsNone(result.intent)  # refresh does not enqueue another task
        self.assertEqual(result.memory.task_id, initial.memory.task_id)
        self.assertEqual(result.memory.target_contact_id, initial.memory.target_contact_id)
        self.assertEqual(result.memory.deadline_game_seconds, initial.memory.deadline_game_seconds)
        self.assertEqual(result.memory.wall_deadline_ms, initial.memory.wall_deadline_ms)

    def test_target_disappears_requests_sticky_retreat_without_retarget(self):
        first = plan()
        raw = snap(101, 2).to_dict()
        raw["battlefield"]["contacts"] = [raw["battlefield"]["contacts"][0]]
        lost = plan(snapshot=Snapshot.from_dict(raw), memory=first.memory, game_frame=1515, monotonic_ms=2000)
        self.assertEqual((lost.action, lost.reason_code), ("request_retreat", "target_lost"))
        regained = plan(snapshot=snap(102, 3), memory=lost.memory, game_frame=1530, monotonic_ms=3000)
        self.assertEqual(regained.action, "request_retreat")
        self.assertEqual(regained.memory.target_contact_id, "contact_base")
        self.assertIsNone(regained.intent)

    def test_stop_and_deadlines_never_create_fresh_task_or_renew_limit(self):
        first = plan(limits=Limits(duration_game_seconds=15))
        stopped = plan(snapshot=snap(101, 2), memory=first.memory, game_frame=1515, monotonic_ms=2000, stop_requested=True)
        self.assertEqual(stopped.reason_code, "host_stop")
        expired = plan(snapshot=snap(115, 3), memory=first.memory, game_frame=1725, monotonic_ms=3000)
        self.assertEqual(expired.reason_code, "deadline")
        self.assertEqual(expired.memory.deadline_game_seconds, 115)
        wall = plan(snapshot=snap(101, 4), memory=first.memory, game_frame=1515, monotonic_ms=241000)
        self.assertEqual(wall.reason_code, "deadline")

    def test_paused_game_emits_no_new_task_but_wall_deadline_still_applies(self):
        paused = replace(snap(), paused=True)
        self.assertEqual(plan(snapshot=paused).reason_code, "game_paused")
        first = plan()
        outcome = plan(snapshot=paused, memory=first.memory, monotonic_ms=242000)
        self.assertEqual(outcome.action, "request_retreat")

    def test_formation_version_or_roles_changed_requests_retreat(self):
        first = plan()
        for change, expected in [("version", "formation_changed"), ("roles", "roles_lost")]:
            raw = snap(101, 2).to_dict()
            if change == "version":raw["battlefield"]["formations"][0]["version"] = 2
            else:raw["battlefield"]["formations"][0]["roles"] = {"armor": 1}
            result = plan(snapshot=Snapshot.from_dict(raw), memory=first.memory, game_frame=1515, monotonic_ms=2000)
            self.assertEqual(result.reason_code, expected)

    def test_reserved_elsewhere_is_never_claimed(self):
        self.assertEqual(plan(unavailable_formations=("formation_main",)).reason_code, "roles_unavailable")
        first = plan()
        self.assertEqual(plan(memory=first.memory, unavailable_formations=("formation_main",)).reason_code, "formation_changed")

    def test_combined_arms_waits_for_both_roles_and_coordination_telemetry(self):
        first = plan("coordinate_force")
        fact = telemetry(first.memory, "prepare", approach_verified=True)
        pending = plan("coordinate_force", snap(101, 2), first.memory, feedback=fact, game_frame=1515, monotonic_ms=2000)
        self.assertEqual(pending.memory.stage, "prepare")
        fact = telemetry(first.memory, "prepare", seq=2, at=102, approach_verified=True, coordination_verified=True)
        ready = plan("coordinate_force", snap(102, 3), pending.memory, feedback=fact, game_frame=1530, monotonic_ms=3000)
        self.assertEqual(ready.memory.stage, "engage")
        self.assertFalse(ready.public()["execution_authorized"])

    def test_reported_damage_requests_retreat_but_is_not_mission_completion(self):
        first = plan("harass_economy")
        fact = telemetry(first.memory, "engage", source_damage_amount=20)
        result = plan("harass_economy", snap(101, 2), first.memory, feedback=fact, game_frame=1515, monotonic_ms=2000)
        self.assertEqual(result.reason_code, "reported_effect")
        self.assertFalse(result.public()["mission_completed"])
        self.assertFalse(result.public()["field_verified"])

    def test_engage_limit_is_fixed_on_first_engage(self):
        first = plan()
        engaged = plan(snapshot=snap(101, 2), memory=first.memory, game_frame=1515, monotonic_ms=2000,
                       feedback=telemetry(first.memory, "engage"))
        self.assertEqual(engaged.memory.engage_started_game_seconds, 101)
        late = plan(snapshot=snap(131, 3), memory=engaged.memory, game_frame=1965, monotonic_ms=32000)
        self.assertEqual(late.reason_code, "engage_limit")
        changed_config = plan(snapshot=snap(131, 3), memory=engaged.memory, game_frame=1965,
                              monotonic_ms=32000, limits=Limits(max_engage_game_seconds=120))
        self.assertEqual(changed_config.reason_code, "engage_limit")

    def test_corrupted_memory_has_no_unbounded_deadline_or_invalid_identity(self):
        first = plan()
        for updates in [dict(deadline_game_seconds=10000), dict(wall_deadline_ms=1e14),
                        dict(task_id="bad-id"), dict(formation_versions=(("formation_main", True),)),
                        dict(required_roles=("air",))]:
            with self.subTest(updates=updates), self.assertRaises(ContractError):
                replace(first.memory, **updates)

    def test_lost_capability_and_native_interference_require_withdrawal(self):
        first = plan()
        lost = plan(memory=first.memory, capability_purposes=())
        self.assertEqual(lost.reason_code, "capability_lost")
        interrupted = plan(snapshot=snap(101, 2), memory=first.memory, game_frame=1515, monotonic_ms=2000,
                           feedback=telemetry(first.memory, "approach", interference="native_ai_override"))
        self.assertEqual(interrupted.reason_code, "native_interference")

    def test_combined_arms_ignores_rosters_with_unpermitted_extra_roles(self):
        value = snap().to_dict()
        value["battlefield"]["formations"][0]["roles"]["naval"] = 1
        self.assertEqual(plan("coordinate_force", snapshot=Snapshot.from_dict(value)).reason_code,
                         "roles_unavailable")

    def test_input_and_advice_never_accept_raw_native_fields(self):
        value = snap().to_dict()
        value["battlefield"]["contacts"][0]["native_address"] = "0x12345678"
        with self.assertRaises(ContractError):Snapshot.from_dict(value)
        result = json.dumps(plan().public())
        for forbidden in ["native_address", "object_id", "xyz", "0x12345678"]:
            self.assertNotIn(forbidden, result)

    def test_return_report_and_release_report_remain_distinct(self):
        first = plan()
        stopped = plan(memory=first.memory, stop_requested=True)
        returned = plan(snapshot=snap(101, 2), memory=stopped.memory, game_frame=1515, monotonic_ms=2000,
                        feedback=telemetry(first.memory, "retreat", retreat_verified=True))
        self.assertEqual(returned.action, "await_release")
        released = plan(snapshot=snap(102, 3), memory=returned.memory, game_frame=1530, monotonic_ms=3000,
                        feedback=telemetry(first.memory, "restored", seq=2, at=102,
                                           retreat_verified=True, restoration_verified=True))
        self.assertEqual(released.action, "closed")
        self.assertFalse(released.public()["control_release_verified"])
        self.assertEqual(plan(snapshot=snap(103, 4), memory=released.memory,
                              game_frame=1545, monotonic_ms=4000).action, "closed")

    def test_mismatched_feedback_or_changed_duplicate_rejected(self):
        first = plan()
        facts = telemetry(first.memory, "approach")
        for forged in [replace(facts, task_id=str(uuid.uuid4())), replace(facts, source="game_bridge"),
                       replace(facts, formation_versions=(("formation_main", 2),))]:
            with self.assertRaisesRegex(ContractError, "planning_feedback_binding"):
                plan(snapshot=snap(101, 2), memory=first.memory, feedback=forged,
                     game_frame=1515, monotonic_ms=2000)
        observed = plan(snapshot=snap(101, 2), memory=first.memory, feedback=facts,
                        game_frame=1515, monotonic_ms=2000)
        changed = replace(facts, observations=MissionObservations(True, approach_verified=True))
        with self.assertRaisesRegex(ContractError, "planning_feedback_duplicate_changed"):
            plan(snapshot=snap(102, 3), memory=observed.memory, feedback=changed, game_frame=1530, monotonic_ms=3000)

    def test_clock_regression_and_invalid_numbers_rejected(self):
        first = plan()
        for kwargs in [dict(game_frame=1499), dict(monotonic_ms=999), dict(snapshot=snap(99, 2))]:
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ContractError, "clock_regressed"):
                plan(memory=first.memory, **kwargs)
        for value in [float("nan"), float("inf"), True]:
            with self.assertRaises(ContractError):plan(monotonic_ms=value)

    def test_session_switch_discards_old_advice_without_cross_session_stop(self):
        first = plan()
        other = replace(binding(), session_id=str(uuid.uuid4()))
        new_snapshot = replace(snap(), session_id=other.session_id)
        result = plan_for_snapshot(other, new_snapshot, "main_attack", memory=first.memory,
                                  game_frame=1, monotonic_ms=1, capability_purposes=ALL, allowed_roles=("infantry",))
        self.assertEqual(result.action, "discard")
        self.assertIsNone(result.memory)
        self.assertIsNone(result.intent)

    def test_generation_change_cannot_reuse_memory_and_changes_new_id(self):
        first = plan()
        with self.assertRaisesRegex(ContractError, "planning_memory_identity"):
            plan(memory=first.memory, generation=2)
        self.assertNotEqual(plan(generation=2).memory.task_id, first.memory.task_id)

    def test_replay_same_inputs_same_bytes_and_digest_and_does_not_mutate_inputs(self):
        rows = [dict(snapshot=snap(100 + i, i + 1).to_dict(), game_frame=1500 + 15*i,
                     monotonic_ms=1000 + 1000*i) for i in range(3)]
        before = copy.deepcopy(rows)
        a = replay(binding(), "main_attack", rows, capability_purposes=ALL, allowed_roles=("infantry",))
        b = replay(binding(), "main_attack", copy.deepcopy(rows), capability_purposes=ALL, allowed_roles=("infantry",))
        self.assertEqual(a, b)
        self.assertEqual(rows, before)
        self.assertEqual([r["action"] for r in a["recommendations"]], ["propose", "continue", "continue"])
        self.assertEqual(a["game_commands"], 0)

    def test_cli_replay_and_duplicate_key_rejection(self):
        doc = dict(binding=asdict(binding()), purpose="main_attack", capability_purposes=list(ALL),
                   allowed_roles=["infantry"], rows=[dict(snapshot=snap().to_dict(), game_frame=1500, monotonic_ms=1000)])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"input.json"
            path.write_text(json.dumps(doc), encoding="utf-8")
            process = subprocess.run([sys.executable, "-B", "-m", "tactical_planning", str(path)],
                                     cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertFalse(json.loads(process.stdout)["execution_authorized"])
            path.write_text('{"purpose":"main_attack","purpose":"harass_economy"}', encoding="utf-8")
            process = subprocess.run([sys.executable, "-B", "-m", "tactical_planning", str(path)],
                                     cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True)
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("planning_replay_duplicate_key", process.stderr)

    def test_replay_rejects_live_label(self):
        row = dict(snapshot=replace(snap(), source="game_bridge").to_dict(), game_frame=1500, monotonic_ms=1000)
        with self.assertRaisesRegex(ContractError, "synthetic_required"):
            replay(binding(), "main_attack", [row])


class ExistingAgentAdapterTests(unittest.TestCase):
    def agent(self):
        purposes = (("attack", ("main_attack",)), ("raid", ("harass_economy",)),
                    ("combined_arms", ("coordinate_force",)))
        roles = (("attack", "main_attack", ("infantry",)), ("raid", "harass_economy", ("infantry",)),
                 ("combined_arms", "coordinate_force", ROLES))
        proof = TacticalEvidence(str(uuid.uuid4()), binding().session_id, 3, "simulated", purposes, roles)
        agent = BattleAgent(StrategyEngine(binding()), tactical_evidence=proof)
        agent.observe(snap())
        return agent

    def test_real_agent_adapter_uses_manifest_and_does_not_mutate_agent(self):
        agent = self.agent()
        before = copy.deepcopy(agent.public_memory())
        result = plan_for_agent(agent, "main_attack", game_frame=1500, monotonic_ms=1000)
        self.assertEqual(result.action, "propose")
        self.assertEqual(before, agent.public_memory())
        unverified = BattleAgent(StrategyEngine(binding()))
        unverified.observe(snap())
        self.assertEqual(plan_for_agent(unverified, "main_attack", game_frame=1500,
                                       monotonic_ms=1000).reason_code, "capability_unavailable")

    def test_batch_reserves_proposed_forms_and_does_not_reuse_them(self):
        agent = self.agent()
        out = plan_batch_for_agent(agent, ALL, game_frame=1500, monotonic_ms=1000)
        self.assertEqual(out["main_attack"].action, "propose")
        self.assertEqual(out["harass_economy"].reason_code, "roles_unavailable")
        self.assertEqual(out["coordinate_force"].reason_code, "roles_unavailable")
        self.assertEqual(agent.goals.tasks, [])

    def test_actual_agent_decision_accepts_each_purpose_through_existing_policy_guards(self):
        for purpose in ALL:
            with self.subTest(purpose=purpose):
                agent = self.agent()
                suggestion = plan_for_agent(agent, purpose, game_frame=1500, monotonic_ms=1000)
                self.assertEqual(suggestion.action, "propose")
                async def model(context):
                    return tactical_policy(context, [suggestion.intent.public()])
                result = asyncio.run(agent.decide(snap(), model))
                self.assertEqual(result.status, "accepted")
                task = next(task for task in agent.goals.tasks if task.request.purpose == purpose)
                self.assertEqual(task.request.target_contact_id, suggestion.intent.target_contact_id)
                self.assertEqual(task.status, "planned")
                self.assertFalse(agent.jobs()["execution_authorized"])

    def test_context_hints_are_bounded_and_keep_memory_out_of_model_projection(self):
        agent = self.agent()
        output = plan_batch_for_agent(agent, ALL, game_frame=1500, monotonic_ms=1000)
        context = agent.context(agent.latest.model_context(binding()), commit=False)
        hints = context_hints(output, context=context)
        self.assertNotIn("memory", json.dumps(hints))
        self.assertFalse(hints["execution_authorized"])
        with self.assertRaisesRegex(ContractError, "budget_exceeded"):
            context_hints(output, context=context, max_bytes=256)
        clipped = copy.deepcopy(context)
        clipped["working_memory"]["battlefield"]["contacts"] = []
        suppressed = context_hints(output, context=clipped)
        self.assertEqual(suppressed["recommendations"][0]["reason_code"], "omitted_from_model_context")
        self.assertIsNone(suppressed["recommendations"][0]["tactical_intent"])

    def test_adopt_real_mission_preserves_identity_deadline_and_original_wall_time(self):
        first = plan()
        m = first.memory
        mission = Mission(m.task_id, m.task_id, "attack", "main_attack", m.target_contact_id,
            "structure", m.target_region, m.retreat_region, m.formation_versions, m.required_roles,
            .5, 100, 280, updated_at_game_seconds=101)
        adopted = memory_for_mission(binding(), snap(101, 2), mission, game_frame=1515,
            monotonic_ms=2000, issued_monotonic_ms=1000)
        self.assertEqual(adopted.task_id, mission.task_id)
        self.assertEqual(adopted.deadline_game_seconds, 280)
        self.assertEqual(adopted.wall_deadline_ms, 241000)
        result = plan(snapshot=snap(102, 3), memory=adopted, game_frame=1530, monotonic_ms=3000)
        self.assertEqual(result.action, "continue")


if __name__ == "__main__":
    unittest.main()
