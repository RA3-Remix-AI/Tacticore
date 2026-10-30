"""Actual Host.run/dispatch/prepare unwind, artificial sampler and native IO."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import macro_host
from macro_host import MacroHost
from host_runtime.contracts import ContractError
import test_macro_host_dispatch_revalidation as fixture
from test_macro_expansion_host import manifest


class ResultCandidateTests(unittest.IsolatedAsyncioTestCase):
    collect=fixture.RevalidationTests.collect
    events=fixture.RevalidationTests.events
    archived=fixture.RevalidationTests.archived
    def setUp(self):fixture.RevalidationTests.setUp(self)

    async def run_case(self,path='dispatch_post',code='macro_native_result_candidate',cleanup_unknown=False):
        host=self.host;native=self.native;agent=host.agent;controller=host.controller;runtime=host.strategy_runtime
        build=self.output/'build';build.mkdir();(build/'build-manifest.json').write_text(json.dumps(manifest(1)),encoding='utf8')
        host.args=SimpleNamespace(macro_bundle=self.output/'bundle.json',session=self.output/'session.json',
            library=self.output/'unused',max_wall_seconds=60,strategy_mode='declared')
        host.session={};host.draft={};host.profile={'name':'offline','connection_id':fixture.CONNECTION}
        host.transport_config=macro_host.native_transport_config(host.sampler.scope,manifest(1),host.args.max_wall_seconds)
        host.phase='starting';host.reason='preparing';host.startup_lawful_snapshots=[]
        host.backend=None;host.transport=None;host.pending=None;host.application=None
        host.check_profile=Mock();host.freeze=Mock();host.freeze_publication_contract=Mock();host.publish=Mock()
        host.finish_transport=Mock(side_effect=ContractError('offline_unknown_cleanup') if cleanup_unknown else None)
        host.store=Mock();host.create_controller=Mock(return_value=controller)
        host.sampler.bundle={'build':str(build)};host.sampler.proof={};host.sampler.participants=[];host.sampler.owner=0
        host.sampler.close=Mock();host.sampler.state={'result_records':[{'victory_frame':1510,'defeat_frame':0}]}
        backend=SimpleNamespace(observation=lambda:dict(real_network_verified=True))
        applied=SimpleNamespace(effective=SimpleNamespace(effective_hash=host.expected_hash),public=lambda:{})
        spec=SimpleNamespace(loader=SimpleNamespace(exec_module=Mock()))
        constructor=Mock(return_value=native)
        # Host allocates before initialization so failed constructors can close.
        # Retain this fixture's existing fake transport and constructor spy.
        class TransportFactory:
            def __new__(cls):return native
        native.__init__=constructor
        module=SimpleNamespace(MacroPolicyProbe=TransportFactory)
        error=ContractError(code)
        if path=='startup':self.views=[error]
        elif path=='loop':self.views=[fixture.view(2,1501),error]
        elif path=='prepare':self.views=[fixture.view(2,1501),fixture.view(3,1503),error]
        else:
            self.views=[fixture.view(2,1501),fixture.view(3,1503),fixture.view(4,1504),error]
            host.pending=asyncio.get_running_loop().create_future()
            host.pending.set_result(SimpleNamespace(status='accepted',reason_code='accepted',plan=self.plan))
        original_collect=self.collect
        def collect():
            if isinstance(self.views[0],BaseException):raise self.views.pop(0)
            return original_collect()
        host.sampler.collect=collect;controller.feedback=Mock(return_value={})
        with patch.object(macro_host,'load_bundle',return_value=({'build':str(build)},host.sampler.scope)), \
            patch.object(macro_host,'digest',return_value='a'*64),patch.object(macro_host,'MacroSampler',return_value=host.sampler), \
            patch.object(macro_host,'load_profile'),patch.object(macro_host,'apply_commander_draft',return_value=applied), \
            patch.object(macro_host,'create_applied_backend',return_value=backend),patch.object(macro_host,'BattleAgent',return_value=agent), \
            patch.object(macro_host,'MacroStrategyRuntime',return_value=runtime), \
            patch.object(macro_host.importlib.util,'spec_from_file_location',return_value=spec), \
            patch.object(macro_host.importlib.util,'module_from_spec',return_value=module):
            result=await host.run()
        return result,constructor

    async def test_actual_queued_accepted_response_result_during_dispatch_postview_unwinds_without_new_work(self):
        result,_=await self.run_case()
        self.assertEqual(result['state'],'result_candidate');self.assertEqual(result['reason_code'],'native_result_requires_visual_confirmation')
        self.assertEqual(self.native.calls,[]);self.assertEqual(self.native.samples,['desktop_macro_tick','desktop_macro_dispatch_revalidation'])
        signal=next(e for e in self.events() if e['kind']=='macro_result_candidate')
        self.assertIn('observe_post_native_view',[f['function'] for f in signal['source_frames']])
        self.assertEqual(signal['native_reason_code'],'macro_native_result_candidate')
        self.assertFalse(any(e['kind']=='host_fault' for e in self.events()))
        self.assertEqual(json.loads((self.output/'result-native-state.json').read_text()),self.host.sampler.state)
        self.host.finish_transport.assert_called_once();self.host.sampler.close.assert_called_once()

    async def test_request_postview_known_match_end_is_candidate_and_cleanup_still_runs(self):
        result,_=await self.run_case('prepare','macro_match_ended')
        self.assertEqual(result['state'],'result_candidate');self.assertEqual(self.native.calls,[])
        signal=next(e for e in self.events() if e['kind']=='macro_result_candidate')
        self.assertIn('prepare_model_request',[f['function'] for f in signal['source_frames']])
        self.host.finish_transport.assert_called_once()

    async def test_main_loop_result_uses_same_candidate_classifier(self):
        result,_=await self.run_case('loop')
        self.assertEqual(result['state'],'result_candidate');self.host.finish_transport.assert_called_once()

    async def test_result_before_constructor_is_fault_without_release_or_result_archive_claim(self):
        result,constructor=await self.run_case('startup')
        self.assertEqual(result['state'],'fault');self.assertEqual(result['reason_code'],'macro_native_result_candidate')
        constructor.assert_not_called();self.assertFalse(self.host.native_transport_attached)
        self.assertFalse((self.output/'result-native-state.json').exists())
        self.assertFalse(any(e['kind']=='macro_result_candidate' for e in self.events()))

    async def test_independent_cleanup_unknown_overrides_candidate(self):
        result,_=await self.run_case(cleanup_unknown=True)
        self.assertEqual(result['state'],'fault');self.assertEqual(result['reason_code'],'macro_stop_unverified')
        self.host.finish_transport.assert_called_once();self.host.sampler.close.assert_called_once()
        self.assertEqual(self.native.calls,[])

    async def test_other_contract_error_keeps_fault_and_trace(self):
        result,_=await self.run_case(code='macro_frame_regression')
        self.assertEqual(result['state'],'fault');self.assertEqual(result['reason_code'],'macro_frame_regression')
        failure=next(e for e in self.events() if e['kind']=='host_fault')
        self.assertIn('observe_post_native_view',[f['function'] for f in failure['source_frames']])
        self.assertFalse(any(e['kind']=='macro_result_candidate' for e in self.events()))

    async def test_result_archive_failure_keeps_fault_and_independent_cleanup(self):
        atomic=macro_host._atomic
        def blocked(path,value):
            if path.name=='result-native-state.json':raise OSError('synthetic archival failure')
            return atomic(path,value)
        with patch.object(macro_host,'_atomic',side_effect=blocked):result,_=await self.run_case()
        self.assertEqual(result['state'],'fault');self.assertEqual(result['reason_code'],'macro_host_failed')
        self.host.finish_transport.assert_called_once()
        self.assertTrue(any(e['kind']=='macro_result_candidate_archive_failed' for e in self.events()))


if __name__=='__main__':unittest.main()
