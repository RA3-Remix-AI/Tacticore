"""Independent AK-only order/damage/return evidence review; immutable files only."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'acceptance/runs/20261025-010403-commander/ordered-ak03-static.json'
TEMPLATE=SOURCE.with_name('ordered-ak03-template.json')
WEAPONS=Path('E:/RA3Modding/SDK/SAGEXML/GlobalData/Weapon.xml')


def sdk_weapon():
    tree=ET.fromstring(WEAPONS.read_bytes());weapon=next(e for e in tree.iter() if e.tag.rsplit('}',1)[-1]=='WeaponTemplate' and e.get('id')=='SovietAntiInfantryInfantryAK47')
    nuggets=[e for e in weapon.iter() if e.tag.rsplit('}',1)[-1]=='DamageNugget']
    return dict(source_sha256=hashlib.sha256(WEAPONS.read_bytes()).hexdigest(),name=weapon.get('id'),clip_size=int(weapon.get('ClipSize')),required_anti_mask=weapon.get('RequiredAntiMask'),no_projectile=not any(e.tag.rsplit('}',1)[-1]=='ProjectileNugget' for e in weapon.iter()),damage=float(nuggets[0].get('Damage')),damage_delay_seconds=nuggets[0].get('DelayTimeSeconds'))


def audit(report,template,sdk):
    ev=report['events'];n=report['native'];pre=report['preflight'];rq=report['request'];issued=n['issued_frame'];returned=n['returned_frame'];source=pre['selected']['object_id'];target=rq['target_object_id'];thread=pre['window_thread']
    def get(kind,**fields):return [e for e in ev if e['kind']==kind and all(e.get(k)==v for k,v in fields.items()) and issued<=e['frame']<=returned]
    checks=dict(finished=report['status']=='finished' and report['host_exit']==0,
        binding=report['session_id']==pre['session_id']==n['session_id'] and n['commander_id']==pre['commander_id'] and all(n[k]==rq[k] for k in ('command_id','task_id','seq')),
        thread_owner=n['callback_thread']==thread and all(e['thread']==thread and e['owner']==int(pre['owner'],0) for e in ev),
        published_sequence=[e['seq'] for e in ev]==list(range(1,len(ev)+1)) and all(a['frame']<=b['frame'] for a,b in zip(ev,ev[1:])),
        finite_events=all(all(type(e[k]) in (int,float) and math.isfinite(e[k]) for k in ('x','y','z','damage_before','damage_after','damage_reported')) for e in ev),
        bounded=0<issued<n['attack_issued_frame']<returned<=issued+rq['lease_frames']+35,
        clean_restoration=n['phase']==3 and n['error']==n['active']==n['overflow']==n['lifecycle_fail']==0 and n['restore_mask']==2047 and n['return_verified']==1,
        normal_burst_not_single_shot=n['attack_calls']==n['attack_facade_calls']==n['attack_private_calls']==1 and n['limit_after']==0x7fffffff,
        observed_ak_template=template['session_id']==report['session_id'] and template['pid']==pre['pid'] and int(template['reported_entry'],0)==n['weapon_entry'] and int(template['reported_template'],0)==n['weapon_template'] and int(template['asset_type'],0)==0x94d4d96e and int(template['asset_id'],0)==0x447ea26e and template['template_name']==sdk['name'],
        sdk_direct_damage=sdk['no_projectile'] and sdk['damage_delay_seconds']=='0.0s' and sdk['clip_size']==3 and sdk['damage']==5 and 'ANTI_STRUCTURE' in sdk['required_anti_mask'],
        no_lease_override=not any(e['tag']==0 and e['kind'] in (10,12,14,16,18,30,32) and issued<=e['frame']<returned for e in ev))
    boundaries=[]
    for stage,gate_kind in ((0,37),(2,38)):
        stops=get(33,lease_stage=stage,arg=1,caller=0x787791);gates=get(gate_kind,lease_stage=stage);rows=[]
        if len(stops)==len(gates)==1:
            for e in get(3,lease_stage=stage):
                if stops[0]['seq']<e['seq']<gates[0]['seq'] and stops[0]['frame']<e['frame']<=gates[0]['frame'] and (not rows or rows[-1]['frame']!=e['frame']):rows.append(e)
        rows=rows[-3:];clean=len(rows)==3 and all(e['path']==0 and e['sm_flags']&0xffff==0 and e['source']==1 for e in rows) and all(math.hypot(a['x']-b['x'],a['y']-b['y'])<=1 for a,b in zip(rows,rows[1:]))
        checks['stop_'+str(stage)]=bool(clean) and len(gates)==1 and math.hypot(rows[-1]['x']-gates[0]['x'],rows[-1]['y']-gates[0]['y'])<=1
        boundaries.append(dict(stage=stage,frames=[e['frame'] for e in rows],gate_seq=gates[0]['seq'] if gates else 0))
    facade=get(34,tag=2,arg=target,arg_shots=0x7fffffff,arg_source=1);private=get(12,tag=2,arg=target,arg_shots=0x7fffffff,arg_source=1,caller=0x78785f)
    checks['unique_order']=len(facade)==len(private)==1 and len(get(12))==1 and boundaries[0]['gate_seq']<facade[0]['seq']<private[0]['seq'] and private[0]['frame']==n['attack_issued_frame'] and private[0]['holder']==0
    commits=get(24,damage_source=source,target_id=target);bodies=get(20,damage_source=source,target_id=target);ammo=get(22,damage_source=source,target_id=target)
    checks['one_source_body_commit']=len(commits)==len(bodies)==len(ammo)==1 and n['damage_count']==n['commit_own_calls']==n['shot_samples']==1
    cycle={}
    if len(commits)==len(bodies)==len(ammo)==1:
        commit,body,drop=commits[0],bodies[0],ammo[0]
        checks['hp_commit_agreement']=commit['caller']==0x7d2946 and body['caller']==0x78e313 and commit['seq']<body['seq'] and commit['frame']==body['frame'] and commit['tick']==body['tick'] and all(commit[k]==body[k] for k in ('damage_before','damage_after','damage_reported')) and commit['damage_before']-commit['damage_after']==sdk['damage']==commit['damage_reported']==n['damage_total']
        prior=[e for e in get(3,lease_stage=1) if e['seq']<commit['seq']];after=[e for e in get(3,lease_stage=1) if e['seq']>commit['seq']]
        checks['one_observed_firing_interval']=bool(prior) and bool(after) and private and private[0]['seq']<prior[-1]['seq']<commit['seq']<body['seq']<after[0]['seq']<drop['seq']<boundaries[1]['gate_seq'] and after[0]['frame']==drop['frame'] and after[0]['tick']==drop['tick'] and 0<=drop['tick']-commit['tick']<=150 and 0<=drop['frame']-commit['frame']<=2 and commit['lease_stage']==body['lease_stage']==drop['lease_stage']==1
        checks['same_verified_entry_ammo']=n['weapon_entry']>0 and n['weapon_template']>0 and n['weapon_slot']>0 and drop['damage_before']==n['weapon_ammo']==3 and drop['damage_after']==n['last_ammo']==2
        cycle=dict(order_frame=n['attack_issued_frame'],body_frame=body['frame'],body_seq=body['seq'],setter_seq=commit['seq'],hp_before=body['damage_before'],hp_after=body['damage_after'],damage=body['damage_reported'],source_actor_id=source,target_object_id=target,ammo_observed_frame=drop['frame'],ammo_before=drop['damage_before'],ammo_after=drop['damage_after'],damage_to_poll_ms=drop['tick']-commit['tick'],poll_frame_before=prior[-1]['frame'] if prior else None,poll_frame_after=after[0]['frame'] if after else None)
    checks['normal_return']=n['detach_calls']==n['return_calls']==1 and n['stop_calls']==n['private_stop_calls']==2 and n['stop_failed']==0 and len(get(18,tag=1,caller=0x838877,arg=int(pre['ai'],0)+0x104))==1 and len(get(16,tag=3,caller=0x83885b,arg=int(pre['ai'],0)+0x104))==1 and any(e['kind']==15 and e['tag']==3 and e['arg']==1 and e['frame']==returned and e['team']==int(pre['default_team'],0) for e in ev)
    return dict(verified=all(checks.values()),checks=checks,stop_boundaries=boundaries,firing_interval=cycle,scope='main_attack:Conscript_AK47_direct_damage_ground_target_only',post_return_native_attack_frames=[e['frame'] for e in ev if e['kind']==12 and e['tag']==0 and e['frame']>=returned],harass_economy_verified=all(checks.values()) and rq.get('target_role')=='economy',flak_verified=False,molotov_verified=False,source_diagnostic_lock_preserved=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=SOURCE);p.add_argument('--template',type=Path,default=TEMPLATE);p.add_argument('--output',type=Path,default=Path(__file__).with_name('ordered-ak03-independent.json'));a=p.parse_args();raw=a.source.read_bytes();report=json.loads(raw);template=json.loads(a.template.read_text(encoding='utf-8'));sdk=sdk_weapon();result=audit(report,template,sdk)
    result['checks']['template_report_sha']=template['report_sha256']==hashlib.sha256(raw).hexdigest();result['verified']=all(result['checks'].values());assert result['verified'],result
    mutants=[]
    bad=copy.deepcopy(report);bad['native']['return_verified']=0;mutants.append((bad,template))
    bad=copy.deepcopy(report)
    for event in bad['events']:
        if event['kind']==22:event['frame']+=10;event['tick']+=700
    mutants.append((bad,template))
    bad=copy.deepcopy(report)
    for event in bad['events']:
        if event['kind'] in (20,24):event['damage_source']=999
    mutants.append((bad,template))
    bad_template=dict(template,asset_id='0x41872ecc',template_name='SovietAntiInfantryInfantryMolotovCocktail');mutants.append((report,bad_template))
    bad=copy.deepcopy(report)
    for event in bad['events']:
        if event['kind']==3 and event['frame']==2699:event['x']+=50
    mutants.append((bad,template))
    assert all(not audit(record,mapping,sdk)['verified'] for record,mapping in mutants)
    result.update(source_report=str(a.source),source_sha256=hashlib.sha256(raw).hexdigest(),template_evidence_sha256=hashlib.sha256(a.template.read_bytes()).hexdigest(),sdk_weapon=sdk,negative_cases=len(mutants),game_or_api_access=False,capabilities_granted=[])
    a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
