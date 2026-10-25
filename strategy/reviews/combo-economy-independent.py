"""Independent real-case preparation/order/AK packet/return audit; files only."""
import copy,hashlib,json,math,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'acceptance/runs/20261025-030636-commander/combo-economy01.json'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def audit(r):
    ev=r['events'];n=r['native'];p=r['preflight'];q=r['request'];start=n['issued_frame'];end=n['returned_frame'];attack=n['attack_issued_frame'];actor=p['selected']['object_id'];target=q['target_object_id']
    def get(kind,**fields):return [e for e in ev if e['kind']==kind and all(e.get(k)==v for k,v in fields.items()) and start<=e['frame']<=end]
    checks=dict(finished=r['status']=='finished' and r['host_exit']==0,
        binding=r['session_id']==p['session_id']==n['session_id'] and n['commander_id']==p['commander_id'] and p['player_id']==3 and p['selected']['type_hash']=='0x19ab11af' and all(n[k]==q[k] for k in ('command_id','task_id','seq')),
        owner_thread=all(e['owner']==int(p['owner'],0) and e['thread']==p['window_thread'] for e in ev) and n['callback_thread']==p['window_thread'],
        ordered_log=[e['seq'] for e in ev]==list(range(1,len(ev)+1)) and all(a['frame']<=b['frame'] and 0<=((b['tick']-a['tick'])&0xffffffff)<0x80000000 for a,b in zip(ev,ev[1:])),
        finite_critical=all(all(type(e[k]) in (int,float) and math.isfinite(e[k]) for k in ('x','y','z','damage_before','damage_after','damage_reported')) for e in ev),
        exact_refinery=r['private_target']['type_hash']=='0xc45aaeab' and r['private_target']['object_id']==target and r['private_target']['owner_player_id']==4 and q['target_role']=='economy',
        normal_bounded_ownership=n['detach_calls']==n['return_calls']==n['return_verified']==1 and start<n['toggle_frame']<n['prepare_gate_frame']<attack<end<=start+q['lease_frames'],
        normal_inputs=n['stop_calls']==n['private_stop_calls']==3 and n['toggle_calls']==n['toggle_hook_calls']==1 and n['attack_calls']==n['attack_facade_calls']==n['attack_private_calls']==1 and n['move_calls']==n['stop_failed']==0,
        hooks_restored=n['phase']==3 and n['error']==n['active']==n['overflow']==n['lifecycle_fail']==n['return_pending']==0 and n['restore_mask']==4095,
        no_lease_override=not any(e['tag']==0 and e['kind'] in (10,12,14,16,18,30,40) and start<=e['frame']<end for e in ev))
    boundaries={}
    for stage,kind in ((0,37),(4,43),(2,38)):
        stops=get(33,lease_stage=stage,tag=4,arg=1,caller=0x787791);gates=get(kind);rows=[]
        if len(stops)==len(gates)==1:
            for e in get(3,lease_stage=stage):
                if stops[0]['seq']<e['seq']<gates[0]['seq'] and stops[0]['frame']<e['frame']<=gates[0]['frame'] and (not rows or rows[-1]['frame']!=e['frame']):rows.append(e)
        rows=rows[-3:]
        okay=len(rows)==3 and all(e['path']==0 and e['sm_flags']&0xffff==0 and e['source']==1 and e['holder']==0 for e in rows) and all(math.hypot(a['x']-b['x'],a['y']-b['y'])<=1 for a,b in zip(rows,rows[1:]))
        checks['raw_stop_'+str(stage)]=bool(okay) and len(gates)==1 and gates[0]['state_id']==16 and gates[0]['requested']==gates[0]['effective']==[0,0,0]
        boundaries[str(stage)]=dict(frames=[e['frame'] for e in rows],gate_seq=gates[0]['seq'] if gates else 0)
    buttons=get(40,tag=5,arg=n['button']);button_out=get(41,tag=5);prepared=get(42);replay=get(33,lease_stage=3,tag=0,arg=1,caller=0x787791)
    ak=[e for e in get(3,lease_stage=3) if e['frame']>=n['toggle_frame']+15][-3:]
    checks['normal_button_and_pack']=q['button']['toggle']['asset_id']=='0x5977a798' and q['button']['toggle']['asset_type']=='0x7d464170' and q['button']['command_set_hash']=='0xb74cf71a' and int(q['button']['toggle']['entry'],0)==n['button'] and int(q['button']['toggle']['schema'],0)==n['button_schema'] and len(buttons)==len(button_out)==len(prepared)==1 and boundaries['0']['gate_seq']<buttons[0]['seq']<button_out[0]['seq']<prepared[0]['seq']<boundaries['4']['gate_seq'] and buttons[0]['frame']==button_out[0]['frame']==n['toggle_frame'] and n['initial_weapon_asset']==0x41872ecc
    checks['three_distinct_idle_ak']=len(ak)==3 and len({e['frame'] for e in ak})==3 and all(e['active_weapon_asset']==0x447ea26e and e['active_weapon_entry']==n['observed_weapon_entry']==n['weapon_entry'] and e['state_id']==16 and e['source']==1 and e['path']==e['holder']==0 and not(e['sm_flags']&0xffff) and not(e['status84']&0x20080000) for e in ak)
    checks['only_bounded_reconstituted_stop']=len(replay)==n['prepare_reconstituted_stops']==1 and n['toggle_frame']+15<=replay[0]['frame']<=n['prepare_gate_frame'] and replay[0]['state_id']==16 and replay[0]['active_weapon_asset']==0x447ea26e and len(get(33))==4 and n['total_private_stops']==4
    orders=[e for e in ev if e['kind'] in (34,12,13,35) and e['tag']==2]
    checks['unique_fresh_script_attack']=len(orders)==4 and [e['kind'] for e in orders]==[34,12,13,35] and len(get(12))==1 and all(e['arg']==target and e['arg_source']==1 and e['arg_shots']==0x7fffffff and e['frame']==attack and e['active_weapon_asset']==0x447ea26e and e['active_weapon_entry']==n['weapon_entry'] for e in orders) and boundaries['4']['gate_seq']<orders[0]['seq']<orders[1]['seq']<orders[2]['seq']<orders[3]['seq']
    bodies=get(20,damage_source=actor,target_id=target);commits=get(24,damage_source=actor,target_id=target);ammo=get(22,damage_source=actor,target_id=target);hit={}
    checks['single_bound_actual_damage']=len(bodies)==len(commits)==len(ammo)==1 and n['damage_count']==n['commit_own_calls']==n['shot_samples']==1
    if len(bodies)==len(commits)==len(ammo)==1:
        body=bodies[0];commit=commits[0];drop=ammo[0];words=body['stack_words'][:body['stack_word_count']];anchors=[]
        for i,word in enumerate(words[:-5]):
            if word!=0x78e313:continue
            ptr=words[i+1];base=body['stack_words_address']
            if ptr<base or (ptr-base)%4:continue
            at=(ptr-base)//4
            if at+36>=len(words) or words[i+2]!=r['private_target']['address'] or words[i+4]!=0x7ad79e or words[i+5]!=ptr:continue
            packet=words[at:at+37];amount=struct.unpack('<f',struct.pack('<I',packet[36]))[0]
            if packet[:3]==[0xbe9508,0xbe9318,actor] and packet[4]==packet[5]==0x447ea26e and packet[7]==21 and math.isfinite(amount) and amount==body['damage_reported']:anchors.append(dict(argument_address=hex(ptr),word_offset=at,asset='0x447ea26e',source=actor,damage_type=21,amount=amount))
        checks['exact_current_damage_info']=body['caller']==0x78e313 and len(anchors)==1
        checks['actual_setter_and_body']=commit['caller']==0x7d2946 and commit['frame']==body['frame'] and commit['tick']==body['tick'] and all(commit[k]==body[k] for k in ('damage_before','damage_after','damage_reported')) and body['damage_before']-body['damage_after']==body['damage_reported']==n['damage_total']==5 and orders[-1]['seq']<commit['seq']<body['seq']<boundaries['2']['gate_seq'] and body['lease_stage']==commit['lease_stage']==1
        checks['same_ak_entry_near_tick_ammo']=body['active_weapon_asset']==drop['active_weapon_asset']==0x447ea26e and body['active_weapon_entry']==drop['active_weapon_entry']==n['weapon_entry']==n['observed_weapon_entry'] and drop['damage_before']==n['weapon_ammo']==3 and drop['damage_after']==n['last_ammo']==2 and body['seq']<drop['seq']<boundaries['2']['gate_seq'] and 0<=drop['frame']-body['frame']<=2 and 0<=drop['tick']-body['tick']<=200
        hit=dict(frame=body['frame'],actor=actor,target=target,hp_before=body['damage_before'],hp_after=body['damage_after'],ammo_frame=drop['frame'],damage_to_ammo_poll_ms=drop['tick']-body['tick'],packet=anchors)
    returns=get(15,tag=3,arg=1)
    checks['normal_native_pool_return']=len(returns)==1 and returns[0]['frame']==end and returns[0]['team']==int(p['default_team'],0) and returns[0]['seq']>boundaries['2']['gate_seq'] and any(e['kind']==16 and e['tag']==3 and e['caller']==0x83885b and e['arg']==int(p['ai'],0)+0x104 and e['frame']==end for e in ev)
    asset=r['weapon_asset_binding'];checks['actual_getter_asset_binding']=asset['session_id']==r['session_id'] and asset['pid']==p['pid'] and int(asset['reported_entry'],0)==n['weapon_entry'] and int(asset['reported_template'],0)==n['weapon_template'] and asset['asset_type']=='0x94d4d96e' and asset['asset_id']=='0x447ea26e' and asset['observed_frame']==attack
    return dict(verified=all(checks.values()),checks=checks,stop_boundaries=boundaries,prepare_ak_frames=[e['frame'] for e in ak],button_frame=n['toggle_frame'],reconstituted_stop_frames=[e['frame'] for e in replay],attack_frame=attack,hit=hit,return_frame=end,post_return_native_attacks=[e['frame'] for e in ev if e['kind']==12 and e['tag']==0 and e['frame']>=end],scope='main_attack_and_harass_economy:Conscript_normal_prepare_AK_direct_ground_only',flak_or_molotov_attack_granted=False)

def main():
    raw=SOURCE.read_bytes();r=json.loads(raw);result=audit(r);folder=ROOT/'tactical/ordered-combo';mapping={'native_binary_sha256':'bin/TacticalOrderedCombo.dll','native_host_sha256':'bin/tactical_host.exe','native_source_sha256':'lease.cpp','native_shared_sha256':'shared.h'}
    result['checks']['frozen_build']=all(r[key]==digest(folder/name) for key,name in mapping.items())
    proof=SOURCE.with_name('combo-economy01-proof.json');visibility=json.loads(proof.read_text(encoding='utf-8'));safety=ROOT/'visibility/template-safety-2d7873e1.json';catalog=json.loads(safety.read_text(encoding='utf-8'));entry=catalog['templates'][r['private_target']['type_hash']]
    result['checks']['exact_safety_role']=digest(safety)==r['request']['safety_sha256']=='1d14e41e10224fb2a8215a2321a7fbbbeae8434b8c006a80fd314f4a11e7719e' and entry['role']=='economy' and entry['template']=='SovietRefinery'
    result['checks']['viewer3_footprint_proof']=digest(proof)==r['request']['visibility_proof_sha256'] and visibility['session_id']==r['session_id'] and visibility['target_player_id']==3 and visibility['package_sha256']==r['package_sha256'] and visibility['object_visibility_method']=='native_footprint_reconstruction' and all(visibility[k] is True for k in ('footprint_live_verified','terrain_view_live_verified','object_view_live_verified','no_observer_fallback','conservative_stealth_exclusion_reviewed'))
    result['checks']['exact_exe_package']=r['executable_sha256']=='ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165' and r['package_sha256']=='2d7873e1b2d2c79950ff9da70b5452b1210370a6d6cbec1eaa69201a7d3d0665'
    result['verified']=all(result['checks'].values());assert result['verified'],result
    mutants=[]
    bad=copy.deepcopy(r);bad['private_target']['type_hash']='0xd50c222e';mutants.append(bad)
    bad=copy.deepcopy(r);bad['native']['return_verified']=0;mutants.append(bad)
    bad=copy.deepcopy(r);next(e for e in bad['events'] if e['kind']==40)['arg']=0;mutants.append(bad)
    bad=copy.deepcopy(r);next(e for e in bad['events'] if e['kind']==3 and e['lease_stage']==3 and e['frame']==2882)['state_id']=96;mutants.append(bad)
    bad=copy.deepcopy(r);next(e for e in bad['events'] if e['kind']==20)['stack_words'][36]=0x41872ecc;mutants.append(bad)
    bad=copy.deepcopy(r);next(e for e in bad['events'] if e['kind']==22)['active_weapon_entry']+=4;mutants.append(bad)
    assert all(not audit(record)['verified'] for record in mutants)
    result.update(source_report=str(SOURCE),source_sha256=hashlib.sha256(raw).hexdigest(),negative_cases=len(mutants),game_or_api_access=False,capabilities_granted=[],grant_recommendation='Both purposes may use this exact verified primitive after trusted host re-verifies current frozen runtime; no broader weapon/actor/target class grant.')
    destination=Path(__file__).with_name('combo-economy01-independent.json');destination.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
