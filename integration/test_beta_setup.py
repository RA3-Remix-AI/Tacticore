"""First-use file preparation and real discovery broker, no Game/model IO."""
from dataclasses import asdict
from contextlib import closing
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch
from types import SimpleNamespace
import sqlite3

from host_runtime import beta_setup as s,native6_qualification as q,beta_launch,beta_setup_upgrade as upgrade
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
        base_config=self.game.parent.parent/beta_launch.ENTRY
        base_config.write_bytes(b'set-exe Data/RA3_1.12.game\nadd-big Data/Core.big\n')
        (self.game.parent/'Core.big').write_bytes(b'synthetic-base-data')
        patch.object(beta_launch,'BASE_PINS',{beta_launch.ENTRY:hashlib.sha256(base_config.read_bytes()).hexdigest()}).start()
        patch.object(s,'no_game').start();patch.object(upgrade,'no_game').start()
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

    def empty_ledgers(self):
        from host_runtime.desktop_backend import DesktopBackend
        backend=DesktopBackend(SimpleNamespace(state_dir=self.state));backend.close()

    def next_manifest(self):
        for module in (s,q):
            old=module.current.return_value
            module.current.return_value=(old[0],'b'*64,*old[2:])

    def test_launch_uses_the_verified_game_and_base_config_without_the_version_launcher(self):
        (self.game.parent.parent/'RA3.exe').unlink()
        s.prepare(self.game,self.mod)
        with patch.object(s.subprocess,'Popen') as spawn:
            self.assertTrue(s.launch()['game_launch_requested'])
        self.assertEqual(spawn.call_args.args[0],[str(self.game),'-ui','-win','-modConfig',
            str(self.mods/'TFCommander_1.0.SkuDef'),'-config',str(self.game.parent.parent/beta_launch.ENTRY)])
        self.assertEqual(spawn.call_args.kwargs['cwd'],self.game.parent.parent)

    def test_changed_base_chain_or_private_launch_record_never_starts_any_process(self):
        s.prepare(self.game,self.mod);record,_=load_policy(self.state)
        with patch.object(s.subprocess,'Popen') as spawn:
            base=self.game.parent.parent/beta_launch.ENTRY;original=base.read_bytes();base.write_bytes(b'changed')
            with self.assertRaises(ContractError):s.launch()
            base.write_bytes(original)
            path=s.launcher_path(self.state,record);raw=json.loads(path.read_text(encoding='utf-8'));raw['base_config']='C:/unowned/other.exe'
            path.write_text(json.dumps(raw),encoding='utf-8')
            with self.assertRaises(ContractError):s.launch()
            spawn.assert_not_called()

    def test_post_validation_launch_json_change_cannot_select_the_executed_base(self):
        s.prepare(self.game,self.mod);real_load=s.load_policy
        def validated_then_changed(*args):
            result=real_load(*args);path=s.launcher_path(self.state,result[0])
            record=json.loads(path.read_text(encoding='utf-8'));record['base_config']='C:/unowned/attacker.SkuDef'
            path.write_text(json.dumps(record),encoding='utf-8');return result
        with patch.object(s,'load_policy',side_effect=validated_then_changed),patch.object(s.subprocess,'Popen') as spawn:
            s.launch()
        self.assertEqual(spawn.call_args.args[0][-1],str(self.game.parent.parent/beta_launch.ENTRY))

    def test_legacy_never_started_setup_refresh_preserves_old_bytes_and_profile(self):
        s.prepare(self.game,self.mod);self.empty_ledgers()
        from host_runtime.session_discovery_native import NAME
        target=self.state/NAME;old=json.loads(target.read_text(encoding='utf-8'))
        old_bundle=Path(old['files']['macro_bundle']);legacy=self.state/'sessions/native6-trial.json'
        old_bundle.rename(legacy);old['files']['macro_bundle']=str(legacy)
        target.write_text(json.dumps(old),encoding='utf-8');old_bytes=target.read_bytes();bundle_bytes=legacy.read_bytes()
        sentinel=self.home/'profile.keep';sentinel.write_bytes(b'untouched-profile-and-credentials')
        (self.state/'game-launch.json').write_text('{"schema_version":1,"launcher":"old-launcher-data-only"}',encoding='utf-8')
        self.next_manifest();result=s.status();self.assertTrue(result['prepared'])
        new,_=load_policy(self.state)
        self.assertEqual(new['runtime_manifest_sha256'],'b'*64);self.assertNotEqual(new['policy_id'],old['policy_id'])
        self.assertEqual(legacy.read_bytes(),bundle_bytes);self.assertEqual(sentinel.read_bytes(),b'untouched-profile-and-credentials')
        backup=self.state/'setup-history'/hashlib.sha256(old_bytes).hexdigest()
        self.assertEqual((backup/target.name).read_bytes(),old_bytes)
        self.assertEqual((backup/legacy.name).read_bytes(),bundle_bytes)
        for name,tables in [('desktop-launch-index.sqlite3',['launches']),('host-runtime.sqlite3',['runs','commands','events','native_sequences'])]:
            with closing(sqlite3.connect(self.state/name)) as db:
                self.assertTrue(all(db.execute('SELECT count(*) FROM '+table).fetchone()[0]==0 for table in tables))

    def test_any_past_host_journal_prevents_manifest_refresh_and_preserves_policy(self):
        s.prepare(self.game,self.mod);self.empty_ledgers()
        from host_runtime.session_discovery_native import NAME
        target=self.state/NAME;original=target.read_bytes()
        with closing(sqlite3.connect(self.state/'host-runtime.sqlite3')) as db:
            db.execute("INSERT INTO runs VALUES ('unclassified-old-run','{}','now')")
            db.commit()
        self.next_manifest()
        with self.assertRaisesRegex(ContractError,'beta_setup_changed_requires_migration'):s.status()
        self.assertEqual(target.read_bytes(),original)
        with closing(sqlite3.connect(self.state/'host-runtime.sqlite3')) as db:self.assertEqual(db.execute('SELECT count(*) FROM runs').fetchone()[0],1)

    def test_missing_original_ledger_is_not_recreated_to_admit_an_upgrade(self):
        s.prepare(self.game,self.mod);self.empty_ledgers()
        from host_runtime.session_discovery_native import NAME
        original=(self.state/NAME).read_bytes();missing=self.state/'host-runtime.sqlite3';missing.unlink()
        self.next_manifest();self.guard_mock.reset_mock()
        with self.assertRaisesRegex(ContractError,'beta_setup_changed_requires_migration'):s.status()
        self.assertFalse(missing.exists());self.assertEqual((self.state/NAME).read_bytes(),original)
        self.guard_mock.assert_not_called()

    def test_interrupted_switch_is_retryable_and_both_host_ledgers_stay_locked(self):
        s.prepare(self.game,self.mod);self.empty_ledgers()
        from host_runtime.session_discovery_native import NAME
        original=(self.state/NAME).read_bytes();self.next_manifest()
        def interrupted(*_):
            for name in upgrade.DATABASES:
                with closing(sqlite3.connect(self.state/name,timeout=0,isolation_level=None)) as contender:
                    with self.assertRaises(sqlite3.OperationalError):contender.execute('BEGIN IMMEDIATE')
            raise OSError('simulated_interruption_before_atomic_policy_replace')
        with patch.object(s,'replace_policy',side_effect=interrupted):
            with self.assertRaises(OSError):s.status()
        self.assertEqual((self.state/NAME).read_bytes(),original)
        self.assertTrue(s.status()['prepared'])
        backup=self.state/'setup-history'/hashlib.sha256(original).hexdigest()/NAME
        self.assertEqual(backup.read_bytes(),original)

    def test_existing_game_or_launcher_prevents_refresh_before_metadata_replacement(self):
        s.prepare(self.game,self.mod);self.empty_ledgers()
        from host_runtime.session_discovery_native import NAME
        original=(self.state/NAME).read_bytes();self.next_manifest()
        with patch.object(s,'no_game',side_effect=ContractError('beta_game_already_running')):
            with self.assertRaisesRegex(ContractError,'beta_game_already_running'):s.status()
        self.assertEqual((self.state/NAME).read_bytes(),original)

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
