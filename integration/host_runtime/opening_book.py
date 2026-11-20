"""Hammer opening book (current native intents only) and its rule-based executor.

A variant is data: a timeline of native intents plus unit-specific steps that
are recorded as intended but cannot be executed until direct unit control
exists. The executor never calls a model; it hands over to the decision layers
on the first scouting report or after the opening timeout.
"""

from __future__ import annotations

OPENING_TIMEOUT_S = 180
# Events that end any harassment step at once (Hammer: stop when it stops paying).
HARASS_STOP_EVENTS = frozenset({"base_under_attack", "ore_collector_lost", "enemy_main_force_contact"})

HAMMER_OPENINGS = {
    "hammer_scout_raid": dict(
        name="战熊侦察 + 恐怖机器人骚扰",
        conditions=dict(max_enemies=1),
        timeline=(
            dict(at_s=0, actions=("budgeteconomy",), intended=("war_bear_scout_enemy_base",)),
            dict(at_s=30, actions=("budgeteconomy", "scout")),
            dict(
                at_s=70,
                actions=("budgeteconomy", "raideconomy"),
                harass=True,
                intended=("terror_drone_miner_harass", "protocol_pick:terror_drone_drop"),
            ),
            dict(at_s=130, actions=("budgeteconomy", "advanceconstruction"), intended=("protocol_pick:cash_bounty",)),
            dict(at_s=160, actions=("budgettech", "advanceconstruction"), intended=("climb_to_t3_apocalypse",)),
        ),
    ),
    "hammer_fast_expand": dict(
        name="早扩张贪矿车 + 延后骚扰",
        conditions=dict(max_enemies=1, min_risk=3),
        timeline=(
            dict(at_s=0, actions=("budgeteconomy",), intended=("war_bear_scout_enemy_base",)),
            dict(at_s=30, actions=("budgeteconomy", "expand", "scout")),
            dict(
                at_s=100,
                actions=("budgeteconomy", "expand", "raideconomy"),
                harass=True,
                intended=("terror_drone_miner_harass",),
            ),
            dict(at_s=150, actions=("budgettech", "advanceconstruction"), intended=("climb_to_t3_apocalypse",)),
        ),
    ),
    "hammer_safe_tech": dict(
        name="守家侦察 + 稳攀科技",
        conditions=dict(),
        timeline=(
            dict(at_s=0, actions=("budgeteconomy",), intended=("war_bear_scout_enemy_base",)),
            dict(at_s=30, actions=("budgeteconomy", "scout")),
            dict(at_s=60, actions=("budgeteconomy", "deploydefense"), intended=("anti_air_escort_at_home",)),
            dict(at_s=120, actions=("budgettech", "advanceconstruction", "deploydefense")),
        ),
    ),
}


def eligible_openings(personality, scenario):
    """Variant ids whose conditions hold for this match and personality."""
    enemies = len(scenario.get("enemy_player_ids") or ()) or 1
    result = []
    for ident, variant in HAMMER_OPENINGS.items():
        rule = variant["conditions"]
        if enemies > rule.get("max_enemies", enemies):
            continue
        if personality["risk"] < rule.get("min_risk", 1):
            continue
        result.append(ident)
    return result


def choose_opening(personality, scenario):
    """Rule-based pre-match choice; the commander's pre-match call may pick another eligible id."""
    eligible = eligible_openings(personality, scenario)
    difficulty = str(scenario.get("opponent_difficulty") or "")
    if len(scenario.get("enemy_player_ids") or ()) >= 2 or "brutal" in difficulty:
        return "hammer_safe_tech"
    if personality["risk"] >= 4 and "hammer_fast_expand" in eligible:
        return "hammer_fast_expand"
    return "hammer_scout_raid" if "hammer_scout_raid" in eligible else eligible[0]


class OpeningExecutor:
    """Plays one variant's timeline; harassment has a time box and stop events."""

    def __init__(self, variant_id, harass_window_s, *, timeout_s=OPENING_TIMEOUT_S):
        self.variant_id = variant_id
        self.variant = HAMMER_OPENINGS[variant_id]
        self.harass_window_s = harass_window_s
        self.timeout_s = timeout_s
        self.step_index = None
        self.harass_started = None
        self.harass_stopped = None
        self.done = False
        self.handover_reason = None
        self.last_note = None

    def switch(self, variant_id):
        """The commander's pre-match reply chose another variant; continue on its timeline."""
        if variant_id in HAMMER_OPENINGS and variant_id != self.variant_id and not self.done:
            self.variant_id = variant_id
            self.variant = HAMMER_OPENINGS[variant_id]
            self.step_index = None
            self.harass_started = self.harass_stopped = None

    def _current(self, now):
        index = None
        for position, step in enumerate(self.variant["timeline"]):
            if step["at_s"] <= now:
                index = position
        return index

    def step(self, now, events=()):
        """Return the opening intent for this moment, or None once handed over.

        The result is {step, actions, intended, changed, note}; changed is True when
        the actions differ from the previous call (a new composition is needed).
        """
        if self.done:
            return None
        kinds = {event["kind"] for event in events}
        if "scouting_report" in kinds or now >= self.timeout_s:
            self.done = True
            self.handover_reason = "scouting_report" if "scouting_report" in kinds else "opening_timeout"
            return None
        index = self._current(now)
        if index is None:
            return None
        step = self.variant["timeline"][index]
        actions = list(step["actions"])
        note = None
        if step.get("harass"):
            if self.harass_started is None or self.step_index != index:
                self.harass_started = step["at_s"]
            stop = None
            if self.harass_stopped is not None:
                stop = self.harass_stopped
            elif kinds & HARASS_STOP_EVENTS:
                stop = sorted(kinds & HARASS_STOP_EVENTS)[0]
            elif now - self.harass_started >= self.harass_window_s:
                stop = "harass_time_box"
            if stop is not None:
                self.harass_stopped = stop
                actions = ["scout" if action == "raideconomy" else action for action in actions]
                note = "harass_stopped:" + stop
        changed = index != self.step_index or note != self.last_note
        self.step_index = index
        self.last_note = note
        return dict(step=index, actions=actions, intended=list(step.get("intended", ())), changed=changed, note=note)
