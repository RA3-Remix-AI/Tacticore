"""One fresh read-only route plan followed by at most one calibration child.
Does not retry, change actors after dispatch, or call a model.
"""
import argparse,json,subprocess,sys,time,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent

def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--natural',type=Path,required=True);p.add_argument('--routes',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--front-id',type=int);p.add_argument('--support-id',type=int);p.add_argument('--contact-id');p.add_argument('--execute',action='store_true');p.add_argument('--wait-route-seconds',type=float,default=0);a=p.parse_args()
 if not 0<=a.wait_route_seconds<=90:raise ValueError('readonly_readiness_wait_bound')
 if a.output.exists():raise ValueError('existing_artifacts_preserved')
 until=time.monotonic()+a.wait_route_seconds;attempt=0
 while True:
  attempt+=1;plan=a.output.with_name(a.output.stem+'-try'+str(attempt).zfill(2)+'-mission.json');selection=plan.with_name(plan.stem+'-selection.json');proof=plan.with_name(plan.stem+'-proof.json')
  if plan.exists():raise ValueError('existing_plan_preserved')
  args=[sys.executable,str(HERE/'field_plan.py'),'--session',str(a.session),'--routes',str(a.routes),'--output',str(plan)]
  for name,value in [('front-id',a.front_id),('support-id',a.support_id),('contact-id',a.contact_id)]:
   if value is not None:args+=['--'+name,str(value)]
  completed=subprocess.run(args)
  if completed.returncode:raise SystemExit(completed.returncode)
  if selection.exists():break
  if time.monotonic()>=until:raise ValueError('no_readonly_route_ready_no_native_child')
  time.sleep(3)
 s=json.loads(selection.read_text(encoding='utf-8-sig'))
 if not a.execute:return
 if s['paused']:raise ValueError('readonly_waiter_must_observe_resume_before_child')
 cmd=[sys.executable,str(HERE/'lease.py'),'--session',str(a.session),'--natural',str(a.natural),'--front-id',str(s['front_id']),'--support-id',str(s['support_id']),'--mission-file',str(plan),'--proof-file',str(proof),'--contact-id',s['contact_id'],'--expires-frame',str(s['frame']+4500),'--command-id',str(uuid.uuid4()),'--task-id',str(uuid.uuid4()),'--seq',str(int(time.monotonic()*1000)&0x7fffffff),'--post-frames','30','--execute','--output',str(a.output)]
 print(json.dumps(dict(dispatching_single_child=True,selection=s)),flush=True);raise SystemExit(subprocess.run(cmd).returncode)
if __name__=='__main__':main()
