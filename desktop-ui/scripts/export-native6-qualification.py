"""Verify original lawful-visibility evidence at build time, export data only.

Does not attach a process, start a game/model, grant product acceptance, ship
SDK XML or rewrite original qualification. Original byte pins are mandatory.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as XML

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'integration'))
from host_runtime.native6_paths import plain_local
from host_runtime.native6_runtime_contract import GAME_SHA,PACKAGE_SHA,read,sha,verify_inventory,canonical
from host_runtime.native6_qualification import CAPABILITY_SHA,SAFETY_SHA,PACKAGE_REPORT_SHA,REGISTRY_SHA,COMMANDER


def export(runtime,source_repo,session,visibility,package_report):
    runtime,source_repo,session,visibility,package_report=map(plain_local,(runtime,source_repo,session,visibility,package_report))
    verify_inventory(runtime)
    output=runtime/'qualification'
    if output.exists():raise ValueError('native6_new_qualification_output_required')
    cap_path=visibility/'build-capability.json';safety_path=visibility/'template-safety.json'
    if sha(cap_path)!=CAPABILITY_SHA or sha(safety_path)!=SAFETY_SHA or sha(package_report)!=PACKAGE_REPORT_SHA:
        raise ValueError('native6_original_qualification_pins_changed')
    cap,safety,source_session,package=read(cap_path),read(safety_path),read(session),read(package_report)
    if hashlib.sha256(json.dumps({k:v for k,v in cap.items() if k!='build_id'},sort_keys=True).encode()).hexdigest()!=cap['build_id']:
        raise ValueError('native6_visibility_capability_checksum')
    if (cap['schema_version']!=2 or cap['object_visibility_method']!='native_footprint_reconstruction'
            or cap['kind']!='visibility_build_capability' or len(cap['checks'])!=6 or any(v is not True for v in cap['checks'].values())
            or cap['executable_sha256']!=GAME_SHA or cap['package_sha256']!=PACKAGE_SHA or safety['package_sha256']!=PACKAGE_SHA
            or cap['safety_sha256']!=SAFETY_SHA or safety['detection_verified'] is not False
            or source_session['mod_sha256']!=PACKAGE_SHA or sha(source_session['mod_big'])!=PACKAGE_SHA
            or sha(source_session['game'])!=GAME_SHA or package.get('compiled') is not True
            or package['big_sha256']!=PACKAGE_SHA or package['commander_id']!=COMMANDER):
        raise ValueError('native6_original_visibility_scope_changed')
    registry=plain_local(source_session['registry'])
    if sha(registry)!=REGISTRY_SHA:raise ValueError('native6_original_registry_changed')
    implementation={}
    for name,expected in cap['implementation_sha256'].items():
        original=source_repo/'visibility'/name
        if sha(original)!=expected:raise ValueError('native6_original_visibility_implementation_changed')
        if name=='capability.py':continue
        staged=runtime/'app/visibility'/name
        if original.read_bytes().replace(b'\r\n',b'\n')!=staged.read_bytes().replace(b'\r\n',b'\n'):
            raise ValueError('native6_ported_visibility_algorithm_changed')
        implementation[name]=sha(staged)
    spec=importlib.util.spec_from_file_location('native6_build_time_template_auditor',source_repo/'visibility/audit_templates.py')
    auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)
    sources={}
    for row in safety['templates'].values():
        if row.get('source_audited_no_intrinsic_stealth') is not True or not row.get('source_chain'):
            raise ValueError('native6_unaudited_visibility_template')
        for source in row['source_chain']:
            path=plain_local(source['path']);pin=source['sha256']
            if sha(path)!=pin or str(path) in sources and sources[str(path)]!=pin:
                raise ValueError('native6_visibility_xml_changed')
            nodes=[node for node in XML.parse(path).getroot() if node.tag==auditor.NS+'GameObject']
            if not nodes or any(auditor.audit_node(node) for node in nodes):
                raise ValueError('native6_intrinsic_stealth_not_excluded')
            if sha(path)!=pin:raise ValueError('native6_visibility_xml_changed_during_audit')
            sources[str(path)]=pin
    if sources!=cap['source_sha256'] or not any('capability_' in reason for reason in safety['rejected'].values()):
        raise ValueError('native6_visibility_source_inventory_or_negative_controls')
    for path,expected in cap['evidence'].items():
        if sha(path)!=expected:raise ValueError('native6_original_visibility_evidence_changed')
    cooked_safety=dict(safety,templates={key:{name:value for name,value in row.items() if name!='source_chain'}
                                         for key,row in safety['templates'].items()})
    # Keep only runtime fields. Original path-bearing notes/rejections are not
    # executable evidence and do not belong in an end-user runtime package.
    cooked_safety={key:cooked_safety[key] for key in ('schema_version','package_sha256','compiled_manifest_sha256','source_audit_only',
                   'detection_verified','runtime_invisibility_must_still_be_excluded','templates')}
    cooked_package={key:package[key] for key in ('compiled','big_sha256','commander_id','personality')}
    cooked_package['assets']=[{k:row[k] for k in ('name','instance_id')} for row in package['assets']
                              if row.get('name')=='AIPersonalityDefinition:'+package['personality']]
    if len(cooked_package['assets'])!=1:raise ValueError('native6_compiled_personality_required')
    package_raw=(canonical(cooked_package)+'\n').encode()
    qualification=dict(schema_version=1,kind='native6_bounded_trial_qualification',game_sha256=GAME_SHA,package_sha256=PACKAGE_SHA,
        boundary='native_ai_details_v1',formal_games=0,product_acceptance_verified=False,
        provenance=dict(visibility_capability_sha256=CAPABILITY_SHA,visibility_safety_sha256=SAFETY_SHA,
            package_report_sha256=PACKAGE_REPORT_SHA,registry_sha256=REGISTRY_SHA,
            visibility_evidence_sha256=sorted(cap['evidence'].values()),template_source_sha256=sorted(set(sources.values())),
            exporter_sha256=sha(__file__),evidence_session_id=cap['evidence_session_id']),
        expected_signatures=cap['expected_signatures'],checks=cap['checks'],safety=cooked_safety,
        implementation_sha256=implementation,registry_sha256=REGISTRY_SHA,package_report_sha256=hashlib.sha256(package_raw).hexdigest())
    output.mkdir()
    (output/'registry.json').write_bytes(registry.read_bytes())
    (output/'package.json').write_bytes(package_raw)
    (output/'native6-trial.json').write_text(canonical(qualification)+'\n',encoding='utf-8',newline='\n')
    files={p.relative_to(runtime).as_posix():sha(p) for p in sorted(runtime.rglob('*')) if p.is_file() and p!=runtime/'manifest.json'}
    (runtime/'manifest.json').write_text(canonical(dict(schema_version=1,python='python/python.exe',working_directory='app/integration',files=files))+'\n',encoding='utf-8',newline='\n')
    verify_inventory(runtime)
    return dict(kind='native6_visibility_data_export',templates=len(cooked_safety['templates']),source_xml_audited=len(sources),
                source_xml_copied=False,original_evidence_modified=False,native_process_access=False,formal_games=0,product_acceptance_verified=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('runtime','source-repo','session','visibility','package-report'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();print(json.dumps(export(args.runtime,args.source_repo,args.session,args.visibility,args.package_report)))
