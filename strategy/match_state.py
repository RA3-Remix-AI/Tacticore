"""Bounded public combatant relationships and announced eliminations."""
from dataclasses import dataclass
import math

# RA3 skirmish has at most six combatants; leave room for eight-start maps.
MAX_OTHER_PLAYERS = 7


def _player_list(value, player_id):
    return (type(value) is list and len(value) == len(set(value))
            and all(type(index) is int and 0 <= index < 16 and index != player_id for index in value))


@dataclass(frozen=True)
class MatchState:
    observed_frame: int
    opponent_player_ids: tuple[int, ...]
    defeated_opponent_ids: tuple[int, ...]
    opponents_allied: bool
    ally_player_ids: tuple[int, ...] = ()
    human_player_ids: tuple[int, ...] = ()

    @classmethod
    def from_dict(cls, value, player_id, game_seconds):
        fields = {'schema_version', 'source', 'observed_frame', 'opponent_player_ids',
                  'defeated_opponent_ids', 'opponents_allied'}
        # Allies and human combatants are optional for older snapshots.
        optional = {'ally_player_ids', 'human_player_ids'}
        if (type(value) is not dict or not fields <= set(value) or set(value) - fields - optional
                or type(value['schema_version']) is not int or value['schema_version'] != 1
                or value['source'] != 'native_public_match'):
            raise ValueError('public_match_fields')
        frame = value['observed_frame']
        if (type(frame) is not int or frame <= 0 or not math.isfinite(game_seconds)
                or not -1e-6 <= game_seconds * 15 - frame <= 15):
            raise ValueError('public_match_time')
        opponents = value['opponent_player_ids']
        defeated = value['defeated_opponent_ids']
        if (type(opponents) is not list or not 1 <= len(opponents) <= MAX_OTHER_PLAYERS
                or any(type(index) is not int or not 0 <= index < 16 or index == player_id for index in opponents)
                or len(set(opponents)) != len(opponents)
                or type(defeated) is not list or len(defeated) > len(opponents)
                or any(type(index) is not int or index not in opponents for index in defeated)
                or len(set(defeated)) != len(defeated)
                or type(value['opponents_allied']) is not bool):
            raise ValueError('public_match_participants')
        allies = value.get('ally_player_ids', [])
        humans = value.get('human_player_ids', [])
        if not _player_list(allies, player_id) or set(allies) & set(opponents):
            raise ValueError('public_match_participants')
        if not _player_list(humans, player_id) or not set(humans) <= set(allies) | set(opponents):
            raise ValueError('public_match_participants')
        if len(opponents) + len(allies) > MAX_OTHER_PLAYERS:
            raise ValueError('public_match_participants')
        return cls(frame, tuple(opponents), tuple(defeated), value['opponents_allied'],
                   tuple(allies), tuple(humans))

    def public(self):
        result = dict(schema_version=1, source='native_public_match', observed_frame=self.observed_frame,
                      opponent_player_ids=list(self.opponent_player_ids),
                      defeated_opponent_ids=list(self.defeated_opponent_ids),
                      opponents_allied=self.opponents_allied)
        if self.ally_player_ids or self.human_player_ids:
            result.update(ally_player_ids=list(self.ally_player_ids),
                          human_player_ids=list(self.human_player_ids))
        return result
