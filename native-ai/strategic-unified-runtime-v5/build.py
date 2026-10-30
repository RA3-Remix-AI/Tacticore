"""Offline frozen manager-only protocol 4 build. No field/product grant."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'native-ai'))
spec=importlib.util.spec_from_file_location('strategic_manager_parent_builder_v4',ROOT/'native-ai/strategic-manager-runtime-v4/build.py')
parent_builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent_builder)
verify_parent=parent_builder.verify

HEADER_SHA='15208d0ded716c8141c0f4aac04b56e7b27bb66fc4bb8b79c61ed132e192abff'
COMPILER_SHA='4f77a5812d96094f6ec565235ab9c2c6acfc7e77b4dc6cea07bf98f3985a7560'
KIND='strategic_unified_transport_v5_candidate'
PARENT_SHA='9e1ca23e7cf8f27f340b21d9dee657b1fce5bd5e0f05c7a8c811baa35972d118'
ACTIONS=['regroup','scout','withdraw','reinforce','budgeteconomy','budgetarmy','budgettech','deployattack','deploydefense','expand']
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True)
def plain(path):
    path=Path(path).absolute()
    if path.resolve()!=path or not path.is_file():raise ValueError('plain_existing_input_required')
    for part in (path,*path.parents):
        if part.is_symlink() or getattr(part.lstat(),'st_file_attributes',0)&0x400:raise ValueError('reparse_input_rejected')
    return path
def assert_pins(pins):
    if any(sha(plain(path))!=expected for path,expected in pins.items()):raise ValueError('manager_input_changed')
def octets(value):return '{'+','.join(str(v) for v in bytes.fromhex(value))+'}'
def wide(path):return 'L'+json.dumps(str(path),ensure_ascii=True)
def profile(pins,package,digest,flags):
    rows=','.join('{'+wide(path)+','+octets(expected)+'}' for path,expected in pins.items())
    return ('#pragma once\n#include <stdint.h>\n#include <wchar.h>\n'
        'static const unsigned HARD_WALL_MS=3600000;\n'
        'static const char* const FLAG_NAMES[]={'+','.join(json.dumps(flag) for flag in flags)+'};\n'
        'struct SourcePin {const wchar_t* path;uint8_t sha[32];};\n'
        'static const SourcePin SOURCE_PINS[]={'+rows+'};\n'
        'static const unsigned SOURCE_PIN_COUNT=sizeof(SOURCE_PINS)/sizeof(SourcePin);\n'
        'static const uint8_t PACKAGE_SHA[32]='+octets(package)+';\n'
        'static const uint8_t SOURCE_SHA[32]='+octets(digest)+';\n'
        'static const wchar_t JOURNAL_ROOT[]='+wide(ROOT/'reports/strategic-unified-native-journal')+';\n'
        'static const wchar_t DEPLOYMENT_ROOT[]='+wide(ROOT.parent/'Mods')[:-1]+'\\\\";\n')

def verify(build):
    build=Path(build).resolve();manifest=json.loads((build/'build-manifest.json').read_bytes())
    if (manifest.get('kind')!=KIND or manifest.get('version')!=5 or manifest.get('field_verified') is not False
        or manifest.get('product_capability_granted') is not False or manifest.get('no_flag_publisher') is not False or manifest.get('admission_ready') is not True or manifest.get('compile_only') is not False or manifest.get('protocol_version')!=5 or manifest.get('actions')!=ACTIONS):raise ValueError('manager_fixed_contract_required')
    pins=manifest['input_pins'];assert_pins(pins)
    parent=Path(manifest['parent']).resolve()
    if sha(parent/'build-manifest.json')!=PARENT_SHA:raise ValueError('unified_qualified_parent_required')
    old=json.loads((parent/'build-manifest.json').read_bytes())
    required=set(old.get('sources',{}))|set(old['input_pins'])|{str(plain(path)) for path in [parent/'build-manifest.json',parent/'profile.h',*(parent/name for name in old['artifacts']),ROOT/'native-ai/strategic_manager_gate_enable_candidate_v2.h',*(HERE/name for name in ('shared.h','native.cpp','host.cpp','flags.h','flag_api.h','client.py','build.py')),ROOT/'toolchain/w64devkit/bin/i686-w64-mingw32-g++.exe',ROOT/'acceptance/run_strategic_manager_field_v4.py',ROOT/'acceptance/run_guarded_strategic_trial_v1.py',ROOT/'acceptance/run_strategic_unified_field_v5.py']}
    if (set(pins)!=required or any(pins[k]!=v for k,v in {**old.get('sources',{}),**old['input_pins']}.items())
        or old.get('version')!=4 or old.get('kind')!='strategic_manager_only_transport_v4_candidate' or manifest['package_sha256']!=old['package_sha256']
        or manifest['flags']!=old['flags'] or set(manifest['artifacts'])!={'StrategicCommanderV5.dll','manager_host.exe'}):raise ValueError('manager_complete_input_inventory_required')
    if hashlib.sha256(canonical(pins).encode()).hexdigest()!=manifest['source_closure_sha256']:raise ValueError('manager_closure_digest')
    if pins.get(str(ROOT/'native-ai/strategic_manager_gate_enable_candidate_v2.h'))!=HEADER_SHA:raise ValueError('manager_reviewed_header_required')
    if pins.get(str(HERE/'build.py'))!=sha(__file__) or pins.get(str(HERE/'client.py'))!=sha(HERE/'client.py'):raise ValueError('manager_loaded_source_changed')
    for name,expected in manifest['artifacts'].items():
        if Path(name).name!=name or sha(plain(build/name))!=expected:raise ValueError('manager_artifact_changed')
    if (build/'profile.h').read_text(encoding='ascii')!=profile(pins,manifest['package_sha256'],manifest['source_closure_sha256'],manifest['flags']):raise ValueError('manager_profile_changed')
    return manifest

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--parent',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--compile-only',action='store_true',help='Offline object/layout/export check; no runtime admission')
    args=parser.parse_args();parent=args.parent.resolve();old=verify_parent(parent);output=args.output.resolve()
    if sha(parent/'build-manifest.json')!=PARENT_SHA:raise ValueError('unified_qualified_parent_required')
    if output.exists() or not output.is_relative_to(ROOT/'native-ai/strategic-runtime-builds'):raise ValueError('fresh_owned_manager_build_required')
    compiler=ROOT/'toolchain/w64devkit/bin/i686-w64-mingw32-g++.exe'
    if sha(compiler)!=COMPILER_SHA:raise ValueError('fixed_compiler_required')
    pins={**old.get('sources',{}),**old['input_pins']}
    for path in [parent/'build-manifest.json',parent/'profile.h',*(parent/name for name in old['artifacts']),ROOT/'native-ai/strategic_manager_gate_enable_candidate_v2.h',*(HERE/name for name in ('shared.h','native.cpp','host.cpp','flags.h','flag_api.h','client.py','build.py')),compiler,ROOT/'acceptance/run_strategic_manager_field_v4.py',ROOT/'acceptance/run_guarded_strategic_trial_v1.py',ROOT/'acceptance/run_strategic_unified_field_v5.py']:pins[str(plain(path))]=sha(path)
    if len(pins)>158:raise ValueError('bounded_native_input_count')
    if sha(ROOT/'native-ai/strategic_manager_gate_enable_candidate_v2.h')!=HEADER_SHA:raise ValueError('reviewed_header_changed')
    assert_pins(pins);digest=hashlib.sha256(canonical(pins).encode()).hexdigest()
    output.mkdir();(ROOT/'reports/strategic-unified-native-journal').mkdir(exist_ok=True)
    for name in ('shared.h','native.cpp','host.cpp','flags.h','flag_api.h'):shutil.copy2(HERE/name,output/name)
    shutil.copy2(ROOT/'native-ai/strategic_manager_gate_enable_candidate_v2.h',output/'strategic_manager_gate_enable_candidate_v2.h')
    (output/'profile.h').write_text(profile(pins,old['package_sha256'],digest,old['flags']),encoding='ascii')
    commands=[]
    for source,target,extra in [('native.cpp','StrategicCommanderV5.dll',['-shared','-Wl,--kill-at','-ladvapi32']),('host.cpp','manager_host.exe',[])]:
        command=[str(compiler),'-std=c++17','-D_WIN32_WINNT=0x0601','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-static-libgcc','-static-libstdc++',str(output/source),'-o',str(output/target),*extra]
        result=subprocess.run(command,capture_output=True,text=True);(output/(target+'.compile.log')).write_text(result.stdout+result.stderr,encoding='utf8');commands.append(command)
        if result.returncode:raise ValueError('manager_compile_failed:'+result.stderr[:3000])
    layout=json.loads(subprocess.check_output([str(output/'manager_host.exe'),'--layout'],text=True))
    subprocess.run([str(output/'manager_host.exe'),'--check-export'],check=True)
    compiled_masks=json.loads(subprocess.check_output([str(output/'manager_host.exe'),'--all-masks'],text=True))
    expected_masks=[mask for mask in range(1026) if not mask&~1023 and (mask&0x70).bit_count()<=1 and (mask&0x38f).bit_count()<=1]
    if compiled_masks!=expected_masks:raise ValueError('unified_compiled_masks_mismatch')
    assert_pins(pins)
    manifest=dict(admission_ready=not args.compile_only,compile_only=args.compile_only,actions=ACTIONS,kind=KIND,version=5,protocol_version=5,no_flag_publisher=False,input_pins=pins,source_closure_sha256=digest,
        parent=str(parent),package_sha256=old['package_sha256'],package_report=old['package_report'],flags=old['flags'],
        artifacts={name:sha(output/name) for name in ('StrategicCommanderV5.dll','manager_host.exe')},layout=layout,
        commands=commands,compiled_mask_cases=1026,field_verified=False,product_capability_granted=False,formal_games=0)
    (output/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    if not args.compile_only:verify(output)
    print(json.dumps(dict(output=str(output),layout=layout,input_files=len(pins),native_calls=0,field_verified=False)))

if __name__=='__main__':main()
