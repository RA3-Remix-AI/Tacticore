"""Read-only verifier mutations; deliberately never dispatches any command."""
import copy,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tactical'))
from ordered_qualification import qualify

def main():
    source=ROOT/'acceptance/runs/20261025-010403-commander/ordered-ak03-static.json';raw=source.read_bytes();report=json.loads(raw);binding=json.loads(source.with_name('ordered-ak03-template.json').read_text(encoding='utf-8'));cases=[]
    bad=copy.deepcopy(report);hits=[e for e in bad['events'] if e['kind'] in (20,24)];bad['events']=[e for e in bad['events'] if e['kind'] not in (20,24)];at=next(i for i,e in enumerate(bad['events']) if e['kind']==34 and e['tag']==2);bad['events'][at:at]=hits
    for i,e in enumerate(bad['events']):e['seq']=i+1
    cases.append(('damage_before_script_order_and_backward_frame',bad))
    bad=copy.deepcopy(report);next(e for e in bad['events'] if e['kind']==3 and e['frame']==2704)['frame']=2600;cases.append(('single_sample_clock_regression',bad))
    bad=copy.deepcopy(report);bad['native']['weapon_ammo']=1;bad['native']['last_ammo']=0;cases.append(('native_ammo_1_to_0_contradicts_event_3_to_2',bad))
    results=[]
    for name,bad in cases:
        result=qualify(bad,binding);results.append(dict(case=name,expected='not_passed',actual=result['status'],rejected=result['status']=='not_passed'))
    bad=copy.deepcopy(report);bad['request']['target_role']='economy';result=qualify(bad,binding);results.append(dict(case='factory_relabelled_economy',private_type_hash=bad['private_target']['type_hash'],expected_harass_economy_verified=False,actual_harass_economy_verified=result['harass_economy_verified'],rejected=not result['harass_economy_verified']))
    output=dict(original_report=str(source),source_sha256=hashlib.sha256(raw).hexdigest(),qualifier_sha256=hashlib.sha256((ROOT/'tactical/ordered_qualification.py').read_bytes()).hexdigest(),original_qualified=qualify(report,binding)['status'],counterexamples=results,all_rejected=all(x['rejected'] for x in results),game_or_api_access=False)
    Path(__file__).with_name('ordered-qualification-counterexamples.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8');print(json.dumps(output,indent=2))

if __name__=='__main__':main()
