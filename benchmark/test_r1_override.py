import unittest

import r1_override as r1


def move_trace(points, step=0.25):
    return [dict(t=round(i * step, 3), x=x, y=y, hp=100) for i, (x, y) in enumerate(points)]


class ClassifyMoveTest(unittest.TestCase):
    def test_arrives_without_override(self):
        samples = move_trace([(float(x), 0.0) for x in range(0, 420, 20)])
        result = r1.classify_move(samples, (400.0, 0.0))
        self.assertTrue(result["started"])
        self.assertIsNotNone(result["arrived_s"])
        self.assertIsNone(result["overridden_s"])

    def test_turns_back_before_arrival(self):
        out = [(float(x), 0.0) for x in range(0, 200, 20)]
        back = [(float(x), 0.0) for x in range(180, -200, -20)]
        result = r1.classify_move(move_trace(out + back), (400.0, 0.0))
        self.assertTrue(result["started"])
        self.assertIsNone(result["arrived_s"])
        self.assertIsNotNone(result["overridden_s"])
        self.assertGreater(result["overridden_s"], 2.0)

    def test_never_moves(self):
        result = r1.classify_move(move_trace([(0.0, 0.0)] * 40), (400.0, 0.0))
        self.assertFalse(result["started"])
        self.assertIsNone(result["overridden_s"])

    def test_leaving_after_arrival_is_not_an_override(self):
        there = [(float(x), 0.0) for x in range(0, 420, 40)]
        away = [(400.0, float(y)) for y in range(0, 400, 40)]
        result = r1.classify_move(move_trace(there + away), (400.0, 0.0))
        self.assertIsNone(result["overridden_s"])
        self.assertIsNotNone(result["left_goal_after_arrival_s"])


class ClassifyAttackTest(unittest.TestCase):
    def trace(self, unit_xs, target_hps):
        return [
            dict(t=i * 0.25, x=x, y=0.0, hp=100, target_x=500.0, target_y=0.0, target_hp=hp)
            for i, (x, hp) in enumerate(zip(unit_xs, target_hps))
        ]

    def test_kills_target(self):
        xs = [float(x) for x in range(0, 300, 20)] + [300.0] * 10
        hps = [100] * 15 + [90, 80, 60, 40, 20, 0, 0, 0, 0, 0]
        result = r1.classify_attack(self.trace(xs, hps))
        self.assertTrue(result["started"])
        self.assertIsNotNone(result["target_destroyed_s"])
        self.assertIsNone(result["overridden_s"])

    def test_walks_away_without_firing(self):
        xs = [float(x) for x in range(0, 200, 20)] + [float(x) for x in range(180, -300, -20)]
        result = r1.classify_attack(self.trace(xs, [100] * len(xs)))
        self.assertTrue(result["started"])
        self.assertIsNotNone(result["overridden_s"])


class SummaryTest(unittest.TestCase):
    def test_table_counts_only_started_trials(self):
        records = [
            dict(situation="idle", act="move", started=True, overridden_s=None, arrived_s=5.0),
            dict(situation="idle", act="move", started=True, overridden_s=3.0, arrived_s=None),
            dict(situation="idle", act="move", started=False, overridden_s=None, arrived_s=None),
        ]
        table = r1.summarize(records)
        self.assertIn("| idle | move | 3 | 2 | 1 | 50% | 3.0 | 1 |", table)


if __name__ == "__main__":
    unittest.main()
