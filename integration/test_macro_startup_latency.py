"""Opening admission reuse and early qualified model readiness, without Game."""
from types import SimpleNamespace
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
import uuid
from unittest.mock import Mock,patch

from macro_host import MacroHost
from host_runtime import macro_desktop
from host_runtime.macro_policy_runtime import COMMANDER


class StartupLatency(unittest.TestCase):
    def test_locked_visibility_reuses_inventory_and_still_checks_capsule_and_live_pid(self):
        from host_runtime import native6_visibility as visibility,native6_qualification as qualification
        from host_runtime.native6_runtime_contract import ACTIONS,FLAGS,PACKAGE_SHA
        from host_runtime.contracts import ContractError
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);capsule=root/'qualification/native6-trial.json'
            capsule.parent.mkdir();capsule.write_text(json.dumps(dict(package_sha256=PACKAGE_SHA,safety={})))
            pin='a'*64;cap_pin=hashlib.sha256(capsule.read_bytes()).hexdigest()
            scope=qualification.Native6Scope(PACKAGE_SHA,tuple(zip(ACTIONS,FLAGS)),(),((str(capsule),cap_pin),),
                runtime_root=root,runtime_manifest_sha256=pin)
            bundle=dict(runtime_root=str(root),runtime_manifest_sha256=pin)
            session=dict(mod_sha256=PACKAGE_SHA,registry=str(root/'qualification/registry.json'),pid=123)
            memory=Mock(pid=124)
            with patch.object(visibility,'current') as current, \
                    patch.object(qualification,'runtime_root',return_value=root), \
                    patch.object(qualification,'trusted_pin',return_value=pin):
                with self.assertRaisesRegex(ValueError,'PID mismatch'):
                    visibility.bind_session(memory,session,3,_locked_qualification=(bundle,scope))
                current.assert_not_called();memory.read.assert_not_called()
                with patch.object(qualification,'trusted_pin',return_value='b'*64):
                    with self.assertRaisesRegex(ContractError,'not_qualified'):
                        visibility.bind_session(memory,session,3,_locked_qualification=(bundle,scope))
                capsule.write_text('{}')
                with self.assertRaises(ValueError):
                    visibility.bind_session(memory,session,3,_locked_qualification=(bundle,scope))
                current.assert_not_called();memory.read.assert_not_called()
            with patch.object(visibility,'current',return_value=(root,pin,{}, {},dict(package_sha256=PACKAGE_SHA,safety={}))) as current:
                with self.assertRaisesRegex(ValueError,'PID mismatch'):
                    visibility.bind_session(memory,session,3)
                current.assert_called_once_with()

    def test_repeated_registration_checks_identity_while_admission_still_qualifies(self):
        from host_runtime.desktop_backend import SessionRegistration
        from host_runtime import native6_qualification as qualification,macro_bundle
        from host_runtime.contracts import ContractError
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manifest=root/'manifest.json';manifest.write_text('{"fixture":true}')
            pin=hashlib.sha256(manifest.read_bytes()).hexdigest()
            session=root/'session.json';session.write_text(json.dumps(dict(run_directory=str(root))))
            bundle=root/'bundle.json'
            descriptor=dict(schema_version=14,kind=qualification.KIND,runtime_root=str(root),runtime_manifest_sha256=pin)
            bundle.write_text(json.dumps(descriptor))
            with patch.object(qualification,'runtime_root',return_value=root), \
                    patch.object(qualification,'trusted_pin',return_value=pin),patch.object(macro_bundle,'load_bundle') as load:
                SessionRegistration.trusted(session,root=root,macro_bundle=bundle,_metadata_only=True)
                load.assert_not_called()
                SessionRegistration.trusted(session,root=root,macro_bundle=bundle)
                load.assert_called_once_with(bundle.resolve(),dict(run_directory=str(root)))
                manifest.write_text('{"fixture":false}')
                with self.assertRaisesRegex(ContractError,'not_qualified'):
                    SessionRegistration.trusted(session,root=root,macro_bundle=bundle,_metadata_only=True)
                manifest.write_text('{"fixture":true}')
                descriptor['runtime_root']=str(root/'different');bundle.write_text(json.dumps(descriptor))
                with self.assertRaisesRegex(ContractError,'not_qualified'):
                    SessionRegistration.trusted(session,root=root,macro_bundle=bundle,_metadata_only=True)

    def test_host_locked_qualification_reuses_files_but_opens_fresh_memory(self):
        from host_runtime import macro_live,native6_qualification as qualification,native6_transport
        from host_runtime.native6_runtime_contract import ACTIONS,FLAGS,PACKAGE_SHA
        from host_runtime.contracts import ContractError
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            descriptor=dict(schema_version=14,kind=qualification.KIND,runtime_root=str(root),runtime_manifest_sha256='a'*64)
            bundle_path=root/'bundle.json';bundle_path.write_text(json.dumps(descriptor))
            registry=root/'registry.json';registry.write_text('{}')
            session=dict(pid=123,registry=str(registry),scenario=dict(commander_id=COMMANDER,
                computer_player_index=3,opponent_player_index=4,observer_player_index=2,participant_count=2,
                map_id='map_mp_2_black1b',faction='Soviet',origin_region='region_8_3'))
            session_path=root/'session.json';session_path.write_text(json.dumps(session))
            scope=qualification.Native6Scope(PACKAGE_SHA,tuple(zip(ACTIONS,FLAGS)),qualification.REGIONS,(),
                runtime_root=root,runtime_manifest_sha256='a'*64)
            memory=Mock(side_effect=RuntimeError('fresh_read_only_memory_entry'))
            with patch.object(macro_live,'load_bundle') as load, \
                    patch.object(qualification,'runtime_root',return_value=root), \
                    patch.object(qualification,'trusted_pin',return_value='a'*64), \
                    patch.object(native6_transport,'native_module',return_value=(None,SimpleNamespace(Memory=memory))):
                with self.assertRaisesRegex(RuntimeError,'fresh_read_only_memory_entry'):
                    macro_live.MacroSampler(session_path,bundle_path,_locked_qualification=(descriptor,scope))
                load.assert_not_called();memory.assert_called_once_with(123,session)
                with patch.object(qualification,'trusted_pin',return_value='b'*64):
                    with self.assertRaisesRegex(ContractError,'not_qualified'):
                        macro_live.MacroSampler(session_path,bundle_path,_locked_qualification=(descriptor,scope))
                self.assertEqual(memory.call_count,1)

    def test_transport_expiry_requires_the_matching_sdk_no_publication_receipt(self):
        from host_runtime.native6_transport import MacroPolicyProbe
        from host_runtime.contracts import ContractError
        transport=MacroPolicyProbe.__new__(MacroPolicyProbe)
        transport._lifecycle_lock=threading.RLock()
        def expired(*args,**kwargs):raise ValueError('unified_expired_before_dispatch')
        transport._probe=SimpleNamespace(apply=expired,receipts={
            'command':dict(rejected='expired_before_dispatch',unknown=False,native=None)})
        with self.assertRaisesRegex(ContractError,'macro_plan_expired_before_native_dispatch'):
            transport.apply(['attackenemy'],900,'command',not_after_frame=900)
        for receipt in ({},dict(rejected='expired_before_dispatch',unknown=True,native=None),
                        dict(rejected='expired_before_dispatch',unknown=False,native={'ack':1})):
            transport._probe.receipts['command']=receipt
            with self.assertRaisesRegex(ValueError,'unified_expired_before_dispatch'):
                transport.apply(['attackenemy'],900,'command',not_after_frame=900)

    def test_normal_native6_admission_reaches_capacity_and_reports_contract_failures(self):
        from fixtures import binding,snapshot
        from host_runtime.contracts import ContractError
        from host_runtime import desktop_backend,native6_presence,native5_capacity_preflight_v1 as capacity
        from host_runtime.native6_qualification import Native6Scope,REGIONS
        from host_runtime.native6_runtime_contract import ACTIONS,FLAGS,PACKAGE_SHA
        from host_runtime.profiles import normalize_profile
        identity=binding(commander=COMMANDER)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);build=root/'build';build.mkdir()
            (build/'build-manifest.json').write_text('{}')
            library=root/'library.json';library.write_text('{}')
            game=root/'Game.exe';game.write_bytes(b'fixture')
            scope=Native6Scope(PACKAGE_SHA,tuple(zip(ACTIONS,FLAGS)),REGIONS,())
            raw=snapshot(capabilities=dict(production_focus=['native_baseline'],regions=['region_1_3','region_8_3']),
                macro_control=dict(mode='macro_native',available_actions=['budgetarmy'],production_counts={},region_targets={}))
            session=dict(session_id=identity.session_id,pid=123,start_time='2026-11-14T10:00:00+00:00',
                run_directory=str(root/'session'),game=str(game),mod_sha256=PACKAGE_SHA,
                scenario=dict(map_id='map_mp_2_black1b'))
            sampler=SimpleNamespace(session=session,bundle={'build':str(build)},scope=scope,
                collect=lambda:raw,footprint=lambda:{'fixture':True},close=Mock())
            draft=dict(schema_version=1,profile_id=COMMANDER,name='Offline',revision=1,
                connection_id=identity.connection_id,model='fixture-model',doctrine='assault',
                custom_traits='己方中等原生电脑在1v2中自然战胜两名同队凶残电脑。')
            effective=normalize_profile(draft)
            profile=dict(profile_id=COMMANDER,name='Offline',revision=1,provider='DeepSeek',draft=draft,
                effective=dict(model=effective.model,effective_hash=effective.effective_hash),
                library_hash=hashlib.sha256(library.read_bytes()).hexdigest())
            registration=SimpleNamespace(session_path='fixture',macro_bundle='fixture')
            limits=SimpleNamespace(public=lambda:{})
            with patch.object(macro_desktop,'MacroSampler',return_value=sampler), \
                    patch.object(desktop_backend,'_module',return_value=SimpleNamespace(check_backend_available=lambda name:None)), \
                    patch.object(native6_presence,'require_unused_macro_process') as unused:
                result=macro_desktop.check(None,registration,profile,str(uuid.uuid4()),root,library,limits)
                self.assertIn('attackenemy',result.capabilities['available_macro_actions'])
                self.assertEqual(len(result.capabilities['available_macro_actions']),14)
                unused.assert_called_once()
                with patch.object(capacity,'check_native5_capacity',side_effect=ValueError('capacity_native5_fixed_grammar_required')):
                    with self.assertRaisesRegex(ContractError,'model_context_capacity_contract_invalid'):
                        macro_desktop.check(None,registration,profile,str(uuid.uuid4()),root,library,limits)
            self.assertEqual(sampler.close.call_count,2)

    def test_observation_preserves_its_public_tuple_and_reuses_qualified_metadata(self):
        scope=object();bundle={'qualified':True};raw={'paused':False}
        session={'session_id':'fixture','scenario':{'map_id':'fixture'}}
        sampler=SimpleNamespace(session=session,bundle=bundle,scope=scope,
            collect=Mock(return_value=raw),footprint=Mock(return_value={'qualified':True}),close=Mock())
        registration=SimpleNamespace(session_path='session',macro_bundle='bundle')
        with patch.object(macro_desktop,'MacroSampler',return_value=sampler) as create:
            observed=macro_desktop._observed_session(registration,COMMANDER)
        create.assert_called_once_with('session','bundle')
        self.assertIs(observed[4],bundle);self.assertIs(observed[5],scope)
        sampler.close.assert_called_once()
        with patch.object(macro_desktop,'_observed_session',return_value=observed):
            self.assertEqual(macro_desktop.observe(registration,COMMANDER,'state'),observed[:4])

    def test_qualified_native6_can_request_early_and_pause_still_suppresses_actions(self):
        host=MacroHost.__new__(MacroHost)
        host.strategic_only=True;host.latest={'paused':False}
        host.controller=SimpleNamespace(available_actions=lambda at:('budgetarmy',))
        host.sampler=SimpleNamespace(scope=SimpleNamespace(production_counts={}))
        host.update_macro_control(2.)
        self.assertEqual(host.latest['macro_control']['available_actions'],[])
        host.sampler.scope.minimum_model_game_seconds=0.
        host.update_macro_control(2.)
        self.assertEqual(host.latest['macro_control']['available_actions'],['budgetarmy'])
        host.latest['paused']=True;host.update_macro_control(2.)
        self.assertEqual(host.latest['macro_control']['available_actions'],[])
