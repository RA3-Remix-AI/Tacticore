import importlib.util,json,hashlib,sys,time,uuid,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUN=Path(__file__).resolve().parent
SESSION=RUN/'session.json';SUPPLIER=RUN/'paid-reserve2-01.json';OUTPUT=RUN/'paid-reserve2-direct02.json'
INVOKE=RUN/'paid-reserve2-direct02-invocation.json';RESULT=RUN/'paid-reserve2-direct02-result.json';READY=RUN/'paid-reserve2-direct02-import-ready.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write_new(p,x):
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,indent=2)
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
if any(p.exists() for p in [OUTPUT,INVOKE,RESULT,READY]):raise ValueError('direct02_requires_fresh_paths')
session_raw=SESSION.read_bytes();supplier_raw=SUPPLIER.read_bytes();session=json.loads(session_raw.decode('utf-8-sig'))
assert session['pid']==59668 and session['scenario']['model_requests_enabled'] is False
lease_path=ROOT/'tactical/reserve-v2/lease.py';assert sha(lease_path)=='5fe17b2f2138319311da6142d2f57142536ff2b816df46dc9f95156a9ec3c39c'
lease=load('reserve2_direct02_frozen_preimport',lease_path)
b=lease.preflight.module('reserve2_direct02_pause_ro',ROOT/'tactical/ordered-combo/lease.py')
seq=int(time.monotonic()*1000)&0x7fffffff or 1;command=str(uuid.uuid4());task=str(uuid.uuid4())
argv=['--session',str(SESSION),'--commander',session['scenario']['commander_id'],'--birth-report',str(SUPPLIER),'--actor-id','781','--seq',str(seq),'--command-id',command,'--task-id',task,'--execute','--output',str(OUTPUT)]
bind=dict(protocol='same_imported_python_fresh_ro_to_one_reserve2_main',session_id=session['session_id'],pid=session['pid'],session_sha256=sha(SESSION),supplier_sha256=sha(SUPPLIER),prior_eightbyte_proof_sha256=sha(RUN/'reserve2-01-preNative-eightbytes-readonly.json'),no_reserve2_module_proof_sha256=sha(RUN/'reserve2-direct02-modules-before-readonly.json'),wrapper_sha256=sha(lease_path),runner_sha256=sha(Path(__file__)),argv=argv,new_command_id=command,new_task_id=task,new_seq=seq,main_invocation_limit=1,ro_window_seconds=5,production_restart=False)
write_new(READY,dict(bind,imported=True,sdk_calls=0))
print(json.dumps(dict(import_ready=True,seq=seq,command_id=command,task_id=task)),flush=True)
called=False;result=dict(main_called=False,main_calls=0,exception=None,sdk_calls_claimed=False)
try:
 pre,_,_,_,_,_,memory=b.readiness(SESSION)
 try:
  start=time.monotonic();logic=int(pre['logic'],0)
  while memory.u32(logic+0x15c):
   if time.monotonic()-start>120:raise TimeoutError('direct02_pause_wait_expired')
   if SESSION.read_bytes()!=session_raw or SUPPLIER.read_bytes()!=supplier_raw:raise ValueError('direct02_source_changed')
   time.sleep(.05)
 finally:memory.close()
 deadline=time.monotonic()+5;errors=[];ready=False
 while time.monotonic()<deadline:
  try:
   _,fresh,_,_,_,_,_,current_memory=lease.preflight.current_selection(SESSION,session['scenario']['commander_id'],781)
   try:chosen=dict(frame=fresh['frame'],actor=fresh['selected'],observed_only=True,not_native_admission_authority=True)
   finally:current_memory.close()
   ready=True;break
  except (ValueError,RuntimeError) as failure:
   errors.append(dict(error=type(failure).__name__+':'+str(failure)));time.sleep(.05)
 if not ready:raise ValueError('direct02_no_current_eligible_paid_actor_in_five_seconds')
 if SESSION.read_bytes()!=session_raw or SUPPLIER.read_bytes()!=supplier_raw:raise ValueError('direct02_source_changed_before_main')
 write_new(INVOKE,dict(bind,fresh_selection=chosen,ro_errors=errors))
 called=True;result.update(main_called=True,main_calls=1)
 lease.main(argv)
except BaseException as failure:
 result['exception']=type(failure).__name__+':'+str(failure);result['traceback']=traceback.format_exc()
finally:
 result.update(output=str(OUTPUT),report_exists=OUTPUT.exists(),supplier_unchanged=SUPPLIER.read_bytes()==supplier_raw,session_unchanged=SESSION.read_bytes()==session_raw)
 write_new(RESULT,result);print(json.dumps(result),flush=True)
