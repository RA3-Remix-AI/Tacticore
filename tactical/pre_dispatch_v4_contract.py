"""Pre-native rejection protocol. No game calls, mappings, UI, or model access.

Exit64 is emitted only before the durable native launch-intent boundary. A child
which may have launched a native host can never attest that it held no units.
"""
import hashlib,json,os,re,time,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent
EXE='ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
PROTOCOL='pre_native_launch_v1';REJECT_EXIT=64
DLLS={'mission-combat-v4':'TacticalMissionCombat4.dll'}
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def atomic(path,record,owned=False):
 path=Path(path)
 if path.exists() and not owned:raise ValueError('existing_report_requires_recovery')
 temp=path.with_name(path.name+'.pending-'+uuid.uuid4().hex)
 with temp.open('x',encoding='utf-8') as f:json.dump(record,f,ensure_ascii=False,allow_nan=False,indent=2);f.flush();os.fsync(f.fileno())
 for attempt in range(25):
  try:temp.replace(path);return
  except PermissionError:
   if attempt==24:raise
   time.sleep(.02)
def rejection(args,directory,error,*,owned=False):
 """Only call when the wrapper's launch-intent flag is still false."""
 directory=Path(directory).resolve();name=directory.name
 if name not in DLLS or not args.output or not args.command_id or not args.task_id or type(args.seq) is not int or args.seq<1:raise ValueError('cannot_attest_unbound_pre_dispatch')
 command=str(uuid.UUID(args.command_id));task=str(uuid.UUID(args.task_id));session=json.loads(Path(args.session).read_text(encoding='utf-8-sig'));path=Path(args.output)
 object_ids=[args.object_id] if name=='mission-combat-v4' else [args.front_id,args.support_id]
 if any(type(x) is not int or x<1 for x in object_ids):raise ValueError('cannot_attest_unbound_actors')
 if path.exists():
  if not owned:raise ValueError('existing_report_requires_recovery')
  record=json.loads(path.read_text(encoding='utf-8'));request=record.get('request',{})
  if request.get('command_id')!=command or request.get('task_id')!=task or request.get('seq')!=args.seq:raise ValueError('existing_report_binding_mismatch')
 else:record={}
 reason=str(error) if isinstance(error,ValueError) and re.fullmatch('[a-zA-Z0-9_]{1,100}',str(error)) else 'wrapper_preflight_error'
 record.update(status='no_dispatch_rejected',session_id=session['session_id'],executable_sha256=EXE,package_sha256=session['mod_sha256'],native_binary_sha256=sha(directory/'bin'/DLLS[name]),native_host_sha256=sha(directory/'bin/tactical_host.exe'),wrapper_sha256=sha(directory/'lease.py'),pre_dispatch_helper_sha256=sha(__file__),host_exit=None,native_launch_intent_persisted=False,pre_dispatch=dict(protocol=PROTOCOL,stage='pre_native_launch',native_launch_intent_persisted=False,sdk_dispatch_possible=False,reason_code=reason),native={},events=[])
 record.setdefault('preflight',{}).update(pid=session['pid'],session_id=session['session_id'],player_id=3,commander_id=session['scenario']['commander_id'])
 record.setdefault('request',{}).update(command_id=command,task_id=task,seq=args.seq,object_ids=object_ids,target_contact_id=args.contact_id)
 atomic(path,record,owned=owned);return record
def verify_no_dispatch(report,*,child_exit_code,session,commander_id,command_id,task_id,seq,object_ids,directory,target_contact_id=None):
 """An inert software rejection, never a return/disposal/completion claim."""
 try:
  if directory not in DLLS:return dict(no_dispatch_verified=False)
  pre=report.get('preflight',{});request=report.get('request',{});attest=report.get('pre_dispatch',{});path=HERE/directory
  checks=dict(exit_code=child_exit_code==REJECT_EXIT,status=report.get('status')=='no_dispatch_rejected',protocol=attest.get('protocol')==PROTOCOL and attest.get('stage')=='pre_native_launch',no_launch=report.get('native_launch_intent_persisted') is False and attest.get('native_launch_intent_persisted') is False and attest.get('sdk_dispatch_possible') is False,no_native=report.get('native')=={} and report.get('events')==[] and report.get('host_exit') is None,binding=report.get('session_id')==session['session_id']==pre.get('session_id') and pre.get('pid')==session['pid'] and pre.get('player_id')==3 and str(uuid.UUID(pre.get('commander_id','')))==str(uuid.UUID(str(commander_id))) and request.get('command_id')==str(uuid.UUID(str(command_id))) and request.get('task_id')==str(uuid.UUID(str(task_id))) and request.get('seq')==seq and request.get('object_ids')==list(object_ids),source=report.get('executable_sha256')==EXE and report.get('package_sha256')==session['mod_sha256'] and report.get('wrapper_sha256')==sha(path/'lease.py') and report.get('pre_dispatch_helper_sha256')==sha(__file__) and report.get('native_binary_sha256')==sha(path/'bin'/DLLS[directory]) and report.get('native_host_sha256')==sha(path/'bin/tactical_host.exe'))
  checks['target_binding']=target_contact_id is None or request.get('target_contact_id')==target_contact_id
  checks['strict_sequence_and_actor_types']=type(seq) is int and seq>0 and type(request.get('seq')) is int and isinstance(request.get('object_ids'),list) and all(type(x) is int and x>0 for x in request['object_ids'])
  ok=all(checks.values());return dict(no_dispatch_verified=ok,exclusive_control_never_held=ok,restoration_verified=False,completion_claim=False,checks=checks,reason_code=attest.get('reason_code') if ok else 'pre_dispatch_attestation_rejected')
 except (KeyError,ValueError,OSError,TypeError):return dict(no_dispatch_verified=False,reason_code='pre_dispatch_attestation_rejected')
