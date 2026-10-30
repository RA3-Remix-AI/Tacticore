"""Real control-only isolated pipes; synthetic existing runs in D scratch only."""
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'integration'),str(ROOT/'strategy'),str(ROOT)]
from host_runtime.control_only_server_v1 import ControlOnlyServiceV1
from host_runtime import desktop_backend as backend_module
import test_host_runtime_desktop_backend as baseline

SCRATCH=Path('D:/CodexScratch/tacticore-control-only-channel-20261029-v1/tests')


class Pipe:
    def __init__(self,state):
        module='host_runtime.control_only_server_v1'
        code=f"import sys,runpy;sys.prefix=sys.exec_prefix={json.dumps(str(ROOT/'.venv'))};sys.path[:0]={json.dumps([str(ROOT/'integration'),str(ROOT/'.venv/Lib/site-packages')])};sys.argv[0]='{module}';runpy.run_module('{module}',run_name='__main__')"
        self.process=subprocess.Popen([sys.executable,'-I','-S','-B','-c',code,'--state-dir',str(state)],
            cwd=ROOT/'integration',stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.replies=queue.Queue()
        def read():
            while True:
                row=self.process.stdout.readline(65537);self.replies.put(row)
                if not row:return
        self.thread=threading.Thread(target=read,daemon=True);self.thread.start()

    def call(self,operation,args,request_id=None):
        value=dict(schema_version=1,request_id=request_id or str(uuid.uuid4()),operation=operation,args=args)
        self.process.stdin.write((json.dumps(value)+'\n').encode());self.process.stdin.flush()
        reply=json.loads(self.replies.get(timeout=8));assert reply['request_id']==value['request_id']
        return reply

    def close(self):
        self.process.stdin.close()
        try:self.process.wait(timeout=8)
        except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=3)
        self.thread.join(timeout=1)
        error=self.process.stderr.read()
        for stream in (self.process.stdout,self.process.stderr):stream.close()
        assert self.process.returncode==0,error


class ControlOnlyTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True,exist_ok=True)

    def case(self):
        case=baseline.DesktopBackendTests(methodName='runTest');original=tempfile.TemporaryDirectory
        with patch.object(tempfile,'TemporaryDirectory',side_effect=lambda **kw:original(dir=SCRATCH,**kw)):case.setUp()
        self.addCleanup(case.tearDown)
        result,request,args=case.start();case.status_file(result)
        # Broken registration/library and an unreadable-as-a-library sentinel.
        case.lib.write_bytes(b'NOT A CONNECTION LIBRARY')
        (case.root/'desktop-runtime-config.json').write_bytes(b'BROKEN REGISTRATION')
        return case,result

    def pipe(self,state):
        value=Pipe(state);self.addCleanup(value.close);return value

    def test_real_cold_pipe_status_resume_stop_and_diagnostics_ignore_broken_library(self):
        case,run=self.case();pipe=self.pipe(case.store.state_dir)
        resumed=pipe.call('run.resume',{})
        self.assertTrue(resumed['ok'],resumed);self.assertEqual(resumed['result']['run']['run_id'],run['run_id'])
        status=pipe.call('run.status',dict(run_id=run['run_id']))
        self.assertTrue(status['ok'],status);self.assertFalse(status['result']['native_release_verified'])
        stopped=pipe.call('run.stop',dict(run_id=run['run_id'],session_id=baseline.SESSION))
        self.assertTrue(stopped['ok'],stopped)
        row=case.backend._launch(run['run_id']);stop=Path(row['output_path'])/'stop.json'
        self.assertEqual(json.loads(stop.read_bytes()),dict(session_id=baseline.SESSION))
        exported=pipe.call('diagnostics.export',dict(run_id=run['run_id']))
        self.assertTrue(exported['ok'],exported)
        self.assertEqual(len(case.spawner.commands),1) # only the artificial pre-existing run
        self.assertEqual(case.lib.read_bytes(),b'NOT A CONNECTION LIBRARY')

    def test_missing_state_resume_is_read_only_and_cannot_block_first_use(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as directory:
            state=Path(directory)/'desktop-runtime';pipe=Pipe(state)
            try:
                self.assertEqual(pipe.call('run.resume',{})['result'],dict(run=None,observation_only=True,other_unreleased_runs=0))
                self.assertFalse(state.exists())
                self.assertEqual(pipe.call('run.status',dict(run_id=str(uuid.uuid4())))['error']['code'],'run_not_found')
                self.assertFalse(state.exists())
            finally:pipe.close()

    def test_four_op_whitelist_and_extra_pid_path_exec_refused_before_store(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as directory:
            state=Path(directory)/'desktop-runtime';service=ControlOnlyServiceV1(state);self.addCleanup(service.close)
            for operation in ['run.start','run.check','profiles.list','profiles.save','session.inspect','session.discover','session.prepare','connections.configure','model.call']:
                value=service.handle(dict(schema_version=1,request_id=str(uuid.uuid4()),operation=operation,args={}))
                self.assertEqual(value['error']['code'],'operation_unsupported',operation)
            for operation,args in [('run.resume',{'path':'C:/outside'}),('run.status',{'run_id':str(uuid.uuid4()),'pid':1}),('run.stop',{'run_id':str(uuid.uuid4()),'session_id':str(uuid.uuid4()),'executable':'cmd.exe'})]:
                self.assertFalse(service.handle(dict(schema_version=1,request_id=str(uuid.uuid4()),operation=operation,args=args))['ok'])
            self.assertFalse(state.exists())

    def test_wrong_session_and_changed_session_identity_never_write_stop(self):
        case,run=self.case();pipe=self.pipe(case.store.state_dir)
        wrong=pipe.call('run.stop',dict(run_id=run['run_id'],session_id=str(uuid.uuid4())))
        self.assertEqual(wrong['error']['code'],'session_mismatch')
        value=json.loads(case.session.read_bytes());value['pid']+=1;case.session.write_text(json.dumps(value))
        changed=pipe.call('run.stop',dict(run_id=run['run_id'],session_id=baseline.SESSION))
        self.assertEqual(changed['error']['code'],'session_changed')
        self.assertFalse((Path(case.backend._launch(run['run_id'])['output_path'])/'stop.json').exists())

    def test_stop_unknown_retains_uncertain_and_never_replays_same_request(self):
        case,run=self.case();service=ControlOnlyServiceV1(case.store.state_dir);self.addCleanup(service.close)
        command=str(uuid.uuid4());request=dict(schema_version=1,request_id=command,operation='run.stop',args=dict(run_id=run['run_id'],session_id=baseline.SESSION))
        real=backend_module._atomic;calls=[]
        def write_then_unknown(path,value):
            calls.append(1);real(path,value);raise OSError('ARTIFICIAL UNKNOWN AFTER LOCAL STOP FILE')
        with patch.object(backend_module,'_atomic',side_effect=write_then_unknown):
            self.assertEqual(service.handle(request)['error']['code'],'run_state_conflict')
            self.assertTrue(service.handle(request)['ok'])
        self.assertEqual(len(calls),1)
        self.assertEqual(case.backend.journal.get_command(run['run_id'],command)['status'],'uncertain')

    def test_no_profile_or_credential_constructor_is_reachable(self):
        case,run=self.case();service=ControlOnlyServiceV1(case.store.state_dir);self.addCleanup(service.close)
        with patch('host_runtime.profile_store.ProfileStore',side_effect=AssertionError('profile forbidden')),patch('http_adapter.load_profile',side_effect=AssertionError('credential forbidden')):
            response=service.handle(dict(schema_version=1,request_id=str(uuid.uuid4()),operation='run.status',args=dict(run_id=run['run_id'])))
        self.assertTrue(response['ok'],response)
        self.assertFalse(hasattr(service.backend.backend.store,'library_path'))

    def test_partial_ledger_fails_closed_without_creating_missing_half(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as directory:
            state=Path(directory);(state/'host-runtime.sqlite3').write_bytes(b'partial')
            service=ControlOnlyServiceV1(state);self.addCleanup(service.close)
            value=service.handle(dict(schema_version=1,request_id=str(uuid.uuid4()),operation='run.resume',args={}))
            self.assertEqual(value['error']['code'],'run_history_unverifiable')
            self.assertFalse((state/'desktop-launch-index.sqlite3').exists())


if __name__=='__main__':unittest.main()
