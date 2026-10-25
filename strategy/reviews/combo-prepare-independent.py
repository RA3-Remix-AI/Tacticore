"""Synthetic Molotov branch contract checks; never a live combo capability proof."""
import copy,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tactical'))
from test_combo_qualification import ComboQualificationTests
import combo_qualification as qualifier


def fixture():
    raw,binding=ComboQualificationTests().fixture();events=raw['events'];boundary=next(e for e in events if e['kind']==42);at=events.index(boundary);base=boundary['frame'];old=copy.deepcopy(boundary);stage3=[]
    for event in events[:at]:event.update(active_weapon_asset=0x41872ecc,active_weapon_entry=raw['native']['weapon_entry']+128)
    for kind in (40,41):stage3.append(dict(old,kind=kind,tag=5,arg=raw['native']['button'] if kind==40 else 0,lease_stage=3))
    for frame in (base+15,base+17,base+19):stage3.append(dict(old,kind=3,frame=frame,tag=0,lease_stage=3))
    boundary.update(frame=base+19,lease_stage=3)
    for event in events[at+1:]:event['frame']+=19
    raw['events']=events[:at]+stage3+events[at:]
    for i,event in enumerate(raw['events']):event.update(seq=i+1,tick=event['frame']*60)
    raw['native'].update(initial_weapon_asset=0x41872ecc,toggle_calls=1,toggle_hook_calls=1,toggle_frame=base,ak_samples=3,observed_weapon_entry=raw['native']['weapon_entry'],prepare_gate_frame=base+19,attack_issued_frame=raw['native']['attack_issued_frame']+19,returned_frame=raw['native']['returned_frame']+19)
    return raw,binding


def main():
    raw,binding=fixture();base=qualifier.qualify(raw,binding);assert base['status']=='bounded_ak_ordered_attack_verified',base['checks']
    cases=[]
    bad=copy.deepcopy(raw);next(e for e in bad['events'] if e['kind']==40)['arg']=0;cases.append(('wrong_button',bad))
    bad=copy.deepcopy(raw)
    for event in bad['events']:
        if event['kind']==3 and event['lease_stage']==3:event['frame']=raw['native']['toggle_frame']+13
    cases.append(('early_or_duplicate_pack_samples',bad))
    bad=copy.deepcopy(raw);next(e for e in bad['events'] if e['kind']==3 and e['lease_stage']==3)['state_id']=96;cases.append(('pack_not_idle',bad))
    bad=copy.deepcopy(raw);next(e for e in bad['events'] if e['kind']==3 and e['lease_stage']==3)['path']=123;cases.append(('path_not_clear',bad))
    bad=copy.deepcopy(raw);next(e for e in bad['events'] if e['kind']==43)['active_weapon_asset']=0x41872ecc;cases.append(('weapon_changed_after_prepare',bad))
    bad=copy.deepcopy(raw);next(e for e in bad['events'] if e['kind']==20)['lease_stage']=3;cases.append(('old_prepare_damage_not_new_order',bad))
    results=[]
    for name,report in cases:
        result=qualifier.qualify(report,binding);assert result['status']=='not_passed',name
        results.append(dict(case=name,rejected=True))
    result=dict(source='synthetic_protocol_joined_to_archived_ak_packet',live_evidence=False,game_or_api_access=False,purpose_granted=False,qualifier_sha256=hashlib.sha256(Path(qualifier.__file__).read_bytes()).hexdigest(),positive_status=base['status'],positive_checks=len(base['checks']),negative_cases=results)
    Path(__file__).with_name('combo-prepare-independent.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
