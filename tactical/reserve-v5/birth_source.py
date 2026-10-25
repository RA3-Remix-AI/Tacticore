"""Read-only paid-birth provenance. A birth receipt never authorizes borrowing."""
import ctypes as c
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[2]
UNITS={'conscript':0x19ab11af,'flak':0x2c358c61}
ENTRIES={0x7ba770:'81ec3c010000f605486bce0001535657',0x70f440:'83ec08558b6c241085ed568bf1',0x849220:'81ecb4000000568bf18b46148b4e04',0x73e390:'83ec208b4424248b54242c5355',0x789bf0:'51568bf180be3801000000'}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical_sha(receipt):return hashlib.sha256(json.dumps(receipt,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def select_source(path,session,actor_id=None):
 path=Path(path).resolve();run=Path(session['run_directory']).resolve()
 if not path.is_relative_to(run):raise ValueError('birth_source_outside_current_run')
 raw=path.read_bytes();report=json.loads(raw.decode('utf-8-sig'))
 if report.get('session_id')!=session['session_id'] or report.get('pid')!=session['pid']:raise ValueError('birth_source_foreign_session')
 if report.get('production_source_sha256')!=sha(ROOT/'production/persistent/client.py'):raise ValueError('birth_producer_source_changed')
 status=report.get('production_stopped',{});identity=report.get('production_native_identity',{})
 if not all(status.get(k)==v and type(status.get(k)) is type(v) for k,v in dict(native_phase=2,native_error=0,restore_mask=31,active_callbacks=0).items()):raise ValueError('birth_producer_not_stopped')
 if any(identity.get(k)!=v for k,v in dict(pid=session['pid'],session_id=session['session_id'],commander_id=session['scenario']['commander_id']).items()):raise ValueError('birth_producer_identity_changed')
 if status.get('session_id')!=session['session_id'] or status.get('commander_id')!=identity['commander_id'] or status.get('player_id')!=3:raise ValueError('birth_producer_status_foreign')
 entries=report.get('after_entries',[])
 if len(entries)!=5 or {int(x['address'],0) for x in entries}!=set(ENTRIES) or any(x.get('expected')!=ENTRIES[int(x['address'],0)] or x.get('actual')!=x.get('expected') for x in entries):raise ValueError('birth_producer_five_bytes_not_restored')
 if report.get('paid_orders_verified') is not True or report.get('serial_handover_verified') is not True:raise ValueError('birth_handover_claim_missing')
 accepted={x['command']['command_id']:x['command'] for x in report['commands'] if x.get('receipt',{}).get('accepted') is True}
 if len(accepted)!=sum(x.get('receipt',{}).get('accepted') is True for x in report['commands']):raise ValueError('birth_duplicate_production_command')
 choices=[]
 for receipt in status.get('ledger',[]):
  command=accepted.get(receipt.get('command_id'))
  if command is None:continue
  if any(receipt.get(k)!=command.get(k) for k in ('command_id','task_id','seq','unit')):raise ValueError('birth_command_receipt_mismatch')
  if command.get('session_id')!=session['session_id'] or command.get('commander_id')!=identity['commander_id'] or command.get('player_id')!=3:raise ValueError('birth_command_foreign')
  if not all(receipt.get(k) is True for k in ('accepted','completed','paid_verified','created','completion_observed','queue_preserved')) or receipt.get('payment_error')!=0 or type(receipt.get('live_samples')) is not int or receipt['live_samples']<1:raise ValueError('birth_incomplete_paid_receipt')
  if type(receipt.get('paid')) is not int or receipt['paid']<=0 or receipt.get('paid')!=receipt.get('cost') or type(receipt.get('queue_id')) is not int or receipt['queue_id']<=0 or type(receipt.get('completion_frame')) is not int or receipt['completion_frame']<=0:raise ValueError('birth_payment_queue_or_frame_invalid')
  if receipt.get('unit') in UNITS and (actor_id is None or receipt.get('object_id')==actor_id):choices.append((receipt,command))
 if len({x[0]['object_id'] for x in choices})!=len(choices) or not choices:raise ValueError('birth_actor_not_unique_or_missing')
 receipt,command=max(choices,key=lambda x:x[0]['seq'])
 return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),receipt=receipt,receipt_sha256=canonical_sha(receipt),command=command)

def producer_module():
 spec=importlib.util.spec_from_file_location('reserve_birth_frozen_producer',ROOT/'production/persistent/client.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def production_readonly(memory,session,birth):
 """Read the stopped named mapping and its exact immutable receipt twice."""
 module=producer_module();k=module.k;w=module.w
 k.OpenFileMappingW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];k.OpenFileMappingW.restype=w.HANDLE
 k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p
 k.UnmapViewOfFile.argtypes=[c.c_void_p];k.CloseHandle.argtypes=[w.HANDLE]
 handle=k.OpenFileMappingW(4,False,'Local\\RA3ProductionPersistent_'+str(session['pid']))
 if not handle:raise ValueError('birth_stopped_production_mapping_missing')
 view=None
 try:
  view=k.MapViewOfFile(handle,4,0,0,c.sizeof(module.Persistent))
  if not view:raise ValueError('birth_stopped_production_mapping_unreadable')
  size=module.Persistent.ledger.offset
  before=c.string_at(view,size);header=module.Persistent();c.memmove(c.addressof(header),before,size)
  if header.magic!=0x50434d44 or header.version!=1 or header.pid!=session['pid'] or module.uuid_string(header.session)!=session['session_id'] or module.uuid_string(header.commander)!=session['scenario']['commander_id'] or header.phase!=2 or header.error or header.active or header.restore_mask!=31 or not 0<header.count<=1024:raise ValueError('birth_stopped_native_mapping_binding')
  found=[]
  for index in range(header.count):
   address=view+size+index*c.sizeof(module.Receipt);raw=c.string_at(address,c.sizeof(module.Receipt));r=module.Receipt.from_buffer_copy(raw)
   if module.uuid_string(r.command.id)==birth['command']['command_id']:
    if raw!=c.string_at(address,c.sizeof(module.Receipt)):raise ValueError('birth_native_receipt_changed')
    found.append((index,r,raw))
  if len(found)!=1:raise ValueError('birth_native_receipt_not_unique')
  index,r,raw=found[0];expected=birth['receipt'];command=birth['command']
  if r.state!=2 or r.error or not r.attempted or module.uuid_string(r.command.task)!=command['task_id'] or r.command.seq!=command['seq'] or module.uuid_string(r.command.session)!=session['session_id'] or module.uuid_string(r.command.commander)!=session['scenario']['commander_id'] or r.command.hash!=UNITS[expected['unit']]:raise ValueError('birth_native_command_changed')
  if not r.created or not r.completed or not r.live_samples or r.payment_error or r.paid!=r.cost or not r.debit_count or not r.preserved:raise ValueError('birth_native_payment_or_completion_unverified')
  for field,value in dict(queue_id=expected['queue_id'],object_id=expected['object_id'],paid=expected['paid'],cost=expected['cost'],completion_frame=expected['completion_frame'],object_owner=header.owner,object_hash=r.command.hash).items():
   if getattr(r,field)!=value:raise ValueError('birth_native_receipt_value_changed')
  entries=[dict(address=hex(a),expected=b,actual=memory.read(a,len(bytes.fromhex(b))).hex()) for a,b in ENTRIES.items()]
  after=c.string_at(view,size);receipt_after=c.string_at(view+size+index*c.sizeof(module.Receipt),c.sizeof(module.Receipt))
  if any(e['actual']!=e['expected'] for e in entries) or before!=after or raw!=receipt_after:raise ValueError('birth_producer_not_stably_inert')
  return dict(protocol='reserve_birth_stopped_production_readonly_v1',mutations=False,sdk_calls=0,pid=session['pid'],session_id=session['session_id'],owner=hex(header.owner),window_thread=header.thread,start_low=header.start_low,start_high=header.start_high,header_hex=before.hex(),header_after_hex=after.hex(),receipt_hex=raw.hex(),receipt_after_hex=receipt_after.hex(),receipt_index=index,header_size=size,receipt_size=c.sizeof(module.Receipt),entries=entries,reader_sha256=sha(__file__),producer_sha256=sha(ROOT/'production/persistent/client.py'),native_binary_sha256=sha(module.NATIVE_BIN/'ProductionPersistent.dll'),native_host_sha256=sha(module.NATIVE_BIN/'persistent_host.exe'))
 finally:
  if view:k.UnmapViewOfFile(view)
  k.CloseHandle(handle)
