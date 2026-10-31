"""First-use file preparation and real discovery broker, no Game/model IO."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from host_runtime import beta_setup as s,native6_qualification as q
from host_runtime.contracts import ContractError
from host_runtime.session_discovery import SessionDiscovery,ProcessIdentity,MatchObservation
from host_runtime.session_discovery_native import SCOPE,creation_start,load_policy


class BetaSetup(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.base=Path(temporary.name)
        self.root=self.base/'runtime';self.home=self.base/'user/Tacticore/beta1';self.state=self.home/'desktop-runtime'
        self.mods=self.base/'Documents/Red Alert 3/Mods/Tacticore-beta1';self.legacy=self.base/'user/Tacticore'
        self.game=self.base/'Game/Data/RA3_1.12.game';self.mod=self.base/'owned.big'
        self.game.parent.mkdir(parents=True);self.game.write_bytes(b'synthetic-game-not-executable');self.mod.write_bytes(b'synthetic-owned-mod')
        (self.game.parent.parent/'RA3.exe').write_bytes(b'synthetic-launcher-not-executable')
        self.game_sha=hashlib.sha256(self.game.read_bytes()).hexdigest();self.mod_sha=hashlib.sha256(self.mod.read_bytes()).hexdigest()
        for name in ('registry.json','package.json'):
            target=self.root/'qualification'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text('{}',encoding='utf-8')
        authority=(self.root,'a'*64,dict(files={}),dict(protocol_version=6),{})
        for module in (s,q):
            self.addCleanup(patch.stopall)
            patch.object(module,'current',return_value=authority).start()
            patch.object(module,'GAME_SHA',self.game_sha).start();patch.object(module,'PACKAGE_SHA',self.mod_sha).start()
        patch.object(s,'locations',return_value=(self.home,self.state,self.mods,self.legacy)).start()
        self.guard=patch.object(s,'guard_states');self.guard_mock=self.guard.start()

    def test_preparation_creates_no_fictitious_session_and_is_idempotent(self):
        result=s.prepare(self.game,self.mod)
        self.assertTrue(result['prepared']);self.assertFalse(result['host_started'])
        self.assertEqual(list(self.state.rglob('session.json')),[])
        record,policy=load_policy(self.state)
        self.assertEqual(record['schema_version'],2);self.assertNotIn('source_session',record)
        self.assertEqual(policy.map_id,q.MAP_ID);self.assertEqual(policy.native_epoch,6)
        self.assertEqual(s.prepare(self.game,self.mod),result)
        self.assertEqual(load_policy(self.state)[0]['policy_id'],record['policy_id'])
        self.assertEqual((self.mods/'TFCommander.big').read_bytes(),self.mod.read_bytes())

    def test_actual_broker_prepares_only_a_newly_observed_bound_session(self):
        s.prepare(self.game,self.mod);record,policy=load_policy(self.state)
        ticks=133000000000000000
        process=ProcessIdentity(123,ticks,creation_start(ticks),self.game,policy.files.mod_config)
        observation=MatchObservation(123,ticks,'b'*64,q.MAP_ID,'Soviet',3,4,2,q.COMMANDER,'region_8_3',6,True)
        registered=[]
        def register(path,bundle):
            from host_runtime.desktop_backend import SessionRegistration
            SessionRegistration.trusted(path,root=policy.session_root,macro_bundle=bundle)
            registered.append(path);return dict(registered=True)
        broker=SessionDiscovery(policy,lambda:[process],lambda *_:observation,register,lambda:[])
        self.addCleanup(broker.close)
        candidate=broker.discover({},str(uuid.uuid4()))['candidates'][0]
        receipt=broker.prepare(dict(candidate_id=candidate['candidate_id']),str(uuid.uuid4()))
        self.assertTrue(receipt['requires_preflight']);self.assertEqual(len(registered),1)
        session=json.loads(registered[0].read_text(encoding='utf-8'))
        self.assertEqual(session['pid'],123);self.assertEqual(session['process_creation_filetime'],ticks)
        self.assertEqual(session['scenario']['map_id'],q.MAP_ID)
        self.assertEqual(q.load(policy.files.macro_bundle,session)[1].native_transport_protocol,6)
        session['scenario']['map_id']='TemplePrime'
        with self.assertRaises(ContractError):q.load(policy.files.macro_bundle,session)

    def test_unreleased_history_prevents_any_owned_file_creation(self):
        self.guard_mock.side_effect=ContractError('beta_existing_run_unreleased')
        with self.assertRaises(ContractError):s.prepare(self.game,self.mod)
        self.assertFalse(self.home.exists());self.assertFalse(self.mods.exists())

    def test_wrong_input_or_existing_unrelated_mod_never_gets_overwritten(self):
        self.mod.write_bytes(b'wrong-mod')
        with self.assertRaisesRegex(ContractError,'beta_mod_unsupported'):s.prepare(self.game,self.mod)
        self.mod.write_bytes(b'synthetic-owned-mod');self.mods.mkdir(parents=True)
        destination=self.mods/'TFCommander.big';destination.write_bytes(b'unrelated-existing')
        with self.assertRaisesRegex(ContractError,'beta_owned_file_conflict'):s.prepare(self.game,self.mod)
        self.assertEqual(destination.read_bytes(),b'unrelated-existing')

    def test_changed_policy_cannot_silently_select_another_package_or_scope(self):
        s.prepare(self.game,self.mod);record,policy=load_policy(self.state)
        for mutation in (lambda r:r['scope'].update(player_id=4),lambda r:r['files'].update(mod_big=str(self.mod)),
                         lambda r:r.update(runtime_manifest_sha256='b'*64)):
            bad=json.loads(json.dumps(record));mutation(bad)
            with self.assertRaises(ContractError):s.load_policy(self.state,bad)


if __name__=='__main__':unittest.main()
