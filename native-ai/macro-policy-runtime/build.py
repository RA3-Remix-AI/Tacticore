"""Build a fixed-profile macro transport; does not load it or grant capability."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def profile(report,epoch):
    if report.get('variant')!='expanded_macro_policy_v1' or report.get('compiled') is not True:
        raise ValueError('compiled_expanded_macro_policy_required')
    if report.get('commander_id')!='57e668b4-4d89-43bd-bc92-0dd436f046ef' or report.get('player_slot')!=3:
        raise ValueError('explicit_macro_profile_required')
    if type(epoch) is not int or not 1<=epoch<=999:raise ValueError('bounded_macro_runtime_epoch')
    consumers=report['consumers'];flags=list(report['flags'].values())
    if len(flags)!=13 or len(set(flags))!=13 or len(consumers)!=13:
        raise ValueError('macro_flag_set_mismatch')
    if any(not isinstance(flag,str) or re.fullmatch(r'/5TFMacro_57e668b44d8943bdbc920dd436f046ef_P3_[a-z_]+',flag) is None for flag in flags):
        raise ValueError('macro_flag_scope')
    if {row['flag'] for row in consumers}!=set(flags):raise ValueError('macro_consumer_flag_mismatch')
    domains=['construction','production','budget','deployment_policy'];masks=[]
    for domain in domains:
        rows=[r for r in consumers if r.get('domain')==domain or r.get('exclusive_group')==domain]
        masks.append(sum(1<<flags.index(r['flag']) for r in rows))
    if not all(masks):raise ValueError('macro_exclusivity_groups_missing')
    library=f'MacroPolicyV{epoch}.dll';prefix=f'Local\\RA3MacroPolicyV{epoch}_'
    ident=next(a['instance_id'] for a in report['assets'] if a['name'].startswith('AIPersonalityDefinition:'))
    source='#pragma once\nstatic const unsigned FLAG_COUNT=13,PLAYER_SLOT=3,PERSONALITY_ID='+ident+';\n'
    source+='static const char MAPPING_PREFIX[]='+json.dumps(prefix)+';\nstatic const char LIBRARY_NAME[]='+json.dumps(library)+';\n'
    source+='static const char* const FLAG_NAMES[]={'+','.join(json.dumps(flag) for flag in flags)+'};\n'
    source+='static const unsigned EXCLUSIVE_MASKS[]={'+','.join(hex(mask) for mask in masks)+'};\n'
    return source,dict(epoch=epoch,flags=flags,consumers=consumers,exclusive_masks=masks,library=library,mapping_prefix=prefix)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package-report',type=Path,required=True)
    p.add_argument('--epoch',type=int,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    out=args.output.resolve()
    if out.exists() or not out.is_relative_to(HERE/'bin'):raise ValueError('fresh_macro_runtime_build_required')
    report=json.loads(args.package_report.read_text(encoding='utf-8'));source,binding=profile(report,args.epoch)
    big=args.package_report.parent/'TFMacroProbe.big'
    if sha(big)!=report['big_sha256']:raise ValueError('macro_policy_big_changed')
    out.mkdir(parents=True);(out/'profile.h').write_text(source,encoding='ascii')
    compiler=ROOT/'toolchain/w64devkit/bin/i686-w64-mingw32-g++.exe'
    manifest=dict(kind='native_macro_policy_transport_candidate',**binding,package_sha256=report['big_sha256'],
        package_report=str(args.package_report.resolve()),package_report_sha256=sha(args.package_report),
        sources={name:sha(HERE/name) for name in ['shared.h','native.cpp','host.cpp','build.py']},
        profile_header_sha256=sha(out/'profile.h'),compiler_sha256=sha(compiler),
        field_verified=False,capability_granted=False,native_code_patches=0,unit_orders_exposed=False,artifacts={})
    for name,binary,extra in [('native.cpp',binding['library'],['-shared','-Wl,--kill-at']),('host.cpp','macro_policy_host.exe',[])]:
        with (out/(name+'.log')).open('x',encoding='utf-8') as log:
            subprocess.run([str(compiler),'-std=c++17','-O2','-Wall','-Wextra','-Werror','-D_WIN32_WINNT=0x0601',
                '-static-libgcc','-static-libstdc++','-I'+str(out),*extra,str(HERE/name),'-o',str(out/binary),'-luser32'],
                stdout=log,stderr=subprocess.STDOUT,check=True)
        manifest['artifacts'][binary]=sha(out/binary)
    manifest['layout']=json.loads(subprocess.check_output([str(out/'macro_policy_host.exe'),'--layout'],text=True))
    cases={0,1<<len(binding['flags']),*(1<<i for i in range(len(binding['flags'])))}
    for mask in binding['exclusive_masks']:
        bits=[1<<i for i in range(len(binding['flags'])) if mask&(1<<i)]
        cases.update(a|b for i,a in enumerate(bits) for b in bits[i+1:])
    for mask in cases:
        valid=not(mask&~8191) and all(not(mask&group) or not((mask&group)&((mask&group)-1)) for group in binding['exclusive_masks'])
        result=subprocess.run([str(out/'macro_policy_host.exe'),'--validate-mask',str(mask)],check=False)
        if result.returncode!=(0 if valid else 23):raise ValueError('compiled_macro_mask_validation_failed')
    manifest['compiled_mask_cases_passed']=len(cases)
    (out/'build-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),layout=manifest['layout'],compiled_mask_cases_passed=len(cases),artifacts=manifest['artifacts'],field_verified=False)))


if __name__=='__main__':main()
