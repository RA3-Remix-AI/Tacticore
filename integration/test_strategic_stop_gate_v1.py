"""Real Windows mutex/file ordering; artificial Native/provider, no game."""
import asyncio
from contextlib import contextmanager
import json
import multiprocessing as mp
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

from host_runtime.contracts import ContractError,SessionBinding
from host_runtime.desktop_backend import _atomic
from host_runtime.strategic_stop_gate_v1 import StrategicStopGateV1


def batch_worker(folder,run,binding,entered,resume,queue):
    gate=StrategicStopGateV1(run,SessionBinding.from_dict(binding),folder)
    with gate.admit():
        queue.put(('child_one',time.monotonic_ns()));entered.set()
        if not resume.wait(10):raise RuntimeError('fixture resume timeout')
        queue.put(('child_two_saw_stop',gate.committed()))
        queue.put(('child_two',time.monotonic_ns()))
    queue.put(('batch_done',time.monotonic_ns()))


def stop_worker(folder,run,binding,attempted,committed,queue):
    gate=StrategicStopGateV1(run,SessionBinding.from_dict(binding),folder)
    attempted.set();gate.publish_stop(_atomic)
    queue.put(('stop_committed',time.monotonic_ns()));committed.set()


@unittest.skipUnless(os.name=='nt','Native5 product requires Windows')
class StopGate(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.output=Path(self.temp.name);self.run=str(uuid.uuid4())
        self.binding=SessionBinding(1,str(uuid.uuid4()),3,str(uuid.uuid4()),123,
            '2026-10-30T00:00:00+00:00',str(uuid.uuid4()),'a'*64,'b'*64)
        self.gate=StrategicStopGateV1(self.run,self.binding,self.output)

    def test_real_crossprocess_stop_cannot_commit_between_admitted_children(self):
        context=mp.get_context('spawn');entered=context.Event();resume=context.Event()
        attempted=context.Event();committed=context.Event();queue=context.Queue()
        batch=context.Process(target=batch_worker,args=(str(self.output),self.run,self.binding.public(),entered,resume,queue))
        stop=context.Process(target=stop_worker,args=(str(self.output),self.run,self.binding.public(),attempted,committed,queue))
        try:
            batch.start();self.assertTrue(entered.wait(10));stop.start();self.assertTrue(attempted.wait(10))
            self.assertFalse(committed.wait(.05));resume.set()
            self.assertTrue(committed.wait(10));batch.join(10);stop.join(10)
            self.assertEqual((batch.exitcode,stop.exitcode),(0,0))
            events=dict(queue.get(timeout=3) for _ in range(5))
            self.assertFalse(events['child_two_saw_stop'])
            # Windows monotonic stamps can share a coarse clock tick; the
            # guarded actual stop-file read supplies the causal evidence.
            self.assertLessEqual(events['child_two'],events['stop_committed'])
            with self.assertRaisesRegex(ContractError,'already_committed'):
                with self.gate.admit():self.fail('new publication after durable STOP')
            record=json.loads(self.gate.path.read_bytes())
            self.assertEqual(record['binding_hash'],self.binding.binding_hash)
        finally:
            resume.set()
            for process in (batch,stop):
                if process.pid is not None:
                    process.join(2)
                    if process.is_alive():process.terminate();process.join(2)
            queue.close()

    def test_actual_controller_holds_one_admission_across_all_three_children(self):
        from test_strategic_unified_product_v5 import Dispatch
        fixture=Dispatch('runTest');fixture.setUp();self.addCleanup(fixture.doCleanups)
        held=[False];t=fixture.controller.transport
        @contextmanager
        def guard(**facts):
            with self.gate.admit():
                held[0]=True
                try:yield None
                finally:held[0]=False
        t.stop_batch=guard
        for method in ('manager','apply'):
            original=getattr(t,method)
            def call(*args,_original=original,**kwargs):
                self.assertTrue(held[0]);return _original(*args,**kwargs)
            setattr(t,method,call)
        plan=fixture.plan(['pauseconstruction','pauseproduction','scout','budgetarmy'])
        fixture.controller.dispatch(plan,101,effective_hash='a'*64)
        self.assertEqual(len(fixture.calls),3)
        self.gate.publish_stop(_atomic)
        with self.assertRaisesRegex(ContractError,'already_committed'):
            fixture.controller.dispatch(fixture.plan(['expand']),102,effective_hash='a'*64)
        self.assertEqual(len(fixture.calls),3)

    def test_provider_admitted_before_stop_may_finish_but_no_later_admission(self):
        from test_host_runtime_application import profile,draft
        from host_runtime.application import apply_commander_draft,observe_applied_backend
        events=[];calls=[]
        async def scenario():
            entered=asyncio.Event();resume=asyncio.Event()
            async def provider(context):calls.append(context);entered.set();await resume.wait();return {}
            backend=observe_applied_backend(provider,apply_commander_draft(profile(),draft()),
                event_sink=lambda kind,payload:events.append(kind),transport_mode='injected_transport',request_admission=self.gate.admit)
            pending=asyncio.create_task(backend({}));await entered.wait()
            self.gate.publish_stop(_atomic)
            with self.assertRaisesRegex(ContractError,'already_committed'):await backend({})
            resume.set();await pending
            self.assertEqual(backend.observation()['calls_started'],1)
        asyncio.run(scenario());self.assertEqual(len(calls),1)
        self.assertEqual(events.count('commander_model_call_started'),1)

    def test_wrong_binding_stop_is_not_ignored_or_treated_as_permission(self):
        _atomic(self.gate.path,dict(session_id=str(uuid.uuid4())))
        with self.assertRaisesRegex(ContractError,'binding_changed'):
            with self.gate.admit():self.fail('binding mismatch must fail closed')

    def test_actual_launch_record_routes_native5_stop_and_preserves_legacy_route(self):
        from host_runtime import desktop_backend as db
        from host_runtime.journal import CommandJournal
        # Synthetic admitted launch, halted before serialization/spawn. The
        # actual launch whitelist and actual run_stop routing remain in use.
        for protocol in (5,4):
            with self.subTest(protocol=protocol):
                folder=self.output/str(protocol);folder.mkdir();output=folder/'battle-host'
                run=str(uuid.uuid4());start=str(uuid.uuid4());stop=str(uuid.uuid4())
                session=folder/'session.json'
                session.write_text(json.dumps(dict(session_id=self.binding.session_id,pid=123,start_time=self.binding.game_process_start)))
                journal=CommandJournal(folder/'ledger.sqlite');self.addCleanup(journal.close)
                backend=db.DesktopBackend.__new__(db.DesktopBackend)
                backend.journal=journal;backend.state_dir=folder;backend.limits=SimpleNamespace(public=lambda:{})
                profile=dict(profile_id=self.binding.commander_id,revision=1,draft={},effective=dict(effective_hash='a'*64,model='synthetic'))
                admission=SimpleNamespace(admission_hash='c'*64,session={},capabilities=dict(native_macro=True,native_transport_protocol=protocol))
                class HaltBeforeSpawn(Exception):pass
                with patch.object(db,'require_macro_evidence',lambda _:None),patch.object(db,'_atomic',side_effect=HaltBeforeSpawn):
                    with self.assertRaises(HaltBeforeSpawn):
                        backend._dispatch_launch(profile,start,run,self.binding,admission,object(),0)
                self.assertEqual(journal.get_command(run,start)['payload']['capabilities']['native_transport_protocol'],protocol)
                row=dict(run_id=run,binding_json=json.dumps(self.binding.public()),session_path=str(session),output_path=str(output),request_id=start)
                backend._launch=lambda _:row;backend._cancel_reserved_launch=lambda *a:False
                backend._status=lambda _:dict(state='synthetic_status')
                original=StrategicStopGateV1.publish_stop
                with patch.object(StrategicStopGateV1,'publish_stop',autospec=True,side_effect=original) as publish:
                    backend.run_stop(dict(run_id=run,session_id=self.binding.session_id),stop)
                    self.assertEqual(publish.call_count,int(protocol==5))
                value=json.loads((output/'stop.json').read_bytes())
                self.assertEqual(value['session_id'],self.binding.session_id)
                if protocol==5:
                    self.assertEqual(value['run_id'],run)
                    self.assertEqual(value['binding_hash'],self.binding.binding_hash)
                    self.assertEqual(value['source'],'strategic_stop_admission_barrier_v1')
                else:self.assertEqual(set(value),{'session_id'})
                self.assertEqual(journal.get_command(run,stop)['status'],'completed')

if __name__=='__main__':unittest.main()
