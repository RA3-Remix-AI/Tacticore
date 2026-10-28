"""Trusted local production executor. Importing does not attach or dispatch."""
import ctypes as c,hashlib,json,math,struct,subprocess,sys,threading,time,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent;NATIVE_BIN=HERE/'bin-v2';PRODUCTION=HERE.parent;BRIDGE=PRODUCTION.parent
sys.path.insert(0,str(PRODUCTION));sys.path.insert(0,str(BRIDGE/'native-ai'))
from observe_production import Memory,read_owner,read_factory,k,w,EXPECTED
from session_package import verify_session_package
from run_flak import durable_write
from natural_evidence import compatible_natural_calls
from session_history import unknown_session
from read_selected_personality import inspect_player,resolve_registry

U=c.c_uint32;L=c.c_int32
class Command(c.Structure):
 _fields_=[('seq',U),('id',U*4),('task',U*4),('session',U*4),('commander',U*4)]+[(x,U) for x in 'hash budget reserve expires queue_limit requested_tick factory factory_id iface'.split()]
R_FIELDS='state error attempted frame queue_id node cost quoted_cost cash liability prior_count preserved paid debit_count payment_error created object object_id object_owner object_hash completed completion_frame live_samples object_hp_bits object_x_bits object_y_bits factory_x_bits factory_y_bits'.split()
class Receipt(c.Structure):
 _fields_=[('updates',L),('version',L),('command',Command)]+[(x,U) for x in R_FIELDS]
class Persistent(c.Structure):
 _fields_=[(x,U) for x in 'magic version pid thread owner ai personality personality_id player_template start_low start_high'.split()]+[('session',U*4),('commander',U*4)]+[(x,U) for x in 'total_budget reserve_floor min_interval start_frame'.split()]+[(x,L) for x in 'phase stop_requested active heartbeat request_state'.split()]+[('request',Command)]+[(x,U) for x in 'reply_index reply_error last_seq last_frame last_accepted_frame spent count restore_mask error callback_thread'.split()]+[('ledger',Receipt*1024)]
UNITS={'conscript':0x19ab11af,'flak':0x2c358c61,'bear':0x33026fa1}
def uuid_words(value):
 result=uuid.UUID(str(value))
 if not result.int:raise ValueError('zero_uuid')
 return struct.unpack('<4I',result.bytes)
def uuid_string(words):return str(uuid.UUID(bytes=struct.pack('<4I',*words)))
def unsigned(value,name,low,high):
 if type(value) is not int or not low<=value<=high:raise ValueError(name+'_bounds')
 return value
def float_bits(value):return struct.unpack('<f',struct.pack('<I',value))[0]
def require_unpaused(memory):
 if memory.u32(memory.u32(0xcd8ce4)+0x15c)!=0:raise ValueError('game_paused')
def validate_command(raw,session_id,commander_id,frame,reserve_floor):
 required={'session_id','player_id','commander_id','command_id','task_id','seq','unit','budget','reserve','expires_frame'}
 if type(raw) is not dict or set(raw)!=required:raise ValueError('command_fields')
 if uuid_words(raw['session_id'])!=uuid_words(session_id) or uuid_words(raw['commander_id'])!=uuid_words(commander_id) or type(raw['player_id']) is not int or raw['player_id']!=3:raise ValueError('command_binding')
 if raw['unit'] not in UNITS:raise ValueError('unit_not_allowed')
 for name in ['command_id','task_id']:uuid_words(raw[name])
 unsigned(raw['seq'],'sequence',1,0xffffffff);unsigned(raw['budget'],'budget',1,1000);unsigned(raw['reserve'],'reserve',reserve_floor,100000);unsigned(raw['expires_frame'],'expiry',frame,min(frame+900,0xffffffff))
 return dict(raw,session_id=str(uuid.UUID(str(raw['session_id']))),commander_id=str(uuid.UUID(str(raw['commander_id']))),command_id=str(uuid.UUID(str(raw['command_id']))),task_id=str(uuid.UUID(str(raw['task_id']))))

class ProductionExecutor:
 def __init__(self,session_path,snapshot_path,factory_address,commander_id,natural_observation_path,total_budget=5000,reserve_floor=500,min_interval_frames=150):
  self.session_path=Path(session_path);self.snapshot_path=Path(snapshot_path);self.factory_address=int(factory_address,0) if isinstance(factory_address,str) else factory_address;self.commander_id=str(uuid.UUID(str(commander_id)));self.natural_path=Path(natural_observation_path)
  self.total_budget=unsigned(total_budget,'total_budget',1,20000);self.reserve_floor=unsigned(reserve_floor,'reserve_floor',50,10000);self.min_interval=unsigned(min_interval_frames,'min_interval',30,900)
  self.memory=None;self.map_handle=None;self.view=None;self.shared=None;self.host=None;self.stopping=threading.Event();self.lock=threading.RLock();self.originals={};self.fingerprints={};self.last_emitted={};self.error=None;self.threads=[]
 def _record(self,record):
  if not hasattr(self,'audit'):return
  with self.lock:
   with self.audit.open('a',encoding='utf-8') as stream:stream.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n');stream.flush();__import__('os').fsync(stream.fileno())
 def _verify_binding(self):
  if self.session_path.read_bytes()!=self.session_bytes:raise RuntimeError('session_changed')
  if hashlib.sha256(self.registry_path.read_bytes()).hexdigest()!=self.registry_digest:raise RuntimeError('registry_changed')
  if hashlib.sha256(self.package.read_bytes()).hexdigest()!=self.session['mod_sha256']:raise RuntimeError('package_changed')
  player=read_owner(self.memory,self.owner,3);native=inspect_player(self.memory.read,self.owner);binding=resolve_registry(native,self.registry,self.session)
  if not binding['personality_binding_verified'] or binding['commander_id']!=self.commander_id or native['personality_wrapper']!=self.native['personality_wrapper'] or native['instance_id']!=self.native['instance_id']:raise RuntimeError('personality_changed')
  return player
 def start(self):
  if self.shared is not None:raise RuntimeError('executor_already_started')
  layout=json.loads(subprocess.check_output([str(NATIVE_BIN/'persistent_host.exe'),'--layout'],text=True))
  if layout!=dict(command=c.sizeof(Command),receipt=c.sizeof(Receipt),persistent=c.sizeof(Persistent),request=Persistent.request.offset,ledger=Persistent.ledger.offset):raise RuntimeError('native_shared_layout_mismatch')
  self.session_bytes=self.session_path.read_bytes();self.session=json.loads(self.session_bytes.decode('utf-8-sig'));self.package=verify_session_package(self.session);self.registry_path=Path(self.session['registry']);self.registry_digest=hashlib.sha256(self.registry_path.read_bytes()).hexdigest();self.registry=json.loads(self.registry_path.read_text(encoding='utf-8-sig'))
  if self.registry['registry_revision']!=self.session['registry_revision']:raise RuntimeError('registry_revision_mismatch')
  if unknown_session(self.session['session_id'],bridge_root=BRIDGE):raise RuntimeError('session_unknown_previous_execution')
  snap=json.loads(self.snapshot_path.read_text(encoding='utf-8-sig'));obs=json.loads(self.natural_path.read_text(encoding='utf-8-sig'))
  if snap['pid']!=self.session['pid'] or snap['sha256']!=EXPECTED:raise RuntimeError('natural_evidence_mismatch')
  compatible_natural_calls(obs,self.session['pid'])
  matches=[x for x in snap['candidates'] if int(x['address'],0)==self.factory_address and x['owner_index_candidate']==3 and int(x['type_hash'],0)==0x80d4ea1e]
  if len(matches)!=1:raise RuntimeError('factory_not_unique')
  self.candidate=matches[0];self.owner=int(self.candidate['owner_address'],0);self.memory=Memory(self.session['pid'],self.session);self.native=inspect_player(self.memory.read,self.owner);self.binding=resolve_registry(self.native,self.registry,self.session)
  if not self.binding['personality_binding_verified'] or self.binding['commander_id']!=self.commander_id or self.binding['side']!='Soviet':raise RuntimeError('commander_binding_unverified')
  self._verify_binding();factory=read_factory(self.memory,self.candidate,self.owner)
  if not factory.get('production_interface_available'):raise RuntimeError('factory_interface_unavailable')
  if self.memory.read(0x8d5727,6)!=bytes.fromhex('89beb0080000') or self.memory.read(0x844a3f,6)!=bytes.fromhex('898690000000'):raise RuntimeError('personality_constructor_signature_mismatch')
  self.run=Path(self.session['run_directory']);self.audit=self.run/'persistent-production.jsonl';self.status_path=self.run/'persistent-production-status.json';self._record(dict(event='attach_preflight',session_id=self.session['session_id'],commander_id=self.commander_id,personality_instance=self.native['instance_id'],package_sha256=self.session['mod_sha256']))
  k.CreateFileMappingW.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,w.DWORD,w.DWORD,w.LPCWSTR];k.CreateFileMappingW.restype=w.HANDLE;k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p;k.UnmapViewOfFile.argtypes=[c.c_void_p];k.GetTickCount.restype=w.DWORD
  self.map_handle=k.CreateFileMappingW(w.HANDLE(-1),None,4,0,c.sizeof(Persistent),'Local\\RA3ProductionPersistent_'+str(self.session['pid']))
  if not self.map_handle or c.get_last_error()==183:raise RuntimeError('persistent_already_used_in_process')
  self.view=k.MapViewOfFile(self.map_handle,0xf001f,0,0,c.sizeof(Persistent))
  if not self.view:raise c.WinError(c.get_last_error())
  c.memset(self.view,0,c.sizeof(Persistent));self.shared=Persistent.from_address(self.view);s=self.shared;s.magic=0x50434d44;s.version=1;s.pid=self.session['pid'];s.thread=obs['window_thread'];s.owner=self.owner;s.ai=int(self.native['ai_player'],0);s.personality=int(self.native['personality_wrapper'],0);s.personality_id=int(self.native['instance_id'],0);s.player_template=int(self.native['player_template'],0)
  times=[w.FILETIME() for _ in range(4)]
  if not k.GetProcessTimes(self.memory.handle,*[c.byref(x) for x in times]):raise c.WinError(c.get_last_error())
  s.start_low=times[0].dwLowDateTime;s.start_high=times[0].dwHighDateTime;s.session[:]=uuid_words(self.session['session_id']);s.commander[:]=uuid_words(self.commander_id);s.total_budget=self.total_budget;s.reserve_floor=self.reserve_floor;s.min_interval=self.min_interval;s.heartbeat=c.c_int32(k.GetTickCount()).value
  self._record(dict(event='attach_dispatch_pending'));log=(self.run/'persistent-native-host.log').open('a',encoding='utf-8');self.host_log=log;self.host=subprocess.Popen([str(NATIVE_BIN/'persistent_host.exe'),str(s.pid)],stdout=log,stderr=log,text=True)
  heartbeat=threading.Thread(target=self._heartbeat,daemon=True);heartbeat.start();self.threads.append(heartbeat);deadline=time.monotonic()+12
  while not s.phase and time.monotonic()<deadline:time.sleep(.02)
  if s.phase!=1:self.stop();raise RuntimeError('native_attach_failed_'+str(s.error))
  self._record(dict(event='attached',thread=s.callback_thread,start_frame=s.start_frame));return self.status()
 def _heartbeat(self):
  while not self.stopping.wait(.5):
   failure_context='binding_or_lifecycle_changed'
   try:
    with self.lock:
     self._verify_binding();self.shared.heartbeat=c.c_int32(k.GetTickCount()).value;failure_context='status_persistence_failed';self._status_unlocked()
   except Exception as error:
    self.error=str(error);self.shared.stop_requested=1;self.stopping.set();self._record(dict(event='local_stop',reason=failure_context));break
 def _copy_receipt(self,index):
  r=self.shared.ledger[index]
  for _ in range(10):
   if r.updates:time.sleep(.001);continue
   version=r.version;raw=c.string_at(c.addressof(r),c.sizeof(Receipt));copy=Receipt.from_buffer_copy(raw)
   if r.updates==0 and r.version==version:return copy
  return None
 def _receipt_view(self,r):
  ident=uuid_string(r.command.id);original=self.originals.get(ident,{});paid_valid=not r.payment_error and r.paid==r.cost and r.cost>0 and r.debit_count>0;complete=bool(r.state==2 and paid_valid and r.created and r.completed and r.live_samples and r.object_id and r.object_owner==self.owner and r.object_hash==r.command.hash)
  state='completed' if complete else ('queued' if r.state==2 else ('unknown' if r.attempted else 'no_dispatch_rejected'))
  return dict(command_id=original.get('command_id',ident),task_id=original.get('task_id',uuid_string(r.command.task)),seq=r.command.seq,status=state,accepted=r.state==2,started=r.state==2,completed=complete,reason_code='game_paused' if r.error==12 else 'native_'+str(r.error),unit=next((n for n,h in UNITS.items() if h==r.command.hash),'unknown'),queue_id=r.queue_id,object_id=r.object_id or None,cost=r.cost or r.quoted_cost,paid=r.paid,paid_verified=paid_valid,created=bool(r.created),completion_observed=bool(r.completed),live_samples=r.live_samples,payment_error=r.payment_error,enqueue_frame=r.frame,completion_frame=r.completion_frame or None,queue_preserved=bool(r.preserved))
 def _status_unlocked(self):
  receipts=[]
  for i in range(min(self.shared.count,1024)):
   r=self._copy_receipt(i)
   if r is None:continue
   value=self._receipt_view(r);receipts.append(value);key=(value['status'],value['paid'],value['created'],value['completion_observed'],min(value['live_samples'],1),value['payment_error'])
   if self.last_emitted.get(value['seq'])!=key:self.last_emitted[value['seq']]=key;self._record(dict(event='execution_feedback',**value))
  result=dict(session_id=self.session['session_id'],player_id=3,commander_id=self.commander_id,personality_binding_verified=True,state='running' if self.shared.phase==1 and not self.shared.stop_requested else 'stopped',native_phase=self.shared.phase,native_error=self.shared.error,restore_mask=self.shared.restore_mask,active_callbacks=self.shared.active,spent_committed=self.shared.spent,total_budget=self.total_budget,last_seq=self.shared.last_seq,ledger=receipts,local_error=self.error)
  durable_write(self.status_path,result);return result
 def status(self):
  with self.lock:
   if self.shared is None:return dict(state='not_started',ledger=[])
   return self._status_unlocked()
 def submit(self,command):
  with self.lock:
   if self.shared is None or self.shared.phase!=1 or self.stopping.is_set():return dict(status='no_dispatch_rejected',accepted=False,started=False,completed=False,reason_code='executor_stopped',task_id=command.get('task_id'))
   try:
    self._verify_binding();require_unpaused(self.memory);frame=self.memory.u32(self.memory.u32(0xcd8ce4)+0x50);normal=validate_command(command,self.session['session_id'],self.commander_id,frame,self.reserve_floor);ident=normal['command_id'];fingerprint=json.dumps(normal,sort_keys=True,separators=(',',':'))
    if ident in self.fingerprints and self.fingerprints[ident]!=fingerprint:raise ValueError('command_id_conflict')
    factory=read_factory(self.memory,self.candidate,self.owner)
    if not factory.get('production_interface_available'):raise ValueError('factory_not_alive')
    require_unpaused(self.memory)
    if self.shared.request_state in (1,2):raise ValueError('native_request_pending')
   except Exception as error:return dict(status='no_dispatch_rejected',accepted=False,started=False,completed=False,reason_code=str(error),task_id=command.get('task_id'))
   self.originals.setdefault(ident,dict(command));self.fingerprints.setdefault(ident,fingerprint);wire=Command();wire.seq=normal['seq'];wire.id[:]=uuid_words(ident);wire.task[:]=uuid_words(normal['task_id']);wire.session[:]=uuid_words(normal['session_id']);wire.commander[:]=uuid_words(normal['commander_id']);wire.hash=UNITS[normal['unit']];wire.budget=normal['budget'];wire.reserve=normal['reserve'];wire.expires=normal['expires_frame'];wire.queue_limit=2;wire.factory=self.factory_address;wire.factory_id=self.memory.u32(self.factory_address+0xdc);wire.iface=int(factory['interface'],0);wire.requested_tick=k.GetTickCount()
   self._record(dict(event='command_dispatch_pending',command=command));self.shared.request=wire;self.shared.request_state=1
   user=c.WinDLL('user32',use_last_error=True);user.PostThreadMessageW.argtypes=[w.DWORD,w.UINT,w.WPARAM,w.LPARAM];user.PostThreadMessageW.restype=w.BOOL
   if not user.PostThreadMessageW(self.shared.thread,0x8000+0x330,0x50434d44,0):self.shared.stop_requested=1;self.stopping.set();return dict(status='unknown',accepted=False,started=False,completed=False,reason_code='message_dispatch_failed',task_id=command['task_id'])
   deadline=time.monotonic()+8
   while self.shared.request_state!=3 and time.monotonic()<deadline:time.sleep(.01)
   if self.shared.request_state!=3:self.shared.stop_requested=1;self.stopping.set();self._record(dict(event='command_outcome_unknown',command_id=command['command_id']));return dict(status='unknown',accepted=False,started=False,completed=False,reason_code='native_timeout',task_id=command['task_id'])
   if self.shared.reply_index==0xffffffff:return dict(status='no_dispatch_rejected',accepted=False,started=False,completed=False,reason_code='native_'+str(self.shared.reply_error),task_id=command['task_id'])
   receipt=self._copy_receipt(self.shared.reply_index);self.shared.request_state=0
   if receipt is None:return dict(status='unknown',accepted=False,started=False,completed=False,reason_code='receipt_unstable',task_id=command['task_id'])
   value=self._receipt_view(receipt);self._record(dict(event='command_receipt',**value));self._status_unlocked();return value
 def stop(self):
  self.stopping.set()
  if self.shared is not None:self.shared.stop_requested=1
  if self.host:
   try:self.host.wait(timeout=8)
   except subprocess.TimeoutExpired:self.error='host_stop_timeout'
  for t in self.threads:
   if t is not threading.current_thread():t.join(timeout=2)
  if self.memory:self.memory.close();self.memory=None
  if hasattr(self,'host_log') and self.host and self.host.poll() is not None:self.host_log.close()
  if self.shared is not None:
   result=self.status();self._record(dict(event='stopped',native_phase=self.shared.phase,restore_mask=self.shared.restore_mask,active=self.shared.active,native_ai_continues=True));return result
  return dict(state='stopped',ledger=[])
