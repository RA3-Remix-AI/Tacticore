"""Read-only proof of two actual AI combatants and a separate observer slot."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'native-ai'))
sys.path.insert(0,str(ROOT.parent/'visibility'))
from read_selected_personality import inspect_player
from native_read import read_player_relation

def verify_two_ai(memory,native_state,registry,model_player,opponent_player,observer_player=2):
    if len({model_player,opponent_player,observer_player})!=3:raise ValueError('Combatants and observer must be distinct')
    rows=native_state.get('victory_conditions',{}).get('participants',[])
    indices=[x.get('player_index') for x in rows]
    if len(rows)!=2 or set(indices)!={model_player,opponent_player}:raise ValueError('Expected exactly two AI combatants')
    players=memory.u32(0xce8c9c)
    identities={}
    for index in (model_player,opponent_player):
        row=next(x for x in rows if x['player_index']==index)
        address=memory.u32(players+0x30+4*index)
        if int(row['player'],0)!=address:raise ValueError('Participant pointer differs from player list')
        identity=inspect_player(memory.read,address)
        if identity['player_index']!=index:raise ValueError('Participant identity mismatch')
        identities[index]=identity
    registered={int(asset['instance_id'],0) for commander in registry.get('commanders',[]) for asset in commander.get('assets',[])}
    if int(identities[opponent_player]['instance_id'],0) in registered:raise ValueError('Opponent is a model commander, not a native personality')
    model_address=int(identities[model_player].get('player',next(x['player'] for x in rows if x['player_index']==model_player)),0)
    opponent_address=int(identities[opponent_player].get('player',next(x['player'] for x in rows if x['player_index']==opponent_player)),0)
    if read_player_relation(memory,model_address,opponent_player)!='enemy' or read_player_relation(memory,opponent_address,model_player)!='enemy':raise ValueError('Combatants are not mutual enemies')
    observer=memory.u32(players+0x30+4*observer_player)
    if not observer or memory.u32(observer)!=0xc5bce0 or memory.u32(observer+0x20)!=observer_player or memory.u32(observer+0x90)!=0:raise ValueError('Observer slot is not a separate human player')
    if memory.u32(0xce8c9c)!=players:raise ValueError('Player-list lifecycle changed')
    return dict(two_ai_combatants_verified=True,mutual_enemy_relationship_verified=True,observer_separate_from_combatants=True,model_player_id=model_player,opponent_player_id=opponent_player,observer_player_id=observer_player,model_personality=identities[model_player]['instance_id'],opponent_personality=identities[opponent_player]['instance_id'],opponent_native_ai_verified=True)
