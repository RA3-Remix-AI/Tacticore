"""Pinned real no-Borrow closure bytes and refusal cases; no game/model IO."""
import copy
import ctypes as c
import json
from pathlib import Path
import unittest
import hashlib
import uuid
from dataclasses import replace
import test_host_runtime_desktop_backend as desktop_fixtures
from host_runtime.contracts import ContractError,SessionBinding
from host_runtime.idle_runtime_release import assess_idle,assess_producer
from host_runtime.runtime_evidence import _layout,_decode,_producer_types

RUN=Path(__file__).resolve().parents[1]/'acceptance/runs/20261027-120917-desktop-match'
read=lambda p:json.loads((RUN/p).read_text(encoding='utf-8-sig'))

class IdleReviewBytes(unittest.TestCase):
    def setUp(self):
        self.report=read('host-tactical-runtime.json');self.capture=read('complete-channel-readonly.json')
        self.proof=read('independent-cleanup-readonly.json');self.binding=SessionBinding.from_dict(self.report['binding'])
        self.l=_layout();self.Receipt,self.Header=_producer_types(self.l)
        self.boot=_decode(self.l.Bootstrap,self.report['bootstrap_hex'])
        self.commands=[r for r in read('journal-before-idle-review.json')['commands']if r['operation']=='produce']

    def assess(self,**changes):
        args=dict(before=bytes.fromhex(self.proof['header_before_hex']),after=bytes.fromhex(self.proof['header_after_hex']),
            ledger=bytes.fromhex(self.proof['ledger_hex']),binding=self.binding,commands=self.commands,bootstrap=self.boot)
        args.update(changes);return assess_producer(**args)

    def test_actual_original_idle_channel_and_three_production_outcomes_recompute(self):
        facts=assess_idle(self.report,self.capture,self.binding)
        self.assertTrue(facts['no_control_acquired']);self.assertFalse(facts['control_released'])
        self.assertEqual(facts['previous_native_sequence'],0);self.assertEqual(facts['original_traces'],285)
        proof=self.assess();self.assertEqual(proof['spent'],85);self.assertEqual(proof['count'],3)

    def test_incomplete_tactical_trace_or_not_restored_header_denied(self):
        for changes in ({'hook_traces':[]},{'events_overwritten':1},{'diagnostic':True},{'host_exit':1}):
            r=dict(self.report,**changes)
            with self.subTest(changes=list(changes)),self.assertRaises((ContractError,ValueError)):assess_idle(r,self.capture,self.binding)

    def test_changed_callback_stop_version_binding_or_spend_denied(self):
        for name,value in (('active',1),('phase',1),('restore_mask',30),('stop_requested',0),('version',2),('pid',1),('spent',0),('count',2),('start_low',0),('personality',0)):
            h=_decode(self.Header,self.proof['header_before_hex']);setattr(h,name,value)
            with self.subTest(name=name),self.assertRaises(ContractError):self.assess(before=bytes(h),after=bytes(h))

    def test_rejected_build_with_attempt_payment_or_creation_cannot_be_called_no_dispatch(self):
        for name,value in (('attempted',1),('paid',85),('created',1),('completed',1),('state',4),('error',0)):
            ledger=bytearray.fromhex(self.proof['ledger_hex']);r=self.Receipt.from_buffer(ledger,c.sizeof(self.Receipt));setattr(r,name,value)
            with self.subTest(name=name),self.assertRaises(ContractError):self.assess(ledger=bytes(ledger))

    def test_unresolved_or_cross_task_journal_cannot_reconcile_production(self):
        for change in ({'status':'uncertain'},{'command_id':'00000000-0000-0000-0000-000000000001'}, {'payload':dict(self.commands[0]['payload'],task_id='00000000-0000-0000-0000-000000000001')}):
            commands=copy.deepcopy(self.commands);commands[0].update(change)
            with self.subTest(change=list(change)),self.assertRaises(ContractError):self.assess(commands=commands)

    def test_unstable_or_missing_receipt_data_denied(self):
        with self.assertRaises(ContractError):self.assess(after=b'bad')
        with self.assertRaises(ContractError):self.assess(ledger=bytes.fromhex(self.proof['ledger_hex'])[:-1])

class IdleDesktopProjection(unittest.TestCase):
    def setUp(self):
        self.f=desktop_fixtures.DesktopBackendTests();self.f.setUp()
        check=self.f.checks.check
        self.f.checks.check=lambda *a,**kw:replace(check(*a,**kw),capabilities=dict(supported_units=['conscript'],runtime_tactical_supported=True,tactics_supported=False))
        self.result,self.request,_=self.f.start();self.backend=self.f.backend;self.run=self.result['run_id']
        row=self.backend._launch(self.run);self.binding=SessionBinding.from_dict(json.loads(row['binding_json']))
        self.f.status_file(self.result,state='fault');self.f.spawner.alive=False;self.backend._status(row)
        self.host_receipt=self.backend.journal.get_command(self.run,self.request)['receipt']
        self.path=self.backend.state_dir/'runs'/self.run/'idle-runtime-release-review.json'

    def tearDown(self):self.f.tearDown()

    def proof(self,**changes):
        proof=dict(kind='idle_runtime_host_release_review',binding=self.binding.public(),run_id=self.run,
            host_pid=self.host_receipt['host_pid'],host_start_time=self.host_receipt['host_start_time'],
            native_release_verified=True,no_control_acquired=True,physical_home_claimed=False,mission_effect_granted=False)
        proof.update(changes);self.path.parent.mkdir(parents=True,exist_ok=True);self.path.write_text(json.dumps(proof),encoding='utf-8')
        request=str(uuid.uuid4());self.backend.journal.reserve_command(self.run,request,'review_idle_runtime_release',{})
        self.backend.journal.mark_dispatching(self.run,request)
        self.backend.journal.record_outcome(self.run,request,'released',dict(reason_code='idle_runtime_host_native_entries_independently_verified',
            binding_hash=self.binding.binding_hash,host_pid=self.host_receipt['host_pid'],host_start_time=self.host_receipt['host_start_time'],
            native_release_verified=True,no_control_acquired=True,review_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest()))

    def released(self):return self.backend._release_receipt(self.run,self.binding,self.host_receipt)

    def test_explicit_bound_idle_review_is_required_and_changed_file_invalidates_it(self):
        self.assertFalse(self.released());self.proof();self.assertTrue(self.released())
        self.path.write_text('{}');self.assertFalse(self.released())

    def test_foreign_review_or_home_effect_claim_does_not_grant_release(self):
        for change in ({'run_id':str(uuid.uuid4())},{'binding':{}},{'host_pid':999},
                       {'no_control_acquired':False},{'physical_home_claimed':True},{'mission_effect_granted':True}):
            self.proof(**change);self.assertFalse(self.released())

    def test_even_completed_tactical_command_disallows_idle_exception(self):
        self.proof();request=str(uuid.uuid4())
        self.backend.journal.reserve_command(self.run,request,'reserve',{})
        self.backend.journal.mark_dispatching(self.run,request)
        self.backend.journal.record_outcome(self.run,request,'rejected',{'reason_code':'synthetic_only'})
        self.assertFalse(self.released())

    def test_unresolved_command_still_prevents_release(self):
        self.proof();self.backend.journal.reserve_command(self.run,str(uuid.uuid4()),'produce',{})
        self.assertFalse(self.released())

if __name__=='__main__':unittest.main()
