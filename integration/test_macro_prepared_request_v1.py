"""Real Agent/Audit/Host boundary with artificial observations, no native IO."""
import asyncio
import copy
from pathlib import Path
import unittest
import tempfile

from host_runtime.macro_prepared_request_v1 import prepare_macro_request_v1,decide_prepared_macro_request_v1,encoded


class ResponseObservationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from fixtures import binding,snapshot,policy
        from engine import StrategyEngine
        from battle_agent import BattleAgent
        from macro_strategy import MacroStrategyMemory
        from host_runtime.macro_policy_runtime import MacroRequestAudit
        from macro_host import MacroHost
        from test_macro_strategy import declaration
        self.folder=tempfile.TemporaryDirectory()
        self.identity=binding();self.engine=StrategyEngine(self.identity,timeout_seconds=1,min_hold_game_seconds=0)
        self.agent=BattleAgent(self.engine);self.started=asyncio.Event();self.release=asyncio.Event();self.calls=[]
        self.initial=snapshot(macro_control=dict(mode='macro_native',available_actions=['scout','budgetarmy']))
        self.initial.update(snapshot_id=1,game_time_seconds=100.)
        self.host=MacroHost.__new__(MacroHost);self.host.output=Path(self.folder.name)
        self.host.agent=self.agent;self.host.strategic_only=True;self.host.coherent_snapshot_id=None
        self.host.production_tick=lambda native:native['coherent']
        self.host.latest=copy.deepcopy(self.initial);self.host.consume_observation({'coherent':True})
        memory=MacroStrategyMemory(session_id=self.identity.session_id,commander_id=self.identity.commander_id,
            player_id=self.identity.player_id,profile_revision=1,effective_hash='a'*64)
        outer=self
        class Backend:
            max_input_bytes=16384
            def input_size(self,context):return len(encoded(context))
            async def __call__(self,context):
                outer.calls.append(copy.deepcopy(context));outer.started.set();await outer.release.wait()
                return policy(context,production_focus='native_baseline',objective_region=None,
                    macro_actions=['scout'],macro_production=None,tactical_tasks=[],runtime_task=None,
                    macro_strategy=declaration(objective='scout',expected_observation='new_lawful_contact'))
        self.audit=MacroRequestAudit(Backend(),lambda *a,**k:None,strategy_supplier=memory.context,strategic_only=True)
        self.running=None

    async def asyncTearDown(self):
        self.engine.stop()
        if self.running is not None and not self.running.done():self.running.cancel()
        if self.running is not None:await asyncio.gather(self.running,return_exceptions=True)
        await self.engine.drain_obsolete_request();self.folder.cleanup()

    async def start_waiting_response(self):
        snap=self.agent.latest
        prepared=prepare_macro_request_v1(self.agent,self.audit,snap,
            response_ready=self.host.response_observation_ready)
        self.running=asyncio.create_task(decide_prepared_macro_request_v1(self.agent,snap,prepared))
        await self.started.wait()
        self.observe(2,101.,['budgetarmy'],coherent=False)
        self.release.set();await asyncio.sleep(.02)

    def observe(self,ident,at,actions,*,coherent):
        raw=copy.deepcopy(self.initial);raw.update(snapshot_id=ident,game_time_seconds=at)
        raw['macro_control']['available_actions']=actions
        self.host.latest=raw;self.host.consume_observation({'coherent':coherent})

    async def test_temporary_native_wait_preserves_one_response_until_fresh_qualified_view(self):
        await self.start_waiting_response()
        self.assertFalse(self.running.done());self.assertFalse(self.host.response_observation_ready())
        self.assertEqual(self.engine.metrics['accepted'],0)
        self.observe(3,102.,['scout','budgetarmy'],coherent=True)
        result=await self.running
        self.assertEqual((result.status,result.reason_code),('accepted','valid_policy'))
        self.assertEqual(result.plan.macro_actions,('scout',))
        self.assertEqual(len(self.calls),1);self.assertEqual(self.engine.metrics['requests'],1)

    async def test_coherent_capability_withdrawal_remains_rejected(self):
        await self.start_waiting_response()
        self.observe(3,102.,['budgetarmy'],coherent=True)
        result=await self.running
        self.assertEqual(result.reason_code,'unsupported_macro_action')
        self.assertEqual(self.engine.metrics['accepted'],0);self.assertEqual(len(self.calls),1)

    async def test_response_wait_uses_the_original_request_deadline(self):
        self.engine.timeout=.05
        await self.start_waiting_response()
        result=await asyncio.wait_for(self.running,.5)
        self.assertEqual(result.reason_code,'response_observation_timeout')
        self.assertEqual(self.engine.metrics['timeouts'],1);self.assertEqual(len(self.calls),1)

    async def test_stop_while_waiting_cannot_accept_the_response(self):
        await self.start_waiting_response();self.engine.stop()
        result=await asyncio.wait_for(self.running,.5)
        self.assertEqual(result.status,'stopped');self.assertEqual(self.engine.metrics['accepted'],0)
        self.assertEqual(len(self.calls),1)

    async def test_fresh_native_view_does_not_refresh_the_old_model_time(self):
        await self.start_waiting_response()
        self.observe(3,140.,['scout','budgetarmy'],coherent=True)
        result=await self.running
        self.assertNotEqual(result.status,'accepted');self.assertEqual(self.engine.metrics['accepted'],0)
        self.assertEqual(self.calls[0]['game_time_seconds'],100.)



if __name__=='__main__':unittest.main()
