"""Public 1v2 state survives the ordinary snapshot and agent context path."""
import copy
import unittest

from battle_agent import BattleAgent
from engine import ContractError, Snapshot, StrategyEngine
from fixtures import binding, snapshot
from macro_strategy import MacroStrategyMemory


class MatchContextTests(unittest.TestCase):
    def setUp(self):
        self.match = dict(schema_version=1, source='native_public_match', observed_frame=1500,
                          opponent_player_ids=[4, 5], defeated_opponent_ids=[], opponents_allied=True)

    def observed(self, match, ident=1):
        return Snapshot.from_dict(snapshot(ident=ident, at=100 + ident - 1, match_state=match,
            macro_control=dict(mode='macro_native', available_actions=['budgetarmy', 'budgeteconomy'])))

    def test_agent_exposes_two_allied_opponents_and_later_elimination(self):
        agent = BattleAgent(StrategyEngine(binding()))
        memory = MacroStrategyMemory(session_id=binding().session_id, commander_id=binding().commander_id,
                                     player_id=3, profile_revision=1, effective_hash='a' * 64)
        for ident, (defeated, remaining) in enumerate([([], 2), ([4], 1)], 1):
            match = dict(self.match, observed_frame=1500 + 15 * (ident - 1), defeated_opponent_ids=defeated)
            observed = self.observed(match, ident)
            self.assertEqual(Snapshot.from_dict(observed.to_dict()).match_state.public(), match)
            agent.observe(observed.to_dict())
            context = agent.context(observed.model_context(binding()))
            self.assertEqual(context['working_memory']['match_state'], match)
            facts = memory.context(context)['fact_catalog']
            self.assertEqual(facts['match.opponents.total'], 2)
            self.assertEqual(facts['match.opponents.remaining'], remaining)
            self.assertIs(facts['match.opponents.allied'], True)

    def test_future_or_old_match_observation_is_rejected(self):
        for frame in (1501, 1484):
            with self.subTest(frame=frame), self.assertRaises(ContractError):
                self.observed(dict(self.match, observed_frame=frame))

    def test_unadmitted_or_duplicate_elimination_is_rejected(self):
        for defeated in ([6], [4, 4], [True]):
            with self.subTest(defeated=defeated), self.assertRaises(ContractError):
                self.observed(dict(self.match, defeated_opponent_ids=defeated))

    def test_human_teammate_and_more_opponents_are_public_facts(self):
        match = dict(self.match, opponent_player_ids=[4, 5, 6], ally_player_ids=[2], human_player_ids=[2])
        observed = self.observed(match)
        self.assertEqual(observed.match_state.public(), match)
        memory = MacroStrategyMemory(session_id=binding().session_id, commander_id=binding().commander_id,
                                     player_id=3, profile_revision=1, effective_hash='a' * 64)
        agent = BattleAgent(StrategyEngine(binding()))
        agent.observe(observed.to_dict())
        facts = memory.context(agent.context(observed.model_context(binding())))['fact_catalog']
        self.assertEqual(facts['match.opponents.total'], 3)
        self.assertEqual(facts['match.allies.total'], 1)
        self.assertEqual(facts['match.allies.human'], 1)

    def test_ally_cannot_also_be_an_opponent_or_the_model(self):
        for change in (dict(ally_player_ids=[4]), dict(ally_player_ids=[3]),
                       dict(ally_player_ids=[2], human_player_ids=[1])):
            with self.subTest(change=change), self.assertRaises(ContractError):
                self.observed(dict(self.match, **change))

    def test_hidden_enemy_details_cannot_be_added_to_public_match(self):
        bad = copy.deepcopy(self.match)
        bad['enemy_credits'] = 100000
        with self.assertRaises(ContractError):
            self.observed(bad)


if __name__ == '__main__':
    unittest.main()
