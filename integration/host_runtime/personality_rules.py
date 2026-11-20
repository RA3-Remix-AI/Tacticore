"""Explicit behaviour rules derived from the nine personality parameters.

Each parameter changes numbers the host enforces (cadences, thresholds, time
boxes), and the commander uses them to veto or modify staff intents. Every
veto is returned with a reason code so the decision log can show it.
"""

from __future__ import annotations

from dataclasses import dataclass

ATTACK_POSTURES = frozenset({"attack", "all_in"})
PRESSURE_POSTURES = ATTACK_POSTURES | {"harass"}


@dataclass(frozen=True)
class PersonalityRules:
    commander_interval_s: float
    economy_interval_s: float
    tactical_interval_s: float
    attack_force_ratio: float
    all_in_force_ratio: float
    retreat_loss_fraction: float
    harass_window_s: float
    attack_window_s: float
    punish_window_s: float
    punish_events: frozenset
    primary_enemy_hold_s: float
    habit_share_threshold: float
    habit_enforced: bool
    bait_max_info_age_s: float
    expand_under_threat: bool
    greedy_opening: bool

    @classmethod
    def from_personality(cls, p: dict) -> "PersonalityRules":
        punish_events = set()
        if p["punish"] >= 3:
            punish_events.add("enemy_main_force_contact")
        if p["punish"] >= 4:
            punish_events.add("enemy_expansion_seen")
        return cls(
            # adaptability: re-read the situation more often
            commander_interval_s=120 - 10 * (p["adaptability"] - 1),
            # risk: a bolder economy re-plans sooner
            economy_interval_s=60 - 5 * (p["risk"] - 1),
            # aggression: faster tactical cycle, lower force ratio to attack
            tactical_interval_s=30 - 5 * (p["aggression"] - 1),
            attack_force_ratio={1: 2.0, 2: 1.6, 3: 1.3, 4: 1.1, 5: 0.9}[p["aggression"]],
            # risk: all-in threshold and greedy openings
            all_in_force_ratio=2.0 - 0.25 * (p["risk"] - 1),
            greedy_opening=p["risk"] >= 3,
            expand_under_threat=p["risk"] >= 4,
            # preserve: retreat earlier after losses
            retreat_loss_fraction=round(0.8 - 0.15 * (p["preserve"] - 1), 2),
            # persistence: longer harassment time box
            harass_window_s=30 + 15 * p["persistence"],
            attack_window_s=40 + 20 * p["aggression"],
            # punish: which openings trigger an immediate tactical decision
            punish_window_s=10 * p["punish"],
            punish_events=frozenset(punish_events),
            # grudge: how long the primary enemy is kept
            primary_enemy_hold_s=60 * p["grudge"],
            # deception lowers the share at which a habit counts as readable;
            # adaptability decides whether the commander enforces a change.
            habit_share_threshold=round(0.9 - 0.1 * p["deception"], 2),
            habit_enforced=p["adaptability"] >= 4,
            # bait awareness: how fresh enemy information must be before an attack
            bait_max_info_age_s=45 - 6 * p["bait_awareness"],
        )

    def public(self):
        value = dict(self.__dict__)
        value["punish_events"] = sorted(self.punish_events)
        return value


def fallback_directive(rules: PersonalityRules, personality: dict, enemies) -> dict:
    """Rule-based directive used until the commander's first valid reply."""
    if personality["aggression"] >= 4 and personality["risk"] >= 4:
        route, split = "rush", dict(economy=0.25, army=0.6, tech=0.05, reserve=0.1)
    elif personality["aggression"] >= 3:
        route, split = "tech_pressure", dict(economy=0.35, army=0.35, tech=0.2, reserve=0.1)
    else:
        route, split = "defend_counter", dict(economy=0.45, army=0.3, tech=0.1, reserve=0.15)
    return dict(
        route=route,
        resource_split=split,
        primary_enemy=enemies[0] if enemies else None,
        overrides=[],
        reasoning=None,
        valid_for_s=rules.commander_interval_s,
        review_when=["base_under_attack", "enemy_defeated"],
        opening_variant=None,
    )


def review_directive(new, previous, rules, *, now, primary_since, defeated):
    """Grudge: keep the primary enemy until its hold time passes or it is defeated."""
    vetoes = []
    old = (previous or {}).get("primary_enemy")
    held = old is not None and old not in defeated and now - primary_since < rules.primary_enemy_hold_s
    if held and new.get("primary_enemy") != old:
        vetoes.append(dict(intent="focusenemy" + str(new.get("primary_enemy")), reason="grudge_hold_primary_enemy"))
        new = dict(new, primary_enemy=old)
    return new, vetoes


def review_economy(intent, rules, world):
    """Risk: a cautious commander does not expand while enemies are at home or at the mines."""
    threatened = (world.near_home_enemy or 0) > 0 or world.mining_threat > 0
    if intent.get("expand") == "now" and threatened and not rules.expand_under_threat:
        return dict(intent, expand="hold"), [dict(intent="expand", reason="expand_under_threat_refused")]
    return intent, []


def _modify(intent, posture, reason, vetoes):
    vetoes.append(dict(intent=intent["posture"], reason=reason, replacement=posture))
    return dict(intent, posture=posture)


def review_tactical(intent, rules, world, *, directive, streak, loss_fraction, habits):
    """Commander review of one tactical intent; returns (intent, vetoes).

    streak: (posture, since_game_seconds) of the posture currently being executed.
    loss_fraction: share of own mobile presence lost since the previous tactical decision.
    habits: HabitAudit summary (flags) for this run.
    """
    vetoes = []
    posture = intent["posture"]
    if posture == "all_in" and directive.get("route") != "all_in":
        intent = _modify(intent, "attack", "all_in_requires_commander_route", vetoes)
        posture = "attack"
    if posture in PRESSURE_POSTURES and loss_fraction >= rules.retreat_loss_fraction:
        return _modify(intent, "withdraw", "losses_exceed_preserve_limit", vetoes), vetoes
    if posture in ATTACK_POSTURES:
        age = world.enemy_newest_age_s
        if age is None or age > rules.bait_max_info_age_s:
            return _modify(intent, "scout", "bait_check_scout_first", vetoes), vetoes
        ratio = world.force_ratio()
        needed = rules.all_in_force_ratio if posture == "all_in" else rules.attack_force_ratio
        if ratio is not None and ratio < needed:
            return _modify(intent, "regroup", "force_ratio_below_threshold", vetoes), vetoes
    if streak is not None and streak[0] == posture:
        elapsed = world.game_time - streak[1]
        if posture in ATTACK_POSTURES and elapsed >= rules.attack_window_s:
            return _modify(intent, "regroup", "attack_time_box", vetoes), vetoes
        if posture == "harass" and elapsed >= rules.harass_window_s:
            return _modify(intent, "scout", "harass_time_box", vetoes), vetoes
    readable = {flag["pattern"] for flag in habits.get("flags", [])}
    if rules.habit_enforced and posture in ("attack", "harass") and "military_action" in readable:
        swapped = "harass" if posture == "attack" else "attack"
        if habits.get("top", {}).get("military_action") == ("raideconomy" if posture == "harass" else "attackenemy"):
            return _modify(intent, swapped, "habit_over_concentration", vetoes), vetoes
    return intent, vetoes
