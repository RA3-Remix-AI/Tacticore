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


def scenario_for_map(map_id):
    for scenario in (TEMPLE_PRIME, INFINITY_ISLE):
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
    return selected
