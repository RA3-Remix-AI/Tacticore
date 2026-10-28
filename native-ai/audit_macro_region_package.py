"""Compare compiled regional consumers with the qualified macro package.

Static preservation is not field qualification or an execution capability.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from validate_side_imports import read_stream

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def evaluate(old,new):
    before=json.loads((old/'build-report.json').read_text());after=json.loads((new/'build-report.json').read_text())
    if (sha(old/'TFMacroProbe.big')!=before['big_sha256'] or sha(new/'TFMacroProbe.big')!=after['big_sha256']
            or before['flags']!=after['flags'] or after.get('regional_waypoints_revision') not in (1,2,3)):raise ValueError('region_package_binding')
    changed_expected={r['state'] for r in after['consumers'] if r['action'] in ('deployattack','deploydefense')}
    new_expected={r['name'] for r in after['assets'] if r['name'].startswith('AITargetingHeuristic:')}
    reports=[];evidence={}
    for stem in ('mod','mod_M','mod_L'):
        a=read_stream(old/'package/data'/(stem+'.manifest'));b=read_stream(new/'package/data'/(stem+'.manifest'))
        by={r['name']:r for r in b['rows']};old_names={r['name'] for r in a['rows']};changed=[];same=[]
        for r in a['rows']:
            t=by.get(r['name'])
            if t is None:raise ValueError('regional_package_removed_asset')
            identical=all(r[k]==t[k] for k in ('refs','type_id','instance_id','type_hash','instance_hash','flags'))
            for ext,off,size in [('bin','binary_offset','binary_size'),('imp','imp_offset','imp_size'),('relo','relo_offset','relo_size')]:
                identical=identical and a['files'][ext][r[off]:r[off]+r[size]]==b['files'][ext][t[off]:t[off]+t[size]]
            (same if identical else changed).append(r['name'])
        added=set(by)-old_names
        if set(changed)!=changed_expected or added!=new_expected or len(added)!=2:
            raise ValueError('regional_package_changed_unreviewed_assets')
        reports.append(dict(stream=stem,unchanged_assets=len(same),changed_assets=changed,added_assets=sorted(added)))
        for folder in (old,new):
            for ext in ('manifest','bin','imp','relo'):
                p=folder/'package/data'/(stem+'.'+ext);evidence[str(p.resolve())]=sha(p)
    for folder in (old,new):
        for name in ('build-report.json','TFMacroProbe.big','MacroProbe.xml'):
            p=folder/name;evidence[str(p.resolve())]=sha(p)
    return dict(kind='compiled_region_waypoint_preservation_audit',base_package_sha256=before['big_sha256'],
        regional_package_sha256=after['big_sha256'],streams=reports,only_two_prior_unqualified_deployment_states_changed=True,
        qualified_budget_build_production_and_scout_assets_preserved=True,native_field_verified=False,
        product_capability_granted=False,formal_goal_complete=False,evidence=evidence)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('baseline','regional','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise ValueError('fresh_region_audit_required')
    value=evaluate(a.baseline,a.regional);a.output.mkdir(parents=True);shutil.copy2(__file__,a.output/'auditor.py')
    value['auditor_sha256']=sha(a.output/'auditor.py');(a.output/'audit.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k!='evidence'}))

if __name__=='__main__':main()
