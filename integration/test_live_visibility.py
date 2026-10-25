"""Integration boundaries with synthetic memory only; no API/game operations."""
import asyncio
import copy
from contextlib import ExitStack,nullcontext
import json
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

import live_state
import formations
import match_participants
import battle_host

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"strategy"))
from battle_agent import BattleAgent,TacticalEvidence
from engine import Binding,Snapshot,StrategyEngine
from fixtures import SESSION,COMMANDER,CONNECTION
from tactical_fixtures import battlefield,intent,tactical_policy,execution


class Memory:
    def __init__(self):self.frame=1500;self.pause=0;self.closed=0;self.words={0xcd8ce4:0x2000,0x2000:0xbeb630,0x108c:0x3000,0x3010:0x4000,0x8004:0x9000,0x9008:0x1000}
    def u32(self,address):
        if address==0x2050:return self.frame
        if address==0x215c:return self.pause
        return self.words.get(address,0)
    def read(self,*args):raise AssertionError("Unexpected unmocked native read")
    def close(self):self.closed+=1


class Reader:
    def __init__(self):
        self.public=battlefield();self.public["formations"]=[];self.m=None;self.failure=None
        self.private_targets={"contact_ore":{"address":0xdeadbeef,"object_id":9999,"xyz":[800,800,0],"hp":100,"observed_frame":1500}}
        self.region_points={"east_ore":[800,800,0]};self.frontier_points={"north_expansion":[100,200,0]}
        self.frontier_regions=[dict(region_id="north_expansion",relation="unknown",observed_at_game_seconds=100,currently_visible=False,role_counts={})]
        self.vision_metrics={"viewer_player_id":3,"observed_frame":1500,"clear_cell_count":20}
    def collect(self,now):
        if self.failure:raise self.failure
        return copy.deepcopy(self.public)


class RecordedMissionEligibility(unittest.TestCase):
    def test_public_reader_requires_uniform_trusted_executor_scope(self):
        def grant(name=None):
            schema=dict(mission_protocol='continuous_tactical_v1',mission_duration_frames=4500)
            if name:schema['actor_admission_filename']=name
            return dict(stop_schema=schema)
        v2='mission_actor_admission_v2.py';old='mission_actor_admission.py'
        self.assertEqual(battle_host.mission_admission_filename({'grants':[grant(v2),grant(v2)]}),v2)
        for grants in ([],[grant(v2),grant()],[grant(v2),grant(old)],[grant('../reader.py')]):
            self.assertEqual(battle_host.mission_admission_filename({'grants':grants}),old)
        self.assertEqual(battle_host.mission_admission_filename(None),old)

    def test_real_idle_positives_and_garrison_state10_negatives(self):
        runs=Path(__file__).resolve().parents[1]/'acceptance/runs'
        positive=runs/'20261025-131138-commander/admission-early01.json'
        negative=runs/'20261025-135011-commander/admission-paused02.json'
        if not positive.exists() or not negative.exists():self.skipTest('Recorded own admission samples unavailable')
        groups=[([r['admission'] for r in json.loads(positive.read_text())['rows']],True),
                (json.loads(negative.read_text())['rows'],False)]
        for records,expected in groups:
            for record in records:
                ground=record.get('grounded_status',{})
                candidate={key:record.get(key,ground.get(key)) for key in ('object_id','address','type_hash')}
                candidate['ai_address']=record.get('state_snapshot',{}).get('update','0x0')
                owner=int(record.get('owner',ground.get('owner')),0)
                with self.subTest(object_id=candidate['object_id'],expected=expected):
                    with patch.object(live_state._admission_module,'actor_admission',return_value=record):
                        self.assertEqual(live_state.mission_actor_eligible(object(),candidate,owner),expected)
                        self.assertFalse(live_state.mission_actor_eligible(object(),candidate,owner+4))


class LiveVisibility(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.memory=Memory();self.reader=Reader()
        state=self.state=live_state.LiveBattleState.__new__(live_state.LiveBattleState)
        state.session_path=self.root/"session.json";registry=self.root/"registry.json";registry.write_text("{}",encoding="utf-8")
        state.session=dict(session_id=SESSION,pid=123,mod_sha256="a"*64,registry=str(registry),scenario={})
        state.session_raw=json.dumps(state.session).encode();state.session_path.write_bytes(state.session_raw)
        state.registry_raw=registry.read_bytes();state.registry={};state.catalog={};state.commander_id=COMMANDER;state.player_id=3;state.foci=("native_baseline","anti_air")
        state.output=self.root;state.visibility_enabled=True;state.visibility_reader=self.reader;state.visibility_proof_path=None
        state.owner=None;state.ai=None;state.logic=None;state.map=None;state.last_frame=None;state.sequence=0;state.native=None;state.latest_snapshot_path=None;state.participant_identity=None
        state.known_regions={"home_base"};state.required_regions=set();state.formations=formations.FormationRegistry(SESSION)
        state.private_formations={};state.private_regions={};state.private_targets={}
        self.units=[dict(object_id=i,type_hash="0x19ab11af" if i<7 else "0x2c358c61",hp=100,xyz=[20+i,30,0],template_annotation="SovietConscript" if i<7 else "SovietFlakTrooper") for i in range(1,8)]
        self.own=dict(game_logic="0x2000",logic_frame_candidate=1500,pause_type_candidate=0,map_path="synthetic.map",resources={"address":"0x1000","display_sum":5000},own_objects=copy.deepcopy(self.units)+[dict(object_id=100,type_hash="0xabc",hp=100,xyz=[50,50,0],template_annotation="SovietConstructionYard")],factories=[])
        candidates=[]
        for unit in self.units:
            address=0x10000+unit["object_id"]*0x100;update=address+0x10000
            candidates.append(dict(object_id=unit["object_id"],owner_address="0x1000",owner_index_candidate=3,type_hash=unit["type_hash"],address=hex(address),ai_address=hex(update)))
            self.memory.words[address+0x414]=0x8000;self.memory.words[update+8]=address
            self.memory.words[address]=0xc4db60;self.memory.words[address+0xdc]=unit['object_id'];self.memory.words[address+0x418]=0x1000
        self.raw=dict(candidate_count=len(candidates),candidates=candidates,frame_start=1500,frame_end=1500,source="native_live_list_own_only")

    def tearDown(self):self.temp.cleanup()

    def collect(self,sample_effect=None):
        def sample(*args):
            result=copy.deepcopy(self.own)
            if sample_effect:sample_effect()
            return result
        with ExitStack() as stack:
            stack.enter_context(patch.object(live_state,"Memory",return_value=self.memory))
            stack.enter_context(patch.object(live_state,"own_candidates",return_value=copy.deepcopy(self.raw)))
            stack.enter_context(patch.object(live_state,"inspect_player",return_value={"ai_player":"0xabc","player_index":3}))
            stack.enter_context(patch.object(live_state,"resolve_registry",return_value={"personality_binding_verified":True,"commander_id":COMMANDER}))
            stack.enter_context(patch.object(live_state,"match_snapshot",return_value={"simulation_frame":self.memory.frame,"mode_raw":2,"result_records":[]}))
            stack.enter_context(patch.object(live_state,"sample",side_effect=sample))
            return self.state.collect()

    def test_garrison_immobile_and_script_holder_troops_are_not_mobile_cohorts(self):
        self.memory.words[0x10100+0x84]=0x20000000
        self.memory.words[0x10200+0x84]=0x80000
        self.memory.words[0x10300+0x238]=0xdeadbeef
        snapshot=self.collect()
        raw=json.loads((self.root/'own-candidates.json').read_text(encoding='utf-8'))
        self.assertEqual(raw['sha256'],live_state.EXPECTED)
        ids={oid for value in self.state.private_formations.values() for oid in value['object_ids']}
        self.assertEqual(ids,{4,5,6,7})
        self.assertEqual(snapshot['production']['own_roles']['infantry'],6)

    def test_continuous_missions_advertise_only_current_admissible_actors(self):
        self.state.mission_history=True;self.state.session['run_directory']=str(self.root)
        self.state.session_raw=json.dumps(self.state.session).encode();self.state.session_path.write_bytes(self.state.session_raw)
        with patch.object(live_state,'mission_actor_eligible',side_effect=lambda memory,candidate,owner:candidate['object_id'] in {4,5,6,7}) as admission:
            snapshot=self.collect()
        ids={oid for value in self.state.private_formations.values() for oid in value['object_ids']}
        self.assertEqual(ids,{4,5,6,7});self.assertEqual(admission.call_count,7)
        self.assertEqual(snapshot['production']['own_roles']['infantry'],6)
        self.assertEqual(sum(f['roles'].get('infantry',0) for f in snapshot['battlefield']['formations']),3)

    def test_new_trusted_reader_is_used_for_public_cohorts_only_when_selected(self):
        self.state.mission_history=True;self.state.session['run_directory']=str(self.root)
        self.state.mission_admission_module=object()
        self.state.session_raw=json.dumps(self.state.session).encode();self.state.session_path.write_bytes(self.state.session_raw)
        with patch.object(live_state,'mission_actor_eligible',return_value=True) as admission:self.collect()
        self.assertEqual(admission.call_count,7)
        self.assertTrue(all(call.args[3] is self.state.mission_admission_module for call in admission.call_args_list))

    def test_admission_scan_clock_change_discards_snapshot(self):
        self.state.mission_history=True
        def admitted(*args):self.memory.frame+=4;return True
        with patch.object(live_state,'mission_actor_eligible',side_effect=admitted):
            with self.assertRaises(live_state.RetryableSample):self.collect()

    def test_admission_clock_rollback_is_fatal(self):
        self.state.mission_history=True
        def admitted(*args):self.memory.frame=1499;return True
        with patch.object(live_state,'mission_actor_eligible',side_effect=admitted):
            try:self.collect()
            except live_state.RetryableSample:self.fail('Admission clock rollback was retried')
            except ValueError:pass
            else:self.fail('Admission clock rollback accepted')

    def test_public_snapshot_is_typed_and_private_addresses_never_cross_model_boundary(self):
        raw=self.collect();parsed=Snapshot.from_dict(raw)
        self.assertEqual(raw["game_time_seconds"],100);self.assertEqual(raw["battlefield"]["viewer_player_id"],3)
        agent=BattleAgent(StrategyEngine(Binding(SESSION,3,COMMANDER,"synthetic",CONNECTION)));agent.observe(parsed)
        text=json.dumps(agent.context(parsed.model_context(agent.engine.binding)))
        for key in ['"object_ids"','"object_id"','"address"','"xyz"','"hp"',"deadbeef"]:self.assertNotIn(key,text)
        self.assertEqual(self.state.private_targets["contact_ore"]["address"],0xdeadbeef)
        self.assertTrue(self.state.private_formations);self.assertTrue(self.state.private_regions)
        self.assertGreaterEqual(self.memory.closed,3)

    def test_last_seen_region_and_active_target_survive_history_capacity_pruning(self):
        self.state.known_regions.update("historical_"+str(i) for i in range(400))
        self.state.required_regions={"active_target"}
        first=self.collect();self.assertLessEqual(len(first["capabilities"]["regions"]),256)
        self.memory.frame=1515;self.own["logic_frame_candidate"]=1515
        self.reader.public["regions"]=[];self.reader.public["contacts"][0]["currently_visible"]=False
        self.reader.private_targets={};self.reader.region_points={}
        second=self.collect();Snapshot.from_dict(second)
        self.assertIn("east_ore",second["capabilities"]["regions"]);self.assertIn("active_target",second["capabilities"]["regions"])
        self.assertLessEqual(len(second["capabilities"]["regions"]),256)
        self.assertEqual(self.state.private_targets,{})
        self.assertNotIn("east_ore",self.state.private_regions)

    def test_stale_own_frame_and_pause_transition_discard_composite_sample(self):
        self.own["logic_frame_candidate"]=1490
        with self.assertRaises(live_state.RetryableSample):self.collect()
        self.own["logic_frame_candidate"]=1500
        with self.assertRaises(live_state.RetryableSample):self.collect(sample_effect=lambda:setattr(self.memory,"pause",1))

    def test_retryable_visibility_failure_clears_old_private_targets(self):
        self.collect();self.assertTrue(self.state.private_targets)
        self.reader.failure=ValueError("Non-atomic visibility snapshot changed; discard whole sample")
        with self.assertRaises(live_state.RetryableSample):self.collect()
        self.assertEqual(self.state.private_targets,{})

    def test_binding_change_is_fatal_and_is_not_reclassified_as_retryable(self):
        self.state.session_path.write_text("{}",encoding="utf-8")
        try:self.collect()
        except live_state.RetryableSample:self.fail("A changed session was swallowed as transient")
        except ValueError:pass
        else:self.fail("Changed session accepted")

    def test_native_memory_read_unavailable_is_retryable_but_read_bounds_is_fatal(self):
        self.reader.failure=RuntimeError("Read unavailable")
        with self.assertRaises(live_state.RetryableSample):self.collect()
        self.reader.failure=RuntimeError("Read bounds")
        try:self.collect()
        except live_state.RetryableSample:self.fail("A read-bounds programming error was swallowed")
        except RuntimeError:pass
        else:self.fail("Out-of-bounds native read accepted")

    def test_backward_frame_between_own_and_visibility_sample_is_fatal(self):
        self.own["logic_frame_candidate"]=1510
        try:self.collect()
        except live_state.RetryableSample:self.fail("A simulation clock rollback was retried")
        except ValueError:pass
        else:self.fail("Newer own data was silently bound to an older vision clock")

    async def test_reserved_casualties_keep_feedback_version_without_recruiting_other_roster(self):
        first=self.collect();main=next(f for f in first["battlefield"]["formations"] if len(f["roles"])==2)
        held=set(self.state.private_formations[main["formation_id"]]["object_ids"])
        binding=Binding(SESSION,3,COMMANDER,"synthetic",CONNECTION)
        agent=BattleAgent(StrategyEngine(binding),tactical_evidence=TacticalEvidence("bfd5c276-1911-4594-bb43-a70a4f915fe9",SESSION,3,"game_bridge",(("attack",("main_attack",)),)))
        async def model(context):return tactical_policy(context,[intent(formation_ids=[main["formation_id"]])])
        await agent.decide(first,model)
        task=next(t for t in agent.goals.tasks if t.request.module=="attack")
        value=dict(session_id=SESSION,player_id=3,commander_id=COMMANDER,task_id=task.task_id,status="started",reason_code="ok",at_game_seconds=100,source="game_bridge",execution=execution(task,command_source="game_thread_bridge"))
        agent.record_feedback(value);self.state.formations.reserve([main["formation_id"]])
        self.own["own_objects"]=[obj for obj in self.own["own_objects"] if obj["object_id"] not in held]
        self.memory.frame=1515;self.own["logic_frame_candidate"]=1515
        self.reader.public["contacts"][0]["observed_at_game_seconds"]=101
        second=self.collect();agent.observe(second)
        self.assertNotIn(main["formation_id"],{f["formation_id"] for f in second["battlefield"]["formations"]})
        self.assertEqual(self.state.private_formations[main["formation_id"]]["version"],main["version"])
        for fid,private in self.state.private_formations.items():
            if fid!=main["formation_id"]:self.assertFalse(set(private["object_ids"])&held)
        value.update(status="failed",reason_code="goal_unobserved",at_game_seconds=101,execution=execution(task,command_source="game_thread_bridge",restoration_verified=True))
        agent.record_feedback(value)
        self.assertEqual(task.status,"failed");self.assertEqual(agent.public_memory()["recent_execution_feedback"][-1]["task_id"],task.task_id)


class OpponentRelations(unittest.TestCase):
    def test_two_ai_must_be_mutual_enemies_not_merely_distinct_ai_players(self):
        words={0xce8c9c:0x1000,0x1038:0x2000,0x103c:0x3000,0x1040:0x4000,0x2000:0xc5bce0,0x2020:2,0x2090:0}
        memory=types.SimpleNamespace(u32=lambda address:words.get(address,0),read=lambda *args:None)
        state={"victory_conditions":{"participants":[{"player_index":3,"player":"0x3000"},{"player_index":4,"player":"0x4000"}]}}
        identities={0x3000:{"player_index":3,"instance_id":"0x1234"},0x4000:{"player_index":4,"instance_id":"0x5678"}}
        registry={"commanders":[{"assets":[{"instance_id":"0x1234"}]}]}
        for relations in [("enemy","enemy"),("ally","enemy"),("enemy","ally")]:
            with patch.object(match_participants,"inspect_player",side_effect=lambda read,address:identities[address]),patch.object(match_participants,"read_player_relation",side_effect=relations):
                if relations==("enemy","enemy"):self.assertTrue(match_participants.verify_two_ai(memory,state,registry,3,4)["mutual_enemy_relationship_verified"])
                else:
                    with self.subTest(relations=relations),self.assertRaises(ValueError):match_participants.verify_two_ai(memory,state,registry,3,4)


class SamplingContinuity(unittest.IsolatedAsyncioTestCase):
    async def run_host(self,steps,result_candidate=False):
        host=battle_host.Host.__new__(battle_host.Host);calls=[];events=[];published=[]
        snapshot=dict(snapshot_id=1,game_time_seconds=100,paused=False)
        sequence=iter(steps)
        def collect():
            calls.append("collect");value=next(sequence)
            if isinstance(value,Exception):raise value
            host.collector.private_targets={"fresh_target":{}};return copy.deepcopy(snapshot)
        host.binding=types.SimpleNamespace(session_id=SESSION,player_id=3,commander_id=COMMANDER)
        host.collector=types.SimpleNamespace(collect=collect,private_targets={"old_target":{}},native={"result_records":[]})
        host.session={"scenario":{}};host.engine=types.SimpleNamespace(metrics={});host.agent=types.SimpleNamespace(observe=lambda value:calls.append("observe"),stop=lambda:calls.append("stop"))
        async def decide(*args):return types.SimpleNamespace(status="held",reason_code="minimum_hold")
        host.agent.decide=decide;host.adapter=None
        host.args=types.SimpleNamespace(execute=False,wait_for_match=False,max_wall_seconds=1,interval=.01)
        host.started=time.monotonic();host.phase="initializing";host.reason="not_started";host.last_snapshot=None;host.last_result=None
        host.pending=None;host.executor=None;host.executor_ready=False;host.observer=None;host.observer_output=None
        host.counters={};host.output=Path("synthetic-no-io");host.stop_requested=lambda:False;host.event=lambda kind,**values:events.append(dict(kind=kind,**values))
        host.publish=lambda:published.append(dict(state=host.phase,private_targets=copy.deepcopy(host.collector.private_targets)))
        async def no_operation():calls.append("native_boundary")
        async def dispatch():calls.append("dispatch")
        async def result():return result_candidate
        host.connect_executor=no_operation;host.receive_receipts=no_operation;host.dispatch=dispatch;host.read_result_candidate=result
        sleep=asyncio.sleep;waits=[]
        async def fast_sleep(duration):waits.append(duration);await sleep(0)
        with patch.object(battle_host,"player_lease",return_value=nullcontext()),patch.object(battle_host.asyncio,"sleep",side_effect=fast_sleep):outcome=await host.run()
        return outcome,calls,events,published,waits

    async def test_retryable_sample_does_not_dispatch_or_consume_old_private_lookup(self):
        outcome,calls,events,published,waits=await self.run_host([live_state.RetryableSample("non_atomic_sample_discarded"),True,ValueError("Match lifecycle changed")])
        self.assertEqual(calls.count("dispatch"),1);self.assertEqual(calls.count("observe"),1)
        retries=[e for e in events if e["kind"]=="sample_retry"]
        self.assertEqual(len(retries),1)
        self.assertEqual(next(p for p in published if p["state"]=="sampling_wait")["private_targets"],{})
        self.assertEqual(outcome["state"],"fault")  # The final real lifecycle change remains fatal.

    async def test_consecutive_retry_limit_is_bounded(self):
        outcome,calls,events,published,waits=await self.run_host([live_state.RetryableSample("non_atomic_sample_discarded") for _ in range(6)])
        self.assertEqual(calls.count("collect"),6);self.assertNotIn("dispatch",calls)
        self.assertEqual(len([e for e in events if e["kind"]=="sample_retry"]),5)
        self.assertEqual(waits,[.2]*5);self.assertEqual(outcome["state"],"fault")

    async def test_success_resets_retry_budget_but_identity_failure_is_never_retried(self):
        discarded=[live_state.RetryableSample("non_atomic_sample_discarded") for _ in range(5)]
        outcome,calls,events,published,waits=await self.run_host(discarded+[True]+discarded+[ValueError("Registry changed")])
        retries=[e["consecutive"] for e in events if e["kind"]=="sample_retry"]
        self.assertEqual(retries,[1,2,3,4,5,1,2,3,4,5]);self.assertEqual(calls.count("dispatch"),1)
        outcome,calls,events,published,waits=await self.run_host([ValueError("Registry changed")])
        self.assertEqual(waits,[]);self.assertNotIn("dispatch",calls);self.assertEqual(outcome["state"],"fault")

    async def test_result_candidate_takes_priority_over_transient_retry(self):
        outcome,calls,events,published,waits=await self.run_host([live_state.RetryableSample("non_atomic_sample_discarded")],True)
        self.assertEqual(outcome["state"],"result_candidate");self.assertEqual(waits,[])
        self.assertNotIn("dispatch",calls);self.assertFalse(any(e["kind"]=="sample_retry" for e in events))


if __name__=="__main__":unittest.main(verbosity=2)
