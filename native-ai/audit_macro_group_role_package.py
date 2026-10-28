"""Bound the three group-role candidates to otherwise preserved native assets."""
import argparse
import json
from pathlib import Path
import shutil
from audit_macro_region_package import sha
from validate_side_imports import read_stream


def evaluate(old,new):
    before=json.loads((old/'build-report.json').read_text());after=json.loads((new/'build-report.json').read_text())
    if (before['big_sha256']!='7a78e3cb66f759aa66b0e877fcc7eca725b4469f3091c0932944967eaf9f0828'
            or before['flags']!=after['flags'] or after.get('group_roles_candidate_revision') not in (1,2)
            or any(sha(d/'TFMacroProbe.big')!=r['big_sha256'] for d,r in ((old,before),(new,after)))):
        raise ValueError('group_role_candidate_packages_required')
    removed={r['state'] for r in before['consumers'] if r['action'] in ('build_airfield','buildtech','economyrefinery')}
    added={r['state'] for r in after['consumers'] if r['action'] in ('regroup','reinforce','withdraw')}
    if len(removed)!=3 or len(added)!=3:raise ValueError('three_role_replacements_required')
    personality='AIPersonalityDefinition:'+after['personality'];streams=[];evidence={}
    for stem in ('mod','mod_M','mod_L'):
        a=read_stream(old/'package/data'/(stem+'.manifest'));b=read_stream(new/'package/data'/(stem+'.manifest'))
        am={r['name']:r for r in a['rows']};bm={r['name']:r for r in b['rows']}
        if set(am)-set(bm)!=removed or set(bm)-set(am)!=added:raise ValueError('unreviewed_role_asset_set_change')
        changed=[]
        for name in sorted(set(am)&set(bm)):
            row,other=am[name],bm[name]
            same=all(row[k]==other[k] for k in ('refs','type_id','instance_id','type_hash','instance_hash','flags'))
            for ext,offset,size in [('bin','binary_offset','binary_size'),('imp','imp_offset','imp_size'),('relo','relo_offset','relo_size')]:
                same=same and a['files'][ext][row[offset]:row[offset]+row[size]]==b['files'][ext][other[offset]:other[offset]+other[size]]
            if not same:changed.append(name)
        if changed!=[personality]:raise ValueError('qualified_or_original_role_asset_changed')
        streams.append(dict(stream=stem,removed_unqualified_states=sorted(removed),added_candidate_states=sorted(added),
            changed_common_assets=changed,unchanged_assets=len(set(am)&set(bm))-1))
        for folder in (old,new):
            for ext in ('manifest','bin','imp','relo'):
                p=folder/'package/data'/(stem+'.'+ext);evidence[str(p.resolve())]=sha(p)
    for folder in (old,new):
        for name in ('build-report.json','TFMacroProbe.big','MacroProbe.xml'):evidence[str((folder/name).resolve())]=sha(folder/name)
    return dict(kind='compiled_three_group_role_candidate_preservation_audit',base_package_sha256=before['big_sha256'],
        package_sha256=after['big_sha256'],streams=streams,qualified_consumers_preserved=True,
        original_micro_assets_preserved=True,only_unqualified_custom_build_states_replaced=True,
        native_execution_granted=False,product_capability_granted=False,evidence=evidence)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','candidate','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if out.exists():raise ValueError('fresh_group_role_audit_required')
    value=evaluate(a.baseline.resolve(),a.candidate.resolve());out.mkdir();shutil.copy2(__file__,out/'auditor.py')
    value['auditor_sha256']=sha(out/'auditor.py');(out/'audit.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k!='evidence'}))
