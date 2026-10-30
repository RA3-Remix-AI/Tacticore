"""Artificial readonly queue replay into the real resource store; no live source."""
import copy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import unittest
import uuid

from host_runtime.contracts import ContractError
from host_runtime.macro_expansion_scope import TARGETS
from host_runtime.resource_reservations import ResourceReservationStore
from host_runtime.test_resource_reservations import queue_cost
from host_runtime.test_macro_expansion_feedback import sample
from host_runtime.resource_settlement_adapter import (SettlementSession,registered_snapshot,QUEUE_SOURCE,
    NativeResourceSettlementAdapter,QueueCashAttribution)


ACTION='producesickle'
FLAGS=tuple('f'+str(i) for i in range(20))
ACTIONS=tuple(TARGETS)+('budgeteconomy','budgetarmy','budgettech')+tuple('legacy'+str(i) for i in range(10))
MASK=(1<<ACTIONS.index(ACTION))|(1<<ACTIONS.index('budgetarmy'))


def flags(mask):return dict(flags=[dict(name=f,present=True,value=bool(mask&(1<<i))) for i,f in enumerate(FLAGS)])


def raw(frame=1500,paid=None,*,multiple=False):
    nodes=[]
    if paid is not None:
        for index in range(2 if multiple else 1):
            nodes.append(dict(node=hex(0x60000+index*0x100),producer_thing_id=765,producer_thing='0x40000',module='0x50000',
                kind=1,native_queue_id=18+index,target='0x70000',target_hash=TARGETS[ACTION][0],native_total_cost=850,
                native_paid_accumulator=paid,outstanding_payment_upper_bound=850-paid,
                previous='0x0' if not index else '0x60000',next='0x60100' if multiple and not index else '0x0',
                paid_stability_policy='strict_equal_double_read'))
    return dict(schema_version=1,kind='native_own_production_queue_commitment_observation',source=QUEUE_SOURCE,
        frame=frame,frame_after=frame,session_identity=dict(game='0x10000',owner='0x20000',owner_index=3,template_factory='0x30000'),
        module_census=[dict(thing_id=765,thing='0x40000',template_hash=TARGETS[ACTION][1],modules=[dict(module='0x50000',vtable='0xc3fad0')],module_vector_terminated=True)],
        queues=[dict(module='0x50000',producer_thing_id=765,head=nodes[0]['node'] if nodes else '0x0',tail=nodes[-1]['node'] if nodes else '0x0',nodes=nodes)],
        registered_roster_scan_complete=True,live_roster_scan_complete=True,roster_union_scan_complete=True,
        roster_scan_complete=True,queue_scan_complete=True,necessary_fields_stable=True,paid_stability_policy='strict_equal_double_read',
        native_calls=0,process_writes=0,enemy_details_read=False,field_qualified_complete_queue_coverage=False)


def cash_proof(session,command,seq,queue,frame,previous):
    # Artificial proof supplied solely by this test. No production reader signs it.
    return QueueCashAttribution(session,command,seq,queue.identity,frame,previous,queue.paid,'a'*64,
        debit_path_verified=True,queue_birth_bound_to_intent=True,zero_paid_at_queue_initialization_verified=True,
        no_transfer_or_load_since_queue_birth=True,cash_attribution_verified=True)


class SettlementAdapterTests(unittest.TestCase):
    def setUp(self):
        self.sid=str(uuid.uuid4());self.command=str(uuid.uuid4());self.plan='bound-plan'
        self.session=SettlementSession(self.sid,101,134376534415833801,'a'*64,'b'*64,
            ('0x10000','0x20000','0x30000'),'0x80000','0x90000','0xa0000')
        self.store=ResourceReservationStore(self.sid)
        fact=replace(queue_cost(),session_id=self.sid,action=ACTION,template_hash=TARGETS[ACTION][0],upper_cost=850,producer_type_hash=TARGETS[ACTION][1])
        self.store.reserve(self.plan,self.command,fact);self.store.delivery_started(self.command);self.store.acknowledged(self.command,1)
        self.manifest=dict(protocol_version=2,package_sha256='b'*64,flags=list(FLAGS),consumers=[dict(action=a,flag=f) for a,f in zip(ACTIONS,FLAGS)])
        self.prepared,self.ack=self.records(self.command,1,1501,MASK,60)
        self.baseline=registered_snapshot(self.session,raw())

    def native(self,seq,frame,mask,duration):
        ticks=self.session.process_creation_filetime
        return dict(magic=0x4d503032,version=2,pid=101,start_low=ticks&0xffffffff,start_high=ticks>>32,
            owner=0x20000,ai=0x80000,personality=0x90000,player_template=0xa0000,personality_id=0x799613e0,
            request=seq,ack=seq,phase=1,error=0,active=int(bool(mask)),applied_mask=mask,self_hook_installed=1,
            lease_held=1,cleanup_verified=int(not mask),last_frame=frame,deadline_frame=1561 if mask else 0,start_frame=100)

    def records(self,ident,seq,frame,mask,duration):
        pre=dict(kind='command_prepared',command_id=ident,seq=seq,kind_code=1,mask=mask,duration_frames=duration,session_id=self.sid,pid=101)
        ack=dict(kind='command_acknowledged',command_id=ident,seq=seq,native_gate_acknowledged=True,
            native=self.native(seq,frame,mask,duration),independent_flags=flags(mask),session_id=self.sid,pid=101)
        return pre,ack

    def adapter(self,**kwargs):
        return NativeResourceSettlementAdapter.bind(self.store,self.session,self.command,manifest=self.manifest,
            prepared=self.prepared,ack=self.ack,baseline=self.baseline,baseline_sample=sample(ACTION),**kwargs)

    def observe(self,adapter,frame=1502,paid=17,**kwargs):
        return adapter.observe(registered_snapshot(self.session,raw(frame,paid,**kwargs)),native=self.native(1,frame,MASK,60),flags=flags(MASK))

    def clear(self,adapter,frame=1503):
        pre,ack=self.records(str(uuid.uuid4()),2,frame,0,1)
        return adapter.independent_clear(pre,ack),pre,ack

    def held(self):return self.store.public(self.command)['held_reservation_amount']

    def test_matching_new_queue_records_acceptance_but_paid_field_and_clear_are_not_cash(self):
        adapter=self.adapter();facts=self.observe(adapter)
        self.assertEqual([f.kind for f in facts],['queue_accepted']);self.assertEqual(facts[0].paid_amount,17)
        self.assertFalse(facts[0].cash_attribution_verified)
        self.clear(adapter);self.observe(adapter,1504,850)
        public=self.store.public(self.command)
        self.assertTrue(public['queue_acceptance_independently_verified']);self.assertTrue(public['preference_release_independently_verified'])
        self.assertEqual(public['actual_cash_payment_verified_amount'],0);self.assertEqual(self.held(),850)

    def test_artificial_separately_verified_cash_and_independent_clear_complete_real_store(self):
        adapter=self.adapter(cash_supplier=cash_proof)
        self.assertEqual([f.kind for f in self.observe(adapter)],['queue_accepted','payment_consumed'])
        self.assertEqual(self.store.public(self.command)['actual_cash_payment_verified_amount'],17)
        _,pre,ack=self.clear(adapter)
        self.observe(adapter,1504,850)
        self.assertEqual(self.store.public(self.command)['status'],'consumed');self.assertEqual(self.held(),0)
        adapter.independent_clear(pre,ack) # Exact fact-id replay, even after a later payment.
        self.assertEqual(self.held(),0)

    def test_clear_without_queue_never_infers_no_acceptance_audit_or_releases_reservation(self):
        adapter=self.adapter();fact,_,_=self.clear(adapter)
        self.assertEqual(fact.kind,'preference_cleared');self.assertFalse(self.store.public(self.command)['no_queue_acceptance_independently_verified'])
        self.assertEqual(adapter.observe(registered_snapshot(self.session,raw(1504))),());self.assertEqual(self.held(),850)

    def test_disappearance_producer_loss_and_multiple_queues_never_cancel_or_refund(self):
        for mode in ('disappear','producer','multiple'):
            with self.subTest(mode=mode):
                self.setUp();adapter=self.adapter()
                if mode=='multiple':snapshot=registered_snapshot(self.session,raw(1502,17,multiple=True))
                else:
                    self.observe(adapter);value=raw(1503,None if mode=='disappear' else 30)
                    if mode=='producer':value['module_census'][0]['thing']='0x41000';value['queues'][0]['nodes'][0]['producer_thing']='0x41000'
                    snapshot=registered_snapshot(self.session,value)
                with self.assertRaises(ContractError):adapter.observe(snapshot,native=self.native(1,1503,MASK,60),flags=flags(MASK))
                self.assertEqual(self.held(),850);self.assertFalse(self.store.public(self.command)['cancellation_independently_verified'])
                self.assertIsNone(self.store.public(self.command)['refund_verified_amount'])

    def test_changed_node_paid_regression_and_identity_cannot_rebind_old_queue(self):
        for mode in ('node','paid','session'):
            self.setUp();adapter=self.adapter();self.observe(adapter);value=raw(1503,10 if mode=='paid' else 20)
            if mode=='node':value['queues'][0]['head']=value['queues'][0]['tail']=value['queues'][0]['nodes'][0]['node']='0x61000'
            snapshot=registered_snapshot(self.session,value)
            if mode=='session':snapshot=replace(snapshot,session=replace(self.session,pid=102))
            with self.subTest(mode=mode),self.assertRaises(ContractError):adapter.observe(snapshot)
            self.assertEqual(self.held(),850)

    def test_unknown_recovered_or_failed_delivery_has_no_settlement_entry(self):
        self.store.delivery_unknown(self.command)
        with self.assertRaises(ContractError):self.adapter()
        self.store=ResourceReservationStore.from_snapshot(self.store.snapshot())
        with self.assertRaises(ContractError):self.adapter()
        self.assertEqual(self.held(),850)

    def test_unknown_after_adapter_binding_cannot_be_settled_by_later_good_samples(self):
        adapter=self.adapter(cash_supplier=cash_proof);self.store.delivery_unknown(self.command)
        with self.assertRaises(ContractError):self.observe(adapter)
        with self.assertRaises(ContractError):self.clear(adapter)
        self.assertEqual(self.held(),850)

    def test_window_requires_current_bound_seq_twenty_flags_and_deadline_minus_duration(self):
        for mode in ('version','creation','sequence','flags','deadline','changed_deadline','expiry','baseline'):
            self.setUp()
            if mode=='baseline':self.baseline=registered_snapshot(self.session,raw(1500,0))
            elif mode=='deadline':self.ack['native']['deadline_frame']=1550
            if mode in ('baseline','deadline'):
                with self.assertRaises(ContractError):self.adapter()
                continue
            adapter=self.adapter();native=self.native(1,1502,MASK,60);gate=flags(MASK);frame=1502
            if mode=='version':native['version']=1
            elif mode=='creation':native['start_low']+=1
            elif mode=='sequence':native['request']=native['ack']=2
            elif mode=='flags':gate['flags'].pop()
            elif mode=='changed_deadline':native['deadline_frame']+=1
            else:frame=1561;native['last_frame']=1561
            with self.subTest(mode=mode),self.assertRaises(ContractError):adapter.observe(registered_snapshot(self.session,raw(frame,17)),native=native,flags=gate)
            self.assertEqual(self.held(),850)

    def test_cash_claim_requires_every_separate_attribution_and_debit_guard(self):
        for key in ('debit_path_verified','queue_birth_bound_to_intent','zero_paid_at_queue_initialization_verified',
                'no_transfer_or_load_since_queue_birth','cash_attribution_verified'):
            self.setUp()
            supplier=lambda *args,key=key:replace(cash_proof(*args),**{key:False})
            adapter=self.adapter(cash_supplier=supplier)
            with self.subTest(key=key),self.assertRaisesRegex(ContractError,'payment_attribution'):self.observe(adapter)
            self.assertEqual(self.store.public(self.command)['actual_cash_payment_verified_amount'],0);self.assertEqual(self.held(),850)

    def test_cash_foreign_queue_false_amount_wrong_previous_or_untyped_claim_rejected(self):
        for mode in ('queue','amount','previous','source','untyped'):
            self.setUp()
            def supplier(*args):
                proof=cash_proof(*args)
                if mode=='queue':return replace(proof,queue_identity=proof.queue_identity[:-1]+(999,))
                if mode=='amount':return replace(proof,cumulative_verified_paid=850)
                if mode=='previous':return replace(proof,previous_verified_paid=17)
                if mode=='source':return replace(proof,source='observed_balance_difference')
                return proof.__dict__
            adapter=self.adapter(cash_supplier=supplier)
            with self.subTest(mode=mode),self.assertRaises(ContractError):self.observe(adapter)
            self.assertEqual(self.held(),850)

    def test_failed_persistence_never_advances_adapter_or_releases_verified_cash(self):
        adapter=self.adapter(cash_supplier=cash_proof);failed=[True]
        def persist(snapshot):
            if failed[0]:raise OSError('synthetic disk failure')
        self.store.persist=persist
        with self.assertRaises(OSError):self.observe(adapter)
        self.assertIsNone(adapter.accepted);self.assertEqual(self.store.public(self.command)['status'],'acknowledged')
        failed[0]=False;self.observe(adapter);self.assertEqual(self.store.public(self.command)['actual_cash_payment_verified_amount'],17)

    def test_payment_persistence_failure_replays_without_double_acceptance_or_payment(self):
        adapter=self.adapter(cash_supplier=cash_proof);failed=[True]
        def persist(snapshot):
            if failed[0] and snapshot['rows'][self.command]['paid_amount']>0:raise OSError('synthetic payment journal failure')
        self.store.persist=persist
        with self.assertRaises(OSError):self.observe(adapter)
        self.assertEqual(self.store.public(self.command)['status'],'queue_accepted');self.assertIsNotNone(adapter.accepted)
        self.assertEqual(adapter.verified_paid,0);self.assertEqual(len(self.store.snapshot()['fact_ids']),1)
        failed[0]=False;self.observe(adapter)
        self.assertEqual(adapter.verified_paid,17);self.assertEqual(len(self.store.snapshot()['fact_ids']),2)

    def test_concurrent_duplicate_observations_keep_single_acceptance_and_payment(self):
        adapter=self.adapter(cash_supplier=cash_proof)
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(lambda _:self.observe(adapter),range(4)))
        self.assertEqual(sum(len(r) for r in results),2);self.assertEqual(len(self.store.snapshot()['fact_ids']),2)
        self.assertEqual(self.store.public(self.command)['actual_cash_payment_verified_amount'],17);self.assertEqual(self.held(),850)

    def test_upper_cost_mismatch_cannot_create_a_second_unreserved_obligation(self):
        adapter=self.adapter();value=raw(1502,17);node=value['queues'][0]['nodes'][0]
        node['native_total_cost']=900;node['outstanding_payment_upper_bound']=883
        with self.assertRaises(ContractError):adapter.observe(registered_snapshot(self.session,value),native=self.native(1,1502,MASK,60),flags=flags(MASK))
        self.assertEqual(self.store.public(self.command)['status'],'acknowledged');self.assertEqual(self.held(),850)

    def test_clear_must_be_next_distinct_command_with_zero_flags_and_real_cleanup(self):
        for mode in ('same_uuid','sequence','duration','flags','cleanup','boolean'):
            self.setUp();adapter=self.adapter();self.observe(adapter);pre,ack=self.records(str(uuid.uuid4()),2,1503,0,1)
            if mode=='same_uuid':pre['command_id']=ack['command_id']=self.command
            elif mode=='sequence':pre['seq']=ack['seq']=ack['native']['request']=ack['native']['ack']=3
            elif mode=='duration':pre['duration_frames']=0
            elif mode=='flags':ack['independent_flags']['flags'][-1]['value']=True
            elif mode=='cleanup':ack['native']['cleanup_verified']=0
            else:ack['native']['lease_held']=True
            with self.subTest(mode=mode),self.assertRaises(ContractError):adapter.independent_clear(pre,ack)
            self.assertFalse(self.store.public(self.command)['preference_release_independently_verified']);self.assertEqual(self.held(),850)


class RegisteredSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.session=SettlementSession(str(uuid.uuid4()),101,123,'a'*64,'b'*64,('0x10000','0x20000','0x30000'),'0x80000','0x90000','0xa0000')

    def test_research_union_fields_do_not_become_cash_or_global_coverage_facts(self):
        result=registered_snapshot(self.session,raw(1502,17))
        self.assertEqual(result.queues[0].paid,17);self.assertEqual(result.queues[0].key,(765,18))
        self.assertFalse(hasattr(result,'cash_attribution_verified'));self.assertFalse(hasattr(result,'all_native_payment_commitments_verified'))

    def test_unknown_source_unstable_paid_incomplete_modules_and_queue_identity_fail_closed(self):
        for mode in ('source','stable','span','owner','missing_module','paid','cost','kind','link','duplicate','target','calls'):
            value=raw(1502,17);node=value['queues'][0]['nodes'][0]
            if mode=='source':value['source']='native_player_partial_roster'
            elif mode=='stable':node['paid_stability_policy']='minimum_paid_fallback'
            elif mode=='span':value['frame_after']+=3
            elif mode=='owner':value['session_identity']['owner_index']=4
            elif mode=='missing_module':value['queues']=[]
            elif mode=='paid':node['native_paid_accumulator']=851
            elif mode=='cost':node['native_total_cost']=True
            elif mode=='kind':node['kind']=3
            elif mode=='link':node['next']='0x60000'
            elif mode=='duplicate':value['module_census'].append(copy.deepcopy(value['module_census'][0]))
            elif mode=='target':node['target']='0x1'
            else:value['native_calls']=True
            with self.subTest(mode=mode),self.assertRaises(ContractError):registered_snapshot(self.session,value)
