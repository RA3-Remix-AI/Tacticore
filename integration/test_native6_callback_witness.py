"""Actual product reader/witness with simulated publications, no game/OS/model."""
import copy
import ctypes as c
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
import sys
import struct
import threading
from unittest.mock import patch

from host_runtime import native6_observation as subject
from host_runtime.native6_callback_snapshot import completed_snapshot
from host_runtime.contracts import ContractError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'native-ai'))
# Load the admitted SDK declarations without initializing its Windows Probe.
import ast
tree=ast.parse((ROOT/'native-ai/strategic-portable-runtime-v6/client.py').read_text(encoding='utf-8'))
ns=dict(c=c,u32=c.c_uint32,u64=c.c_uint64)
nodes=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name in ('Binding','GateStatus','Shared')]
exec(compile(ast.Module(body=nodes,type_ignores=[]),'<actual Native6 SDK layouts>','exec'),ns)
Shared=ns['Shared']

class Witness(unittest.TestCase):
    def fixture(self):
        now=[0];state={key:0 for key in subject.CALLBACK_CONTROL_FIELDS}
        state.update(raw_binding={'game':123},magic=0x53434736,version=6,size=4592,phase=1,
            lease_held=1,hook_held=1,gates=[dict(phase=0),dict(phase=0)],active=0,last_frame=100,callback_serial=5)
        original=copy.deepcopy(state)
        def wait(seconds):now[0]+=int(seconds*1e9);state['callback_serial']+=1
        clock=SimpleNamespace(monotonic_ns=lambda:now[0],sleep=wait)
        transport=SimpleNamespace(completed_native_status=lambda:copy.deepcopy(state))
        return state,original,clock,transport
    def test_requires_strictly_later_completed_callback(self):
        state,initial,clock,transport=self.fixture()
        with patch.object(subject,'time',clock):result=subject._post_tail_callback_witness(transport,initial,100,0)
        self.assertEqual((result['anchor_serial'],result['later_serial']),(5,6))
        self.assertFalse(result['native_guard_side_store_rechecked'])
    def test_old_callback_and_busy_copies_cannot_be_completion(self):
        for busy in (False,True):
            state,initial,clock,transport=self.fixture()
            clock.sleep=lambda seconds:setattr(clock,'elapsed',getattr(clock,'elapsed',0)+1)
            if busy:transport.completed_native_status=lambda:None
            with patch.object(subject,'time',clock),self.assertRaises(ValueError):
                subject._post_tail_callback_witness(transport,initial,100,0)
    def test_late_callback_identity_error_or_regression_is_rejected(self):
        for change in (dict(phase=5,error=34),dict(callback_serial=4),dict(raw_binding={'game':124})):
            state,initial,clock,transport=self.fixture()
            clock.sleep=lambda seconds:state.update(change)
            with patch.object(subject,'time',clock),self.assertRaises(ContractError):
                subject._post_tail_callback_witness(transport,initial,100,0)
    def test_full_wait_counts_toward_original_250ms(self):
        state,initial,clock,transport=self.fixture()
        clock.monotonic_ns=lambda:300_000_000
        with patch.object(subject,'time',clock),self.assertRaises(ValueError):
            subject._post_tail_callback_witness(transport,initial,100,0)
    def test_actual_sdk_layout_and_aligned_publication_copy(self):
        state=Shared();state.callback_serial=5;state.last_frame=100
        self.assertEqual(completed_snapshot(state).last_frame,100)
        state.active=1;self.assertIsNone(completed_snapshot(state))
        state.active=0
        original=c.string_at
        def torn(address,size):
            value=original(address,size);state.callback_serial+=1;return value
        with patch('host_runtime.native6_callback_snapshot.c.string_at',torn):
            self.assertIsNone(completed_snapshot(state))

    def test_observer_admission_waits_only_within_original_wall_window(self):
        from host_runtime import native6_strategic_observer as adapter
        observer=adapter.Native6StrategicObserver.__new__(adapter.Native6StrategicObserver)
        state=Shared();state.magic=0x53434736;state.version=6;state.size=4592
        state.phase=1;state.active=1;state.lease_held=state.hook_held=1;state.callback_serial=5
        observer._state=state;observer._sealed=bytes(state.binding);observer._serial_highwater=0
        now=[0];observer._clock=lambda:now[0];observer._read_deadline=250_000_000
        observer._references=lambda:None
        def finish(seconds):now[0]+=int(seconds*1e9);state.active=0;state.callback_serial=6
        with patch.object(adapter.time,'sleep',finish):
            self.assertEqual(observer._ready_snapshot()['callback_serial'],6)
        state.active=1;now[0]=250_000_001
        with self.assertRaisesRegex(ValueError,'callback_not_completed'):observer._ready_snapshot()

    def test_actual_controls_tail_and_complete_two_frame_window(self):
        # Only identity/flag decoders are fixtures here; the actual bounded
        # ordered reader, controls sampler, tail and witness all execute.
        for attack in ('none','root_on_final_frame','ai_on_final_frame','frame103_in_tail'):
            state,initial,clock,transport=self.fixture();words={}
            game,owner,ai,manager=0x90000,0x10000,0x20000,0x30000
            binding=dict(game=game,engine=0x40000,owner=owner,ai=ai,personality=0x50000,
                personality_data=0x60000,player_template=0x70000)
            state['raw_binding']=binding
            words.update({0xcd8ce4:game,0xcdd190:binding['engine'],game:0xbeb630,game+0x50:100,
                0xcdd1a0:manager,manager:0xc07ab8,manager+0x48:owner,owner:0xc5bce0,
                owner+0x20:3,owner+0x90:ai})
            for offset,vt,own,enabled in ((0x458,0xc5f8f8,0x14,0x1c),(0x4d4,0xc5f484,8,0x10),(0x564,0xc5f440,8,0x10)):
                words.update({ai+offset:vt,ai+offset+own:owner,ai+offset+enabled:1})
            identity=lambda:dict(player=hex(owner),ai_player=hex(words[owner+0x90]),
                personality_wrapper=hex(binding['personality']),personality_data=hex(binding['personality_data']),
                player_template=hex(binding['player_template']))
            transport.native=identity();transport.manifest=dict(flags=['flag'])
            reads=[0]
            def read(address,size):
                if address==game+0x50:
                    reads[0]+=1
                    if reads[0]==3:
                        if attack=='root_on_final_frame':words[0xcd8ce4]=0x91000
                        if attack=='ai_on_final_frame':words[owner+0x90]=0x21000
                if attack=='frame103_in_tail' and reads[0]==3 and address==0xcdd1a0:
                    words[game+0x50]=103
                return struct.pack('<I',words.get(address,0))[:size]
            transport.memory=SimpleNamespace(read=read);transport.native_status=lambda:copy.deepcopy(state)
            original_wait=clock.sleep
            def callback(seconds):
                original_wait(seconds);state['last_frame']=words[game+0x50]
                if words[0xcd8ce4]!=game or words[owner+0x90]!=ai:state.update(phase=5,error=34)
            clock.sleep=callback
            modules={'read_selected_personality':SimpleNamespace(inspect_player=lambda *args:identity()),
                'read_script_flags':SimpleNamespace(inspect_flags=lambda *args:dict(flags=[]))}
            with patch.dict(sys.modules,modules),patch.object(subject,'time',clock):
                if attack=='none':
                    result=subject.sample_controls(transport)
                    self.assertEqual(result['frame_after'],100)
                    self.assertEqual(result['post_tail_callback_witness']['later_serial'],6)
                else:
                    with self.assertRaises(ValueError,msg=attack):subject.sample_controls(transport)

    def test_product_close_waits_for_observation_to_release_mapping(self):
        from host_runtime.native6_transport import MacroPolicyProbe
        transport=MacroPolicyProbe.__new__(MacroPolicyProbe);transport._lifecycle_lock=threading.RLock()
        entered=threading.Event();release=threading.Event();closed=threading.Event()
        def observe(label):entered.set();self.assertTrue(release.wait(2));return 'sample'
        transport._observe=observe;transport._close=closed.set
        reader=threading.Thread(target=transport.observe,args=('fixture',));reader.start()
        self.assertTrue(entered.wait(2));closer=threading.Thread(target=transport.close);closer.start()
        self.assertFalse(closed.wait(.03));release.set();reader.join(2);closer.join(2)
        self.assertTrue(closed.is_set());self.assertFalse(reader.is_alive() or closer.is_alive())

    def test_ack_is_read_to_completion_without_any_second_command(self):
        from host_runtime.native6_transport import MacroPolicyProbe
        probe=MacroPolicyProbe.__new__(MacroPolicyProbe)
        completed=dict(ack=4,request=4,phase=1,error=0,result=8,active=0)
        snapshots=iter((None,completed));probe.completed_native_status=lambda:next(snapshots)
        receipt=probe._receipt(dict(ack=4,result=8,active=1),'fixture')
        self.assertEqual(receipt['seq'],4);self.assertEqual(receipt['native']['active'],0)
        self.assertTrue(receipt['native_gate_acknowledged'])
        probe.completed_native_status=lambda:dict(completed,ack=5,request=5)
        with self.assertRaisesRegex(ContractError,'generation_changed'):
            probe._receipt(dict(ack=4,result=8),'fixture')

    def test_known_epoch_return_covers_only_its_historical_strategy_ownership(self):
        from host_runtime.strategic_unified_unknown_return_v5 import covered_unknown_ownership
        parent=dict(request_id='p',operation='macro_policy',status='uncertain',created_at='1',payload=dict(
            actions=['scout'],plan_id='plan',native_command_id='p',duration_frames=450,not_after_frame=3000,unit_operation_policy='native_ai'))
        child=dict(request_id='c',operation='native_strategic_v5',status='uncertain',created_at='2',payload=dict(
            parent_command_id='p',actions=['scout'],duration_frames=450,not_after_frame=3000))
        stop=dict(created_at='3');rows=[parent,child]
        self.assertTrue(covered_unknown_ownership(rows,rows,stop))
        self.assertEqual(parent['status'],'uncertain')
        for change in (dict(operation='produce'),dict(created_at='4'),dict(status='dispatching')):
            bad=dict(child,**change)
            self.assertFalse(covered_unknown_ownership([bad],[parent,bad],stop))
        bad=copy.deepcopy(parent);bad['payload']['actions']=['produceconscript']
        self.assertFalse(covered_unknown_ownership([bad],[bad],stop))

if __name__=='__main__':unittest.main()
