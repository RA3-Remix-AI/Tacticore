"""Derive visibility build evidence only for independently verified AI-only appends.

Original native visibility code, every original compiled asset/dependency and
source allowlist must remain identical. This does not repeat old field trials or
grant native execution. All comparison inputs and outputs remain local.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT.parent/'native-ai')]
from capability import verify_build,sha,load
from build_commander_package import big_entries,unpack_refpack,read_stream,payload

ALLOWED_ADDITIONS={'AIBuildStateDefinition','AIStrategicStateDefinition','AIPersonalityDefinition','AIBudgetStateDefinition','AITargetingHeuristic'}


def compare(base,current):
    if base['header'][0]!=current['header'][0] or base['header'][2]!=current['header'][2]:
        raise ValueError('visibility_append_stream_layout')
    if len(current['rows'])<=len(base['rows']) or base['manifest_refs']!=current['manifest_refs']:
        raise ValueError('visibility_append_dependencies_or_count')
    for before,after in zip(base['rows'],current['rows']):
        for field in ['name','source','type_id','instance_id','type_hash','instance_hash','refs','flags']:
            if before[field]!=after[field]:raise ValueError('visibility_append_original_metadata_changed')
        for ext in ['bin','imp','relo']:
            if payload(base,before,ext)!=payload(current,after,ext):
                raise ValueError('visibility_append_original_payload_changed')
    keys={(r['type_id'],r['instance_id']) for r in base['rows']}
    added=[]
    for row in current['rows'][len(base['rows']):]:
        key=row['type_id'],row['instance_id']
        if key in keys or row['name'].split(':',1)[0] not in ALLOWED_ADDITIONS:
            raise ValueError('visibility_append_requires_unique_ai_only_assets')
        keys.add(key);added.append(row['name'])
    return dict(original_assets_preserved=len(base['rows']),added_ai_assets=added,
        original_payloads_imports_relocations_and_references_equal=True,external_dependencies_equal=True)


def extract(big,target):
    entries={}
    for name,compressed in big_entries(big):
        name=name.replace('\\','/');path=(target/name).resolve()
        if not path.is_relative_to(target.resolve()) or name.lower() in entries:
            raise ValueError('visibility_append_unsafe_archive')
        raw=unpack_refpack(compressed);entries[name.lower()]=hashlib.sha256(raw).hexdigest()
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    return entries


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--session',required=True,type=Path)
    p.add_argument('--macro-package-report',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    args=p.parse_args();session=load(args.session);report=load(args.macro_package_report)
    out=args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT.parent/'reports'):
        raise ValueError('fresh_local_visibility_derivation_required')
    if report.get('kind')!='isolated_native_macro_probe' or report.get('big_sha256')!=session['mod_sha256'] or sha(session['mod_big'])!=session['mod_sha256']:
        raise ValueError('visibility_append_exact_macro_package')
    base=Path(report['baseline_big'])
    if sha(base)!=report['baseline_big_sha256']:raise ValueError('visibility_append_baseline_changed')
    cap,safety=verify_build(dict(session,mod_sha256=report['baseline_big_sha256'],mod_big=str(base)))
    out.mkdir(parents=True)
    old_entries=extract(base,out/'baseline');new_entries=extract(Path(session['mod_big']),out/'current')
    if set(old_entries)!=set(new_entries):raise ValueError('visibility_append_archive_entry_set_changed')
    streams=[]
    for stem in ['mod','mod_M','mod_L']:
        relative='data/'+stem+'.manifest'
        before=read_stream(out/'baseline'/relative);after=read_stream(out/'current'/relative)
        streams.append(dict(stem=stem,**compare(before,after)))
    allowed={'data/gamestrings.csf'}|{'data/'+stem.lower()+'.'+ext for stem in ['mod','mod_M','mod_L'] for ext in ['manifest','bin','imp','relo']}
    if any(old_entries[name]!=new_entries[name] for name in old_entries if name not in allowed):
        raise ValueError('visibility_append_unrelated_archive_change')
    new_safety=copy.deepcopy(safety);new_safety['package_sha256']=session['mod_sha256']
    new_safety['compiled_manifest_sha256']=sha(out/'current/data/mod.manifest')
    safety_path=out/'template-safety.json'
    safety_path.write_text(json.dumps(new_safety,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    evidence=dict(kind='visibility_ai_only_append_derivation',base_package_sha256=report['baseline_big_sha256'],
        current_package_sha256=session['mod_sha256'],base_build_id=cap['build_id'],streams=streams,
        old_field_trials_repeated=False,native_execution_granted=False,
        inputs={str(path.resolve()):sha(path) for path in [args.session,args.macro_package_report,Path(__file__)]})
    evidence_path=out/'derivation.json';evidence_path.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    derived=copy.deepcopy(cap);derived.pop('build_id')
    derived.update(package_sha256=session['mod_sha256'],safety_sha256=sha(safety_path),
        compiled_manifest_sha256=new_safety['compiled_manifest_sha256'],
        append_only_derivation=dict(base_build_id=cap['build_id'],evidence_sha256=sha(evidence_path)))
    derived['evidence'][str(evidence_path)]=sha(evidence_path)
    derived['build_id']=hashlib.sha256(json.dumps(derived,sort_keys=True).encode()).hexdigest()
    cap_path=out/'build-capability.json';cap_path.write_text(json.dumps(derived,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    verify_build(session,cap_path,safety_path)
    print(json.dumps(dict(output=str(out),derived_build_id=derived['build_id'],streams=streams,
        old_field_trials_repeated=False,native_execution_granted=False)))


if __name__=='__main__':main()
