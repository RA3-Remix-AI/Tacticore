"""One normally paid birth, stopped production, then one bounded reserve child.

The paid source report is immutable once the child can reference its SHA.
No model, target choice, direct game-memory mutation, or production restart.
"""
import argparse, hashlib, importlib.util, json, subprocess, sys, time, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
 sys.modules[name]=module;spec.loader.exec_module(module);return module

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--session',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--max-seconds',type=float,default=180)
 args=parser.parse_args();args.session=args.session.resolve();args.output=args.output.resolve()
 if args.output.exists() or not 30<=args.max_seconds<=300:raise ValueError('fresh_bounded_reserve_supply_required')
 raw=args.session.read_bytes();session=json.loads(raw.decode('utf-8-sig'));run=Path(session['run_directory']).resolve()
 if args.output.parent!=run or session['scenario'].get('model_requests_enabled') is not False:raise ValueError('owned_nonmodel_reserve_calibration_required')
 common=load('reserve_paid_supply_frozen_helpers',Path(__file__).with_name('continuous_paid_margin12_static.py'))
 wrapper=load('reserve_candidate_readonly_preflight',ROOT/'tactical/reserve-v4/lease.py')
 natural=run/'natural-production.json'
 if not natural.exists():
  observation=subprocess.run([str(ROOT/'production/bin/observe_build.exe'),str(session['pid']),'30'],capture_output=True,text=True,check=True)
  with natural.open('x',encoding='utf-8') as stream:stream.write(observation.stdout)
 rt=load('reserve_paid_production_runtime',ROOT/'production/persistent/client.py')
 deadline=time.monotonic()+args.max_seconds;factory=None
 while time.monotonic()<deadline:
  memory=common.Memory(session['pid'],session)
  try:
   own=common.own_candidates(memory,3,common.load_catalog())
   factories=[u for u in own['candidates'] if u['type_hash']=='0x80d4ea1e' and memory.f32(memory.u32(int(u['address'],0)+0x33c)+4)>0]
   if len(factories)==1:factory=factories[0];before=common.entry_proof(memory);break
  finally:memory.close()
  time.sleep(.2)
 if factory is None:raise ValueError('reserve_supply_no_unique_owned_barracks')
 snapshot=run/('reserve-supply-owned-'+uuid.uuid4().hex+'.json')
 common.durable(snapshot,dict(own,pid=session['pid'],sha256=common.EXPECTED))
 executor=rt.ProductionExecutor(args.session,snapshot,factory['address'],session['scenario']['commander_id'],natural,total_budget=85,reserve_floor=1000,min_interval_frames=150)
 report=dict(protocol='single_paid_birth_for_reserve_v4',session_id=session['session_id'],pid=session['pid'],model_requests=0,
  production_source_sha256=hashlib.sha256((ROOT/'production/persistent/client.py').read_bytes()).hexdigest(),
  supply_driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),commands=[],before_entries=before,
  status='preflight',reserve_calls_before_source_freeze=0,budget_limit=85,reserve=1000)
 selected=None;error=None
 try:
  executor.start()
  memory=common.Memory(session['pid'],session)
  try:frame=memory.u32(memory.u32(0xcd8ce4)+0x50)
  finally:memory.close()
  command=dict(session_id=session['session_id'],player_id=3,commander_id=session['scenario']['commander_id'],command_id=str(uuid.uuid4()),task_id=str(uuid.uuid4()),seq=1,unit='conscript',budget=85,reserve=1000,expires_frame=frame+450)
  reply=executor.submit(command);report['commands'].append(dict(command=command,receipt=reply));common.durable(args.output,report)
  if reply.get('accepted') is not True:raise ValueError('single_reserve_birth_order_not_accepted')
  while time.monotonic()<deadline:
   if args.session.read_bytes()!=raw:raise ValueError('reserve_supply_session_changed')
   status=executor.status();report['production_status']=status
   receipt=next((x for x in status['ledger'] if x['command_id']==command['command_id']),None)
   if receipt and all(receipt.get(k) is True for k in ('completed','paid_verified','created','completion_observed')) and receipt.get('live_samples',0)>0:
    # Receipt metadata only chooses the paid ID. It is NOT permission to borrow.
    # Stop production promptly; the preloaded wrapper and Native independently
    # recheck the live actor, including all three actual admission frames.
    selected=receipt['object_id'];report['paid_actor_id']=selected;break
   if status['native_phase']!=1:raise ValueError('reserve_supply_producer_not_running')
   common.durable(args.output,report);time.sleep(.05)
 except Exception as failure:error=type(failure).__name__+':'+str(failure)
 finally:
  status=executor.stop();report['production_stopped']=status
  shared=executor.shared
  identity=dict(pid=shared.pid,session_id=rt.uuid_string(shared.session),commander_id=rt.uuid_string(shared.commander),owner=hex(shared.owner),thread=shared.callback_thread,last_seq=shared.last_seq) if shared is not None else {}
  report['production_native_identity']=identity
  memory=common.Memory(session['pid'],session)
  try:after=common.entry_proof(memory)
  finally:memory.close()
  report['after_entries']=after;report['paid_orders_verified']=common.paid_orders_verified(report['commands'],status)
  report['serial_handover_verified']=common.restored(status,identity,session,after) and report['paid_orders_verified']
  report.update(status='production_stopped',error=error);common.durable(args.output,report)
 # Never mutate this report below: it becomes the child's paid-birth source.
 if error or not report['serial_handover_verified'] or selected is None:return
 output=args.output.with_name(args.output.stem+'-reserve.json')
 command=[sys.executable,str(ROOT/'tactical/reserve-v4/lease.py'),'--session',str(args.session),'--commander',session['scenario']['commander_id'],'--birth-report',str(args.output),'--actor-id',str(selected),'--seq',str(int(time.monotonic()*1000)&0x7fffffff),'--wait-ready-seconds','5','--execute','--output',str(output)]
 invocation=args.output.with_name(args.output.stem+'-execution.json')
 with invocation.open('x',encoding='utf-8') as stream:json.dump(dict(command=command,execution_mode='same_process_preloaded_frozen_wrapper',attempts=1,native_host_spawns_max=1,source_sha256=hashlib.sha256(args.output.read_bytes()).hexdigest()),stream,indent=2)
 from contextlib import redirect_stdout,redirect_stderr
 result=0;failure=None
 with output.with_suffix('.child.log').open('w',encoding='utf-8') as log,redirect_stdout(log),redirect_stderr(log):
  try:wrapper.main(command[2:])
  except SystemExit as stopped:result=stopped.code if type(stopped.code) is int else 1
  except Exception as stopped:
   import traceback
   traceback.print_exc();result=1;failure=type(stopped).__name__
 with invocation.with_suffix('.result.json').open('x',encoding='utf-8') as stream:json.dump(dict(child_exit=result,error_type=failure,execution_mode='same_process_preloaded_frozen_wrapper',reserve_report=str(output),source_unchanged=hashlib.sha256(args.output.read_bytes()).hexdigest()==json.loads(invocation.read_text())['source_sha256']),stream,indent=2)
 print(json.dumps(dict(reserve_report=str(output),child_exit=result)),flush=True)

if __name__=='__main__':main()
