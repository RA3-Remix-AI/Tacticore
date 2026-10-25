"""Private own position history; ground passability needs separate evidence."""
import argparse,ctypes,hashlib,importlib.util,json,math,os,time
from pathlib import Path
from live_state import Memory,atomic_json,load_catalog,own_candidates
from observe_production import k,w
from read_selected_personality import inspect_player,resolve_registry
from session_package import verify_session_package
from ground_history import record as record_ground_positions
from own_actor_timeline import sample as sample_own_actor_timeline
ROOT=Path(__file__).resolve().parent
ALLOWED={'0x19ab11af','0x2c358c61'}

def cell(point):
 if not isinstance(point,(list,tuple)) or len(point)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) for x in point):return None
 return tuple(math.floor(x/40) for x in point)

def unseen_candidates(raw,seen):
 return [r for r in raw.get('candidates',[]) if r.get('type_hash') in ALLOWED and r.get('owner_index_candidate')==3 and cell(r.get('xyz')) is not None and cell(r['xyz']) not in seen]

def claim_recorder(output,session):
 path=output/'recorder-claim.json'
 with path.open('x',encoding='utf-8') as stream:json.dump(dict(session_id=session['session_id'],pid=session['pid'],recorder_pid=os.getpid(),mutations=False),stream)
 return path

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--session',type=Path,required=True);parser.add_argument('--commander',required=True)
 parser.add_argument('--interval',type=float,default=.75);parser.add_argument('--max-wall-seconds',type=int,default=3700)
 args=parser.parse_args()
 if not .25<=args.interval<=1.5 or not 30<=args.max_wall_seconds<=7200:raise ValueError('Own-history bounds')
 session_raw=args.session.read_bytes();session=json.loads(session_raw.decode('utf-8-sig'));verify_session_package(session)
 registry_path=Path(session['registry']);registry_raw=registry_path.read_bytes();registry=json.loads(registry_raw.decode('utf-8-sig'))
 output=Path(session['run_directory'])/'formation-own-history';output.mkdir(parents=True,exist_ok=True)
 stop=Path(session['run_directory'])/'battle-host/route-recorder-stop.json'
 claim_recorder(output,session)
 reader_path=ROOT.parent/'tactical/grounded_status_v2.py'
 spec=importlib.util.spec_from_file_location('passive_own_ground_status',reader_path);reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
 reader_sha=hashlib.sha256(reader_path.read_bytes()).hexdigest()
 atomic_json(output/('ground-status-audit-'+reader_sha[:12]+'.json'),reader.static_proof(session['game']))
 catalog=load_catalog();seen=set();memory=None;last_frame=None;owner_bound=None;samples=points=skips=positive=unknown=0
 started=time.monotonic();published=0;reason='time_limit';status={};timeline_last=None
 timeline_path=output/'complete-owned-foot-roster.jsonl'
 try:
  memory=Memory(session['pid'],session)
  k.GetExitCodeProcess.argtypes=[w.HANDLE,ctypes.POINTER(w.DWORD)];k.GetExitCodeProcess.restype=w.BOOL
  while time.monotonic()-started<args.max_wall_seconds:
   if args.session.read_bytes()!=session_raw or registry_path.read_bytes()!=registry_raw:reason='session_or_registry_changed';break
   if stop.exists() and json.loads(stop.read_text(encoding='utf-8-sig')).get('session_id')==session['session_id']:reason='host_stopped';break
   exit_code=w.DWORD()
   if not k.GetExitCodeProcess(memory.handle,ctypes.byref(exit_code)) or exit_code.value!=259:reason='game_exited';break
   try:
    raw=own_candidates(memory,3,catalog);frame=raw['frame_start']
    if last_frame is not None and frame<last_frame:reason='native_clock_ended';break
    if frame<=0:time.sleep(args.interval);continue
    owners={int(r['owner_address'],0) for r in raw['candidates']}
    if len(owners)!=1:raise ValueError('Own route identity unavailable')
    owner=next(iter(owners))
    if owner_bound is None:
     identity=inspect_player(memory.read,owner);binding=resolve_registry(identity,registry,session)
     if identity['player_index']!=3 or not binding['personality_binding_verified'] or binding['commander_id']!=args.commander:reason='commander_binding_rejected';break
     owner_bound=owner
    elif owner!=owner_bound:reason='own_player_changed';break
    if frame!=timeline_last:
     full=sample_own_actor_timeline(memory,raw)
     if full['atomic']:
      with timeline_path.open('a',encoding='utf-8') as stream:stream.write(json.dumps(dict(full,session_id=session['session_id'],pid=session['pid']),allow_nan=False)+'\n')
      timeline_last=frame
    if len(seen)<16384:
     selected=unseen_candidates(raw,seen)
     outcome=record_ground_positions(memory,session,selected,output,seen,reader.grounded_status,reader_sha)
     points+=outcome['points'];positive+=outcome['ground_positive_samples'];unknown+=outcome['unknown_or_ineligible']
    last_frame=frame;samples+=1
   except (ValueError,RuntimeError):
    skips+=1
    if last_frame is None and time.monotonic()-started>180:reason='waiting_for_match_timeout';break
   now=time.monotonic()
   if now-published>=5:
    status=dict(session_id=session['session_id'],pid=session['pid'],source='own_ground_status_positions',ground_passability_verified=False,read_only=True,model_eligible=False,samples=samples,points=points,cells=len(seen),ground_positive_samples=positive,unknown_or_ineligible_samples=unknown,skipped_non_atomic_samples=skips,last_frame=last_frame,state='recording')
    atomic_json(output/'recorder-status.json',status);published=now
   time.sleep(args.interval)
 except (ValueError,RuntimeError,OSError):reason='read_only_observer_unavailable'
 finally:
  if memory is not None:memory.close()
  status.update(session_id=session['session_id'],pid=session['pid'],source='own_ground_status_positions',ground_passability_verified=False,read_only=True,model_eligible=False,samples=samples,points=points,cells=len(seen),ground_positive_samples=positive,unknown_or_ineligible_samples=unknown,skipped_non_atomic_samples=skips,last_frame=last_frame,state='stopped',reason_code=reason)
  atomic_json(output/'recorder-status.json',status)
 print(json.dumps(status))

if __name__=='__main__':main()
