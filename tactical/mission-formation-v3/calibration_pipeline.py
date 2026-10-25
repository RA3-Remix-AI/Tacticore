"""Sole-runner bounded calibration: passive observer -> paid actors -> one mission.

Root authorizes this calibration explicitly. No model, GUI, resource editing,
native retry, production/mission overlap, or hidden-contact fallback.
"""
import argparse,json,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parent.parent
def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--wait-seconds',type=float,default=90);p.add_argument('--output',type=Path,required=True);p.add_argument('--economy',action='store_true');p.add_argument('--mission',choices=['combat','formation'],default='combat');a=p.parse_args()
 if not 0<=a.wait_seconds<=180:raise ValueError('bounded_wait_required')
 s=json.loads(a.session.read_text(encoding='utf-8-sig'));run=Path(s['run_directory']);natural=run/'natural-production.json'
 if natural.exists() or a.output.exists():raise ValueError('one_fresh_pipeline_originals_preserved')
 raw=a.session.read_bytes();observer=subprocess.run([str(BRIDGE/'production/bin/observe_build.exe'),str(s['pid']),'30'],capture_output=True,text=True,check=True)
 natural.write_text(observer.stdout,encoding='utf-8');n=json.loads(observer.stdout)
 if not (n.get('state')==2 and n.get('error')==0 and n.get('original_bytes_restored') is True and n.get('active_detours')==0 and n.get('window_thread')==n.get('callback_thread') and n.get('window_thread',0)>0):raise ValueError('observer_not_restored_no_production')
 if a.session.read_bytes()!=raw:raise ValueError('session_changed_before_production')
 paid=subprocess.run([sys.executable,str(HERE.parent/'enqueue_actor.py'),'--session',str(a.session),'--natural',str(natural),'--after-report',str(natural),'--count','2'],capture_output=True,text=True)
 (run/'pipeline-paid.stdout.txt').write_text(paid.stdout,encoding='utf-8');(run/'pipeline-paid.stderr.txt').write_text(paid.stderr,encoding='utf-8')
 if paid.returncode:raise ValueError('paid_actor_child_failed_no_mission')
 result=json.loads(paid.stdout.strip().splitlines()[-1])
 if not(result.get('stop_phase')==2 and result.get('restore_mask')==31 and result.get('active')==0):raise ValueError('production_not_restored_no_mission')
 print(json.dumps(dict(production_restored=True,paid_report=result['report'],waiting_legal_contact=True)),flush=True)
 if a.mission=='formation':
  if a.wait_seconds>90:raise ValueError('formation_readonly_wait_bound')
  cmd=[sys.executable,str(HERE/'field_coordinate.py'),'--session',str(a.session),'--natural',str(natural),'--routes',str(run/'formation-own-history'),'--wait-route-seconds',str(a.wait_seconds),'--execute','--output',str(a.output)]
  raise SystemExit(subprocess.run(cmd).returncode)
 until=time.monotonic()+a.wait_seconds;attempt=0
 while True:
  if a.session.read_bytes()!=raw:raise ValueError('session_changed_during_readonly_wait')
  attempt+=1;plan=a.output.with_name(a.output.stem+f'-plan{attempt:03d}.json')
  args=[sys.executable,str(HERE.parent/'mission-formation/field_combat.py'),'--session',str(a.session),'--natural',str(natural),'--backend','mission-combat-v5','--min-distance','1800','--max-distance','2600','--output',str(plan)]
  if a.economy:args.append('--economy')
  check=subprocess.run(args,capture_output=True,text=True)
  if check.returncode==0:
   selected=json.loads(plan.with_name(plan.stem+'-selection.json').read_text(encoding='utf-8'))
   # Exactly one native attempt; no retries if actor/contact changes at dispatch.
   actual=args[:];actual[actual.index('--output')+1]=str(a.output);actual+=['--object-id',str(selected['actor']['object_id']),'--target-id',str(selected['target']['object_id']),'--execute']
   print(json.dumps(dict(dispatch_once=True,actor=selected['actor']['object_id'],target=selected['target']['object_id'],selection_file=str(plan))),flush=True)
   raise SystemExit(subprocess.run(actual).returncode)
  if time.monotonic()>=until:
   a.output.with_name(a.output.stem+'-wait-no-dispatch.json').write_text(json.dumps(dict(session_id=s['session_id'],pid=s['pid'],status='bounded_readonly_wait_no_legal_actor_target',attempts=attempt,sdk_mission_calls=0,production_restored=True),indent=2),encoding='utf-8');return
  time.sleep(2)
if __name__=='__main__':main()
