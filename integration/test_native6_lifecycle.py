"""Synthetic Native6 proofs + real journal/mutex. Never opens a game/model."""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

from host_runtime import native6_lifecycle as subject
from host_runtime import native6_orphan_return as orphan
from host_runtime.contracts import SessionBinding,ContractError
from host_runtime.journal import CommandJournal
from host_runtime.native6_journal import WORDS,ARRAYS,JOURNAL_SIZE,JOURNAL_END,wire_binding
from host_runtime.native6_qualification import COMMANDER,Native6Scope,KIND as BUNDLE_KIND
from host_runtime.native6_runtime_contract import FLAGS,ACTIONS,FIELD_KIND,GAME_SHA,PACKAGE_SHA,sha
from host_runtime.native6_release import verified_final
from host_runtime.strategic_stop_gate_v1 import StrategicStopGateV1


class Lifecycle(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='native6-lifecycle-fixture-');self.addCleanup(temporary.cleanup)
        self.base=Path(temporary.name);self.root=self.base/'runtime';self.output=self.base/'session/battle-host';self.output.mkdir(parents=True)
        self.report=self.base/'native6-report';self.report.mkdir();self.run=str(uuid.uuid4());self.sid=str(uuid.uuid4())
        self.binding=SessionBinding(1,self.sid,3,COMMANDER,123,'2026-10-31T00:00:00+00:00',str(uuid.uuid4()),GAME_SHA,PACKAGE_SHA)
        self.session=dict(session_id=self.sid,pid=123,start_time=self.binding.game_process_start,process_creation_filetime=123456789,
            mod_sha256=PACKAGE_SHA,game=str(self.base/'Game/RA3_1.12.game'),mod_big=str(self.base/'Mods/fixture.big'))
        self.manifest=dict(kind=FIELD_KIND,protocol_version=6,package_sha256=PACKAGE_SHA,flags=list(FLAGS),source_closure_sha256='a'*64,
                           artifacts={'manager_host.exe':'b'*64})
        self.scope=Native6Scope(PACKAGE_SHA,tuple(zip(ACTIONS,FLAGS)),(),(),runtime_root=self.root,runtime_manifest_sha256='')
        for name,raw in {'app/integration/macro_host.py':b'# explicitly synthetic Host source',
                         'native/strategic6/build-manifest.json':json.dumps(self.manifest).encode(),
                         'qualification/native6-trial.json':b'{}'}.items():
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        files={p.relative_to(self.root).as_posix():sha(p) for p in self.root.rglob('*') if p.is_file()}
        for module in (subject,orphan):files['app/integration/host_runtime/'+Path(module.__file__).name]=sha(module.__file__)
        files['app/integration/host_runtime/native6_no_attachment.py']='c'*64
        (self.root/'manifest.json').write_text(json.dumps(dict(schema_version=1,files=files)),encoding='utf-8')
        self.pin=sha(self.root/'manifest.json');object.__setattr__(self.scope,'runtime_manifest_sha256',self.pin)
        self.env=patch.dict(os.environ,TACTICORE_RUNTIME_MANIFEST_SHA256=self.pin);self.env.start();self.addCleanup(self.env.stop)
        self.args=SimpleNamespace()
        for key,value in {'session':self.session,'macro_bundle':dict(schema_version=14,kind=BUNDLE_KIND,runtime_root=str(self.root),runtime_manifest_sha256=self.pin),
                          'commander_draft':{},'binding':self.binding.public()}.items():
            path=self.output.parent/(key+'.json');path.write_text(json.dumps(value),encoding='utf-8');setattr(self.args,key,path)
        self.row=dict(run_id=self.run,request_id='start',output_path=str(self.output),session_path=str(self.args.session),binding_json=json.dumps(self.binding.public()))
        self.journal=CommandJournal(self.base/'journal.sqlite');self.addCleanup(self.journal.close)
        self.journal.register_run(self.run,self.binding.public())
        self.receipt=dict(host_pid=555,host_start_time='fixture-host-incarnation')
        self.journal.reserve_command(self.run,'start','host_start',dict(capabilities=dict(native_transport_protocol=6)))
        self.journal.mark_dispatching(self.run,'start');self.journal.record_outcome(self.run,'start','started',self.receipt)
        self.host=SimpleNamespace(output=self.output,args=self.args,run_id=self.run,binding=self.binding,session=self.session,
            native6_scope=self.scope,profile={},journal=self.journal,host_pid=555,host_start=self.receipt['host_start_time'],
            latest=dict(game_time_seconds=100),strategy_runtime=None,sampler=None)
        self.addCleanup(patch.stopall)
        patch.object(subject,'runtime_root',return_value=self.root).start()
        patch.object(subject,'report_directory',return_value=self.report).start()
        subject.freeze(self.host)
        self.proof,self.raw=self.synthetic_proof()
        self.backend=SimpleNamespace(journal=self.journal,spawner=SimpleNamespace(identity=lambda _:None))

    @staticmethod
    def atomic(path,value):Path(path).write_text(json.dumps(value),encoding='utf-8')

    def synthetic_proof(self):
        b={name:1000+i for i,name in enumerate(WORDS)}
        b.update(pid=123,start_low=self.session['process_creation_filetime'],start_high=0)
        b.update({name:[i+1]*size for i,(name,size) in enumerate(ARRAYS)})
        b.update(session=list(uuid.UUID(self.sid).bytes),package=list(bytes.fromhex(PACKAGE_SHA)),sources=list(bytes.fromhex('a'*64)),
            runtime_manifest=list(bytes.fromhex(self.pin)),deployment=self.session['mod_big'],game_image=self.session['game'],
            runtime_root=str(self.root),journal_root=str(self.base/'journals'))
        native=dict(magic=0x53434736,version=6,size=4592,binding=b,phase=2,error=0,active=0,applied_mask=0,flag_deadline=0,
            cleanup_verified=1,hook_held=0,lease_held=0,request=2,ack=2,flag_phase=4,flag_attempted=1,journal_records=2,
            last_frame=1500,gates=[dict(phase=4,baseline_captured=1,baseline=[1,1,1],observed=[1,1,1]) for _ in range(2)])
        own={key:hex(b[field]) for key,field in (('player','owner'),('ai_player','ai'),('personality_wrapper','personality'),('player_template','player_template'))}
        own.update(player_index=3,instance_id='0x799613e0',store_membership_verified=True,side_matches_player=True,mutations=False)
        proof=dict(native=native,flags=dict(flags=[dict(name=name,present=True,value=False) for name in FLAGS]),
            components=[dict(index=i,owned=True,enabled=1) for i in range(3)],current_own_identity=own,
            native_release_verified=True,sequential_reads_revalidated=True,native_durable_journal_verified=True,native_durable_journal_records=2,
            semaphore_current=1,semaphore_maximum=1,actual_OS_before=dict(pid=123,process_creation_filetime=self.session['process_creation_filetime']),
            actual_OS_after=dict(pid=123,process_creation_filetime=self.session['process_creation_filetime']),frame=1500,frame_after=1501,
            started_monotonic_ns=10,ended_monotonic_ns=100,host_process_ended=True,host_returncode=0)
        raw=b''
        for seq in (1,2):
            record=bytearray(JOURNAL_SIZE);struct.pack_into('<7I',record,0,0x53434736,6,seq,JOURNAL_SIZE,seq,1,1600)
            record[28:28+4332]=wire_binding(b);struct.pack_into('<I',record,JOURNAL_END,0x454e4436);raw+=record
        return proof,raw

    def install_final(self,mutate=None):
        proof=copy.deepcopy(self.proof)
        if mutate:mutate(proof)
        path=self.report/'independent-release.json';self.atomic(path,proof)
        (self.report/'native-journal.bin').write_bytes(self.raw)
        final=dict(native_release_contract='native6_unified_release_v1',cleanup_verified=True,session_id=self.sid,pid=123,
            process_creation_filetime=self.session['process_creation_filetime'],mod_sha256=PACKAGE_SHA,unknown_command_ids=[],host_returncode=0,
            runtime_root=str(self.root),runtime_manifest_sha256=self.pin,raw_native=proof['native'],native=dict(last_frame=1500),
            independent_flags=proof['flags'],independent_release_sha256=sha(path),native_journal_sha256=hashlib.sha256(self.raw).hexdigest())
        self.atomic(self.report/'final-state.json',final)
        return final

    def start_done(self):self.journal.record_outcome(self.run,'start','completed',self.receipt)

    def test_actual_host_stop_and_real_ledger_publish_only_after_complete_proof(self):
        transport=SimpleNamespace(manifest=self.manifest,close=lambda:self.install_final(),native_status=lambda:dict(last_frame=1500))
        self.host.transport=transport;self.host.controller=None
        subject.finish(self.host)
        self.assertEqual(self.journal.get_command(self.run,'macro-stop')['status'],'released')
        self.start_done()
        self.assertTrue(subject.verified_return(self.backend,self.row,self.binding,self.receipt))
        changed=self.install_final(lambda proof:proof['components'][2].update(enabled=0))
        self.assertFalse(verified_final(changed,self.report/'independent-release.json',self.session,self.binding,self.manifest,
            runtime_root=self.root,runtime_manifest_sha256=self.pin))

    def test_ack_or_flag_or_other_epoch_cannot_release_the_host(self):
        for mutation in (lambda p:p['native'].update(hook_held=1),lambda p:p['actual_OS_after'].update(pid=999),
                         lambda p:p['flags']['flags'][0].update(value=True),lambda p:p['native'].update(version=5)):
            final=self.install_final(mutation)
            self.assertFalse(verified_final(final,self.report/'independent-release.json',self.session,self.binding,self.manifest,
                runtime_root=self.root,runtime_manifest_sha256=self.pin))

    def test_bad_return_keeps_stop_uncertain(self):
        self.host.transport=SimpleNamespace(manifest=self.manifest,close=lambda:self.install_final(lambda p:p['native'].update(lease_held=1)))
        self.host.controller=None
        with self.assertRaises(ContractError):subject.finish(self.host)
        self.assertEqual(self.journal.get_command(self.run,'macro-stop')['status'],'uncertain')

    def test_no_constructor_history_still_requires_independent_no_attachment_proof(self):
        from host_runtime import native6_no_attachment as noattach
        # Exercise the actual file/receipt/history wrapper; never borrow an old
        # Native5 release row or declare that no transport means no ownership.
        inventory=json.loads((self.root/'manifest.json').read_text(encoding='utf-8'))
        inventory['files']['app/integration/host_runtime/native6_no_attachment.py']=sha(noattach.__file__)
        (self.root/'manifest.json').write_text(json.dumps(inventory),encoding='utf-8')
        self.pin=sha(self.root/'manifest.json');object.__setattr__(self.scope,'runtime_manifest_sha256',self.pin)
        os.environ['TACTICORE_RUNTIME_MANIFEST_SHA256']=self.pin
        self.atomic(self.args.macro_bundle,dict(schema_version=14,kind=BUNDLE_KIND,runtime_root=str(self.root),runtime_manifest_sha256=self.pin))
        self.host.output=self.output=self.output.parent/'no-attachment-host';self.output.mkdir()
        self.row['output_path']=str(self.output)
        subject.freeze(self.host)
        proof=dict(capture_code_sha256=sha(noattach.__file__))
        self.host.transport=None;self.host.controller=None
        with patch.object(noattach,'capture',return_value=proof):subject.finish(self.host)
        self.start_done();events=self.output/'host-events.jsonl'
        events.write_text(json.dumps(dict(kind='host_stopped'))+'\n',encoding='utf-8')
        # This independent OS capture validator is isolated; the real validator
        # and exact mapping rejection are covered in test_native6_admission.
        with patch.object(noattach,'verified_capture',return_value=True):
            self.assertTrue(subject.verified_return(self.backend,self.row,self.binding,self.receipt))
            events.write_text(json.dumps(dict(kind='macro_native_transport_constructor_begin'))+'\n'+json.dumps(dict(kind='host_stopped'))+'\n',encoding='utf-8')
            self.assertFalse(subject.verified_return(self.backend,self.row,self.binding,self.receipt))
        with patch.object(noattach,'verified_capture',return_value=False):
            events.write_text(json.dumps(dict(kind='host_stopped'))+'\n',encoding='utf-8')
            self.assertFalse(subject.verified_return(self.backend,self.row,self.binding,self.receipt))

    def test_native6_real_stop_rpc_commits_same_barrier_for_provider_constructor_and_batch(self):
        from host_runtime.desktop_backend import DesktopBackend
        backend=SimpleNamespace(_launch=lambda run:self.row,journal=self.journal,_cancel_reserved_launch=lambda *a:False,
                                _status=lambda row:dict(state='stopping',native_release_verified=False))
        result=DesktopBackend.run_stop(backend,dict(run_id=self.run,session_id=self.sid),str(uuid.uuid4()))
        self.assertFalse(result['native_release_verified'])
        gate=StrategicStopGateV1(self.run,self.binding,self.output)
        for kind in ('provider_request','native_constructor','native_batch'):
            with self.assertRaisesRegex(ContractError,'stop_already_committed'):
                with gate.admit(kind):self.fail('work admitted after STOP')

    def test_normal_return_preserves_historical_unknown_without_reissuing_it(self):
        parent=str(uuid.uuid4());payload=dict(actions=['scout'],plan_id=str(uuid.uuid4()),native_command_id=parent,
            duration_frames=60,not_after_frame=1800,unit_operation_policy='native_ai')
        self.journal.reserve_command(self.run,parent,'macro_policy',payload);self.journal.mark_dispatching(self.run,parent)
        self.journal.record_outcome(self.run,parent,'uncertain',dict(reason_code='synthetic_unknown'))
        self.host.transport=SimpleNamespace(manifest=self.manifest,close=lambda:self.install_final(),native_status=lambda:dict(last_frame=1500))
        self.host.controller=None;subject.finish(self.host);self.start_done()
        self.assertTrue(subject.verified_return(self.backend,self.row,self.binding,self.receipt))
        self.assertEqual(self.journal.get_command(self.run,parent)['status'],'uncertain')

    def test_frozen_descriptor_or_session_tamper_is_not_a_new_epoch(self):
        subject.context(self.row,self.session,self.binding)
        with patch.dict(os.environ,TACTICORE_RUNTIME_MANIFEST_SHA256='0'*64):
            with self.assertRaises(ContractError):subject.context(self.row,self.session,self.binding)
        self.atomic(self.output/'source/2-macro_bundle.json',dict(schema_version=14,kind=BUNDLE_KIND,runtime_root='C:/other',runtime_manifest_sha256=self.pin))
        with self.assertRaises(ContractError):subject.context(self.row,self.session,self.binding)

    def test_helper_identity_can_be_sealed_before_attach_ack_without_granting_return(self):
        from host_runtime import native6_readonly_return as reader
        binary=self.root/'native/strategic6/manager_host.exe';binary.write_bytes(b'synthetic-helper-not-executable')
        helper=dict(pid=666,process_creation_filetime=13,image=str(binary),alive=True)
        parent=dict(pid=555,process_creation_filetime=12,image='fixture-host',alive=True)
        probe=SimpleNamespace(host=SimpleNamespace(pid=666,poll=lambda:None),session=self.session,build=binary.parent,
            output=self.report,status=lambda:dict(phase=0,binding=self.proof['native']['binding']))
        with patch.object(reader,'process_identity',side_effect=[helper,parent]):
            seal=reader.record_helper_identity(probe)
        self.assertEqual(seal['native_binding'],self.proof['native']['binding'])
        self.assertEqual(seal['helper_sha256'],sha(binary))
        self.assertEqual(seal['native_commands_issued'],0)
        self.assertNotIn('native_release_verified',seal)
        self.assertFalse((self.report/'final-state.json').exists())
        # A second writer cannot replace an earlier incarnation's seal.
        with patch.object(reader,'process_identity',side_effect=[helper,parent]):
            with self.assertRaises(FileExistsError):reader.record_helper_identity(probe)

    def test_orphan_requires_explicit_stop_and_leaves_broker_rpc_untouched(self):
        self.assertFalse(orphan.recover_after_stop(self.backend,self.row,self.binding,self.receipt,self.atomic))
        gate=StrategicStopGateV1(self.run,self.binding,self.output);gate.publish_stop(self.atomic)
        parent=str(uuid.uuid4());payload=dict(actions=['scout'],plan_id=str(uuid.uuid4()),native_command_id=parent,
            duration_frames=60,not_after_frame=1800,unit_operation_policy='native_ai')
        self.journal.reserve_command(self.run,parent,'macro_policy',payload);self.journal.mark_dispatching(self.run,parent)
        ended=dict(ended=True,reason='pid_absent',exit_code=None)
        identity=dict(native_binding=self.proof['native']['binding'],parent=dict(pid=555,process_creation_filetime=12,image='Host.exe'),
            helper=dict(pid=666,process_creation_filetime=13,image='manager_host.exe'))
        orphan_proof=copy.deepcopy(self.proof);orphan_proof['host_returncode']=None
        value=dict(kind=orphan.KIND,run_id=self.run,binding=self.binding.public(),helper_identity=identity,helper_exit_code=None,
            parent_ended=ended,helper_ended_before=ended,helper_ended_after=ended,current_restoration=orphan_proof,
            native_commands_issued=0,mapping_access='FILE_MAP_READ',ownership_return_claimed=False,
            native_journal_sha256=hashlib.sha256(self.raw).hexdigest(),capture_source_sha256=sha(orphan.__file__))
        frozen,manifest,inventory=subject.context(self.row,self.session,self.binding)
        with patch.object(orphan,'inputs',return_value=(self.session,frozen,manifest,inventory,identity)),patch.object(orphan,'capture',return_value=(value,self.raw)) as collector:
            self.assertTrue(orphan.recover_after_stop(self.backend,self.row,self.binding,self.receipt,self.atomic))
            self.assertEqual(self.journal.get_command(self.run,parent)['status'],'uncertain')
            self.assertTrue(orphan.recover_after_stop(self.backend,self.row,self.binding,self.receipt,self.atomic))
            self.assertEqual(collector.call_count,1)
            self.journal.reserve_command(self.run,'broker','host_stop',{})
            self.journal.mark_dispatching(self.run,'broker')
            self.assertFalse(orphan.verified_return(self.backend,self.row,self.binding,self.receipt))
            self.assertEqual(self.journal.get_command(self.run,'broker')['status'],'dispatching')


if __name__=='__main__':unittest.main()
