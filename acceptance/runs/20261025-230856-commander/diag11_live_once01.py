"""Pure bounded live static selection; at most one original frozen MF11 child."""
import hashlib,json,subprocess,sys,time
from pathlib import Path
RUN=Path(__file__).resolve().parent;BRIDGE=RUN.parents[2];SESSION=BRIDGE/'acceptance/active-session.json'
SELECTOR=BRIDGE/'acceptance/calibration/field_plan_margin11_static.py';FIELD=BRIDGE/'tactical/mission-formation-v11/field_coordinate.py'
AUDIT=RUN/'diag11-live01-driver.json';OUTPUT=RUN/'coord-mf11-diag01.json'
if AUDIT.exists() or OUTPUT.exists():raise ValueError('fresh_attempt_required')
raw=SESSION.read_bytes();s=json.loads(raw.decode('utf-8-sig'))
sys.path.insert(0,str(BRIDGE/'production'))
from observe_production import Memory
record=dict(pid=s['pid'],session_id=s['session_id'],selector=str(SELECTOR),selector_sha256=hashlib.sha256(SELECTOR.read_bytes()).hexdigest(),status='readonly_waiting_resume',sdk_calls_before_child=0,child_count=0,model_requests=0)
def save():AUDIT.write_text(json.dumps(record,indent=2,allow_nan=False),encoding='utf-8')
save();print(json.dumps(record),flush=True)
m=Memory(s['pid'],s)
try:
 logic=m.u32(0xcd8ce4);initial=m.u32(logic+0x50);end=time.monotonic()+180;live_since=None;live_frame=None
 while time.monotonic()<end:
  if SESSION.read_bytes()!=raw or m.u32(0xcd8ce4)!=logic:raise ValueError('session_changed')
  frame=m.u32(logic+0x50);pause=m.u32(logic+0x15c)
  if frame<initial:raise ValueError('clock_regression')
  if not pause and frame>initial:
   if live_since is None:live_since=time.monotonic();live_frame=frame
   if time.monotonic()-live_since>=5 and frame-live_frame>=75:break
  else:live_since=None;live_frame=None
  time.sleep(.05)
 else:raise ValueError('stable_resume_timeout')
 record.update(status='pure_static_selection',resume_frame=live_frame,stable_frame=frame,stable_wall_seconds=time.monotonic()-live_since);save()
finally:m.close()
end=time.monotonic()+90;attempt=0;selection=None
while time.monotonic()<end:
 if SESSION.read_bytes()!=raw or hashlib.sha256(SELECTOR.read_bytes()).hexdigest()!=record['selector_sha256']:raise ValueError('source_or_session_changed')
 attempt+=1;plan=RUN/f'diag11-live01-plan{attempt:02d}.json'
 result=subprocess.run([sys.executable,str(SELECTOR),'--session',str(SESSION),'--output',str(plan)],capture_output=True,text=True,encoding='utf-8',timeout=5)
 plan.with_suffix('.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
 if result.returncode:raise ValueError('pure_selector_failed')
 chosen=plan.with_name(plan.stem+'-selection.json')
 record.update(pure_attempts=attempt,last_probe=str(plan));save()
 if chosen.exists():selection=json.loads(chosen.read_text(encoding='utf-8-sig'));break
 time.sleep(2)
if selection is None:record.update(status='no_current_static_pair_no_child');save();print(json.dumps(record),flush=True);raise SystemExit(0)
if selection['paused']:raise ValueError('paused_selection_never_dispatches')
cmd=[sys.executable,str(FIELD),'--session',str(SESSION),'--natural',str(RUN/'natural-production.json'),'--front-id',str(selection['front_id']),'--support-id',str(selection['support_id']),'--contact-id',selection['contact_id'],'--execute','--output',str(OUTPUT)]
record.update(status='single_fresh_field_child',child_count=1,selection=selection,argv=cmd);save();print(json.dumps(record),flush=True)
with (RUN/'diag11-live01-field.log').open('w',encoding='utf-8') as log:child=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
record.update(status='single_child_exited',child_exit=child.returncode);save();print(json.dumps(record),flush=True)
