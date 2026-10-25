"""Simulated shared-buffer tests only. No process/mapping/game/network access."""
import ast
import copy
import ctypes as c
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import uuid
from unittest.mock import patch
import running_birth_source_v1 as m

SESSION="11111111-1111-4111-8111-111111111111"
COMMANDER="22222222-2222-4222-8222-222222222222"
COMMAND="33333333-3333-4333-8333-333333333333"
TASK="44444444-4444-4444-8444-444444444444"
def words(value): return struct.unpack("<4I",uuid.UUID(value).bytes)
def bits(value): return struct.unpack("<I",struct.pack("<f",value))[0]

def fixture():
    ticks=134059968000000000
    expected=dict(pid=1234,thread=5678,owner=0x100000,ai=0x200000,personality=0x300000,personality_id=123,player_template=0x400000,start_low=ticks&0xffffffff,start_high=ticks>>32,command_id=COMMAND,task_id=TASK,seq=1,unit="conscript",cost=85,factory=0x500000,factory_id=600,iface=0x600000,object=0,object_id=0)
    session=dict(pid=1234,session_id=SESSION,start_time=datetime.fromtimestamp((ticks-116444736000000000)/10000000,timezone.utc).isoformat(),scenario=dict(commander_id=COMMANDER,computer_player_index=3),game="fixture-no-game")
    h=m.Header();h.magic=m.MAGIC;h.version=1;h.phase=1;h.heartbeat=999;h.active=2;h.count=1;h.callback_thread=expected["thread"]
    for key in m.BINDING: setattr(h,key,expected[key])
    h.session[:]=words(SESSION);h.commander[:]=words(COMMANDER)
    r=m.Receipt();r.version=4;r.command.seq=1;r.command.id[:]=words(COMMAND);r.command.task[:]=words(TASK);r.command.session[:]=words(SESSION);r.command.commander[:]=words(COMMANDER)
    for key in ("factory","factory_id","iface"): setattr(r.command,key,expected[key])
    r.command.hash=m.UNITS["conscript"];r.command.budget=85;r.command.reserve=1000;r.command.expires=500;r.command.queue_limit=2;r.command.requested_tick=400
    for key,value in dict(state=2,attempted=1,frame=100,queue_id=601,node=0x700000,cost=85,quoted_cost=85,cash=10000,paid=85,debit_count=4,preserved=1,created=1,object=0x800000,object_id=700,object_owner=expected["owner"],object_hash=m.UNITS["conscript"],completed=1,completion_frame=150,live_samples=3,object_hp_bits=bits(100),object_x_bits=bits(20),object_y_bits=bits(40),factory_x_bits=bits(30),factory_y_bits=bits(50)).items(): setattr(r,key,value)
    return session,expected,h,r

class Channel:
    def __init__(self,h,r): self.h=h;self.rows=[r];self.closed=False;self.reads=0;self.mutate=None;self.now=1000;self.frame=200
    def read(self,offset,size):
        self.reads+=1
        if self.mutate:self.mutate(self,offset,size)
        if offset==0: return bytes(self.h)[:size]
        index=(offset-m.HEADER_SIZE)//m.RECEIPT_SIZE;inside=(offset-m.HEADER_SIZE)%m.RECEIPT_SIZE
        return bytes(self.rows[index])[inside:inside+size]
    def tick(self): return self.now
    def runtime(self,expected): return dict(frame=self.frame,owner=expected["owner"],thread=expected["thread"])
    def close(self): self.closed=True

class RunningBirth(unittest.TestCase):
    def setUp(self): self.session,self.expected,self.h,self.r=fixture();self.channel=Channel(self.h,self.r)
    def snap(self): return m.snapshot_running(self.channel,self.session,self.expected)
    def test_actual_struct_schema_matches_frozen_production_python_source_without_import(self):
        source=(m.ROOT/"production/persistent/client.py").read_text()
        tree=ast.parse(source)
        words_node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="R_FIELDS" for t in n.targets))
        self.assertEqual(ast.literal_eval(words_node.value.func.value).split(),m.RECEIPT_WORDS)
        self.assertEqual((c.sizeof(m.Command),c.sizeof(m.Header),c.sizeof(m.Receipt)),(104,256,224))
        self.assertEqual(m.Header.request.offset,112)
        shared=(m.ROOT/"production/persistent/shared.h").read_text()
        self.assertIn("#define P_MAGIC 0x50434d44u",shared)
        self.assertIn("volatile LONG updates,version;Command command;",shared)
    def test_import_cannot_open_api_or_attach(self):
        with patch.object(c,"WinDLL",side_effect=AssertionError("no Windows API on import")):
            spec=importlib.util.spec_from_file_location("running_birth_import_test",Path(m.__file__));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.PROTOCOL,m.PROTOCOL)
    def test_positive_raw_provenance_not_actor_admission(self):
        result=self.snap();self.assertEqual(result["receipt_hex"],result["receipt_after_hex"]);self.assertEqual(result["actor_discovered"]["object_id"],700)
        self.assertEqual(result["dynamic"]["decoded"]["object_hp"],100)
        self.assertFalse(result["actor_admission_verified"]);self.assertFalse(result["current_actor_liveness_verified"]);self.assertFalse(result["runtime_capability_authorized"])
        self.assertEqual(result["sdk_calls"],0)
    def test_active_callback_and_changing_heartbeat_header_allowed(self):
        def mutate(ch,offset,size):
            if offset==0: ch.h.heartbeat+=1;ch.now+=1;ch.h.active=3;ch.h.last_frame+=1
        self.channel.mutate=mutate
        result=self.snap();self.assertNotEqual(result["header_hex"],result["header_after_hex"])
    def test_tick_wrap_freshness_is_unsigned(self):
        self.h.heartbeat=-10;self.channel.now=5;self.snap()
        self.h.heartbeat=-3000
        with self.assertRaisesRegex(ValueError,"heartbeat"):self.snap()
    def test_stopped_producer_never_qualified_as_running(self):
        self.h.phase=2
        with self.assertRaisesRegex(ValueError,"not_running"):self.snap()
    def test_phase_stop_error_and_binding_rejected(self):
        for field,value in (("stop_requested",1),("error",1),("owner",0x900000),("callback_thread",77),("version",2)):
            with self.subTest(field=field):
                old=getattr(self.h,field);setattr(self.h,field,value)
                with self.assertRaises(ValueError):self.snap()
                setattr(self.h,field,old)
    def test_stale_heartbeat_rejected(self):
        self.channel.now=4000
        with self.assertRaisesRegex(ValueError,"heartbeat"):self.snap()
    def test_inflight_receipt_bounded_no_sleep_or_output(self):
        self.r.updates=1
        with patch.object(m,"_Channel",side_effect=AssertionError("pure reader")):
            with self.assertRaises(m.NotReady): self.snap()
        self.assertLessEqual(self.channel.reads,48)
    def test_torn_row_retries_then_accepts_stable_new_version(self):
        changed=[False]
        def mutate(ch,offset,size):
            if size==m.RECEIPT_SIZE and not changed[0]: ch.rows[0].version+=1;changed[0]=True
        self.channel.mutate=mutate
        result=self.snap();self.assertEqual(result["attempts"],2)
    def test_duplicate_matching_uuid_rejected(self):
        self.h.count=2;self.channel.rows.append(m.Receipt.from_buffer_copy(bytes(self.r)))
        with self.assertRaisesRegex(ValueError,"ambiguous"):self.snap()
    def test_same_command_uuid_wrong_task_or_seq_rejected(self):
        for field in ("task","seq"):
            old=bytes(self.r)
            if field=="task":self.r.command.task[:]=words(SESSION)
            else:self.r.command.seq+=1
            with self.assertRaisesRegex(ValueError,"command"):self.snap()
            self.r=m.Receipt.from_buffer_copy(old);self.channel.rows[0]=self.r
    def test_payment_created_identity_and_clock_failures(self):
        for field,value in (("paid",84),("quoted_cost",86),("payment_error",1),("object_owner",123),("object_id",0),("object_hash",12),("completion_frame",201)):
            with self.subTest(field=field):
                old=getattr(self.r,field);setattr(self.r,field,value)
                with self.assertRaises(ValueError):self.snap()
                setattr(self.r,field,old)
    def test_incomplete_receipt_does_not_grant(self):
        self.r.completed=0
        with self.assertRaises(m.NotReady):self.snap()
    def test_nonfinite_dynamic_rejected(self):
        self.r.object_hp_bits=bits(float("nan"))
        with self.assertRaisesRegex(ValueError,"dynamic"):self.snap()
    def test_locked_actor_cannot_be_rediscovered_as_another(self):
        self.expected.update(object=0x800004,object_id=701)
        with self.assertRaisesRegex(ValueError,"actor_changed"):self.snap()
    def test_input_binding_types_uuid_and_start(self):
        for key,value in (("pid",True),("seq",0),("start_low",0),("command_id","00000000-0000-0000-0000-000000000000"),("object_id",700)):
            expected=dict(self.expected);expected[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):m.validate_expected(self.session,expected)
    def test_count_advance_retries_and_new_duplicate_is_not_missed(self):
        reads=[0]
        def mutate(ch,offset,size):
            if offset==0:
                reads[0]+=1
                if reads[0]==2:
                    ch.h.count=2;ch.rows.append(m.Receipt.from_buffer_copy(bytes(ch.rows[0])))
        self.channel.mutate=mutate
        with self.assertRaisesRegex(ValueError,"ambiguous"):self.snap()
    def test_completion_published_during_frame_advance_uses_actual_after_clock(self):
        calls=[0]
        def runtime(expected):
            calls[0]+=1
            return dict(frame=149 if calls[0]==1 else 150,owner=expected["owner"],thread=expected["thread"])
        self.channel.runtime=runtime
        self.assertEqual(self.snap()["runtime_after"]["frame"],150)
    def test_max_attempts_strict(self):
        for value in (0,33,True):
            with self.assertRaises(ValueError):m.snapshot_running(self.channel,self.session,self.expected,value)
    def test_collector_creates_immutable_file_closes_mapping_and_accepts_dynamic_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);self.session["run_directory"]=str(folder);session_path=folder/"session.json";session_path.write_text(json.dumps(self.session));first=folder/"first.json";second=folder/"second.json"
            with patch.object(m,"_Channel",return_value=self.channel): result=m.collect_running_birth(session_path,self.expected,first)
            self.assertTrue(self.channel.closed);self.assertFalse(result["actor_admission_verified"])
            frozen=first.read_bytes();self.r.version+=1;self.r.live_samples+=1;self.r.object_x_bits=bits(25);self.h.heartbeat+=1
            with patch.object(m,"_Channel",return_value=self.channel): later=m.collect_running_birth(session_path,self.expected,second,prior_snapshot=first)
            self.assertEqual(first.read_bytes(),frozen);self.assertEqual(result["payment_identity"],later["payment_identity"])
            with patch.object(m,"_Channel",side_effect=AssertionError("no mapping for existing output")):
                with self.assertRaises(FileExistsError):m.collect_running_birth(session_path,self.expected,first)
    def test_prior_actor_or_payment_projection_change_rejected_without_new_file(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);self.session["run_directory"]=str(folder);path=folder/"session.json";path.write_text(json.dumps(self.session));first=folder/"first.json";second=folder/"second.json"
            with patch.object(m,"_Channel",return_value=self.channel):m.collect_running_birth(path,self.expected,first)
            self.r.object_id+=1
            with patch.object(m,"_Channel",return_value=self.channel),self.assertRaisesRegex(ValueError,"prior_payment"):m.collect_running_birth(path,self.expected,second,prior_snapshot=first)
            self.assertFalse(second.exists())
    def test_prior_live_sample_regression_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);self.session["run_directory"]=str(folder);path=folder/"session.json";path.write_text(json.dumps(self.session));first=folder/"first.json";second=folder/"second.json"
            with patch.object(m,"_Channel",return_value=self.channel):m.collect_running_birth(path,self.expected,first)
            self.r.live_samples=1
            with patch.object(m,"_Channel",return_value=self.channel),self.assertRaisesRegex(ValueError,"regressed"):m.collect_running_birth(path,self.expected,second,prior_snapshot=first)
    def test_prior_actual_clock_cannot_reset_in_same_process(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);self.session["run_directory"]=str(folder);path=folder/"session.json";path.write_text(json.dumps(self.session));first=folder/"first.json";second=folder/"second.json"
            with patch.object(m,"_Channel",return_value=self.channel):m.collect_running_birth(path,self.expected,first)
            self.channel.frame=199
            with patch.object(m,"_Channel",return_value=self.channel),self.assertRaisesRegex(ValueError,"prior_clock"):m.collect_running_birth(path,self.expected,second,prior_snapshot=first)
    def test_outside_run_rejected_before_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);run=folder/"run";run.mkdir();self.session["run_directory"]=str(run);path=run/"session.json";path.write_text(json.dumps(self.session))
            with patch.object(m,"_Channel",side_effect=AssertionError("no map")),self.assertRaisesRegex(ValueError,"outside_run"):m.collect_running_birth(path,self.expected,folder/"outside.json")

if __name__=="__main__":unittest.main()
