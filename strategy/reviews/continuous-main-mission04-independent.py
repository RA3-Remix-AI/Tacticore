"""Independent raw-case review. No producer qualification or active game calls."""
import copy,hashlib,json,math,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'acceptance/runs/20261025-095141-commander/main-mission04.json'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def xy(e):return [e['x'],e['y'],e['z']]
def dist(a,b):return math.hypot(a[0]-b[0],a[1]-b[1])

def audit(r):
    n=r['native'];q=r['request'];pre=r['preflight'];ev=r['events'];actor=pre['selected']['object_id'];target=q['target_object_id']
    issued=n['issued_frame'];returned=n['returned_frame'];thread=pre['window_thread'];owner=int(pre['owner'],0)
    ret=next(e for e in ev if e['kind']==15 and e['tag']==3 and e['arg']==1)
    lease=[e for e in ev if issued<=e['frame'] and e['seq']<=ret['seq']]
    def get(kind,**fields):return [e for e in lease if e['kind']==kind and all(e.get(k)==v for k,v in fields.items())]
    stages=[e for e in ev if e['kind']==50];by_stage={e['arg']:e for e in stages}
    checks={
        'finished_clean':r['status']=='finished' and r['host_exit']==0 and n['phase']==3 and n['restore_mask']==16383 and all(n[k]==0 for k in ['error','active','overflow','lifecycle_fail','owner_fail','stop_failed','return_pending']),
        'binding':r['session_id']==pre['session_id']==n['session_id'] and pre['player_id']==3 and pre['pid']==63320 and pre['commander_id']==n['commander_id'] and pre['selected']['type_hash']=='0x19ab11af' and actor==830 and target==774 and all(q[k]==n[k] for k in ['command_id','task_id','seq']),
        'raw_sequence':all(e['seq']==i+1 for i,e in enumerate(ev)) and all(b['frame']>=a['frame'] and 0<=((b['tick']-a['tick'])&0xffffffff)<0x80000000 for a,b in zip(ev,ev[1:])),
        'owner_thread':all(e['owner']==owner and e['thread']==thread for e in lease) and n['callback_thread']==thread,
        'immutable_deadline':q['mission_protocol']=='continuous_tactical_v1' and q['expires_frame']==q['mission']['expires_frame']==n['mission_deadline_frame'] and pre['frame']<=issued<returned<=q['expires_frame'] and q['expires_frame']-pre['frame']<=4500,
        'stage_sequence':[e['arg'] for e in stages]==list(range(1,11)) and all(e['stage_revision']==i+1 and e['mission_stage']==e['arg'] and e['stage_frame']==e['frame'] for i,e in enumerate(stages)),
        'no_lease_override':not any(e['tag']==0 and e['kind'] in [10,12,14,16,18,30,52,54] for e in lease),
        'raw_target_source_scope':r['private_target']['object_id']==target and r['private_target']['owner_player_id']==4 and r['private_target']['type_hash']=='0xc45aaeab' and q['target_role']=='economy',
    }
    boundaries={}
    for stage,kind in [(0,37),(6,58),(4,43),(7,59),(2,38)]:
        stop=get(33,lease_stage=stage,tag=4,arg=1,caller=0x787791);gate=get(kind);samples=[]
        if len(stop)==len(gate)==1:
            for e in get(3,lease_stage=stage):
                if stop[0]['seq']<e['seq']<gate[0]['seq'] and stop[0]['frame']<e['frame'] and (not samples or samples[-1]['frame']!=e['frame']):samples.append(e)
        samples=samples[-3:]
        checks['stop_clean_'+str(stage)]=len(samples)==3 and all(e['path']==e['holder']==0 and e['source']==1 and not e['sm_flags']&0xffff for e in samples) and all(dist(xy(a),xy(b))<=1 for a,b in zip(samples,samples[1:]))
        boundaries[str(stage)]=[e['frame'] for e in samples]
    moves=[e for e in lease if e['kind'] in [54,52,53,55]];move_groups=[moves[i:i+4] for i in range(0,len(moves),4)]
    checks['four_normal_move_chains']=len(moves)==16 and len(move_groups)==4 and n['move_calls']==n['normal_move_facade_calls']==n['normal_move_private_calls']==4 and n['approach_move_calls']==n['retreat_move_calls']==2 and all([e['kind'] for e in g]==[54,52,53,55] and len({e['move_index'] for e in g})==1 and all(e['tag']==6 and e['arg']==1 and math.dist(e['command_xyz'],g[0]['command_xyz'])<=.01 for e in g) and g[1]['argument_path']==0 and g[1]['argument_limit']>1e30 for g in move_groups)
    initial=by_stage[2];near=by_stage[3];goal=q['mission']['retreat_point']['xyz'];arrive=get(60)
    approach=dist(xy(initial),xy(near));initial_distance=dist(xy(initial),initial['visible_target_xyz'])
    checks['live_long_approach']=initial['current_visible']==near['current_visible']==1 and initial['frame']==n['approach_started'] and initial_distance>=300 and approach>=120 and dist(xy(near),near['visible_target_xyz'])<=125.01 and near['frame']-initial['frame']<=q['mission']['approach_frames']
    checks['own_origin_retreat_provenance']=q['mission']['retreat_point']['source']=='own_actor_history' and q['mission']['retreat_point']['anchor_object_id']==actor and math.dist(goal,xy(by_stage[1]))<=15 and math.dist(n['retreat_goal'],goal)<.01
    retreat_samples=[]
    if len(arrive)==1:
        retreat_samples=[e for e in get(3,mission_stage=8) if e['seq']<arrive[0]['seq'] and e['move_index']==arrive[0]['move_index']]
        retreat_samples=list({e['frame']:e for e in retreat_samples}.values())[-3:]
    retreat_distance=dist(xy(by_stage[7]),xy(arrive[0])) if arrive else 0
    checks['live_long_retreat_three_frames']=len(retreat_samples)==3 and retreat_distance>=120 and all(dist(xy(e),goal)<=15 and abs(e['z']-goal[2])<=10 for e in retreat_samples) and arrive[0]['frame']<returned and n['retreat_started']==by_stage[7]['frame']
    buttons=get(40,tag=5);replay=get(33,tag=0,lease_stage=3,caller=0x787791,arg=1)
    ready=[e for e in get(3,mission_stage=4) if e['frame']>=n['toggle_frame']+15][-3:]
    checks['normal_toggle_and_idle_ak']=len(buttons)==n['toggle_calls']==n['toggle_hook_calls']==1 and buttons[0]['frame']==n['toggle_frame'] and q['button']['toggle']['asset_id']=='0x5977a798' and len(ready)==3 and len({e['frame'] for e in ready})==3 and all(e['active_weapon_asset']==0x447ea26e and e['active_weapon_entry']==n['weapon_entry'] and e['state_id']==16 and e['path']==e['holder']==0 for e in ready) and len(replay)==1 and replay[0]['frame']>=n['toggle_frame']+15
    orders=[e for e in lease if e['kind'] in [34,12,13,35] and e['tag']==2]
    checks['unique_fresh_script_attack']=len(orders)==4 and [e['kind'] for e in orders]==[34,12,13,35] and all(e['frame']==n['attack_issued_frame'] and e['arg']==target and e['arg_source']==1 and e['arg_shots']==0x7fffffff and e['active_weapon_entry']==n['weapon_entry'] and e['active_weapon_asset']==0x447ea26e for e in orders) and n['attack_calls']==n['attack_facade_calls']==n['attack_private_calls']==1
    body=get(20,damage_source=actor,target_id=target);commit=get(24,damage_source=actor,target_id=target);drop=get(22,damage_source=actor,target_id=target)
    packet=[]
    if len(body)==len(commit)==len(drop)==1:
        b=body[0];c=commit[0];a=drop[0];words=b['stack_words'][:b['stack_word_count']]
        for i,w in enumerate(words[:-5]):
            if w!=0x78e313:continue
            ptr=words[i+1];base=b['stack_words_address']
            if ptr<base or (ptr-base)%4:continue
            off=(ptr-base)//4
            if off+36>=len(words) or words[i+2]!=r['private_target']['address'] or words[i+4]!=0x7ad79e or words[i+5]!=ptr:continue
            data=words[off:off+37];amount=struct.unpack('<f',struct.pack('<I',data[36]))[0]
            if data[:3]==[0xbe9508,0xbe9318,actor] and data[4]==data[5]==0x447ea26e and data[7]==21 and amount==b['damage_reported']:packet.append({'asset':'0x447ea26e','source':actor,'damage_type':'GUN','amount':amount,'word_offset':off})
        checks['new_order_actual_body_setter']=b['caller']==0x78e313 and c['caller']==0x7d2946 and b['frame']==c['frame'] and b['tick']==c['tick'] and all(b[k]==c[k] for k in ['damage_before','damage_after','damage_reported']) and b['damage_before']-b['damage_after']==b['damage_reported']==n['damage_total']==5 and orders[-1]['seq']<c['seq']<b['seq']<by_stage[7]['seq']
        checks['actual_ak_damage_info']=len(packet)==1
        checks['same_entry_ammo_after_order']=a['active_weapon_entry']==b['active_weapon_entry']==n['weapon_entry']==n['observed_weapon_entry'] and a['active_weapon_asset']==b['active_weapon_asset']==0x447ea26e and a['damage_before']==n['weapon_ammo']==3 and a['damage_after']==n['last_ammo']==2 and b['seq']<a['seq']<by_stage[7]['seq'] and 0<=a['frame']-b['frame']<=2 and 0<=a['tick']-b['tick']<=200
    else:checks.update(new_order_actual_body_setter=False,actual_ak_damage_info=False,same_entry_ammo_after_order=False)
    asset=r['weapon_asset_binding']
    checks['actual_weapon_getter_asset']=asset['session_id']==r['session_id'] and asset['pid']==pre['pid'] and int(asset['reported_entry'],0)==n['weapon_entry'] and int(asset['reported_template'],0)==n['weapon_template'] and asset['asset_type']=='0x94d4d96e' and asset['asset_id']=='0x447ea26e' and asset['observed_frame']==n['attack_issued_frame']
    checks['normal_pool_return']=n['detach_calls']==n['return_calls']==n['return_verified']==1 and ret['frame']==returned and ret['team']==int(pre['default_team'],0) and any(e['kind']==16 and e['tag']==3 and e['caller']==0x83885b and e['arg']==int(pre['ai'],0)+0x104 and e['seq']<ret['seq'] for e in lease)
    return {'verified':all(checks.values()),'checks':checks,'approach_initial_distance':initial_distance,'approach_actual_displacement':approach,'retreat_actual_displacement':retreat_distance,'retreat_three_frames':[e['frame'] for e in retreat_samples],'final_origin_distance':dist(xy(arrive[0]),goal) if arrive else None,'stop_boundaries':boundaries,'attack_frame':n['attack_issued_frame'],'damage_frame':body[0]['frame'] if body else None,'damage_packet':packet,'return_frame':returned,'scope':'main_attack_calibration_only; separate harassment command/raw still required'}

if __name__=='__main__':
    r=json.loads(SOURCE.read_text(encoding='utf-8'));result=audit(r);directory=ROOT/'tactical/mission-combat'
    fields={'native_binary_sha256':'bin/TacticalMissionCombat.dll','native_host_sha256':'bin/tactical_host.exe','wrapper_sha256':'lease.py','native_source_sha256':'lease.cpp','native_shared_sha256':'shared.h','mission_contract_sha256':'mission_contract.py'}
    result['source_sha256']=sha(SOURCE);result['source_report']=str(SOURCE)
    result['revision_checks']={field:r[field]==sha(directory/name) for field,name in fields.items()}
    result['revision_checks']['mission_tick.inc']=r['native_includes_sha256']['mission_tick.inc']==sha(directory/'mission_tick.inc')
    negatives={}
    for name in ['zero_effect','wrong_source','no_retreat','same_frame_arrival','wrong_entry','wrong_packet']:
        modified=copy.deepcopy(r)
        if name=='zero_effect':modified['native']['damage_total']=0
        elif name=='wrong_source':next(e for e in modified['events'] if e['kind']==20)['damage_source']=999
        elif name=='no_retreat':modified['request']['mission']['retreat_point']['xyz'][0]+=200
        elif name=='same_frame_arrival':
            end=next(e for e in modified['events'] if e['kind']==60)
            candidates=[e for e in modified['events'] if e['kind']==3 and e['mission_stage']==8 and e['seq']<end['seq']][-3:]
            for e in candidates:e['frame']=candidates[-1]['frame']
        elif name=='wrong_entry':next(e for e in modified['events'] if e['kind']==22)['active_weapon_entry']+=4
        else:
            body=next(e for e in modified['events'] if e['kind']==20);body['stack_words']=[0]*len(body['stack_words'])
        negatives[name]=not audit(modified)['verified']
    result['negative_tests_rejected']=negatives
    readonly_path=SOURCE.with_name('main-mission04-terminal-readonly.json')
    readonly=json.loads(readonly_path.read_text(encoding='utf-8'))
    layout=json.loads((directory/'inert-layout.json').read_text(encoding='utf-8'))
    expected={e['address']:e['expected'] for e in layout['entries']}
    actual={e['address']:e for e in readonly['entries']}
    result['terminal_readonly_checks']={
        'same_report':readonly['source_sha256']==sha(SOURCE),
        'same_session_pid':readonly['session_id']==r['session_id'] and readonly['pid']==r['preflight']['pid'],
        'layout_exact_native_build':layout['dll_sha256']==r['native_binary_sha256']==sha(directory/'bin/TacticalMissionCombat.dll'),
        'timer_zero':readonly['timer']==0,
        'terminal_clean':readonly['phase']==3 and readonly['error']==readonly['active']==0 and readonly['restore_mask']==16383,
        'fourteen_entries_against_pinned_layout':len(expected)==len(actual)==len(readonly['entries'])==14 and set(expected)==set(actual) and all(actual[a]['expected']==actual[a]['actual']==actual[a]['file_bytes']==value for a,value in expected.items()),
    }
    result['terminal_readonly_source_sha256']=sha(readonly_path)
    Path(__file__).with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
