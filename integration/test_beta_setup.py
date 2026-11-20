"""First-use file preparation, runtime change and maintenance guard; no Game/model IO."""
from contextlib import redirect_stdout
import io
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from host_runtime import beta_setup as s, native_runtime as q, native_runtime_contract as contract, beta_launch
from host_runtime.contracts import ContractError
from host_runtime.session_discovery_native import NAME, SCOPE


def local(value, *, existing=True):
    """Tests run on any OS; the Windows path policy is exercised elsewhere."""
    return Path(value)


class BetaSetup(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.base=Path(temporary.name)
        self.addCleanup(patch.stopall)
        self.root=self.base/'runtime';self.home=self.base/'user/Tacticore/beta1';self.state=self.home/'desktop-runtime'
        self.mods=self.base/'Documents/Red Alert 3/Mods/Tacticore-beta4';self.legacy=self.base/'user/Tacticore'
        self.game=self.base/'Game/Data/RA3_1.12.game';self.mod=self.base/'owned.big'
        self.game.parent.mkdir(parents=True);self.game.write_bytes(b'synthetic-game-not-executable')
        self.mod.write_bytes(b'synthetic-owned-mod')
        base_config=self.game.parent.parent/beta_launch.ENTRY
        base_config.write_bytes(b'set-exe Data/RA3_1.12.game\nadd-big Data/Core.big\n')
        (self.game.parent/'Core.big').write_bytes(b'synthetic-base-data')
        patch.object(beta_launch,'BASE_PINS',{beta_launch.ENTRY:hashlib.sha256(base_config.read_bytes()).hexdigest()}).start()
        for module in (s,beta_launch,q,contract):patch.object(module,'plain_local',local).start()
        self.no_game=patch.object(s,'no_game').start()
        self.game_sha=hashlib.sha256(self.game.read_bytes()).hexdigest()
        self.mod_sha=hashlib.sha256(self.mod.read_bytes()).hexdigest()
        for name in ('registry.json','package.json'):
            target=self.root/'qualification'/name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text('{}',encoding='utf-8')
        self.pin='a'*64
        self.full_checks=0
        def current():
            self.full_checks+=1
            return self.root,self.pin,dict(files={}),dict(protocol_version=7)
        patch.object(s,'current',side_effect=current).start()
        for module in (s,q):
            patch.object(module,'runtime_root',side_effect=lambda:self.root).start()
            patch.object(module,'trusted_pin',side_effect=lambda:self.pin).start()
        patch.object(s,'GAME_SHA',self.game_sha).start();patch.object(s,'PACKAGE_SHA',self.mod_sha).start()
        patch.object(s,'locations',return_value=(self.home,self.state,self.mods,self.legacy)).start()

    def policy(self):
        return s.load_policy(self.state,json.loads((self.state/NAME).read_text(encoding='utf-8')))

    def launches(self,count):
        """Recorded launches in the desktop launch index, as the backend writes them."""
        self.state.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.state/s.LAUNCH_INDEX) as db:
            db.execute('CREATE TABLE IF NOT EXISTS launches (run_id TEXT)')
            db.executemany('INSERT INTO launches VALUES (?)',[(str(index),) for index in range(count)])
        db.close()

    def test_preparation_creates_no_fictitious_session_and_is_idempotent(self):
        result=s.prepare(self.game,self.mod)
        self.assertTrue(result['prepared']);self.assertFalse(result['host_started'])
        self.assertEqual(list(self.state.rglob('session.json')),[])
        record,policy=self.policy()
        self.assertEqual(record['kind'],s.KIND);self.assertEqual(record['scope'],dict(SCOPE,native_epoch=7))
        self.assertEqual(policy.native_epoch,7)
        self.assertEqual(s.prepare(self.game,self.mod),result)
        self.assertEqual(self.policy()[0]['policy_id'],record['policy_id'])
        self.assertEqual((self.mods/'TFCommander.big').read_bytes(),self.mod.read_bytes())
        self.assertFalse((self.state/s.ARCHIVE).exists())

    def test_launch_verifies_the_whole_runtime_then_uses_the_verified_game_and_base_config(self):
        s.prepare(self.game,self.mod);before=self.full_checks
        with patch.object(s.subprocess,'Popen',create=True) as spawn,\
                patch.object(s.subprocess,'CREATE_NO_WINDOW',0,create=True):
            self.assertTrue(s.launch()['game_launch_requested'])
        self.assertEqual(self.full_checks,before+1)
        self.assertEqual(spawn.call_args.args[0],[str(self.game),'-win','-modConfig',
            str(self.mods/'TFCommander_1.0.SkuDef'),'-config',str(self.game.parent.parent/beta_launch.ENTRY)])
        self.assertEqual(spawn.call_args.kwargs['cwd'],self.game.parent.parent)

    def test_changed_base_chain_or_private_launch_record_never_starts_any_process(self):
        s.prepare(self.game,self.mod);record,_=self.policy()
        with patch.object(s.subprocess,'Popen') as spawn,patch.object(s.subprocess,'CREATE_NO_WINDOW',0,create=True):
            base=self.game.parent.parent/beta_launch.ENTRY;original=base.read_bytes();base.write_bytes(b'changed')
            with self.assertRaises(ContractError):s.launch()
            base.write_bytes(original)
            path=s.launcher_path(self.state,record);raw=json.loads(path.read_text(encoding='utf-8'))
            raw['base_config']='C:/unowned/other.exe';path.write_text(json.dumps(raw),encoding='utf-8')
            with self.assertRaises(ContractError):s.launch()
            spawn.assert_not_called()

    def test_running_game_prevents_launch_and_any_owned_file_creation(self):
        self.no_game.side_effect=ContractError('beta_game_already_running')
        with self.assertRaisesRegex(ContractError,'beta_game_already_running'):s.prepare(self.game,self.mod)
        self.assertFalse(self.mods.exists())
        with self.assertRaisesRegex(ContractError,'beta_game_already_running'):s.launch()

    def test_runtime_change_archives_earlier_runs_and_refreshes_the_policy(self):
        s.prepare(self.game,self.mod);old,_=self.policy()
        self.launches(3)
        self.pin='b'*64
        result=s.status()
        self.assertTrue(result['prepared']);self.assertTrue(result['setup_changed'])
        record,_=self.policy()
        self.assertNotEqual(record['policy_id'],old['policy_id'])
        self.assertEqual(record['runtime_manifest_sha256'],'b'*64)
        self.assertEqual(s.archived_through(self.state),3)
        self.launches(2)
        self.assertFalse(s.status()['setup_changed'])
        self.assertEqual(s.archived_through(self.state),3)

    def test_runtime_change_while_a_game_runs_changes_nothing(self):
        s.prepare(self.game,self.mod);raw=(self.state/NAME).read_bytes();self.launches(1)
        self.pin='b'*64;self.no_game.side_effect=ContractError('beta_game_already_running')
        with self.assertRaisesRegex(ContractError,'beta_game_already_running'):s.status()
        self.assertEqual((self.state/NAME).read_bytes(),raw);self.assertFalse((self.state/s.ARCHIVE).exists())

    def test_old_setup_with_another_mod_requires_the_update_without_archiving(self):
        s.prepare(self.game,self.mod);self.launches(1)
        record=json.loads((self.state/NAME).read_text());record['kind']='native7_installed_discovery_v1'
        record['files']['mod_sha256']='c'*64;(self.state/NAME).write_text(json.dumps(record))
        self.assertEqual(s.status()['reason_code'],'beta_mod_update_required')
        self.assertFalse((self.state/s.ARCHIVE).exists())

    def test_wrong_input_or_existing_unrelated_mod_never_gets_overwritten(self):
        self.mod.write_bytes(b'wrong-mod')
        with self.assertRaisesRegex(ContractError,'beta_mod_unsupported'):s.prepare(self.game,self.mod)
        self.mod.write_bytes(b'synthetic-owned-mod');self.mods.mkdir(parents=True)
        destination=self.mods/'TFCommander.big';destination.write_bytes(b'unrelated-existing')
        with self.assertRaisesRegex(ContractError,'beta_owned_file_conflict'):s.prepare(self.game,self.mod)
        self.assertEqual(destination.read_bytes(),b'unrelated-existing')

    def test_changed_policy_cannot_silently_select_another_package_or_scope(self):
        s.prepare(self.game,self.mod);record,policy=self.policy()
        for mutation in (lambda r:r['scope'].update(player_id=4),lambda r:r['files'].update(mod_big=str(self.mod)),
                         lambda r:r.update(runtime_manifest_sha256='b'*64),lambda r:r.update(kind='other')):
            bad=json.loads(json.dumps(record));mutation(bad)
            with self.assertRaises(ContractError):s.load_policy(self.state,bad)


class MaintenanceGuard(unittest.TestCase):
    def invoke(self):
        stdin=SimpleNamespace(buffer=io.BytesIO(b'{"operation":"guard"}\n'))
        with patch('sys.stdin',stdin),redirect_stdout(io.StringIO()) as output:
            code=s.main()
        return code,json.loads(output.getvalue())

    def test_running_game_blocks_an_update(self):
        with patch.object(s,'no_game',side_effect=ContractError('beta_game_already_running')):
            code,result=self.invoke()
        self.assertEqual(code,2);self.assertEqual(result['error']['code'],'beta_game_already_running')

    def test_no_game_means_no_native_state_and_allows_the_update(self):
        with patch.object(s,'no_game') as absent:
            code,result=self.invoke()
        self.assertEqual(code,0);self.assertTrue(result['result']['quiet']);absent.assert_called_once()


if __name__=='__main__':unittest.main()
