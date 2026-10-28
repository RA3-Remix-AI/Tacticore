"""Synthetic native executor boundary tests; no game/process/model access."""
from pathlib import Path
import ctypes
from ctypes import wintypes
from datetime import datetime
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

from host_runtime.capabilities import CapabilityCatalog, VerifiedGrant
from host_runtime.contracts import SessionBinding, canonical_json
from host_runtime.coordinator import HostCoordinator
from host_runtime.gateway import AdmissionRefused, ExecutionGateway
from host_runtime.journal import CommandJournal
from host_runtime.limits import ExecutionLimits
from host_runtime.native_adapters import AdmissionSnapshot, ExistingProductionChecks, PersistentProductionAdapter
from host_runtime.orchestration import OrchestrationConfig


def uid():return str(uuid.uuid4())


class Checks:
    def __init__(self):
        self.calls=[];self.reason=None;self.paused=False;self.native_last=20;self.binary="d"*64
    def admit(self,executor,binding,operation):
        self.calls.append(operation)
        if self.reason:raise AdmissionRefused(self.reason)
        return AdmissionSnapshot(100,self.paused,self.native_last,self.binary)
    def validate(self,wire,executor,snapshot):
        if set(wire)!={"session_id","player_id","commander_id","command_id","task_id","seq","unit","budget","reserve","expires_frame"}:raise ValueError("fields")
        if not snapshot.game_frame<=wire["expires_frame"]<=snapshot.game_frame+900:raise ValueError("expiry")
        return dict(wire)


class Executor:
    def __init__(self,path,binding):
        self.session_path=path;self.session_bytes=path.read_bytes()
        self.session={"session_id":binding.session_id,"pid":binding.game_process_id,
                      "start_time":binding.game_process_start,"mod_sha256":binding.mod_sha256}
        self.commander_id=binding.commander_id;self.reserve_floor=1000;self.total_budget=5000
        self.calls=[];self.mode="queued";self.stops=0;self.bad_status=False;self.ledger=[]
    def submit(self,wire):
        self.calls.append(dict(wire))
        if self.mode=="error":raise OSError("must never leak private exception")
        if self.mode=="unknown":return dict(status="unknown",reason_code="native_timeout",task_id=wire["task_id"])
        if self.mode=="reject":return dict(status="no_dispatch_rejected",accepted=False,started=False,completed=False,reason_code="game_paused",task_id=wire["task_id"])
        result=dict(command_id=wire["command_id"],task_id=wire["task_id"],seq=wire["seq"],unit=wire["unit"],status="queued",accepted=True,started=True,completed=False,queue_id=11,
                    reason_code="native_0",object_id=None,cost=85,paid=0,paid_verified=False,created=False,completion_observed=False,live_samples=0,payment_error=0,enqueue_frame=100,completion_frame=None,queue_preserved=True)
        if self.mode in ("completed","unpaid"):
            result.update(status="completed",completed=True,paid=85,paid_verified=True,created=True,completion_observed=True,object_id=801,live_samples=2,completion_frame=120)
            if self.mode=="unpaid":result["paid_verified"]=False
        if self.mode=="wrong_id":result["command_id"]=uid()
        if self.mode=="wrong_seq":result["seq"]+=1
        self.ledger.append(dict(result))
        return result
    def status(self):
        ledger=[dict(row) for row in self.ledger]
        if self.mode=="completed":
            for row in ledger:row.update(status="completed",completed=True,paid=85,paid_verified=True,created=True,completion_observed=True,object_id=801,live_samples=2,completion_frame=120)
        return dict(session_id="wrong" if self.bad_status else self.session["session_id"],player_id=3,commander_id=self.commander_id,personality_binding_verified=True,state="running",native_phase=1,native_error=0,restore_mask=0,active_callbacks=0,spent_committed=85,total_budget=5000,last_seq=21,local_error=None,ledger=ledger)
    def stop(self):
        self.stops+=1;out=self.status();out.update(state="stopped",native_phase=2,restore_mask=31)
        if self.mode=="stop_unknown":out["active_callbacks"]=1
        return out


class NativeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        self.binding=SessionBinding(1,uid(),3,uid(),1234,"2026-10-26T00:00:00+00:00",uid(),"a"*64,"b"*64)
        self.run=uid();self.task=uid();self.journal=CommandJournal(root/"ledger.sqlite");self.limits=ExecutionLimits(5000,1000,1000)
        path=root/"session.json";path.write_text("immutable-original",encoding="utf-8")
        self.executor=Executor(path,self.binding);self.checks=Checks();self.catalog=self.catalog_for()
    def tearDown(self):self.journal.close();self.tmp.cleanup()
    def catalog_for(self,unit="conscript",**changes):
        capability="production.infantry" if unit=="conscript" else "production.anti_air"
        constraints=dict(runtime_family="production_persistent_v2",executor_directory="production/persistent/bin-v2",allowed_units=[unit],persistent_units_verified=[unit],execution_ready=True,executor_sha256="d"*64,evidence_id="proof")
        constraints.update(changes)
        grant=VerifiedGrant(capability,"proof","c"*64,"d"*64,"fixture verified scope",canonical_json(constraints))
        return CapabilityCatalog.verify(self.binding,[grant],lambda value,binding:value)
    def adapter(self,catalog=None):
        return PersistentProductionAdapter(self.executor,self.binding,run_id=self.run,journal=self.journal,capabilities=self.catalog if catalog is None else catalog,execution_limits=self.limits,checks=self.checks)
    def gateway(self,adapter=None,catalog=None):
        catalog=self.catalog if catalog is None else catalog
        return ExecutionGateway(self.run,self.binding,self.journal,catalog,adapter or self.adapter(catalog))
    def payload(self,**changes):
        value=dict(unit="conscript",task_id=self.task,budget=85,reserve=1000,expires_frame=500)
        value.update(changes);return value

    def test_exact_wire_and_persistent_sequence_not_repeated(self):
        gate=self.gateway();request=uid();out=gate.submit(request,"produce",self.payload())
        self.assertEqual(out["status"],"accepted")
        wire=self.executor.calls[0]
        self.assertEqual(wire["seq"],21);self.assertEqual(wire["command_id"],out["command_id"])
        self.assertEqual(wire["task_id"],self.task);self.assertEqual(wire["player_id"],3)
        self.assertEqual(out["receipt"]["facts"]["source"],"injected_test_adapter")
        gate.submit(request,"produce",self.payload());self.assertEqual(len(self.executor.calls),1)
        # New adapter instances still get a monotone sequence from the database.
        again=self.gateway(self.adapter()).submit(uid(),"produce",self.payload())
        self.assertEqual(again["status"],"accepted");self.assertEqual(self.executor.calls[-1]["seq"],22)

    def test_sequence_survives_connection_reopen(self):
        self.gateway().submit(uid(),"produce",self.payload())
        database=Path(self.tmp.name)/"ledger.sqlite";self.journal.close();self.journal=CommandJournal(database)
        self.gateway().submit(uid(),"produce",self.payload())
        self.assertEqual([wire["seq"] for wire in self.executor.calls],[21,22])

    def test_raw_completion_requires_payment_create_identity_and_live_samples(self):
        self.executor.mode="completed";out=self.gateway().submit(uid(),"produce",self.payload())
        self.assertEqual(out["status"],"completed")
        self.assertFalse(out["receipt"]["facts"]["actor_generation_verified"])
        self.assertNotIn("actor_generation",out["receipt"]["facts"])
        self.executor.mode="unpaid";out=self.gateway().submit(uid(),"produce",self.payload())
        self.assertEqual(out["status"],"uncertain")

    def test_unknown_or_wrong_identity_never_retries(self):
        for mode in ("unknown","wrong_id","wrong_seq","error"):
            with self.subTest(mode=mode):
                self.executor.mode=mode;request=uid();gate=self.gateway();before=len(self.executor.calls)
                out=gate.submit(request,"produce",self.payload());self.assertEqual(out["status"],"uncertain")
                gate.submit(request,"produce",self.payload());self.assertEqual(len(self.executor.calls),before+1)
        self.assertNotIn("private exception",str(self.journal.events(self.run)))

    def test_definitive_native_refusal_is_rejected(self):
        self.executor.mode="reject";out=self.gateway().submit(uid(),"produce",self.payload())
        self.assertEqual(out["status"],"rejected")
        self.assertFalse(out["receipt"]["facts"]["native_dispatch_attempted"])

    def test_pause_changed_process_and_changed_session_refuse_before_submit(self):
        self.checks.paused=True;out=self.gateway().submit(uid(),"produce",self.payload())
        self.assertEqual(out["status"],"rejected");self.assertEqual(self.executor.calls,[])
        self.checks.paused=False;self.checks.reason="production_process_start_changed"
        out=self.gateway().submit(uid(),"produce",self.payload());self.assertEqual(out["status"],"rejected")
        self.checks.reason=None;self.executor.session_path.write_text("changed",encoding="utf-8")
        out=self.gateway().submit(uid(),"produce",self.payload());self.assertEqual(out["status"],"rejected")
        self.assertEqual(self.executor.calls,[])

    def test_scope_empty_not_ready_wrong_runtime_and_one_shot_flak_refused(self):
        bad=[self.catalog_for(execution_ready=False),self.catalog_for(runtime_family="production_one_shot",persistent_units_verified=[]),self.catalog_for(allowed_units=[])]
        empty=VerifiedGrant("production.infantry","proof","c"*64,"d"*64,"descriptive text only")
        bad.append(CapabilityCatalog.verify(self.binding,[empty],lambda value,binding:value))
        for catalog in bad:
            out=self.gateway(catalog=catalog).submit(uid(),"produce",self.payload())
            self.assertEqual(out["status"],"rejected")
        flak=self.catalog_for(unit="flak",runtime_family="production_one_shot",persistent_units_verified=[],execution_ready=False)
        out=self.gateway(catalog=flak).submit(uid(),"produce",self.payload(unit="flak",budget=220))
        self.assertEqual(out["status"],"rejected");self.assertEqual(self.executor.calls,[])

    def test_actual_executor_binary_must_match_verified_grant(self):
        self.checks.binary="e"*64
        out=self.gateway().submit(uid(),"produce",self.payload())
        self.assertEqual(out["status"],"rejected");self.assertEqual(self.executor.calls,[])

    def test_default_checks_reject_fake_executor_before_loading_native_modules(self):
        with patch("host_runtime.native_adapters._legacy_module",side_effect=AssertionError("must remain lazy")) as load:
            with self.assertRaisesRegex(AdmissionRefused,"existing_production_executor_required"):
                ExistingProductionChecks().admit(self.executor,self.binding,"produce")
            load.assert_not_called()

    def test_settlement_cleanup_checks_attached_identity_without_destroyed_owner_reads(self):
        # This exercises the default admission, replacing only OS/kernel IO.
        # The source-module/class fence remains active, unlike injected Checks.
        from host_runtime import native_adapters as module
        owner=ModuleType('fixture_original_executor');owner.__file__=str(module.CLIENT)
        original_type=type('ProductionExecutor',(Executor,),{'__module__':owner.__name__})
        executor=original_type(self.executor.session_path,self.binding)
        expected=int(datetime.fromisoformat(self.binding.game_process_start).timestamp()*10000000)+116444736000000000
        words=lambda value:tuple(uuid.UUID(value).bytes_le)
        executor.shared=SimpleNamespace(pid=1234,session=words(self.binding.session_id),commander=words(self.binding.commander_id),start_high=expected>>32,start_low=expected&0xffffffff,owner=9,personality=16,personality_id=17,last_seq=20)
        executor.owner=9;executor.native={'personality_wrapper':'0x10','instance_id':'0x11'}
        executor.binding={'personality_binding_verified':True,'commander_id':self.binding.commander_id}
        executor.package=Path(self.tmp.name)/'package';executor.host=SimpleNamespace(poll=lambda:None)
        executor.memory=SimpleNamespace(pid=1234,path=Path('game.exe'),handle=1,u32=lambda address:(_ for _ in ()).throw(AssertionError('destroyed game object read')))
        executor._verify_binding=lambda:(_ for _ in ()).throw(AssertionError('destroyed owner read'))
        def process_times(handle,*pointers):
            pointers[0]._obj.dwHighDateTime=expected>>32;pointers[0]._obj.dwLowDateTime=expected&0xffffffff;return True
        class Function:
            def __init__(self,call):self.call=call
            def __call__(self,*args):return self.call(*args)
        def process_exit(handle,pointer):pointer._obj.value=0;return True
        kernel=SimpleNamespace(GetProcessTimes=process_times,GetExitCodeProcess=Function(process_exit))
        legacy=SimpleNamespace(c=ctypes,w=wintypes,k=kernel,uuid_words=words,verify_session_package=lambda session:executor.package,NATIVE_BIN=Path('native'))
        digest=lambda path:'a'*64 if Path(path)==Path('game.exe') else 'd'*64
        with patch.dict(sys.modules,{owner.__name__:owner}),patch.object(module,'_legacy_module',return_value=legacy),patch.object(module,'_digest',side_effect=digest):
            adapter=PersistentProductionAdapter(executor,self.binding,run_id=self.run,journal=self.journal,capabilities=self.catalog,execution_limits=self.limits)
            gate=self.gateway(adapter)
            outcome=gate.submit(uid(),'query_status',{})
            self.assertEqual(outcome['status'],'completed',outcome)
            self.assertEqual(gate.submit(uid(),'produce',self.payload())['status'],'rejected')
            # A process start or session mismatch must still prevent cleanup.
            executor.shared.start_low+=1
            self.assertEqual(gate.submit(uid(),'stop',{})['status'],'rejected');self.assertEqual(executor.stops,0)
            executor.shared.start_low-=1;executor.shared.session=words(uid())
            self.assertEqual(gate.submit(uid(),'stop',{})['status'],'rejected');self.assertEqual(executor.stops,0)
            executor.shared.session=words(self.binding.session_id)
            executor.mode='stop_unknown'
            self.assertEqual(gate.submit(uid(),'stop',{})['status'],'uncertain');self.assertEqual(executor.stops,1)
            executor.mode='queued'
            self.assertEqual(gate.submit(uid(),'stop',{})['status'],'released');self.assertEqual(executor.stops,2)

    def test_explicit_evidence_budget_scope_is_enforced(self):
        limited=self.catalog_for(max_budget=50)
        self.assertEqual(self.gateway(catalog=limited).submit(uid(),"produce",self.payload())["status"],"rejected")
        reserve=self.catalog_for(reserve_floor=1500)
        self.assertEqual(self.gateway(catalog=reserve).submit(uid(),"produce",self.payload())["status"],"rejected")
        self.assertEqual(self.executor.calls,[])

    def test_invalid_fields_budgets_and_expiry_are_not_dispatched(self):
        cases=[self.payload(budget=0),self.payload(reserve=999),self.payload(expires_frame=99),self.payload(expires_frame=1001),self.payload(seq=1)]
        for value in cases:
            self.assertEqual(self.gateway().submit(uid(),"produce",value)["status"],"rejected")
        self.assertEqual(self.executor.calls,[])

    def test_hard_execution_limits_are_not_changed_by_soft_configuration(self):
        self.executor.total_budget=6000
        self.assertEqual(self.gateway().submit(uid(),"produce",self.payload())["status"],"rejected")
        self.executor.total_budget=5000;self.executor.reserve_floor=500
        self.assertEqual(self.gateway().submit(uid(),"produce",self.payload())["status"],"rejected")
        self.executor.reserve_floor=1000;self.limits=ExecutionLimits(5000,1000,84)
        self.assertEqual(self.gateway().submit(uid(),"produce",self.payload())["status"],"rejected")
        self.assertEqual(self.executor.calls,[])

    def test_query_and_stop_have_separate_meanings_and_verify_release(self):
        gate=self.gateway();query=gate.submit(uid(),"query_status",{})
        self.assertEqual(query["status"],"completed");self.assertTrue(query["receipt"]["facts"]["query_only"])
        self.assertEqual(self.executor.calls,[])
        stopped=gate.submit(uid(),"stop",{"scope":"production"})
        self.assertEqual(stopped["status"],"released")
        self.assertFalse(stopped["receipt"]["facts"]["mission_effect_verified"])
        self.executor.mode="stop_unknown"
        self.assertEqual(gate.submit(uid(),"stop",{})["status"],"uncertain")

    def test_wrong_query_identity_is_unknown_and_tactical_operations_are_refused(self):
        self.executor.bad_status=True
        self.assertEqual(self.gateway().submit(uid(),"query_status",{})["status"],"uncertain")
        # Direct adapter admission rejects tactical operations even if a caller
        # presents an unrelated capability; no fake reserve/commit implementation.
        for operation in ("reserve","commit","return"):
            command=dict(run_id=self.run,session_id=self.binding.session_id,commander_id=self.binding.commander_id,
                         player_id=3,request_id=uid(),command_id=uid(),operation=operation,payload={})
            with self.assertRaisesRegex(AdmissionRefused,"operation_unsupported"):
                self.adapter().preflight(command,self.binding)
        self.assertEqual(self.executor.calls,[])

    def test_coordinator_gateway_existing_protocol_production_integration(self):
        gate=self.gateway();coordinator=HostCoordinator(gate,config=OrchestrationConfig(production_gap_frames=0),execution_limits=self.limits)
        coordinator.create_task(self.task)
        observation=dict(session_id=self.binding.session_id,session_binding_hash=self.binding.binding_hash,
            game_frame=100,monotonic_ms=0,source="simulated",own_view_verified=True,anchors=[[0,0,0]],actors=[],
            contacts=[dict(contact_id="target",object_id=900,owner_player_id=4,relation="enemy",currently_visible=True,observed_frame=100,xyz=[600,0,0],hp=1000,role="structure",type_hash="0x123",template="Barracks")],
            plan=dict(session_id=self.binding.session_id,plan_id=uid(),task_id=self.task,generation=1,expires_frame=10000,valid_until_monotonic_ms=100000))
        result=coordinator.tick(observation)
        self.assertEqual(result["command_results"][0]["status"],"accepted")
        self.assertEqual(len(self.executor.calls),1)
        self.assertEqual(set(self.executor.calls[0]),{"session_id","player_id","commander_id","command_id","task_id","seq","unit","budget","reserve","expires_frame"})
        self.assertEqual(self.executor.calls[0]["budget"],85)
        self.assertEqual(self.executor.calls[0]["reserve"],1000)
        # The next production role is refused because the real catalog does not
        # establish persistent Flak, rather than inventing tactical success.
        observation.update(game_frame=101,monotonic_ms=10)
        result=coordinator.tick(observation)
        self.assertEqual(result["command_results"][0]["status"],"rejected")
        self.assertEqual(len(self.executor.calls),1)

    def test_scope_metadata_are_validated_but_not_sent_to_legacy_wire(self):
        payload=self.payload(generation=1,lease_id=uid(),plan_id=uid(),observed_frame=100,monotonic_ms=0,max_cost=85)
        self.assertEqual(self.gateway().submit(uid(),"produce",payload)["status"],"accepted")
        self.assertNotIn("generation",self.executor.calls[-1])
        payload["generation"]=True
        self.assertEqual(self.gateway().submit(uid(),"produce",payload)["status"],"rejected")
        self.assertEqual(len(self.executor.calls),1)

    def test_later_native_query_reuses_original_sequence_and_identity(self):
        gate=self.gateway();request=uid();original=gate.submit(request,"produce",self.payload())
        self.executor.mode="completed"
        query=gate.submit(uid(),"query_status",{"production_request_id":request})
        outcome=query["receipt"]["facts"]["production_result"]
        self.assertEqual(outcome["command_id"],original["command_id"])
        self.assertEqual(outcome["status"],"completed")
        self.assertEqual(outcome["facts"]["seq"],21)
        self.assertEqual(len(self.executor.calls),1)


if __name__=="__main__":unittest.main()
