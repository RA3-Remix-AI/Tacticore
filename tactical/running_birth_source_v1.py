"""Read-only snapshots of paid births from a RUNNING producer.

Import creates no Windows APIs, process handles, mappings, threads or SDK calls.
A snapshot proves producer provenance only; Native must independently admit the
current own actor. Dynamic receipt samples are historical, not current liveness.
"""
from __future__ import annotations
import ctypes as c
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import struct
import uuid

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_GAME = "ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165"
PROTOCOL = "running_paid_birth_source_v1"
MAGIC = 0x50434d44
UNITS = {"conscript": 0x19ab11af, "flak": 0x2c358c61}
U, L = c.c_uint32, c.c_int32
COMMAND_WORDS = "hash budget reserve expires queue_limit requested_tick factory factory_id iface".split()
RECEIPT_WORDS = "state error attempted frame queue_id node cost quoted_cost cash liability prior_count preserved paid debit_count payment_error created object object_id object_owner object_hash completed completion_frame live_samples object_hp_bits object_x_bits object_y_bits factory_x_bits factory_y_bits".split()
class Command(c.Structure):
    _fields_ = [("seq", U), ("id", U*4), ("task", U*4), ("session", U*4), ("commander", U*4)] + [(n, U) for n in COMMAND_WORDS]
class Receipt(c.Structure):
    _fields_ = [("updates", L), ("version", L), ("command", Command)] + [(n, U) for n in RECEIPT_WORDS]
class Header(c.Structure):
    _fields_ = [(n,U) for n in "magic version pid thread owner ai personality personality_id player_template start_low start_high".split()] + [("session",U*4),("commander",U*4)] + [(n,U) for n in "total_budget reserve_floor min_interval start_frame".split()] + [(n,L) for n in "phase stop_requested active heartbeat request_state".split()] + [("request",Command)] + [(n,U) for n in "reply_index reply_error last_seq last_frame last_accepted_frame spent count restore_mask error callback_thread".split()]
HEADER_SIZE, RECEIPT_SIZE, CAP = 256, 224, 1024
MAPPING_SIZE = HEADER_SIZE + CAP*RECEIPT_SIZE
BINDING = "pid thread owner ai personality personality_id player_template start_low start_high".split()
EXPECTED_FIELDS = set(BINDING + "command_id task_id seq unit cost factory factory_id iface object object_id".split())
DYNAMIC = {"updates", "version", "live_samples", "object_hp_bits", "object_x_bits", "object_y_bits", "factory_x_bits", "factory_y_bits"}
HEARTBEAT_MAX_MS = 2000

class NotReady(ValueError):
    """A bounded caller may try later; this reader never waits or dispatches."""

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value): return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def ident(words): return str(uuid.UUID(bytes=struct.pack("<4I",*words)))
def uuid_text(value):
    if type(value) is not str or not uuid.UUID(value).int: raise ValueError("birth_uuid")
    return str(uuid.UUID(value))
def u32(value, name, minimum=0):
    if type(value) is not int or not minimum <= value <= 0xffffffff: raise ValueError("birth_"+name)
    return value

def no_duplicates(items):
    result={}
    for key,value in items:
        if key in result: raise ValueError("birth_duplicate_json_key")
        result[key]=value
    return result

def read_json(raw):
    return json.loads(raw.decode("utf-8-sig"),object_pairs_hook=no_duplicates,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("birth_nonfinite_json")))

def validate_expected(session, expected):
    if type(expected) is not dict or set(expected)!=EXPECTED_FIELDS: raise ValueError("birth_expected_fields")
    out=dict(expected)
    for key in EXPECTED_FIELDS-{"unit","command_id","task_id"}: u32(out[key],key)
    for key in BINDING+"seq cost factory factory_id iface".split():
        if not out[key] and key not in ("start_low","start_high"): raise ValueError("birth_expected_zero_"+key)
    if not (out["start_low"] or out["start_high"]): raise ValueError("birth_expected_start")
    if out["unit"] not in UNITS: raise ValueError("birth_expected_unit")
    for key in ("command_id","task_id"): out[key]=uuid_text(out[key])
    if out["pid"]!=session.get("pid") or type(session.get("pid")) is not int: raise ValueError("birth_expected_pid")
    uuid_text(session["session_id"]); uuid_text(session["scenario"]["commander_id"])
    if session["scenario"].get("computer_player_index")!=3: raise ValueError("birth_expected_player")
    ticks=(out["start_high"]<<32)|out["start_low"]
    if abs((ticks-116444736000000000)/10000000-datetime.fromisoformat(session["start_time"]).timestamp())>.001:
        raise ValueError("birth_expected_start")
    if bool(out["object"])!=bool(out["object_id"]): raise ValueError("birth_expected_actor_pair")
    for key in ("owner","ai","personality","player_template","factory","iface"):
        if out[key]<0x10000 or out[key]%4: raise ValueError("birth_expected_pointer_"+key)
    if out["object"] and (out["object"]<0x10000 or out["object"]%4): raise ValueError("birth_expected_object")
    return out

def header_identity(h):
    return dict(**{key:int(getattr(h,key)) for key in BINDING},magic=h.magic,version=h.version,
                session_id=ident(h.session),commander_id=ident(h.commander),callback_thread=h.callback_thread)

def verify_header(h, session, expected, tick):
    if (h.magic,h.version,h.phase,h.error,h.stop_requested)!=(MAGIC,1,1,0,0): raise ValueError("birth_producer_not_running")
    if not 0<h.count<=CAP: raise NotReady("birth_ledger_count")
    if any(getattr(h,key)!=expected[key] for key in BINDING) or h.callback_thread!=expected["thread"]:
        raise ValueError("birth_producer_binding")
    if ident(h.session)!=session["session_id"] or ident(h.commander)!=session["scenario"]["commander_id"]:
        raise ValueError("birth_producer_uuid")
    if ((tick-int(h.heartbeat))&0xffffffff)>HEARTBEAT_MAX_MS: raise ValueError("birth_producer_heartbeat")
    if h.active<0: raise ValueError("birth_producer_active_malformed")
    return header_identity(h)

def command_view(command):
    return dict(seq=command.seq,command_id=ident(command.id),task_id=ident(command.task),
                session_id=ident(command.session),commander_id=ident(command.commander),
                **{key:int(getattr(command,key)) for key in COMMAND_WORDS})

def stable_receipt(channel,index):
    offset=HEADER_SIZE+index*RECEIPT_SIZE
    prefix=channel.read(offset,8);updates,version=struct.unpack("<ii",prefix)
    if updates or version<=0: raise NotReady("birth_receipt_writing")
    first=channel.read(offset,RECEIPT_SIZE);second=channel.read(offset,RECEIPT_SIZE)
    after=channel.read(offset,8)
    if first!=second or prefix!=after or first[:8]!=prefix: raise NotReady("birth_receipt_unstable")
    receipt=Receipt.from_buffer_copy(first)
    return receipt,first,second

def receipt_facts(receipt,session,expected,frame):
    command=command_view(receipt.command)
    wanted=dict(command_id=expected["command_id"],task_id=expected["task_id"],seq=expected["seq"],
                session_id=session["session_id"],commander_id=session["scenario"]["commander_id"],
                hash=UNITS[expected["unit"]],factory=expected["factory"],factory_id=expected["factory_id"],iface=expected["iface"])
    if any(command.get(k)!=value for k,value in wanted.items()): raise ValueError("birth_receipt_command")
    r=receipt
    if r.state!=2 or r.error or r.attempted!=1 or r.preserved!=1 or r.created!=1 or r.completed!=1 or not r.live_samples:
        raise NotReady("birth_receipt_not_completed")
    if r.payment_error or not r.debit_count or not r.cost or r.cost!=r.quoted_cost or r.paid!=r.cost or r.cost!=expected["cost"]:
        raise ValueError("birth_receipt_payment")
    if not r.queue_id or not r.node or not r.object or not r.object_id or r.object_owner!=expected["owner"] or r.object_hash!=command["hash"]:
        raise ValueError("birth_receipt_object")
    if r.object<0x10000 or r.object%4 or r.node<0x10000 or r.node%4: raise ValueError("birth_receipt_pointer")
    if expected["object"] and (r.object,r.object_id)!=(expected["object"],expected["object_id"]): raise ValueError("birth_receipt_actor_changed")
    if not 0<r.frame<=r.completion_frame<=frame or command["expires"]<r.frame: raise ValueError("birth_receipt_clock")
    if command["budget"]<r.cost or not 1<=command["queue_limit"]<=2 or not command["reserve"]: raise ValueError("birth_receipt_envelope")
    fields={key:int(getattr(r,key)) for key in RECEIPT_WORDS}
    projection=dict(command=command,**{key:value for key,value in fields.items() if key not in DYNAMIC})
    dynamic={key:int(getattr(r,key)) for key in DYNAMIC}
    floats={key[:-5]:struct.unpack("<f",struct.pack("<I",value))[0] for key,value in dynamic.items() if key.endswith("_bits")}
    if any(not math.isfinite(value) or abs(value)>1e6 for value in floats.values()) or floats["object_hp"]<=0:
        raise ValueError("birth_receipt_dynamic_malformed")
    return projection,dict(dynamic,decoded=floats)

def snapshot_running(channel, session, expected, max_attempts=16):
    """Pure bounded reader over read/header/tick/runtime methods; no mutations."""
    if type(max_attempts) is not int or not 1<=max_attempts<=32: raise ValueError("birth_attempt_bound")
    last="birth_receipt_unavailable"
    for attempt in range(1,max_attempts+1):
        try:
            runtime_before=channel.runtime(expected)
            before_raw=channel.read(0,HEADER_SIZE);before=Header.from_buffer_copy(before_raw)
            binding=verify_header(before,session,expected,channel.tick())
            found=[]
            for index in range(before.count):
                receipt,raw,raw_after=stable_receipt(channel,index)
                if ident(receipt.command.id)==expected["command_id"]: found.append((index,receipt,raw,raw_after))
            if len(found)>1: raise ValueError("birth_receipt_ambiguous")
            if not found: raise NotReady("birth_receipt_missing")
            index,receipt,raw,raw_after=found[0]
            after_raw=channel.read(0,HEADER_SIZE);after=Header.from_buffer_copy(after_raw)
            if verify_header(after,session,expected,channel.tick())!=binding or after.count<before.count:
                raise ValueError("birth_header_identity_changed")
            if after.count>before.count: raise NotReady("birth_ledger_prefix_advanced")
            runtime_after=channel.runtime(expected)
            if runtime_after["frame"]<runtime_before["frame"]: raise ValueError("birth_runtime_clock_regressed")
            # Runtime identity is independently re-read; frames may advance.
            if {k:v for k,v in runtime_before.items() if k!="frame"}!={k:v for k,v in runtime_after.items() if k!="frame"}:
                raise ValueError("birth_runtime_identity_changed")
            projection,dynamic=receipt_facts(receipt,session,expected,runtime_after["frame"])
            return dict(protocol=PROTOCOL,producer_protocol_version=1,mutations=False,sdk_calls=0,
                session_id=session["session_id"],pid=session["pid"],player_id=3,commander_id=session["scenario"]["commander_id"],
                expected=expected,producer_binding=binding,header_size=HEADER_SIZE,receipt_size=RECEIPT_SIZE,
                header_hex=before_raw.hex(),header_after_hex=after_raw.hex(),receipt_index=index,
                receipt_hex=raw.hex(),receipt_after_hex=raw_after.hex(),receipt_sha256=hashlib.sha256(raw).hexdigest(),
                payment_identity=projection,payment_identity_sha256=hashlib.sha256(canonical(projection)).hexdigest(),
                dynamic=dynamic,runtime_before=runtime_before,runtime_after=runtime_after,attempts=attempt,
                actor_discovered=dict(object=receipt.object,object_id=receipt.object_id,object_owner=receipt.object_owner,object_hash=receipt.object_hash),
                current_actor_liveness_verified=False,actor_admission_verified=False,runtime_capability_authorized=False,
                note="Paid producer provenance only; live_samples/HP/XY are historical. Native must check current own roster and three-frame admission.")
        except NotReady as error: last=str(error)
    raise NotReady(last)

class _Channel:
    """Windows read-only process + FILE_MAP_READ view, opened only on request."""
    def __init__(self,session,expected):
        from ctypes import wintypes as w
        self.k=c.WinDLL("kernel32",use_last_error=True);self.w=w;self.process=None;self.mapping=None;self.view=None
        k=self.k
        k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
        k.OpenFileMappingW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];k.OpenFileMappingW.restype=w.HANDLE
        k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p
        k.ReadProcessMemory.argtypes=[w.HANDLE,c.c_void_p,c.c_void_p,c.c_size_t,c.POINTER(c.c_size_t)];k.ReadProcessMemory.restype=w.BOOL
        k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)];k.QueryFullProcessImageNameW.restype=w.BOOL
        k.GetProcessTimes.argtypes=[w.HANDLE,c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME)];k.GetProcessTimes.restype=w.BOOL
        k.GetExitCodeProcess.argtypes=[w.HANDLE,c.POINTER(w.DWORD)];k.GetExitCodeProcess.restype=w.BOOL
        k.UnmapViewOfFile.argtypes=[c.c_void_p];k.CloseHandle.argtypes=[w.HANDLE];k.GetTickCount.restype=w.DWORD
        try:
            self.process=k.OpenProcess(0x410,False,session["pid"])
            if not self.process: raise ValueError("birth_process_unavailable")
            size=w.DWORD(32768);path=c.create_unicode_buffer(size.value)
            if not k.QueryFullProcessImageNameW(self.process,0,path,c.byref(size)) or Path(path.value).resolve()!=Path(session["game"]).resolve() or sha(path.value)!=EXPECTED_GAME:
                raise ValueError("birth_game_identity")
            times=[w.FILETIME() for _ in range(4)]
            if not k.GetProcessTimes(self.process,*[c.byref(t) for t in times]) or (times[0].dwLowDateTime,times[0].dwHighDateTime)!=(expected["start_low"],expected["start_high"]):
                raise ValueError("birth_process_start")
            self.mapping=k.OpenFileMappingW(4,False,"Local\\RA3ProductionPersistent_"+str(session["pid"]))
            if not self.mapping: raise NotReady("birth_running_mapping_missing")
            self.view=k.MapViewOfFile(self.mapping,4,0,0,MAPPING_SIZE)
            if not self.view: raise ValueError("birth_mapping_unreadable")
        except BaseException:
            self.close();raise
    def read(self,offset,size):
        if type(offset) is not int or type(size) is not int or offset<0 or size<1 or offset+size>MAPPING_SIZE: raise ValueError("birth_mapping_read_bounds")
        return c.string_at(self.view+offset,size)
    def memory(self,address,size=4):
        if not 0x10000<=address<2**32 or address+size>2**32 or not 0<size<=0x2000: raise ValueError("birth_process_read_bounds")
        value=c.create_string_buffer(size);got=c.c_size_t()
        if not self.k.ReadProcessMemory(self.process,address,value,size,c.byref(got)) or got.value!=size: raise ValueError("birth_process_read_unavailable")
        return value.raw
    def word(self,address): return struct.unpack("<I",self.memory(address))[0]
    def tick(self): return self.k.GetTickCount()
    def runtime(self,expected):
        code=self.w.DWORD()
        if not self.k.GetExitCodeProcess(self.process,c.byref(code)) or code.value!=259: raise ValueError("birth_process_exited")
        owner,ai,personality=expected["owner"],expected["ai"],expected["personality"]
        checks={"owner_vtable":self.word(owner),"player_index":self.word(owner+0x20),"player_template":self.word(owner+0x10),"ai":self.word(owner+0x90),"ai_vtable":self.word(ai),"ai_owner":self.word(ai+8),"ai_owner_second":self.word(ai+0x8a8),"personality":self.word(ai+0x8b0),"personality_id":self.word(personality+0x18)}
        wanted=dict(owner_vtable=0xc5bce0,player_index=3,player_template=expected["player_template"],ai=ai,ai_vtable=0xc60f60,ai_owner=owner,ai_owner_second=owner,personality=personality,personality_id=expected["personality_id"])
        if checks!=wanted: raise ValueError("birth_current_player_identity")
        logic=self.word(0xcd8ce4)
        return dict(checks,logic=logic,frame=self.word(logic+0x50))
    def close(self):
        if self.view: self.k.UnmapViewOfFile(self.view);self.view=None
        if self.mapping: self.k.CloseHandle(self.mapping);self.mapping=None
        if self.process: self.k.CloseHandle(self.process);self.process=None

def collect_running_birth(session_path, expected, output, *, prior_snapshot=None, max_attempts=16):
    """Freeze one running-producer snapshot with exclusive-create semantics.

    expected uses native struct field names; object/object_id are BOTH zero for
    first discovery, or both fixed. prior_snapshot detects later payment/actor
    projection changes while allowing dynamic sample/version advancement.
    """
    if c.sizeof(Header)!=HEADER_SIZE or c.sizeof(Receipt)!=RECEIPT_SIZE: raise ValueError("birth_native_layout")
    session_path=Path(session_path).resolve();source=session_path.read_bytes();session=read_json(source)
    expected=validate_expected(session,expected);output=Path(output).resolve()
    if not output.is_relative_to(Path(session["run_directory"]).resolve()) or output==session_path: raise ValueError("birth_output_outside_run")
    if output.exists(): raise FileExistsError(output)
    prior=None
    if prior_snapshot is not None:
        prior_path=Path(prior_snapshot).resolve()
        if prior_path==output or not prior_path.is_relative_to(Path(session["run_directory"]).resolve()): raise ValueError("birth_prior_path")
        prior=read_json(prior_path.read_bytes())
        if prior.get("protocol")!=PROTOCOL or prior.get("session_source",{}).get("sha256")!=hashlib.sha256(source).hexdigest() or prior.get("helper_sha256")!=sha(__file__) or prior.get("expected")!=expected:
            raise ValueError("birth_prior_binding")
    channel=_Channel(session,expected)
    try: result=snapshot_running(channel,session,expected,max_attempts)
    finally: channel.close()
    if session_path.read_bytes()!=source: raise ValueError("birth_session_changed")
    if prior is not None:
        if prior.get("producer_binding")!=result["producer_binding"] or prior.get("payment_identity")!=result["payment_identity"] or prior.get("payment_identity_sha256")!=hashlib.sha256(canonical(result["payment_identity"])).hexdigest():
            raise ValueError("birth_prior_payment_identity_changed")
        if result["dynamic"]["live_samples"]<prior.get("dynamic",{}).get("live_samples",0): raise ValueError("birth_live_samples_regressed")
        if result["runtime_before"]["frame"]<prior.get("runtime_after",{}).get("frame",0): raise ValueError("birth_prior_clock_regressed")
        result["prior_snapshot"]=dict(path=str(prior_path),sha256=sha(prior_path))
    result.update(session_source=dict(path=str(session_path),sha256=hashlib.sha256(source).hexdigest()),helper_sha256=sha(__file__),
        producer_sources={str(p.relative_to(ROOT)).replace("\\","/"):sha(p) for p in (ROOT/"production/persistent/client.py",ROOT/"production/persistent/shared.h",ROOT/"production/persistent/executor.cpp",ROOT/"production/persistent/bin-v2/ProductionPersistent.dll",ROOT/"production/persistent/bin-v2/persistent_host.exe")})
    if prior is not None and prior.get("producer_sources")!=result["producer_sources"]: raise ValueError("birth_prior_producer_sources_changed")
    encoded=json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2)+"\n"
    with output.open("x",encoding="utf-8") as stream: stream.write(encoded)
    return result
