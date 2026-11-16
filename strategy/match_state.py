"""Bounded public combatant relationships and announced eliminations."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class MatchState:
    observed_frame: int
    opponent_player_ids: tuple[int, ...]
    defeated_opponent_ids: tuple[int, ...]
    opponents_allied: bool

    @classmethod
    def from_dict(cls, value, player_id, game_seconds):
        fields = {'schema_version', 'source', 'observed_frame', 'opponent_player_ids',
                  'defeated_opponent_ids', 'opponents_allied'}
        if (type(value) is not dict or set(value) != fields
                or type(value['schema_version']) is not int or value['schema_version'] != 1
                or value['source'] != 'native_public_match'):
            raise ValueError('public_match_fields')
        frame = value['observed_frame']
        if (type(frame) is not int or frame <= 0 or not math.isfinite(game_seconds)
                or not -1e-6 <= game_seconds * 15 - frame <= 15):
            raise ValueError('public_match_time')
        opponents = value['opponent_player_ids']
        defeated = value['defeated_opponent_ids']
        if (type(opponents) is not list or not 1 <= len(opponents) <= 2
                or any(type(index) is not int or not 0 <= index < 16 or index == player_id for index in opponents)
                or len(set(opponents)) != len(opponents)
                or type(defeated) is not list or len(defeated) > len(opponents)
                or any(type(index) is not int or index not in opponents for index in defeated)
                or len(set(defeated)) != len(defeated)
                or type(value['opponents_allied']) is not bool):
            raise ValueError('public_match_participants')
        return cls(frame, tuple(opponents), tuple(defeated), value['opponents_allied'])

    def public(self):
        return dict(schema_version=1, source='native_public_match', observed_frame=self.observed_frame,
                    opponent_player_ids=list(self.opponent_player_ids),
                    defeated_opponent_ids=list(self.defeated_opponent_ids),
                    opponents_allied=self.opponents_allied)
