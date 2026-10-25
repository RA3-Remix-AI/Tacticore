import asyncio
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest

from engine import Binding, ContractError, Snapshot, StrategyEngine, parse_model_json, validate_policy
from fixtures import COMMANDER, SESSION, binding, policy, snapshot


async def good(context):
    return policy(context)


class Contracts(unittest.TestCase):
    def test_unknown_power_is_preserved_and_invalid_known_power_rejected(self):
        value=snapshot();value["resources"]["power_balance"]=None
        parsed=Snapshot.from_dict(value)
        self.assertIsNone(parsed.power_balance)
        self.assertIsNone(parsed.model_context(binding())["resources"]["power_balance"])
        for bad in [True,"unknown",float("inf"),float("nan")]:
            value=snapshot();value["resources"]["power_balance"]=bad
            with self.subTest(bad=bad),self.assertRaises(ContractError):Snapshot.from_dict(value)

    def test_snapshot_rejects_nonfinite_bool_future_observation_and_unknown_fields(self):
        variants = []
        value = snapshot();value["resources"]["credits"] = float("nan");variants.append(value)
        value = snapshot();value["player_id"] = True;variants.append(value)
        value = snapshot();value["enemy_observations"][0]["observed_at_game_seconds"] = 101;variants.append(value)
        value = snapshot();value["raw_memory_address"] = "0x1234";variants.append(value)
        value = snapshot();value["capabilities"]["regions"].append("home_base");variants.append(value)
        for value in variants:
            with self.subTest(value=value), self.assertRaises(ContractError):
                Snapshot.from_dict(value)

    def test_policy_player_session_commander_snapshot_time_target_and_capability(self):
        request = Snapshot.from_dict(snapshot())
        context = request.model_context(binding())
        variants = [
            {"player_id": 2}, {"player_id": True}, {"session_id": "fce65015-2433-4b43-a18f-8b3cc70f2c7c"},
            {"commander_id": "another-commander"}, {"snapshot_id": 0}, {"based_on_game_time_seconds": 99},
            {"objective_region": "unknown_region"}, {"production_focus": "naval"},
            {"stance": "raid", "objective_region": None}, {"execute_lua": "print('no')"},
        ]
        for change in variants:
            with self.subTest(change=change), self.assertRaises(ContractError):
                validate_policy(policy(context, **change), request, request, binding(), 10)

    def test_budget_must_be_finite_bounded_sum_one_with_reserve(self):
        request = Snapshot.from_dict(snapshot());context = request.model_context(binding())
        for budget in [
            {"economy": .25, "army": .5, "tech": .05, "reserve": float("nan")},
            {"economy": .25, "army": 1.5, "tech": .05, "reserve": .2},
            {"economy": .25, "army": .5, "tech": .05, "reserve": True},
            {"economy": .25, "army": .5, "tech": .05, "reserve": .01},
            {"economy": .25, "army": .5, "tech": .05, "reserve": .3},
        ]:
            with self.subTest(budget=budget), self.assertRaises(ContractError):
                validate_policy(policy(context, budget=budget), request, request, binding(), 10)

    def test_model_json_rejects_duplicates_nan_large_and_invalid_encoding(self):
        for raw in ['{"stance":"raid","stance":"defend"}', '{"x":NaN}', "[1]", b"\xff", "\ud800", "x" * 17000]:
            with self.subTest(raw=repr(raw[:30])), self.assertRaises(ContractError):
                parse_model_json(raw)


class Coordinator(unittest.IsolatedAsyncioTestCase):
    async def test_valid_plan_and_dry_run_status(self):
        engine = StrategyEngine(binding())
        result = await engine.decide(snapshot(), good)
        self.assertEqual(result.status, "accepted")
        self.assertEqual(result.plan.production_focus, "anti_air")
        status = engine.public_status()
        self.assertEqual(status["service_state"], "holding")
        self.assertFalse(status["execution"]["enabled"])
        self.assertTrue(status["execution"]["dry_run"])
        self.assertFalse(status["binding"]["computer_verified"])
        self.assertEqual(status["binding"]["commander_id"], COMMANDER)

    async def test_snapshot_regression_binding_source_and_conflict(self):
        engine = StrategyEngine(binding());engine.observe(snapshot())
        for value in [snapshot(0, 99), snapshot(2, 101, player=2), snapshot(1, 101), snapshot(2, 101, source="game_bridge")]:
            with self.subTest(value=value), self.assertRaises(ContractError):
                engine.observe(value)
        engine.observe(snapshot())  # Idempotent duplicate is allowed.

    async def test_minimum_hold_avoids_request_and_identical_refresh_not_plan_change(self):
        engine = StrategyEngine(binding())
        first = await engine.decide(snapshot(), good)
        async def must_not_call(_):
            raise AssertionError("Model should not run during hold")
        held = await engine.decide(snapshot(2, 101), must_not_call)
        self.assertEqual(held.status, "held")
        self.assertEqual(first.plan.plan_id, held.plan.plan_id)
        self.assertEqual(engine.metrics["requests"], 1)
        refreshed = await engine.decide(snapshot(3, 116), good)
        self.assertEqual(refreshed.status, "accepted")
        self.assertEqual(engine.metrics["plan_changes"], 1)

    async def test_emergency_interrupts_hold_but_not_every_frame(self):
        engine = StrategyEngine(binding())
        async def raid(ctx):return policy(ctx, stance="raid", objective_region="east_ore")
        await engine.decide(snapshot(), raid)
        held = await engine.decide(snapshot(2, 101, events=["base_under_attack"]), good)
        self.assertEqual(held.status, "held")
        changed = await engine.decide(snapshot(3, 103, events=["base_under_attack"]), good)
        self.assertEqual(changed.status, "accepted")
        self.assertEqual(changed.plan.stance, "defend")

    async def test_invalid_policy_continues_unexpired_plan_without_extending_it(self):
        engine = StrategyEngine(binding())
        first = await engine.decide(snapshot(), good)
        async def bad(ctx):return policy(ctx, production_focus="arbitrary_script")
        rejected = await engine.decide(snapshot(2, 116), bad)
        self.assertEqual(rejected.status, "fallback_continuing")
        self.assertEqual(rejected.plan.plan_id, first.plan.plan_id)
        self.assertEqual(rejected.plan.expires_at_game_seconds, 130)
        expired = await engine.decide(snapshot(3, 131), bad)
        self.assertEqual(expired.status, "local_fallback")
        self.assertEqual(expired.plan.production_focus, "native_baseline")

    async def test_timeout_is_bounded_and_does_not_extend_fallback(self):
        engine = StrategyEngine(binding(), timeout_seconds=.01)
        async def slow(_):await asyncio.sleep(10)
        started = time.monotonic()
        first = await engine.decide(snapshot(), slow)
        self.assertLess(time.monotonic() - started, .3)
        self.assertEqual(first.status, "local_fallback")
        self.assertEqual(first.reason_code, "model_timeout")
        await asyncio.sleep(0)
        second = await engine.decide(snapshot(2, 105), slow)
        self.assertEqual(second.plan.plan_id, first.plan.plan_id)
        self.assertEqual(second.plan.expires_at_game_seconds, 110)

    async def test_stubborn_cancelled_adapter_cannot_spawn_unbounded_requests_or_commit_late(self):
        engine = StrategyEngine(binding(), timeout_seconds=.005)
        release = asyncio.Event()
        async def stubborn(ctx):
            try:await release.wait()
            except asyncio.CancelledError:await release.wait()
            return policy(ctx)
        first = await engine.decide(snapshot(), stubborn)
        await asyncio.sleep(0)
        second = await engine.decide(snapshot(2, 101), stubborn)
        self.assertEqual(second.reason_code, "adapter_still_cancelling")
        self.assertEqual(engine.metrics["requests"], 1)
        release.set();await asyncio.sleep(.01)
        self.assertEqual(engine.metrics["accepted"], 0)
        self.assertEqual(engine.current.plan_id, first.plan.plan_id)

    async def test_state_can_advance_during_request_but_stale_response_is_rejected(self):
        engine = StrategyEngine(binding())
        async def slow(ctx):
            engine.observe(snapshot(2, 112))
            return policy(ctx)
        result = await engine.decide(snapshot(), slow)
        self.assertEqual(result.reason_code, "stale_response")
        self.assertEqual(result.plan.snapshot_id, 2)

    async def test_fresh_advanced_state_accepts_request_bound_response(self):
        engine = StrategyEngine(binding())
        async def fresh(ctx):
            engine.observe(snapshot(2, 102))
            return policy(ctx)
        result = await engine.decide(snapshot(), fresh)
        self.assertEqual(result.status, "accepted")
        self.assertEqual(result.plan.snapshot_id, 1)
        self.assertEqual(engine.latest.snapshot_id, 2)

    async def test_capability_disappears_during_request(self):
        engine = StrategyEngine(binding())
        async def changed(ctx):
            next_state = snapshot(2, 102)
            next_state["capabilities"]["production_focus"].remove("anti_air")
            engine.observe(next_state)
            return policy(ctx)
        result = await engine.decide(snapshot(), changed)
        self.assertEqual(result.reason_code, "unsupported_production_focus")
        self.assertEqual(result.plan.production_focus, "native_baseline")

    async def test_new_critical_event_rejects_response_and_overrides_offensive_plan_locally(self):
        engine = StrategyEngine(binding(), min_hold_game_seconds=0)
        async def raid(ctx):return policy(ctx, stance="raid", objective_region="east_ore")
        await engine.decide(snapshot(), raid)
        async def event_arrives(ctx):
            engine.observe(snapshot(3, 103, events=["base_under_attack"]))
            return policy(ctx)
        result = await engine.decide(snapshot(2, 102), event_arrives)
        self.assertEqual(result.reason_code, "critical_event_after_request")
        self.assertEqual(result.plan.origin, "local_fallback")
        self.assertEqual(result.plan.stance, "defend")

    async def test_pause_uses_game_clock_and_does_not_request_or_execute(self):
        engine = StrategyEngine(binding())
        first = await engine.decide(snapshot(), good)
        async def forbidden(_):raise AssertionError("Paused request")
        result = await engine.decide(snapshot(2, 100, paused=True), forbidden)
        self.assertEqual(result.status, "paused")
        self.assertEqual(result.plan.plan_id, first.plan.plan_id)
        self.assertEqual(engine.metrics["requests"], 1)

    async def test_pause_while_waiting_prevents_new_plan_commit(self):
        engine = StrategyEngine(binding())
        async def paused(ctx):
            engine.observe(snapshot(2, 101, paused=True))
            return policy(ctx)
        result = await engine.decide(snapshot(), paused)
        self.assertEqual(result.status, "paused")
        self.assertIsNone(result.plan)

    async def test_stop_during_pending_request_cannot_resurrect_plan(self):
        engine = StrategyEngine(binding());started = asyncio.Event()
        async def slow(ctx):started.set();await asyncio.sleep(10);return policy(ctx)
        pending = asyncio.create_task(engine.decide(snapshot(), slow))
        await started.wait();engine.stop()
        result = await pending
        self.assertEqual(result.status, "stopped")
        self.assertIsNone(engine.current)
        self.assertEqual(engine.metrics["accepted"], 0)

    async def test_external_cancellation_is_not_swallowed(self):
        engine = StrategyEngine(binding());started = asyncio.Event()
        async def slow(_):started.set();await asyncio.sleep(10)
        pending = asyncio.create_task(engine.decide(snapshot(), slow));await started.wait();pending.cancel()
        with self.assertRaises(asyncio.CancelledError):await pending

    async def test_multi_commander_instances_can_share_adapter_without_cross_binding(self):
        other = "b563816c-204c-4689-9959-760cbdaf8052"
        first = StrategyEngine(binding(player=2));second = StrategyEngine(binding(player=3, commander=other))
        results = await asyncio.gather(first.decide(snapshot(player=2), good), second.decide(snapshot(player=3), good))
        self.assertEqual([r.plan.player_id for r in results], [2, 3])
        self.assertEqual([r.plan.commander_id for r in results], [COMMANDER, other])
        async def wrong(ctx):return policy(ctx, commander_id=COMMANDER)
        second.min_hold = 0
        rejected = await second.decide(snapshot(2, 101, player=3), wrong)
        self.assertEqual(rejected.reason_code, "policy_binding")
        self.assertEqual(rejected.plan.commander_id, other)

    async def test_status_atomic_json_and_audit_exclude_secret_fields_and_exception_text(self):
        secret = "sk-FAKE_SECRET_SHOULD_NEVER_APPEAR"
        with tempfile.TemporaryDirectory() as folder:
            audit = Path(folder)/"audit.jsonl";status = Path(folder)/"status.json"
            engine = StrategyEngine(binding(), audit_path=audit, status_path=status, min_hold_game_seconds=0)
            async def extra(ctx):
                self.assertNotIn("connection_id", ctx)
                self.assertNotIn("api_key", ctx)
                return policy(ctx, api_key=secret)
            await engine.decide(snapshot(), extra)
            async def error(_):raise ContractError(secret)
            result = await engine.decide(snapshot(2, 101), error)
            self.assertEqual(result.reason_code, "adapter_error")
            text = audit.read_text(encoding="utf-8") + status.read_text(encoding="utf-8")
            self.assertNotIn(secret, text)
            self.assertNotIn("api_key", text)
            for line in audit.read_text(encoding="utf-8").splitlines():json.loads(line)
            current = json.loads(status.read_text(encoding="utf-8"))
            self.assertFalse(current["execution"]["enabled"])
            self.assertEqual(current["mode"], "simulation")
            self.assertFalse(list(Path(folder).glob(".status-*")))

    async def test_game_bridge_snapshot_is_still_read_only_and_not_verified(self):
        engine = StrategyEngine(binding())
        await engine.decide(snapshot(source="game_bridge"), good)
        status = engine.public_status()
        self.assertEqual(status["mode"], "read_only")
        self.assertFalse(status["execution"]["enabled"])
        self.assertFalse(status["binding"]["computer_verified"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
