"""One fresh read-only MF12 selection, then at most one bound calibration child."""
import argparse,json,subprocess,sys,time,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parents[2]/'tactical/mission-formation-v12'

def child_arguments(session,natural,output,selection,plan,proof,command,task,seq):
 return [sys.executable,str(HERE/'lease.py'),'--session',str(session),'--natural',str(natural),'--front-id',str(selection['front_id']),'--support-id',str(selection['support_id']),'--mission-file',str(plan),'--proof-file',str(proof),'--contact-id',selection['contact_id'],'--expires-frame',str(selection['expires_frame']),'--command-id',command,'--task-id',task,'--seq',str(seq),'--post-frames','30','--execute','--output',str(output)]

def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--natural',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--front-id',type=int);p.add_argument('--support-id',type=int);p.add_argument('--contact-id');p.add_argument('--execute',action='store_true');p.add_argument('--wait-ready-seconds',type=float,default=0);p.add_argument('--minimum-selection-gap',type=float,default=25);a=p.parse_args()
 if not 0<=a.wait_ready_seconds<=90 or a.output.exists():raise ValueError('bounded_fresh_readiness_required')
 command,task=str(uuid.uuid4()),str(uuid.uuid4());seq=int(time.monotonic()*1000)&0x7fffffff;end=time.monotonic()+a.wait_ready_seconds;attempt=0
 while True:
  attempt+=1;plan=a.output.with_name(a.output.stem+'-plan'+str(attempt)+'.json');selection=plan.with_name(plan.stem+'-selection.json');proof=plan.with_name(plan.stem+'-proof.json')
  args=[sys.executable,str(Path(__file__).with_name('field_plan_margin12_supported.py')),'--session',str(a.session),'--output',str(plan),'--minimum-selection-gap',str(a.minimum_selection_gap)]
  for key,flag in [('front_id','--front-id'),('support_id','--support-id'),('contact_id','--contact-id')]:
   if getattr(a,key) is not None:args += [flag,str(getattr(a,key))]
  completed=subprocess.run(args,capture_output=True,text=True,timeout=5);plan.with_suffix('.log').write_text(completed.stdout+'\n'+completed.stderr,encoding='utf-8')
  if completed.returncode:raise SystemExit(completed.returncode)
  if selection.exists():break
  if time.monotonic()>=end:raise ValueError('no_current_pair_contact_no_native_child')
  time.sleep(min(3,max(0,end-time.monotonic())))
 s=json.loads(selection.read_text(encoding='utf-8-sig'))
 if not a.execute:return
 if s['paused']:raise ValueError('readiness_must_observe_resume_before_child')
 cmd=child_arguments(a.session,a.natural,a.output,s,plan,proof,command,task,seq)
 invocation=a.output.with_name(a.output.stem+'-invocation.json')
 with invocation.open('x',encoding='utf-8') as f:json.dump(dict(command_id=command,task_id=task,seq=seq,selection=s,argv=cmd,native_attempts=1),f,indent=2)
 sys.path.insert(0,str(HERE.parent))
 from mission_risk_worker import MissionRiskWorker
 with a.output.with_suffix('.child.log').open('w',encoding='utf-8') as log:
  result=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
  risk=MissionRiskWorker(a.output,a.session,a.output.with_suffix('.local-risk.json')).start()
  try:
   while result.poll() is None:time.sleep(.1)
  finally:
   worker=risk.close()
   with a.output.with_suffix('.local-risk-worker.json').open('x',encoding='utf-8') as f:json.dump(worker,f,indent=2,allow_nan=False)
 if a.output.exists():
  raw=json.loads(a.output.read_text(encoding='utf-8-sig'));issued=raw.get('native',{}).get('issued_frame',0);support_frame=s.get('native_support',{}).get('frame')
  with a.output.with_suffix('.selection-age.json').open('x',encoding='utf-8') as f:json.dump(dict(issued_frame=issued,support_observed_frame=support_frame,age_frames=issued-support_frame if issued and support_frame else None,support_at_issue_verified=False,semantics='support_is_a_selection_observation_not_a_native_issue_guarantee'),f,indent=2)
 raise SystemExit(result.returncode)

if __name__=='__main__':main()
