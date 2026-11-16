"""Fixed Native6 trial scenarios, using public native start waypoint names.

These entries authorize bounded trials. They do not certify a map's natural
game, lawful-view or product acceptance. No RPC value can add a scenario.
"""
from dataclasses import dataclass

from .contracts import ContractError


@dataclass(frozen=True)
class Native6Scenario:
    map_id: str
    display_map: str
    decoded_map_sha256: str
    own_region: str
    opposing_start_region: str
    opponent_player_ids: tuple[int, ...] = (4,)

    @property
    def participant_count(self):
        return 1 + len(self.opponent_player_ids)

    @property
    def regional_action_regions(self):
        return (('deployattack', self.opposing_start_region),
                ('deploydefense', self.own_region), ('regroup', self.own_region),
                ('reinforce', self.own_region), ('withdraw', self.own_region))


TEMPLE_PRIME = Native6Scenario(
    'map_mp_2_black1b', 'TemplePrime',
    'ec4775f8c2d50ad15576544f00071ed1e409ee70f5a9dc7610282584e6798d66',
    'region_8_3', 'region_1_3')
INFINITY_ISLE = Native6Scenario(
    'map_mp_2_rao1', 'InfinityIsle',
    '220d7006b8659d0e1baf78a9b794b0d53be2461bd8045d2478e0c72b96c7f7f7',
    'region_7_4', 'region_2_3')

# Display localization and live adoption are checked in the new four-player
# trial. These are public starting waypoints from the exact decoded map.
FOUR_PLAYER_1V2 = Native6Scenario(
    'map_mp_4_stewart_1', 'ColdShowdown (1v2)',
    '30b0cea6f5345b6b7caf2fc1bfdbe7ed305be9c214af7f071189f6f7685d8eb9',
    'region_7_1', 'region_1_7', (4, 5))

NATIVE6_SCENARIOS = (TEMPLE_PRIME, INFINITY_ISLE, FOUR_PLAYER_1V2)


def scenario_for_map(map_id):
    for scenario in NATIVE6_SCENARIOS:
        if type(map_id) is str and map_id == scenario.map_id:
            return scenario
    raise ContractError('session_scope_unsupported')


def scenario_for_session(scenario):
    selected = scenario_for_map(scenario.get('map_id'))
    # Original TemplePrime descriptors predate the explicit origin/faction
    # fields. New scenarios require both fields in their observed descriptor.
    legacy = selected == TEMPLE_PRIME
    if (scenario.get('origin_region', selected.own_region if legacy else None) != selected.own_region
            or scenario.get('faction', 'Soviet' if legacy else None) != 'Soviet'):
        raise ContractError('session_scope_unsupported')
    if selected.participant_count == 3:
        opponents = scenario.get('opponent_player_indices')
        if (type(opponents) is not list or opponents != [4, 5]
                or any(type(index) is not int for index in opponents)
                or scenario.get('opponents_allied') is not True
                or type(scenario.get('participant_count')) is not int
                or scenario['participant_count'] != 3):
            raise ContractError('session_scope_unsupported')
    else:
        opponents = scenario.get('opponent_player_indices')
        if (opponents is not None and (type(opponents) is not list or opponents != [4]
                                      or any(type(index) is not int for index in opponents))
                or type(scenario.get('participant_count', 2)) is not int
                or scenario.get('participant_count', 2) != 2):
            raise ContractError('session_scope_unsupported')
    return selected
