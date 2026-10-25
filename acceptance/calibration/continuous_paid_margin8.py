"""Owned calibration with stricter actor margins before irreversible handover.

No model calls, GUI, resource/health edits, unit spawning, parallel tactical
leases, or production restart. Every production order has a distinct UUID.
"""
import argparse,hashlib,importlib.util,json,subprocess,sys,time,uuid
from pathlib import Path
BRIDGE=Path(__file__).resolve().parents[2];HERE=BRIDGE/'tactical/mission-formation-v8';TACTICAL=HERE.parent;MARGIN_PLAN=Path(__file__).with_name('field_plan_margin8.py')
sys.path[:0]=[str(BRIDGE/'production'),str(BRIDGE/'integration'),str(TACTICAL)]
from observe_production import Memory,EXPECTED
from own_candidates import own_candidates,load_catalog
ENTRIES={0x7ba770:'81ec3c010000f605486bce0001535657',0x70f440:'83ec08558b6c241085ed568bf1',0x849220:'81ecb4000000568bf18b46148b4e04',0x73e390:'83ec208b4424248b54242c5355',0x789bf0:'51568bf180be3801000000'}
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def durable(path,data):
 path=Path(path);tmp=path.with_name(path.name+'.pending-'+uuid.uuid4().hex);tmp.write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8')
 for i in range(25):
  try:tmp.replace(path);return
  except PermissionError:
   if i==24:raise
   time.sleep(.02)
def entry_proof(memory):
 return [dict(address=hex(a),expected=b,actual=memory.read(a,len(bytes.fromhex(b))).hex()) for a,b in ENTRIES.items()]
def restored(status,identity,session,entries):
 return (status.get('native_phase')==2 and status.get('native_error')==0 and status.get('restore_mask')==31 and status.get('active_callbacks')==0 and identity.get('pid')==session['pid'] and identity.get('session_id')==session['session_id'] and identity.get('commander_id')==session['scenario']['commander_id'] and len(entries)==5 and {int(e['address'],0) for e in entries}==set(ENTRIES) and all(e.get('expected')==ENTRIES.get(int(e['address'],0))==e.get('actual') for e in entries))
def paid_orders_verified(commands,status):
 ledger={x['command_id']:x for x in status.get('ledger',[])}
 for row in commands:
  if not row['receipt'].get('accepted'):continue
  command=row['command'];r=ledger.get(command['command_id'],{})
  if not all(r.get(k)==command[k] for k in ('command_id','task_id','seq','unit')) or not all(r.get(k) is True for k in ('completed','paid_verified','created','completion_observed','queue_preserved')) or not r.get('object_id') or r.get('live_samples',0)<1 or r.get('payment_error')!=0:return False
 return True
def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--mission',choices=['formation'],default='formation');p.add_argument('--max-seconds',type=int,default=600);a=p.parse_args()
 if not 30<=a.max_seconds<=900 or a.output.exists():raise ValueError('bounded_fresh_driver_required')
 raw=a.session.read_bytes();s=json.loads(raw.decode('utf-8-sig'));run=Path(s['run_directory']);natural=run/'natural-production.json'
 if not natural.exists():
  obs=subprocess.run([str(BRIDGE/'production/bin/observe_build.exe'),str(s['pid']),'30'],capture_output=True,text=True,check=True);natural.write_text(obs.stdout,encoding='utf-8')
 n=json.loads(natural.read_text(encoding='utf-8-sig'))
 if not(n.get('pid')==s['pid'] and n.get('state')==2 and n.get('error')==0 and n.get('original_bytes_restored') is True and n.get('active_detours')==0 and n.get('window_thread')==n.get('callback_thread') and n.get('window_thread',0)>0):raise ValueError('natural_not_restored')
 rt=load('calibration_paid_production_executor',BRIDGE/'production/persistent/client.py');fm=load('calibration_peer_formation_entries',HERE/'lease.py');m=Memory(s['pid'],s)
 try:
  if m.u32(m.u32(0xcd8ce4)+0x15c):raise ValueError('paused_no_production')
  fm.original_entries(m);before=entry_proof(m)
  if any(x['actual']!=x['expected'] for x in before):raise ValueError('production_entry_not_original')
  snap=own_candidates(m,3,load_catalog());factories=[x for x in snap['candidates'] if x['type_hash']=='0x80d4ea1e' and m.f32(m.u32(int(x['address'],0)+0x33c)+4)>0]
  if len(factories)!=1:raise ValueError('one_owned_live_barracks_required')
 finally:m.close()
 snapshot=run/('continuous-paid-snapshot-'+uuid.uuid4().hex+'.json');durable(snapshot,dict(snap,pid=s['pid'],sha256=EXPECTED))
 exe=rt.ProductionExecutor(a.session,snapshot,factories[0]['address'],s['scenario']['commander_id'],natural,total_budget=4000,reserve_floor=1000,min_interval_frames=150)
 report=dict(selection_policy='calibration_gap60_120_margin450_prefer600_1300_allow2600',selector_sha256=hashlib.sha256(MARGIN_PLAN.read_bytes()).hexdigest(),frozen_driver_sha256=hashlib.sha256((HERE/'continuous_paid_driver.py').read_bytes()).hexdigest(),session_id=s['session_id'],pid=s['pid'],budget_limit=4000,reserve=1000,max_seconds=a.max_seconds,production_source_sha256=hashlib.sha256((BRIDGE/'production/persistent/client.py').read_bytes()).hexdigest(),commands=[],plans=[],before_entries=before,native_tactical_attempts=0,status='preflight',mutations='normal_paid_production_only',model_requests=0)
 pending=None;last_submit=-1000;sequence=0;ready=None;next_plan=0;end=time.monotonic()+a.max_seconds
 try:
  exe.start();report['status']='supplying_and_planning';durable(a.output,report)
  while time.monotonic()<end:
   if a.session.read_bytes()!=raw:raise ValueError('session_changed')
   status=exe.status()
   if status['native_phase']!=1:raise ValueError('production_not_running')
   if pending:
    entry=next((x for x in status['ledger'] if x['task_id']==pending),None)
    if entry and entry['completed']:pending=None
    elif entry and not entry['accepted']:pending=None
   if time.monotonic()>=next_plan:
    index=len(report['plans'])+1;plan=a.output.with_name(a.output.stem+f'-plan{index:04d}.json')
    if a.mission=='formation':
     cmd=[sys.executable,str(MARGIN_PLAN),'--session',str(a.session),'--output',str(plan)]
     for unit,flag in [('conscript','--preferred-front-id'),('flak','--preferred-support-id')]:
      born=[x for x in status['ledger'] if x.get('completed') and x.get('unit')==unit and x.get('object_id')]
      if born:cmd += [flag,str(max(born,key=lambda x:x['seq'])['object_id'])]
    else:cmd=[sys.executable,str(HERE/'field_combat_v6.py'),'--session',str(a.session),'--natural',str(natural),'--economy','--min-distance','1800','--max-distance','2600','--output',str(plan)]
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=5)
    plan.with_name(plan.stem+'.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8');report['plans'].append(str(plan));next_plan=time.monotonic()+1
    selected=plan.with_name(plan.stem+'-selection.json')
    if result.returncode==0 and selected.exists() and pending is None:
     ready=json.loads(selected.read_text(encoding='utf-8-sig'));report['ready_selection']=ready;break
   mem=Memory(s['pid'],s)
   try:frame=mem.u32(mem.u32(0xcd8ce4)+0x50)
   finally:mem.close()
   if pending is None and frame-last_submit>=150 and status['spent_committed']<4000 and sequence<32:
    sequence+=1;unit='conscript' if sequence%2 else 'flak';command=dict(session_id=s['session_id'],player_id=3,commander_id=s['scenario']['commander_id'],command_id=str(uuid.uuid4()),task_id=str(uuid.uuid4()),seq=sequence,unit=unit,budget=min(1000,4000-status['spent_committed']),reserve=1000,expires_frame=frame+450)
    receipt=exe.submit(command);report['commands'].append(dict(command=command,receipt=receipt));last_submit=frame
    if receipt.get('status')=='unknown':raise ValueError('production_outcome_unknown')
    if receipt.get('accepted'):pending=command['task_id']
    print(json.dumps(dict(production_order=sequence,unit=unit,accepted=receipt.get('accepted'),reason=receipt.get('reason_code'))),flush=True)
   report['production_status']=status;durable(a.output,report);time.sleep(.2)
 except Exception as e:report['error']=str(e)
 finally:
  stopped=exe.stop();report['production_stopped']=stopped
  shared=exe.shared;identity=dict(pid=shared.pid,session_id=rt.uuid_string(shared.session),commander_id=rt.uuid_string(shared.commander),owner=hex(shared.owner),thread=shared.callback_thread,last_seq=shared.last_seq) if shared is not None else {}
  report['production_native_identity']=identity
  mem=Memory(s['pid'],s)
  try:after=entry_proof(mem)
  finally:mem.close()
  report['after_entries']=after;report['paid_orders_verified']=paid_orders_verified(report['commands'],stopped);report['serial_handover_verified']=restored(stopped,identity,s,after) and report['paid_orders_verified'];report['status']='production_stopped';durable(a.output,report)
 if report.get('error') or not report['serial_handover_verified'] or ready is None:return
 tactical=a.output.with_name(a.output.stem+'-'+a.mission+'.json');report['native_tactical_attempts']=1;report['status']='fresh_revalidation_driver';durable(a.output,report)
 if a.mission=='formation':cmd=[sys.executable,str(HERE/'field_coordinate.py'),'--session',str(a.session),'--natural',str(natural),'--front-id',str(ready['front_id']),'--support-id',str(ready['support_id']),'--contact-id',ready['contact_id'],'--execute','--output',str(tactical)]
 else:cmd=[sys.executable,str(HERE/'field_combat_v6.py'),'--session',str(a.session),'--natural',str(natural),'--economy','--object-id',str(ready['actor']['object_id']),'--target-id',str(ready['target']['object_id']),'--min-distance','1800','--max-distance','2600','--execute','--output',str(tactical)]
 with a.output.with_name(a.output.stem+'-formation-driver.log').open('w',encoding='utf-8') as log:child=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
 report.update(status='single_tactical_driver_exited',tactical_report=str(tactical),tactical_child_exit=child.returncode);durable(a.output,report);print(json.dumps(dict(report=str(a.output),status=report['status'],child_exit=child.returncode)),flush=True)
if __name__=='__main__':main()
