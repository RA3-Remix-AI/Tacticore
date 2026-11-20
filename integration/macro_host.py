"""Desktop-launched macro host; the native AI retains all unit operations.

One native runtime (native_runtime / native_transport). The model picks
high-level strategic intents; the native skirmish AI executes them.
"""

import argparse
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "integration"), str(ROOT / "strategy")]
from host_runtime.application import apply_commander_draft, load_commander_draft, create_applied_backend
from host_runtime.contracts import ContractError, SessionBinding
from host_runtime.decision_log import DecisionLogWriter, run_config_from_scenario
from host_runtime.desktop_backend import NativeHostSpawner, _atomic
from host_runtime.journal import CommandJournal
from host_runtime.layered_decision import MODES as DECISION_MODES, ComposerBackend, LayeredDecider, decision_mode
from host_runtime.profiles import commander_available, commander_info
from host_runtime.profile_store import ProfileStore
from host_runtime.macro_live import MacroSampler
from host_runtime.macro_bundle import digest
from host_runtime.macro_forces import observe_forces
from engine import Binding, StrategyEngine, ContractError as StrategyContractError
from battle_agent import BattleAgent
from http_adapter import load_profile
from prompt_versions import PROMPT_VERSIONS, active_prompt_version, select_prompt_version
from macro_strategy import MacroStrategyMemory
from host_runtime.native_runtime import NativeScope
from host_runtime.native_runtime_contract import FIELD_KIND, PROTOCOL
from host_runtime.strategic_controller import StrategicController
from host_runtime.strategic_feedback import StrategicRequestAudit, StrategicRuntime

LIMITS = dict(
    production_queue_observed=False,
    idle_producers_observed=False,
    queue_and_idle_numbers="unobserved_lower_bounds",
    own_roles_coverage="audited_templates_only",
    power_observed=False,
    payment_verified=False,
)
# Reason codes for a plan the controller refused before any native delivery.
NOT_DISPATCHED = {"macro_plan_expired_before_native_dispatch", "macro_action_not_currently_available"}


def native_transport_config(scope, manifest, max_wall_seconds=None):
    """Pure admission before attach; the DLL's absolute wall guard is only a backup."""
    if (
        type(scope) is not NativeScope
        or manifest.get("kind") != FIELD_KIND
        or manifest.get("protocol_version") != PROTOCOL
        or manifest.get("package_sha256") != scope.package_sha256
        or manifest.get("admission_ready") is not True
        or manifest.get("compile_only") is not False
        or tuple(manifest.get("flags", ())) != tuple(scope.action_flags.values())
        or len(scope.runtime_manifest_sha256) != 64
    ):
        raise ContractError("macro_native_transport_protocol_mismatch")
    wall = 3540 if max_wall_seconds is None else max_wall_seconds
    if type(wall) is not int or not 10 <= wall <= 3540:
        raise ContractError("macro_host_wall_bound")
    return dict(
        protocol_version=PROTOCOL,
        client_path=str(ROOT / "integration/host_runtime/native_transport.py"),
        max_wall_seconds=wall,
        maximum_host_wall_seconds=3540,
        heartbeat_loss_ms=5000,
        absolute_native_wall_ms=3600000,
        native_wall_guard_is_backup_only=True,
    )


def request_telemetry_ready(audited, snapshot, event):
    if not audited.fresh_for_game_seconds(snapshot["game_time_seconds"]):
        event("macro_decision_deferred", reason_code="macro_telemetry_frame_mismatch")
        return False
    return True


class MacroHost:
    def __init__(self, args):
        self.strategic_only = True
        self.args = args
        self.binding = SessionBinding.from_dict(json.loads(args.binding.read_text(encoding="utf8")))
        self.run_id = args.run_id
        self.started = time.monotonic()
        self.host_pid = os.getpid()
        self.host_start = NativeHostSpawner.identity(self.host_pid)
        self.session = json.loads(args.session.read_text(encoding="utf-8-sig"))
        if (
            self.session["session_id"] != self.binding.session_id
            or self.session["pid"] != self.binding.game_process_id
            or self.session["start_time"] != self.binding.game_process_start
            or self.session["mod_sha256"] != self.binding.mod_sha256
            or digest(self.session["game"]) != self.binding.game_sha256
        ):
            raise ContractError("session_mismatch")
        self.output = Path(self.session["run_directory"]) / "battle-host"
        if self.output.exists() and any(self.output.iterdir()):
            names = {p.name for p in self.output.iterdir()}
            stop = self.output / "stop.json"
            allowed = {"stop.json", "strategic-admission.jsonl"}
            if not names <= allowed or not stop.is_file():
                raise ContractError("run_state_conflict")
            value = json.loads(stop.read_bytes())
            if (
                value.get("session_id") != self.binding.session_id
                or value.get("run_id") != self.run_id
                or value.get("binding_hash") != self.binding.binding_hash
                or value.get("source") != "strategic_stop_admission_barrier_v1"
            ):
                raise ContractError("run_state_conflict")
        self.output.mkdir(exist_ok=True)
        self.store = ProfileStore(args.library, args.profile_state_dir)
        self.journal = CommandJournal(args.ledger)
        self.journal.register_run(self.run_id, self.binding.public())
        self.profile = self.store.get_profile(self.binding.commander_id)["profile"]
        if not commander_available(self.profile.get("commander_id", "hammer")):
            raise ContractError("commander_unavailable")
        self.decision_mode = decision_mode(getattr(args, "decision_mode", None))
        self.layered = None
        self.draft = load_commander_draft(args.commander_draft)
        self.expected_hash = self.profile["effective"]["effective_hash"]
        self.expected_revision = self.profile["revision"]
        self.phase = "starting"
        self.reason = "macro_preparing"
        self.latest = None
        self.backend = None
        self.agent = None
        self.startup_lawful_snapshots = []
        self.coherent_snapshot_id = None
        self.sampler = None
        self.transport = None
        self.controller = None
        self.pending = None
        self.application = None
        self.strategy_runtime = None
        self.strategy_audit = None
        self.prepared_macro_commands = {}
        self.native_transport_attached = False
        starts = self.journal.commands_for_run(self.run_id, operation="host_start")
        if (
            len(starts) != 1
            or starts[0]["payload"].get("profile_revision") != self.expected_revision
            or starts[0]["payload"].get("effective_hash") != self.expected_hash
            or starts[0]["payload"].get("capabilities", {}).get("native_macro") is not True
        ):
            raise ContractError("macro_host_launch_binding")
        self.check_profile()
        self.decision_log = self.open_decision_log()

    def open_decision_log(self):
        """One human-readable decisions.jsonl per run; see host_runtime.decision_log."""
        config = run_config_from_scenario(self.session.get("scenario"))
        teams = {key: config[key] for key in ("mode", "enemy_player_ids", "ally_player_ids", "human_player_ids")}
        commander = self.profile.get("commander_id", "hammer")
        mode = getattr(self, "decision_mode", "single")
        log = DecisionLogWriter(
            self.output,
            self.run_id,
            prompt_version=active_prompt_version(),
            provider=self.profile.get("provider"),
            model=self.profile.get("effective", {}).get("model"),
            map_id=config["map_id"],
            opponent_difficulty=config["opponent_difficulty"],
            player_id=config["model_player_id"] if config["model_player_id"] is not None else 3,
            opponent_player_ids=config["enemy_player_ids"],
            run_facts=teams,
            response_supplier=lambda: getattr(self.backend, "last_response", None),
            commander=dict(id=commander, name=commander_info(commander)["name"]),
            decision_mode=mode,
        )
        if mode == "single":
            # Layered runs write run_start once the opening variant is settled.
            log.start()
        return log

    def check_profile(self):
        current = self.store.get_profile(self.binding.commander_id)["profile"]
        if (
            current["validation"]["ok"] is not True
            or current["library_changed"]
            or current["revision"] != self.expected_revision
            or current["library_hash"] != self.profile["library_hash"]
            or current["effective"]["effective_hash"] != self.expected_hash
        ):
            raise ContractError("effective_profile_changed")

    def stopping(self):
        path = self.output / "stop.json"
        if path.exists():
            try:
                if json.loads(path.read_text(encoding="utf8")).get("session_id") == self.binding.session_id:
                    return True
            except (ValueError, OSError):
                raise ContractError("macro_stop_file_invalid") from None
        return False

    def event(self, kind, **facts):
        if kind.endswith("_prepared") and facts.get("plan_id") and facts.get("command_id"):
            self.prepared_macro_commands[facts["plan_id"]] = facts["command_id"]
        value = dict(
            session_id=self.binding.session_id,
            player_id=3,
            commander_id=self.binding.commander_id,
            wall_seconds=round(time.monotonic() - self.started, 3),
            **facts,
        )
        self.journal.append_event(
            self.run_id,
            kind,
            value,
            game_frame=int(self.latest["game_time_seconds"] * 15) if self.latest else None,
            monotonic_ns=time.monotonic_ns(),
        )
        with (self.output / "host-events.jsonl").open("a", encoding="utf8") as stream:
            stream.write(json.dumps(dict(kind=kind, **value), ensure_ascii=False, allow_nan=False) + "\n")
        decision_log = getattr(self, "decision_log", None)
        if decision_log is not None:
            decision_log.observe_event(kind, value)
        layered = getattr(self, "layered", None)
        if layered is not None and kind == "macro_plan_not_dispatched":
            layered.not_dispatched(facts.get("reason_code"))

    def publish(self):
        if getattr(self, "strategy_runtime", None) is not None:
            strategic_state = self.strategy_runtime.memory.public_state()
            _atomic(self.output / "macro-strategy-state.json", strategic_state)
        else:
            strategic_state = None
        current = self.agent.engine.current.public() if self.agent and self.agent.engine.current else None
        latest = None
        if self.latest:
            latest = {key: self.latest[key] for key in ("snapshot_id", "game_time_seconds", "paused", "resources")}
        status = dict(
            schema_version=1,
            kind="native_macro_host_v1",
            session_id=self.binding.session_id,
            pid=self.session["pid"],
            process_start=self.session["start_time"],
            host_pid=self.host_pid,
            host_start_time=self.host_start,
            state=self.phase,
            reason_code=self.reason,
            runtime_macro=dict(run_id=self.run_id, binding_hash=self.binding.binding_hash),
            native_transport_protocol=getattr(self, "transport_config", {}).get("protocol_version", PROTOCOL),
            execution=dict(
                enabled=self.phase == "running",
                dry_run=False,
                executor_connected=self.transport is not None,
                control_mode="macro_native",
                unit_operation_policy="native_ai",
                remaining_budget=0,
                commander_boundary="native_ai_details_v1",
            ),
            jobs=[],
            current_plan=getattr(self, "last_plan", None) or current,
            macro_strategy=strategic_state,
            macro_feedback=getattr(self, "last_feedback", None),
            macro_unified_feedback=getattr(self, "last_unified_feedback", None),
            metrics=dict(self.agent.engine.metrics) if self.agent else {},
            task_counters=dict(
                dispatches=len(self.controller.sent) if self.controller else 0,
                started=0,
                completed=0,
                failed=0,
                blocked=0,
            ),
            profile_application=self.application.public() if self.application else None,
            profile_consumption=self.backend.observation() if self.backend else None,
            latest_snapshot=latest,
        )
        _atomic(self.output / "host-status.json", status)

    def update_macro_control(self, game_seconds):
        scope = self.sampler.scope
        actions = ()
        if game_seconds >= scope.minimum_model_game_seconds and not self.latest["paused"]:
            actions = self.controller.available_actions(game_seconds)
        from host_runtime.delegation_boundary import strategic_actions

        actions = strategic_actions(actions)
        self.latest["macro_control"] = dict(
            mode="macro_native",
            available_actions=list(actions),
            production_counts={
                action: list(counts) for action, counts in scope.production_counts.items() if action in actions
            },
        )
        self.latest["macro_control"]["intent_contract"] = scope.intent_contract
        self.latest["macro_control"]["region_targets"] = {
            action: region for action, region in scope.regional_action_regions.items() if action in actions
        }

    def production_tick(self, native, *, update_capabilities=True):
        from host_runtime.native_observation import validate_sample

        frames = validate_sample(native, self.latest, self.transport, self.strategic_transport_binding)
        if frames is None:
            self.event("macro_sample_deferred", reason_code="unified_native_sample_out_of_phase")
            return False
        state = native["unified_native"]
        observation = native["observation"]
        if not self.controller.observe(observation, state, native["independent_controls"]):
            return False
        self.capability_sample_frames = frames
        self.capability_sample_kind = "rooted_strategy_v" + str(PROTOCOL)
        self.last_unified_feedback = self.controller.unified_feedback()
        if update_capabilities or self.latest["paused"]:
            self.update_macro_control(self.latest["game_time_seconds"])
        self.event("macro_unified_feedback", **self.last_unified_feedback)
        return True

    def observe_current(self, *, coherent_native=False):
        from host_runtime.delegation_boundary import restrict_snapshot

        self.latest = restrict_snapshot(self.latest)
        # Archive every successful lawful startup view immediately. Keep an
        # isolated copy to prime the agent later with the real original IDs.
        encoded = json.dumps(self.latest, ensure_ascii=False, allow_nan=False)
        with (self.output / "macro-snapshots.jsonl").open("a", encoding="utf8") as stream:
            stream.write(encoded + "\n")
        snapshot = json.loads(encoded)
        if getattr(self, "agent", None) is None:
            pending = getattr(self, "startup_lawful_snapshots", [])
            if len(pending) >= 8:
                raise ContractError("macro_startup_snapshot_bound")
            pending.append(snapshot)
            self.startup_lawful_snapshots = pending
        else:
            self.agent.observe(snapshot)
        if coherent_native:
            self.coherent_snapshot_id = snapshot["snapshot_id"]

    def prime_startup_snapshots(self):
        if getattr(self, "agent", None) is None:
            raise ContractError("macro_startup_agent_missing")
        # Acquisition order is authoritative; BattleAgent enforces monotonic
        # snapshots and the existing unseen/hidden-contact guards unchanged.
        pending = getattr(self, "startup_lawful_snapshots", [])
        for snapshot in pending:
            self.agent.observe(snapshot)
        self.event(
            "macro_startup_history_primed",
            snapshot_count=len(pending),
            first_snapshot_id=pending[0]["snapshot_id"] if pending else None,
            last_snapshot_id=pending[-1]["snapshot_id"] if pending else None,
            transport_constructor_started=False,
            attach_started=False,
        )
        self.startup_lawful_snapshots = []

    def consume_observation(self, native):
        coherent = self.production_tick(native)
        # VisibilityProjection has already retained this lawful view. Feed it
        # to agent memory even when native telemetry is discarded; otherwise a
        # later last-seen contact appears to change while hidden.
        self.observe_current(coherent_native=coherent)
        return coherent

    def refresh_dispatch_observation(self, plan):
        collect = getattr(getattr(self, "sampler", None), "collect", None)
        if not callable(collect):
            return True
        latest = self.collect_dispatch_view(collect, plan=plan)
        if latest is None:
            return False
        self.latest = latest
        self.last_forces = observe_forces(self.sampler.latest_census, self.sampler.safety)
        # Feed the real pre-view to history even if subsequent native sampling
        # fails. VisibilityProjection has already retained this observation.
        self.observe_current()
        if self.latest["paused"] or plan.expires_at_game_seconds <= self.latest["game_time_seconds"]:
            return True
        native = self.transport.observe("desktop_macro_dispatch_revalidation")
        # Refresh actual native predicates and bounded effects first.
        if not self.production_tick(native, update_capabilities=False):
            self.event(
                "macro_plan_not_dispatched", plan_id=plan.plan_id, reason_code="macro_dispatch_native_pair_deferred"
            )
            return False
        return self.observe_post_native_view(plan=plan)

    def collect_dispatch_view(self, collect, *, plan=None):
        """Discard unstable reads before preparing or dispatching a decision."""
        try:
            latest = collect()
        except ContractError:
            raise
        except (ValueError, RuntimeError):
            self.post_native_view_failures = getattr(self, "post_native_view_failures", 0) + 1
            if self.post_native_view_failures > 5:
                raise ContractError("macro_observation_unstable") from None
            if plan is None:
                self.event("macro_decision_deferred", reason_code="macro_post_native_view_unstable")
            else:
                self.event(
                    "macro_plan_not_dispatched", plan_id=plan.plan_id, reason_code="macro_post_native_view_unstable"
                )
            return None
        self.post_native_view_failures = 0
        return latest

    def observe_post_native_view(self, *, plan=None):
        """Get a true post-view after native memory mutations, without retiming."""
        collect = getattr(getattr(self, "sampler", None), "collect", None)
        if not callable(collect):
            raise ContractError("macro_post_native_view_unavailable")
        latest = self.collect_dispatch_view(collect, plan=plan)
        if latest is None:
            return False
        self.latest = latest
        self.last_forces = observe_forces(self.sampler.latest_census, self.sampler.safety)
        coherent_native = False
        try:
            if self.latest["paused"]:
                return True
            if plan is not None and plan.expires_at_game_seconds <= self.latest["game_time_seconds"]:
                return True
            pair = getattr(self, "capability_sample_frames", None)
            frame = self.latest["game_time_seconds"] * 15
            if pair is None or any(not -1e-6 <= frame - value <= 15 + 1e-6 for value in pair):
                if plan is None:
                    self.event("macro_decision_deferred", reason_code="macro_request_native_pair_stale")
                else:
                    self.event(
                        "macro_plan_not_dispatched",
                        plan_id=plan.plan_id,
                        reason_code="macro_dispatch_native_pair_stale",
                    )
                return False
            # A new qualification at the post-view time, never a copy of the
            # request's actions or the sampler's budget-only defaults.
            self.update_macro_control(self.latest["game_time_seconds"])
            coherent_native = True
        finally:
            self.observe_current(coherent_native=coherent_native)
        return True

    def response_observation_ready(self):
        latest = self.agent.latest
        return latest is not None and (
            latest.paused or latest.snapshot_id == getattr(self, "coherent_snapshot_id", None)
        )

    def prepare_model_request(self, audited):
        """Capture one request synchronously before any async scheduling gap."""
        if not self.observe_post_native_view():
            return None
        if self.latest["paused"]:
            return None
        if not request_telemetry_ready(audited, self.latest, self.event):
            return None
        from host_runtime.prepared_request import prepare_macro_request_v1

        ready = self.response_observation_ready
        try:
            return prepare_macro_request_v1(self.agent, audited, self.agent.latest, response_ready=ready)
        except (ContractError, StrategyContractError) as error:
            code = getattr(error, "code", None) or str(error)
            if code != "strategy_context_before_memory":
                raise
            # A new real observation is required; never move the old time or
            # insert a newer memory into an older request to make it pass.
            self.event("macro_decision_deferred", reason_code=code)
            return None

    def dispatch_plan(self, plan):
        # Retain only decisions deferred before any controller invocation.
        # Unknown native outcomes never enter this retry path.
        self.pending_dispatch = None
        from host_runtime.delegation_boundary import validate_policy

        try:
            validate_policy(plan)
        except ContractError as error:
            self.event("macro_plan_not_dispatched", plan_id=plan.plan_id, reason_code=error.code)
            return False
        if getattr(self, "strategy_runtime", None) is not None:
            if not self.refresh_dispatch_observation(plan):
                self.pending_dispatch = plan
                return False
        if self.latest["paused"] or plan.expires_at_game_seconds <= self.latest["game_time_seconds"]:
            self.event("macro_plan_not_dispatched", plan_id=plan.plan_id, reason_code="expired_or_paused")
            return False
        review = None
        if getattr(self, "strategy_runtime", None) is not None:
            try:
                current = self.agent.context(self.agent.latest.model_context(self.agent.engine.binding), commit=False)
                review = self.strategy_runtime.review(
                    plan, self.strategy_audit, self.strategy_audit.prepare(current), controller=self.controller
                )
            except ContractError as error:
                self.event("macro_plan_not_dispatched", plan_id=plan.plan_id, reason_code=error.code)
                return False
            if not review.allowed:
                self.event("macro_plan_not_dispatched", plan_id=plan.plan_id, reason_code=review.reason_code)
                return False
        layered = getattr(self, "layered", None)
        if layered is not None:
            # The directive may have changed while the composed request was in flight.
            conflicts = layered.revalidate(plan.macro_actions, self.latest["game_time_seconds"])
            if conflicts:
                self.event(
                    "macro_plan_not_dispatched",
                    plan_id=plan.plan_id,
                    reason_code="composer_directive_changed",
                    conflicts=conflicts,
                )
                return False
        try:
            receipt = self.controller.dispatch(
                plan, self.latest["game_time_seconds"], effective_hash=self.expected_hash, paused=False
            )
        except ContractError as error:
            if layered is not None:
                layered.not_dispatched(error.code)
            if error.code == "macro_dispatch_outcome_unknown" and getattr(self, "strategy_runtime", None) is not None:
                command_id = self.prepared_macro_commands.get(plan.plan_id)
                if command_id is not None:
                    self.strategy_runtime.dispatched(
                        review, plan, None, self.latest["game_time_seconds"], unknown_command_id=command_id
                    )
            if error.code not in NOT_DISPATCHED:
                raise
            # No native delivery was attempted; the next decision uses new facts.
            self.event("macro_plan_not_dispatched", plan_id=plan.plan_id, reason_code=error.code)
            return False
        if getattr(self, "strategy_runtime", None) is not None:
            if hasattr(self, "journal") and type(receipt) is dict:
                recorded = self.journal.get_command(self.run_id, receipt["command_id"])
                proof = recorded.get("receipt") or {}
                if (
                    recorded["status"] != "completed"
                    or recorded["payload"].get("actions") != list(plan.macro_actions)
                    or proof.get("seq") != receipt.get("seq")
                ):
                    raise ContractError("strategy_native_receipt_required")
                receipt = dict(
                    receipt,
                    **{key: proof[key] for key in ("native_start_frame", "native_deadline_frame") if key in proof},
                )
            self.strategy_runtime.dispatched(review, plan, receipt, self.latest["game_time_seconds"])
        self.last_plan = plan.public()
        if layered is not None:
            layered.dispatched(plan, self.latest["game_time_seconds"])
        self.event("plan_applied", plan_id=plan.plan_id, snapshot_id=plan.snapshot_id, plan=plan.public())
        return True

    def layered_context(self):
        """The lawful prepared context the layers read; None when no coherent view exists yet."""
        from host_runtime.delegation_boundary import restrict_context

        try:
            current = self.agent.context(self.agent.latest.model_context(self.agent.engine.binding), commit=False)
        except Exception:
            return None
        try:
            return self.strategy_audit.prepare(current)
        except Exception:
            return restrict_context(current)

    def create_layered(self, model_input_limit):
        """Layered mode: the composer stands where the model backend stood in the request audit."""
        commander = self.application.effective.commander_id
        self.layered = LayeredDecider(
            backend=self.backend,
            binding=dict(commander_id=self.binding.commander_id, session_id=self.binding.session_id, player_id=3),
            commander=dict(id=commander, name=commander_info(commander)["name"]),
            personality=self.application.effective.personality_dict(),
            scenario=run_config_from_scenario(self.session.get("scenario")),
            event=lambda kind, **facts: self.event(kind, **facts),
            log=getattr(self, "decision_log", None),
            max_input_bytes=model_input_limit,
        )
        return ComposerBackend(self.layered, max_input_bytes=model_input_limit)

    def create_controller(self):
        return StrategicController(
            self.transport,
            self.journal,
            self.run_id,
            self.sampler.scope,
            self.binding.session_id,
            self.expected_hash,
            self.event,
        )

    def finish_transport(self):
        from host_runtime.native_lifecycle import finish

        return finish(self)

    def record_run_exception(self, error):
        """Classify only a known result signal from a returned constructor.

        This is a candidate, never visual confirmation or a cleanup proof.
        The verified native return in run.finally still decides safe termination.
        """
        if isinstance(error, ContractError) and error.code == "strategic_stop_already_committed" and self.stopping():
            self.phase = "stopped"
            self.reason = "user_stop"
            self.event("macro_dispatch_cancelled_before_stop_barrier", reason_code="user_stop")
            return
        candidate = (
            isinstance(error, ContractError)
            and error.code in ("macro_match_ended", "macro_native_result_candidate")
            and getattr(self, "native_transport_attached", False) is True
            and self.transport is not None
        )
        if candidate:
            try:
                _atomic(self.output / "result-native-state.json", self.sampler.state)
            except BaseException as archive_error:
                self.event(
                    "macro_result_candidate_archive_failed",
                    native_reason_code=error.code,
                    error_type=type(archive_error).__name__,
                )
                error = archive_error
                candidate = False
        self.phase = "result_candidate" if candidate else "fault"
        if candidate:
            self.reason = "native_result_requires_visual_confirmation"
        else:
            self.reason = error.code if isinstance(error, ContractError) else "macro_host_failed"
        if (
            not candidate
            and isinstance(error, StrategyContractError)
            and re.fullmatch(r"[a-z][a-z0-9_]{0,79}", str(error))
        ):
            self.reason = str(error)
        frames = []
        for frame in traceback.extract_tb(error.__traceback__)[-12:]:
            path = Path(frame.filename)
            name = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name
            frames.append(dict(file=name, line=frame.lineno, function=frame.name))
        self.event(
            "macro_result_candidate" if candidate else "host_fault",
            reason_code=self.reason,
            native_reason_code=error.code if candidate else None,
            error_type=type(error).__name__,
            source_frames=frames,
        )

    def check_model_capacity(self, scope):
        from host_runtime.model_capacity import check_model_capacity
        from macro_policy import public_descriptions

        provider = self.profile.get("provider")
        if provider not in ("DeepSeek", "OpenAI", "自定义"):
            raise ContractError("model_context_capacity_provider_unavailable")
        if provider != self.application.profile.provider:
            raise ContractError("effective_profile_changed")
        catalog = public_descriptions(scope.available_actions, region_targets=scope.regional_action_regions.items())
        catalog.update(scope.model_catalog_overrides())
        capacity = check_model_capacity(self.application.effective, provider, self.latest, catalog)
        self.event("macro_model_capacity_checked", native_constructor_started=False, capacity=capacity)
        if not capacity["fits"]:
            raise ContractError(capacity["reason_code"])

    def attach_transport(self, admission):
        path = self.transport_config["client_path"]
        spec = importlib.util.spec_from_file_location("desktop_macro_native_transport", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        from host_runtime.native_lifecycle import report_directory

        admitted = {"admission_id": admission["admission_id"]} if admission is not None else {}
        self.event(
            "macro_native_transport_constructor_begin",
            constructor_boundary_entered=True,
            attach_started=None,
            **admitted,
        )
        self.transport = module.MacroPolicyProbe.__new__(module.MacroPolicyProbe)
        self.transport.__init__(
            self.args.session,
            self.sampler.owner,
            Path(self.sampler.bundle["build"]),
            report_directory(self.session),
            build_feedback=False,
        )
        self.native_transport_attached = True
        self.transport.configure_stop_gate(self.stop_gate)
        self.event("macro_native_transport_constructor_returned", constructor_returned=True, attach_started=None)
        from host_runtime.native_observation import bind_transport

        self.strategic_transport_binding = bind_transport(self.transport, self.session)

    async def run(self):
        last_request = -100.0
        failures = 0
        self.native_transport_attached = False
        try:
            self.event("macro_startup_stage", stage="qualification_begin")
            from host_runtime.native_runtime import current, load

            # One full runtime verification per Host start (every file against the pinned manifest).
            root, pin, inventory, manifest = current()
            bundle, scope = load(self.args.macro_bundle, self.session)
            self.native_scope = scope
            self.event("macro_startup_stage", stage="qualification_verified")
            self.transport_config = native_transport_config(
                scope, manifest, getattr(self.args, "max_wall_seconds", None)
            )
            self.args.max_wall_seconds = self.transport_config["max_wall_seconds"]
            bundle_sha = digest(self.args.macro_bundle)
            _atomic(
                self.output / "native-transport-preflight.json",
                dict(
                    kind="native_macro_host_preflight",
                    schema_version=1,
                    bundle_sha256=bundle_sha,
                    scope=scope.public(),
                    transport=self.transport_config,
                    attach_started=False,
                ),
            )
            from host_runtime.native_lifecycle import freeze

            freeze(self)
            self.sampler = MacroSampler(self.args.session, self.args.macro_bundle, scope=(bundle, scope))
            if digest(self.args.macro_bundle) != bundle_sha:
                raise ContractError("session_changed")
            self.latest = self.sampler.collect()
            self.observe_current()
            self.check_profile()
            self.last_forces = observe_forces(self.sampler.latest_census, self.sampler.safety)
            self.event("macro_startup_stage", stage="lawful_sampler_ready")
            _atomic(self.output / "visibility-proof.json", self.sampler.proof)
            _atomic(self.output / "participants.json", self.sampler.participants)
            self.application = apply_commander_draft(
                load_profile(self.args.library, self.binding.commander_id), self.draft
            )
            if self.application.effective.effective_hash != self.expected_hash:
                raise ContractError("effective_profile_changed")
            from host_runtime.stop_gate import StopGate

            self.stop_gate = StopGate(self.run_id, self.binding, self.output)
            model_input_limit = scope.maximum_model_input_bytes
            self.backend = create_applied_backend(
                self.application,
                event_sink=lambda kind, payload: self.event(kind, **payload),
                request_admission=self.stop_gate.admit,
                backend="pydantic",
                timeout=28,
                max_tokens=8192,
                max_input_bytes=model_input_limit,
                # Economy and tactical layers may ask concurrently; the commander stays serial.
                max_inflight=2 if self.decision_mode == "layered" else 1,
            )
            engine = StrategyEngine(
                Binding(
                    self.binding.session_id,
                    3,
                    self.binding.commander_id,
                    self.profile["name"],
                    self.profile["connection_id"],
                ),
                timeout_seconds=30,
                max_response_age_seconds=30,
                min_hold_game_seconds=15,
                audit_path=self.output / "plans.jsonl",
                status_path=self.output / "strategy-status.json",
            )
            self.agent = BattleAgent(
                engine,
                memory_path=self.output / "agent-state.json",
                jobs_path=self.output / "jobs.json",
                context_budget_bytes=model_input_limit,
            )
            if getattr(self.args, "strategy_mode", "declared") == "declared":
                memory = MacroStrategyMemory(
                    session_id=self.binding.session_id,
                    commander_id=self.binding.commander_id,
                    player_id=3,
                    profile_revision=self.expected_revision,
                    effective_hash=self.expected_hash,
                )
                self.strategy_runtime = StrategicRuntime(memory, self.event)
            self.prime_startup_snapshots()
            self.check_model_capacity(scope)
            with self.stop_gate.admit("native_constructor") as admission:
                self.attach_transport(admission)
            self.controller = self.create_controller()
            request_backend = self.backend
            if self.decision_mode == "layered":
                request_backend = self.create_layered(model_input_limit)
            audited = StrategicRequestAudit(
                request_backend,
                self.event,
                feedback_supplier=lambda: getattr(self, "last_feedback", None),
                forces_supplier=lambda: getattr(self, "last_forces", None),
                catalog_supplier=scope.model_catalog_overrides,
                strategy_supplier=self.strategy_runtime.memory.context if self.strategy_runtime is not None else None,
                strategic_only=True,
                unified_supplier=lambda: self.last_unified_feedback,
            )
            self.strategy_audit = audited
            self.event(
                "host_started",
                execution_requested=True,
                control_mode="macro_native",
                commander_boundary="native_ai_details_v1",
                decision_mode=self.decision_mode,
            )
            self.event("commander_profile_applied", **self.application.public())
            while time.monotonic() - self.started < self.args.max_wall_seconds:
                if self.stopping():
                    self.reason = "user_stop"
                    break
                self.check_profile()
                try:
                    self.latest = self.sampler.collect()
                    failures = 0
                    self.last_forces = observe_forces(self.sampler.latest_census, self.sampler.safety)
                except ContractError:
                    raise
                except (ValueError, RuntimeError):
                    failures += 1
                    if failures > 5:
                        raise ContractError("macro_observation_unstable") from None
                    await asyncio.sleep(0.2)
                    continue
                native = self.transport.observe("desktop_macro_tick")
                if not self.consume_observation(native):
                    self.phase = "sampling_wait"
                    self.reason = "macro_native_pair_pending"
                    self.publish()
                    await asyncio.sleep(0.2)
                    continue
                if "observation" in native:
                    feedback = self.controller.feedback(native["observation"])
                    feedback.update(LIMITS)
                    self.last_feedback = feedback
                    self.agent.feedback.append(feedback)
                    self.event("macro_native_feedback", **feedback)
                    with (self.output / "macro-feedback.jsonl").open("a", encoding="utf8") as stream:
                        stream.write(json.dumps(feedback) + "\n")
                if getattr(self, "strategy_runtime", None) is not None:
                    strategy_native = self.transport.native_status()
                    self.strategy_runtime.observe(
                        self.controller,
                        strategy_native,
                        max(self.latest["game_time_seconds"], strategy_native["last_frame"] / 15),
                        budget_feedback=getattr(self, "last_feedback", None),
                    )
                if self.pending is not None and self.pending.done():
                    result = await self.pending
                    self.pending = None
                    self.event("decision", status=result.status, reason_code=result.reason_code)
                    if getattr(self, "decision_log", None) is not None:
                        self.decision_log.decided(result)
                    if result.status == "accepted":
                        if self.stopping():
                            self.reason = "user_stop"
                            break
                        self.check_profile()
                        if self.backend.observation()["real_network_verified"]:
                            self.dispatch_plan(result.plan)
                deferred = getattr(self, "pending_dispatch", None)
                if deferred is not None:
                    if self.stopping():
                        self.reason = "user_stop"
                        break
                    self.check_profile()
                    self.dispatch_plan(deferred)
                self.phase = "paused" if self.latest["paused"] else "running"
                self.reason = "observing"
                now = self.latest["game_time_seconds"]
                if self.layered is not None:
                    # Layer calls are not gated by the native minimum time: the pre-match
                    # commander call happens at once. Only composed dispatch waits.
                    self.layered.tick(self.layered_context(), now, model_allowed=not self.latest["paused"])
                    due = self.layered.wants_composition(now)
                else:
                    due = time.monotonic() - last_request >= 12
                ready = (
                    self.pending is None
                    and not self.latest["paused"]
                    and now >= scope.minimum_model_game_seconds
                    and getattr(self, "pending_dispatch", None) is None
                    and due
                )
                if ready:
                    # Live snapshot and native feedback are read sequentially.
                    # If those reads span too many frames, wait for a coherent
                    # next sample instead of counting an unsent provider error.
                    if self.strategy_runtime is not None:
                        prepared = self.prepare_model_request(audited)
                        if prepared is not None:
                            from host_runtime.prepared_request import decide_prepared_macro_request_v1

                            self.pending = asyncio.create_task(
                                decide_prepared_macro_request_v1(self.agent, self.agent.latest, prepared)
                            )
                            last_request = time.monotonic()
                    elif request_telemetry_ready(audited, self.latest, self.event):
                        self.pending = asyncio.create_task(self.agent.decide(self.latest, audited))
                        last_request = time.monotonic()
                self.publish()
                await asyncio.sleep(0.5)
            else:
                self.reason = "host_time_limit"
        except BaseException as error:
            self.record_run_exception(error)
        finally:
            await self.shutdown()
        return dict(state=self.phase, reason_code=self.reason, runtime=str(self.output))

    async def shutdown(self):
        self.event("macro_host_stop_started", reason_code=self.reason)
        if self.pending:
            if not self.pending.done():
                self.pending.cancel()
            await asyncio.gather(self.pending, return_exceptions=True)
        if getattr(self, "layered", None) is not None:
            await self.layered.drain()
        if self.agent:
            self.agent.stop()
            await self.agent.engine.drain_obsolete_request()
        try:
            self.finish_transport()
        except BaseException:
            self.phase = "fault"
            self.reason = "macro_stop_unverified"
        finally:
            if getattr(self, "strategy_runtime", None) is not None:
                self.strategy_runtime.memory.stop()
        # On an unverified return keep the SDK (mapping, heartbeat) alive and
        # only re-read STOP/return; never re-send a command.
        probe = getattr(getattr(self, "transport", None), "_probe", None)
        while (
            probe is not None and getattr(probe, "state", None) is not None and getattr(probe, "host", None) is not None
        ):
            self.phase = "fault"
            self.reason = "macro_stop_unverified"
            self.publish()
            await asyncio.sleep(1)
            try:
                self.transport.close()
            except BaseException:
                continue
        if self.sampler:
            self.sampler.close()
        if self.phase not in ("fault", "result_candidate"):
            self.phase = "stopped"
        self.publish()
        if getattr(self, "decision_log", None) is not None:
            self.decision_log.finish(
                match_result=getattr(self.sampler, "match_result", None),
                game_time_s=self.latest.get("game_time_seconds") if isinstance(self.latest, dict) else None,
                reason_code=self.reason,
            )
        self.event("host_stopped", reason_code=self.reason)
        self.store.close()
        self.journal.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("session", "macro-bundle", "library", "commander-draft", "profile-state-dir", "binding", "ledger"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--strategy-mode", choices=("declared", "legacy"), default="declared")
    parser.add_argument(
        "--prompt-version",
        choices=PROMPT_VERSIONS,
        default=None,
        help="Strategic prompt version; default from TACTICORE_PROMPT_VERSION, else v2",
    )
    parser.add_argument(
        "--decision-mode",
        choices=DECISION_MODES,
        default=None,
        help="layered (default) or single (v2 single call); default from TACTICORE_DECISION_MODE",
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--max-wall-seconds", type=int, default=None)
    args = parser.parse_args()
    if args.prompt_version is not None:
        select_prompt_version(args.prompt_version)
    try:
        host = MacroHost(args)
        print(json.dumps(asyncio.run(host.run())))
        return 0 if host.phase != "fault" else 1
    except Exception as error:
        code = error.code if isinstance(error, ContractError) else "macro_host_start_failed"
        print(json.dumps(dict(state="fault", reason_code=code)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
