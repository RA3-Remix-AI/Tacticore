"""Read-only native gate rejection proof, distinct from pre-native exit64.
The native host ran, but this exact mapped request never borrowed an actor.
"""
import ctypes as c,hashlib,json,struct,uuid
from pathlib import Path
import mission_v5_readonly_disposal as d
HERE=Path(__file__).resolve().parent
PROTOCOL='native_gate_no_actor_lease_v1'
COUNTERS='issued_frame returned_frame detach_calls return_calls move_calls attack_calls attack_facade_calls attack_private_calls normal_move_facade_calls normal_move_private_calls stop_calls private_stop_calls toggle_calls toggle_hook_calls'.split()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def eligible(report):
 n=report.get('native',{});return report.get('native_binary_sha256')==d.MISSION_LAYOUT['dll_sha256'] and n.get('phase')==4 and type(n.get('error')) is int and n['error']>0 and n.get('restore_mask')==16383 and n.get('active')==0 and n.get('overflow')==0 and all(n.get(k)==0 for k in COUNTERS) and not any(e.get('tag') in [1,2,3,4,5,6] and e.get('kind') in [10,12,14,16,18,30,32,34,40,52,54] for e in report.get('events',[]))
def snapshot(memory,report,base,runtime):
 layout=d.MISSION_LAYOUT;ptr=memory.u32(base+layout['shared_pointer_rva']);s=runtime.Tactical();block=memory.read(ptr,runtime.Tactical.events.offset);c.memmove(c.addressof(s),block,len(block));ident=lambda field:str(uuid.UUID(bytes=struct.pack('<4I',*getattr(s,field))));pre=report['preflight'];rq=report['request']
 binding=s.magic==0x4d435435 and s.version==13 and s.pid==pre['pid'] and s.thread==s.callback_thread==pre['window_thread'] and s.token==rq['token'] and s.seq==rq['seq'] and ident('session')==report['session_id'] and ident('commander')==pre['commander_id'] and ident('command')==rq['command_id'] and ident('task')==rq['task_id'] and s.unit==int(pre['selected']['address'],0) and s.object_id==pre['selected']['object_id'] and s.owner==int(pre['owner'],0) and s.ai==int(pre['ai'],0) and s.logic==int(pre['logic'],0)
 entries=[dict(address=x['address'],expected=x['expected'],actual=memory.read(x['address'],len(bytes.fromhex(x['expected']))).hex()) for x in d.trusted_entries(report)]
 return dict(binding_verified=bool(binding),module_base=hex(base),shared_pointer=hex(ptr),timer=memory.u32(base+layout['timer_rva']),phase=s.phase,error=s.error,restore_mask=s.restore_mask,active=s.active,token=s.token,seq=s.seq,pid=s.pid,session_id=ident('session'),commander_id=ident('commander'),command_id=ident('command'),task_id=ident('task'),object_id=s.object_id,unit=hex(s.unit),owner=hex(s.owner),ai=hex(s.ai),logic=hex(s.logic),thread=s.thread,callback_thread=s.callback_thread,counters={k:getattr(s,k) for k in COUNTERS},entries=entries)
def verify(evidence,report,source_sha256):
 checks={};pre=report.get('preflight',{});rq=report.get('request',{});snaps=evidence.get('snapshots',[])
 checks['eligible_exact_native_gate']=eligible(report)
 checks['source_binding']=evidence.get('protocol')==PROTOCOL and evidence.get('source_sha256')==source_sha256 and evidence.get('session_id')==report.get('session_id')==pre.get('session_id') and evidence.get('pid')==pre.get('pid') and evidence.get('command_id')==rq.get('command_id') and evidence.get('task_id')==rq.get('task_id') and evidence.get('seq')==rq.get('seq') and evidence.get('token')==rq.get('token') and evidence.get('native_host_exit')==report.get('host_exit')
 expected={x['address']:x['expected'] for x in d.trusted_entries(report)}
 checks['two_native_inert_snapshots']=len(snaps)==2 and all(s.get('binding_verified') is True and s.get('timer')==s.get('active')==0 and s.get('phase')==4 and s.get('error')==report['native'].get('error') and s.get('restore_mask')==16383 and s.get('counters')=={k:0 for k in COUNTERS} and all(s.get(k)==evidence.get(k) for k in ['pid','session_id','command_id','task_id','seq','token']) for s in snaps)
 checks['actor_and_owner_binding']=len(snaps)==2 and all(s.get('commander_id')==pre.get('commander_id') and s.get('object_id')==pre.get('selected',{}).get('object_id') and s.get('unit')==pre.get('selected',{}).get('address') and s.get('owner')==pre.get('owner') and s.get('ai')==pre.get('ai') and s.get('logic')==pre.get('logic') and s.get('thread')==s.get('callback_thread')==pre.get('window_thread') for s in snaps)
 checks['fourteen_exact_entries']=len(expected)==14 and all(len(s.get('entries',[]))==14 and len({x.get('address') for x in s['entries']})==14 and {x.get('address'):x.get('expected') for x in s['entries']}==expected and all(x.get('actual')==expected.get(x.get('address')) for x in s['entries']) for s in snaps)
 checks['no_lease_claim_only']=evidence.get('completed') is False and evidence.get('return_verified') is False and evidence.get('restoration_verified') is False
 ok=all(checks.values());return dict(no_dispatch_verified=ok,no_actor_lease_verified=ok,exclusive_control_never_held=ok,native_host_launched=True,restoration_verified=False,return_verified=False,completion_claim=False,checks=checks,protocol=PROTOCOL)
def collect(report_path,session_path,output=None):
 report_path=Path(report_path).resolve();session_path=Path(session_path);source=report_path.read_bytes();report=json.loads(source.decode('utf-8-sig'));session_raw=session_path.read_bytes();session=json.loads(session_raw.decode('utf-8-sig'))
 if not eligible(report) or report['session_id']!=session['session_id'] or report['preflight']['pid']!=session['pid']:raise ValueError('not_this_session_zero_lease_native_gate')
 output=Path(output) if output else report_path.with_suffix('.native-gate.json')
 if output.exists():return verify_path(output,report_path)
 memory=d.Memory(session['pid'],session)
 try:
  d.verify_session_package(session);runtime=d.runtime('mission-combat-v5');base=d.module_base(memory,HERE/'mission-combat-v5/bin/TacticalMissionCombat5.dll');evidence=dict(protocol=PROTOCOL,source_report=str(report_path),source_sha256=hashlib.sha256(source).hexdigest(),reader_sha256=sha(__file__),session_id=report['session_id'],pid=session['pid'],command_id=report['request']['command_id'],task_id=report['request']['task_id'],seq=report['request']['seq'],token=report['request']['token'],native_host_exit=report.get('host_exit'),snapshots=[snapshot(memory,report,base,runtime)],completed=False,return_verified=False,restoration_verified=False,mutations=False)
  evidence['snapshots'].append(snapshot(memory,report,base,runtime))
  if session_path.read_bytes()!=session_raw or report_path.read_bytes()!=source:raise ValueError('gate_source_or_session_changed')
  evidence['assessment']=verify(evidence,report,evidence['source_sha256']);runtime.durable(output,evidence)
  return dict(evidence['assessment'],evidence_path=str(output),evidence_sha256=sha(output))
 finally:memory.close()
def verify_path(evidence_path,source_report):
 path=Path(evidence_path).resolve();source_report=Path(source_report).resolve();raw=source_report.read_bytes();report=json.loads(raw.decode('utf-8-sig'));evidence=json.loads(path.read_text(encoding='utf-8'))
 if evidence.get('reader_sha256')!=sha(__file__) or Path(evidence.get('source_report','')).resolve()!=source_report:raise ValueError('gate_reader_or_report_binding_changed')
 result=verify(evidence,report,hashlib.sha256(raw).hexdigest());return dict(result,evidence_path=str(path),evidence_sha256=sha(path))
