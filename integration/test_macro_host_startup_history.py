"""Real MacroHost.run startup, lawful snapshots, no model/native transport."""
import copy
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import macro_host
from macro_host import MacroHost
from host_runtime.contracts import ContractError
from host_runtime.test_macro_expansion_runtime import expansion_scope
from test_macro_expansion_host import manifest
from fixtures import binding
from tactical_fixtures import tactical_snapshot
from battle_agent import BattleAgent
from engine import StrategyEngine,ContractError as StrategyContractError


def startup_views():
    visible=tactical_snapshot(1,100)
    hidden=tactical_snapshot(2,102)
    hidden['battlefield']['contacts'][0].update(currently_visible=False,observed_at_game_seconds=100)
    hidden['battlefield']['regions'][1].update(currently_visible=False,observed_at_game_seconds=100,role_counts={})
    return visible,hidden


class StartupHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def run_startup(self,folder,views,boot_effect=None):
        host=MacroHost.__new__(MacroHost);host.binding=binding()
        root=Path(folder);build=root/'build';build.mkdir()
        (build/'build-manifest.json').write_text(json.dumps(manifest(2)),encoding='utf8')
        host.output=root/'battle-host';host.output.mkdir()
        host.args=SimpleNamespace(macro_bundle=root/'bundle.json',session=root/'session.json',library=root/'unused',
            max_wall_seconds=60,strategy_mode='declared')
        host.session={};host.run_id='offline-startup';host.started=time.monotonic()
        host.expected_hash='a'*64;host.expected_revision=1;host.draft={}
        host.profile={'name':host.binding.commander_name,'connection_id':host.binding.connection_id}
        host.phase='starting';host.reason='macro_preparing';host.latest=None;host.agent=None
        host.backend=None;host.transport=None;host.controller=None;host.pending=None;host.application=None
        host.sampler=None;host.strategy_runtime=None;host.startup_lawful_snapshots=[]
        host.check_profile=Mock();host.freeze=Mock();host.event=Mock();host.publish=Mock()
        host.finish_transport=Mock();host.store=Mock();host.journal=Mock()
        scope=expansion_scope()
        host.transport_config=macro_host.native_transport_config(scope,manifest(2),host.args.max_wall_seconds)
        sampler=SimpleNamespace(scope=scope,bundle={'build':str(build)},owner=0,latest_census={},safety={},
            proof={},participants=[],collect=Mock(side_effect=views),close=Mock())
        # Stop at the exact native construction boundary. Reaching this fake
        # constructor means real startup priming and its guards completed.
        transport=Mock(side_effect=ContractError('offline_transport_boundary'))
        # Match the real Host's explicit allocation/initialization boundary.
        class FakeTransport:
            def __init__(self,*args,**kwargs):transport(*args,**kwargs)
        module=SimpleNamespace(MacroPolicyProbe=FakeTransport)
        spec=SimpleNamespace(loader=SimpleNamespace(exec_module=Mock()))
        applied=SimpleNamespace(effective=SimpleNamespace(effective_hash=host.expected_hash),profile=object())
        with patch.object(macro_host,'load_bundle',return_value=({'build':str(build)},scope)), \
            patch.object(macro_host,'digest',return_value='a'*64),patch.object(macro_host,'MacroSampler',return_value=sampler), \
            patch.object(macro_host,'observe_forces',return_value={}),patch.object(macro_host,'load_profile'), \
            patch.object(macro_host,'apply_commander_draft',return_value=applied), \
            patch.object(macro_host,'create_applied_backend',return_value=Mock()) as backend, \
            patch('host_runtime.macro_cost_boot_v4.boot_macro_cost_v4',side_effect=boot_effect,return_value=SimpleNamespace(session=None)) as boot, \
            patch.object(macro_host.importlib.util,'spec_from_file_location',return_value=spec) as importer, \
            patch.object(macro_host.importlib.util,'module_from_spec',return_value=module):
            result=await host.run()
        self.assertEqual(boot.call_count,1);self.assertEqual(sampler.collect.call_count,2)
        self.assertEqual(backend.call_count,1)
        self.assertEqual(host.agent.engine.metrics['requests'],0)
        host.finish_transport.assert_called_once();sampler.close.assert_called_once()
        snapshots=[json.loads(line) for line in (host.output/'macro-snapshots.jsonl').read_text(encoding='utf8').splitlines()]
        return host,result,snapshots,transport,importer

    async def test_actual_startup_visible_before_cost_boot_then_hidden_is_primed_in_original_order(self):
        visible,hidden=startup_views()
        with tempfile.TemporaryDirectory() as folder:
            host,result,rows,transport,_=await self.run_startup(folder,[visible,hidden])
            self.assertEqual(result['reason_code'],'offline_transport_boundary')
            transport.assert_called_once()
            self.assertEqual(rows,[visible,hidden])
            self.assertEqual([(r['snapshot_id'],r['game_time_seconds']) for r in rows],[(1,100),(2,102)])
            fact=host.agent.contact_facts['contact_ore']
            self.assertFalse(fact['currently_visible']);self.assertEqual(fact['observed_at_game_seconds'],100)
            self.assertEqual(host.agent.latest.snapshot_id,2)
            self.assertEqual(host.startup_lawful_snapshots,[])
            primed=next(c.kwargs for c in host.event.call_args_list if c.args[0]=='macro_startup_history_primed')
            self.assertEqual(primed,dict(snapshot_count=2,first_snapshot_id=1,last_snapshot_id=2,
                transport_constructor_started=False,attach_started=False))
            began=next(c.kwargs for c in host.event.call_args_list if c.args[0]=='macro_native_transport_constructor_begin')
            self.assertIsNone(began['attach_started'])
            self.assertFalse(any(c.args[0]=='macro_native_transport_constructor_returned' for c in host.event.call_args_list))

    async def test_hidden_changes_are_still_rejected_before_native_construction(self):
        for field,value in [('region_id','north_expansion'),('observed_at_game_seconds',101)]:
            visible,hidden=startup_views();hidden['battlefield']['contacts'][0][field]=value
            with self.subTest(field=field),tempfile.TemporaryDirectory() as folder:
                _,result,rows,transport,importer=await self.run_startup(folder,[visible,hidden])
                self.assertEqual(result['reason_code'],'hidden_contact_updated')
                self.assertEqual(rows,[visible,hidden]);transport.assert_not_called();importer.assert_not_called()

    async def test_no_actual_visible_history_cannot_be_invented_by_startup_buffer(self):
        first,hidden=startup_views();first['battlefield']['contacts']=[]
        with tempfile.TemporaryDirectory() as folder:
            _,result,rows,transport,importer=await self.run_startup(folder,[first,hidden])
            self.assertEqual(result['reason_code'],'unseen_contact_history')
            self.assertEqual(rows,[first,hidden]);transport.assert_not_called();importer.assert_not_called()

    async def test_source_mutation_after_archive_does_not_rewrite_earlier_lawful_view(self):
        visible,hidden=startup_views();original=copy.deepcopy(visible)
        def boot(*args,**kwargs):visible['battlefield']['contacts'][0]['region_id']='north_expansion'
        with tempfile.TemporaryDirectory() as folder:
            host,result,rows,transport,_=await self.run_startup(folder,[visible,hidden],boot)
            self.assertEqual(result['reason_code'],'offline_transport_boundary')
            self.assertEqual(rows,[original,hidden]);transport.assert_called_once()
            self.assertEqual(host.agent.contact_facts['contact_ore']['region_id'],'east_ore')

    async def test_unseen_guard_without_startup_history_remains_unchanged(self):
        _,hidden=startup_views();agent=BattleAgent(StrategyEngine(binding()))
        with self.assertRaisesRegex(StrategyContractError,'unseen_contact_history'):agent.observe(hidden)


if __name__=='__main__':unittest.main()
