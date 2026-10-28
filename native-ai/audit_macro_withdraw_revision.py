"""Permit only the reviewed withdrawal recruitment revision between role fields."""
import argparse
import json
from pathlib import Path
import shutil
from audit_macro_region_package import sha
from validate_side_imports import read_stream

OLD='aec5131537d2852c5ccda55391e85a74a3457256859fc94a924832cacc0da756'
NEW='bf0bb3105dc9d1124173ff8aa6ccfa15e494ceb550f78e05600092356970c260'


def evaluate(old,new):
    a_report=json.loads((old/'build-report.json').read_text());b_report=json.loads((new/'build-report.json').read_text())
    if (a_report['big_sha256']!=OLD or b_report['big_sha256']!=NEW or sha(old/'TFMacroProbe.big')!=OLD
            or sha(new/'TFMacroProbe.big')!=NEW or a_report['flags']!=b_report['flags']):
        raise ValueError('exact_withdrawal_revision_required')
    expected=next(r['state'] for r in b_report['consumers'] if r['action']=='withdraw');streams=[];evidence={}
    for stem in ('mod','mod_M','mod_L'):
        a=read_stream(old/'package/data'/(stem+'.manifest'));b=read_stream(new/'package/data'/(stem+'.manifest'))
        am={r['name']:r for r in a['rows']};bm={r['name']:r for r in b['rows']}
        if set(am)!=set(bm):raise ValueError('withdraw_revision_asset_set_changed')
        changed=[]
        for name in sorted(am):
            r,s=am[name],bm[name]
            same=all(r[k]==s[k] for k in ('refs','type_id','instance_id','type_hash','instance_hash','flags'))
            for ext,offset,size in [('bin','binary_offset','binary_size'),('imp','imp_offset','imp_size'),('relo','relo_offset','relo_size')]:
                same=same and a['files'][ext][r[offset]:r[offset]+r[size]]==b['files'][ext][s[offset]:s[offset]+s[size]]
            if not same:changed.append(name)
        if changed!=[expected]:raise ValueError('unreviewed_withdraw_revision')
        streams.append(dict(stream=stem,changed=changed,unchanged_assets=len(am)-1))
        for folder in (old,new):
            for ext in ('manifest','bin','imp','relo'):
                p=folder/'package/data'/(stem+'.'+ext);evidence[str(p.resolve())]=sha(p)
    for folder in (old,new):
        for name in ('build-report.json','TFMacroProbe.big','MacroProbe.xml'):evidence[str((folder/name).resolve())]=sha(folder/name)
    return dict(kind='compiled_single_withdraw_recruitment_revision',old_package_sha256=OLD,package_sha256=NEW,
        streams=streams,regroup_and_reinforce_consumers_preserved=True,original_micro_assets_preserved=True,
        native_execution_granted=False,evidence=evidence)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','candidate','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if out.exists():raise ValueError('fresh_withdraw_revision_audit_required')
    value=evaluate(a.baseline.resolve(),a.candidate.resolve());out.mkdir();shutil.copy2(__file__,out/'auditor.py')
    value['auditor_sha256']=sha(out/'auditor.py');(out/'audit.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k!='evidence'}))
