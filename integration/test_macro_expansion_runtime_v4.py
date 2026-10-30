"""Artificial raw transport/journal integration; no native attachment or model."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
import uuid

from host_runtime.contracts import ContractError,SessionBinding
from host_runtime.journal import CommandJournal
from host_runtime.macro_expansion_factory_v4 import (NativeDispatchLockV4,NativeEvidencePortV4,create_native_evidence_port_v4,create_expansion_controller_v4)
from host_runtime.macro_expansion_runtime_v4 import MacroExpansionControllerV4
from host_runtime.macro_expansion_runtime import MacroExpansionController
from host_runtime.macro_policy_runtime import COMMANDER
from host_runtime.macro_expansion_scope import TARGETS
from host_runtime.resource_admission_reservations_v4 import (AdmissionReservationStoreV4,AdmissionCostV4,FinancialStateV4,CLOSED,restore_store_v4)
from host_runtime.macro_admission_feedback_v4 import compact_admission_feedback_v4,restore_admission_feedback_v4,MacroRequestAuditV4
from host_runtime.test_macro_expansion_runtime import expansion_scope
from host_runtime.test_macro_expansion_feedback import sample
import test_resource_settlement_adapter as fixture

TRUE_FINANCE=('complete_registered_live_union_coverage_verified','all_production_upgrade_modules_and_nodes_verified',
    'same_financial_window_stable','native_payment_balance_currency_verified','owner_lifecycle_contract_verified',
    'field_complete_queue_coverage_qualified','held_handle_identity_before_after_verified','gc_inactive_verified')


class Clock:
    value=1_000_000_000
    def __call__(self):self.value+=10_000_000;return self.value


class RawProbe:
    def __init__(self,test,output):
        self.test=test;self.output=output;self.manifest=copy.deepcopy(test.fixture.manifest)
        self.session=dict(session_id=test.session.session_id,pid=test.session.pid,process_creation_filetime=test.session.process_creation_filetime,mod_sha256=test.session.package_sha256)
        self.session['start_time']=test.binding.game_process_start
        self.memory=SimpleNamespace(u32=lambda address:0x10000 if address==0xcd8ce4 else test.frame,read=lambda *args:b'')
        self.ledger={};self.pending=False;self.calls=[];self.closed=False;self.state=test.fixture.native(0,test.frame,0,1)
        attach=[dict(kind='attach_prepared',session_id=test.session.session_id,pid=test.session.pid,monotonic_ns=test.clock()),
            dict(kind='attach_acknowledged',session_id=test.session.session_id,pid=test.session.pid,monotonic_ns=test.clock(),native=self.state)]
        (output/'policy-probe.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in attach),encoding='utf8')
        self.drop_ack=False;self.fail_apply=False;self.bad_seq=False
    def apply(self,actions,duration,command):
        self.test.port.lock.require_owned();self.calls.append((actions,duration,command));self.pending=True
        seq=len(self.calls);mask=sum(1<<next(i for i,row in enumerate(self.manifest['consumers']) if row['action']==action) for action in actions)
        self.test.frame+=1
        pre,ack=self.test.fixture.records(command,seq,self.test.frame,mask,duration)
        ack['native']['active']=0
        ack['native']['deadline_frame']=self.test.frame+duration if mask else 0
        pre['monotonic_ns']=self.test.clock();ack['monotonic_ns']=self.test.clock()
        self.ledger[command]=dict(status='unknown');self.state=copy.deepcopy(ack['native'])
        with (self.output/'policy-probe.jsonl').open('a',encoding='utf8') as stream:
            stream.write(json.dumps(pre)+'\n')
            if not self.drop_ack:stream.write(json.dumps(ack)+'\n')
        if self.fail_apply:raise RuntimeError('artificial delivery unknown')
        self.pending=False;self.ledger[command]=dict(status='acknowledged',receipt=ack)
        return dict(ack,seq=999 if self.bad_seq else seq)
    def native_status(self):return copy.deepcopy(self.state)
    def close(self):self.test.port.lock.require_owned();self.closed=True


class ExpansionV4Tests(unittest.TestCase):
    def setUp(self):
        f=fixture.SettlementAdapterTests();f.setUp();self.fixture=f;self.session=f.session
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.directory=Path(self.tmp.name)
        self.clock=Clock();self.frame=1500;self.events=[];self.persisted=[]
        self.run=str(uuid.uuid4());self.journal=CommandJournal(self.directory/'journal.sqlite3');self.addCleanup(self.journal.close)
        from host_runtime.session_discovery_native import creation_start
        self.binding=SessionBinding(1,self.session.session_id,3,COMMANDER,self.session.pid,creation_start(self.session.process_creation_filetime),
            str(uuid.uuid4()),self.session.executable_sha256,self.session.package_sha256)
        self.journal.register_run(self.run,self.binding.public())
        self.raw=RawProbe(self,self.directory)
        self.port=create_native_evidence_port_v4(self.raw,self.journal,self.run,self.session,
            read_flags=lambda *args:fixture.flags(self.raw.state['applied_mask']),clock=self.clock,admission_apply=self.artificial_guarded_apply)
        self.store=AdmissionReservationStoreV4(self.session,persist=lambda snapshot:self.persisted.append(snapshot))
        scope=expansion_scope(('producesickle',));scope=replace(scope,budget=replace(scope.budget,package_sha256=self.session.package_sha256),
            expansion_evidence=(('producesickle',f.manifest['consumers'][5]['flag']),))
        self.scope=scope;self.cash=3000;self.debt=0;self.financial_failed=False
        self.controller=MacroExpansionControllerV4(self.port,scope,self.session.session_id,'e'*64,self.event,
            cost_supplier=self.cost,financial_supplier=self.finance,reservation_store=self.store)
        self.plan=SimpleNamespace(origin='model',session_id=self.session.session_id,commander_id=COMMANDER,player_id=3,
            based_on_game_time_seconds=100.,expires_at_game_seconds=140.,tactical_tasks=(),runtime_task=None,
            macro_actions=('producesickle','budgetarmy'),macro_production=SimpleNamespace(action='producesickle',additional_count=1),objective_region=None,plan_id='first')
        self.controller.refresh(sample('producesickle'))

    def event(self,kind,**payload):self.events.append((kind,copy.deepcopy(payload)))
    def artificial_guarded_apply(self,actions,duration,command,*,last_check):
        # This fixture has no hidden native-client preflight or fsync. The
        # real publisher has its own adverse-delay tests at that boundary.
        last_check();return self.raw.apply(actions,duration,command)
    def financial(self):
        begin=self.clock();end=self.clock()
        return FinancialStateV4(self.session,self.frame,self.frame,(self.frame,),begin,end,self.cash,self.debt,'a'*64,'b'*64,
            **{key:True for key in TRUE_FINANCE})
    def cost(self,action,observed,seconds):
        self.port.lock.require_owned()
        return AdmissionCostV4(self.financial(),action,TARGETS[action][0],765,TARGETS[action][1],self.frame,850,'c'*64,
            native_upper_cost_verified=True,loaded_target_schema_verified=True,current_quote_and_producer_verified=True)
    def finance(self):
        self.port.lock.require_owned()
        if self.financial_failed:raise ValueError('artificial unstable financial observation')
        self.frame+=1;self.raw.state['last_frame']=self.frame
        return self.financial()
    def dispatch(self):return self.controller.dispatch(self.plan,self.frame/15,effective_hash='e'*64)
    def queue_and_tick(self):
        self.frame+=1;self.raw.state['last_frame']=self.frame
        self.controller.refresh(sample('producesickle',self.frame,queues=[(18,17)]));self.controller.tick(self.frame/15)

    def test_known_raw_ack_clear_and_fresh_current_state_end_buffer_then_next_dispatch(self):
        sent=self.dispatch();self.assertEqual(sent,self.dispatch());self.assertEqual(len(self.raw.calls),1)
        self.assertEqual(self.store.public(sent['command_id'])['status'],'acknowledged')
        self.assertTrue(self.persisted);self.queue_and_tick()
        public=self.controller.resource_feedback();self.assertEqual(public['status'],CLOSED);self.assertEqual(public['active_buffer_amount'],0)
        self.assertIsNone(public['actual_cash_payment']);self.assertIsNone(public['refund_amount']);self.assertIsNone(public['latent_native_work_cancelled'])
        self.assertEqual(len(self.raw.calls),2);self.assertFalse(self.controller.busy)
        self.controller.refresh(sample('producesickle',self.frame));self.plan=copy.deepcopy(self.plan);self.plan.plan_id='next'
        self.dispatch();self.assertEqual(len(self.raw.calls),3)

    def test_reserve_and_delivery_are_durable_before_physical_apply(self):
        original=self.raw.apply
        def apply(*args):
            self.assertEqual(self.persisted[-1]['rows'][args[2]]['status'],'delivering')
            self.assertEqual(self.journal.get_command(self.run,args[2])['status'],'dispatching')
            return original(*args)
        self.raw.apply=apply;self.dispatch()

    def test_simplified_receipt_without_raw_ack_or_seq_disagreement_is_unknown_forever(self):
        for mode in ('missing','wrong_seq','exception'):
            with self.subTest(mode=mode):
                if mode!='missing':self.tearDown();self.doCleanups();self.setUp()
                self.raw.drop_ack=mode=='missing';self.raw.bad_seq=mode=='wrong_seq';self.raw.fail_apply=mode=='exception'
                with self.assertRaisesRegex(ContractError,'outcome_unknown'):self.dispatch()
                command=self.controller.expansion_resource_command;self.assertEqual(self.store.public(command)['status'],'unknown')
                self.controller.tick(200.);self.assertEqual(len(self.raw.calls),1)
                with self.assertRaises(ContractError):self.dispatch()

    def test_clear_unknown_does_not_release_buffer_or_use_policy_released_bool(self):
        self.dispatch();self.raw.drop_ack=True
        with self.assertRaisesRegex(ContractError,'outcome_unknown'):self.queue_and_tick()
        self.assertEqual(self.controller.resource_feedback()['status'],'unknown');self.assertEqual(self.controller.resource_feedback()['active_buffer_amount'],850)
        self.controller.expansion_tracker.policy_released=True;self.controller.tick(200.)
        self.assertEqual(self.controller.resource_feedback()['active_buffer_amount'],850)

    def test_financial_unavailable_keeps_known_clear_held_without_resending_clear(self):
        self.dispatch();self.financial_failed=True;self.queue_and_tick()
        self.assertEqual(self.controller.resource_feedback()['status'],'preference_cleared');self.assertEqual(len(self.raw.calls),2)
        self.controller.tick(self.frame/15);self.assertEqual(len(self.raw.calls),2)
        self.financial_failed=False;self.controller.tick(self.frame/15)
        self.assertEqual(self.controller.resource_feedback()['status'],CLOSED);self.assertEqual(len(self.raw.calls),2)

    def test_known_shortfall_reconciles_and_later_fresh_admission_refuses(self):
        self.dispatch();self.cash=596;self.debt=1890;self.queue_and_tick()
        public=self.controller.resource_feedback();self.assertEqual(public['status'],CLOSED);self.assertEqual(public['current_financial_shortfall'],1294)
        self.controller.refresh(sample('producesickle',self.frame));self.plan=copy.deepcopy(self.plan);self.plan.plan_id='shortfall'
        with self.assertRaisesRegex(ContractError,'insufficient_current_funds'):self.dispatch()
        self.assertEqual(len(self.raw.calls),2)

    def test_latent_enqueue_after_reconcile_is_rechecked_before_new_dispatch(self):
        self.dispatch();self.queue_and_tick();self.cash=1000;self.debt=900
        self.controller.refresh(sample('producesickle',self.frame));self.plan=copy.deepcopy(self.plan);self.plan.plan_id='latent'
        with self.assertRaisesRegex(ContractError,'insufficient_current_funds'):self.dispatch()

    def test_unresolved_durable_command_not_yet_in_raw_probe_blocks_reconciliation(self):
        self.dispatch();self.financial_failed=True;self.queue_and_tick()
        self.journal.reserve_command(self.run,str(uuid.uuid4()),'macro_policy',dict(native_command_id=str(uuid.uuid4()),actions=[],duration_frames=1))
        self.financial_failed=False
        with self.assertRaisesRegex(ContractError,'ledger_unknown'):self.controller.tick(self.frame/15)
        self.assertEqual(self.controller.resource_feedback()['status'],'unknown')

    def test_current_clear_cleanup_marker_must_agree_with_real_zero_flags(self):
        self.dispatch();self.financial_failed=True;self.queue_and_tick();self.financial_failed=False
        self.raw.state['cleanup_verified']=0
        with self.assertRaisesRegex(ContractError,'ledger_unknown'):self.controller.tick(self.frame/15)
        self.assertEqual(self.controller.resource_feedback()['status'],'unknown')

    def test_request_capacity_reserves_both_independent_clear_and_final_close(self):
        for seq in (2046,2047,2048):
            self.raw.state.update(request=seq,ack=seq)
            with self.subTest(seq=seq),self.assertRaisesRegex(ContractError,'clear_and_stop_capacity'):self.dispatch()
        self.assertFalse(self.raw.calls);self.assertFalse(self.store.rows)
        self.raw.state.update(request=2045,ack=2045)
        with self.port.lock:self.port.require_new_work_capacity()

    def test_existing_durable_unknown_blocks_new_reserve_before_any_native_call(self):
        self.journal.reserve_command(self.run,str(uuid.uuid4()),'macro_policy',dict(actions=[],duration_frames=1,native_command_id=str(uuid.uuid4())))
        with self.assertRaisesRegex(ContractError,'existing_native_ledger_unresolved'):self.dispatch()
        self.assertFalse(self.raw.calls);self.assertFalse(self.store.rows)

    def test_original_thirteen_budget_dispatch_delegates_legacy_and_uses_same_lock(self):
        self.controller.cost_supplier=None;self.controller.financial_supplier=None
        self.plan.macro_actions=('budgetarmy',);self.plan.macro_production=None
        result=self.dispatch();self.assertTrue(result['native_gate_acknowledged']);self.assertEqual(self.raw.calls[0][0],['budgetarmy'])
        self.assertFalse(self.store.rows);self.controller.stop();self.assertTrue(self.raw.closed)

    def test_none_or_old_fact_never_grants_new_action(self):
        self.controller.cost_supplier=None
        self.assertNotIn('producesickle',self.controller.available_actions(100.))
        with self.assertRaisesRegex(ContractError,'blocked_native_cost'):self.dispatch()
        self.assertFalse(self.raw.calls)
        self.controller.cost_supplier=lambda *args:fixture.queue_cost()
        with self.assertRaisesRegex(ContractError,'cost_required'):self.dispatch()
        self.assertFalse(self.raw.calls)

    def test_no_recovery_upgrade_and_stop_release_does_not_imply_reconciliation(self):
        self.dispatch();self.financial_failed=True;self.queue_and_tick()
        recovered=restore_store_v4(self.store.snapshot(),persist=lambda snapshot:None)
        controller=MacroExpansionControllerV4(self.port,self.scope,self.session.session_id,'e'*64,self.event,
            cost_supplier=self.cost,financial_supplier=self.finance,reservation_store=recovered)
        self.assertTrue(controller.busy);self.assertEqual(recovered.public(self.controller.expansion_resource_command)['status'],'unknown')
        self.controller.stop();self.assertTrue(self.raw.closed);self.assertEqual(self.controller.resource_feedback()['active_buffer_amount'],850)

    def test_lock_rejects_unowned_evidence_and_serializes_parallel_physical_dispatch(self):
        with self.assertRaisesRegex(ContractError,'shared_dispatch_lock'):self.port.snapshot()
        entered=threading.Event();done=threading.Event()
        def other():
            entered.set()
            with self.port.lock:done.set()
        with self.port.lock:
            worker=threading.Thread(target=other);worker.start();entered.wait(1)
            self.assertFalse(done.is_set())
        worker.join(1);self.assertTrue(done.is_set())

    def test_explicit_schema4_model_projection_rejects_fabricated_payment(self):
        self.dispatch();self.queue_and_tick();resource=self.controller.resource_feedback()
        compact=compact_admission_feedback_v4(resource);self.assertFalse(compact['hard_spending_cap_verified'])
        self.assertEqual(restore_admission_feedback_v4(compact),resource)
        self.assertEqual(compact['reconciled_frames'],resource['financial_observation_frames'])
        self.assertNotIn('current_credits',compact)
        self.assertIn('actual_cash_payment',compact['unverified_outcomes'])
        bad=copy.deepcopy(resource);bad['actual_cash_payment']=17
        with self.assertRaises(ContractError):compact_admission_feedback_v4(bad)
        audit=MacroRequestAuditV4(SimpleNamespace(),lambda *args,**kwargs:None,resource_supplier=lambda:resource)
        result=audit.prepare(dict(control_mode='macro_native',game_time_seconds=self.frame/15))
        self.assertEqual(result['macro_resource_feedback'],compact)
        self.assertEqual(compact_admission_feedback_v4(compact),compact)
        audit.resource_supplier=lambda:compact
        self.assertEqual(audit.prepare(dict(control_mode='macro_native',game_time_seconds=self.frame/15))['macro_resource_feedback'],compact)
        for change in (dict(known_ack=False),dict(buffer_scope='future_work_cancelled'),dict(unverified_outcomes=[]),dict(unknown_key=True)):
            with self.subTest(change=change),self.assertRaises(ContractError):restore_admission_feedback_v4(dict(compact,**change))

    def test_slow_cost_collection_cannot_reuse_old_readiness(self):
        original=self.controller.cost_supplier
        def slow(*args):
            self.frame+=20
            return original(*args)
        self.controller.cost_supplier=slow
        with self.assertRaisesRegex(ContractError,'stale'):self.dispatch()
        self.assertFalse(self.raw.calls);self.assertFalse(self.store.rows)

    def test_slow_reserve_persist_aborts_before_delivery_instead_of_dispatching_stale(self):
        def slow(snapshot):
            self.persisted.append(snapshot)
            if next(iter(snapshot['rows'].values()))['status']=='reserved':self.frame+=20
        self.store.persist=slow
        with self.assertRaises(ContractError):self.dispatch()
        self.assertFalse(self.raw.calls);self.assertEqual(self.controller.resource_feedback()['status'],'aborted_before_delivery')

    def test_slow_delivery_intent_persist_proves_not_invoked_and_aborts_without_native(self):
        def slow(snapshot):
            self.persisted.append(snapshot)
            if next(iter(snapshot['rows'].values()))['status']=='delivering':self.frame+=20
        self.store.persist=slow
        with self.assertRaisesRegex(ContractError,'refused_before_native'):self.dispatch()
        self.assertFalse(self.raw.calls);self.assertEqual(self.controller.resource_feedback()['status'],'aborted_before_delivery')

    def late_plan(self,expiry_frame):
        self.plan.based_on_game_time_seconds=expiry_frame/15-5
        self.plan.expires_at_game_seconds=expiry_frame/15

    def test_cost_and_reservation_and_delivery_event_expiry_are_known_not_dispatched(self):
        for stage in ('cost','reserve','delivering','event','final_event'):
            if stage!='cost':self.doCleanups();self.setUp()
            self.late_plan(1503)
            if stage=='cost':
                original=self.controller.cost_supplier
                def cost(*args):self.frame+=4;return original(*args)
                self.controller.cost_supplier=cost
            elif stage in ('reserve','delivering'):
                def persist(snapshot):
                    row=next(iter(snapshot['rows'].values()))
                    if row['status']==('reserved' if stage=='reserve' else 'delivering'):self.frame+=4
                self.store.persist=persist
            else:
                def event(kind,**facts):
                    if kind==('model_macro_expansion_prepared' if stage=='event' else 'model_macro_expansion_delivery_prepared'):self.frame+=4
                self.controller.event=event
            with self.subTest(stage=stage),self.assertRaises(ContractError):self.dispatch()
            self.assertFalse(self.raw.calls)
            if self.store.rows:self.assertEqual(self.controller.resource_feedback()['status'],'aborted_before_delivery')

    def test_expiry_after_durable_intent_produces_exact_no_invocation_proof_and_next_plan_can_close(self):
        self.late_plan(1503);original=self.journal.mark_dispatching;advanced=False
        def mark(*args):
            nonlocal advanced
            result=original(*args)
            if not advanced:self.frame+=4;advanced=True
            return result
        self.journal.mark_dispatching=mark
        with self.assertRaisesRegex(ContractError,'refused_before_native'):self.dispatch()
        self.assertTrue(advanced);self.assertFalse(self.raw.calls)
        aborted=self.controller.expansion_resource_command
        self.assertEqual(self.store.public(aborted)['status'],'aborted_before_delivery')
        row=self.journal.get_command(self.run,aborted)
        self.assertEqual(row['status'],'failed');self.assertFalse(row['receipt']['native_delivery_attempted'])
        self.assertEqual(row['receipt']['source'],'guarded_admission_no_native_invocation_v4')
        self.journal.mark_dispatching=original;self.plan.plan_id='after-known-not-invoked'
        self.plan.based_on_game_time_seconds=self.frame/15;self.plan.expires_at_game_seconds=self.frame/15+20
        self.controller.refresh(sample('producesickle',self.frame))
        self.dispatch();self.queue_and_tick()
        self.assertEqual(len(self.raw.calls),2);self.assertEqual(self.controller.resource_feedback()['status'],CLOSED)
        self.assertEqual(self.journal.get_command(self.run,aborted),row)

    def test_no_invocation_receipt_cannot_be_forged_or_hide_actual_unknown(self):
        self.test_expiry_after_durable_intent_produces_exact_no_invocation_proof_and_next_plan_can_close()
        commands=self.journal.commands_for_run(self.run)
        failed=next(row for row in commands if row['status']=='failed');receipt=copy.deepcopy(failed['receipt']);receipt['guard_source_sha256']='0'*64
        self.journal._db.execute('UPDATE commands SET receipt=? WHERE command_id=?',(json.dumps(receipt),failed['command_id']))
        with self.port.lock,self.assertRaisesRegex(ContractError,'no_invocation_history_unverified'):self.port.require_new_work_capacity()
        from host_runtime.macro_admission_delivery_v4 import abort_proven_before_native_v4,refusal_before_native_v4
        current=self.controller.expansion_resource_command
        # Even a new trusted refusal certificate cannot turn an unknown old
        # delivery into a no-op. That transition is deliberately unavailable.
        self.store.rows[current]['status']='unknown'
        proof=refusal_before_native_v4(self.session,current,'test','before_durable_intent',{}).proof
        with self.assertRaisesRegex(ContractError,'refusal_transition_invalid'):abort_proven_before_native_v4(self.store,proof)

    def test_full_known_not_invoked_ledger_must_not_change_inside_financial_window(self):
        self.test_expiry_after_durable_intent_produces_exact_no_invocation_proof_and_next_plan_can_close()
        failed=next(row for row in self.journal.commands_for_run(self.run) if row['status']=='failed')
        self.plan.plan_id='full-ledger-change';self.plan.based_on_game_time_seconds=self.frame/15;self.plan.expires_at_game_seconds=self.frame/15+20
        self.controller.refresh(sample('producesickle',self.frame));self.dispatch()
        original=self.controller.financial_supplier
        def financial():
            from host_runtime.macro_admission_delivery_v4 import known_not_invoked_receipt_v4
            from host_runtime.macro_expansion_factory_v4 import GUARDED_SOURCE_SHA256
            value=original()
            receipt=known_not_invoked_receipt_v4(self.session,self.run,failed['request_id'],failed['payload'],
                'another_individually_valid_reason',GUARDED_SOURCE_SHA256)
            self.journal._db.execute('UPDATE commands SET receipt=? WHERE command_id=?',(json.dumps(receipt),failed['command_id']))
            return value
        self.controller.financial_supplier=financial
        with self.assertRaisesRegex(ContractError,'ledger_unknown'):self.queue_and_tick()
        self.assertEqual(self.controller.resource_feedback()['status'],'unknown')

    def test_exact_requested_budget_duration_and_actual_deadline_are_checked_before_known_ack(self):
        for mode in ('budget','duration','late_native_tick'):
            if mode!='budget':self.doCleanups();self.setUp()
            self.late_plan(1530);original=self.raw.apply
            def changed(actions,duration,command):
                if mode=='budget':actions=[a if a!='budgetarmy' else 'budgeteconomy' for a in actions]
                elif mode=='duration':duration+=2
                else:self.frame+=2
                return original(actions,duration,command)
            self.raw.apply=changed
            with self.subTest(mode=mode),self.assertRaisesRegex(ContractError,'outcome_unknown'):self.dispatch()
            self.assertEqual(len(self.raw.calls),1);self.assertEqual(self.controller.resource_feedback()['status'],'unknown')
            row=self.journal.get_command(self.run,self.controller.expansion_resource_command)
            self.assertEqual(row['status'],'uncertain')

    def test_actual_duration_is_recomputed_from_fresh_frame_and_return_object_bounds_are_ignored(self):
        self.late_plan(1530);original_cost=self.controller.cost_supplier
        def cost(*args):self.frame+=2;return original_cost(*args)
        self.controller.cost_supplier=cost;original=self.raw.apply
        def returned_bounds(*args):
            receipt=original(*args);receipt=copy.deepcopy(receipt);receipt['native']['deadline_frame']+=500
            return receipt
        self.raw.apply=returned_bounds
        public=self.dispatch()
        self.assertEqual(self.raw.calls[0][1],1530-1502-1)
        self.assertLessEqual(self.controller.expansion_tracker.deadline_frame,1530)
        receipt=self.journal.get_command(self.run,public['command_id'])['receipt']
        self.assertEqual(receipt['native_deadline_frame'],self.controller.expansion_tracker.deadline_frame)

    def test_financial_read_and_persist_hold_same_lock_against_parallel_legacy_apply(self):
        self.dispatch();entered=threading.Event();done=threading.Event();worker=[]
        original=self.controller.financial_supplier
        def financial():
            def other():
                entered.set();self.port.transport.apply(['budgetarmy'],1,str(uuid.uuid4()));done.set()
            thread=threading.Thread(target=other);worker.append(thread);thread.start();entered.wait(1)
            self.assertFalse(done.wait(.02));return original()
        self.controller.financial_supplier=financial
        original_persist=self.store.persist
        def persist(snapshot):
            if next(iter(snapshot['rows'].values()))['status']==CLOSED:self.assertFalse(done.is_set())
            original_persist(snapshot)
        self.store.persist=persist;self.queue_and_tick()
        worker[0].join(1);self.assertTrue(done.is_set());self.assertEqual(self.controller.resource_feedback()['status'],CLOSED)

    def test_changed_financial_identity_and_before_clear_time_cannot_close_buffer(self):
        self.dispatch();original=self.controller.financial_supplier
        def wrong():
            fact=original();return replace(fact,session=replace(fact.session,process_creation_filetime=fact.session.process_creation_filetime+1))
        self.controller.financial_supplier=wrong;self.queue_and_tick()
        self.assertEqual(self.controller.resource_feedback()['status'],'preference_cleared')
        self.assertEqual(self.controller.resource_feedback()['active_buffer_amount'],850)

    def test_wrong_manifest_scope_flag_cannot_boot_v4_controller(self):
        scope=replace(self.scope,expansion_evidence=(('producesickle','wrongflag'),))
        with self.assertRaisesRegex(ContractError,'scope_transport_mismatch'):
            MacroExpansionControllerV4(self.port,scope,self.session.session_id,'e'*64,self.event,
                cost_supplier=self.cost,financial_supplier=self.finance,reservation_store=self.store)

    def test_production_factory_requires_durable_store_and_explicit_qualified_readers(self):
        args=(self.raw,self.journal,self.run,self.scope,self.session,'e'*64,self.event)
        with self.assertRaisesRegex(ContractError,'durable_store_required'):
            create_expansion_controller_v4(*args,read_flags=lambda *args:fixture.flags(0))
        with self.assertRaisesRegex(ContractError,'qualified_cost_supplier_required'):
            create_expansion_controller_v4(*args,read_flags=lambda *args:fixture.flags(0),persist=lambda value:None,cost_supplier=lambda *args:None)
        controller=create_expansion_controller_v4(*args,read_flags=lambda *args:fixture.flags(self.raw.state['applied_mask']),persist=lambda value:None,clock=self.clock,
            admission_apply=self.artificial_guarded_apply)
        self.port=controller.port
        controller.refresh(sample('producesickle'))
        self.assertNotIn('producesickle',controller.available_actions(100.));self.assertIn('budgetarmy',controller.available_actions(100.))

    def test_schema4_projection_roundtrip_keeps_held_unknown_and_blocked_facts(self):
        self.dispatch();known=self.controller.resource_feedback()
        self.assertEqual(restore_admission_feedback_v4(compact_admission_feedback_v4(known)),known)
        self.financial_failed=True;self.queue_and_tick();blocked=self.controller.resource_feedback()
        self.assertEqual(restore_admission_feedback_v4(compact_admission_feedback_v4(blocked)),blocked)
        self.store.delivery_unknown(self.controller.expansion_resource_command);unknown=self.controller.resource_feedback()
        self.assertEqual(restore_admission_feedback_v4(compact_admission_feedback_v4(unknown)),unknown)
        for change in (dict(active_buffer_amount=0),dict(current_credits=100),dict(actual_cash_payment=1),dict(unreviewed_claim=True)):
            with self.subTest(change=change),self.assertRaises(ContractError):compact_admission_feedback_v4(dict(unknown,**change))

    def test_production_factory_accepts_canonical_c_qualified_same_window_suppliers(self):
        # C's existing artificial memory + artificial price-review fixtures.
        # No real qualification is written or installed by this test.
        import time
        import test_macro_admission_factory_v4 as admission_fixture
        import test_quoteless_financial_factory_v4 as financial_fixture
        from host_runtime.session_discovery_native import creation_start
        admission_fixture.AdmissionFactoryTests.setUpClass();cost_case=admission_fixture.AdmissionFactoryTests();cost_case.setUp()
        self.addCleanup(cost_case.doCleanups);cost_provider=cost_case.provider()
        financial_fixture.FinancialFactoryTests.setUpClass();finance_case=financial_fixture.FinancialFactoryTests();finance_case.setUp()
        self.addCleanup(finance_case.doCleanups);financial_provider=finance_case.provider
        session=cost_provider.session;self.assertEqual(session,financial_provider.session)
        journal=CommandJournal(self.directory/'canonical-c-positive.sqlite3');self.addCleanup(journal.close)
        binding=SessionBinding(1,session.session_id,3,COMMANDER,session.pid,creation_start(session.process_creation_filetime),
            str(uuid.uuid4()),session.executable_sha256,session.package_sha256)
        run=str(uuid.uuid4());journal.register_run(run,binding.public())
        native=self.fixture.native(0,100,0,1);ticks=session.process_creation_filetime
        native.update(pid=session.pid,start_low=ticks&0xffffffff,start_high=ticks>>32,owner=int(session.game_identity[1],0),
            ai=int(session.ai_player,0),personality=int(session.personality_wrapper,0),player_template=int(session.player_template,0))
        game=int(session.game_identity[0],0);manifest=copy.deepcopy(self.raw.manifest);manifest['package_sha256']=session.package_sha256
        def forbidden(*args):self.fail('artificial canonical test must never dispatch or close native')
        raw=SimpleNamespace(session=dict(session_id=session.session_id,pid=session.pid,process_creation_filetime=ticks,
            mod_sha256=session.package_sha256,start_time=binding.game_process_start),manifest=manifest,output=self.directory,
            native_status=lambda:copy.deepcopy(native),memory=SimpleNamespace(u32=lambda address:game if address==0xcd8ce4 else 100,read=lambda *args:b''),
            ledger={},pending=False,apply=forbidden,close=forbidden)
        scope=replace(self.scope,budget=replace(self.scope.budget,package_sha256=session.package_sha256))
        controller=create_expansion_controller_v4(raw,journal,run,scope,session,'e'*64,self.event,read_flags=lambda *args:fixture.flags(0),
            cost_supplier=cost_provider,financial_supplier=financial_provider,persist=lambda value:None,clock=time.monotonic_ns,admission_apply=forbidden)
        value=sample('producesickle',100)
        for row in value['build_observation']['builders']:row['factory']['thing_id']=17
        for row in value['observation']['construction_feedback']['own_objects']:row['thing_id']=17
        for row in value['readiness']['own_objects']:row['thing_id']=17
        value['dependency']['session_identity'].update(zip(('game','owner','template_factory'),session.game_identity))
        for row in value['dependency']['actions'][0]['enqueue_admission_candidates']:row['producer_thing_id']=17
        controller.refresh(value)
        self.assertIn('producesickle',controller.available_actions(100/15))
        self.assertIs(type(cost_provider.last_fact),AdmissionCostV4)

    def test_twenty_actions_strategy1536_and_1200_chinese_traits_stay_under_wire_limit(self):
        # Reuse the same archived lawful snapshot and full pressure as the old
        # Host test, with the new explicit resource schema and unchanged codec.
        import test_macro_expansion_host as pressure_bootstrap
        from engine import Snapshot,Binding,StrategyEngine
        from battle_agent import BattleAgent
        from http_adapter import macro_system_prompt
        from macro_strategy import MacroStrategyMemory
        from host_runtime.macro_expansion_scope import EXTRA_ACTIONS,expansion_catalog_overrides
        from unittest.mock import Mock
        self.dispatch();self.queue_and_tick()
        expansion=self.controller.expansion_feedback();resources=self.controller.resource_feedback()
        # Maximum valid u32 amounts keep the test from depending on small
        # sample balances. These are artificial projection pressure values.
        resources.update(current_credits=0xffffffff,current_production_upgrade_commitment_upper_bound=0xffffffff,
            current_available_credit_filter=0,current_financial_shortfall=0)
        root=Path(__file__).resolve().parents[1]
        raw=json.loads((root/'acceptance/runs/20261028-075720-macro-probe/battle-host/macro-snapshots.jsonl').read_text().splitlines()[0])
        frame=round(raw['game_time_seconds']*15)
        for key in ('builder_frame','own_census_frame'):expansion[key]=frame
        actions=['budgeteconomy','budgetarmy','budgettech','produceconscript','produceflak','producetank','buildreactor','scout',
            'deployattack','deploydefense','regroup','withdraw','reinforce',*EXTRA_ACTIONS]
        raw['capabilities']['regions']=sorted(set(raw['capabilities']['regions'])|{'region_1_3','region_8_3'})
        raw['macro_control']=dict(mode='macro_native',available_actions=actions,production_counts={action:[1] for action in actions if action.startswith('produce')},
            region_targets={action:('region_1_3' if action=='deployattack' else 'region_8_3') for action in ('deployattack','deploydefense','regroup','withdraw','reinforce')})
        request=Snapshot.from_dict(raw);binding=Binding(request.session_id,3,COMMANDER,'commander','23968c8e-25d3-47bd-8c84-5f0d5bbfd43b')
        agent=BattleAgent(StrategyEngine(binding),context_budget_bytes=16384);agent.observe(raw)
        prose='优先观察经济和供电再决定扩张。保持生产设施运转，遇到明确威胁时调整资源分配。侦察只参考已知公开信息，不能把失联目标当作当前事实。保存长期战略但随实际局势修订，队伍和建筑的完成状态分别判断。'
        profile=SimpleNamespace(traits=(prose*20)[:1200],personality=1)
        measured=[]
        def wire(context):
            value=len(json.dumps({'messages':[dict(role='system',content=macro_system_prompt(profile,context)),
                dict(role='user',content=json.dumps(context,ensure_ascii=False,separators=(',',':')))]},ensure_ascii=False).encode())+1024
            measured.append(value);return value
        budget=dict(status='native_delegation_observed',selected_policy=None,actions=[],observed_frame=frame,native_effect_verified=False)
        memory=MacroStrategyMemory(session_id=binding.session_id,commander_id=COMMANDER,player_id=3,profile_revision=1,effective_hash='b'*64)
        def strategy(context):
            value=memory.context(context);value['fact_catalog']['wire_pressure_fixture']=''
            size=lambda:len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())
            remaining=1536-size();self.assertGreaterEqual(remaining,0)
            value['fact_catalog']['wire_pressure_fixture']='测'*(remaining//3)+'x'*(remaining%3);self.assertEqual(size(),1536)
            return value
        audit=MacroRequestAuditV4(SimpleNamespace(input_size=wire),Mock(),feedback_supplier=lambda:budget,
            expansion_supplier=lambda:expansion,resource_supplier=lambda:resources,
            catalog_supplier=lambda:expansion_catalog_overrides(EXTRA_ACTIONS),strategy_supplier=strategy)
        try:context=agent.context(request.model_context(binding),wire_size=audit.input_size,wire_limit=16384)
        except Exception as error:raise AssertionError('wire pressure min='+str(min(measured))+' max='+str(max(measured))) from error
        self.pressure_wire_bytes=audit.input_size(context)
        self.assertLessEqual(self.pressure_wire_bytes,16384);self.assertEqual(set(context['allowed_macro_actions']),set(actions))
        prepared=audit.prepare(context)
        self.assertEqual(prepared['macro_resource_feedback']['schema_version'],4)
        self.assertIn('latent_work_cancelled',prepared['macro_resource_feedback']['unverified_outcomes'])


if __name__=='__main__':unittest.main()
