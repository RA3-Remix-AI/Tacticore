"""Actual isolated Python pipes, temporary libraries, no GUI/game/model."""
import hashlib
import json
from pathlib import Path
import queue
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'integration'),str(ROOT/'strategy'),str(ROOT)]
from host_runtime.connection_config_service_v1 import ConnectionConfigServiceV1
from host_runtime.profile_store import ProfileStore
from host_runtime import connection_config_service_v1 as module

COMMANDER='57e668b4-4d89-43bd-bc92-0dd436f046ef'
FAKE_KEY='INDEPENDENT-FAKE-PIPE-KEY-ONLY'
SCRATCH=Path('D:/CodexScratch/ra3-independent-next/fused-configuration-v1')


class IsolatedPipe:
    def __init__(self,root,configuration):
        name='host_runtime.connection_config_server_v1' if configuration else 'host_runtime.bridge_service'
        prefix=str(ROOT/'.venv');paths=[str(ROOT/'integration'),str(ROOT/'.venv/Lib/site-packages')]
        # Exactly the trusted debug Native launcher import/bootstrap contract.
        code=f"import sys,runpy;sys.prefix=sys.exec_prefix={json.dumps(prefix)};sys.path[:0]={json.dumps(paths)};sys.argv[0]='{name}';runpy.run_module('{name}',run_name='__main__')"
        argv=[sys.executable,'-I','-S','-B','-c',code,'--library',str(root/'library.v2.json'),'--state-dir',str(root/'desktop-runtime')]
        if configuration:argv+=['--registration',str(root/'desktop-runtime-config.json'),'--commander-id',COMMANDER]
        self.process=subprocess.Popen(argv,cwd=ROOT/'integration',stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.replies=queue.Queue();self.transcripts=[]
        self.closed=False
        def read():
            while True:
                line=self.process.stdout.readline(65537)
                self.replies.put(line)
                if not line:break
        self.thread=threading.Thread(target=read,daemon=True);self.thread.start()

    def call(self,operation,args):
        request=dict(schema_version=1,request_id=str(uuid.uuid4()),operation=operation,args=args)
        self.process.stdin.write((json.dumps(request)+'\n').encode('utf8'));self.process.stdin.flush()
        raw=self.replies.get(timeout=8);self.transcripts.append(raw)
        value=json.loads(raw)
        if value.get('request_id')!=request['request_id']:raise AssertionError('pipe response identity')
        if FAKE_KEY.encode() in raw:raise AssertionError('fake credential leaked')
        return value

    def close(self):
        if self.closed:return
        self.closed=True
        if self.process.poll() is None:
            self.process.stdin.close()
            try:self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=3)
        self.thread.join(timeout=1)
        error=self.process.stderr.read()
        if FAKE_KEY.encode() in error:raise AssertionError('fake credential leaked to stderr')
        for stream in (self.process.stdout,self.process.stderr):stream.close()


class FusedConfigurationIndependentTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True,exist_ok=True);self.temp=tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def pipe(self,configuration=True):
        pipe=IsolatedPipe(self.root,configuration);self.addCleanup(pipe.close);return pipe

    def configured(self):
        pipe=self.pipe();self.assertTrue(pipe.call('connections.bootstrap',{})['ok'])
        current=pipe.call('connections.configuration',{})['result'];row=current['connections'][0]
        saved=pipe.call('connections.configure',dict(schema_version=1,connection_id=row['id'],
            expected_config_fingerprint=current['config_fingerprint'],name='Independent temporary connection',provider='自定义',
            endpoint='http://127.0.0.1:9999/v1',model='independent-offline-model',credential_operation='set',api_key=FAKE_KEY))
        self.assertTrue(saved['ok'],saved);return pipe

    def assert_no_launch(self):
        db=sqlite3.connect(self.root/'desktop-runtime/desktop-launch-index.sqlite3')
        try:
            self.assertEqual(db.execute('select count(*) from launches').fetchone()[0],0)
        finally:db.close()
        registration=json.loads((self.root/'desktop-runtime-config.json').read_text())
        self.assertEqual(registration['library_sha256'],hashlib.sha256((self.root/'library.v2.json').read_bytes()).hexdigest())

    def test_real_isolated_configuration_then_new_normal_rpc_reload_is_bound_and_keyless(self):
        configuration=self.configured()
        self.assertEqual(configuration.call('run.start',{})['error']['code'],'operation_unsupported')
        normal=self.pipe(False);profiles=normal.call('profiles.list',{})['result']['profiles'];profile=profiles[0]
        self.assertEqual(profile['model'],'independent-offline-model')
        self.assertTrue(profile['validation']['ok'])
        check=normal.call('run.check',dict(profile_id=COMMANDER,profile_revision=profile['revision']))
        self.assertTrue(check['ok'],check);self.assertFalse(check['result']['ready'])
        self.assertEqual(check['result']['reason_code'],'session_unavailable')
        start=normal.call('run.start',dict(profile_id=COMMANDER,profile_revision=profile['revision'],
            session_id=str(uuid.uuid4()),ready_token='artificial-not-a-readiness-token'))
        self.assertFalse(start['ok']);self.assert_no_launch()

    def test_actual_pending_recovery_blocks_normal_admission_then_reloads_new_source(self):
        configuration=self.configured();configuration.close()
        # The existing normal pipe must still refuse new admissions during repair.
        normal=self.pipe(False);self.assertTrue(normal.call('profiles.list',{})['ok'])
        store=ProfileStore(self.root/'library.v2.json',self.root/'desktop-runtime')
        service=ConnectionConfigServiceV1(store,stopped_guard=lambda:True,registration_path=self.root/'desktop-runtime-config.json')
        current=service.configuration({});row=current['connections'][0];real=module.atomic_bytes
        def crash(path,raw):
            if Path(path)==self.root/'desktop-runtime-config.json':raise OSError('ARTIFICIAL REGISTRATION INTERRUPTION')
            return real(path,raw)
        try:
            args=dict(schema_version=1,connection_id=row['id'],expected_config_fingerprint=current['config_fingerprint'],
                name=row['name'],provider=row['provider'],endpoint=row['endpoint'],model='recovered-offline-model',credential_operation='keep')
            with patch.object(module,'atomic_bytes',side_effect=crash):
                response=service.handle(dict(schema_version=1,request_id=str(uuid.uuid4()),operation='connections.configure',args=args))
            self.assertFalse(response['ok'])
        finally:service.close();store.close()
        blocked=normal.call('run.check',dict(profile_id=COMMANDER,profile_revision=1))
        self.assertEqual(blocked['error']['code'],'connection_config_recovery_required')
        self.assertTrue(normal.call('run.resume',{})['ok'])
        repair=self.pipe();pending=repair.call('connections.configuration',{})['result']
        self.assertFalse(pending['ready']);self.assertEqual(pending['connections'],[])
        recovered=repair.call('connections.recover',pending['recovery'][0]);self.assertTrue(recovered['ok'],recovered)
        normal.close();fresh=self.pipe(False);profile=fresh.call('profiles.list',{})['result']['profiles'][0]
        self.assertEqual(profile['model'],'recovered-offline-model');self.assert_no_launch()

    def test_tauri_real_registration_acl_and_build_manifest_name_the_exact_channel(self):
        native=ROOT/'desktop-ui/src-tauri'
        acl=json.loads((native/'capabilities/main.json').read_text())
        self.assertIn('allow-connection-config-request',acl['permissions']);self.assertEqual(acl['windows'],['main'])
        self.assertIn('host_bridge::connection_config_request',(native/'src/lib.rs').read_text())
        self.assertIn('"connection_config_request"',(native/'build.rs').read_text())
        generated=(native/'permissions/autogenerated/connection_config_request.toml').read_text()
        self.assertIn('identifier = "allow-connection-config-request"',generated)
        self.assertIn('commands.allow = ["connection_config_request"]',generated)
        source=(native/'src/host_bridge.rs').read_text()
        self.assertIn('"host_runtime.connection_config_server_v1"',source)
        self.assertIn('slot.process=None;slot.source=None;slot.configuration=None;slot.configuration_source=None;',source)
        self.assertIn('format!("{:x}", Sha256::digest(&library)) != record.library_sha256',source)


if __name__=='__main__':unittest.main()
