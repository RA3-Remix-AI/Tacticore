"""Offline protocol-2 candidate build; compilation never grants field capability."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import struct
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'native-ai'))
from macro_expansion_contract import validate_expansion_profile

PROTOCOL_VERSION=2
MAX_REQUESTS=2048
HARD_WALL_MS=3600000
MAX_HOST_WALL_SECONDS=3540
SOURCES=('shared.h','native.cpp','host.cpp','build.py','client.py')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def profile(report,epoch):
    contract=validate_expansion_profile(report)
    if type(epoch) is not int or not 1<=epoch<=999:raise ValueError('bounded_macro_runtime_epoch')
    personalities=[a['instance_id'] for a in report['assets'] if a['name'].startswith('AIPersonalityDefinition:')]
    if len(personalities)!=1:raise ValueError('macro_expansion_personality_required')
    ident=int(personalities[0],0)
    if ident!=0x799613e0:raise ValueError('macro_expansion_personality_changed')
    library=f'MacroPolicy2V{epoch}.dll'
    prefix=f'Local\\RA3MacroPolicy2V{epoch}_'
    source='#pragma once\n'
    source+='static const unsigned PROTOCOL_VERSION=2,FLAG_COUNT=20,PLAYER_SLOT=3,PERSONALITY_ID='+hex(ident)+';\n'
    source+=f'static const unsigned KNOWN_MASK={hex(contract["known_mask"])},MAX_REQUESTS={MAX_REQUESTS},HARD_WALL_MS={HARD_WALL_MS};\n'
    source+='static const char MAPPING_PREFIX[]='+json.dumps(prefix)+';\nstatic const char LIBRARY_NAME[]='+json.dumps(library)+';\n'
    source+='static const char* const FLAG_NAMES[]={'+','.join(json.dumps(flag) for flag in contract['flags'])+'};\n'
    source+='static const unsigned EXCLUSIVE_MASKS[]={'+','.join(hex(mask) for mask in contract['exclusive_masks'])+'};\n'
    return source,dict(epoch=epoch,protocol_version=2,flags=contract['flags'],consumers=contract['consumers'],
        exclusive_masks=contract['exclusive_masks'],library=library,mapping_prefix=prefix,profile_contract=contract,
        maximum_requests=MAX_REQUESTS,absolute_native_wall_ms=HARD_WALL_MS,maximum_host_wall_seconds=MAX_HOST_WALL_SECONDS,
        heartbeat_loss_ms=5000,same_process_reattach_supported=False)

def checked_file(path):
    path=Path(path)
    if (not path.is_absolute() or str(path).startswith('\\') or not path.is_file()
            or path.resolve()!=path):raise ValueError('macro_expansion_audit_path_invalid')
    for item in (path,*path.parents):
        if item.is_symlink() or getattr(item.lstat(),'st_file_attributes',0)&0x400:
            raise ValueError('macro_expansion_audit_path_invalid')
    return path

def object_file(path):
    def pairs(items):
        value={}
        for key,item in items:
            if key in value:raise ValueError('macro_expansion_audit_duplicate_key')
            value[key]=item
        return value
    def constant(_):raise ValueError('macro_expansion_audit_nonfinite')
    raw=checked_file(path).read_bytes()
    if len(raw)>1024*1024:raise ValueError('macro_expansion_audit_too_large')
    value=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=constant)
    if type(value) is not dict:raise ValueError('macro_expansion_audit_object_required')
    return value

def unpack_entry(raw,expected):
    """Bounded RefPack decoding; command layout follows the existing SDK helper.

    The loose file length is the allocation bound. No numpy/image/reference
    application is imported, and malformed backreferences never use slicing
    semantics to synthesize missing bytes.
    """
    if not 0<=expected<=128*1024*1024:raise ValueError('macro_expansion_big_entry_size')
    if len(raw)<2 or raw[1]!=0xfb or (raw[0]&0x7e)!=0x10:
        if len(raw)!=expected:raise ValueError('macro_expansion_big_entry_size')
        return raw
    width=4 if raw[0]&0x80 else 3;position=2+width*(2 if raw[0]&1 else 1)
    if len(raw)<position or int.from_bytes(raw[2:2+width],'big')!=expected:
        raise ValueError('macro_expansion_big_refpack_header')
    out=bytearray();done=False
    while position<len(raw):
        control=raw[position];position+=1;length=0;distance=0
        extra=1 if control<0x80 else 2 if control<0xc0 else 3 if control<0xe0 else 0
        if position+extra>len(raw):raise ValueError('macro_expansion_big_refpack_truncated')
        if control<0x80:
            value=raw[position];position+=1;literal=control&3
            length=((control>>2)&7)+3;distance=((control&0x60)<<3)+value+1
        elif control<0xc0:
            a,b=raw[position:position+2];position+=2;literal=a>>6
            length=(control&0x3f)+4;distance=((a&0x3f)<<8)+b+1
        elif control<0xe0:
            a,b,d=raw[position:position+3];position+=3;literal=control&3
            length=((control&12)<<6)+d+5;distance=((control&16)<<12)+(a<<8)+b+1
        elif control<0xfc:literal=((control&31)<<2)+4
        else:literal=control&3;done=True
        if position+literal>len(raw) or len(out)+literal+length>expected:
            raise ValueError('macro_expansion_big_refpack_truncated')
        out.extend(raw[position:position+literal]);position+=literal
        if length:
            if not 1<=distance<=len(out):raise ValueError('macro_expansion_big_refpack_distance')
            start=len(out)-distance
            if length<=distance:out.extend(out[start:start+length])
            else:out.extend((out[start:]*((length+distance-1)//distance))[:length])
        if done:break
    if not done or position!=len(raw) or len(out)!=expected:
        raise ValueError('macro_expansion_big_refpack_size')
    return bytes(out)

def verify_archive(directory):
    """Tie every embedded BIG entry to the exact loose input audited below."""
    directory=Path(directory)
    archive_path=checked_file(directory/'TFMacroProbe.big')
    if not 16<=archive_path.stat().st_size<=256*1024*1024:
        raise ValueError('macro_expansion_big_header')
    raw=archive_path.read_bytes()
    if raw[:4]!=b'BIG4' or struct.unpack_from('<I',raw,4)[0]!=len(raw):
        raise ValueError('macro_expansion_big_header')
    count,index_end=struct.unpack_from('>II',raw,8)
    if not 1<=count<=4096 or not 16<=index_end<=len(raw):raise ValueError('macro_expansion_big_index')
    entries={};intervals=[];position=16
    for _ in range(count):
        if position+9>index_end:raise ValueError('macro_expansion_big_index')
        offset,size=struct.unpack_from('>II',raw,position);position+=8
        try:
            end=raw.index(0,position,min(index_end,position+1025));name=raw[position:end].decode('ascii')
        except (ValueError,UnicodeError):raise ValueError('macro_expansion_big_entry_name') from None
        position=end+1;name=name.replace('\\','/').lower();parts=name.split('/')
        if (not name or ':' in name or any(part in ('','.','..','additionalmaps') for part in parts)
                or name in entries):raise ValueError('macro_expansion_big_entry_name')
        if offset<index_end or size>128*1024*1024 or offset+size>len(raw):
            raise ValueError('macro_expansion_big_entry_bounds')
        entries[name]=(offset,size)
        if size:intervals.append((offset,offset+size))
    if raw[position:index_end] not in (b'',b'L219\x00\x00\x00\x00'):
        raise ValueError('macro_expansion_big_index')
    intervals.sort()
    if any(a[1]>b[0] for a,b in zip(intervals,intervals[1:])):raise ValueError('macro_expansion_big_entry_overlap')
    allowed={'data/gamestrings.csf'}|{'data/'+stem+'.'+ext for stem in ('mod','mod_m','mod_l')
                                    for ext in ('manifest','bin','imp','relo')}
    if set(entries)!=allowed:raise ValueError('macro_expansion_big_entry_set')
    for name,(offset,size) in entries.items():
        target=checked_file(directory/'package'/name)
        decoded=unpack_entry(raw[offset:offset+size],target.stat().st_size)
        if hashlib.sha256(decoded).hexdigest()!=sha(target):raise ValueError('macro_expansion_big_loose_mismatch')

def verify_inputs(report,path):
    """Replay actual compiled streams, not just self-reported preservation booleans."""
    validate_expansion_profile(report)
    path=Path(path).resolve();candidate=path.parent
    if sha(checked_file(candidate/'TFMacroProbe.big'))!=report['big_sha256']:raise ValueError('macro_policy_big_changed')
    audit_path=checked_file(candidate/'compiled-expansion-audit.json')
    if sha(audit_path)!=report['compiled_expansion_audit_sha256']:raise ValueError('macro_expansion_compiled_audit_changed')
    if sha(ROOT/'native-ai/macro_expansion_contract.py')!=report['contract_source_sha256']:
        raise ValueError('macro_expansion_contract_changed')
    if sha(ROOT/'native-ai/stage_macro_expansion.py')!=report['source_sha256']:
        raise ValueError('macro_expansion_generator_changed')
    audit=object_file(audit_path)
    required={'kind','baseline_package_sha256','package_sha256','streams','evidence',
              'qualified_consumer_semantics_preserved','original_micro_assets_preserved','field_verified','capability_granted'}
    if (set(audit)!=required or audit['kind']!='compiled_append_only_macro_expansion_audit'
            or audit['package_sha256']!=report['big_sha256']
            or audit['qualified_consumer_semantics_preserved'] is not True
            or audit['original_micro_assets_preserved'] is not True
            or audit['field_verified'] is not False or audit['capability_granted'] is not False):
        raise ValueError('macro_expansion_audit_package_or_scope_mismatch')
    streams=audit['streams']
    if (type(streams) is not list or len(streams)!=3 or any(type(row) is not dict for row in streams)
            or [row.get('stream') for row in streams]!=['mod','mod_M','mod_L']):
        raise ValueError('macro_expansion_audit_stream_set')
    evidence=audit['evidence']
    if type(evidence) is not dict or len(evidence)!=24:raise ValueError('macro_expansion_audit_evidence_set')
    paths={}
    for name,digest in evidence.items():
        if type(name) is not str or type(digest) is not str or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('macro_expansion_audit_evidence_pin')
        item=Path(name)
        if (not item.is_absolute() or item.parent.name!='data' or item.parent.parent.name!='package'
                or item.name.lower() not in {stem+'.'+ext for stem in ('mod','mod_m','mod_l') for ext in ('manifest','bin','imp','relo')}
                or item in paths):raise ValueError('macro_expansion_audit_evidence_set')
        paths[item]=digest
    roots={item.parents[2] for item in paths}
    if len(roots)!=2 or candidate not in roots:raise ValueError('macro_expansion_audit_candidate_root')
    baseline=next(root for root in roots if root!=candidate)
    expected={root/'package/data'/(stem+'.'+ext) for root in roots
              for stem in ('mod','mod_M','mod_L') for ext in ('manifest','bin','imp','relo')}
    if set(paths)!=expected:raise ValueError('macro_expansion_audit_evidence_set')
    for item,digest in paths.items():
        if sha(checked_file(item))!=digest:raise ValueError('macro_expansion_audit_evidence_changed')
    original=object_file(baseline/'build-report.json')
    if (original.get('variant')!='expanded_macro_policy_v1' or original.get('compiled') is not True
            or original.get('group_roles_candidate_revision')!=2
            or original.get('consumers')!=report.get('legacy_consumer_definitions')
            or original.get('big_sha256')!=audit['baseline_package_sha256']
            or sha(checked_file(baseline/'TFMacroProbe.big'))!=audit['baseline_package_sha256']):
        raise ValueError('macro_expansion_audit_baseline_mismatch')
    verify_archive(baseline)
    verify_archive(candidate)
    stage=importlib.import_module('stage_macro_expansion')
    if Path(stage.__file__).resolve()!=ROOT/'native-ai/stage_macro_expansion.py':
        raise ValueError('macro_expansion_auditor_origin')
    actual=stage.audit_compiled_expansion(baseline,candidate,report)
    canonical=lambda value:json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    if canonical(actual)!=canonical(audit):raise ValueError('macro_expansion_compiled_audit_replay_mismatch')
    return audit_path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-report',type=Path,required=True)
    parser.add_argument('--epoch',type=int)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--verify-inputs-only',action='store_true',help='Read-only package and compiled audit replay; no build, deployment or game access')
    args=parser.parse_args()
    if args.verify_inputs_only:
        if args.epoch is not None or args.output is not None:parser.error('verification does not accept epoch or output')
        report=object_file(args.package_report.resolve());profile(report,1)
        verify_inputs(report,args.package_report)
        print(json.dumps(dict(package_verified=True,compiled_audit_replayed=True,field_verified=False,capability_granted=False)));return
    if args.epoch is None or args.output is None:parser.error('compilation requires epoch and output')
    out=args.output.resolve()
    if out.exists() or not out.is_relative_to(HERE/'bin'):raise ValueError('fresh_macro_v2_build_required')
    raw=args.package_report.read_bytes();report=json.loads(raw.decode('utf8'))
    source,binding=profile(report,args.epoch);audit_path=verify_inputs(report,args.package_report)
    compiler=ROOT/'toolchain/w64devkit/bin/i686-w64-mingw32-g++.exe'
    inputs={name:sha(HERE/name) for name in SOURCES}
    out.mkdir(parents=True);(out/'profile.h').write_text(source,encoding='ascii')
    manifest=dict(kind='native_macro_policy_transport_v2_candidate',**binding,package_sha256=report['big_sha256'],
        package_report=str(args.package_report.resolve()),package_report_sha256=hashlib.sha256(raw).hexdigest(),
        profile_contract_sha256=sha(ROOT/'native-ai/macro_expansion_contract.py'),
        compiled_expansion_audit_sha256=sha(audit_path),sources=inputs,
        profile_header_sha256=sha(out/'profile.h'),compiler_sha256=sha(compiler),
        field_verified=False,capability_granted=False,native_code_patches=0,unit_orders_exposed=False,artifacts={})
    for name,binary,extra in [('native.cpp',binding['library'],['-shared','-Wl,--kill-at']),('host.cpp','macro_policy_host.exe',[])]:
        with (out/(name+'.log')).open('x',encoding='utf8') as log:
            subprocess.run([str(compiler),'-std=c++17','-O2','-Wall','-Wextra','-Werror','-D_WIN32_WINNT=0x0601',
                '-static-libgcc','-static-libstdc++','-I'+str(out),*extra,str(HERE/name),'-o',str(out/binary),'-luser32'],
                stdout=log,stderr=subprocess.STDOUT,check=True)
        manifest['artifacts'][binary]=sha(out/binary)
    manifest['layout']=json.loads(subprocess.check_output([str(out/'macro_policy_host.exe'),'--layout'],text=True))
    cases={0,1<<20,0xffffffff,*(1<<i for i in range(20))}
    cases.update((1<<i)|(1<<j) for i in range(20) for j in range(i+1,20))
    for mask in cases:
        valid=not(mask&~binding['profile_contract']['known_mask']) and all(not(mask&g) or not((mask&g)&((mask&g)-1)) for g in binding['exclusive_masks'])
        result=subprocess.run([str(out/'macro_policy_host.exe'),'--validate-mask',str(mask)],check=False)
        if result.returncode!=(0 if valid else 23):raise ValueError('compiled_macro_v2_mask_validation_failed')
    if any(sha(HERE/name)!=digest for name,digest in inputs.items()):raise ValueError('macro_v2_source_changed_during_build')
    manifest['compiled_mask_cases_passed']=len(cases)
    (out/'build-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(output=str(out),protocol_version=2,layout=manifest['layout'],compiled_mask_cases_passed=len(cases),
        artifacts=manifest['artifacts'],field_verified=False,capability_granted=False)))

if __name__=='__main__':main()
