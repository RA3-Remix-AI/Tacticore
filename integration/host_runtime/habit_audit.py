"""Self-habit audit: what the enemy can learn from our own applied decisions this run.

Fed with each dispatched plan (actions, attack region, focus target, game time).
summary() reports the dominant value per pattern and flags patterns whose share
reaches the commander's threshold, so the commander layer can change them.
"""

from __future__ import annotations

from collections import Counter, deque

MILITARY = ("attackenemy", "deployattack", "raideconomy", "scout", "deploydefense", "regroup", "withdraw", "reinforce")
ATTACKS = ("attackenemy", "deployattack")
MIN_SAMPLES = 3


class HabitAudit:
    def __init__(self, window=10):
        self.records = deque(maxlen=window)

    def record(self, at, actions, *, region=None):
        actions = list(actions)
        military = next((a for a in actions if a in MILITARY), None)
        focus = next((a for a in actions if a.startswith("focusenemy")), None)
        self.records.append(dict(at=at, military=military, focus=focus, region=region))

    def _attack_starts(self):
        starts, previous = [], None
        for row in self.records:
            attacking = row["military"] in ATTACKS
            if attacking and previous not in ATTACKS:
                starts.append(row["at"])
            previous = row["military"]
        return starts

    def summary(self, threshold):
        patterns = {
            "military_action": [r["military"] for r in self.records if r["military"]],
            "attack_region": [r["region"] for r in self.records if r["military"] in ATTACKS and r["region"]],
            "harass_target": [r["focus"] for r in self.records if r["military"] == "raideconomy" and r["focus"]],
            "focus_target": [r["focus"] for r in self.records if r["focus"]],
        }
        top, flags = {}, []
        for name, values in patterns.items():
            if not values:
                continue
            value, count = Counter(values).most_common(1)[0]
            share = round(count / len(values), 2)
            top[name] = value
            if len(values) >= MIN_SAMPLES and share >= threshold:
                flags.append(dict(pattern=name, value=value, share=share, samples=len(values)))
        starts = self._attack_starts()
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        if len(gaps) >= 2:
            mean = sum(gaps) / len(gaps)
            if mean > 0 and all(abs(gap - mean) <= 0.15 * mean for gap in gaps):
                flags.append(dict(pattern="attack_timing", value=round(mean), share=1.0, samples=len(starts)))
        return dict(samples=len(self.records), top=top, flags=flags, attack_starts=[round(s) for s in starts[-4:]])
