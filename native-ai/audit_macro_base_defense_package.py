"""Permit one own-infrastructure defense state change from qualified regions."""
import argparse
import json
from pathlib import Path
import shutil
from audit_macro_region_package import sha
from validate_side_imports import read_stream


def evaluate(old,new):
    before=json.loads((old/'build-report.json').read_text());after=json.loads((new/'build-report.json').read_text())
    if (before['big_sha256']!='4a65c9b683c9de210f84aa14383cc99f1bef9fe066b7295151bf1edce46171bd'
            or after['big_sha256']!='7a78e3cb66f759aa66b0e877fcc7eca725b4469f3091c0932944967eaf9f0828'
            or sha(old/'TFMacroProbe.big')!=before['big_sha256'] or sha(new/'TFMacroProbe.big')!=after['big_sha256']
            or before['flags']!=after['flags']):raise ValueError('base_defense_packages_required')
    expected=next(r['state'] for r in after['consumers'] if r['action']=='deploydefense');streams=[];evidence={}
    for stem in ('mod','mod_M','mod_L'):
        a=read_stream(old/'package/data'/(stem+'.manifest'));b=read_stream(new/'package/data'/(stem+'.manifest'))
        by={r['name']:r for r in b['rows']};changed=[]
        if set(by)!={r['name'] for r in a['rows']}:raise ValueError('base_defense_asset_set_changed')
        for row in a['rows']:
            other=by[row['name']]
            same=all(row[k]==other[k] for k in ('refs','type_id','instance_id','type_hash','instance_hash','flags'))
            for ext,offset,size in [('bin','binary_offset','binary_size'),('imp','imp_offset','imp_size'),('relo','relo_offset','relo_size')]:
                same=same and a['files'][ext][row[offset]:row[offset]+row[size]]==b['files'][ext][other[offset]:other[offset]+other[size]]
            if not same:changed.append(row['name'])
        if changed!=[expected]:raise ValueError('unreviewed_base_defense_asset_change')
        streams.append(dict(stream=stem,changed=changed,unchanged_assets=len(a['rows'])-1))
        for folder in (old,new):
            for ext in ('manifest','bin','imp','relo'):
                p=folder/'package/data'/(stem+'.'+ext);evidence[str(p.resolve())]=sha(p)
    for folder in (old,new):
        for name in ('build-report.json','TFMacroProbe.big','MacroProbe.xml'):evidence[str((folder/name).resolve())]=sha(folder/name)
    return dict(kind='compiled_one_native_base_defense_preservation_audit',base_package_sha256=before['big_sha256'],
        package_sha256=after['big_sha256'],streams=streams,only_east_task_definition_changed=True,
        qualified_west_attack_budget_build_production_and_scout_preserved=True,
        original_micro_assets_preserved=True,native_execution_granted=False,evidence=evidence)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','candidate','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if out.exists():raise ValueError('fresh_base_defense_audit_required')
    value=evaluate(a.baseline.resolve(),a.candidate.resolve());out.mkdir();shutil.copy2(__file__,out/'auditor.py')
    value['auditor_sha256']=sha(out/'auditor.py');(out/'audit.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k!='evidence'}))


if __name__=='__main__':main()
