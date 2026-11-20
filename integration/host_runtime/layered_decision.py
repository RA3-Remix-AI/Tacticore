"""Layered decisions: commander, economy and tactical layers merged into one native plan.

LayerScheduler decides which layer asks the model (cadence + events), the
LayeredDecider validates each reply and lets the commander veto staff intents
by personality rules, and PlanComposer merges the latest valid intent per
native domain into one policy for the unchanged native dispatch path.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
import time

from .contracts import ContractError
from .habit_audit import HabitAudit
from .opening_book import HAMMER_OPENINGS, OpeningExecutor, choose_opening, eligible_openings
from .personality_rules import (
    PersonalityRules,
    fallback_directive,
    review_directive,
    review_economy,
    review_tactical,
)
from .world_state import EventDetector, build_world_state

# The strategy contract lives beside the other strategy modules (fixed repository path).
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / "strategy")]
from layered_contract import (  # noqa: E402
    DOMAIN_ORDER,
    DOMAIN_OWNER,
    LayerContractError,
    blocked_by,
    directive_actions,
    economy_actions,
    recorded_only,
    tactical_actions,
    validate_directive,
    validate_economy_intent,
    validate_tactical_intent,
)

LAYERS = ("commander", "economy", "tactical")
MODES = ("layered", "single")
ENVIRONMENT_VARIABLE = "TACTICORE_DECISION_MODE"
DEFAULT_MODE = "layered"
# Plans shorter than this are not worth dispatching; the native baseline continues.
MIN_PLAN_SECONDS = 5
MAX_PLAN_SECONDS = 60
EXPIRY_WARNING_S = 5
EVENT_MIN_GAP_S = 5
COMPOSE_MIN_GAP_S = 15
TRIGGERS = dict(
    commander=frozenset({"match_start", "opening_handover", "enemy_defeated", "base_under_attack", "expansion_lost"}),
    economy=frozenset({"ore_collector_lost", "tech_unlocked", "expansion_changed", "plan_expiring"}),
    tactical=frozenset(
        {"enemy_main_force_contact", "base_under_attack", "scouting_report", "ore_collector_lost", "plan_expiring"}
    ),
)
ROUTE_OBJECTIVES = dict(
    rush="pressure",
    steady_growth="expand_economy",
    tech_pressure="develop_technology",
    all_in="pressure",
    defend_counter="defend_base",
)
POSTURE_STANCES = dict(attack="pressure", all_in="pressure", harass="raid", scout="scout")


def decision_mode(value=None):
    """'layered' (default) or 'single' from the flag or TACTICORE_DECISION_MODE."""
    import os

    selected = value or os.environ.get(ENVIRONMENT_VARIABLE, "").strip() or DEFAULT_MODE
    if selected not in MODES:
        raise ContractError("decision_mode_unsupported")
    return selected


@dataclass
class LayerIntent:
    """One accepted layer intent and the native actions it asks for, per domain."""

    layer: str
    intent: dict
    actions: dict
    decided_at: float
    expires_at: float
    vetoes: list = field(default_factory=list)


@dataclass
class Composition:
    actions: list
    applied: list
    dropped: list
    valid_until: float | None
    layers: list

    def public(self):
        return dict(applied_intents=list(self.applied), dropped=[dict(d) for d in self.dropped])


class PlanComposer:
    """Merge the latest valid intent per domain into one native action list."""

    def compose(self, intents, directive, offered, now, *, independent=True) -> Composition:
        offered = set(offered)
        overrides = directive.get("overrides", []) if directive else []
        chosen, dropped, expiries, layers = {}, [], [], []
        opening = intents.get("opening")
        if opening is not None and opening.expires_at - now < MIN_PLAN_SECONDS:
            dropped.append(dict(intent="opening", reason="intent_expired"))
            opening = None
        for domain in DOMAIN_ORDER:
            owner = "opening" if opening is not None and domain in opening.actions else DOMAIN_OWNER[domain]
            source = intents.get(owner)
            if source is None:
                continue
            candidates = source.actions.get(domain)
            if candidates is None:
                continue
            if source.expires_at - now < MIN_PLAN_SECONDS:
                dropped.append(dict(intent=_first(candidates), reason="intent_expired"))
                continue
            for layer, other in intents.items():
                if layer != owner and domain in other.actions:
                    dropped.append(dict(intent=_first(other.actions[domain]), reason="domain_owned_by_" + owner))
            action = self._pick(candidates, offered, overrides, dropped)
            if action is not None:
                chosen[domain] = action
                expiries.append(source.expires_at)
                if owner not in layers:
                    layers.append(owner)
        if not independent and "expansion" in chosen and "military" in chosen:
            dropped.append(dict(intent=chosen.pop("expansion"), reason="single_work_slot_taken_by_military"))
        actions = [chosen[d] for d in DOMAIN_ORDER if d in chosen]
        valid_until = min(min(expiries), now + MAX_PLAN_SECONDS) if expiries else None
        return Composition(actions, list(actions), dropped, valid_until, layers)

    @staticmethod
    def _pick(candidates, offered, overrides, dropped):
        candidates = (candidates,) if isinstance(candidates, str) else tuple(candidates)
        for action in candidates:
            override = blocked_by(overrides, action)
            if override is not None:
                dropped.append(dict(intent=action, reason="directive_override_" + override))
                return None
            if action in offered:
                return action
        dropped.append(dict(intent=candidates[0], reason="action_unavailable"))
        return None

    @staticmethod
    def conflicts(actions, directive, *, commander_owns_budget=True):
        """Actions that the latest directive no longer allows (checked right before dispatch)."""
        found = []
        wanted = directive_actions(directive) if directive else {}
        for action in actions:
            override = blocked_by(directive.get("overrides", []) if directive else [], action)
            if override is not None:
                found.append(dict(intent=action, reason="directive_override_" + override))
            elif commander_owns_budget and action.startswith("budget") and wanted.get("budget") not in (None, action):
                found.append(dict(intent=action, reason="directive_budget_changed"))
            elif action.startswith("focusenemy") and wanted.get("enemy_focus") != action:
                found.append(dict(intent=action, reason="directive_primary_enemy_changed"))
        return found


def _first(candidates):
    return candidates if isinstance(candidates, str) else candidates[0]


class LayerScheduler:
    """Which layers should ask the model now: cadence, events, never a duplicate in-flight call."""

    def __init__(self, rules: PersonalityRules):
        self.intervals = dict(
            commander=rules.commander_interval_s,
            economy=rules.economy_interval_s,
            tactical=rules.tactical_interval_s,
        )

    def due(self, now, *, last_started, inflight, triggers, staff_ready, opening_active):
        result = []
        if opening_active:
            return result
        for layer in LAYERS:
            if layer in inflight:
                continue
            if layer != "commander" and not staff_ready:
                continue
            last = last_started.get(layer)
            reasons = sorted(triggers.get(layer, ()))
            if last is None:
                result.append((layer, reasons or ["match_start"]))
            elif now - last >= self.intervals[layer]:
                result.append((layer, reasons or ["cadence"]))
            elif reasons and now - last >= EVENT_MIN_GAP_S:
                result.append((layer, reasons))
        return result


class LayeredDecider:
    """Runs the opening, the three layers and the composer for one host run."""

    def __init__(
        self,
        *,
        backend,
        binding,
        commander,
        personality,
        scenario,
        event=None,
        log=None,
        max_input_bytes=16384,
        monotonic=time.monotonic,
    ):
        self.backend = backend
        self.binding = dict(binding)
        self.commander = dict(commander)
        self.personality = dict(personality)
        self.rules = PersonalityRules.from_personality(self.personality)
        self.scenario = dict(scenario or {})
        self.event = event or (lambda kind, **facts: None)
        self.log = log
        self.max_input_bytes = max_input_bytes
        self.monotonic = monotonic
        self.scheduler = LayerScheduler(self.rules)
        self.composer = PlanComposer()
        self.detector = EventDetector()
        self.habits = HabitAudit()
        self.enemies = list(self.scenario.get("enemy_player_ids") or [])
        self.directive = fallback_directive(self.rules, self.personality, self.enemies)
        self.directive_source = None
        self.directive_until = 0.0
        self.primary_since = 0.0
        self.intents = {}
        self.inflight = {}
        self.last_started = {}
        self.triggers = {layer: set() for layer in LAYERS}
        self.recent_events = deque(maxlen=8)
        self.world = None
        self.context = None
        self.opening_variant = choose_opening(self.personality, self.scenario)
        self.opening = OpeningExecutor(self.opening_variant, self.rules.harass_window_s)
        self.prematch_started = False
        self.dirty = False
        self.urgent = False
        self.unknown_delivery = False
        self.last_composed_at = None
        self.composed_until = None
        self.last_composition = None
        self.streak = None
        self.mobile_at_tactical = None
        self.staff_status = {}
        if self.log is not None:
            self._record_opening_variant()

    def _record_opening_variant(self):
        self.log.set_run_fact("opening_variant", self.opening_variant)
        self.log.set_run_fact("opening_variant_name", HAMMER_OPENINGS[self.opening_variant]["name"])

    # -- host loop -----------------------------------------------------------

    def tick(self, context, now, *, model_allowed=True):
        """One host-loop step: collect replies, detect events, run the opening, start due layers."""
        self._collect()
        if context is not None:
            self.context = context
            self.world = build_world_state(context)
            events = self.detector.detect(self.world)
            for row in events:
                self._route_event(row)
            self._run_opening(now, events)
        self._expiry_triggers(now)
        if not model_allowed or self.world is None:
            return
        if not self.prematch_started:
            self.prematch_started = True
            self._start("commander", ["pre_match"], now, prematch=True)
        due = self.scheduler.due(
            now,
            last_started=self.last_started,
            inflight=self.inflight,
            triggers=self.triggers,
            staff_ready=self.directive_source is not None,
            opening_active=not self.opening.done,
        )
        for layer, reasons in due:
            self._start(layer, reasons, now)

    def wants_composition(self, now):
        if self.unknown_delivery or self.world is None:
            return False
        renewal = (
            self.composed_until is not None
            and self.composed_until - now <= EXPIRY_WARNING_S
            and any(row.expires_at - now >= MIN_PLAN_SECONDS + EXPIRY_WARNING_S for row in self.intents.values())
        )
        if not (self.dirty or renewal):
            return False
        spaced = self.last_composed_at is None or now - self.last_composed_at >= COMPOSE_MIN_GAP_S
        return spaced or self.urgent

    def compose_policy(self, context):
        """Build the native policy JSON for the composer request context (called at send time)."""
        now = float(context["game_time_seconds"])
        world = build_world_state(context)
        independent = context.get("macro_intent_contract") == "native7_independent_development_v1"
        self._drop_expired(now)
        composition = self.composer.compose(
            self.intents, self.directive, world.allowed_actions, now, independent=independent
        )
        self.last_composition = composition
        self.dirty = False
        self.urgent = False
        self.last_composed_at = now
        if self.log is not None:
            self.log.composed(composition.public(), layers=composition.layers)
        self.event(
            "layered_composition",
            applied_intents=composition.applied,
            dropped=composition.dropped,
            layers=composition.layers,
        )
        return self._policy(context, composition, world, now)

    def revalidate(self, actions, now):
        """Conflicts between a composed plan and the latest directive, right before dispatch."""
        found = self.composer.conflicts(
            list(actions), self.directive, commander_owns_budget="budget" not in self._opening_domains()
        )
        if found:
            self.dirty = True
        return found

    def _opening_domains(self):
        opening = self.intents.get("opening")
        return set(opening.actions) if opening is not None else set()

    def dispatched(self, plan, now):
        self.composed_until = plan.expires_at_game_seconds
        self.habits.record(now, plan.macro_actions, region=plan.objective_region)

    def not_dispatched(self, reason_code):
        if reason_code == "macro_dispatch_outcome_unknown":
            # Delivery is unknown: never compose or re-send a replacement blindly.
            self.unknown_delivery = True
        else:
            self.dirty = True

    async def drain(self):
        for task in self.inflight.values():
            task.cancel()
        await asyncio.gather(*self.inflight.values(), return_exceptions=True)
        self.inflight.clear()
        if self.log is not None:
            self.log.flush_layers("host_stopped_before_composition")

    # -- events and opening ----------------------------------------------------

    def _route_event(self, row):
        self.recent_events.append(row)
        kind = row["kind"]
        self.event("layered_world_event", **{("event" if k == "kind" else k): v for k, v in row.items()})
        if kind == "base_under_attack":
            self.urgent = True
        names = {kind}
        if kind == "expansion_changed" and row.get("direction") == "lost":
            names.add("expansion_lost")
        if kind == "scouting_report" and row.get("found") == "enemy_base":
            seen = sum(1 for pid, _ in self.detector.seen_bases if pid == row.get("player"))
            if seen >= 2:
                names.add("enemy_expansion_seen")
        if names & self.rules.punish_events:
            names.add("punish_window")
        for layer in LAYERS:
            wanted = TRIGGERS[layer] | (set(self.directive.get("review_when", ())) if layer == "commander" else set())
            if layer == "tactical":
                wanted = wanted | self.rules.punish_events | {"punish_window"}
            for name in names & wanted:
                self.triggers[layer].add(name)

    def _run_opening(self, now, events):
        if self.opening.done:
            return
        step = self.opening.step(now, events)
        if step is None:
            if self.opening.done:
                self.intents.pop("opening", None)
                self.dirty = True
                self.triggers["commander"].add("opening_handover")
                self.event("layered_opening_handover", reason_code=self.opening.handover_reason, at=now)
            return
        if not step["changed"]:
            return
        timeline = HAMMER_OPENINGS[self.opening.variant_id]["timeline"]
        later = [row["at_s"] for row in timeline if row["at_s"] > now]
        expires = min([*later, self.opening.timeout_s])
        actions = {}
        for action in step["actions"]:
            actions[_domain(action)] = action
        self.intents["opening"] = LayerIntent("opening", dict(step), actions, now, max(expires, now + 1))
        self.dirty = True
        if self.log is not None:
            self.log.layer_decided(
                self._entry(
                    "opening",
                    now,
                    intents=step["actions"],
                    objective=HAMMER_OPENINGS[self.opening.variant_id]["name"],
                    reasoning=_opening_reasoning(self.opening.variant_id, step),
                    valid_for_s=expires - now,
                    recorded=step["intended"],
                    source="opening_step",
                )
            )

    def _expiry_triggers(self, now):
        for layer, row in self.intents.items():
            if layer in LAYERS and layer not in self.inflight and 0 <= row.expires_at - now <= EXPIRY_WARNING_S:
                self.triggers[layer].add("plan_expiring")
        expired = self.directive_source == "model" and now >= self.directive_until
        if expired and "commander" not in self.inflight:
            self.triggers["commander"].add("directive_expired")

    def _drop_expired(self, now):
        for layer in [name for name, row in self.intents.items() if row.expires_at <= now]:
            del self.intents[layer]

    # -- layer calls -------------------------------------------------------------

    def _start(self, layer, reasons, now, *, prematch=False):
        context = self._layer_context(layer, now, prematch=prematch)
        self.triggers[layer].clear()
        self.last_started[layer] = now
        task = asyncio.ensure_future(self._call(layer, context, now, reasons))
        self.inflight[layer] = task
        self.event("layered_layer_requested", layer=layer, reasons=list(reasons), prematch=prematch)

    async def _call(self, layer, context, now, reasons):
        started = self.monotonic()
        encoded = json.dumps(context, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        measure = getattr(self.backend, "input_size", None)
        size = measure(context) if callable(measure) else len(encoded)
        if size > self.max_input_bytes:
            return dict(context=context, now=now, reasons=reasons, error="layer_input_budget_exceeded", bytes=size)
        try:
            response = await self.backend(context)
        except ContractError as error:
            if error.code == "strategic_stop_already_committed":
                raise
            return dict(context=context, now=now, reasons=reasons, error=error.code, bytes=size)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            code = str(error) if type(error).__name__ in ("RuntimeAdapterError", "AdapterError") else None
            return dict(context=context, now=now, reasons=reasons, error=code or "model_call_failed", bytes=size)
        latency = int(round((self.monotonic() - started) * 1000))
        return dict(context=context, now=now, reasons=reasons, response=response, bytes=size, latency_ms=latency)

    def _collect(self):
        for layer, task in list(self.inflight.items()):
            if not task.done():
                continue
            del self.inflight[layer]
            if task.cancelled():
                continue
            result = task.result()  # strategic_stop_already_committed propagates to the host
            self._accept(layer, result)

    def _accept(self, layer, result):
        now = self.world.game_time if self.world is not None else result["now"]
        prematch = result["context"].get("phase") == "pre_match"
        model = dict(latency_ms=result.get("latency_ms"), input_bytes=result.get("bytes"), error=result.get("error"))
        try:
            if "error" in result:
                raise LayerContractError(result["error"])
            response = result["response"]
            if isinstance(response, (str, bytes)):
                response = json.loads(response)
            handler = getattr(self, "_accept_" + layer)
            entry = handler(response, now, prematch=prematch)
        except (LayerContractError, ValueError, TypeError, KeyError) as error:
            code = (str(error) if isinstance(error, LayerContractError) else "") or "layer_response_invalid"
            if layer == "commander" and self.directive_source is None:
                # Staff may proceed under the rule-based directive.
                self.directive_source = "fallback"
                self.directive_until = now + self.rules.commander_interval_s
            self.staff_status[layer] = dict(status="rejected", reason=code, at=round(now, 1))
            self.event("layered_layer_rejected", layer=layer, reason_code=code)
            if self.log is not None:
                entry = self._entry(layer, now, reasoning=None, source="layer_response", model=model)
                self.log.layer_rejected(entry, code)
            return
        entry["model"] = model
        self.dirty = True
        self.event("layered_layer_accepted", layer=layer, intents=entry["decision"]["intents"])
        if self.log is not None:
            self.log.layer_decided(entry)

    def _accept_commander(self, response, now, *, prematch):
        variants = eligible_openings(self.personality, self.scenario) if prematch else ()
        directive = validate_directive(response, enemies=self._enemy_options(), opening_variants=variants)
        defeated = self.world.defeated if self.world is not None else ()
        previous = self.directive if self.directive_source == "model" else None
        directive, vetoes = review_directive(
            directive, previous, self.rules, now=now, primary_since=self.primary_since, defeated=defeated
        )
        if previous is None or directive["primary_enemy"] != previous.get("primary_enemy"):
            self.primary_since = now
        if prematch and directive.get("opening_variant"):
            self.opening.switch(directive["opening_variant"])
            self.opening_variant = self.opening.variant_id
            if self.log is not None:
                self._record_opening_variant()
        self.directive = directive
        self.directive_source = "model"
        self.triggers["commander"].discard("directive_expired")
        self.directive_until = now + directive["valid_for_s"]
        self.intents["commander"] = LayerIntent(
            "commander", directive, directive_actions(directive), now, now + directive["valid_for_s"], vetoes
        )
        return self._entry(
            "commander",
            now,
            intents=list(directive_actions(directive).values()),
            objective=directive["route"],
            reasoning=directive["reasoning"],
            valid_for_s=directive["valid_for_s"],
            vetoes=vetoes,
            directive=directive,
        )

    def _accept_economy(self, response, now, *, prematch=False):
        intent = validate_economy_intent(response)
        intent, vetoes = review_economy(intent, self.rules, self.world)
        actions = economy_actions(intent)
        self.intents["economy"] = LayerIntent("economy", intent, actions, now, now + intent["valid_for_s"], vetoes)
        self.staff_status["economy"] = dict(status="accepted", intents=list(actions.values()), at=round(now, 1))
        return self._entry(
            "economy",
            now,
            intents=list(actions.values()),
            objective="expand_" + str(intent["expand"]),
            reasoning=intent["reasoning"],
            valid_for_s=intent["valid_for_s"],
            recorded=recorded_only("economy", intent),
            vetoes=vetoes,
        )

    def _accept_tactical(self, response, now, *, prematch=False):
        intent = validate_tactical_intent(response, enemies=self._enemy_options())
        world = self.world
        loss = 0.0
        if self.mobile_at_tactical and world is not None:
            loss = max(0.0, (self.mobile_at_tactical - world.own_mobile) / self.mobile_at_tactical)
        intent, vetoes = review_tactical(
            intent,
            self.rules,
            world,
            directive=self.directive,
            streak=self.streak,
            loss_fraction=loss,
            habits=self.habits.summary(self.rules.habit_share_threshold),
        )
        if self.streak is None or self.streak[0] != intent["posture"]:
            self.streak = (intent["posture"], now)
        self.mobile_at_tactical = world.own_mobile if world is not None else None
        valid = intent["valid_for_s"]
        if intent["posture"] == "harass":
            valid = min(valid, max(MIN_PLAN_SECONDS, self.streak[1] + self.rules.harass_window_s - now))
        actions = tactical_actions(intent)
        self.intents["tactical"] = LayerIntent("tactical", intent, actions, now, now + valid, vetoes)
        names = list(actions.get("military", ()))[:1]
        self.staff_status["tactical"] = dict(status="accepted", posture=intent["posture"], at=round(now, 1))
        if vetoes:
            self.staff_status["tactical"]["vetoed"] = [v["reason"] for v in vetoes]
        recorded = recorded_only("tactical", intent)
        if intent["posture"] == "patrol":
            recorded.append("posture")
        return self._entry(
            "tactical",
            now,
            intents=names,
            objective=intent["posture"],
            reasoning=intent["reasoning"],
            valid_for_s=valid,
            recorded=recorded,
            vetoes=vetoes,
        )

    # -- contexts, policy and records ---------------------------------------------

    def _enemy_options(self):
        remaining = self.world.remaining_enemies if self.world is not None and self.world.opponents else ()
        return list(remaining or self.enemies)

    def _layer_context(self, layer, now, *, prematch=False):
        world = self.world
        context = dict(
            decision_layer=layer,
            commander_id=self.binding["commander_id"],
            session_id=self.binding["session_id"],
            player_id=self.binding["player_id"],
            snapshot_id=world.snapshot_id,
            game_time_seconds=world.game_time,
            commander=dict(self.commander, personality=self.personality),
            directive=_directive_brief(self.directive),
            events=list(self.recent_events)[-6:],
        )
        if layer == "commander":
            context.update(
                phase="pre_match" if prematch else "match",
                situation=world.public(),
                staff=self.staff_status,
                habits=self.habits.summary(self.rules.habit_share_threshold),
                options=dict(enemies=self._enemy_options()),
            )
            if prematch:
                context["scenario"] = {
                    k: self.scenario.get(k) for k in ("map_id", "mode", "opponent_difficulty", "enemy_player_ids")
                }
                context["options"]["opening_variants"] = eligible_openings(self.personality, self.scenario)
                context["opening_names"] = {
                    k: HAMMER_OPENINGS[k]["name"] for k in context["options"]["opening_variants"]
                }
        elif layer == "economy":
            tactical = self.intents.get("tactical")
            context.update(
                economy=world.economy_slice(),
                composition_need=tactical.intent.get("composition_need", []) if tactical else [],
            )
        else:
            postures = sorted(
                {p for p, acts in _POSTURE_OPTIONS.items() if any(a in world.allowed_actions for a in acts)}
            )
            context.update(
                forces=world.tactical_slice(),
                options=dict(enemies=self._enemy_options(), postures=postures or ["scout"]),
                habits=self.habits.summary(self.rules.habit_share_threshold)["flags"],
                time_boxes=dict(harass_s=self.rules.harass_window_s, attack_s=self.rules.attack_window_s),
                punish_window="punish_window" in self.triggers["tactical"],
            )
        return context

    def _policy(self, context, composition, world, now):
        from macro_policy import restore_public_defaults

        public = restore_public_defaults(context)
        catalog = public.get("macro_policy_catalog", {})
        region = next(
            (
                catalog[a]["target_region"]
                for a in composition.actions
                if isinstance(catalog.get(a), dict) and "target_region" in catalog[a]
            ),
            None,
        )
        duration = MAX_PLAN_SECONDS if composition.valid_until is None else composition.valid_until - now
        duration = max(MIN_PLAN_SECONDS, min(MAX_PLAN_SECONDS, int(duration)))
        tactical = self.intents.get("tactical")
        posture = tactical.intent.get("posture") if tactical and "tactical" in composition.layers else None
        stance = POSTURE_STANCES.get(posture, "expand" if "expand" in composition.actions else "defend")
        if stance != "defend" and region is None and any(a.startswith("deploy") for a in composition.actions):
            stance = "defend"
        reasons = [row.intent.get("reasoning") for row in self.intents.values() if row.intent.get("reasoning")]
        policy = dict(
            schema_version=1,
            commander_id=context["commander_id"],
            session_id=context["session_id"],
            player_id=context["player_id"],
            snapshot_id=context["snapshot_id"],
            based_on_game_time_seconds=context["game_time_seconds"],
            valid_for_game_seconds=duration,
            stance=stance,
            production_focus="native_baseline",
            economy_policy="expand_if_defensible" if "expand" in composition.actions else "stabilize",
            tech_policy="advance_if_affordable" if "budgettech" in composition.actions else "hold_current_tier",
            budget=_budget(self.directive["resource_split"]),
            objective_region=region,
            reason_code="defensive_emergency" if (world.near_home_enemy or 0) >= 3 else "balanced_default",
            macro_actions=list(composition.actions),
            macro_production=None,
            tactical_tasks=[],
            runtime_task=None,
            reasoning=" / ".join(reasons)[:300] if reasons else None,
        )
        if isinstance(public.get("macro_strategy"), dict):
            policy["macro_strategy"] = _declaration(public["macro_strategy"], self.directive)
        return policy

    def _entry(
        self,
        layer,
        now,
        *,
        intents=(),
        objective=None,
        reasoning=None,
        valid_for_s=None,
        recorded=(),
        vetoes=(),
        directive=None,
        source="layer_response",
        model=None,
    ):
        from .decision_log import situation_from_context

        entry = dict(
            layer=layer,
            game_time_s=round(now, 1),
            situation=situation_from_context(self.context),
            decision=dict(
                intents=list(intents),
                objective=objective,
                reasoning=reasoning,
                valid_for_s=round(valid_for_s, 1) if valid_for_s is not None else None,
                objective_region=None,
                plan_id=None,
                source=source,
                recorded_only=list(recorded),
            ),
            vetoes=[dict(intent=v["intent"], reason="commander_veto_" + v["reason"]) for v in vetoes],
            model=model or dict(latency_ms=None, input_bytes=None, error=None),
        )
        if directive is not None:
            entry["directive"] = {
                k: directive[k] for k in ("route", "resource_split", "primary_enemy", "overrides", "valid_for_s")
            }
        return entry


_POSTURE_OPTIONS = dict(
    attack=("attackenemy", "deployattack"),
    all_in=("attackenemy", "deployattack"),
    harass=("raideconomy",),
    defend=("deploydefense", "reinforce"),
    regroup=("regroup",),
    withdraw=("withdraw",),
    scout=("scout",),
)


def _domain(action):
    if action.startswith("budget"):
        return "budget"
    if action.startswith("focusenemy"):
        return "enemy_focus"
    if action == "expand":
        return "expansion"
    if action.endswith("construction"):
        return "construction_gate"
    if action.endswith("production"):
        return "production_gate"
    return "military"


def _directive_brief(directive):
    return {k: directive.get(k) for k in ("route", "resource_split", "primary_enemy", "overrides")}


def _budget(split):
    """Policy budget: shares summing to 1 with reserve inside 0.05..0.6."""
    reserve = min(0.6, max(0.05, split.get("reserve", 0.1)))
    rest = {k: max(0.0, split.get(k, 0.0)) for k in ("economy", "army", "tech")}
    total = sum(rest.values()) or 1.0
    budget = {k: round(v / total * (1 - reserve), 4) for k, v in rest.items()}
    budget["reserve"] = round(1 - sum(budget.values()), 4)
    return budget


def _declaration(memory, directive):
    """Strategy declaration for the existing strategy memory; keeps the id while the route holds."""
    objective = ROUTE_OBJECTIVES[directive["route"]]
    current = memory.get("current_strategy") if isinstance(memory.get("current_strategy"), dict) else None
    facts = memory.get("fact_catalog") if isinstance(memory.get("fact_catalog"), dict) else {}
    if "own.credits" in facts:
        ref = "own.credits"
    else:
        known = [key for key in sorted(facts) if facts[key] is not None]
        ref = known[0] if known else next(iter(sorted(facts)), "own.credits")
    keep = current is not None and current.get("objective") == objective and current.get("strategy_id")
    return dict(
        strategy_id=current["strategy_id"] if keep else None,
        objective=objective,
        phase="execute",
        public_fact_refs=[ref],
        expected_observation="no_change",
        continue_conditions=["capability_available"],
        replan_conditions=["facts_changed"],
        resource_priorities=_budget(directive["resource_split"]),
    )


def _opening_reasoning(variant_id, step):
    title = HAMMER_OPENINGS[variant_id]["name"]
    text = "开局方案「" + title + "」第" + str(step["step"] + 1) + "步。"
    if step.get("note"):
        text += "骚扰到此为止，转为侦察（" + step["note"].split(":", 1)[1] + "）。"
    return text


class ComposerBackend:
    """Stands where the model backend stood: returns the composed policy for the prepared context."""

    def __init__(self, decider, *, max_input_bytes):
        self.decider = decider
        self.max_input_bytes = max_input_bytes

    def input_size(self, context):
        return len(json.dumps(context, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    async def __call__(self, context):
        return self.decider.compose_policy(context)
