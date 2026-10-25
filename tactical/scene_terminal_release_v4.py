"""Strict read-only scene-closure release for current MCT7 and verified formation revisions.

An ended scene releases exclusivity. It never proves actor return, physical
retreat, a goal, a kill, or mission completion. No target memory is written and
no native host, hook, SDK command, debugger, GUI or model endpoint is used.
"""
import argparse,ctypes as c,hashlib,json,re,struct,time,uuid
from datetime import datetime
from pathlib import Path
P=Path(__file__).resolve().parent
EXE='ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
EXE_PATH=Path('E:/RedRar3/Data/RA3_1.12.game')
PROTOCOL='scene_terminal_release_v4'
COMMON={k:i*4 for i,k in enumerate('magic version pid thread owner ai personality personality_id player_template start_low start_high'.split())}
COMMON.update(session=44,commander=60,command=76,task=92,token=108,seq=112,unit=116,object_id=120,type_hash=124,update=128,logic=132,phase=260,error=276,active=268,restore_mask=280,callback_thread=284,issued_frame=288,returned_frame=292,detach_calls=300,return_calls=304,return_verified=344,overflow=340)
PROFILES={
 'mission-combat-v7':dict(dll='TacticalMissionCombat7.dll',binary='c5100e55662609dd5549289b3653500b420aa3d4bc4fda6c4d4d7f434842cadf',host='20ede705bc3a0d360fcc817c3eae15b709b37d6b9805477b4a78c87ebbd92b7c',cpp='c2b8fa479b54252602f692b0ad4100285e4ea59ab304949e84f3422146dfca17',shared='7bb35b2f6e47c49e181ff9a85245dd1cff8b227f585e79a29db081a4fad02b1d',layout_sha='12a12e1803d6ccf3855975076e215fc90f69a21513aec8f054e48c733e9807a0',magic=0x4d435437,version=15,mask=16383,hooks=14,header=1124,timer_rva=90784,pointer_rva=90800),
 'mission-formation-v4':dict(dll='TacticalMissionFormation4.dll',binary='1421d30446aa27712654b269edea52fcbe4abf5913e027bd1b45ffd230d948a4',host='2487f693f7ac71a746335258a019674243df36abe02ab7297474ef282758b531',cpp='0bbec35b24a695b3240e0e87758b5ba0b0d893fef86bfc98c53a0b7431d4feaf',shared='8cdd01fc082a4f0b9ccb05770a0d83de2bbdee7f8e11799e90e619c11bedb53d',layout_sha='096e3894074a1f77b0205bce4eab6e76e76eee04f6a42c84c8aa2c548ac13e2a',magic=0x4d464d34,version=4,mask=8191,hooks=13,header=1052,timer_rva=103032,pointer_rva=103048),
 'mission-formation-v5':{'dll': 'TacticalMissionFormation5.dll', 'binary': '6896a11b3a3b621239db910a7159217d732c07b4dfdfd1691a19ae4aca4bd613', 'host': 'dfed29b15ccc141deaf7480f284eb1c33e4c95150ebfeb5af4d5d5100789f5ad', 'cpp': 'ececdff20572c79990e852b403064a92a270e4e65e16dce343ba87b531796ae0', 'shared': 'd4c55df8ad421ceff8e56f23af751218c8952449bbf89d35aed39b2f96cc80c9', 'layout_sha': 'c90ddfc61b86dd14e647800588885972ecfea8b0a79b06ef629a864ed94ed916', 'magic': 1296452917, 'version': 5, 'mask': 8191, 'hooks': 13, 'header': 27900, 'timer_rva': 107256, 'pointer_rva': 107272},
 'mission-formation-v6':{'dll': 'TacticalMissionFormation6.dll', 'binary': 'e3bf3613b2d1677e3e85d8f2193340f746885662c6c66ec9395efc64dda9353e', 'host': '9e8e4effbb3ad9b105be96c6ed75819484b420926efd980418df079a1f7e0e1a', 'cpp': 'd9996f8a533b2537dd79e14b664f80d99a2f13404810c0270db36a9dc541cfad', 'shared': '4b1bb2882c6d20a1eaa32dd4dbe3e17912fcf589d1fce08ecd805b21934d27b4', 'layout_sha': '465a01b2b8fb4a96aec316f6d124845308754d34b1037cb7e4395af379ab667b', 'magic': 1296452918, 'version': 6, 'mask': 8191, 'hooks': 13, 'header': 27900, 'timer_rva': 111352, 'pointer_rva': 111368},
 'mission-formation-v7':{'dll': 'TacticalMissionFormation7.dll', 'binary': '53b7523699918b495a7e3dbf173e015fdf8b0793e81fb916bed92b6ace7405d7', 'host': 'b88830e5c2942257b2e4c015d7e5a4527d136a5e4f87927f22a2614120cdedee', 'cpp': 'fb6351a5b6342ba24f81cc35c0307b87c4ea7daa67100c643e5f5e234e06e4f7', 'shared': '74be230c7de2a9be917b84137ef31eabfc97c3d6be02a870d8a650e8c238391a', 'layout_sha': '7a307f2d22c8b1de3e95fd3c92ece2742cd84b191b5b75292c3e617de9089c60', 'magic': 1296452919, 'version': 7, 'mask': 8191, 'hooks': 13, 'header': 27900, 'timer_rva': 111352, 'pointer_rva': 111368}
}
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def num(x):return int(x,0) if isinstance(x,str) else x
def profile(report):
 matches=[(name,p) for name,p in PROFILES.items() if report.get('native_binary_sha256')==p['binary']]
 if len(matches)!=1:raise ValueError('scene_release_unsupported_binary')
 name,p=matches[0];folder=P/name
 for file,expected in [(folder/'bin'/p['dll'],p['binary']),(folder/'bin/tactical_host.exe',p['host']),(folder/'lease.cpp',p['cpp']),(folder/'shared.h',p['shared']),(folder/'inert-layout.json',p['layout_sha'])]:
  if sha(file)!=expected:raise ValueError('scene_release_profile_drift')
 if report.get('native_host_sha256')!=p['host'] or report.get('executable_sha256')!=EXE:raise ValueError('scene_release_source_revision')
 return name,p
def expected_entries(report):
 name,p=profile(report);source=(P/name/'lease.cpp').read_text().split('static Hook hooks[]={',1)[1].split(';',1)[0]
 entries=[dict(address=int(a,0),expected=b.replace('\\x','')) for a,b in re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)"',source)]
 if len(entries)!=p['hooks'] or len({e['address'] for e in entries})!=p['hooks']:raise ValueError('scene_hook_set')
 return entries
def pe_bytes(path,address,n):
 data=Path(path).read_bytes();pe=struct.unpack_from('<I',data,0x3c)[0];count=struct.unpack_from('<H',data,pe+6)[0];optional=pe+24;size=struct.unpack_from('<H',data,pe+20)[0];base=struct.unpack_from('<I',data,optional+28)[0];rva=address-base
 for i in range(count):
  at=optional+size+i*40;virtual_size,virtual,raw_size,raw=struct.unpack_from('<4I',data,at+8)
  if virtual<=rva and rva+n<=virtual+raw_size:return data[raw+rva-virtual:raw+rva-virtual+n]
 raise ValueError('scene_hook_not_file_backed')
def raw_binding(report):
 pre=report.get('preflight',{});rq=report.get('request',{});n=report.get('native',{})
 return report.get('status')=='finished' and n.get('phase')==4 and n.get('error')==31 and n.get('active')==0 and n.get('overflow')==0 and type(n.get('issued_frame')) is int and n['issued_frame']>0 and n.get('session_id')==report.get('session_id')==pre.get('session_id') and n.get('commander_id')==pre.get('commander_id') and all(n.get(k)==rq.get(k) for k in ['command_id','task_id','seq']) and type(rq.get('seq')) is int and rq['seq']>0
def decode(block,name):
 result={k:struct.unpack_from('<I',block,v)[0] for k,v in COMMON.items() if k not in ['session','commander','command','task']}
 for key in ['session','commander','command','task']:result[key]=str(uuid.UUID(bytes=block[COMMON[key]:COMMON[key]+16]))
 if name in ('mission-formation-v4','mission-formation-v5','mission-formation-v6','mission-formation-v7'):result['support']={key:struct.unpack_from('<I',block,484+offset)[0] for key,offset in [('thing',0),('id',4),('hash',8),('update',12),('detach_calls',20),('return_calls',24),('returned',28)]}
 return result
def scene(memory,logic,owner):
 return dict(global_logic=memory.u32(0xcd8ce4),logic_vtable=memory.u32(logic),frame=memory.u32(logic+0x50),live_head=memory.u32(logic+0xb4),mode=memory.u32(logic+0x148),paused_raw=memory.u32(logic+0x15c),owner_vtable=memory.u32(owner),owner_index=memory.u32(owner+0x20),owner_ai=memory.u32(owner+0x90))
def read_bounded_exact(memory,address,length):
 if type(length) is not int or not 0<length<=1024*1024:raise ValueError('scene_header_read_size')
 parts=[]
 for offset in range(0,length,0x2000):
  amount=min(0x2000,length-offset);data=memory.read(address+offset,amount)
  if len(data)!=amount:raise ValueError('scene_short_header_read')
  parts.append(data)
 return b''.join(parts)
def snapshot(memory,report,base):
 name,p=profile(report);pre=report['preflight'];logic=num(pre['logic']);owner=num(pre['owner']);pointer=memory.u32(base+p['pointer_rva']);raw_a=read_bounded_exact(memory,pointer,p['header']);a=decode(raw_a,name);world_a=scene(memory,logic,owner);timer=memory.u32(base+p['timer_rva'])
 entries=[dict(e,actual=memory.read(e['address'],len(bytes.fromhex(e['expected']))).hex()) for e in expected_entries(report)]
 world_b=scene(memory,logic,owner);raw_b=read_bounded_exact(memory,pointer,p['header']);b=decode(raw_b,name);after_pointer=memory.u32(base+p['pointer_rva']);after_timer=memory.u32(base+p['timer_rva'])
 return dict(module_base=base,shared_pointer=pointer,shared_pointer_after=after_pointer,timer=timer,timer_after=after_timer,native_before=a,native_after=b,header_before_hex=raw_a.hex(),header_after_hex=raw_b.hex(),scene_before=world_a,scene_after=world_b,entries=entries,observed_monotonic_ns=time.monotonic_ns())
def _verify(record,report,source_sha256):
 checks={};name,p=profile(report);pre=report.get('preflight',{});rq=report.get('request',{});n=report.get('native',{});samples=record.get('snapshots',[]);entries={e['address']:e['expected'] for e in expected_entries(report)};session=record.get('session',{})
 checks['source_and_reader']=record.get('protocol')==PROTOCOL and record.get('source_sha256')==source_sha256 and record.get('reader_sha256')==sha(__file__) and record.get('directory')==name and record.get('native_binary_sha256')==p['binary'] and record.get('mutations') is False
 checks['terminal_scene_error_only']=raw_binding(report) and n.get('restore_mask')==p['mask']
 checks['session_package_start']=record.get('pid')==session.get('pid')==pre.get('pid') and record.get('session_id')==session.get('session_id')==report.get('session_id') and session.get('mod_sha256')==report.get('package_sha256') and record.get('process_executable_sha256')==EXE and record.get('session_start_time')==session.get('start_time')
 try:checks['actual_process_start']=abs((record['process_start_filetime']-116444736000000000)/1e7-datetime.fromisoformat(session['start_time']).timestamp())<.001
 except (TypeError,ValueError,KeyError):checks['actual_process_start']=False
 checks['two_distinct_readonly_samples']=len(samples)==2 and all(type(s.get('observed_monotonic_ns')) is int for s in samples) and 100_000_000<=samples[1]['observed_monotonic_ns']-samples[0]['observed_monotonic_ns']<=5_000_000_000
 checks['collection_complete']=not record.get('collection_error_type')
 checks['one_actual_native_channel']=len(samples)==2 and type(samples[0].get('module_base')) is int and samples[0]['module_base']>=0x10000 and samples[0]['module_base']==samples[1].get('module_base') and samples[0].get('shared_pointer')==samples[1].get('shared_pointer')
 checks['same_native_request']=len(samples)==2;checks['actual_inert']=len(samples)==2;checks['actual_exact_hook_bytes']=len(samples)==2;checks['actual_closed_scene_not_live_pause']=len(samples)==2
 for s in samples:
  header_a=bytes.fromhex(s.get('header_before_hex',''));header_b=bytes.fromhex(s.get('header_after_hex',''));header_ok=len(header_a)==len(header_b)==p['header'] and header_a==header_b and decode(header_a,name)==s.get('native_before') and decode(header_b,name)==s.get('native_after');checks['same_native_request'] &= header_ok
  a=s.get('native_before',{});b=s.get('native_after',{});checks['same_native_request'] &= a==b and all(a.get(k)==v for k,v in dict(magic=p['magic'],version=p['version'],pid=pre.get('pid'),thread=pre.get('window_thread'),callback_thread=pre.get('window_thread'),owner=num(pre.get('owner',0)),ai=num(pre.get('ai',0)),logic=num(pre.get('logic',0)),personality=num(pre.get('personality',0)),personality_id=num(pre.get('personality_id',0)),unit=num(pre.get('selected',{}).get('address',0)),object_id=pre.get('selected',{}).get('object_id'),type_hash=num(pre.get('selected',{}).get('type_hash',0)),update=num(pre.get('selected',{}).get('ai_address',0)),session=report.get('session_id'),commander=pre.get('commander_id'),command=rq.get('command_id'),task=rq.get('task_id'),seq=rq.get('seq'),token=rq.get('token')).items())
  checks['same_native_request'] &= a.get('player_template')==num(pre.get('player_template',0)) and ((a.get('start_high',0)<<32)|a.get('start_low',0))==record.get('process_start_filetime') and all(a.get(k)==n.get(k) for k in ['issued_frame','returned_frame','detach_calls','return_calls','return_verified'])
  if name in ('mission-formation-v4','mission-formation-v5','mission-formation-v6','mission-formation-v7'):
   support=pre.get('support',{});actual=a.get('support',{});raw_support=n.get('support',{});checks['same_native_request'] &= all(actual.get(k)==v for k,v in dict(thing=num(support.get('address',0)),id=support.get('object_id'),hash=num(support.get('type_hash',0)),update=num(support.get('ai_address',0))).items()) and all(actual.get(k)==raw_support.get(k) for k in ['detach_calls','return_calls','returned'])
  checks['actual_inert'] &= s.get('timer')==s.get('timer_after')==0 and s.get('shared_pointer')==s.get('shared_pointer_after') and type(s.get('shared_pointer')) is int and s['shared_pointer']>=0x10000 and a.get('phase')==4 and a.get('error')==31 and a.get('active')==a.get('overflow')==0 and a.get('restore_mask')==p['mask']
  rows=s.get('entries',[]);checks['actual_exact_hook_bytes'] &= len(rows)==len({x.get('address') for x in rows})==p['hooks'] and {e.get('address'):e.get('actual') for e in rows}==entries and all(e.get('actual')==e.get('expected') for e in rows)
  world=s.get('scene_before',{});checks['actual_closed_scene_not_live_pause'] &= world==s.get('scene_after') and world.get('global_logic')==num(pre.get('logic',0)) and world.get('logic_vtable')==0xbeb630 and world.get('frame')==0 and world.get('live_head')==0 and world.get('mode')==9 and world.get('owner_vtable')==0xc5bce0 and world.get('owner_index')==3 and world.get('owner_ai')==0
 checks['pristine_matches_real_exe']=sha(EXE_PATH)==EXE and all(pe_bytes(EXE_PATH,a,len(bytes.fromhex(v))).hex()==v for a,v in entries.items())
 checks['never_claim_return_or_completion']=record.get('return_verified') is False and record.get('completed') is False and record.get('goal_observed') is False
 ok=all(v is True for v in checks.values());return dict(protocol=PROTOCOL,status='scene_disposed_exclusive_control_released' if ok else 'not_verified',checks=checks,scene_disposed_verified=ok,scene_disposed_control_release=ok,control_release_verified=ok,restoration_verified=False,return_verified=False,physical_retreat_verified=False,completed=False,goal_observed=False,completion_claim=False,semantics='scene_disposed_exclusive_control_released' if ok else 'unknown')
def verify(record,report,source_sha256):
 try:return _verify(record,report,source_sha256)
 except (OSError,ValueError,TypeError,KeyError,OverflowError,AttributeError):return dict(protocol=PROTOCOL,status='not_verified',checks={'well_formed_supported_scene_evidence':False},scene_disposed_verified=False,scene_disposed_control_release=False,control_release_verified=False,restoration_verified=False,return_verified=False,physical_retreat_verified=False,completed=False,goal_observed=False,completion_claim=False,semantics='unknown')
def module_base(memory,path):
 from ctypes import wintypes as w
 api=c.WinDLL('psapi',use_last_error=True);api.EnumProcessModulesEx.argtypes=[w.HANDLE,c.POINTER(w.HMODULE),w.DWORD,c.POINTER(w.DWORD),w.DWORD];api.EnumProcessModulesEx.restype=w.BOOL;api.GetModuleFileNameExW.argtypes=[w.HANDLE,w.HMODULE,w.LPWSTR,w.DWORD];api.GetModuleFileNameExW.restype=w.DWORD
 mods=(w.HMODULE*1024)();needed=w.DWORD()
 if not api.EnumProcessModulesEx(memory.handle,mods,c.sizeof(mods),c.byref(needed),3) or needed.value>c.sizeof(mods):raise ValueError('module_inventory')
 found=[]
 for mod in mods[:needed.value//c.sizeof(w.HMODULE)]:
  text=c.create_unicode_buffer(32768)
  if not api.GetModuleFileNameExW(memory.handle,mod,text,len(text)):raise ValueError('module_path')
  if Path(text.value).resolve()==path.resolve():found.append(int(mod))
 if len(found)!=1:raise ValueError('exact_scene_dll_unavailable')
 return found[0]
def collect(report_path,session_path,output=None):
 import sys
 sys.path.insert(0,str(P.parent/'production'))
 from observe_production import Memory,k
 from ctypes import wintypes as w
 from session_package import verify_session_package
 report_path=Path(report_path).resolve();raw=report_path.read_bytes();r=json.loads(raw.decode('utf-8-sig'));name,p=profile(r);session=json.loads(Path(session_path).read_text(encoding='utf-8-sig'))
 if not raw_binding(r) or session.get('session_id')!=r['session_id'] or session.get('pid')!=r['preflight']['pid']:raise ValueError('not_this_ended_scene_request')
 verify_session_package(session);output=Path(output) if output else report_path.with_name(report_path.stem+'-scene-terminal-release.json')
 if output.exists():raise ValueError('existing_scene_release_preserved')
 memory=Memory(session['pid'],session);record=dict(protocol=PROTOCOL,directory=name,source_report=str(report_path),source_sha256=hashlib.sha256(raw).hexdigest(),native_binary_sha256=p['binary'],reader_sha256=sha(__file__),session=session,session_start_time=session['start_time'],session_id=session['session_id'],pid=session['pid'],process_executable_sha256=sha(memory.path),return_verified=False,completed=False,goal_observed=False,mutations=False,snapshots=[])
 try:
  times=[w.FILETIME() for _ in range(4)]
  if not k.GetProcessTimes(memory.handle,*[c.byref(x) for x in times]):raise ValueError('process_creation_time_unavailable')
  record['process_start_filetime']=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime;base=module_base(memory,P/name/'bin'/p['dll'])
  for index in range(2):
   record['snapshots'].append(snapshot(memory,r,base))
   if not index:time.sleep(.15)
 except Exception as error:record['collection_error_type']=type(error).__name__
 finally:memory.close()
 result=verify(record,r,record['source_sha256']);record['assessment']=result
 with output.open('x',encoding='utf-8') as f:json.dump(record,f,indent=2,allow_nan=False)
 return dict(result,sidecar_path=str(output.resolve()),sidecar_sha256=sha(output),source_sha256=record['source_sha256'])
def verify_path(sidecar_path,report_path):
 sidecar_path=Path(sidecar_path);report_path=Path(report_path);raw=report_path.read_bytes();record=json.loads(sidecar_path.read_text(encoding='utf-8-sig'));r=json.loads(raw.decode('utf-8-sig'));return dict(verify(record,r,hashlib.sha256(raw).hexdigest()),sidecar_path=str(sidecar_path.resolve()),sidecar_sha256=sha(sidecar_path),source_sha256=hashlib.sha256(raw).hexdigest())
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('report',type=Path);parser.add_argument('--session',type=Path);parser.add_argument('--output',type=Path);parser.add_argument('--verify',type=Path);args=parser.parse_args()
 print(json.dumps(verify_path(args.verify,args.report) if args.verify else collect(args.report,args.session,args.output),indent=2))
