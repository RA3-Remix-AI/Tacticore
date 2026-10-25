"""Arm the model host and independent result recorder for a fresh AI-vs-AI match.

The GUI runner must first record the lobby in a fresh owned session. This script
does not launch a game, alter the lobby, or turn diagnostic evidence into grants.
"""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
from live_state import atomic_json
from tactical_bridge import verify_manifest
from continuous_contract import PROTOCOL,mission_limits

ROOT=Path(__file__).resolve().parent
COMMANDER='57e668b4-4d89-43bd-bc92-0dd436f046ef'
REQUIRED={('raid','harass_economy'),('attack','main_attack'),('combined_arms','coordinate_force')}

def preflight(session_path,manifest_path,require_missions=False):
 session=json.loads(session_path.read_text(encoding='utf-8-sig'));scenario=session.get('scenario',{})
 expected=dict(trial_kind='model_vs_native_full_match',acceptance_fresh=True,observer_player_index=2,computer_player_index=3,opponent_player_index=4,participant_count=2,observer_local_player=True,model_requests_enabled=True,commander_id=COMMANDER,opponent='native_soviet_oleg',map_id='map_mp_2_feasel6',starting_credits=10000,model_side_native_difficulty='medium',opponent_difficulty='medium',lobby_verified=True,calibration_commands_dispatched=0)
 if any(type(scenario.get(key)) is not type(value) or scenario[key]!=value for key,value in expected.items()):raise ValueError('Record the fresh native-opponent acceptance lobby first')
 run=Path(session['run_directory']).resolve()
 if not run.is_dir() or session.get('phase')!='llm_full_match':raise ValueError('Fresh recorded acceptance session required')
 if (run/'full-match-runner.json').exists():raise ValueError('Match already armed')
 if (run/'battle-host').exists() or (run/'settlement-watch').exists():raise ValueError('Acceptance requires a fresh, unarmed match')
 if any(path.name not in ('session.json','lobby-scenario.json') for path in run.glob('*.json')):raise ValueError('Calibration process cannot serve as a fresh acceptance match')
 grant=verify_manifest(manifest_path,session,COMMANDER)
 purposes={(name,purpose) for name,items in grant['supported_purposes'] for purpose in items}
 if not REQUIRED<=purposes:raise ValueError('Not all three required real purpose capabilities have passed')
 if require_missions:
  if scenario.get('continuous_missions_required') is not True:raise ValueError('Continuous mission acceptance must be recorded in the fresh lobby')
  continuous={(g['module'],g['purpose']) for g in grant['grants'] if mission_limits(g) is not None}
  if not REQUIRED<=continuous:raise ValueError('All three purposes require real approach, effect, retreat and restoration evidence')
 return session,grant

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--session',type=Path,required=True);parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--preflight',action='store_true')
 parser.add_argument('--require-mission-effects',action='store_true',help='Require three independently qualified continuous mission capabilities; dispatch counts never establish acceptance')
 args=parser.parse_args();args.session=args.session.resolve();args.manifest=args.manifest.resolve()
 session,grant=preflight(args.session,args.manifest,args.require_mission_effects);run=Path(session['run_directory'])
 if args.preflight:
  print(json.dumps(dict(session_id=session['session_id'],ready_to_arm=True,purposes=sorted(REQUIRED),mission_effects_required=args.require_mission_effects,commands_dispatched=0)));return
 production=ROOT.parent/'acceptance/runs/20261024-183816-commander'
 host=[sys.executable,str(ROOT/'battle_host.py'),'--session',str(args.session),'--commander',COMMANDER,'--player','3','--execute','--with-visibility','--wait-for-match','--max-wall-seconds','3600','--total-budget','4000','--reserve','1000','--evidence',str(production/'production-trace-20261024-184048-9696c7b3.json'),'--persistent-evidence',str(production/'persistent-production-status.json'),'--tactical-evidence',str(args.manifest)]
 watch=[sys.executable,str(ROOT/'watch_match.py'),'--session',str(args.session),'--max-wall-seconds','3700']
 creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)
 record=dict(session_id=session['session_id'],game_pid=session['pid'],purposes=sorted(REQUIRED),source_reports=[g['source_report'] for g in grant['grants']],mission_effects_required=args.require_mission_effects,mission_protocol=PROTOCOL if args.require_mission_effects else None,mutates_lobby=False,model_host=None,watcher=None,phase='arming')
 # Claim ownership before spawning anything; concurrent arm attempts fail closed.
 with (run/'full-match-runner.json').open('x',encoding='utf-8') as claim:
  json.dump(record,claim);claim.flush();os.fsync(claim.fileno())
 with (run/'full-match-watch.log').open('w',encoding='utf-8') as watch_log,(run/'full-match-host.log').open('w',encoding='utf-8') as host_log:
  watcher=subprocess.Popen(watch,stdout=watch_log,stderr=watch_log,creationflags=creationflags)
  record['watcher']=watcher.pid;atomic_json(run/'full-match-runner.json',record)
  try:
   time.sleep(.25)
   if watcher.poll() is not None:raise RuntimeError('Independent settlement recorder failed before host arming')
   model=subprocess.Popen(host,stdout=host_log,stderr=host_log,creationflags=creationflags)
  except BaseException:
   if watcher.poll() is None:watcher.terminate();watcher.wait(timeout=5)
   record.update(phase='arm_failed',watcher_exit=watcher.returncode);atomic_json(run/'full-match-runner.json',record)
   raise
  record.update(model_host=model.pid,phase='armed');atomic_json(run/'full-match-runner.json',record)
  print(json.dumps(dict(phase='armed',session_id=session['session_id'],host_pid=model.pid,watch_pid=watcher.pid)),flush=True)
  while model.poll() is None:time.sleep(.5)
  record.update(host_exit=model.returncode,phase='host_ended_waiting_settlement');atomic_json(run/'full-match-runner.json',record)
  while watcher.poll() is None:time.sleep(.5)
  record.update(watcher_exit=watcher.returncode,phase='requires_independent_review');atomic_json(run/'full-match-runner.json',record)
  print(json.dumps(record),flush=True)

if __name__=='__main__':main()
