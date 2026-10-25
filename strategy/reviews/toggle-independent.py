"""Immutable normal-toggle case review, not a generic allowance for Stop overrides."""
import copy,hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'acceptance/runs/20261025-022351-commander/toggle01.json'

def audit(r):
    e=r['events'];n=r['native'];p=r['preflight'];q=r['request'];toggle=n['toggle_frame'];end=n['returned_frame'];button=int(q['button']['toggle']['entry'],0)
    def get(kind,**fields):return [x for x in e if x['kind']==kind and all(x.get(k)==v for k,v in fields.items())]
    own_stop=get(23,tag=4,arg=1,caller=0x787791);gate=get(24);rows=[]
    if len(own_stop)==len(gate)==1:
        for row in get(3):
            if own_stop[0]['seq']<row['seq']<gate[0]['seq'] and own_stop[0]['frame']<row['frame']<=gate[0]['frame'] and (not rows or row['frame']!=rows[-1]['frame']):rows.append(row)
    rows=rows[-3:];stable=len(rows)==3 and all(x['path']==0 and x['sm_flags']&0xffff==0 and x['source']==1 for x in rows) and all(math.hypot(a['x']-b['x'],a['y']-b['y'])<=1 for a,b in zip(rows,rows[1:]))
    inputs=get(32,tag=5,arg=button);outputs=get(33,tag=5);returns=get(15,tag=3,arg=1)
    ak=[x for x in get(3) if toggle+15<=x['frame']<=end and x['weapon_asset']==0x447ea26e and x['weapon_entry']==n['observed_weapon_entry']]
    ready=get(31);recent=ak[-3:]
    replay=[x for x in get(23,tag=0,arg=1,caller=0x787791) if toggle<=x['frame']<end]
    checks=dict(finished=r['status']=='finished' and r['host_exit']==0,
        binding=r['session_id']==p['session_id']==n['session_id'] and n['commander_id']==p['commander_id'] and all(n[k]==q[k] for k in ('command_id','task_id','seq')),
        identity=all(x['owner']==int(p['owner'],0) and x['thread']==p['window_thread'] for x in e) and n['callback_thread']==p['window_thread'],
        log_order=[x['seq'] for x in e]==list(range(1,len(e)+1)) and all(a['frame']<=b['frame'] for a,b in zip(e,e[1:])),
        own_stop_boundary=bool(stable) and len(gate)==1 and n['stop_calls']==len(get(20,tag=4,arg=1))==1,
        exact_registered_button=q['button']['toggle']['asset_id']=='0x5977a798' and q['button']['toggle']['asset_type']=='0x7d464170' and q['button']['command_set_hash']=='0xb74cf71a' and n['button']==button and q['source']==1 and q['third_flag']==0,
        one_normal_input=n['toggle_calls']==n['toggle_hook_calls']==len(inputs)==len(outputs)==1 and gate[0]['seq']<inputs[0]['seq']<outputs[0]['seq'] and inputs[0]['frame']==outputs[0]['frame']==toggle,
        actual_weapon_transition=n['initial_weapon_asset']==0x41872ecc and n['observed_weapon_asset']==0x447ea26e and n['initial_weapon_entry']!=n['observed_weapon_entry'] and r['initial_weapon']['selected']['template_id']=='0x41872ecc',
        distinct_pack_samples=len(recent)==3 and len({x['frame'] for x in recent})==3 and len(ready)==1 and recent[-1]['seq']<ready[0]['seq'] and recent[-1]['frame']==ready[0]['frame']==end and n['ak_samples']==3 and all(not x['status84']&0x20080000 for x in recent),
        expected_replay_window=len(replay)==1 and replay[0]['frame']>=toggle+15 and replay[0]['weapon_asset']==0x447ea26e and replay[0]['state_id']==16 and replay[0]['path']==0 and replay[0]['requested']==replay[0]['effective']==[0,0,0] and replay[0]['source']==1 and not any(x['kind']==20 and toggle<=x['frame']<end for x in e),
        all_private_stops_explained=n['private_stop_calls']==len(own_stop)+len(replay)==2 and len([x for x in get(23) if n['issued_frame']<=x['frame']<end])==2,
        no_moves_or_attacks=n['move_calls']==0 and n['native_move']==n['native_attack']==n['native_add']==n['native_remove']==0 and not any(x['kind'] in (10,12,20,32) and x['tag']==0 and n['issued_frame']<=x['frame']<end for x in e),
        clean_pool_return=n['detach_calls']==n['return_calls']==n['return_verified']==len(returns)==1 and returns[0]['frame']==end and returns[0]['team']==int(p['default_team'],0) and ready[0]['seq']<returns[0]['seq'] and any(x['kind']==16 and x['tag']==3 and x['caller']==0x83885b and x['arg']==int(p['ai'],0)+0x104 and x['frame']==end for x in e),
        restored=n['phase']==3 and n['error']==n['active']==n['overflow']==n['lifecycle_fail']==n['return_pending']==0 and n['restore_mask']==255,
        bounded=0<n['issued_frame']<toggle<end<=n['issued_frame']+q['lease_frames'])
    return dict(verified=all(checks.values()),checks=checks,stop_frames=[x['frame'] for x in rows],button_frame=toggle,ak_frames=[x['frame'] for x in recent],reconstituted_stop_frames=[x['frame'] for x in replay],returned_frame=end,scope='normal_conscript_molotov_to_ak_auxiliary_only',replay_causality='Observed timing, source, ordinary private caller, idle transition and no second facade are consistent with the SDK RECONSTITUTE_STORED_COMMAND option; no generic Stop override exemption.',model_purpose_granted=False,stable_weapon_after_return_claim=False)

def main():
    raw=SOURCE.read_bytes();r=json.loads(raw);result=audit(r);folder=ROOT/'tactical/toggle-aux';result['checks']['binary_host_revision']=all(r[key]==hashlib.sha256((folder/path).read_bytes()).hexdigest() for key,path in [('native_binary_sha256','bin/TacticalWeaponToggle.dll'),('native_host_sha256','bin/tactical_host.exe')]);result['verified']=all(result['checks'].values());assert result['verified'],result
    mutants=[]
    bad=copy.deepcopy(r);bad['native']['return_verified']=0;mutants.append(bad)
    bad=copy.deepcopy(r);next(x for x in bad['events'] if x['kind']==32)['arg']=0;mutants.append(bad)
    bad=copy.deepcopy(r);next(x for x in bad['events'] if x['kind']==23 and x['frame']==1553)['caller']=0;mutants.append(bad)
    bad=copy.deepcopy(r)
    for x in bad['events']:
        if x['kind']==3 and x['frame'] in (1552,1554,1556):x['frame']=1552
    mutants.append(bad)
    assert all(not audit(record)['verified'] for record in mutants)
    after=SOURCE.with_name('post-toggle-weapon.json');post=json.loads(after.read_text(encoding='utf-8'));result.update(source_report=str(SOURCE),source_sha256=hashlib.sha256(raw).hexdigest(),original_status=r['assessment']['status'],negative_cases=len(mutants),game_or_api_access=False,after_return_readonly=dict(frame=post['frame'],object_id=post['units'][0]['object_id'],asset=post['units'][0]['selected']['template_id'],sha256=hashlib.sha256(after.read_bytes()).hexdigest()))
    output=Path(__file__).with_name('toggle01-independent.json');output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
