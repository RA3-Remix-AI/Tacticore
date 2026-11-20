"""Fixed-policy Win32 discovery. No game launch, injection, process write or model call.

Only beta_setup installs policy paths. WebView requests can select
an opaque broker candidate; a candidate still needs the normal live admission.
Importing this module, registering a policy and constructing the factory do not
read a game process. Native reads occur only in the adapter's discover/probe calls.
"""
from __future__ import annotations

import ctypes as c
from ctypes import wintypes as w
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
from types import SimpleNamespace

from .contracts import ContractError, SessionBinding, canonical_json
from .desktop_session_registry import load_root, register_session_source
from .macro_bundle import load_bundle
from .macro_policy_runtime import COMMANDER
from .scenario import MODEL_FACTION, MODEL_PLAYER_ID, derive_scenario, own_base_point, start_by_vote
from .native_runtime_contract import PROTOCOL
from .session_discovery import MatchObservation, ProcessIdentity, RunRecord, SessionDiscovery, _local_path

ROOT = Path(__file__).resolve().parents[2]
NAME = 'session-discovery-policy.json'
KIND = 'trusted_macro_session_discovery_policy'
PINS = {0x8d5727: bytes.fromhex('89beb0080000'), 0x844a3f: bytes.fromhex('898690000000')}
# The commander seat only. Map, participants, teams and regions are derived
# live for each candidate (host_runtime.scenario).
SCOPE = dict(commander_id=COMMANDER, faction=MODEL_FACTION, player_id=MODEL_PLAYER_ID, candidate_ttl_seconds=90)


def fail(code):
    raise ContractError(code)


def read_object(path, maximum=1024*1024):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                fail('discovery_policy_invalid')
            result[key] = value
        return result
    try:
        with Path(path).open('rb') as stream:
            raw = stream.read(maximum+1)
        if len(raw) > maximum:
            fail('discovery_policy_invalid')
        value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs,
                           parse_constant=lambda _: fail('discovery_policy_invalid'))
        if not isinstance(value, dict):
            fail('discovery_policy_invalid')
        return value, hashlib.sha256(raw).hexdigest()
    except ContractError:
        raise
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        fail('discovery_policy_invalid')


def read_macro_bundle(path):
    """The runtime descriptor; scope admission still uses load_bundle."""
    _,digest=read_object(path,16384)
    return load_bundle(path)[0],digest


def creation_start(ticks):
    if type(ticks) is not int or not 0 < ticks < 2**64:
        fail('session_probe_invalid')
    try:
        at = datetime(1601,1,1,tzinfo=timezone.utc)+timedelta(microseconds=ticks//10)
        return at.strftime('%Y-%m-%dT%H:%M:%S')+f'.{ticks%10_000_000:07d}+00:00'
    except (OverflowError, ValueError):
        fail('session_probe_invalid')


def require_creation(start, ticks):
    try:
        parsed = datetime.fromisoformat(start)
        if parsed.tzinfo is None:
            raise ValueError()
        delta = parsed.astimezone(timezone.utc)-datetime(1601,1,1,tzinfo=timezone.utc)
        lower = ((delta.days*86400+delta.seconds)*1_000_000+delta.microseconds)*10
        if type(ticks) is not int or not lower <= ticks <= lower+9:
            raise ValueError()
    except (ValueError, TypeError, OverflowError):
        fail('run_history_unverifiable')


def parse_mod_config(argv, expected_game, expected_config):
    if (not isinstance(argv, (list, tuple)) or not 1 <= len(argv) <= 64
            or any(not isinstance(arg,str) or len(arg)>32767 or '\x00' in arg for arg in argv)
            or Path(argv[0]) != Path(expected_game)):
        fail('session_probe_invalid')
    switches = [i for i, arg in enumerate(argv) if arg.lower().startswith('-modconfig')]
    if len(switches) != 1:
        fail('session_scope_unsupported')
    index = switches[0]
    if (argv[index].lower() != '-modconfig' or index+1 >= len(argv)
            or not Path(argv[index+1]).is_absolute() or Path(argv[index+1]) != Path(expected_config)):
        fail('session_scope_unsupported')
    return Path(argv[index+1])


def validate_mod_file(config, big):
    try:
        lines = [line.strip() for line in Path(config).read_text(encoding='utf-8-sig').splitlines() if line.strip()]
        if len(lines)!=2 or lines[0].lower()!='mod-game 1.12':
            fail('discovery_policy_invalid')
        match = re.fullmatch(r'(?i)add-big\s+(?:"([^"\r\n]+)"|([^\s]+))',lines[1])
        if match is None:
            fail('discovery_policy_invalid')
        name = next(value for value in match.groups() if value is not None)
        if Path(name).name != name or Path(name).is_absolute() or Path(config).parent/name != Path(big):
            fail('discovery_policy_invalid')
    except (OSError, UnicodeError, ValueError):
        fail('discovery_policy_invalid')


def load_policy(state_dir):
    """The installed discovery policy written by beta_setup."""
    path=_local_path(Path(state_dir)/NAME)
    record,_=read_object(path,16384)
    from .beta_setup import load_policy as installed_policy
    return installed_policy(state_dir,record)


class PROCESSENTRY32W(c.Structure):
    _fields_=[('dwSize',w.DWORD),('cntUsage',w.DWORD),('th32ProcessID',w.DWORD),
              ('th32DefaultHeapID',c.c_size_t),('th32ModuleID',w.DWORD),('cntThreads',w.DWORD),
              ('th32ParentProcessID',w.DWORD),('pcPriClassBase',w.LONG),('dwFlags',w.DWORD),
              ('szExeFile',w.WCHAR*260)]


class UNICODE_STRING(c.Structure):
    _fields_=[('Length',w.USHORT),('MaximumLength',w.USHORT),('Buffer',c.c_void_p)]


class Win32ReadOnly:
    """Only fixed-name process enumeration, identity and bounded command-line reads."""
    def __init__(self):
        if os.name!='nt':
            fail('session_discovery_unavailable')
        self.k=c.WinDLL('kernel32',use_last_error=True)
        self.nt=c.WinDLL('ntdll');self.shell=c.WinDLL('shell32',use_last_error=True)
        self.k.CreateToolhelp32Snapshot.argtypes=[w.DWORD,w.DWORD];self.k.CreateToolhelp32Snapshot.restype=w.HANDLE
        for name in ('Process32FirstW','Process32NextW'):
            function=getattr(self.k,name);function.argtypes=[w.HANDLE,c.POINTER(PROCESSENTRY32W)];function.restype=w.BOOL
        self.k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];self.k.OpenProcess.restype=w.HANDLE
        self.k.CloseHandle.argtypes=[w.HANDLE];self.k.CloseHandle.restype=w.BOOL
        self.k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)];self.k.QueryFullProcessImageNameW.restype=w.BOOL
        self.k.GetProcessTimes.argtypes=[w.HANDLE,*[c.POINTER(w.FILETIME)]*4];self.k.GetProcessTimes.restype=w.BOOL
        self.nt.NtQueryInformationProcess.argtypes=[w.HANDLE,w.ULONG,c.c_void_p,w.ULONG,c.POINTER(w.ULONG)]
        self.nt.NtQueryInformationProcess.restype=w.LONG
        self.shell.CommandLineToArgvW.argtypes=[w.LPCWSTR,c.POINTER(c.c_int)]
        self.shell.CommandLineToArgvW.restype=c.POINTER(w.LPWSTR)
        self.k.LocalFree.argtypes=[c.c_void_p];self.k.LocalFree.restype=c.c_void_p

    def process_ids(self, executable_name):
        handle=self.k.CreateToolhelp32Snapshot(2,0)
        if handle in (None,0,c.c_void_p(-1).value):
            fail('session_discovery_unavailable')
        try:
            row=PROCESSENTRY32W();row.dwSize=c.sizeof(row)
            present=self.k.Process32FirstW(handle,c.byref(row));result=[];count=0
            while present:
                count+=1
                if count>65536:
                    fail('session_discovery_unavailable')
                if row.szExeFile.casefold()==executable_name.casefold():
                    result.append(int(row.th32ProcessID))
                present=self.k.Process32NextW(handle,c.byref(row))
            # FALSE is also returned for enumeration errors. A partial/failed
            # snapshot cannot attest absence of an old Host or Game process.
            if c.get_last_error()!=18:fail('session_discovery_unavailable')  # ERROR_NO_MORE_FILES
            return result
        finally:
            self.k.CloseHandle(handle)

    def creation_filetime(self,handle):
        times=[w.FILETIME() for _ in range(4)]
        if not self.k.GetProcessTimes(handle,*[c.byref(value) for value in times]):
            fail('session_probe_unavailable')
        return int(times[0].dwHighDateTime)<<32|int(times[0].dwLowDateTime)

    def command_line(self,handle):
        required=w.ULONG()
        self.nt.NtQueryInformationProcess(handle,60,None,0,c.byref(required))
        if not c.sizeof(UNICODE_STRING)<=required.value<=65536:
            fail('session_probe_unavailable')
        buffer=c.create_string_buffer(required.value);capacity=required.value
        status=self.nt.NtQueryInformationProcess(handle,60,buffer,capacity,c.byref(required))
        if status!=0 or required.value>capacity:
            fail('session_probe_unavailable')
        value=UNICODE_STRING.from_buffer(buffer);base=c.addressof(buffer)
        if (value.Length%2 or value.Length>value.MaximumLength or value.Length>65532 or not value.Buffer
                or not base<=value.Buffer or value.Buffer+value.Length>base+capacity):
            fail('session_probe_invalid')
        try:
            text=c.string_at(value.Buffer,value.Length).decode('utf-16-le')
        except UnicodeError:
            fail('session_probe_invalid')
        if not text or '\x00' in text:
            fail('session_probe_invalid')
        return text

    def argv(self,command_line):
        count=c.c_int();pointer=self.shell.CommandLineToArgvW(command_line,c.byref(count))
        if not pointer:
            fail('session_probe_invalid')
        try:
            if not 1<=count.value<=64:
                fail('session_probe_invalid')
            return [pointer[index] for index in range(count.value)]
        finally:
            self.k.LocalFree(c.cast(pointer,c.c_void_p))

    def inspect_process(self,pid,expected_game):
        handle=self.k.OpenProcess(0x1000,False,pid)
        if not handle:
            return None
        try:
            path=c.create_unicode_buffer(32768);size=w.DWORD(len(path))
            if not self.k.QueryFullProcessImageNameW(handle,0,path,c.byref(size)):
                fail('session_probe_unavailable')
            executable=Path(path.value)
            if executable!=expected_game:
                return None
            ticks=self.creation_filetime(handle)
            argv=self.argv(self.command_line(handle))
            return executable,ticks,argv
        finally:
            self.k.CloseHandle(handle)


def dependencies():
    from .desktop_backend import _module
    memory=_module('observe_production',ROOT/'production').Memory
    native=_module('read_selected_personality',ROOT/'native-ai')
    participants=_module('match_participants',ROOT/'integration')
    starts=_module('public_start_waypoints',ROOT/'native-ai')
    return SimpleNamespace(Memory=memory,snapshot=_module('read_match_state',ROOT/'native-ai').snapshot,
        inspect_player=native.inspect_player,resolve_registry=native.resolve_registry,
        verify_participants=participants.verify_participants,
        controlled_match_result=participants.controlled_match_result,
        public_start_waypoints=starts.public_start_waypoints,owned_object_points=starts.owned_object_points,
        own_census=_module('macro_observation',ROOT/'native-ai').own_census)


def allied_starts(readers,memory,logic,players,participants,starts):
    """Start waypoints of allied combatants (shared vision), by majority of their objects."""
    result=[]
    for row in participants['participants']:
        if row['relation']!='ally':continue
        address=memory.u32(players+0x30+4*row['player_id'])
        name=start_by_vote(readers.owned_object_points(memory,logic,address),starts)
        if name is not None:result.append(name)
    return tuple(result)


class NativeAdapter:
    def __init__(self,policy,*,win32=None,readers=None):
        self.policy=policy;self._win32=win32;self._readers=readers

    @property
    def win32(self):
        if self._win32 is None:self._win32=Win32ReadOnly()
        return self._win32

    def enumerate_processes(self):
        result=[]
        for pid in self.win32.process_ids(self.policy.files.game.name):
            identity=self.win32.inspect_process(pid,self.policy.files.game)
            if identity is None:continue
            executable,ticks,argv=identity
            config=parse_mod_config(argv,self.policy.files.game,self.policy.files.mod_config)
            result.append(ProcessIdentity(pid,ticks,creation_start(ticks),executable,config))
        return result

    def probe_match(self,process,policy):
        readers=self._readers
        if readers is None:readers=dependencies()
        seed=dict(pid=process.pid,start_time=process.start_time,game=str(policy.files.game),
                  process_creation_filetime=process.creation_filetime,mod_sha256=policy.files.mod_sha256)
        memory=None
        try:
            memory=readers.Memory(process.pid,seed)
            if Path(memory.path)!=policy.files.game or self.win32.creation_filetime(memory.handle)!=process.creation_filetime:
                fail('session_changed')
            for address,expected in PINS.items():
                if memory.read(address,len(expected))!=expected:
                    fail('session_probe_invalid')
            state=readers.snapshot(memory.read)
            logic=memory.u32(0xcd8ce4)
            if (not logic or memory.u32(logic)!=0xbeb630 or state.get('game_logic')!=hex(logic)
                    or type(state.get('simulation_frame')) is not int or state['simulation_frame']<=0):
                fail('session_not_ready')
            seat=policy.player_id
            players=memory.u32(0xce8c9c);owner=memory.u32(players+0x30+4*seat)
            native=readers.inspect_player(memory.read,owner)
            registry,digest=read_object(policy.files.registry)
            if digest!=policy.files.registry_sha256:
                fail('discovery_source_changed')
            resolved=readers.resolve_registry(native,registry,seed)
            if (resolved.get('commander_id')!=policy.commander_id or resolved.get('personality_binding_verified') is not True
                    or resolved.get('side')!=policy.faction or native.get('player_index')!=seat
                    or native.get('store_membership_verified') is not True or native.get('side_matches_player') is not True):
                fail('session_scope_unsupported')
            pointer=memory.u32(logic+0x98);raw=memory.read(pointer,260)
            if b'\x00' not in raw:fail('session_probe_invalid')
            path=PureWindowsPath(raw.split(b'\x00',1)[0].decode('ascii'))
            # Every RA3 map lives in a folder of its own name: <name>\<name>.map.
            map_id=path.stem.lower()
            if path.suffix.lower()!='.map' or path.parent.name.lower()!=map_id:
                fail('session_scope_unsupported')
            participants=readers.verify_participants(memory,state,registry,seat)
            if participants.get('participants_verified') is not True or participants.get('model_player_id')!=seat:
                fail('session_scope_unsupported')
            stable=('instance_id','personality_wrapper','personality_data','player_template','ai_player','player_index')
            if any(not isinstance(native.get(key),str) for key in stable if key!='player_index'):
                fail('session_probe_invalid')
            census=readers.own_census(memory,owner)
            if census.get('enemy_details_read') is not False:fail('session_probe_invalid')
            own_point=own_base_point(census)
            starts=readers.public_start_waypoints(memory.read)
            scenario=derive_scenario(map_id=map_id,model_player_id=seat,participants=participants['participants'],
                alliances=participants['alliances'],own_point=own_point,starts=starts,
                allied_starts=allied_starts(readers,memory,logic,players,participants,starts),
                model_faction=resolved['side'])
            after=readers.snapshot(memory.read);identity_after=readers.inspect_player(memory.read,owner)
            if (type(census.get('frame')) is not int or not state['simulation_frame']<=census['frame']<=after['simulation_frame']
                    or memory.u32(0xcd8ce4)!=logic or memory.u32(0xce8c9c)!=players or memory.u32(players+0x30+4*seat)!=owner
                    or after.get('game_logic')!=hex(logic) or not 0<=after['simulation_frame']-state['simulation_frame']<=15
                    or any(identity_after.get(key)!=native.get(key) for key in stable)
                    or identity_after.get('store_membership_verified') is not True or identity_after.get('side_matches_player') is not True
                    or self.win32.creation_filetime(memory.handle)!=process.creation_filetime):
                fail('session_changed')
            facts=dict(pid=process.pid,creation_filetime=process.creation_filetime,logic=logic,owner=owner,
                       personality={key:native.get(key) for key in stable})
            instance=hashlib.sha256(canonical_json(facts).encode('utf8')).hexdigest()
            ended=any(readers.controlled_match_result(value,seat,scenario.enemy_player_ids,
                                                      participant_ids=scenario.player_ids)['terminal']
                      for value in (state,after))
            return MatchObservation(process.pid,process.creation_filetime,instance,resolved['commander_id'],
                policy.native_epoch,scenario.to_public_dict(),True,
                paused=bool(state.get('pause_flag_candidate')) or bool(after.get('pause_flag_candidate')),ended=bool(ended))
        except ContractError:
            raise
        except (OSError,ValueError,TypeError,KeyError,RuntimeError,UnicodeError):
            fail('session_probe_unavailable')
        finally:
            if memory is not None:memory.close()


def run_records(backend):
    """One RunRecord per launch, from the backend's own status projection.

    Archived launches (from before the last runtime change, when no game was
    running) are finished history: they never block a new match.
    """
    try:
        result=[]
        for row in backend._db.execute('SELECT * FROM launches ORDER BY rowid').fetchall():
            binding=SessionBinding.from_dict(json.loads(row['binding_json']))
            status=backend._status(row)
            if status.get('run_id')!=row['run_id'] or status.get('session_id')!=binding.session_id:
                fail('run_history_unverifiable')
            if status.get('history_archived') is True:
                result.append(RunRecord(row['run_id'],status['state'],True,0,binding.game_process_id,None,None,
                                        native_delivery_attempted=False,
                                        history_protocol='archived_before_runtime_change'))
                continue
            session,_=read_object(_local_path(Path(row['session_path'])))
            ticks=session.get('process_creation_filetime')
            if (session.get('session_id')!=binding.session_id or session.get('pid')!=binding.game_process_id
                    or type(session.get('pid')) is not int or session.get('start_time')!=binding.game_process_start
                    or session.get('mod_sha256')!=binding.mod_sha256):
                fail('run_history_unverifiable')
            require_creation(binding.game_process_start,ticks)
            released=status.get('native_release_verified') is True
            unresolved=backend.journal.unresolved(row['run_id'])
            if released and unresolved:
                # Uncertain deliveries before a verified return are settled:
                # the native settings were read back restored. Never retried.
                from .native_lifecycle import unknown_before_stop
                stop=backend.journal.get_command(row['run_id'],'macro-stop')
                if unknown_before_stop(backend.journal,row['run_id'],stop) is not None:unresolved=[]
            result.append(RunRecord(row['run_id'],status['state'],released,len(unresolved),binding.game_process_id,
                                    ticks,PROTOCOL,
                                    native_delivery_attempted=status.get('no_native_execution_started') is not True))
        return result
    except ContractError:
        fail('run_history_unverifiable')
    except Exception:
        fail('run_history_unverifiable')


class RefusedDiscovery:
    def __init__(self,code):self.code=code
    def discover(self,*args):fail(self.code)
    def prepare(self,*args):fail(self.code)
    def close(self):pass


def create_discovery(backend):
    path=Path(backend.state_dir)/NAME
    try:
        if not path.exists() and not path.is_symlink():return None
        _,policy=load_policy(backend.state_dir)
        current=load_root(backend.state_dir)
        if current is not None and Path(current['session_root'])!=policy.session_root:
            fail('session_root_conflict')
        adapter=NativeAdapter(policy)
        return SessionDiscovery(policy,adapter.enumerate_processes,adapter.probe_match,
            lambda session,bundle:register_session_source(backend.store,policy.session_root,session,
                                                          macro_bundle=bundle,replace_stopped=True),
            lambda:run_records(backend))
    except ContractError as error:
        allowed={'discovery_policy_invalid','discovery_source_changed','discovery_source_unavailable',
                 'session_root_conflict','session_root_invalid','session_scope_unsupported'}
        return RefusedDiscovery(error.code if error.code in allowed else 'discovery_policy_invalid')
    except Exception:
        return RefusedDiscovery('discovery_policy_invalid')
