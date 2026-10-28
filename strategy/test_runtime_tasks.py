"""Local maneuver contract is separate from broad tactical purpose claims."""
import asyncio
import unittest
import uuid
from engine import Snapshot,StrategyEngine,ContractError,validate_policy
from battle_agent import BattleAgent
from fixtures import binding,snapshot,policy

def uid():return str(uuid.uuid4())
def opportunity():return dict(opportunity_id=uid(),max_hold_frames=450,targets=[dict(target_point_id=uid(),bearing_degrees=90,distance_units=60)])
def intent(o):return dict(opportunity_id=o['opportunity_id'],purpose='move_hold_return',target_point_id=o['targets'][0]['target_point_id'],hold_frames=15)

class RuntimeTaskContract(unittest.TestCase):
    def test_preparation_roundtrip_is_information_and_never_an_opportunity(self):
        preparation=dict(state='waiting_paid_unit',reason_code='completed_paid_unit_required',paid_units_available=0)
        s=Snapshot.from_dict(snapshot(runtime_preparation=preparation))
        self.assertEqual(Snapshot.from_dict(s.to_dict()),s)
        self.assertEqual(s.model_context(binding())['runtime_preparation'],preparation)
        with self.assertRaises(ContractError):
            validate_policy(policy(s.model_context(binding()),runtime_task=intent(opportunity())),s,s,binding(),20)
        for edit in ({'grant':True},{'state':[]},{'paid_units_available':True},{'paid_units_available':1025}):
            with self.subTest(edit=edit),self.assertRaises(ContractError):Snapshot.from_dict(snapshot(runtime_preparation=dict(preparation,**edit)))

    def test_optional_roundtrip_and_exact_visible_choice(self):
        o=opportunity();s=Snapshot.from_dict(snapshot(runtime_opportunity=o))
        self.assertEqual(Snapshot.from_dict(s.to_dict()),s)
        self.assertEqual(s.model_context(binding())['runtime_opportunity'],o)
        p=validate_policy(policy(s.model_context(binding()),runtime_task=intent(o)),s,s,binding(),20)
        self.assertEqual(p.runtime_task.public(),intent(o));self.assertEqual(p.tactical_tasks,())
        self.assertIsNone(validate_policy(policy(s.model_context(binding())),s,s,binding(),20).runtime_task)

    def test_omitted_unavailable_changed_or_paused_opportunity_denied(self):
        o=opportunity();s=Snapshot.from_dict(snapshot(runtime_opportunity=o));p=policy(s.model_context(binding()),runtime_task=intent(o))
        for changes in ({},{'runtime_opportunity':opportunity()},{'runtime_opportunity':o,'paused':True}):
            latest=Snapshot.from_dict(snapshot(ident=2,at=101,**changes))
            with self.subTest(changes=changes),self.assertRaises(ContractError):validate_policy(p,s,latest,binding(),20)

    def test_authority_coordinates_wrong_purpose_or_hold_rejected(self):
        o=opportunity();s=Snapshot.from_dict(snapshot(runtime_opportunity=o))
        for edit in ({'purpose':'main_attack'},{'hold_frames':True},{'hold_frames':451},{'hold_frames':float('nan')},
                     {'executor_sha256':'a'*64},{'coordinates':[1,2,3]},{'target_point_id':uid()},{'opportunity_id':uid()}):
            raw=dict(intent(o),**edit)
            with self.subTest(edit=edit),self.assertRaises(ContractError):validate_policy(policy(s.model_context(binding()),runtime_task=raw),s,s,binding(),20)

    def test_snapshot_does_not_accept_authority_or_unbounded_choices(self):
        for edit in ({'grant':True},{'max_hold_frames':451},{'max_hold_frames':True},{'targets':[]},{'targets':[opportunity()['targets'][0]]*9}):
            with self.subTest(edit=edit),self.assertRaises(ContractError):Snapshot.from_dict(snapshot(runtime_opportunity=dict(opportunity(),**edit)))

class RuntimeAgent(unittest.IsolatedAsyncioTestCase):
    async def test_actual_agent_preserves_opportunity_to_model_and_returns_typed_intent(self):
        o=opportunity();a=BattleAgent(StrategyEngine(binding()));captured=[]
        async def model(context):
            captured.append(context)
            return policy(context,runtime_task=intent(context['runtime_opportunity']))
        result=await a.decide(snapshot(runtime_opportunity=o),model)
        self.assertEqual(result.status,'accepted');self.assertEqual(result.plan.runtime_task.public(),intent(o))
        self.assertEqual(captured[0]['runtime_opportunity'],o)
        self.assertFalse(any(k in str(captured[0]) for k in ('executor_sha256','api_key','actor_address')))
        self.assertFalse(any(t.get('module')=='runtime' for t in a.jobs()['jobs']))

    async def test_inflight_response_cannot_use_replaced_opportunity(self):
        a=BattleAgent(StrategyEngine(binding()));o=opportunity();started=asyncio.Event();resume=asyncio.Event()
        async def model(context):
            started.set();await resume.wait();return policy(context,runtime_task=intent(o))
        pending=asyncio.create_task(a.decide(snapshot(runtime_opportunity=o),model));await started.wait()
        a.observe(snapshot(ident=2,at=101,runtime_opportunity=opportunity()));resume.set()
        result=await pending
        self.assertNotEqual(result.status,'accepted');self.assertIsNone(a.engine.current.runtime_task)

    async def test_local_feedback_cannot_credit_combat_modules_or_fake_completion(self):
        a=BattleAgent(StrategyEngine(binding()));a.observe(snapshot())
        raw=dict(task_id=uid(),plan_id=uid(),purpose='move_hold_return',status='completed',reason_code='local_maneuver_verified')
        with self.assertRaises(ContractError):a.record_runtime_feedback(raw,100)
        a.record_runtime_feedback(dict(raw,physical_home=True,control_released=True,mission_effect_verified=True),100)
        self.assertEqual(sum(a.summary['completed_tasks'].values()),0)
        context=a.context(a.latest.model_context(binding()))
        self.assertEqual(context['working_memory']['local_maneuver_feedback'][-1]['task_id'],raw['task_id'])

if __name__=='__main__':unittest.main()
