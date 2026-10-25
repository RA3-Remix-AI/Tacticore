"""No SDK/network: pure audit negatives and actual session-context persistence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from mission_audit import analyze,context_record
import test_missions as mission_fixtures
from tactical_fixtures import tactical_snapshot,tactical_policy


class Audit(unittest.TestCase):
    def fixture(self):
        session=dict(session_id='session',pid=123,scenario={'commander_id':'commander'})
        ident=dict(session_id='session',pid=123,binding={'commander_id':'commander'},native={'player_index':3})
        task=uuid.uuid4().hex;command=str(uuid.uuid4())
        entry=dict(mission_protocol='continuous_tactical_v1',command_id=command,module='attack',purpose='main_attack',queued=True,started=True,terminal=True,object_ids=[7],dispatch_frame=1500,expires_frame=4200,model_plan_id='p1',model_plan_generation=1,model_plan_expires_game_seconds=145,target_contact_id='contact_ore')
        bound=dict(session_id='session',player_id=3,commander_id='commander')
        def event(kind,wall,**kw):return dict(bound,kind=kind,wall_seconds=wall,**kw)
        events=[event('host_started',0),event('tactical_dispatch_accepted',1,task_id=task,command_id=command),event('tactical_task_feedback',2,task_id=task,status='started'),event('mission_progress_observed',3,task_id=task,command_id=command,module='attack',stage='approach',revision=1,observed_frame=1600,deadline_frame=4200),event('mission_progress_observed',20,task_id=task,command_id=command,module='attack',stage='restored',revision=2,observed_frame=2800,deadline_frame=4200),event('tactical_task_feedback',21,task_id=task,status='completed'),event('host_stopped',22)]
        item=dict(task_id=task,mission_id=str(uuid.UUID(task)),module='attack',purpose='main_attack',target_contact_id='contact_ore',deadline_game_seconds=280,phase='approach',progress_seq=1)
        contexts=[dict(bound,source='game_bridge',snapshot_id=2,game_time_seconds=160,events_compacted=5,missions=[item])]
        plans=[dict(bound,event='request',request_id='r',snapshot_id=2,game_time_seconds=160),dict(bound,event='plan_accepted',request_id='r',plan_id='p2')]
        return [session,ident,{task:entry},[{'task_id':task,'status':'completed'}],events,contexts,plans,{'metrics':{'compactions':5}}]

    def test_cross_ttl_request_and_compression_have_distinct_evidence(self):
        a=analyze(*self.fixture());self.assertTrue(a['metadata_lifecycle_verified']);m=a['missions'][0]
        self.assertTrue(m['cross_original_plan_ttl']);self.assertTrue(m['context_preserved_after_original_ttl']);self.assertTrue(m['context_preserved_during_compression']);self.assertEqual(m['other_accepted_plans_during_mission'],1)
        self.assertEqual(m['accepted_post_ttl_compressed_contexts_with_mission'],1)

    def test_failed_post_ttl_context_cannot_borrow_earlier_accepted_plan(self):
        args=self.fixture();bound=dict(session_id='session',player_id=3,commander_id='commander')
        args[6][1]=dict(bound,event='request',request_id='earlier',snapshot_id=1,game_time_seconds=120)
        args[6].append(dict(bound,event='plan_accepted',request_id='earlier',plan_id='p2'))
        m=analyze(*args)['missions'][0]
        self.assertTrue(m['context_preserved_after_original_ttl']);self.assertEqual(m['other_accepted_plans_during_mission'],1)
        self.assertEqual(m['accepted_post_ttl_compressed_contexts_with_mission'],0)

    def test_ambiguous_retry_key_cannot_be_correlated_as_accepted_context(self):
        args=self.fixture();args[6].append(dict(args[6][0],request_id='retry'))
        self.assertEqual(analyze(*args)['missions'][0]['accepted_post_ttl_contexts_with_mission'],0)

    def test_old_run_without_request_audit_never_implies_model_memory(self):
        args=self.fixture();args[5]=[];a=analyze(*args)
        self.assertIn('request_context_metadata_unavailable',a['observability_gaps']);self.assertFalse(a['missions'][0]['context_preserved_after_original_ttl'])

    def test_actual_request_cannot_silently_forget_active_mission(self):
        args=self.fixture();args[5][0]['missions']=[]
        self.assertTrue(any(e['code']=='mission_missing_from_actual_request_context' for e in analyze(*args)['errors']))

    def test_new_deadline_target_or_mission_in_context_is_rejected(self):
        for key,value in [('deadline_game_seconds',300),('target_contact_id','contact_other'),('mission_id',str(uuid.uuid4()))]:
            args=self.fixture();args[5][0]['missions'][0][key]=value;self.assertFalse(analyze(*args)['metadata_lifecycle_verified'])

    def test_duplicate_dispatch_and_progress_regression_are_rejected(self):
        args=self.fixture();args[4].insert(2,copy.deepcopy(args[4][1]));self.assertFalse(analyze(*args)['metadata_lifecycle_verified'])
        args=self.fixture();args[4][4]['revision']=1;self.assertFalse(analyze(*args)['metadata_lifecycle_verified'])

    def test_other_actor_lease_cannot_begin_before_release(self):
        args=self.fixture();task,entry=next(iter(args[2].items()));other=uuid.uuid4().hex;newcommand=str(uuid.uuid4());args[2][other]=dict(entry,command_id=newcommand)
        bound=dict(session_id='session',player_id=3,commander_id='commander')
        args[4].extend([dict(bound,kind='tactical_dispatch_accepted',wall_seconds=10,task_id=other,command_id=newcommand),dict(bound,kind='tactical_task_feedback',wall_seconds=11,task_id=other,status='started'),dict(bound,kind='tactical_task_feedback',wall_seconds=30,task_id=other,status='failed')]);args[3].append(dict(task_id=other,status='failed'))
        self.assertTrue(any(e['code']=='actor_lease_overlap' for e in analyze(*args)['errors']))
        # Even if native issuance waits until after the old lease, its earlier
        # accepted reservation must not steal the still-reserved roster.
        args[4][-2]['wall_seconds']=23
        self.assertTrue(any(e['code']=='actor_lease_overlap' for e in analyze(*args)['errors']))
        args[4][-3]['wall_seconds']=22;args[4][-2]['wall_seconds']=23
        self.assertFalse(any(e['code']=='actor_lease_overlap' for e in analyze(*args)['errors']))

    def test_foreign_records_or_nonterminal_stop_cannot_pass(self):
        args=self.fixture();args[5][0]['commander_id']='foreign'
        with self.assertRaisesRegex(ValueError,'audit_record_binding'):analyze(*args)
        args=self.fixture();next(iter(args[2].values()))['terminal']=False;self.assertFalse(analyze(*args)['metadata_lifecycle_verified'])


class ActualContext(unittest.IsolatedAsyncioTestCase):
    async def test_actual_adapter_sees_same_mission_after_compaction_and_plan_refresh(self):
        fixture=mission_fixtures.Missions();agent,task=await fixture.create();fixture.commit(agent,task)
        with tempfile.TemporaryDirectory() as folder:
            agent.context_audit_path=Path(folder)/'context.jsonl'
            for i in range(1,51):fixture.observe_progress(agent,task,fixture.progress(agent,task,'approach',i,100+i))
            async def adapter(payload):return tactical_policy(payload,[])
            for at in [151,200]:self.assertEqual((await agent.decide(tactical_snapshot(int(at*10),at),adapter)).status,'accepted')
            records=[json.loads(x) for x in agent.context_audit_path.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(records),2)
            for r in records:
                self.assertGreater(r['events_compacted'],0);self.assertEqual(r['missions'][0]['task_id'],task.task_id);self.assertEqual(r['missions'][0]['progress_seq'],50);self.assertEqual(r['missions'][0]['deadline_game_seconds'],280)
            self.assertEqual(agent.pending_mission_retreats(),[])

    async def test_metadata_allowlist_does_not_log_payload_text_secrets_or_coordinates(self):
        fixture=mission_fixtures.Missions();agent,task=await fixture.create();fixture.commit(agent,task)
        payload=agent.context(agent.latest.model_context(agent.engine.binding));payload['secret']='NEVER_LOG_THIS';payload['xyz']=[987654,987654,987654]
        record=context_record(payload,agent.metrics,'simulated');encoded=json.dumps(record)
        self.assertNotIn('NEVER_LOG_THIS',encoded);self.assertNotIn('987654',encoded);self.assertNotIn('working_memory',record);self.assertEqual(len(record['payload_sha256']),64)


if __name__=='__main__':unittest.main()
