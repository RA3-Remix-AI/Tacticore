"""Offline expansion dispatch; synthetic evidence is never written as a grant."""
from dataclasses import fields
from types import SimpleNamespace
import copy
import unittest
import uuid

from .contracts import ContractError
from .macro_policy_runtime import BudgetScope,COMMANDER
from .macro_group_role_scope import GroupRoleScope
from .macro_expansion_scope import ExpansionScope,TARGETS
from .macro_expansion_runtime import MacroExpansionController
from .test_macro_expansion_feedback import sample
from .test_resource_reservations import cost
from .resource_reservations import ResourceReservationStore


def legacy_scope():
    budget=BudgetScope('a'*64,{},tuple('flag'+str(n) for n in range(13)),
        dict(budgetarmy='army',budgeteconomy='economy'),{})
    return GroupRoleScope(budget,'flak',{},construction_flag='reactor')


def expansion_scope(actions=('buildpower','producesickle')):
    base=legacy_scope()
    return ExpansionScope(**{f.name:getattr(base,f.name) for f in fields(GroupRoleScope)},
        expansion_choices=actions,expansion_evidence=tuple((a,'expansion-'+a) for a in actions))


class ExpansionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.sid=str(uuid.uuid4());self.calls=[];self.closed=[]
        def apply(actions,duration,ident):
            self.calls.append((actions,duration,ident))
            return dict(seq=len(self.calls),native_start_frame=1501,native_deadline_frame=1501+duration)
        self.transport=SimpleNamespace(session=dict(session_id=self.sid,mod_sha256='a'*64),
            apply=apply,close=lambda:self.closed.append(True))
        self.reservations=ResourceReservationStore(self.sid)
        self.controller=MacroExpansionController(self.transport,expansion_scope(),self.sid,'b'*64,lambda *a,**kw:None,
            cost_supplier=lambda action,data,seconds:cost(self.sid,action,TARGETS[action][0],data['build_observation']['frame']),
            reservation_store=self.reservations)
        self.plan=SimpleNamespace(origin='model',session_id=self.sid,commander_id=COMMANDER,player_id=3,
            based_on_game_time_seconds=100.,expires_at_game_seconds=160.,tactical_tasks=(),runtime_task=None,
            macro_actions=('buildpower','budgetarmy'),macro_production=None,objective_region=None,plan_id='one')
        self.controller.refresh(sample())

    def dispatch(self,**kwargs):return self.controller.dispatch(self.plan,100.,effective_hash='b'*64,**kwargs)

    def test_once_bounded_and_ack_is_not_effect(self):
        first=self.dispatch();self.assertEqual(first,self.dispatch())
        self.assertEqual(self.calls[0][:2],(['buildpower','budgetarmy'],600))
        self.assertFalse(first['native_effect_verified']);self.assertTrue(self.controller.busy)
        self.assertEqual(self.controller.available_actions(100.),())
        self.controller.tick(141.);self.controller.tick(142.)
        self.assertEqual(len(self.calls),2);self.assertEqual(self.calls[-1][:2],([],1))
        self.assertEqual(self.controller.expansion_feedback()['release_reason'],'expired')

    def test_single_new_queue_releases_once_then_old_feedback_remains_separate(self):
        self.dispatch();self.controller.refresh(sample(frame=1502,queues=[(8,0)]))
        self.controller.tick(1502/15);self.controller.tick(1503/15)
        self.assertEqual(len(self.calls),2)
        self.assertEqual(self.controller.expansion_feedback()['observed_new_queue_count'],1)
        self.assertEqual(self.controller.expansion_feedback()['release_reason'],'queue_target_observed')

    def test_real_prerequisite_loss_releases_without_retry(self):
        self.dispatch();data=sample(frame=1502)
        data['dependency']['actions'][0]['prerequisite_met']=False
        self.controller.refresh(data);self.controller.tick(1502/15)
        self.assertEqual(self.controller.expansion_feedback()['release_reason'],'prerequisite_changed')
        self.assertEqual(self.calls[-1][:2],([],1))

    def test_new_unit_quantity_is_one_and_does_not_enter_old_three_type_tracker(self):
        self.controller.refresh(sample('producesickle'))
        self.plan.macro_actions=('producesickle',);self.plan.macro_production=SimpleNamespace(action='producesickle',additional_count=1)
        self.dispatch();self.controller.refresh(sample('producesickle',1502,queues=[(9,0)]))
        self.assertEqual(self.controller.expansion_feedback()['domain'],'production')
        self.assertNotIn('producesickle',self.controller.scope.production_counts)
        self.assertEqual(self.controller.expansion_scope.production_counts['producesickle'],(1,))

    def test_qualification_single_work_identity_quantity_and_pause_rejections(self):
        for change in (dict(macro_actions=('buildbarracks',)),dict(macro_actions=('buildpower','produceflak')),
                dict(macro_actions=('buildpower','producesickle')),dict(player_id=2),dict(session_id=str(uuid.uuid4())),
                dict(macro_production=SimpleNamespace(action='buildpower',additional_count=1))):
            original=copy.copy(self.plan);self.plan.__dict__.update(change)
            with self.subTest(change=change),self.assertRaises(ContractError):self.dispatch()
            self.plan=original
        with self.assertRaises(ContractError):self.dispatch(paused=True)
        self.assertEqual(self.calls,[])
        self.controller.refresh(sample('producesickle'));self.plan.macro_actions=('producesickle',)
        for quantity in (None,0,2,True):
            self.plan.macro_production=None if quantity is None else SimpleNamespace(action='producesickle',additional_count=quantity)
            with self.assertRaises(ContractError):self.dispatch()
        self.assertEqual(self.calls,[])

    def test_conflicting_id_and_unknown_delivery_cannot_resend(self):
        self.dispatch();self.plan.expires_at_game_seconds=150.
        with self.assertRaisesRegex(ContractError,'id_conflict'):self.dispatch()
        self.assertEqual(len(self.calls),1)
        self.setUp()
        def fail(*a):self.calls.append(a);raise RuntimeError('unknown')
        self.transport.apply=fail
        with self.assertRaisesRegex(ContractError,'outcome_unknown'):self.dispatch()
        with self.assertRaises(ContractError):self.dispatch()
        self.assertEqual(len(self.calls),1)

    def test_missing_native_window_terminal_and_stop_closes_transport(self):
        self.transport.apply=lambda *a:dict(seq=1)
        with self.assertRaisesRegex(ContractError,'outcome_unknown'):self.dispatch()
        self.assertTrue(self.controller.stopped);self.controller.stop();self.assertTrue(self.closed)

    def test_missing_cost_or_store_blocks_only_new_seven(self):
        self.controller.cost_supplier=None
        self.assertNotIn('buildpower',self.controller.available_actions(100.))
        self.assertEqual(self.controller.expansion_blocked['buildpower'],'blocked_native_cost_reservation_unverified')
        with self.assertRaisesRegex(ContractError,'blocked_native_cost_reservation_unverified'):self.dispatch()
        self.plan.macro_actions=('budgetarmy',)
        self.dispatch();self.assertEqual(self.calls[-1][0],['budgetarmy'])

    def test_native_flag_clear_does_not_auto_release_the_resource_reservation(self):
        self.dispatch();self.controller.refresh(sample(frame=1502,queues=[(8,0)]));self.controller.tick(1502/15)
        self.assertTrue(self.reservations.unresolved)
        feedback=self.controller.expansion_feedback()['resource_reservation']
        self.assertEqual(feedback['held_reservation_amount'],1000)
        self.assertFalse(feedback['preference_release_independently_verified'])
        self.assertNotIn('buildpower',self.controller.available_actions(1502/15))

    def test_native_unknown_retains_reservation_after_stop(self):
        self.transport.apply=lambda *a:(_ for _ in ()).throw(RuntimeError('unknown'))
        with self.assertRaisesRegex(ContractError,'outcome_unknown'):self.dispatch()
        self.controller.stop()
        row=next(iter(self.reservations.rows.values()));self.assertEqual(row['status'],'unknown')
        self.assertEqual(self.reservations.public(row['command_id'])['held_reservation_amount'],1000)
        self.assertEqual(self.controller.resource_feedback()['status'],'unknown')

    def test_feedback_compaction_keeps_only_public_resource_reservation(self):
        from .macro_expansion_feedback import compact_expansion_feedback
        self.dispatch();value=compact_expansion_feedback(self.controller.expansion_feedback(),100.)
        self.assertTrue(value['resource_reservation_verified'])
        self.assertEqual(value['resource_reservation']['held_reservation_amount'],1000)
        self.assertFalse(value['resource_reservation']['budget_hard_cap_verified'])

