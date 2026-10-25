"""Post-response guard diagnostics stay distinct from transport and policy errors."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from battle_agent import BattleAgent,TacticalEvidence
from engine import ContractError,StrategyEngine
from fixtures import binding,SESSION
from tactical_fixtures import tactical_snapshot,tactical_policy,intent


class PolicyGuardAudit(unittest.IsolatedAsyncioTestCase):
    async def run_case(self,change=None,*,transport=False,unknown_guard=False):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'audit.jsonl'
            proof=TacticalEvidence(str(uuid.uuid4()),SESSION,3,'simulated',(('attack',('main_attack',)),),(('attack','main_attack',('infantry',)),))
            agent=BattleAgent(StrategyEngine(binding(),audit_path=path),tactical_evidence=proof)
            async def adapter(context):
                if transport:raise OSError('SECRET_TRANSPORT_BODY')
                response=tactical_policy(context,[intent()])
                return change(response) if change else response
            if unknown_guard:
                with patch.object(agent.goals,'validate_actor_roles',side_effect=ContractError('SECRET_UNKNOWN_BODY')):
                    result=await agent.decide(tactical_snapshot(),adapter)
            else:result=await agent.decide(tactical_snapshot(),adapter)
            text=path.read_text(encoding='utf-8')
            entries=[json.loads(line) for line in text.splitlines()]
            self.assertNotIn('SECRET_',text)
            self.assertNotIn('SECRET_',json.dumps(agent.public_memory()))
            return agent,result,[e for e in entries if e['event']=='policy_guard_rejected'],entries

    async def test_context_and_actor_failures_have_separate_fixed_codes(self):
        def field(name,value):
            def change(response):response['tactical_tasks'][0][name]=value;return response
            return change
        cases=[
            (field('formation_ids',['SECRET_HIDDEN_FORMATION']),'context_formation'),
            (field('target_contact_id',{'SECRET_UNKNOWN_ID':1}),'context_contact'),
            (field('target_region','SECRET_HIDDEN_REGION'),'context_tactical_region'),
            (field('required_roles',['anti_air']),'tactical_actor_roles'),
            (field('required_roles',['infantry','infantry']),'tactical_single_actor_role'),
            (lambda response:'{"SECRET_BODY":','model_json'),
            (lambda response:'{"stance":NaN}','nonfinite_json'),
        ]
        for change,code in cases:
            with self.subTest(code=code):
                agent,result,guards,entries=await self.run_case(change)
                self.assertNotEqual(result.status,'accepted')
                self.assertEqual([e['reason_code'] for e in guards],[code])
                self.assertEqual(agent.metrics['post_response_guard_rejections'],1)
                self.assertEqual(guards[0]['snapshot_id'],agent.latest.snapshot_id)
                self.assertEqual(guards[0]['commander_id'],binding().commander_id)
                self.assertTrue(any(e.get('reason_code')=='adapter_error' for e in entries))

    async def test_transport_failure_does_not_invent_policy_guard_reason(self):
        agent,result,guards,_=await self.run_case(transport=True)
        self.assertEqual(result.reason_code,'adapter_error');self.assertEqual(guards,[])
        self.assertEqual(agent.metrics['post_response_guard_rejections'],0)

    async def test_valid_response_and_engine_enum_rejection_are_not_context_failures(self):
        agent,result,guards,_=await self.run_case()
        self.assertEqual(result.status,'accepted');self.assertEqual(guards,[])
        def invalid(response):response['stance']='SECRET_INVALID_ENUM';return response
        agent,result,guards,_=await self.run_case(invalid)
        self.assertNotEqual(result.status,'accepted');self.assertEqual(guards,[])
        self.assertEqual(agent.engine.metrics['rejected'],1)

    async def test_unknown_contract_exception_value_never_enters_audit(self):
        agent,result,guards,_=await self.run_case(unknown_guard=True)
        self.assertEqual(guards[0]['reason_code'],'post_response_contract')


if __name__=='__main__':unittest.main()
