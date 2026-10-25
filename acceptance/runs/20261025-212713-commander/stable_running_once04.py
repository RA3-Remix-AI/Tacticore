"""Calibration-only: wait for stable live clock, pure current selection, one MF8 child."""
import hashlib,json,subprocess,sys,time
from pathlib import Path
RUN=Path(__file__).resolve().parent;BRIDGE=RUN.parents[2]
sys.path.insert(0,str(BRIDGE/'production'))
from observe_production import Memory
SESSION=BRIDGE/'acceptance/active-session.json';raw=SESSION.read_bytes();s=json.loads(raw.decode('utf-8-sig'))
OUTPUT=RUN/'coord-mf8-04.json';audit=RUN/'stable-running04-driver.json'
if OUTPUT.exists() or audit.exists():raise ValueError('fresh_attempt_required')
record=dict(session_id=s['session_id'],pid=s['pid'],status='readonly_waiting_resume',child_count=0,model_requests=0,sdk_calls_before_child=0)
def save():audit.write_text(json.dumps(record,indent=2,allow_nan=False),encoding='utf-8')
save();print(json.dumps(record),flush=True)
m=Memory(s['pid'],s)
try:
 logic=m.u32(0xcd8ce4);initial=m.u32(logic+0x50);start=time.monotonic();live_since=None;live_frame=None
 while time.monotonic()-start<180:
  if SESSION.read_bytes()!=raw or m.u32(0xcd8ce4)!=logic:raise ValueError('session_changed')
  frame=m.u32(logic+0x50);pause=m.u32(logic+0x15c)
  if frame<initial:raise ValueError('clock_regression')
  if pause==0 and frame>initial:
   if live_since is None:live_since=time.monotonic();live_frame=frame
   if time.monotonic()-live_since>=5 and frame-live_frame>=75:break
  else:live_since=None;live_frame=None
  time.sleep(.05)
 else:raise ValueError('stable_resume_timeout')
 record.update(status='stable_running_pure_selection',resume_frame=live_frame,stable_frame=frame,stable_wall_seconds=time.monotonic()-live_since,stable_logic_frames=frame-live_frame);save();print(json.dumps(record),flush=True)
finally:m.close()
source=(RUN/'margin_probe_current.py').read_text(encoding='utf-8-sig')
end=time.monotonic()+90;attempt=0;selected=None
while time.monotonic()<end:
 if SESSION.read_bytes()!=raw:raise ValueError('session_changed')
 attempt+=1;name=f'stable-running04-probe{attempt:02d}'
 text=source.replace('mf8-margin-candidates01-readonly.json',name+'.json').replace('paused_hint_only=True','paused_hint_only=False')
 text=text.replace("target_hp=t['hp'],target_distance", "target_hp=t['hp'],target_role=safety['templates'][t['type_hash']]['role'],target_distance")
 probe=RUN/(name+'.py');probe.write_text(text,encoding='utf-8')
 result=subprocess.run([sys.executable,str(probe)],capture_output=True,text=True,encoding='utf-8',timeout=5)
 (RUN/(name+'.log')).write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
 if result.returncode:raise ValueError('pure_probe_failed')
 report=json.loads((RUN/(name+'.json')).read_text(encoding='utf-8-sig'))
 if report['paused']!=0:raise ValueError('paused_after_stability')
 rows=[x for x in report['candidates'] if x['original_safety_rejection'] is None and 60<=x['gap']<=120 and x['minimum_current_visible_enemy_distance']>=400 and 600<=x['target_distance']<=2600]
 rows.sort(key=lambda x:(not(x['front_state']==16 and x['support_state']==16),not 600<=x['target_distance']<=1300,x.get('target_role') not in ('structure','economy'),x['target_distance']))
 record.update(pure_attempts=attempt,last_probe_frame=report['frame'],last_candidate_count=len(rows));save();print(json.dumps(dict(pure_attempt=attempt,frame=report['frame'],candidates=len(rows))),flush=True)
 if rows:selected=rows[0];break
 time.sleep(2)
if selected is None:
 record.update(status='no_current_pair_no_child');save();raise SystemExit(0)
record.update(status='single_fresh_field_child',selected=selected,selected_probe_frame=report['frame'],child_count=1);save()
cmd=[sys.executable,str(BRIDGE/'tactical/mission-formation-v8/field_coordinate.py'),'--session',str(SESSION),'--natural',str(RUN/'natural-production.json'),'--front-id',str(selected['front_id']),'--support-id',str(selected['support_id']),'--contact-id',selected['target_contact_id'],'--execute','--output',str(OUTPUT)]
record['argv']=cmd;save()
with (RUN/'stable-running04-field.log').open('w',encoding='utf-8') as log:child=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
record.update(status='single_child_exited',child_exit=child.returncode);save();print(json.dumps(record),flush=True)
