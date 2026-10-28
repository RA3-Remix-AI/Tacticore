"""Map terminal native result indices through the actual victory-player array.

No live reads/calls/writes. A result never establishes model contribution to a win.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

ROOT=Path(__file__).resolve().parents[1]
EXPECTED='ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
PINS={
    0xc07acc:'300b5700', # victory manager update virtual method
    0x570be1:'8d4d48',0x570c55:'33f68d5548', # participants array
    0x570c74:'80bc2ea000000000',0x570c95:'c6842ea000000001', # per-array-index defeat flag
    0x570ca3:'8b4f20898dc0000000', # last defeated Player+20; NOT the winner
    0x570ccb:'56e87ff90800', # push same participant index; record defeat
    0x600650:'8b44240483f805',0x600665:'89908033ce00', # result[index].defeat_frame
    0x558318:'8d5e48',0x55834d:'55e81d830a00', # same array/index; record victory
    0x600670:'8b44240483f805',0x600685:'89908433ce00', # result[index].victory_frame
    0x55835b:'83c50183c30483fd14',
}

def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def verify_static(game):
    raw=game.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=EXPECTED:raise ValueError('qualified_outcome_executable_required')
    pe=struct.unpack_from('<I',raw,0x3c)[0];number=struct.unpack_from('<H',raw,pe+6)[0]
    optional=struct.unpack_from('<H',raw,pe+20)[0];base=struct.unpack_from('<I',raw,pe+52)[0];sections=[]
    for i in range(number):
        p=pe+24+optional+i*40;vsize,rva,size,offset=struct.unpack_from('<4I',raw,p+8);sections.append((rva,size,offset))
    results=[]
    for address,expected in PINS.items():
        candidates=[offset+address-base-rva for rva,size,offset in sections if rva<=address-base<rva+size]
        if len(candidates)!=1 or raw[candidates[0]:candidates[0]+len(bytes.fromhex(expected))].hex()!=expected:
            raise ValueError('native_outcome_mapping_signature')
        results.append(dict(address=hex(address),bytes=expected))
    return results

def map_terminal(row,participants):
    if (participants.get('two_ai_combatants_verified') is not True or participants.get('mutual_enemy_relationship_verified') is not True
            or participants.get('observer_separate_from_combatants') is not True):raise ValueError('two_ai_outcome_scope_required')
    native=row.get('victory_conditions',{}).get('participants',[])
    expected={participants['model_player_id'],participants['opponent_player_id']}
    if len(native)!=2 or {r['player_index'] for r in native}!=expected:raise ValueError('outcome_participant_array_mismatch')
    if len({r['manager_index'] for r in native})!=2 or any(not 0<=r['manager_index']<6 or r['player_vtable']!='0xc5bce0' for r in native):
        raise ValueError('outcome_participant_index')
    records={r['native_index']:r for r in row['result_records']}
    outcomes=[]
    for p in native:
        r=records[p['manager_index']]
        if (r['raw'][2]!=r['defeat_frame'] or r['raw'][3]!=r['victory_frame'] or r['quit_frame']
                or r['disconnect_frame_candidate']):raise ValueError('outcome_record_inconsistent_or_disconnected')
        won=r['victory_frame']>0 and r['defeat_frame']==0 and p['defeated_flag_raw']==0
        lost=r['defeat_frame']>0 and r['victory_frame']==0 and p['defeated_flag_raw']==1
        if won==lost:raise ValueError('outcome_not_unique')
        if max(r['victory_frame'],r['defeat_frame'])>row['simulation_frame']:raise ValueError('outcome_future_frame')
        outcomes.append(dict(player_index=p['player_index'],manager_index=p['manager_index'],outcome='victory' if won else 'defeat',
            victory_frame=r['victory_frame'],defeat_frame=r['defeat_frame']))
    winners=[r for r in outcomes if r['outcome']=='victory'];losers=[r for r in outcomes if r['outcome']=='defeat']
    if len(winners)!=1 or len(losers)!=1 or winners[0]['victory_frame']<losers[0]['defeat_frame']:
        raise ValueError('two_ai_terminal_result_required')
    return dict(winner_player_index=winners[0]['player_index'],loser_player_index=losers[0]['player_index'],participants=outcomes,
        model_side_outcome='victory' if winners[0]['player_index']==participants['model_player_id'] else 'defeat')

def evaluate(run,watch):
    session=load(run/'session.json');pre=load(watch/'preflight.json');report=load(watch/'report.json')
    if any(pre[k]!=session[k] for k in ('session_id','pid','process_creation_filetime','mod_sha256')):
        raise ValueError('outcome_watch_session_mismatch')
    if (report['session_id']!=session['session_id'] or report['pid']!=session['pid'] or report['read_errors']!=0
            or report['reason']!='native_lifecycle_frame_reset'):raise ValueError('natural_watch_required')
    for source in pre['sources']:
        if sha(watch/'source'/source['copy'])!=source['sha256']:raise ValueError('outcome_watch_source_changed')
    rows=[json.loads(l) for l in (watch/'native-match-transitions.jsonl').read_text().splitlines()]
    if rows[-1].get('simulation_frame')!=0:raise ValueError('natural_frame_reset_required')
    last=[r for r in rows if r.get('simulation_frame')][-1];archive=load(run/'research-settlement.json')
    if archive['session_id']!=session['session_id'] or archive['natural_settlement_verified'] is not True:
        raise ValueError('visual_natural_archive_required')
    for key in ('screenshot','replay'):
        if sha(run/archive[key])!=archive[key+'_sha256']:raise ValueError('outcome_archive_changed')
    people=load(run/'battle-host/participants.json');proof=load(run/'battle-host/visibility-proof.json')
    own=next(r for r in last['victory_conditions']['participants'] if r['player_index']==people['model_player_id'])
    if int(own['player'],0)!=proof['handshake']['player'] or int(last['game_logic'],0)!=proof['handshake']['game_logic']:
        raise ValueError('outcome_native_owner_or_match_mismatch')
    result=map_terminal(last,people);pins=verify_static(Path(session['game']))
    paths=[run/'session.json',watch/'preflight.json',watch/'report.json',watch/'native-match-transitions.jsonl',
        run/'research-settlement.json',run/'battle-host/participants.json',run/'battle-host/visibility-proof.json']
    return dict(kind='native_two_ai_terminal_outcome_mapping',session_id=session['session_id'],pid=session['pid'],
        executable_sha256=EXPECTED,byte_checks=pins,last_live_frame=last['simulation_frame'],**result,
        native_winner_mapping_verified=True,visual_winner_symbol_mapping_verified=False,
        model_contribution_to_win_verified=False,full_G7_verified=False,formal_goal_complete=False,
        evidence={str(p.resolve()):sha(p) for p in paths})

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('run-directory','watch','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('fresh_outcome_assessment_required')
    result=evaluate(a.run_directory.resolve(),a.watch.resolve());out.mkdir();shutil.copy2(__file__,out/'assessor.py')
    result['assessor_sha256']=sha(out/'assessor.py');(out/'assessment.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('evidence','byte_checks')}))

if __name__=='__main__':main()
