"""Opening admission and early model readiness, without Game."""
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

    def test_repeated_registration_checks_identity_while_admission_still_qualifies(self):
        from host_runtime.desktop_backend import SessionRegistration
        from host_runtime import native_runtime as qualification,macro_bundle
        from host_runtime.contracts import ContractError
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manifest=root/'manifest.json';manifest.write_text('{"fixture":true}')
            pin=hashlib.sha256(manifest.read_bytes()).hexdigest()
            session=root/'session.json';session.write_text(json.dumps(dict(run_directory=str(root))))
            bundle=root/'bundle.json'
            descriptor=dict(schema_version=qualification.DESCRIPTOR_VERSION,kind=qualification.KIND,
                            runtime_root=str(root),runtime_manifest_sha256=pin)
            bundle.write_text(json.dumps(descriptor))
            with patch.object(qualification,'runtime_root',return_value=root), \
                    patch.object(qualification,'trusted_pin',return_value=pin),patch.object(macro_bundle,'load_bundle') as load:
                SessionRegistration.trusted(session,root=root,macro_bundle=bundle,_metadata_only=True)
                load.assert_not_called()
                SessionRegistration.trusted(session,root=root,macro_bundle=bundle)
                load.assert_called_once_with(bundle.resolve(),dict(run_directory=str(root)))
                manifest.write_text('{"fixture":false}')
                with self.assertRaisesRegex(ContractError,'not_verified'):
                    SessionRegistration.trusted(session,root=root,macro_bundle=bundle,_metadata_only=True)
                manifest.write_text('{"fixture":true}')
                descriptor['runtime_root']=str(root/'different');bundle.write_text(json.dumps(descriptor))
                with self.assertRaisesRegex(ContractError,'not_verified'):
                    SessionRegistration.trusted(session,root=root,macro_bundle=bundle,_metadata_only=True)


    def test_transport_expiry_requires_the_matching_sdk_no_publication_receipt(self):
        from host_runtime.native_transport import MacroPolicyProbe
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

    def test_normal_native_admission_reaches_capacity_and_reports_contract_failures(self):
        from fixtures import binding,snapshot
        from host_runtime.contracts import ContractError
        from host_runtime import desktop_backend,native_presence,model_capacity as capacity
        from host_runtime.native_runtime import NativeScope
        from host_runtime.native_runtime_contract import FLAG_ACTIONS,FLAGS,PACKAGE_SHA
        from host_runtime.profiles import normalize_profile
        identity=binding(commander=COMMANDER)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);build=root/'build';build.mkdir()
            (build/'build-manifest.json').write_text('{}')
            library=root/'library.json';library.write_text('{}')
            game=root/'Game.exe';game.write_bytes(b'fixture')
            regions=tuple((action,'region_8_3') for action in ('deploydefense','regroup','reinforce','withdraw'))
            scope=NativeScope(PACKAGE_SHA,tuple(zip(FLAG_ACTIONS,FLAGS)),regions,())
            raw=snapshot(capabilities=dict(production_focus=['native_baseline'],regions=['region_1_3','region_8_3']),
                macro_control=dict(mode='macro_native',available_actions=['budgetarmy'],production_counts={},
                    region_targets={},intent_contract=scope.intent_contract))
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
                    patch.object(native_presence,'require_unused_macro_process') as unused:
                result=macro_desktop.check(None,registration,profile,str(uuid.uuid4()),root,library,limits)
                self.assertIn('attackenemy',result.capabilities['available_macro_actions'])
                self.assertEqual(len(result.capabilities['available_macro_actions']),15)
                self.assertEqual(result.capabilities['native_transport_protocol'],7)
                unused.assert_called_once()
                with patch.object(capacity,'check_model_capacity',side_effect=ValueError('capacity_fixed_grammar_required')):
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

    def test_native_scope_can_request_early_and_pause_still_suppresses_actions(self):
        host=MacroHost.__new__(MacroHost)
        host.strategic_only=True;host.latest={'paused':False}
        host.controller=SimpleNamespace(available_actions=lambda at:('budgetarmy',))
        host.sampler=SimpleNamespace(scope=SimpleNamespace(production_counts={},minimum_model_game_seconds=30.,
            intent_contract='native7_independent_development_v1',regional_action_regions={}))
        host.update_macro_control(2.)
        self.assertEqual(host.latest['macro_control']['available_actions'],[])
        host.sampler.scope.minimum_model_game_seconds=0.
        host.update_macro_control(2.)
        self.assertEqual(host.latest['macro_control']['available_actions'],['budgetarmy'])
        host.latest['paused']=True;host.update_macro_control(2.)
        self.assertEqual(host.latest['macro_control']['available_actions'],[])
