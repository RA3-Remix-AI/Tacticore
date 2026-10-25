"""Pure RPM proof: a pinned MFM2/MFM3 request launched but borrowed neither actor."""
import ctypes as c,hashlib,importlib.util,json,re,struct,sys,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent
PROTOCOL='native_gate_no_actor_lease_v1'
FRONT='issued_frame returned_frame detach_calls return_calls move_calls attack_calls attack_facade_calls attack_private_calls stop_calls private_stop_calls toggle_calls toggle_hook_calls return_verified'.split()
SUPPORT='detach_calls return_calls returned move_calls stop_calls private_stop_calls'.split()

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def profile(report):
 for directory,version in [('mission-formation-v3',3)]:
  path=HERE/directory;dll=path/'bin'/('TacticalMissionFormation'+str(version)+'.dll')
  if dll.exists() and report.get('native_binary_sha256')==sha(dll):
   q=load('gate_formation_q_'+str(version),path/'formation_mission_qualification_v4.py')
   if not q.source_pins(report):raise ValueError('formation_gate_source_changed')
   layout=json.loads((path/'inert-layout.json').read_text());return dict(directory=directory,version=version,path=path,dll=dll,layout=layout,magic=0x4d464d30+version)
 raise ValueError('unsupported_formation_gate_revision')

def entries(report):
 p=profile(report);block=(p['path']/'lease.cpp').read_text().split('static Hook hooks[]={',1)[1].split(';',1)[0]
 rows=[dict(address=int(a,0),expected=e.replace('\\x','')) for a,e,n in re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)",(\d+),',block)]
 if len(rows)!=13 or len({x['address'] for x in rows})!=13:raise ValueError('formation_gate_hook_table')
 return rows

def eligible(report):
 try:profile(report)
 except (ValueError,OSError,KeyError):return False
 n=report.get('native',{});return n.get('phase')==4 and type(n.get('error')) is int and n['error']>0 and n.get('restore_mask')==8191 and n.get('active')==0 and n.get('overflow')==0 and all(n.get(k)==0 for k in FRONT) and all(n.get('support',{}).get(k)==0 for k in SUPPORT) and not any(e.get('tag') in [1,2,3,4,5,6] for e in report.get('events',[]))

def snapshot(memory,report,base,runtime):
 p=profile(report);ptr=memory.u32(base+p['layout']['shared_pointer_rva']);n=runtime.Tactical();data=memory.read(ptr,runtime.Tactical.events.offset);c.memmove(c.addressof(n),data,len(data));ident=lambda f:str(uuid.UUID(bytes=struct.pack('<4I',*getattr(n,f))));pre=report['preflight'];rq=report['request']
 bound=n.magic==p['magic'] and n.version==p['version'] and n.pid==pre['pid'] and n.thread==n.callback_thread==pre['window_thread'] and n.token==rq['token'] and n.seq==rq['seq'] and ident('session')==report['session_id'] and ident('commander')==pre['commander_id'] and ident('command')==rq['command_id'] and ident('task')==rq['task_id'] and n.unit==int(pre['selected']['address'],0) and n.object_id==pre['selected']['object_id'] and n.support.thing==int(pre['support']['address'],0) and n.support.id==pre['support']['object_id'] and n.owner==int(pre['owner'],0) and n.ai==int(pre['ai'],0) and n.logic==int(pre['logic'],0)
 return dict(binding_verified=bool(bound),module_base=hex(base),shared_pointer=hex(ptr),timer=memory.u32(base+p['layout']['timer_rva']),phase=n.phase,error=n.error,restore_mask=n.restore_mask,active=n.active,pid=n.pid,session_id=ident('session'),commander_id=ident('commander'),command_id=ident('command'),task_id=ident('task'),seq=n.seq,token=n.token,object_ids=[n.object_id,n.support.id],units=[hex(n.unit),hex(n.support.thing)],owner=hex(n.owner),ai=hex(n.ai),logic=hex(n.logic),thread=n.thread,callback_thread=n.callback_thread,front={k:getattr(n,k) for k in FRONT},support={k:getattr(n.support,k) for k in SUPPORT},entries=[dict(x,actual=memory.read(x['address'],len(bytes.fromhex(x['expected']))).hex()) for x in entries(report)])

def verify(evidence,report,source_sha256):
 pre=report.get('preflight',{});rq=report.get('request',{});snaps=evidence.get('snapshots',[]);checks=dict(eligible_exact_native_gate=eligible(report))
 expected={x['address']:x['expected'] for x in entries(report)};binding=dict(pid=pre['pid'],session_id=report['session_id'],commander_id=pre['commander_id'],command_id=rq['command_id'],task_id=rq['task_id'],seq=rq['seq'],token=rq['token'])
 checks['source_binding']=evidence.get('protocol')==PROTOCOL and evidence.get('source_sha256')==source_sha256 and all(evidence.get(k)==v for k,v in binding.items()) and evidence.get('native_host_exit')==report.get('host_exit')
 checks['two_native_inert_snapshots']=len(snaps)==2 and all(x.get('binding_verified') is True and x.get('timer')==x.get('active')==0 and x.get('phase')==4 and x.get('error')==report['native']['error'] and x.get('restore_mask')==8191 and x.get('front')=={k:0 for k in FRONT} and x.get('support')=={k:0 for k in SUPPORT} and all(x.get(k)==v for k,v in binding.items()) for x in snaps)
 checks['both_actors_owner_thread']=len(snaps)==2 and all(x.get('object_ids')==[pre['selected']['object_id'],pre['support']['object_id']] and x.get('units')==[pre['selected']['address'],pre['support']['address']] and all(x.get(k)==pre[k] for k in ['owner','ai','logic']) and x.get('thread')==x.get('callback_thread')==pre['window_thread'] for x in snaps)
 checks['thirteen_exact_entries']=all(len(x.get('entries',[]))==13 and len({e.get('address') for e in x['entries']})==13 and {e.get('address'):e.get('expected') for e in x['entries']}==expected and all(e.get('actual')==expected.get(e.get('address')) for e in x['entries']) for x in snaps)
 checks['stable_mapping']=len(snaps)==2 and snaps[0].get('shared_pointer')==snaps[1].get('shared_pointer') and snaps[0].get('module_base')==snaps[1].get('module_base')
 checks['no_completion_or_return_claim']=evidence.get('mutations') is False and evidence.get('completed') is False and evidence.get('return_verified') is False and evidence.get('restoration_verified') is False
 ok=all(checks.values());return dict(no_dispatch_verified=ok,no_actor_lease_verified=ok,exclusive_control_never_held=ok,native_host_launched=True,restoration_verified=False,return_verified=False,completion_claim=False,checks=checks,protocol=PROTOCOL)

def collect(report_path,session_path,output=None):
 report_path=Path(report_path).resolve();source=report_path.read_bytes();report=json.loads(source.decode('utf-8-sig'));session_path=Path(session_path);session_raw=session_path.read_bytes();session=json.loads(session_raw.decode('utf-8-sig'))
 if not eligible(report) or report['session_id']!=session['session_id'] or report['preflight']['pid']!=session['pid']:raise ValueError('not_this_formation_zero_lease_gate')
 output=Path(output) if output else report_path.with_suffix('.native-gate.json')
 if output.exists():return verify_path(output,report_path)
 p=profile(report);runtime=load('formation_gate_runtime_'+str(p['version']),p['path']/'lease_admission_v4.py');reader=load('formation_gate_module_lookup',HERE/'readonly_disposal.py');memory=runtime.b.Memory(session['pid'],session)
 try:
  from session_package import verify_session_package
  verify_session_package(session);base=reader.module_base(memory,p['dll']);rq=report['request'];evidence=dict(protocol=PROTOCOL,source_report=str(report_path),source_sha256=hashlib.sha256(source).hexdigest(),reader_sha256=sha(__file__),session_id=report['session_id'],pid=session['pid'],commander_id=report['preflight']['commander_id'],command_id=rq['command_id'],task_id=rq['task_id'],seq=rq['seq'],token=rq['token'],native_host_exit=report.get('host_exit'),snapshots=[snapshot(memory,report,base,runtime)],completed=False,return_verified=False,restoration_verified=False,mutations=False)
  evidence['snapshots'].append(snapshot(memory,report,base,runtime))
  if session_path.read_bytes()!=session_raw or report_path.read_bytes()!=source:raise ValueError('formation_gate_source_or_session_changed')
  evidence['assessment']=verify(evidence,report,evidence['source_sha256']);runtime.b.durable(output,evidence);return dict(evidence['assessment'],evidence_path=str(output),evidence_sha256=sha(output))
 finally:memory.close()

def verify_path(sidecar,raw):
 path=Path(sidecar).resolve();report_path=Path(raw).resolve();source=report_path.read_bytes();report=json.loads(source.decode('utf-8-sig'));e=json.loads(path.read_text(encoding='utf-8-sig'))
 if e.get('reader_sha256')!=sha(__file__) or Path(e.get('source_report','')).resolve()!=report_path:raise ValueError('formation_gate_reader_or_source_binding')
 return dict(verify(e,report,hashlib.sha256(source).hexdigest()),evidence_path=str(path),evidence_sha256=sha(path))
