"""The single match scenario model, derived at runtime for any RA3 1.12 map.

A scenario is built from public facts only: the loaded map path, the map's
public Player_N_Start waypoints, the native participant list, player
relationships and the model AI's own construction yard. There is no per-map
table: a new map needs no code change.

Everything that needs "which map, which seats, which teams, where is home"
imports from this module. Older session descriptors that predate the
``match`` block are read through ``MatchScenario.from_session``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import re

from .contracts import ContractError

# The native runtime binds the commander to player index 3: the SDK requires a
# unique player with index 3 (strategic-portable-runtime-v7/client.py
# 'unique_own_player_required') and the DLL's live identity check does too. The
# enemy-focus lease itself takes the own seat from the binding. In the lobby
# this is the second slot. Other seats (enemies, allies, humans) are not fixed.
MODEL_PLAYER_ID = 3
# TFCommander.big registers the commander personality for the Soviet side
# only (registry side check in session_discovery_native.source_fields).
MODEL_FACTION = 'Soviet'
# Soviet construction yard type hash, as used by the existing own-base origin
# checks (macro_live.require_base_origin, session_discovery_native).
MODEL_CONSTRUCTION_YARD = '0xc16ff13f'
# region_X_Y names are 512-unit map cells (stage_macro_regions.py,
# session_discovery_native.py origin derivation).
REGION_CELL = 512
# The compiled RegroupHome/WithdrawHome states gather at the public waypoint
# named Player_2_Start (native-ai/stage_macro_group_roles.py). They only mean
# "go home" when the commander actually starts there.
COMPILED_HOME_WAYPOINT = 'Player_2_Start'
HOME_WAYPOINT_ACTIONS = ('regroup', 'withdraw')
OWN_REGION_ACTIONS = ('deploydefense', 'regroup', 'reinforce', 'withdraw')

MAX_PLAYER_ID = 15
PLAYER_KINDS = ('model_ai', 'native_ai', 'human')
DIFFICULTIES = ('easy', 'medium', 'hard', 'brutal')
MODES = ('ai_vs_native', 'human_with_ai', 'human_vs_ai', 'other')

_REGION = re.compile(r'region_(\d{1,3})_(\d{1,3})')
_START = re.compile(r'Player_([1-8])_Start')
_MAP_ID = re.compile(r'[^\x00-\x1f\\/:*?"<>|]{1,128}')
# Display labels for maps we have seen. Cosmetic only: no behaviour depends on
# them and any other map is shown by its map id.
_MAP_LABELS = {
    'map_mp_2_black1b': 'TemplePrime',
    'map_mp_2_rao1': 'InfinityIsle',
    'map_mp_4_stewart_1': 'ColdShowdown',
}


def fail(code='session_scope_unsupported'):
    raise ContractError(code)


def is_region(value):
    return type(value) is str and _REGION.fullmatch(value) is not None


def region_for_point(x, y):
    """Return the region_X_Y cell that contains a map point."""
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in (x, y)):
        fail('session_probe_invalid')
    if x < 0 or y < 0 or x >= 1000 * REGION_CELL or y >= 1000 * REGION_CELL:
        fail('session_probe_invalid')
    return f'region_{int(x // REGION_CELL)}_{int(y // REGION_CELL)}'


def display_map_name(map_id):
    return _MAP_LABELS.get(map_id, map_id)


def own_base_point(census):
    """Position of the model AI's single living construction yard, or fail."""
    yards = [row for row in census.get('own_objects', [])
             if row.get('type_hash') == MODEL_CONSTRUCTION_YARD
             and type(row.get('hp')) in (int, float) and math.isfinite(row['hp']) and row['hp'] > 0]
    if len(yards) != 1:
        fail('session_scope_unsupported')
    point = yards[0].get('xyz', [])
    if len(point) != 3 or any(type(value) not in (int, float) or not math.isfinite(value) for value in point):
        fail('session_probe_invalid')
    return point[0], point[1]


def nearest_start(point, starts):
    """Name of the public start waypoint closest to a map point."""
    if not starts:
        return None
    return min(starts, key=lambda row: (math.dist(point, row['xyz'][:2]), row['name']))['name']


def start_by_vote(points, starts):
    """The start waypoint that most of a player's objects are closest to."""
    votes = {}
    for point in points:
        name = nearest_start(point, starts)
        if name is not None:
            votes[name] = votes.get(name, 0) + 1
    if not votes:
        return None
    return max(sorted(votes), key=lambda name: votes[name])


def assign_teams(model_player_id, relations, alliances):
    """Team numbers from relationships: 1 is the model's side, enemies 2+.

    ``relations`` maps each other participant to 'ally' or 'enemy' as seen by
    the model (both directions already verified). ``alliances`` holds pairs of
    other participants that are mutual allies. Enemies that are mutual allies
    share a team; teams are labels, not the lobby's team numbers.
    """
    teams = {model_player_id: 1}
    for player_id, relation in relations.items():
        if relation == 'ally':
            teams[player_id] = 1
        elif relation != 'enemy':
            fail('session_scope_unsupported')
    enemies = sorted(player_id for player_id, relation in relations.items() if relation == 'enemy')
    allied = {frozenset(pair) for pair in alliances}
    next_team = 2
    for player_id in enemies:
        if player_id in teams:
            continue
        group = [player_id]
        for other in enemies:
            if other not in teams and other not in group and frozenset((player_id, other)) in allied:
                group.append(other)
        for member in group:
            teams[member] = next_team
        next_team += 1
    return teams


@dataclass(frozen=True)
class ScenarioPlayer:
    player_id: int
    kind: str
    team: int
    difficulty: str | None = None
    faction: str | None = None

    def __post_init__(self):
        if type(self.player_id) is not int or not 0 <= self.player_id <= MAX_PLAYER_ID:
            fail()
        if self.kind not in PLAYER_KINDS:
            fail()
        if type(self.team) is not int or not 1 <= self.team <= MAX_PLAYER_ID + 1:
            fail()
        if self.difficulty is not None and self.difficulty not in DIFFICULTIES:
            fail()
        if self.faction is not None and (type(self.faction) is not str or not 1 <= len(self.faction) <= 32):
            fail()

    def public(self):
        return dict(player_id=self.player_id, kind=self.kind, team=self.team,
                    difficulty=self.difficulty, faction=self.faction)

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != {'player_id', 'kind', 'team', 'difficulty', 'faction'}:
            fail()
        return cls(**value)


@dataclass(frozen=True)
class MatchScenario:
    map_id: str
    display_map: str
    model_player_id: int
    players: tuple[ScenarioPlayer, ...]
    own_region: str
    enemy_regions: tuple[str, ...] = ()
    enemy_regions_exact: bool = False
    own_start_waypoint: str | None = None
    observer_player_ids: tuple[int, ...] = field(default=())

    def __post_init__(self):
        for name in ('map_id', 'display_map'):
            value = getattr(self, name)
            if type(value) is not str or _MAP_ID.fullmatch(value) is None:
                fail()
        if type(self.players) is not tuple or not all(isinstance(row, ScenarioPlayer) for row in self.players):
            fail()
        ids = [row.player_id for row in self.players]
        if len(ids) != len(set(ids)) or not 2 <= len(ids) <= 8:
            fail()
        models = [row for row in self.players if row.kind == 'model_ai']
        if len(models) != 1 or models[0].player_id != self.model_player_id:
            fail()
        if not self.enemy_player_ids:
            fail()
        if not is_region(self.own_region) or type(self.enemy_regions) is not tuple:
            fail()
        if any(not is_region(row) for row in self.enemy_regions):
            fail()
        if len(set(self.enemy_regions)) != len(self.enemy_regions):
            fail()
        if type(self.enemy_regions_exact) is not bool:
            fail()
        if self.own_start_waypoint is not None and (
                type(self.own_start_waypoint) is not str or _START.fullmatch(self.own_start_waypoint) is None):
            fail()
        observers = self.observer_player_ids
        if (type(observers) is not tuple or len(set(observers)) != len(observers)
                or any(type(index) is not int or not 0 <= index <= MAX_PLAYER_ID for index in observers)
                or set(observers) & set(ids)):
            fail()

    def player(self, player_id):
        return next(row for row in self.players if row.player_id == player_id)

    @property
    def player_ids(self):
        return tuple(sorted(row.player_id for row in self.players))

    @property
    def model_team(self):
        return self.player(self.model_player_id).team

    @property
    def teams(self):
        result = {}
        for row in sorted(self.players, key=lambda row: row.player_id):
            result.setdefault(row.team, []).append(row.player_id)
        return {team: tuple(ids) for team, ids in sorted(result.items())}

    @property
    def enemy_player_ids(self):
        team = self.model_team
        return tuple(sorted(row.player_id for row in self.players if row.team != team))

    @property
    def ally_player_ids(self):
        team = self.model_team
        return tuple(sorted(row.player_id for row in self.players
                            if row.team == team and row.player_id != self.model_player_id))

    @property
    def human_player_ids(self):
        return tuple(sorted(row.player_id for row in self.players if row.kind == 'human'))

    @property
    def participant_count(self):
        return len(self.players)

    @property
    def enemies_allied(self):
        """True when two or more enemies all share one team."""
        enemies = self.enemy_player_ids
        return len(enemies) > 1 and len({self.player(index).team for index in enemies}) == 1

    @property
    def mode(self):
        team = self.model_team
        humans = [self.player(index) for index in self.human_player_ids]
        if not humans:
            return 'ai_vs_native'
        if all(row.team == team for row in humans):
            return 'human_with_ai'
        if all(row.team != team for row in humans):
            return 'human_vs_ai'
        return 'other'

    @property
    def home_waypoint_verified(self):
        """Whether compiled home-waypoint actions really lead to our start."""
        return self.own_start_waypoint == COMPILED_HOME_WAYPOINT

    @property
    def regional_action_regions(self):
        """(action, region) labels shown to the model for regional actions."""
        pairs = []
        if len(self.enemy_regions) == 1 and self.enemy_regions_exact:
            pairs.append(('deployattack', self.enemy_regions[0]))
        for action in OWN_REGION_ACTIONS:
            if action in HOME_WAYPOINT_ACTIONS and not self.home_waypoint_verified:
                continue
            pairs.append((action, self.own_region))
        return tuple(pairs)

    @property
    def withheld_actions(self):
        """Actions this scenario cannot honour on the current compiled package."""
        return () if self.home_waypoint_verified else HOME_WAYPOINT_ACTIONS

    def matches_participants(self, verified):
        """Whether a fresh match_participants.verify_participants result is this match."""
        rows = verified.get('participants', [])
        kinds = {row['player_id']: row['kind'] for row in rows}
        relations = {row['player_id']: row['relation'] for row in rows if row['relation'] != 'self'}
        if verified.get('model_player_id') != self.model_player_id or self.model_player_id not in kinds:
            return False
        try:
            teams = assign_teams(self.model_player_id, relations, verified.get('alliances', []))
        except ContractError:
            return False
        return (kinds == {row.player_id: row.kind for row in self.players}
                and teams == {row.player_id: row.team for row in self.players})

    def match_state(self, frame, defeated_ids):
        """The public match-state block of a strategy snapshot."""
        result = dict(schema_version=1, source='native_public_match', observed_frame=frame,
                      opponent_player_ids=list(self.enemy_player_ids),
                      defeated_opponent_ids=[index for index in self.enemy_player_ids if index in defeated_ids],
                      opponents_allied=self.enemies_allied)
        if self.ally_player_ids or self.human_player_ids:
            result.update(ally_player_ids=list(self.ally_player_ids), human_player_ids=list(self.human_player_ids))
        return result

    def to_public_dict(self):
        """Shape listed by session discovery and shown in the desktop UI."""
        return dict(map_id=self.map_id, display_map=self.display_map, mode=self.mode,
                    model_player_id=self.model_player_id,
                    players=[row.public() for row in sorted(self.players, key=lambda row: row.player_id)],
                    teams={str(team): list(ids) for team, ids in self.teams.items()},
                    own_region=self.own_region, enemy_regions=list(self.enemy_regions),
                    enemy_regions_exact=self.enemy_regions_exact,
                    own_start_waypoint=self.own_start_waypoint,
                    observer_player_ids=list(self.observer_player_ids),
                    difficulty_verified=False)

    @classmethod
    def from_dict(cls, value):
        keys = {'map_id', 'display_map', 'mode', 'model_player_id', 'players', 'teams', 'own_region',
                'enemy_regions', 'enemy_regions_exact', 'own_start_waypoint', 'observer_player_ids',
                'difficulty_verified'}
        if type(value) is not dict or set(value) != keys or value['difficulty_verified'] is not False:
            fail()
        if type(value['players']) is not list or type(value['enemy_regions']) is not list:
            fail()
        if type(value['observer_player_ids']) is not list:
            fail()
        scenario = cls(value['map_id'], value['display_map'], value['model_player_id'],
                       tuple(ScenarioPlayer.from_dict(row) for row in value['players']),
                       value['own_region'], tuple(value['enemy_regions']), value['enemy_regions_exact'],
                       value['own_start_waypoint'], tuple(value['observer_player_ids']))
        if scenario.to_public_dict() != value:
            fail()
        return scenario

    def to_session_dict(self, commander_id):
        """The ``scenario`` block of session.json.

        ``match`` is the source of truth. The flat fields are derived from it
        for older readers and are cross-checked by ``from_session``.
        """
        enemies = list(self.enemy_player_ids)
        return dict(map_id=self.map_id, commander_id=commander_id,
                    computer_player_index=self.model_player_id, opponent_player_index=enemies[0],
                    opponent_player_indices=enemies, opponents_allied=self.enemies_allied,
                    participant_count=self.participant_count,
                    faction=self.player(self.model_player_id).faction,
                    origin_region=self.own_region, match=self.to_public_dict())

    @classmethod
    def from_session(cls, scenario):
        """Read a session.json ``scenario`` block, current or legacy."""
        if type(scenario) is not dict:
            fail()
        if 'match' in scenario:
            result = cls.from_dict(scenario['match'])
            derived = result.to_session_dict(scenario.get('commander_id'))
            if any(scenario.get(key) != item for key, item in derived.items()):
                fail()
            return result
        return cls._from_legacy_session(scenario)

    @classmethod
    def _from_legacy_session(cls, scenario):
        """Descriptors written before the match block: AI seats versus native AI.

        They name the model seat, one or two native opponents and a separate
        observer. Their own start waypoint was not recorded.
        """
        model = scenario.get('computer_player_index')
        opponents = scenario.get('opponent_player_indices', [scenario.get('opponent_player_index')])
        count = scenario.get('participant_count', 1 + len(opponents) if type(opponents) is list else None)
        if (type(model) is not int or type(opponents) is not list or not opponents
                or any(type(index) is not int for index in opponents)
                or scenario.get('opponent_player_index') != opponents[0]
                or type(count) is not int or count != 1 + len(opponents)):
            fail()
        allied = scenario.get('opponents_allied', False)
        if type(allied) is not bool or (allied and len(opponents) < 2) or (len(opponents) > 1 and not allied):
            fail()
        observer = scenario.get('observer_player_index', 2)
        players = [ScenarioPlayer(model, 'model_ai', 1, faction=scenario.get('faction', MODEL_FACTION))]
        players += [ScenarioPlayer(index, 'native_ai', 2 if allied else 2 + number)
                    for number, index in enumerate(opponents)]
        map_id = scenario.get('map_id')
        if type(map_id) is not str:
            fail()
        return cls(map_id, display_map_name(map_id), model, tuple(players), scenario.get('origin_region'),
                   observer_player_ids=(observer,) if type(observer) is int else ())


def derive_scenario(*, map_id, model_player_id, participants, alliances, own_point, starts,
                    allied_starts=(), observer_player_ids=(), model_faction=MODEL_FACTION):
    """Build a scenario from verified live participants and public map facts.

    ``participants`` are rows of player_id, kind and relation (to the model);
    the model's own row has relation 'self'. ``starts`` are the map's public
    Player_N_Start waypoints; ``allied_starts`` are start names already
    attributed to allied players. Remaining starts become enemy regions; they
    are exact only when their number matches the enemy count.
    """
    relations = {}
    kinds = {}
    for row in participants:
        kinds[row['player_id']] = row['kind']
        if row['player_id'] != model_player_id:
            relations[row['player_id']] = row['relation']
        elif row['kind'] != 'model_ai' or row['relation'] != 'self':
            fail()
    if model_player_id not in kinds:
        fail()
    teams = assign_teams(model_player_id, relations, alliances)
    players = tuple(ScenarioPlayer(player_id, kinds[player_id], teams[player_id],
                                   faction=model_faction if player_id == model_player_id else None)
                    for player_id in sorted(kinds))
    own_start = nearest_start(own_point, starts)
    friendly = {own_start, *allied_starts} - {None}
    enemy_starts = [row for row in sorted(starts, key=lambda row: row['name']) if row['name'] not in friendly]
    enemy_regions = []
    for row in enemy_starts:
        region = region_for_point(row['xyz'][0], row['xyz'][1])
        if region not in enemy_regions:
            enemy_regions.append(region)
    enemy_count = sum(relation == 'enemy' for relation in relations.values())
    exact = bool(enemy_starts) and len(enemy_starts) == enemy_count and len(enemy_regions) == enemy_count
    return MatchScenario(map_id, display_map_name(map_id), model_player_id, players,
                         region_for_point(*own_point), tuple(enemy_regions), exact, own_start,
                         tuple(sorted(observer_player_ids)))
