"""Complete synthetic transport sequence, clocks and negative boundaries."""
import unittest

from host_runtime.orchestration import MissionOrchestrator, OrchestrationConfig

BINDING=dict(run_id="run-one",session_id="session-one",commander_id="commander-one",player_id=3)


def observation(frame=100,wall=0,**changes):
    out=dict(session_id=BINDING["session_id"],game_frame=frame,monotonic_ms=wall,
             own_view_verified=True,anchors=[[0,0,0]],
             contacts=[dict(contact_id="target",object_id=900,owner_player_id=4,
                            relation="enemy",currently_visible=True,observed_frame=frame,
                            xyz=[600,0,0],hp=1000,role="structure",type_hash="0x123",template="Barracks")],
             actors=[],receipts=[],plan=dict(session_id=BINDING["session_id"],plan_id="plan-one",task_id="task",generation=1,expires_frame=10000,valid_until_monotonic_ms=100000))
    out.update(changes);return out


def receipt(intent,status,**changes):
    out={k:intent[k] for k in ("request_id","session_id","task_id","generation")}
    out.update(status=status,**changes);return out


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.machine=MissionOrchestrator(BINDING,OrchestrationConfig(production_gap_frames=0))

    def ready(self):
        m=self.machine
        def observed(frame=100,wall=0,**kwargs):
            row=observation(frame+getattr(self,"frame_offset",0),wall+getattr(self,"wall_offset",0),**kwargs)
            row["plan"].update(task_id=m.task_id,generation=m.generation)
            return row
        first=m.advance(observed()).intents[0]
        a=dict(role="infantry",object_id=801,generation=11,owner_player_id=3,alive=True,ground_ready=True,held=False)
        b=dict(role="anti_air",object_id=802,generation=12,owner_player_id=3,alive=True,ground_ready=True,held=False)
        ra=receipt(first,"completed",enqueue_frame=100,object_id=801,actor_generation=11,paid_verified=True,created=True,paid=85)
        second=m.advance(observed(101,10,receipts=[ra],actors=[a])).intents[0]
        rb=receipt(second,"completed",enqueue_frame=101,object_id=802,actor_generation=12,paid_verified=True,created=True,paid=220)
        reserve=m.advance(observed(102,20,receipts=[rb],actors=[a,b])).intents[0]
        for actor in (a,b):actor.update(held=True,ready=True,lease_id=m.lease_id)
        rr=receipt(reserve,"accepted",lease_issued_frame=102)
        return a,b,rr

    def commit(self):
        a,b,rr=self.ready()
        row=observation(103+getattr(self,"frame_offset",0),30+getattr(self,"wall_offset",0),receipts=[rr],actors=[a,b])
        row["plan"].update(task_id=self.machine.task_id,generation=self.machine.generation)
        result=self.machine.advance(row)
        return a,b,result.intents[0]

    def test_no_target_never_spends_or_borrows_even_after_timeout(self):
        self.assertEqual(self.machine.advance(observation(contacts=[])).intents,())
        result=self.machine.advance(observation(200,60000,contacts=[]))
        self.assertEqual(result.state,"failed");self.assertEqual(result.reason_code,"opportunity_timeout")
        self.assertEqual(result.intents,())

    def test_complete_paid_ready_commit_effect_home_release_sequence(self):
        a,b,commit=self.commit()
        self.assertEqual(commit["operation"],"commit")
        self.assertEqual(commit["payload"]["reserve_deadline_frame"],552)
        self.assertFalse(commit["authority_granted"])
        accepted=receipt(commit,"accepted")
        self.assertEqual(self.machine.advance(observation(104,40,receipts=[accepted],actors=[a,b])).state,"executing")
        for actor in (a,b):actor["held"]=False
        terminal=dict(session_id=BINDING["session_id"],lease_id=self.machine.lease_id,effect_verified=True,home_verified=True,release_verified=True)
        result=self.machine.advance(observation(150,100,actors=[a,b],terminal=terminal))
        self.assertEqual(result.state,"completed")
        self.assertEqual(self.machine.advance(observation(151,101)).intents,())

    def test_unknown_commit_is_not_resent(self):
        a,b,commit=self.commit()
        out=self.machine.advance(observation(104,40,receipts=[receipt(commit,"uncertain")],actors=[a,b]))
        self.assertEqual(out.state,"uncertain")
        self.assertEqual([i["operation"] for i in out.intents],["query_status"])
        again=self.machine.advance(observation(105,60,actors=[a,b]))
        self.assertEqual(again.state,"uncertain");self.assertEqual(again.intents,())

    def test_commit_ack_timeout_uses_wall_clock_while_paused(self):
        a,b,_=self.commit()
        out=self.machine.advance(observation(103,5030,actors=[a,b],paused=True))
        self.assertEqual(out.state,"uncertain")
        self.assertEqual(out.reason_code,"command_ack_timeout")

    def test_rejected_commit_requests_stop_and_awaits_release(self):
        a,b,commit=self.commit()
        out=self.machine.advance(observation(104,40,receipts=[receipt(commit,"rejected")],actors=[a,b]))
        self.assertEqual(out.state,"returning")
        stop=out.intents[0];self.assertEqual(stop["operation"],"stop")
        for actor in (a,b):actor["held"]=False
        terminal=dict(session_id=BINDING["session_id"],lease_id=self.machine.lease_id,release_verified=True)
        out=self.machine.advance(observation(105,50,receipts=[receipt(stop,"released")],actors=[a,b],terminal=terminal))
        self.assertEqual(out.state,"failed")

    def test_actor_generation_reuse_does_not_commit(self):
        a,b,rr=self.ready();b["generation"]+=1
        out=self.machine.advance(observation(103,30,receipts=[rr],actors=[a,b]))
        self.assertEqual(out.state,"uncertain")
        self.assertEqual(out.reason_code,"actor_identity_reused")
        self.assertNotIn("commit",[i["operation"] for i in out.intents])

    def test_spawn_transition_waits_for_ground_before_reserve(self):
        first=self.machine.advance(observation()).intents[0]
        ra=receipt(first,"completed",enqueue_frame=100,object_id=801,actor_generation=1,paid_verified=True,created=True,paid=85)
        actor=dict(role="infantry",object_id=801,generation=1,owner_player_id=3,ground_ready=False)
        out=self.machine.advance(observation(101,10,receipts=[ra],actors=[actor]))
        self.assertEqual(out.state,"producing")
        self.assertTrue(any(e["reason_code"]=="spawn_transition" for e in out.events))
        self.assertNotIn("reserve",[i["operation"] for i in out.intents])

    def test_stale_plan_never_starts_production(self):
        row=observation();row["plan"]["valid_until_monotonic_ms"]=0
        out=self.machine.advance(row)
        self.assertEqual(out.state,"waiting_opportunity");self.assertEqual(out.intents,())
        self.assertTrue(any(e["reason_code"]=="plan_stale_or_wrong_binding" for e in out.events))

    def test_current_opportunity_loss_aborts_before_commit(self):
        a,b,rr=self.ready()
        out=self.machine.advance(observation(103,30,receipts=[rr],actors=[a,b],contacts=[]))
        self.assertEqual(out.state,"returning")
        self.assertEqual(out.reason_code,"opportunity_lost")
        self.assertEqual([i["operation"] for i in out.intents],["stop"])

    def test_unpublished_reserve_expiry_is_not_renewed_by_new_plan(self):
        a,b,rr=self.ready()
        out=self.machine.advance(observation(552,30,receipts=[rr],actors=[a,b]))
        self.assertEqual(out.state,"returning")
        self.assertEqual(out.reason_code,"precommit_deadline")

    def test_session_change_never_issues_mutating_intent(self):
        self.machine.advance(observation())
        out=self.machine.advance(observation(101,10,session_id="new-session"))
        self.assertEqual(out.state,"uncertain")
        self.assertEqual([i["operation"] for i in out.intents],["query_status"])

    def test_rejected_production_does_not_borrow(self):
        first=self.machine.advance(observation()).intents[0]
        out=self.machine.advance(observation(101,10,receipts=[receipt(first,"rejected")]))
        self.assertEqual(out.state,"failed");self.assertEqual(out.reason_code,"production_rejected")
        self.assertEqual(out.intents,())

    def test_user_stop_waits_for_verified_release(self):
        a,b,rr=self.ready()
        out=self.machine.advance(observation(103,30,receipts=[rr],actors=[a,b],stop_requested=True))
        self.assertEqual(out.state,"returning")
        out=self.machine.advance(observation(104,40,actors=[a,b],terminal={"release_verified":True}))
        self.assertEqual(out.state,"returning")

    def test_clock_reversal_rejected(self):
        self.machine.advance(observation())
        with self.assertRaisesRegex(ValueError,"clock_moved_backwards"):
            self.machine.advance(observation(99,10))

    def test_release_without_effect_or_home_is_not_success(self):
        a,b,commit=self.commit()
        self.machine.advance(observation(104,40,receipts=[receipt(commit,"accepted")],actors=[a,b]))
        for actor in (a,b):actor["held"]=False
        terminal=dict(session_id=BINDING["session_id"],lease_id=self.machine.lease_id,release_verified=True)
        out=self.machine.advance(observation(105,50,actors=[a,b],terminal=terminal))
        self.assertEqual(out.state,"failed")

    def test_receipt_regression_and_identity_change_are_uncertain(self):
        first=self.machine.advance(observation()).intents[0]
        accepted=receipt(first,"started",enqueue_frame=100)
        self.machine.advance(observation(101,10,receipts=[accepted]))
        out=self.machine.advance(observation(102,20,receipts=[receipt(first,"accepted",enqueue_frame=100)]))
        self.assertEqual(out.reason_code,"receipt_regressed")
        other=MissionOrchestrator(BINDING,OrchestrationConfig(production_gap_frames=0))
        first=other.advance(observation()).intents[0]
        other.advance(observation(101,10,receipts=[receipt(first,"accepted",enqueue_frame=100)]))
        out=other.advance(observation(102,20,receipts=[receipt(first,"started",enqueue_frame=99)]))
        self.assertEqual(out.reason_code,"receipt_identity_changed")

    def test_task_b_runs_after_a_verified_release(self):
        a,b,commit=self.commit()
        self.machine.advance(observation(104,40,receipts=[receipt(commit,"accepted")],actors=[a,b]))
        for actor in (a,b):actor["held"]=False
        terminal=dict(session_id=BINDING["session_id"],lease_id=self.machine.lease_id,effect_verified=True,home_verified=True,release_verified=True)
        self.assertEqual(self.machine.advance(observation(150,100,actors=[a,b],terminal=terminal)).state,"completed")
        task_b=MissionOrchestrator(BINDING,OrchestrationConfig(production_gap_frames=0),task_id="task-b",generation=2)
        row=observation(151,110);row["plan"].update(task_id="task-b",generation=2)
        first_b=task_b.advance(row).intents[0]
        self.assertEqual(first_b["operation"],"produce")
        self.assertNotIn(first_b["request_id"],self.machine.public()["issued_request_ids"])
        self.assertNotEqual(task_b.lease_id,self.machine.lease_id)
        # A fresh task instance in the same session can complete the whole chain;
        # no attempted-once flag or prior task receipt authorizes task B.
        self.machine=MissionOrchestrator(BINDING,OrchestrationConfig(production_gap_frames=0),task_id="task-b",generation=2)
        self.frame_offset,self.wall_offset=200,1000
        a,b,commit_b=self.commit()
        self.machine.advance(observation(304,1040,receipts=[receipt(commit_b,"accepted")],actors=[a,b]))
        for actor in (a,b):actor["held"]=False
        terminal.update(lease_id=self.machine.lease_id)
        self.assertEqual(self.machine.advance(observation(350,1100,actors=[a,b],terminal=terminal)).state,"completed")

    def test_production_gap_and_unpaid_receipt_do_not_borrow(self):
        machine=MissionOrchestrator(BINDING)
        first=machine.advance(observation()).intents[0]
        self.assertEqual(machine.advance(observation(101,10,receipts=[receipt(first,"accepted",enqueue_frame=100)])).intents,())
        out=machine.advance(observation(250,20))
        self.assertEqual([i["operation"] for i in out.intents],["produce"])
        machine=MissionOrchestrator(BINDING)
        first=machine.advance(observation()).intents[0]
        bad=receipt(first,"completed",object_id=801,actor_generation=1,paid_verified=False,created=True,paid=85)
        out=machine.advance(observation(101,10,receipts=[bad]))
        self.assertEqual(out.state,"failed")
        self.assertEqual(out.reason_code,"production_payment_unverified")


if __name__=="__main__":unittest.main()
