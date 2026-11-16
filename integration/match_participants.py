"""Read-only proof of AI combatants, relationships and a separate observer."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'native-ai'))
sys.path.insert(0,str(ROOT.parent/'visibility'))
from read_selected_personality import inspect_player
from native_read import read_player_relation

def verify_ai_combatants(memory, native_state, registry, model_player,
                         opponent_players, observer_player=2, *, opponents_allied=False):
    opponents = tuple(opponent_players)
    indices = (model_player, *opponents, observer_player)
    if (len(opponents) not in (1, 2)
            or any(type(index) is not int or not 0 <= index < 16 for index in indices)
            or len(set(indices)) != len(indices)):
        raise ValueError('Expected distinct AI combatants and a separate observer')
    if type(opponents_allied) is not bool:
        raise ValueError('Opponent alliance requirement must be explicit')
    rows=native_state.get('victory_conditions',{}).get('participants',[])
    expected = {model_player, *opponents}
    if len(rows) != len(expected) or {row.get('player_index') for row in rows} != expected:
        raise ValueError('Actual combatants differ from the expected match')
    players=memory.u32(0xce8c9c)
    identities = {}
    addresses = {}
    registered={int(asset['instance_id'],0) for commander in registry.get('commanders',[]) for asset in commander.get('assets',[])}
    for index in (model_player, *opponents):
        row=next(x for x in rows if x['player_index']==index)
        address=memory.u32(players+0x30+4*index)
        if int(row['player'],0)!=address:raise ValueError('Participant pointer differs from player list')
        identity=inspect_player(memory.read,address)
        if identity['player_index']!=index:raise ValueError('Participant identity mismatch')
        identities[index]=identity
        addresses[index] = address
        if index in opponents and int(identity['instance_id'], 0) in registered:
            raise ValueError('Opponent is a model commander, not a native personality')
    for opponent in opponents:
        if (read_player_relation(memory, addresses[model_player], opponent) != 'enemy'
                or read_player_relation(memory, addresses[opponent], model_player) != 'enemy'):
            raise ValueError('Combatants are not mutual enemies')
    if opponents_allied:
        for source in opponents:
            for target in opponents:
                if source != target and read_player_relation(memory, addresses[source], target) != 'ally':
                    raise ValueError('Opponents are not mutual allies')
    observer=memory.u32(players+0x30+4*observer_player)
    if not observer or memory.u32(observer)!=0xc5bce0 or memory.u32(observer+0x20)!=observer_player or memory.u32(observer+0x90)!=0:raise ValueError('Observer slot is not a separate human player')
    if (memory.u32(0xce8c9c) != players
            or any(memory.u32(players + 0x30 + 4 * index) != address for index, address in addresses.items())):
        raise ValueError('Player-list lifecycle changed')
    return dict(ai_combatants_verified=True, mutual_enemy_relationship_verified=True,
                observer_separate_from_combatants=True, model_player_id=model_player,
                opponent_player_ids=list(opponents), observer_player_id=observer_player,
                model_personality=identities[model_player]['instance_id'],
                opponent_personalities={str(index): identities[index]['instance_id'] for index in opponents},
                opponent_native_ai_verified=True, opponents_allied_verified=opponents_allied and len(opponents) == 2)


def verify_two_ai(memory,native_state,registry,model_player,opponent_player,observer_player=2):
    result = verify_ai_combatants(memory, native_state, registry, model_player,
                                  (opponent_player,), observer_player)
    return dict(two_ai_combatants_verified=True, mutual_enemy_relationship_verified=True,
                observer_separate_from_combatants=True, model_player_id=model_player,
                opponent_player_id=opponent_player, observer_player_id=observer_player,
                model_personality=result['model_personality'],
                opponent_personality=result['opponent_personalities'][str(opponent_player)],
                opponent_native_ai_verified=True)


def controlled_match_result(native_state, model_player, opponent_players):
    """Map result slots through combatant identities, retaining partial eliminations."""
    expected = {model_player, *opponent_players}
    participants = native_state.get('victory_conditions', {}).get('participants', [])
    records = native_state.get('result_records', [])
    if (len(participants) != len(expected)
            or {row.get('player_index') for row in participants} != expected):
        raise ValueError('Result combatants differ from the admitted match')
    slots = {}
    for row in records:
        index = row.get('native_index')
        if type(index) is not int or not 0 <= index < 6 or index in slots:
            raise ValueError('Native result slot identity is invalid')
        slots[index] = row
    outcomes = {}
    manager_indices = set()
    for player in participants:
        index = player.get('manager_index')
        if type(index) is not int or index not in slots or index in manager_indices:
            raise ValueError('Result slot cannot be bound to its combatant')
        manager_indices.add(index)
        row = slots[index]
        frames = {name: row.get(name, 0) for name in ('victory_frame', 'defeat_frame', 'quit_frame')}
        if any(type(frame) is not int or not 0 <= frame <= 0xffffffff for frame in frames.values()):
            raise ValueError('Native result frame is invalid')
        if frames['victory_frame'] and (frames['defeat_frame'] or frames['quit_frame']):
            raise ValueError('Native victory conflicts with defeat or quit')
        outcome = ('victory' if frames['victory_frame'] else 'defeat' if frames['defeat_frame']
                   else 'quit' if frames['quit_frame'] else 'ongoing')
        outcomes[str(player['player_index'])] = dict(outcome=outcome, **frames)
    own = outcomes[str(model_player)]['outcome']
    return dict(terminal=own != 'ongoing', controlled_outcome=own, players=outcomes,
                remaining_opponents=sum(outcomes[str(index)]['outcome'] == 'ongoing' for index in opponent_players),
                all_opponents_defeated=all(outcomes[str(index)]['outcome'] == 'defeat' for index in opponent_players))
