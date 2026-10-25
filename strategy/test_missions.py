"""Synthetic continuous missions; no controller, HTTP, credentials or game I/O."""
import copy
import json
from dataclasses import replace
import unittest
import uuid

from battle_agent import BattleAgent,TacticalEvidence,MissionEvidence,MissionObservations
from engine import ContractError,StrategyEngine
from fixtures import binding,SESSION,CONNECTION
from http_adapter import tactical_example,ChatAdapter,Profile,Endpoint
from tactical_fixtures import tactical_snapshot,tactical_policy,intent

SHA='a'*64


class Missions(unittest.IsolatedAsyncioTestCase):
    async def create(self,module='raid',purpose='harass_economy',*,mission=True):
        roles=('infantry','anti_air') if module=='combined_arms' else ('infantry',)
        proof=TacticalEvidence(str(uuid.uuid4()),SESSION,3,'simulated',((module,(purpose,)),),((module,purpose,roles),))
        grant=MissionEvidence(str(uuid.uuid4()),SESSION,3,binding().commander_id,'simulated',((module,(purpose,)),)) if mission else None
        agent=BattleAgent(StrategyEngine(binding()),tactical_evidence=proof,mission_evidence=grant)
        async def model(context):return tactical_policy(context,[intent(module,purpose,required_roles=list(roles),force_fraction=.5)])
        self.assertEqual((await agent.decide(tactical_snapshot(),model)).status,'accepted')
        task=next(t for t in agent.goals.tasks if t.request.module==module)
        return agent,task

    def commit(self,agent,task):return agent.host_commit_task(task.task_id,mission_deadline_game_seconds=280,retreat_region='home_base')

    def advance(self,agent,at):
        agent.observe(tactical_snapshot(int(at*10),at))

    def progress(self,agent,task,phase,revision,at,damage=0,**updates):
        self.advance(agent,at);mission=agent.missions.active[task.task_id]
        raw=dict(mission_id=mission.mission_id,stage=phase,revision=revision,observed_frame=round(at*15),deadline_frame=4200,approach_distance=250,own_hp=70,damage=damage,reason='active')
        raw.update(updates)
        return raw

    def observe_progress(self,agent,task,raw,**facts):
        obs=MissionObservations(target_currently_visible=True,distance_to_goal=raw['approach_distance'],**facts)
        return agent.record_mission_progress(task.task_id,raw,observations=obs,evidence_sha256=SHA)

    def feedback(self,agent,task,status,*,restored=False,goal=False):
        b=binding()
        return dict(session_id=SESSION,player_id=3,commander_id=b.commander_id,task_id=task.task_id,status=status,reason_code='ok' if status in {'started','completed'} else 'goal_unobserved',at_game_seconds=agent.latest.game_time_seconds,source='simulated',execution=dict(formation_versions=dict(task.request.formation_versions),issued_frame=1500,expires_frame=4200,command_source='simulated',interference='none',goal_observed=goal,restoration_verified=restored))

    async def test_primitive_evidence_cannot_extend_task_lease(self):
        agent,task=await self.create(mission=False)
        with self.assertRaisesRegex(ContractError,'mission_not_verified'):self.commit(agent,task)
        self.assertEqual(task.status,'planned');self.assertEqual(agent.missions.active,{})

    async def test_mission_survives_plan_ttl_and_keeps_identity_lock_deadline(self):
        agent,task=await self.create();initial=self.commit(agent,task)
        self.advance(agent,160);jobs=agent.jobs()
        held=next(j for j in jobs['jobs'] if j['task_id']==task.task_id)
        self.assertEqual(held['mission']['mission_id'],str(uuid.UUID(task.task_id)))
        self.assertEqual(held['status'],'dispatch_pending');self.assertFalse(held['host_dispatch_candidate'])
        self.assertEqual(held['mission']['deadline_game_seconds'],280)
        self.assertEqual(self.commit(agent,task)['mission']['mission_id'],initial['mission']['mission_id'])
        with self.assertRaisesRegex(ContractError,'mission_commit_changed'):agent.host_commit_task(task.task_id,mission_deadline_game_seconds=300,retreat_region='home_base')
        self.assertEqual(len(agent.missions.active),1)

    async def test_refresh_same_goal_does_not_enqueue_and_explicit_retarget_requests_retreat(self):
        agent,task=await self.create();self.commit(agent,task)
        self.advance(agent,146)
        async def same(context):return tactical_policy(context,[intent('raid','harass_economy',force_fraction=.5)])
        await agent.decide(tactical_snapshot(2000,150),same)
        agent.jobs();self.assertEqual(agent.pending_mission_retreats(),[])
        current=agent.engine.current
        target=replace(current.tactical_tasks[0],target_contact_id='contact_other')
        agent.engine.current=replace(current,tactical_tasks=(target,))
        agent.jobs();self.assertEqual(agent.pending_mission_retreats()[0]['reason'],'replan')
        self.assertEqual(agent.missions.active[task.task_id].target_contact_id,'contact_ore')
        self.assertTrue(any(t.task_id==task.task_id and t.status=='dispatch_pending' for t in agent.goals.tasks))

    async def test_deadline_requests_retreat_without_releasing_or_renewing(self):
        agent,task=await self.create();self.commit(agent,task);self.advance(agent,281)
        self.assertEqual(agent.pending_mission_retreats()[0]['reason'],'deadline')
        self.assertEqual(agent.missions.active[task.task_id].deadline_game_seconds,280)
        self.assertEqual(task.status,'dispatch_pending')

    async def test_progress_is_telemetry_until_final_raw_certification(self):
        agent,task=await self.create();self.commit(agent,task);agent.record_feedback(self.feedback(agent,task,'started'))
        for phase,revision,at,damage in [('approach',1,101,0),('prepare',2,103,0),('engage',3,105,5),('retreat',4,107,5),('restored',5,109,5)]:
            raw=self.progress(agent,task,phase,revision,at,damage);self.observe_progress(agent,task,raw)
        mission=agent.missions.active[task.task_id]
        self.assertEqual(mission.reported_damage,5);self.assertEqual(mission.observations.source_damage_amount,0)
        self.assertEqual(agent.missions.coverage['raid']['completed'],0)
        with self.assertRaisesRegex(ContractError,'mission_terminal_requires_restoration'):agent.record_feedback(self.feedback(agent,task,'completed',restored=True,goal=True))
        facts=MissionObservations(False,approach_verified=True,source_damage_amount=5,retreat_verified=True,restoration_verified=True,distance_to_goal=250)
        agent.certify_mission_result(task.task_id,observations=facts,evidence_sha256='b'*64)
        self.assertEqual(mission.progress_seq,5)  # Certification did not invent a native revision.
        agent.record_feedback(self.feedback(agent,task,'completed',restored=True,goal=True))
        self.assertEqual(agent.missions.active,{});self.assertEqual(agent.missions.coverage['raid']['completed'],1)
        self.assertEqual(agent.missions.history[-1]['target_role'],'economy')

    async def test_no_damage_or_no_retreat_cannot_be_promoted_to_completed(self):
        for damage,retreat in [(0,True),(5,False)]:
            agent,task=await self.create();self.commit(agent,task);agent.record_feedback(self.feedback(agent,task,'started'))
            raw=self.progress(agent,task,'restored',1,110,damage)
            self.observe_progress(agent,task,raw)
            facts=MissionObservations(False,approach_verified=True,source_damage_amount=damage,retreat_verified=retreat,restoration_verified=True,distance_to_goal=250)
            agent.certify_mission_result(task.task_id,observations=facts,evidence_sha256='b'*64)
            with self.assertRaisesRegex(ContractError,'mission_goal_unverified'):agent.record_feedback(self.feedback(agent,task,'completed',restored=True,goal=True))
            self.assertIn(task.task_id,agent.missions.active)

    async def test_feedback_cannot_release_unrestored_mission_and_stop_quarantines(self):
        agent,task=await self.create();self.commit(agent,task);agent.record_feedback(self.feedback(agent,task,'started'))
        with self.assertRaisesRegex(ContractError,'mission_terminal_requires_restoration'):agent.record_feedback(self.feedback(agent,task,'failed',restored=True))
        agent.stop();self.assertEqual(task.status,'active');self.assertEqual(task.reason_code,'mission_restoration_pending')
        self.assertIn(task.request.formation_ids[0],agent.goals.quarantined_formations)

    async def test_trusted_predispatch_rejection_releases_without_native_progress_or_effect(self):
        agent,task=await self.create();self.commit(agent,task)
        agent.certify_mission_not_dispatched(task.task_id,evidence_sha256=SHA)
        mission=agent.missions.active[task.task_id]
        self.assertEqual(mission.phase,'reserved');self.assertEqual(mission.progress_seq,0)
        raw=self.feedback(agent,task,'cancelled');raw.pop('execution');raw['reason_code']='prerequisite_missing'
        agent.record_feedback(raw)
        self.assertEqual(agent.missions.active,{})
        self.assertEqual(agent.missions.coverage['raid']['completed'],0)
        self.assertFalse(agent.goals.quarantined_formations)

    async def test_not_dispatched_certificate_cannot_erase_started_or_native_progress(self):
        for started in [False,True]:
            agent,task=await self.create();self.commit(agent,task)
            if started:agent.record_feedback(self.feedback(agent,task,'started'))
            else:
                raw=self.progress(agent,task,'approach',1,101);self.observe_progress(agent,task,raw)
            with self.assertRaisesRegex(ContractError,'mission_not_dispatched_lifecycle'):agent.certify_mission_not_dispatched(task.task_id,evidence_sha256=SHA)
            self.assertIn(task.task_id,agent.missions.active)

    async def test_raw_revision_binding_clock_and_numeric_rejections_do_not_mutate(self):
        agent,task=await self.create();self.commit(agent,task)
        raw=self.progress(agent,task,'approach',1,101);self.observe_progress(agent,task,raw)
        self.assertFalse(self.observe_progress(agent,task,raw))
        bad_values=[dict(mission_id=str(uuid.uuid4())),dict(deadline_frame=4201),dict(revision=0),dict(revision=True),dict(own_hp=float('nan')),dict(damage=-1),dict(reason='SECRET_RAW_BODY'),dict(observed_frame=999999),dict(own_hp=69)]
        for change in bad_values:
            candidate={**raw,**change}
            with self.subTest(change=change),self.assertRaises(ContractError):self.observe_progress(agent,task,candidate)
        self.assertEqual(agent.missions.active[task.task_id].progress_seq,1)
        self.assertEqual(agent.missions.active[task.task_id].reported_damage,0)

    async def test_damage_counter_cannot_regress_and_retreat_cannot_reengage(self):
        agent,task=await self.create();self.commit(agent,task)
        raw=self.progress(agent,task,'engage',1,103,5);self.observe_progress(agent,task,raw)
        raw=self.progress(agent,task,'retreat',2,104,5);self.observe_progress(agent,task,raw)
        for phase,damage in [('retreat',4),('engage',5)]:
            raw=self.progress(agent,task,phase,3,105,damage)
            with self.assertRaises(ContractError):self.observe_progress(agent,task,raw)
        self.assertEqual(agent.missions.active[task.task_id].phase,'retreat')

    async def test_harass_cannot_lock_an_ordinary_structure(self):
        agent,task=await self.create();raw=tactical_snapshot(2,101);raw['battlefield']['contacts'][0]['role']='structure'
        # A preexisting contact cannot silently change role; use a fresh instance.
        agent=BattleAgent(StrategyEngine(binding()),tactical_evidence=agent.goals.tactical_evidence,mission_evidence=agent.missions.evidence)
        async def model(context):return tactical_policy(context,[intent('raid','harass_economy')])
        self.assertNotEqual((await agent.decide(raw,model)).status,'accepted');self.assertEqual(agent.missions.active,{})

    async def test_continuous_coord_requires_explicit_contact_and_examples_supply_it(self):
        agent,task=await self.create('combined_arms','coordinate_force');self.commit(agent,task)
        fresh,_=await self.create('combined_arms','coordinate_force')
        context=fresh.context(fresh.latest.model_context(binding()));example=tactical_example(context)
        self.assertEqual(example[0]['target_contact_id'],'contact_ore')
        async def none(context):return tactical_policy(context,[intent('combined_arms','coordinate_force',target_contact_id=None,required_roles=['infantry','anti_air'])])
        # Fresh game-time snapshot avoids the engine's legitimate minimum-hold fast path.
        self.assertNotEqual((await fresh.decide(tactical_snapshot(5,120),none)).status,'accepted')

    async def test_coordinate_effect_requires_both_front_damage_and_support_proof(self):
        agent,task=await self.create('combined_arms','coordinate_force');self.commit(agent,task)
        agent.record_feedback(self.feedback(agent,task,'started'))
        raw=self.progress(agent,task,'restored',1,110,5);self.observe_progress(agent,task,raw)
        facts=MissionObservations(False,approach_verified=True,coordination_verified=True,retreat_verified=True,restoration_verified=True,distance_to_goal=250)
        agent.certify_mission_result(task.task_id,observations=facts,evidence_sha256=SHA)
        with self.assertRaisesRegex(ContractError,'mission_goal_unverified'):agent.record_feedback(self.feedback(agent,task,'completed',restored=True,goal=True))
        facts=replace(facts,source_damage_amount=5)
        agent.certify_mission_result(task.task_id,observations=facts,evidence_sha256='b'*64)
        agent.record_feedback(self.feedback(agent,task,'completed',restored=True,goal=True))
        self.assertEqual(agent.missions.coverage['combined_arms']['completed'],1)

    async def test_active_missions_are_isolated_between_commander_instances(self):
        a,task=await self.create();self.commit(a,task);b,_=await self.create()
        raw=self.progress(a,task,'approach',1,101)
        with self.assertRaisesRegex(ContractError,'mission_progress_binding'):self.observe_progress(b,task,raw)
        self.assertEqual(b.missions.active,{})

    async def test_mission_context_survives_many_turns_bounded_compression(self):
        agent,task=await self.create();self.commit(agent,task)
        for i in range(1,51):
            raw=self.progress(agent,task,'approach',i,100+i,0);self.observe_progress(agent,task,raw)
        context=agent.context(agent.latest.model_context(binding()))
        active=context['working_memory']['persistent_missions']['active']
        self.assertEqual(len(active),1);self.assertEqual(active[0]['mission_id'],str(uuid.UUID(task.task_id)))
        self.assertEqual(active[0]['progress_seq'],50);self.assertGreater(agent.summary['events_compacted'],0)
        self.assertEqual(agent.missions.coverage['raid']['completed'],0)

    async def test_concurrent_missions_keep_locks_and_compact_memory_within_wire_budget(self):
        purposes=(('attack',('main_attack',)),('raid',('harass_economy',)),('combined_arms',('coordinate_force',)))
        proof=TacticalEvidence(str(uuid.uuid4()),SESSION,3,'simulated',purposes)
        grant=MissionEvidence(str(uuid.uuid4()),SESSION,3,binding().commander_id,'simulated',purposes)
        agent=BattleAgent(StrategyEngine(binding()),tactical_evidence=proof,mission_evidence=grant)
        raw=tactical_snapshot();form=raw['battlefield']['formations'][0]
        raw['battlefield']['formations']=[dict(form,formation_id='formation_'+str(i),roles={'infantry':3,'anti_air':2}) for i in range(32)]
        contact=raw['battlefield']['contacts'][0]
        raw['battlefield']['contacts']=[dict(contact,contact_id='contact_'+str(i)) for i in range(64)]
        tasks=[intent(module,purpose[0],target_contact_id='contact_0',formation_ids=['formation_'+str(i)],required_roles=['infantry','anti_air'] if module=='combined_arms' else ['infantry'],force_fraction=.2) for i,(module,purpose) in enumerate(purposes)]
        async def model(context):return tactical_policy(context,tasks)
        self.assertEqual((await agent.decide(raw,model)).status,'accepted')
        for task in list(agent.goals.tasks):
            if task.request.module!='build' and task.status=='planned':self.commit(agent,task)
        profile=Profile(binding().commander_id,'mock',CONNECTION,'自定义','m'*200,2,'战'*4000,Endpoint.parse('http://localhost:1'),'')
        adapter=ChatAdapter(profile,max_input_bytes=16384)
        context=agent.context(agent.latest.model_context(binding()),wire_size=adapter.input_size,wire_limit=adapter.max_input_bytes)
        # Main attack and combined arms intentionally share main_force; the
        # third module cannot bypass that lock just to claim coverage.
        self.assertEqual(len(context['working_memory']['persistent_missions']['active']),2)
        self.assertLessEqual(adapter.input_size(context),16384)
        self.assertLessEqual(len(json.dumps(context,ensure_ascii=False,separators=(',',':')).encode()),8192)

    async def test_failed_goal_backoff_survives_roster_version_change(self):
        agent,task=await self.create();self.commit(agent,task);agent.record_feedback(self.feedback(agent,task,'started'))
        raw=self.progress(agent,task,'restored',1,110)
        self.observe_progress(agent,task,raw,restoration_verified=True)
        agent.record_feedback(self.feedback(agent,task,'failed',restored=True))
        later=tactical_snapshot(2000,115);later['battlefield']['formations'][0]['version']=2
        async def model(context):return tactical_policy(context,[intent('raid','harass_economy',force_fraction=.5)])
        await agent.decide(later,model)
        job=next(j for j in agent.jobs()['jobs'] if j['module']=='raid')
        self.assertEqual(job['status'],'blocked');self.assertEqual(job['reason_code'],'failure_backoff')
        later=tactical_snapshot(2001,131);later['battlefield']['formations'][0]['version']=2;agent.observe(later)
        job=next(j for j in agent.jobs()['jobs'] if j['module']=='raid')
        self.assertTrue(job['host_dispatch_candidate'])

    async def test_verified_restored_terminal_clock_does_not_advance_battle_snapshot(self):
        agent,task=await self.create();self.commit(agent,task)
        mission=agent.missions.active[task.task_id]
        raw=dict(mission_id=mission.mission_id,stage='restored',revision=1,observed_frame=4250,deadline_frame=4200,approach_distance=0,own_hp=70,damage=0,reason='deadline')
        facts=MissionObservations(False,restoration_verified=True,distance_to_goal=0)
        with self.assertRaisesRegex(ContractError,'mission_progress_time'):agent.record_mission_progress(task.task_id,raw,observations=facts,evidence_sha256=SHA)
        agent.record_mission_progress(task.task_id,raw,observations=facts,evidence_sha256=SHA,verified_terminal_clock=4250/15)
        self.assertEqual(agent.latest.game_time_seconds,100);self.assertEqual(agent.engine.metrics['requests'],1)
        self.assertEqual(mission.deadline_game_seconds,280)

    async def test_terminal_clock_cannot_bypass_normal_phase_or_unverified_restoration(self):
        for phase,verified in [('engage',True),('restored',False)]:
            agent,task=await self.create();self.commit(agent,task)
            raw=self.progress(agent,task,phase,1,101)
            facts=MissionObservations(False,restoration_verified=verified,distance_to_goal=250)
            with self.assertRaisesRegex(ContractError,'mission_terminal_clock_guard'):agent.record_mission_progress(task.task_id,raw,observations=facts,evidence_sha256=SHA,verified_terminal_clock=101)
            self.assertEqual(agent.missions.active[task.task_id].progress_seq,0)

    async def test_proven_disposal_releases_only_failed_and_preserves_last_native_phase(self):
        agent,task=await self.create();self.commit(agent,task);agent.record_feedback(self.feedback(agent,task,'started'))
        raw=self.progress(agent,task,'engage',1,105,5);self.observe_progress(agent,task,raw)
        agent.certify_mission_disposed(task.task_id,evidence_sha256=SHA)
        mission=agent.missions.active[task.task_id]
        self.assertEqual(mission.phase,'engage');self.assertEqual(mission.progress_seq,1)
        self.assertTrue(mission.observations.disposed_verified);self.assertFalse(mission.observations.retreat_verified)
        with self.assertRaisesRegex(ContractError,'mission_disposal_is_not_completion'):agent.record_feedback(self.feedback(agent,task,'completed',restored=True,goal=True))
        agent.record_feedback(self.feedback(agent,task,'failed',restored=True))
        self.assertEqual(agent.missions.active,{})
        self.assertEqual(agent.missions.coverage['raid']['completed'],0)
        self.assertEqual(agent.missions.history[-1]['phase'],'engage')
        self.assertFalse(agent.goals.quarantined_formations)

    async def test_disposal_cannot_be_asserted_via_ordinary_telemetry_or_untrusted_sha(self):
        agent,task=await self.create();self.commit(agent,task)
        raw=self.progress(agent,task,'approach',1,101)
        with self.assertRaisesRegex(ContractError,'mission_disposal_requires_certificate'):self.observe_progress(agent,task,raw,disposed_verified=True)
        with self.assertRaisesRegex(ContractError,'mission_progress_evidence'):agent.certify_mission_disposed(task.task_id,evidence_sha256='unverified')
        self.assertEqual(agent.missions.active[task.task_id].phase,'reserved')

    async def test_legal_example_considers_uncovered_purposes_without_forcing_missing_targets(self):
        purposes=(('attack',('main_attack',)),('raid',('harass_economy',)),('combined_arms',('coordinate_force',)))
        proof=TacticalEvidence(str(uuid.uuid4()),SESSION,3,'simulated',purposes)
        grant=MissionEvidence(str(uuid.uuid4()),SESSION,3,binding().commander_id,'simulated',purposes)
        agent=BattleAgent(StrategyEngine(binding()),tactical_evidence=proof,mission_evidence=grant)
        observed=agent.observe(tactical_snapshot());context=agent.context(observed.model_context(binding()))
        coverage=context['working_memory']['persistent_missions']['effect_coverage']
        self.assertEqual(tactical_example(context)[0]['module'],'combined_arms')
        coverage['attack']['completed']=1
        self.assertEqual(tactical_example(context)[0]['module'],'raid')
        coverage['raid']['completed']=1
        example=tactical_example(context)[0]
        self.assertEqual(example['module'],'combined_arms');self.assertIsNotNone(example['target_contact_id'])
        context['working_memory']['battlefield']['contacts']=[]
        self.assertEqual(tactical_example(context),[])

    async def test_static_targets_and_failed_target_backoff_affect_examples_only(self):
        agent,_=await self.create('attack','main_attack')
        context=agent.context(agent.latest.model_context(binding()))
        field=context['working_memory']['battlefield'];original=field['contacts'][0]
        field['contacts']=[dict(original,contact_id='contact_fast',role='infantry'),dict(original,contact_id='contact_static',role='structure')]
        self.assertEqual(tactical_example(context)[0]['target_contact_id'],'contact_static')
        context['working_memory']['failure_memory']=[dict(module='attack',purpose='main_attack',target_contact_id='contact_static',retry_after_game_seconds=120)]
        self.assertEqual(tactical_example(context)[0]['target_contact_id'],'contact_fast')
        field['contacts']=[field['contacts'][1]]
        self.assertEqual(tactical_example(context),[])
        context['game_time_seconds']=120
        field['contacts'][0]['observed_at_game_seconds']=120
        self.assertEqual(tactical_example(context)[0]['target_contact_id'],'contact_static')


if __name__=='__main__':unittest.main()
