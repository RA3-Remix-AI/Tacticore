"""Actual Host/controllers; artificial native kind1-paused/kind2-STOP behavior."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import test_macro_strategic_observation_v1 as observation
from host_runtime.contracts import ContractError
from host_runtime.macro_durable import DurableMacroTransport
from fixtures import SESSION


class StrategicPausedTests(unittest.TestCase):
    def fixture(self):
        outer=observation.independent.StrategicDelegationIndependentTests()
        case=outer.case();self.addCleanup(outer.doCleanups)
        host=case.host();fixture=observation.regional.RegionalControllerTests();fixture.setUp()
        host.controller=fixture.controller
        host.controller.session_id=host.controller.budget.session_id=SESSION
        durable=DurableMacroTransport(host.transport,host.journal,host.run_id)
        host.controller.transport=host.controller.budget.transport=durable
        host.sampler=SimpleNamespace(scope=fixture.scope)
        sample,host.latest,state,flags,host.strategic_transport_binding=observation.transport_facts(host.transport)
        host.native_commands=[]
        def apply(actions,duration,command):
            host.native_commands.append(dict(kind=1,actions=list(actions),paused=host.latest['paused']))
            host.transport.calls.append((actions,duration,command))
            if host.latest['paused']:
                state.update(error=16)
                raise ContractError('artificial_native_fatal_16')
            seq=len(host.transport.calls)
            state.update(request=seq,ack=seq,applied_mask=0,deadline_frame=0,cleanup_verified=1)
            return dict(seq=seq,native=dict(last_frame=state['last_frame'],deadline_frame=state['last_frame']+duration))
        def close():
            host.native_commands.append(dict(kind=2,paused=host.latest['paused']))
            state.update(applied_mask=0,deadline_frame=0,cleanup_verified=1,lease_held=0,phase=2)
        host.transport.apply=apply;host.transport.close=close
        self.addCleanup(patch.stopall)
        patch('read_script_flags.inspect_flags',return_value=flags).start()
        self.assertTrue(host.consume_observation(sample))
        return case,host,fixture,sample,state

    def pause_view(self,host,sample,state,frame=1515):
        host.latest=copy.deepcopy(host.latest)
        host.latest.update(paused=True,snapshot_id=host.latest['snapshot_id']+1,game_time_seconds=frame/15)
        sample['observation']['frame']=sample['observation']['construction_feedback']['frame']=frame
        state['last_frame']=frame

    def test_expired_regional_intent_waits_for_resume_without_extending_ttl(self):
        case,host,fixture,sample,state=self.fixture()
        plan=copy.copy(fixture.plan);plan.session_id=SESSION;plan.expires_at_game_seconds=101
        host.controller.dispatch(plan,100,effective_hash=host.expected_hash)
        original=host.controller.regional_plan
        self.pause_view(host,sample,state)
        self.assertTrue(host.consume_observation(sample))
        self.assertEqual(len(host.transport.calls),1)
        self.assertFalse(host.controller.stopped)
        self.assertEqual(host.controller.regional_plan,original)
        self.assertEqual(host.latest['macro_control']['available_actions'],[])
        self.assertEqual(host.last_regional_feedback['active_native_tactics'],1)
        host.latest['paused']=False;host.latest['snapshot_id']+=1
        self.assertTrue(host.consume_observation(sample))
        self.assertEqual([row['kind'] for row in host.native_commands],[1,1])
        self.assertEqual(host.transport.calls[-1][:2],([],1))
        self.assertEqual(host.controller.regional_plan,original)
        self.assertEqual(host.controller.regional_feedback()['release_reason'],'expired')
        self.assertTrue(all(r['status']=='completed' for r in host.journal.commands_for_run(host.run_id)))

    def test_newly_inactive_scout_still_observed_while_paused_but_not_cleared(self):
        case,host,fixture,sample,state=self.fixture()
        sample['observation']['runtimes'][0]['native_execution_active']=True
        self.assertTrue(host.consume_observation(sample))
        plan=copy.copy(fixture.plan);plan.session_id=SESSION;plan.macro_actions=('scout',);plan.objective_region=None
        host.controller.dispatch(plan,100,effective_hash=host.expected_hash)
        original=host.controller.scout_plan
        runtime=SimpleNamespace(commands={},observe=Mock());host.strategy_runtime=runtime
        self.pause_view(host,sample,state)
        sample['observation']['runtimes'][0]['native_execution_active']=False
        self.assertTrue(host.consume_observation(sample))
        self.assertEqual(len(host.transport.calls),1)
        self.assertFalse(host.last_scouting_feedback['policy_released'])
        self.assertEqual(host.last_scouting_feedback['active_native_tactics'],0)
        runtime.observe.assert_called_once_with(host.controller,state,101.)
        self.assertEqual(host.controller.scout_plan,original)
        host.latest['paused']=False;host.latest['snapshot_id']+=1
        self.assertTrue(host.consume_observation(sample))
        self.assertEqual(len(host.transport.calls),2)
        self.assertEqual(host.controller.scouting_feedback()['release_reason'],'native_execution_inactive')

    def test_paused_capabilities_request_preparation_and_late_dispatch_remain_disabled(self):
        case,host,fixture,sample,state=self.fixture()
        plan=copy.copy(fixture.plan);plan.session_id=SESSION
        self.pause_view(host,sample,state)
        self.assertTrue(host.consume_observation(sample))
        self.assertEqual(host.latest['macro_control']['available_actions'],[])
        self.assertEqual(host.latest['macro_control']['region_targets'],{})
        self.assertFalse(host.dispatch_plan(plan))
        post=copy.deepcopy(host.latest);post['snapshot_id']+=1
        host.sampler.collect=lambda:copy.deepcopy(post)
        host.sampler.latest_census={};host.sampler.safety=None
        audited=Mock();audited.prepare.side_effect=AssertionError('paused model preparation')
        with patch('macro_host.observe_forces',return_value={}):
            self.assertIsNone(host.prepare_model_request(audited))
        audited.prepare.assert_not_called()
        self.assertEqual(host.transport.calls,[])

    def test_unknown_delivery_is_never_resent_after_pause_or_resume(self):
        case,host,fixture,sample,state=self.fixture()
        plan=copy.copy(fixture.plan);plan.session_id=SESSION
        def unknown(*args):
            host.transport.calls.append(args);raise TimeoutError('artificial unknown')
        host.transport.apply=unknown
        with self.assertRaisesRegex(ContractError,'outcome_unknown'):
            host.controller.dispatch(plan,100,effective_hash=host.expected_hash)
        self.pause_view(host,sample,state)
        for paused in (True,False):
            host.latest['paused']=paused
            with self.assertRaises(ContractError):host.consume_observation(sample)
        self.assertEqual(len(host.transport.calls),1)
        self.assertEqual([r['status'] for r in host.journal.commands_for_run(host.run_id)],['uncertain'])

    def test_stop_still_uses_kind2_while_paused(self):
        case,host,fixture,sample,state=self.fixture()
        plan=copy.copy(fixture.plan);plan.session_id=SESSION
        host.controller.dispatch(plan,100,effective_hash=host.expected_hash)
        self.pause_view(host,sample,state)
        host.controller.stop()
        self.assertEqual(host.native_commands[-1],dict(kind=2,paused=True))
        self.assertTrue(host.controller.stopped)
        self.assertEqual(state['cleanup_verified'],1)
        self.assertEqual(state['lease_held'],0)
        self.assertEqual(host.controller.regional_feedback()['release_reason'],'stopped')


if __name__=='__main__':unittest.main()
