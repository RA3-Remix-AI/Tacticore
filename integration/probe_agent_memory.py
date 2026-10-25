"""Two real default-backend requests with synthetic persistent-mission context.

No game process, actuator, live capability, request body or response body is
accessed or persisted. This checks provider compatibility and agent memory;
only a later live-match audit can establish actual battlefield behavior.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'strategy'))
from battle_agent import BattleAgent,TacticalEvidence,MissionEvidence,MissionObservations
from engine import Binding,StrategyEngine
from http_adapter import load_profile
from model_backend import check_backend_available,create_backend
from mission_audit import context_record
from tactical_fixtures import tactical_snapshot,tactical_policy,intent


async def run(args):
 if not args.real_model:raise ValueError('explicit_real_model_probe_required')
 if args.output.exists():raise ValueError('probe_output_must_be_new')
 check_backend_available('pydantic')
 profile=load_profile(args.library,args.commander)
 session=str(uuid.uuid4())
 binding=Binding(session,3,profile.commander_id,profile.commander_name,profile.connection_id)
 args.output.mkdir(parents=True)
 purposes=(('attack',('main_attack',)),)
 tactical=TacticalEvidence(str(uuid.uuid4()),session,3,'simulated',purposes,(('attack','main_attack',('infantry',)),))
 mission=MissionEvidence(str(uuid.uuid4()),session,3,profile.commander_id,'simulated',purposes)
 engine=StrategyEngine(binding,timeout_seconds=15,max_response_age_seconds=20,audit_path=args.output/'plans.jsonl')
 agent=BattleAgent(engine,event_capacity=8,context_budget_bytes=8192,tactical_evidence=tactical,mission_evidence=mission,memory_path=args.output/'agent-state.json')
 def snapshot(ident,at,events=()):
  value=tactical_snapshot(ident,at);value.update(session_id=session,events=list(events));return value
 async def seed(context):return tactical_policy(context,[intent('attack','main_attack',force_fraction=.5)])
 seeded=await agent.decide(snapshot(1,100),seed)
 if seeded.status!='accepted':raise ValueError('synthetic_seed_rejected')
 task=next(t for t in agent.goals.tasks if t.request.module=='attack')
 agent.host_commit_task(task.task_id,mission_deadline_game_seconds=280,retreat_region='home_base')
 agent.record_feedback(dict(session_id=session,player_id=3,commander_id=profile.commander_id,task_id=task.task_id,status='started',reason_code='ok',at_game_seconds=100,source='simulated',execution=dict(formation_versions=dict(task.request.formation_versions),issued_frame=1500,expires_frame=4200,command_source='simulated',interference='none',goal_observed=False,restoration_verified=False)))
 expected=agent.missions.active[task.task_id].public()
 backend=create_backend(profile,backend='pydantic',max_inflight=1,timeout=12,max_input_bytes=16384,max_tokens=1536)
 contexts=[];decisions=[];started=time.monotonic();error_type=None
 class Capture:
  max_input_bytes=backend.max_input_bytes
  def input_size(self,context):return backend.input_size(context)
  async def __call__(self,context):
   contexts.append(context_record(context,agent.metrics,'simulated'))
   return await backend(context)
 adapter=Capture()
 try:
  for ident,at in ((2,116),(40,170)):
   if ident==40:
    for index in range(3,23):agent.observe(snapshot(index,116+index*2,('phase_changed',)))
   value=snapshot(ident,at);agent.observe(value)
   raw=dict(mission_id=expected['mission_id'],stage='approach',revision=len(decisions)+1,observed_frame=round(at*15),deadline_frame=4200,approach_distance=250,own_hp=100,damage=0,reason='active')
   agent.record_mission_progress(task.task_id,raw,observations=MissionObservations(True,distance_to_goal=250),evidence_sha256='a'*64)
   result=await agent.decide(value,adapter)
   decisions.append(dict(snapshot_id=ident,game_time_seconds=at,status=result.status,reason_code=result.reason_code))
 except Exception as error:
  error_type=type(error).__name__
 finally:
  active=agent.missions.active.get(task.task_id)
  stable=bool(active and all(active.public()[key]==expected[key] for key in ('mission_id','task_id','target_contact_id','formation_versions','deadline_game_seconds')))
  checks=dict(default_backend=backend.backend_name=='pydantic',two_actual_requests=backend.metrics['attempts']==2,two_actual_responses=backend.metrics['responses']==2,no_backend_retries=backend.metrics['retries']==0,both_decisions_accepted=len(decisions)==2 and all(row['status']=='accepted' for row in decisions),event_history_compacted=agent.metrics['compactions']>0,mission_identity_and_deadline_preserved=stable,accepted_post_ttl_context=len(contexts)==2 and len(decisions)==2 and decisions[-1]['status']=='accepted' and contexts[-1]['game_time_seconds']>145 and contexts[-1]['events_compacted']>0 and any(m['mission_id']==expected['mission_id'] and m['deadline_game_seconds']==280 and m['phase']=='approach' for m in contexts[-1]['missions']),bounded_actual_wire=0<backend.metrics['max_request_bytes']<=16384)
  passed=not error_type and all(checks.values())
  report=dict(status='passed' if passed else 'not_passed',scope='real_provider_synthetic_mission_context_only',source='simulated',backend=backend.backend_name,provider=profile.provider,connection_id=profile.connection_id,commander_id=profile.commander_id,session_id=session,library_path=str(args.library.resolve()),checks=checks,decisions=decisions,context_metadata=contexts,transport=dict(backend.metrics),memory=dict(agent.metrics),error_type=error_type,adapter_error_code=backend.last_error_code,elapsed_seconds=round(time.monotonic()-started,3),real_game_commands=0,game_actuator_created=False,actual_battlefield_effect_verified=False)
  (args.output/'probe-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  agent.stop()
 print(json.dumps(dict(status=report['status'],output=str(args.output.resolve()),checks=checks,real_game_commands=0)))
 return 0 if passed else 1


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--library',type=Path,required=True)
 parser.add_argument('--commander',required=True)
 parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--real-model',action='store_true')
 args=parser.parse_args()
 try:return asyncio.run(run(args))
 except Exception as error:
  print(json.dumps(dict(status='not_started',error_type=type(error).__name__,real_game_commands=0)))
  return 2

if __name__=='__main__':raise SystemExit(main())
