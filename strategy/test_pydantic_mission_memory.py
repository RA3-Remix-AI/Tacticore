"""Actual default Pydantic path with MockTransport; no library/game/network I/O.

All missions and execution observations are explicitly simulated. Passing this
cannot establish real game context retention, effects or capability evidence.
"""
import json
import asyncio
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'agent_runtime/src'))
import httpx2
from tacticore_agent_runtime.factory import create_backend,DEFAULT_BACKEND
from battle_agent import BattleAgent,TacticalEvidence,MissionEvidence,MissionObservations
from engine import StrategyEngine
from fixtures import binding,SESSION,COMMANDER,CONNECTION
from tactical_fixtures import tactical_snapshot,tactical_policy,intent
from http_adapter import Profile,Endpoint

class PersistentPydantic(unittest.IsolatedAsyncioTestCase):
 def agent(self,folder):
  proof=TacticalEvidence(str(uuid.uuid4()),SESSION,3,'simulated',(('raid',('harass_economy',)),),(('raid','harass_economy',('infantry',)),))
  grant=MissionEvidence(str(uuid.uuid4()),SESSION,3,COMMANDER,'simulated',(('raid',('harass_economy',)),))
  return BattleAgent(StrategyEngine(binding()),tactical_evidence=proof,mission_evidence=grant,event_capacity=4,dialogue_turns=2,memory_path=Path(folder)/'agent-state.json')
 def backend(self,seen,failures,*,timeout=12):
  async def transport(request):
   wire=json.loads(request.content);ctx=json.loads(wire['messages'][-1]['content']);seen.append(ctx)
   mode=failures.pop(0) if failures else None
   if mode=='timeout':await asyncio.sleep(2)
   elif mode:return httpx2.Response(429,json={'error':{'message':'FAKE-PRIVATE-PROVIDER-DETAIL'}})
   answer=tactical_policy(ctx,[intent('raid','harass_economy',required_roles=['infantry'],force_fraction=.5)])
   return httpx2.Response(200,json={'id':'offline','object':'chat.completion','created':1,'model':'fixture-model','choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(answer)}}]})
  profile=Profile(COMMANDER,'Synthetic only',CONNECTION,'DeepSeek','fixture-model',0,'',Endpoint.parse('https://fixture.invalid/v1'),'FAKE-NO-REAL-KEY')
  return create_backend(profile,transport=httpx2.MockTransport(transport),timeout=timeout),transport
 def feedback(self,agent,task,status,restored=False):
  return dict(session_id=SESSION,player_id=3,commander_id=COMMANDER,task_id=task.task_id,status=status,reason_code='ok' if status=='started' else 'goal_unobserved',at_game_seconds=agent.latest.game_time_seconds,source='simulated',execution=dict(formation_versions=dict(task.request.formation_versions),issued_frame=1500,expires_frame=4200,command_source='simulated',interference='none',goal_observed=False,restoration_verified=restored))
 def progress(self,agent,task,revision,at,stage='approach'):
  agent.observe(tactical_snapshot(round(at*10),at))
  raw=dict(mission_id=agent.missions.active[task.task_id].mission_id,stage=stage,revision=revision,observed_frame=round(at*15),deadline_frame=4200,approach_distance=250,own_hp=100,damage=0,reason='active')
  agent.record_mission_progress(task.task_id,raw,observations=MissionObservations(target_currently_visible=True,distance_to_goal=250),evidence_sha256='a'*64)
 async def start(self,agent,backend):
  result=await agent.decide(tactical_snapshot(),backend);self.assertEqual(result.status,'accepted')
  task=next(t for t in agent.goals.tasks if t.request.module=='raid')
  agent.host_commit_task(task.task_id,mission_deadline_game_seconds=280,retreat_region='home_base')
  agent.record_feedback(self.feedback(agent,task,'started'));return task
 async def test_same_mission_crosses_plans_ttl_compaction_then_keeps_failed_result(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(httpx2.AsyncHTTPTransport,'handle_async_request',side_effect=AssertionError('external network forbidden')):
   seen=[];backend,_=self.backend(seen,[]);self.assertEqual(DEFAULT_BACKEND,'pydantic');agent=self.agent(folder);task=await self.start(agent,backend)
   original_plan=task.plan_id;ttl=agent.engine.current.expires_at_game_seconds
   accepted=[]
   for revision,at in enumerate((116,132,148,164,180,196),1):
    self.progress(agent,task,revision,at)
    result=await agent.decide(tactical_snapshot(round(at*10)+1,at),backend)
    if result.status=='accepted':accepted.append(result)
    jobs=agent.jobs()['jobs'];matching=[j for j in jobs if j['task_id']==task.task_id]
    self.assertEqual(len(matching),1);self.assertFalse(matching[0]['host_dispatch_candidate']);self.assertEqual(task.plan_id,original_plan)
   self.assertGreaterEqual(len(accepted),3);self.assertGreater(agent.metrics['compactions'],0)
   later=[c for c in seen if c['game_time_seconds']>ttl]
   self.assertTrue(later)
   for ctx in later:
    active=ctx['working_memory']['persistent_missions']['active'];same=[m for m in active if m['task_id']==task.task_id]
    self.assertEqual(len(same),1);self.assertEqual(same[0]['mission_id'],str(uuid.UUID(task.task_id)));self.assertEqual(same[0]['target_contact_id'],'contact_ore');self.assertEqual(same[0]['deadline_game_seconds'],280)
    self.assertGreater(ctx['working_memory']['compressed_history']['events_compacted'],0);self.assertNotIn('units',ctx);self.assertNotIn('addresses',ctx)
   self.progress(agent,task,7,210,'restored')
   agent.certify_mission_result(task.task_id,observations=MissionObservations(False,approach_verified=True,restoration_verified=True,distance_to_goal=250),evidence_sha256='b'*64)
   agent.record_feedback(self.feedback(agent,task,'failed',restored=True))
   await agent.decide(tactical_snapshot(2320,232),backend)
   self.assertEqual(agent.missions.coverage['raid']['completed'],0);self.assertTrue(seen[-1]['working_memory']['failure_memory'])
   metadata=(Path(folder)/'agent-state.context-audit.jsonl').read_text(encoding='utf-8')
   self.assertNotIn('FAKE-NO-REAL-KEY',metadata);self.assertNotIn('FAKE-PRIVATE-PROVIDER-DETAIL',metadata);self.assertNotIn('messages',metadata)
   self.assertTrue(any(c['game_time_seconds']>ttl and c['missions'] for c in map(json.loads,metadata.splitlines())))
 async def test_single_provider_failure_does_not_replace_or_release_active_mission(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(httpx2.AsyncHTTPTransport,'handle_async_request',side_effect=AssertionError('external network forbidden')):
   seen=[];failures=[];backend,_=self.backend(seen,failures);agent=self.agent(folder);task=await self.start(agent,backend)
   self.progress(agent,task,1,140);failures.append(True)
   result=await agent.decide(tactical_snapshot(1401,140),backend)
   self.assertNotEqual(result.status,'accepted');self.assertEqual(backend.metrics['attempts'],2);self.assertEqual(backend.metrics['retries'],0)
   self.assertIn(task.task_id,agent.missions.active);self.assertEqual(agent.missions.active[task.task_id].deadline_game_seconds,280);self.assertEqual(agent.missions.coverage['raid']['completed'],0)
   self.progress(agent,task,2,156);result=await agent.decide(tactical_snapshot(1561,156),backend);self.assertEqual(result.status,'accepted')
   active=seen[-1]['working_memory']['persistent_missions']['active'];self.assertEqual([m['task_id'] for m in active],[task.task_id]);self.assertEqual(task.status,'active');self.assertFalse(next(j for j in agent.jobs()['jobs'] if j['task_id']==task.task_id)['host_dispatch_candidate'])


 async def test_timeout_is_single_cancelled_request_and_keeps_mission_for_next_plan(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(httpx2.AsyncHTTPTransport,'handle_async_request',side_effect=AssertionError('external network forbidden')):
   seen=[];normal,_=self.backend(seen,[]);agent=self.agent(folder);task=await self.start(agent,normal)
   self.progress(agent,task,1,150)
   slow,_=self.backend(seen,['timeout'],timeout=.02)
   result=await agent.decide(tactical_snapshot(1501,150),slow)
   self.assertNotEqual(result.status,'accepted');self.assertEqual(slow.metrics['attempts'],1);self.assertEqual(slow.metrics['retries'],0);self.assertEqual(slow.metrics['timeouts'],1)
   self.assertEqual(slow.last_error_code,'deadline_exceeded');self.assertIn(task.task_id,agent.missions.active);self.assertEqual(task.status,'active')
   self.progress(agent,task,2,166);result=await agent.decide(tactical_snapshot(1661,166),normal);self.assertEqual(result.status,'accepted')
   self.assertEqual([m['task_id'] for m in seen[-1]['working_memory']['persistent_missions']['active']],[task.task_id]);self.assertEqual(agent.missions.active[task.task_id].deadline_game_seconds,280);self.assertFalse(agent.pending_mission_retreats())

if __name__=='__main__':unittest.main()
