"""Fixed ten-intent next-candidate transport; no field/product authority.

The complete source/input closure is frozen before compiled-field validation.
Old build manifests are historical records and cannot acquire this revision.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
NATIVE=ROOT/'native-ai/macro-policy-runtime-v2'
ENTRY_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
from strategic_source_closure_v1 import (SourceClosure,PackageClosure,source_paths,plain,
    strict_json,canonical,sha,REPORT_SHA,PACKAGE_SHA,KIND as CLOSURE_KIND)

KIND='native_strategic_flag_transport_v1_candidate'
VERSION=3
BUILD_REVISION=2
COMMANDER='57e668b4-4d89-43bd-bc92-0dd436f046ef'
STRATEGIC=('regroup','scout','withdraw','reinforce','budgeteconomy','budgetarmy',
           'budgettech','deployattack','deploydefense','expand')
LIBRARY='StrategicPolicyV1.dll'
PREFIX='Local\\RA3StrategicPolicyV1_'
NAME_PREFIX='5TFMacro_57e668b44d8943bdbc920dd436f046ef_P3'
SUFFIXES=('build_airfield','scout','buildtech','economyrefinery','budgeteconomy',
          'budgetarmy','budgettech','deployattack','deploydefense','expand')
STATE_NAMES=('RegroupHome','Scout','WithdrawHome','ReinforceBase','BudgetEconomy',
             'BudgetArmy','BudgetTech','DeployAttack','DeployDefense','StockExpansionPreference')
EXACT_FLAGS=tuple('/'+NAME_PREFIX+'_'+name for name in SUFFIXES)
EXACT_STATES=tuple(('AIBudgetStateDefinition:' if 4<=index<=6 else 'AIStrategicStateDefinition:')+
                  NAME_PREFIX+'_'+name for index,name in enumerate(STATE_NAMES))
LAYOUT=dict(size=128,request=48,error=64,mask=112,heartbeat=104)


def load(path):return strict_json(plain(path).read_bytes())


def profile(report):
    if (type(report) is not dict or report.get('variant')!='strategic_stock_expansion_candidate_v1'
            or report.get('compiled') is not True or report.get('commander_id')!=COMMANDER
            or type(report.get('player_slot')) is not int or report['player_slot']!=3
            or report.get('strategic_actions')!=list(STRATEGIC)
            or type(report.get('flag_count')) is not int or report['flag_count']!=10
            or report.get('product_capability_granted') is not False or report.get('expansion_field_verified') is not False):
        raise ValueError('fixed_strategic_candidate_required')
    consumers=report.get('consumers')
    if (type(consumers) is not list or len(consumers)!=10 or any(type(row) is not dict for row in consumers)
            or tuple(row.get('action') for row in consumers)!=STRATEGIC
            or tuple(row.get('flag') for row in consumers)!=EXACT_FLAGS
            or tuple(row.get('state') for row in consumers)!=EXACT_STATES
            or report.get('flags')!=dict(zip(SUFFIXES,EXACT_FLAGS))
            or any(row.get('field_verified') is not False or row.get('capability_granted') is not False for row in consumers)):
        raise ValueError('strategic_consumer_identity')
    if (type(report.get('transport_known_mask')) is not int or report['transport_known_mask']!=1023
            or report.get('transport_exclusive_masks')!=[0x70,0x38f]):raise ValueError('strategic_mask_contract')
    expansion=consumers[-1]
    semantics=dict(stock_source_state='SovietExpansion_MEDIUM',native_tactic='SimpleExpansion',
        target_policy='original_native_expansion_target_selection',native_micro_manager='ExpansionMicroManager',
        details_owner='native_ai',additional_preference_only=True,removes_native_conditions=False,
        release_cancels_committed_work=False,release_blocks_autonomous_expansion=False)
    if any(type(expansion.get(key)) is not type(value) or expansion[key]!=value for key,value in semantics.items()):
        raise ValueError('strategic_expansion_semantics')
    header=('#pragma once\nstatic const unsigned PROTOCOL_VERSION=3,FLAG_COUNT=10,PLAYER_SLOT=3,PERSONALITY_ID=0x799613e0;\n'
        'static const unsigned KNOWN_MASK=1023,MAX_REQUESTS=2048,HARD_WALL_MS=600000;\n'
        'static const char MAPPING_PREFIX[]='+json.dumps(PREFIX)+';\n'
        'static const char LIBRARY_NAME[]='+json.dumps(LIBRARY)+';\n'
        'static const char* const FLAG_NAMES[]={'+','.join(json.dumps(flag) for flag in EXACT_FLAGS)+'};\n'
        'static const unsigned EXCLUSIVE_MASKS[]={0x70,0x38f};\n')
    return header,dict(protocol_version=VERSION,flags=list(EXACT_FLAGS),actions=list(STRATEGIC),
        known_mask=1023,exclusive_masks=[0x70,0x38f],library=LIBRARY,mapping_prefix=PREFIX,
        maximum_host_wall_seconds=540,heartbeat_loss_ms=5000,same_process_reattach_supported=False)


def _fixed_report(path):
    raw=plain(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=REPORT_SHA:raise ValueError('strategic_fixed_report_required')
    report=strict_json(raw);profile(report);return report


def action_mask(actions,manifest):
    if (type(actions) is not list or len(actions)>2 or any(type(action) is not str or action not in STRATEGIC for action in actions)
            or len(set(actions))!=len(actions) or type(manifest) is not dict or manifest.get('kind')!=KIND
            or manifest.get('source_closure_kind')!=CLOSURE_KIND or manifest.get('build_contract_revision')!=BUILD_REVISION):
        raise ValueError('strategic_actions_invalid')
    sources=SourceClosure(ENTRY_SHA,expected=manifest.get('sources'))
    _,expected=profile(_fixed_report(manifest['package_report']))
    if any(manifest.get(key)!=value for key,value in expected.items()):raise ValueError('strategic_manifest_profile_changed')
    mask=sum(1<<STRATEGIC.index(action) for action in actions)
    if any((part:=mask&group) and part&(part-1) for group in (0x70,0x38f)):raise ValueError('conflicting_strategic_actions')
    sources.check();return mask


def verify_package(path):
    sources=SourceClosure(ENTRY_SHA)
    package=PackageClosure(path,sources)
    try:profile(package.report);package.finish();return package.report
    finally:package.close()


def _check_header(package,directory,expected):
    package.check()
    if plain(directory/'profile.h').read_bytes()!=expected or (directory/'profile.h.gch').exists():
        raise ValueError('strategic_profile_header_changed')


def _copy_rows(sources,package,directory,header):
    return [*sources.raw.items(),(str(package.report_path),package.raw_report),(str(directory/'profile.h'),header)]


def _verify_copies(manifest,sources,package,directory,header):
    expected=_copy_rows(sources,package,directory,header);rows=manifest.get('source_copies')
    if type(rows) is not list or len(rows)!=len(expected):raise ValueError('strategic_source_copy_set')
    for index,(row,(path,raw)) in enumerate(zip(rows,expected)):
        name=str(index)+'-'+Path(path).name;digest=hashlib.sha256(raw).hexdigest()
        if row!=dict(path=path,copy=name,sha256=digest) or sha(plain(directory/'source'/name))!=digest:
            raise ValueError('strategic_source_copy_changed')


def verify_build(directory):
    directory=Path(directory).absolute();manifest_path=plain(directory/'build-manifest.json')
    manifest_raw=manifest_path.read_bytes();manifest=strict_json(manifest_raw)
    if (type(manifest) is not dict or manifest.get('kind')!=KIND or manifest.get('capability_granted') is not False
            or manifest.get('field_verified') is not False or manifest.get('source_closure_kind')!=CLOSURE_KIND
            or type(manifest.get('build_contract_revision')) is not int or manifest['build_contract_revision']!=BUILD_REVISION):
        raise ValueError('strategic_next_source_closure_required')
    sources=SourceClosure(ENTRY_SHA,expected=manifest.get('sources'))
    package=PackageClosure(manifest['package_report'],sources,expected_inputs=manifest.get('input_pins'))
    try:
        header,binding=profile(package.report);raw_header=header.encode('ascii')
        if any(manifest.get(key)!=value for key,value in binding.items()):raise ValueError('strategic_generated_profile_mismatch')
        if (manifest.get('package_report_sha256')!=REPORT_SHA or manifest.get('package_sha256')!=PACKAGE_SHA
                or manifest.get('compiler_sha256')!=package.compiler_sha256 or manifest.get('layout')!=LAYOUT
                or type(manifest.get('compiled_mask_cases_passed')) is not int or manifest['compiled_mask_cases_passed']!=1026):
            raise ValueError('strategic_build_evidence_binding')
        _check_header(package,directory,raw_header)
        if manifest.get('profile_header_sha256')!=hashlib.sha256(raw_header).hexdigest():raise ValueError('strategic_header_hash')
        if (type(manifest.get('artifacts')) is not dict or set(manifest['artifacts'])!={LIBRARY,'macro_policy_host.exe'}
                or any(sha(plain(directory/name))!=digest for name,digest in manifest['artifacts'].items())):
            raise ValueError('strategic_transport_binary_changed')
        _verify_copies(manifest,sources,package,directory,raw_header)
        validation=package.finish()
        if canonical(manifest.get('compiled_validation'))!=canonical(validation):raise ValueError('strategic_compiled_receipt_changed')
        if manifest_path.read_bytes()!=manifest_raw:raise ValueError('strategic_manifest_changed')
        _check_header(package,directory,raw_header);return manifest
    finally:package.close()


def build_transport(report_path,output):
    output=Path(output).resolve()
    if output.exists() or not output.is_relative_to(ROOT/'native-ai/strategic-runtime-builds'):
        raise ValueError('fresh_owned_strategic_build_required')
    sources=SourceClosure(ENTRY_SHA);package=PackageClosure(report_path,sources)
    try:
        header,binding=profile(package.report);raw_header=header.encode('ascii')
        output.mkdir(parents=True);(output/'profile.h').write_bytes(raw_header);artifacts={}
        for name,binary,extra in [('native.cpp',LIBRARY,['-shared','-Wl,--kill-at']),('host.cpp','macro_policy_host.exe',[])]:
            _check_header(package,output,raw_header)
            with (output/(name+'.log')).open('x',encoding='utf8') as log:
                subprocess.run([str(package.compiler),'-std=c++17','-O2','-Wall','-Wextra','-Werror','-D_WIN32_WINNT=0x0601',
                    '-static-libgcc','-static-libstdc++','-I'+str(output),*extra,str(NATIVE/name),'-o',str(output/binary),'-luser32'],
                    stdout=log,stderr=subprocess.STDOUT,check=True)
            _check_header(package,output,raw_header);artifacts[binary]=sha(output/binary)
        layout=json.loads(subprocess.check_output([str(output/'macro_policy_host.exe'),'--layout'],text=True))
        if layout!=LAYOUT:raise ValueError('strategic_compiled_layout_changed')
        for mask in (*range(1024),1024,0xffffffff):
            valid=not mask&~1023 and all(not(part:=mask&group) or not part&(part-1) for group in binding['exclusive_masks'])
            checked=subprocess.run([str(output/'macro_policy_host.exe'),'--validate-mask',str(mask)])
            if checked.returncode!=(0 if valid else 23):raise ValueError('strategic_compiled_mask_mismatch')
        _check_header(package,output,raw_header);validation=package.finish()
        archive=output/'source';archive.mkdir();copies=[]
        for index,(path,raw) in enumerate(_copy_rows(sources,package,output,raw_header)):
            name=str(index)+'-'+Path(path).name;(archive/name).write_bytes(raw)
            copies.append(dict(path=path,copy=name,sha256=hashlib.sha256(raw).hexdigest()))
        manifest=dict(kind=KIND,**binding,source_closure_kind=CLOSURE_KIND,build_contract_revision=BUILD_REVISION,
            package_report=str(package.report_path),package_report_sha256=REPORT_SHA,package_sha256=PACKAGE_SHA,
            sources=sources.pins,input_pins=package.input_pins,source_copies=copies,compiled_validation=validation,
            artifacts=artifacts,layout=layout,profile_header_sha256=hashlib.sha256(raw_header).hexdigest(),
            compiler_sha256=package.compiler_sha256,compiled_mask_cases_passed=1026,
            native_code_patches=0,transport_attached=False,field_verified=False,capability_granted=False)
        _verify_copies(manifest,sources,package,output,raw_header);_check_header(package,output,raw_header)
        if any(sha(output/name)!=digest for name,digest in artifacts.items()):raise ValueError('strategic_artifact_changed')
        (output/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
        return dict(output=str(output),protocol_version=VERSION,mask_cases=1026,field_verified=False,capability_granted=False)
    finally:package.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--package-report',type=Path,required=True)
    parser.add_argument('--output',type=Path);parser.add_argument('--verify-inputs-only',action='store_true');args=parser.parse_args()
    if args.verify_inputs_only:
        if args.output is not None:parser.error('read-only verification does not accept output')
        verify_package(args.package_report);print(json.dumps(dict(package_verified=True,compiled=False,field_verified=False)))
    else:
        if args.output is None:parser.error('build requires output')
        print(json.dumps(build_transport(args.package_report,args.output)))


if __name__=='__main__':main()
