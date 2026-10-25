"""One real model request against live, visibility-filtered state; no game actuator."""
import argparse,asyncio,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'strategy'))
from battle_agent import BattleAgent,TacticalEvidence,BuildEvidence
from engine import Binding,StrategyEngine
from http_adapter import ChatAdapter,TransportPool,load_profile
from live_state import LiveBattleState,RetryableSample,atomic_json
from tactical_bridge import verify_manifest,air_scout_authorized
from battle_host import capability_evidence,conscript_evidence,default_library

async def run(args):
 session=json.loads(args.session.read_text(encoding='utf-8-sig'))
 if args.output.exists():raise ValueError('Use a new probe output directory')
 args.output.mkdir(parents=True)
 profile=load_profile(args.library,args.commander)
 tactical=verify_manifest(args.tactical_evidence,session,args.commander)
 binding=Binding(session['session_id'],3,args.commander,profile.commander_name,profile.connection_id)
 production=capability_evidence(args.production_evidence,session) if args.production_evidence else None
 if args.persistent_evidence:
  if production is None:raise ValueError('Persistent evidence requires base production proof')
  production['supported_foci']+=conscript_evidence(args.persistent_evidence,session)['supported_foci']
 foci=('native_baseline',)+tuple(production['supported_foci'] if production else ())
 collector=LiveBattleState(args.session,args.commander,3,visibility=True,foci=foci,output=args.output,air_scout=air_scout_authorized(tactical))
 snapshot=await asyncio.to_thread(collector.collect)
 if snapshot['paused']:raise ValueError('Resume game before a model probe')
 engine=StrategyEngine(binding,timeout_seconds=12.5,max_response_age_seconds=20,audit_path=args.output/'plans.jsonl')
 tactical_evidence=TacticalEvidence(tactical['evidence_id'],binding.session_id,3,'game_bridge',tactical['supported_purposes'],actor_roles=tactical['actor_roles'])
 build=BuildEvidence(production['evidence_id'],binding.session_id,3,'game_bridge',production['supported_foci']) if production else None
 agent=BattleAgent(engine,build_evidence=build,tactical_evidence=tactical_evidence,event_capacity=16,context_budget_bytes=8192,memory_path=args.output/'agent-state.json',jobs_path=args.output/'jobs.json')
 adapter=ChatAdapter(profile,pool=TransportPool(1),total_timeout=12,max_input_bytes=16384,max_tokens=1536)
 agent.observe(snapshot);pending=asyncio.create_task(agent.decide(snapshot,adapter));started=time.monotonic();failures=0
 try:
  while not pending.done():
   await asyncio.sleep(.5)
   if pending.done():break
   try:
    snapshot=await asyncio.to_thread(collector.collect);agent.observe(snapshot);failures=0
   except RetryableSample:
    failures+=1
    if failures>5:raise
  result=await pending
  summary=dict(session_id=binding.session_id,commander_id=binding.commander_id,status=result.status,reason_code=result.reason_code,engine=dict(engine.metrics),transport=dict(adapter.metrics),memory=dict(agent.metrics),elapsed_wall_seconds=round(time.monotonic()-started,3),plan=result.plan.public() if result.plan else None,dispatch_candidates=[job for job in agent.jobs()['jobs'] if job['host_dispatch_candidate']],game_actuator_created=False,game_commands_dispatched=0)
  atomic_json(args.output/'probe-result.json',summary)
  print(json.dumps(dict(output=str(args.output),status=result.status,reason_code=result.reason_code,requests=engine.metrics['requests'],tactical_candidates=[job['module'] for job in summary['dispatch_candidates'] if job['module']!='build'],game_commands_dispatched=0)))
 finally:
  if not pending.done():pending.cancel();await asyncio.gather(pending,return_exceptions=True)
  agent.stop()

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--session',type=Path,required=True);parser.add_argument('--commander',required=True);parser.add_argument('--library',type=Path,default=default_library());parser.add_argument('--tactical-evidence',type=Path,required=True);parser.add_argument('--production-evidence',type=Path);parser.add_argument('--persistent-evidence',type=Path);parser.add_argument('--output',type=Path,required=True)
 asyncio.run(run(parser.parse_args()))

if __name__=='__main__':main()
