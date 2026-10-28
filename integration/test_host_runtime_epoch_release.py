"""Pinned actual three-epoch evidence and real SQLite refusal/reopen checks."""
import copy,hashlib,json,sqlite3,tempfile,uuid
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from host_runtime.contracts import SessionBinding,content_hash,ContractError
from host_runtime.journal import CommandJournal
from host_runtime.runtime_epoch_release import inspect_chain,projection_verified,command_snapshot,family
import test_host_runtime_desktop_backend as desktop_fixtures

RUN=Path(__file__).resolve().parents[1]/'acceptance/runs/20261027-131614-desktop-match'
read=lambda n:json.loads((RUN/n).read_text(encoding='utf-8-sig'))
ROOT_ID='d5ed27b7-d0ea-45ef-b9a7-0bfe094d1bac'
LAST='99aeaebe-9e3a-4ebb-9c6e-d770237f3a07'

class PinnedJournal:
    def __init__(self):
        raw=read('journal-before-independent-closure-review.json');self.commands=raw['commands']
        self._db=sqlite3.connect(':memory:');self._db.row_factory=sqlite3.Row
        self._db.execute('CREATE TABLE runs(run_id TEXT,binding TEXT)')
        self._db.executemany('INSERT INTO runs VALUES(?,?)',[(r['run_id'],r['binding'])for r in raw['runs']])
    def commands_for_run(self,rid):return copy.deepcopy([r for r in self.commands if r['run_id']==rid])
    def get_native_sequence(self,rid,cid):
        row=next(r for r in self.commands if r['run_id']==rid and r['command_id']==cid)
        return row['receipt']['facts']['seq']

class PinnedEpochs(unittest.TestCase):
    def setUp(self):
        self.j=PinnedJournal();self.addCleanup(self.j._db.close)
        self.binding=SessionBinding.from_dict(read('host-tactical-runtime.json')['binding'])
        self.supervisor=read('host-tactical-deferred-'+ROOT_ID+'.json')['supervisor']
        self.capture=read('host-tactical-runtime-'+LAST+'-fresh-post-host-capture.json')
    def inspect(self):
        return inspect_chain(self.j,ROOT_ID,self.binding,RUN,self.supervisor,RUN/'session.json',capture_final=lambda *a:self.capture)
    def test_original_actual_three_epochs_recompute_with_last_uncertainty_retained(self):
        result=self.inspect();channels=result['channels']
        self.assertEqual(len(channels),3);self.assertEqual([r['facts']['original_events']for r in channels],[120,0,0])
        self.assertEqual([r['facts']['original_traces']for r in channels],[1617,122,1])
        self.assertTrue(channels[0]['facts']['control_released']);self.assertTrue(channels[-1]['facts']['no_control_acquired'])
        self.assertEqual(len(channels[-1]['uncertain_attach_ids']),1)
        self.assertEqual(next(r for r in self.j.commands if r['run_id']==LAST)['status'],'uncertain')
    def test_changed_retirement_manifest_pin_is_denied(self):
        row=next(r for r in self.j.commands if r['operation']=='runtime_channel_retire')
        row['receipt']['manifest_sha256']='0'*64
        with self.assertRaisesRegex(ContractError,'source_digest_changed'):self.inspect()
    def test_missing_successor_authorization_cannot_hide_registered_epochs(self):
        self.j.commands=[r for r in self.j.commands if not(r['run_id']==ROOT_ID and r['operation']=='runtime_channel_successor_authorize')]
        with self.assertRaisesRegex(ContractError,'unlinked_session_epoch'):self.inspect()
    def test_native_receipt_not_found_in_raw_events_is_denied(self):
        row=next(r for r in self.j.commands if r['operation']=='commit');row['receipt']['facts']['game_frame']+=1
        with self.assertRaisesRegex(ContractError,'receipt_not_in_original_events'):self.inspect()
    def test_unknown_commit_cannot_use_idle_attach_exception(self):
        row=next(r for r in self.j.commands if r['operation']=='commit');row['status']='uncertain'
        with self.assertRaisesRegex(ContractError,'native_journal_correlation_changed'):self.inspect()
    def test_incomplete_latest_trace_cannot_close_unknown_attach(self):
        self.capture['hook_traces']=[]
        with self.assertRaises(ContractError):self.inspect()
    def test_foreign_commander_in_same_session_is_denied(self):
        row=self.j._db.execute('SELECT binding FROM runs WHERE run_id=?',(LAST,)).fetchone();b=json.loads(row['binding']);b['commander_id']=str(uuid.uuid4())
        self.j._db.execute('UPDATE runs SET binding=? WHERE run_id=?',(json.dumps(b),LAST))
        with self.assertRaisesRegex(ContractError,'session_binding_changed'):self.inspect()
    def test_extra_unlinked_epoch_cannot_be_ignored(self):
        b=dict(self.binding.public(),host_id=str(uuid.uuid4()));self.j._db.execute('INSERT INTO runs VALUES(?,?)',(str(uuid.uuid4()),json.dumps(b)))
        with self.assertRaisesRegex(ContractError,'unlinked_session_epoch'):self.inspect()
    def test_inflight_publication_is_not_terminal(self):
        row=next(r for r in self.j.commands if r['operation']=='runtime_channel_attach');row['status']='dispatching'
        with self.assertRaisesRegex(ContractError,'active_command'):self.inspect()

class AttachClosureProjection(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'journal.sqlite3';self.j=CommandJournal(self.path);self.addCleanup(lambda:self.j.close())
        self.binding=SessionBinding.from_dict(read('host-tactical-runtime-'+LAST+'.json')['binding']);self.j.register_run(LAST,self.binding.public())
        self.request=str(uuid.uuid4());self.old=self.j.reserve_command(LAST,self.request,'runtime_channel_attach',{'binding_hash':self.binding.binding_hash})
        self.j.mark_dispatching(LAST,self.request);self.j.record_outcome(LAST,self.request,'uncertain',{'reason_code':'runtime_successor_attach_unknown_no_retry'})
        self.before=self.j.get_command(LAST,self.request)
    def save_review(self,*,payload_change=None,receipt_change=None,prior=None):
        request=str(uuid.uuid4());old=prior or self.old['command_id']
        p=dict(recovery_of_command_id=old,binding_hash=self.binding.binding_hash);p.update(payload_change or {})
        r=dict(reason_code='runtime_attach_no_control_independently_closed',source='independent_runtime_epoch_release_review',
            reviewed_command_id=old,binding_hash=self.binding.binding_hash,review_sha256='a'*64,native_release_verified=True,
            channel_closed=True,no_control_acquired=True,mission_effect_granted=False);r.update(receipt_change or {})
        self.j.reserve_command(LAST,request,'review_runtime_channel_release',p);self.j.mark_dispatching(LAST,request);self.j.record_outcome(LAST,request,'released',r)
    def test_new_review_closes_projection_without_modifying_old_unknown_and_survives_reopen(self):
        self.assertEqual(len(self.j.unresolved(LAST)),1);self.save_review();self.assertEqual(self.j.unresolved(LAST),[])
        self.assertEqual(self.j.get_command(LAST,self.request),self.before)
        self.j.close();self.j=CommandJournal(self.path)
        self.assertEqual(self.j.unresolved_for_session(self.binding.public()),[]);self.assertEqual(self.j.get_command(LAST,self.request),self.before)
    def test_missing_or_wrong_typed_closed_facts_never_close_attach(self):
        for change in ({'channel_closed':False},{'no_control_acquired':False},{'native_release_verified':False},
            {'mission_effect_granted':True},{'channel_closed':1},{'source':'other'},{'review_sha256':'z'*64},
            {'binding_hash':'0'*64},{'reviewed_command_id':str(uuid.uuid4())}):
            with self.subTest(change=change):
                self.save_review(receipt_change=change);self.assertEqual(len(self.j.unresolved(LAST)),1)
    def test_wrong_payload_binding_never_closes_attach(self):
        self.save_review(payload_change={'binding_hash':'0'*64});self.assertEqual(len(self.j.unresolved(LAST)),1)
    def test_attach_review_cannot_close_an_unknown_tactical_command(self):
        req=str(uuid.uuid4());r=self.j.reserve_command(LAST,req,'commit',{});self.j.mark_dispatching(LAST,req);self.j.record_outcome(LAST,req,'uncertain',{'reason_code':'original_unknown'})
        self.save_review(prior=r['command_id']);self.assertEqual(len(self.j.unresolved(LAST)),2)

class DesktopEpochProjection(unittest.TestCase):
    def setUp(self):
        self.f=desktop_fixtures.DesktopBackendTests();self.f.setUp();self.addCleanup(self.f.tearDown)
        self.result,self.request,_=self.f.start();self.backend=self.f.backend;self.run=self.result['run_id']
        row=self.backend._launch(self.run);self.binding=SessionBinding.from_dict(json.loads(row['binding_json']))
        self.f.status_file(self.result,state='fault');self.f.spawner.alive=False;self.backend._status(row)
        self.receipt=self.backend.journal.get_command(self.run,self.request)['receipt']
        self.path=self.backend.state_dir/'runs'/self.run/'runtime-epochs-release-review.json'
        self.source=self.backend.state_dir/'test-closed-native-evidence.json';self.source.write_text('{}')
    def save(self,**changes):
        b=self.binding;bindings=family(self.backend.journal,b)
        proof=dict(kind='runtime_epoch_host_release_review',binding=b.public(),run_id=self.run,
            host_pid=self.receipt['host_pid'],host_start_time=self.receipt['host_start_time'],
            native_release_verified=True,mission_effect_granted=False,physical_home_claimed=False,natural_result_verified=False,
            epoch_ids=sorted(bindings),command_snapshot_hash=content_hash(command_snapshot(self.backend.journal,bindings)),
            files={str(self.source):hashlib.sha256(self.source.read_bytes()).hexdigest()})
        proof.update(changes);self.path.parent.mkdir(parents=True,exist_ok=True);self.path.write_text(json.dumps(proof))
        req=str(uuid.uuid4());self.backend.journal.reserve_command(self.run,req,'review_runtime_host_release',{'binding_hash':b.binding_hash})
        self.backend.journal.mark_dispatching(self.run,req);self.backend.journal.record_outcome(self.run,req,'released',dict(
            reason_code='runtime_epoch_host_native_entries_independently_verified',binding_hash=b.binding_hash,
            host_pid=self.receipt['host_pid'],host_start_time=self.receipt['host_start_time'],native_release_verified=True,
            mission_effect_granted=False,review_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest()))
    def verified(self):return projection_verified(self.backend,self.run,self.binding,self.receipt)
    def test_saved_review_requires_source_pin_and_keeps_fault_state(self):
        self.assertFalse(self.verified());self.save();self.assertTrue(self.verified())
        self.assertEqual(self.backend._status(self.backend._launch(self.run))['state'],'fault')
        self.assertTrue(self.backend._status(self.backend._launch(self.run))['native_release_verified'])
        self.source.write_text('{"changed":true}');self.assertFalse(self.verified())
    def test_foreign_host_or_home_mission_result_claims_are_denied(self):
        for change in ({'host_pid':999},{'host_start_time':'changed'},{'binding':{}},{'run_id':str(uuid.uuid4())},
            {'physical_home_claimed':True},{'mission_effect_granted':True},{'natural_result_verified':True}):
            with self.subTest(change=change):self.save(**change);self.assertFalse(self.verified())
    def test_new_command_after_review_invalidates_inventory_even_when_rejected(self):
        self.save();self.assertTrue(self.verified());request=str(uuid.uuid4())
        self.backend.journal.reserve_command(self.run,request,'produce',{})
        self.backend.journal.record_outcome(self.run,request,'rejected',{'reason_code':'synthetic_rejected'})
        self.assertFalse(self.verified())
    def test_new_unlinked_epoch_invalidates_whole_host_release(self):
        self.save();b=dict(self.binding.public(),host_id=str(uuid.uuid4()))
        self.backend.journal.register_run(str(uuid.uuid4()),b);self.assertFalse(self.verified())

if __name__=='__main__':unittest.main()
