"""Discovery RPC and reopen-observation behavior without a live process."""
import json
from contextlib import contextmanager
import os
from pathlib import Path
import types
import unittest
from unittest.mock import patch
import uuid

from host_runtime.bridge_service import BridgeService
from host_runtime.contracts import ContractError
from host_runtime.desktop_session_registry import register_root
import test_host_runtime_desktop_backend as fixture


class Discovery:
    def __init__(self, owner):
        self.owner=owner;self.policy=types.SimpleNamespace(session_root=owner.backend.registration_root)
        self.calls=[];self.closed=False
    def discover(self,args,request_id):
        self.calls.append(('discover',args,request_id))
        return dict(candidates=[dict(candidate_id=fixture.PROFILE,display_name='TemplePrime / P3 苏军')],
                    issues=[],state='select_session',native_execution_started=False)
    def prepare(self,args,request_id):
        self.calls.append(('prepare',args,request_id))
        register_root(self.policy.session_root,self.owner.store.state_dir)
        self.owner.backend.register_session(self.owner.session,self.owner.report,self.owner.persistent)
        return dict(registered=True,session_id=fixture.SESSION,requires_preflight=True,registration_reload_required=True,
                    native_execution_started=False)
    def close(self):
        self.closed=True


class SessionFlowTests(unittest.TestCase):
    setUp=fixture.DesktopBackendTests.setUp
    tearDown=fixture.DesktopBackendTests.tearDown
    new_backend=fixture.DesktopBackendTests.new_backend
    ready=fixture.DesktopBackendTests.ready
    start_args=fixture.DesktopBackendTests.start_args
    start=fixture.DesktopBackendTests.start
    status_file=fixture.DesktopBackendTests.status_file
    assertCode=fixture.DesktopBackendTests.assertCode

    def rpc(self,operation,args=None):
        return BridgeService(self.store,self.backend).handle(dict(schema_version=1,request_id=str(uuid.uuid4()),
                                                               operation=operation,args=args or {}))

    def test_missing_discovery_is_explicit_and_existing_registration_still_works(self):
        for operation,args in (('session.discover',{}),('session.prepare',dict(candidate_id=fixture.PROFILE))):
            result=self.rpc(operation,args)
            self.assertEqual(result['error']['code'],'session_discovery_unavailable')
        self.assertTrue(self.ready()['ready'])
        self.assertEqual(self.spawner.commands,[])

    def test_rpc_discovery_and_prepare_accept_only_opaque_candidate(self):
        discovery=Discovery(self);self.backend.discovery=discovery
        self.assertTrue(self.rpc('session.discover')['ok'])
        result=self.rpc('session.prepare',dict(candidate_id=fixture.PROFILE))
        self.assertTrue(result['ok']);self.assertFalse(result['result']['registration_reload_required'])
        for operation,args in (('session.discover',dict(pid=101)),('session.prepare',dict(candidate_id=fixture.PROFILE,path='PRIVATE')),
                               ('session.prepare',dict(candidate_id='arbitrary')),('run.resume',dict(run_id=fixture.PROFILE))):
            self.assertFalse(self.rpc(operation,args)['ok'])
        self.assertEqual(len(discovery.calls),2)
        self.assertEqual(self.spawner.commands,[])

    def test_prepare_refreshes_trusted_root_and_invalidates_old_readiness(self):
        previous=self.ready();self.backend.discovery=Discovery(self)
        self.assertEqual(self.backend._db.execute('SELECT COUNT(*) FROM readiness').fetchone()[0],1)
        self.rpc('session.prepare',dict(candidate_id=fixture.PROFILE))
        self.assertEqual(self.backend._db.execute('SELECT COUNT(*) FROM readiness').fetchone()[0],0)
        self.assertTrue(self.backend._root_bootstrap)
        self.assertEqual(self.backend._registration().session_path,self.session)
        self.assertCode('readiness_invalid',lambda:self.backend.run_start(self.profile,self.start_args(previous),str(uuid.uuid4())))
        self.assertTrue(self.ready()['ready'])
        self.assertEqual(self.spawner.commands,[])

    def test_success_claim_without_actual_root_registration_cannot_refresh_source(self):
        discovery=Discovery(self);discovery.prepare=lambda *args:dict(registered=True)
        self.backend.discovery=discovery
        result=self.rpc('session.prepare',dict(candidate_id=fixture.PROFILE))
        self.assertEqual(result['error']['code'],'session_root_invalid')
        self.assertEqual(self.spawner.commands,[])

    def test_preparation_failure_preserves_reason_and_never_restarts_host(self):
        discovery=Discovery(self)
        def blocked(*args):
            raise ContractError('run_history_unverifiable')
        discovery.prepare=blocked;self.backend.discovery=discovery
        result=self.rpc('session.prepare',dict(candidate_id=fixture.PROFILE))
        self.assertEqual(result['error']['code'],'run_history_unverifiable')
        self.assertEqual(self.spawner.commands,[])

    def test_old_prepare_receipt_cannot_be_reported_as_current_different_registration(self):
        discovery=Discovery(self);prepare=discovery.prepare
        def old_receipt(*args):
            value=prepare(*args);value['session_id']=str(uuid.uuid4());return value
        discovery.prepare=old_receipt;self.backend.discovery=discovery
        result=self.rpc('session.prepare',dict(candidate_id=fixture.PROFILE))
        self.assertEqual(result['error']['code'],'session_preparation_changed')
        self.assertEqual(self.backend._registration().session_path,self.session)
        self.assertEqual(self.spawner.commands,[])

    def test_empty_launch_index_has_nothing_to_resume_and_no_launch(self):
        result=self.rpc('run.resume')['result']
        self.assertIsNone(result['run']);self.assertTrue(result['observation_only'])
        self.assertEqual(result['other_unreleased_runs'],0)
        self.assertEqual(self.spawner.commands,[])

    def test_reopen_recovers_existing_host_from_durable_index_without_start(self):
        result,run_id,_=self.start();self.status_file(result)
        self.assertEqual(len(self.spawner.commands),1)
        self.backend.close();self.backend=self.new_backend()
        resumed=self.rpc('run.resume')['result']
        self.assertEqual(resumed['run']['run_id'],run_id)
        self.assertEqual(resumed['run']['state'],'running')
        self.assertTrue(resumed['observation_only'])
        self.assertEqual(len(self.spawner.commands),1)
        self.assertEqual(len(self.backend.journal.commands_for_run(run_id,operation='host_start')),1)

    def test_unverified_terminal_run_is_recovered_for_release_review(self):
        result,run_id,_=self.start();self.status_file(result,state='stopped')
        self.spawner.alive=False
        resumed=self.rpc('run.resume')['result']
        self.assertEqual(resumed['run']['run_id'],run_id)
        self.assertFalse(resumed['run']['native_release_verified'])
        self.assertEqual(len(self.spawner.commands),1)

    def test_newer_verified_terminal_does_not_hide_older_unreleased_run(self):
        result,older,_=self.start();row=dict(self.backend._launch(older));newer=str(uuid.uuid4())
        self.backend._db.execute('INSERT INTO launches VALUES (?,?,?,?,?,?,?)',
            (newer,newer,row['fingerprint'],row['session_path'],row['output_path'],row['binding_json'],'new-channel'))
        def status(row):
            return dict(run_id=row['run_id'],session_id=fixture.SESSION,
                        state='stopped' if row['run_id']==newer else 'uncertain',native_release_verified=row['run_id']==newer)
        with patch.object(self.backend,'_status',side_effect=status):
            result=self.rpc('run.resume')['result']
        self.assertEqual(result['run']['run_id'],older)
        self.assertEqual(len(self.spawner.commands),1)

    def test_status_projects_bounded_reason_and_marks_old_state_without_inventing_fresh_observation(self):
        result,run_id,_=self.start();self.status_file(result,reason_code='model_wait')
        path=self.run/'battle-host'/'host-status.json'
        self.now=2_000_000;os.utime(path,(1_980,1_980))
        status=self.rpc('run.resume')['result']['run']
        self.assertEqual(status['reason_code'],'model_wait')
        self.assertTrue(status['host_process_alive']);self.assertTrue(status['status_stale'])
        self.assertEqual(status['status_age_ms'],20_000)
        self.status_file(result,reason_code='PRIVATE / path')
        status=self.rpc('run.resume')['result']['run']
        self.assertNotIn('reason_code',status)
        self.assertNotIn('PRIVATE',json.dumps(status))

    def test_corrupt_old_binding_has_explicit_history_error_without_new_host(self):
        _,run_id,_=self.start()
        self.backend._db.execute('UPDATE launches SET binding_json=? WHERE run_id=?',('not json',run_id))
        result=self.rpc('run.resume')
        self.assertEqual(result['error']['code'],'run_history_unverifiable')
        self.assertEqual(len(self.spawner.commands),1)

    def test_readiness_invalidated_between_native_check_and_claim_cannot_launch(self):
        ready=self.ready();original=self.backend._transaction
        @contextmanager
        def concurrent_prepare():
            # A completed source preparation clears readiness while this
            # launcher was waiting for the shared index write lock.
            self.backend.register_session(self.session,self.report,self.persistent)
            with original():yield
        with patch.object(self.backend,'_transaction',concurrent_prepare):
            self.assertCode('readiness_invalid',lambda:self.backend.run_start(
                self.profile,self.start_args(ready),str(uuid.uuid4())))
        self.assertEqual(self.backend._db.execute('SELECT COUNT(*) FROM launches').fetchone()[0],0)
        self.assertEqual(self.spawner.commands,[])

    def test_predispatch_compares_original_source_instead_of_accepting_any_valid_registration(self):
        ready=self.ready();original=self.backend._predispatch
        folder=self.root/'acceptance'/'next-session';folder.mkdir()
        path=folder/'session.json';record=json.loads(self.session.read_text())
        record.update(session_id=str(uuid.uuid4()),run_directory=str(folder));path.write_text(json.dumps(record))
        def concurrent_prepare(profile,expires_at,registration=None):
            self.backend.register_session(path,self.report,self.persistent)
            return original(profile,expires_at,registration)
        with patch.object(self.backend,'_predispatch',side_effect=concurrent_prepare):
            self.assertCode('session_changed',lambda:self.backend.run_start(
                self.profile,self.start_args(ready),str(uuid.uuid4())))
        self.assertEqual(self.spawner.commands,[])

    def test_backend_close_releases_only_discovery_service_not_game_host(self):
        self.backend.discovery=discovery=Discovery(self)
        self.backend.close();self.backend=self.new_backend()
        self.assertTrue(discovery.closed)
        self.assertEqual(self.spawner.commands,[])


if __name__=='__main__':unittest.main()
