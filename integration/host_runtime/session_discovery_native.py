"""Fixed-policy Win32 discovery. No game launch, injection, process write or model call.

Only the explicit native CLI installs policy paths. WebView requests can select
an opaque broker candidate; a candidate still needs the normal live admission.
Importing this module, registering a policy and constructing the factory do not
read a game process. Native reads occur only in the adapter's discover/probe calls.
"""
from __future__ import annotations

import argparse
import ctypes as c
from ctypes import wintypes as w
from dataclasses import asdict, fields
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
from types import SimpleNamespace
import uuid

from .contracts import ContractError, SessionBinding, canonical_json, identifier, object_fields, sha256
from .desktop_session_registry import load_root, register_root, register_session_source
from .macro_bundle import load_bundle
from .macro_policy_runtime import COMMANDER
from .session_discovery import (DiscoveryPolicy, MatchObservation, ProcessIdentity, RunRecord,
                                SessionDiscovery, TrustedFiles, TERMINAL, _digest, _local_path)

ROOT = Path(__file__).resolve().parents[2]
NAME = 'session-discovery-policy.json'
KIND = 'trusted_macro_session_discovery_policy'
GAME_SHA = 'ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
PINS = {0x8d5727: bytes.fromhex('89beb0080000'), 0x844a3f: bytes.fromhex('898690000000')}
SCOPE = dict(commander_id=COMMANDER, origin_region='region_8_3', map_id='map_mp_2_black1b',
             display_map='TemplePrime', faction='Soviet', player_id=3, opponent_player_id=4,
             observer_player_id=2, candidate_ttl_seconds=90)


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
    """Bounded metadata only; capability admission still uses load_bundle."""
    value,digest=read_object(path,2*1024*1024)
    version=value.get('schema_version')
    if type(version) is int and version==14:
        from .native6_qualification import load
        return load(path)[0],digest
    if type(version) is int and version==13:
        from .strategic_unified_bundle_v5 import header
        header(value)
        return value,digest
    if type(version) is int and version==12:
        from . import macro_catalog_bundle_v12 as catalog
        if set(value)!=catalog.FIELDS or value.get('kind')!=catalog.KIND:fail('discovery_policy_invalid')
        # Explicit schema12 descriptors, never a generic old-schema upgrade.
        catalog._header(value)
        return value,digest
    if type(version) is not int or version not in (1,2,3,4,5,6,7,8,9,10,11):fail('discovery_policy_invalid')
    if (version in (10,11) and value.get('kind')!=('verified_macro_fixed_consumer_bootstrap' if version==11
            else 'verified_macro_expansion_bootstrap')):fail('discovery_policy_invalid')
    maximum=2*1024*1024 if version in (10,11) else 65536 if version==9 else 49152 if version==8 else 32768
    if Path(path).stat().st_size>maximum:fail('discovery_policy_invalid')
    return value,digest


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


def source_fields(session_path, bundle_path, root, *, qualify):
    session_path, bundle_path, root = (_local_path(session_path), _local_path(bundle_path),
                                       _local_path(root,directory=True))
    if not all(path.is_relative_to(root) for path in (session_path,bundle_path)):
        fail('discovery_policy_invalid')
    session, session_digest = read_object(session_path)
    scenario = session.get('scenario')
    if (not isinstance(scenario,dict) or scenario.get('commander_id')!=COMMANDER
            or scenario.get('computer_player_index')!=3 or type(scenario.get('computer_player_index')) is not int
            or scenario.get('opponent_player_index')!=4 or type(scenario.get('opponent_player_index')) is not int
            or scenario.get('observer_player_index',2)!=2 or type(scenario.get('observer_player_index',2)) is not int
            or scenario.get('participant_count')!=2 or type(scenario.get('participant_count')) is not int
            or scenario.get('map_id')!=SCOPE['map_id'] or Path(session.get('run_directory',''))!=session_path.parent):
        fail('discovery_policy_invalid')
    identifier(session.get('session_id'))
    require_creation(session.get('start_time'),session.get('process_creation_filetime'))
    if type(session.get('pid')) is not int or session['pid']<=0:
        fail('discovery_policy_invalid')
    paths = {key:_local_path(session.get(key,'')) for key in ('game','mod_config','mod_big','registry')}
    paths['macro_bundle']=bundle_path
    paths['package_report']=_local_path(session.get('macro_package_report',''))
    if paths['game'].name.lower()!='ra3_1.12.game' or _digest(paths['game'])!=GAME_SHA:
        fail('discovery_policy_invalid')
    validate_mod_file(paths['mod_config'],paths['mod_big'])
    if _digest(paths['mod_big'])!=session.get('mod_sha256'):
        fail('discovery_source_changed')
    registry,_ = read_object(paths['registry'])
    if registry.get('compiled_ids_verified') is not True or registry.get('package_sha256')!=session['mod_sha256']:
        fail('discovery_policy_invalid')
    commanders=[row for row in registry.get('commanders',[]) if isinstance(row,dict) and row.get('id')==COMMANDER]
    if len(commanders)!=1 or not any(isinstance(row,dict) and row.get('side')=='Soviet'
                                    for row in commanders[0].get('assets',[])):
        fail('discovery_policy_invalid')
    package,_=read_object(paths['package_report'])
    if (package.get('compiled') is not True or package.get('big_sha256')!=session['mod_sha256']
            or package.get('commander_id')!=COMMANDER):
        fail('discovery_policy_invalid')
    assets=[row for row in commanders[0].get('assets',[]) if isinstance(row,dict) and row.get('side')=='Soviet']
    if len(assets)!=1:
        fail('discovery_policy_invalid')
    compiled=[row for row in package.get('assets',[]) if isinstance(row,dict)
              and row.get('name')=='AIPersonalityDefinition:'+str(assets[0].get('asset_id'))]
    try:
        if (len(compiled)!=1 or assets[0].get('asset_id')!=package.get('personality')
                or int(compiled[0]['instance_id'],0)!=int(assets[0]['instance_id'],0)):
            fail('discovery_policy_invalid')
    except (ValueError,TypeError,KeyError):
        fail('discovery_policy_invalid')
    bundle,_=read_macro_bundle(bundle_path)
    manifest_path=_local_path(Path(bundle.get('build',''))/'build-manifest.json')
    expected=bundle.get('pins',{}).get(str(manifest_path))
    if _digest(manifest_path)!=expected:
        fail('discovery_source_changed')
    manifest,_=read_object(manifest_path)
    epoch=native_epoch(manifest)
    if type(epoch) is not int or epoch<=0 or manifest.get('package_sha256')!=session['mod_sha256']:
        fail('discovery_policy_invalid')
    if qualify:
        _, scope=load_bundle(bundle_path,session)
        if (getattr(scope,'required_origin_region',None)!=SCOPE['origin_region']
                or scope.package_sha256!=session['mod_sha256']):
            fail('session_scope_unsupported')
    values={}
    for key,path in paths.items():
        values[key]=path
        values['mod_sha256' if key=='mod_big' else key+'_sha256']=_digest(path)
    return session, session_digest, TrustedFiles(**values), epoch


def policy_record(session_path, bundle_path, state_dir, session_root):
    _local_path(state_dir,directory=True)
    _,digest,files,epoch=source_fields(session_path,bundle_path,session_root,qualify=True)
    record=dict(schema_version=1,kind=KIND,policy_id=str(uuid.uuid4()),session_root=str(session_root),
                source_session=str(session_path),source_session_sha256=digest,
                files={key:str(value) if isinstance(value,Path) else value for key,value in asdict(files).items()},
                scope=dict(SCOPE,native_epoch=epoch))
    return record


def load_policy(state_dir):
    path=_local_path(Path(state_dir)/NAME)
    record,_=read_object(path,16384)
    if type(record.get('schema_version')) is int and record['schema_version']==2:
        from .beta_setup import load_policy as installed_policy
        return installed_policy(state_dir,record)
    object_fields(record,{'schema_version','kind','policy_id','session_root','source_session',
                          'source_session_sha256','files','scope'})
    if record['schema_version']!=1 or type(record['schema_version']) is not int or record['kind']!=KIND:
        fail('discovery_policy_invalid')
    identifier(record['policy_id']);sha256(record['source_session_sha256'])
    object_fields(record['files'],{field.name for field in fields(TrustedFiles)})
    object_fields(record['scope'],set(SCOPE)|{'native_epoch'})
    if any(record['scope'].get(key)!=value or type(record['scope'].get(key)) is not type(value) for key,value in SCOPE.items()):
        fail('discovery_policy_invalid')
    _,digest,files,epoch=source_fields(Path(record['source_session']),Path(record['files']['macro_bundle']),
                                      Path(record['session_root']),qualify=False)
    expected={key:str(value) if isinstance(value,Path) else value for key,value in asdict(files).items()}
    if record['files']!=expected or record['source_session_sha256']!=digest or record['scope']['native_epoch']!=epoch:
        fail('discovery_source_changed')
    policy=DiscoveryPolicy(files,Path(record['session_root']),Path(state_dir),**record['scope'])
    return record,policy


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
    return SimpleNamespace(Memory=memory,snapshot=_module('read_match_state',ROOT/'native-ai').snapshot,
        inspect_player=native.inspect_player,resolve_registry=native.resolve_registry,
        verify_two_ai=_module('match_participants',ROOT/'integration').verify_two_ai,
        own_census=_module('macro_observation',ROOT/'native-ai').own_census)


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
            players=memory.u32(0xce8c9c);owner=memory.u32(players+0x30+4*3)
            native=readers.inspect_player(memory.read,owner)
            registry,digest=read_object(policy.files.registry)
            if digest!=policy.files.registry_sha256:
                fail('discovery_source_changed')
            resolved=readers.resolve_registry(native,registry,seed)
            if (resolved.get('commander_id')!=policy.commander_id or resolved.get('personality_binding_verified') is not True
                    or resolved.get('side')!='Soviet' or native.get('player_index')!=3
                    or native.get('store_membership_verified') is not True or native.get('side_matches_player') is not True):
                fail('session_scope_unsupported')
            participants=readers.verify_two_ai(memory,state,registry,3,4,2)
            if any(participants.get(key) is not True for key in ('two_ai_combatants_verified','mutual_enemy_relationship_verified',
                                                               'observer_separate_from_combatants','opponent_native_ai_verified')):
                fail('session_scope_unsupported')
            pointer=memory.u32(logic+0x98);raw=memory.read(pointer,260)
            if b'\x00' not in raw:fail('session_probe_invalid')
            path=PureWindowsPath(raw.split(b'\x00',1)[0].decode('ascii'))
            if path.suffix.lower()!='.map' or path.stem.lower()!=policy.map_id or path.parent.name.lower()!=policy.map_id:
                fail('session_scope_unsupported')
            stable=('instance_id','personality_wrapper','personality_data','player_template','ai_player','player_index')
            if any(not isinstance(native.get(key),str) for key in stable if key!='player_index'):
                fail('session_probe_invalid')
            census=readers.own_census(memory,owner)
            if census.get('enemy_details_read') is not False:fail('session_probe_invalid')
            yards=[row for row in census.get('own_objects',[]) if row.get('type_hash')=='0xc16ff13f'
                   and type(row.get('hp')) in (int,float) and math.isfinite(row['hp']) and row['hp']>0]
            if len(yards)!=1:fail('session_scope_unsupported')
            point=yards[0].get('xyz',[])
            if len(point)!=3 or any(type(value) not in (int,float) or not math.isfinite(value) for value in point):
                fail('session_probe_invalid')
            origin='region_'+str(int(point[0]//512))+'_'+str(int(point[1]//512))
            if origin!=policy.origin_region:fail('session_scope_unsupported')
            after=readers.snapshot(memory.read);identity_after=readers.inspect_player(memory.read,owner)
            if (type(census.get('frame')) is not int or not state['simulation_frame']<=census['frame']<=after['simulation_frame']
                    or memory.u32(0xcd8ce4)!=logic or memory.u32(0xce8c9c)!=players or memory.u32(players+0x30+12)!=owner
                    or after.get('game_logic')!=hex(logic) or not 0<=after['simulation_frame']-state['simulation_frame']<=15
                    or any(identity_after.get(key)!=native.get(key) for key in stable)
                    or identity_after.get('store_membership_verified') is not True or identity_after.get('side_matches_player') is not True
                    or self.win32.creation_filetime(memory.handle)!=process.creation_filetime):
                fail('session_changed')
            facts=dict(pid=process.pid,creation_filetime=process.creation_filetime,logic=logic,owner=owner,
                       personality={key:native.get(key) for key in stable})
            instance=hashlib.sha256(canonical_json(facts).encode('utf8')).hexdigest()
            ended=any(row.get(key) for value in (state,after) for row in value.get('result_records',[])
                      for key in ('victory_frame','defeat_frame','quit_frame'))
            return MatchObservation(process.pid,process.creation_filetime,instance,policy.map_id,resolved['side'],3,4,2,
                resolved['commander_id'],origin,policy.native_epoch,True,
                paused=bool(state.get('pause_flag_candidate')) or bool(after.get('pause_flag_candidate')),ended=bool(ended))
        except ContractError:
            raise
        except (OSError,ValueError,TypeError,KeyError,RuntimeError,UnicodeError):
            fail('session_probe_unavailable')
        finally:
            if memory is not None:memory.close()


def native_epoch(manifest):
    from .native6_runtime_contract import FIELD_KIND
    if (manifest.get('kind')==FIELD_KIND and type(manifest.get('protocol_version')) is int
            and manifest['protocol_version']==6 and manifest.get('admission_ready') is True and manifest.get('compile_only') is False):return 6
    if (manifest.get('kind')=='strategic_unified_transport_v5_candidate' and type(manifest.get('protocol_version')) is int
            and manifest['protocol_version']==5 and manifest.get('admission_ready') is True and manifest.get('compile_only') is False):
        # Fixed protocol identity for history; never permits same-PID reattach.
        return 5
    return manifest.get('epoch')

def frozen_manifest(row,session,binding):
    if (Path(row['output_path'])/'native6-context.json').exists():
        from .native6_lifecycle import context
        return context(row,session,binding)[1]
    output=_local_path(Path(row['output_path']),directory=True)
    source_root=_local_path(output/'source',directory=True)
    record,_=read_object(_local_path(output/'sources.json'))
    sources=record.get('sources')
    if record.get('kind')!='pre_execution_macro_host_sources' or not isinstance(sources,list) or len(sources)<3:
        fail('run_history_unverifiable')
    for index,source in enumerate(sources[:3]):
        if (not isinstance(source,dict) or set(source)!={'path','copy','sha256'}
                or not isinstance(source['copy'],str) or Path(source['copy']).name!=source['copy']
                or not Path(source['path']).is_absolute() or source['copy']!=str(index)+'-'+Path(source['path']).name):
            fail('run_history_unverifiable')
        sha256(source['sha256'])
        if _digest(_local_path(source_root/source['copy']))!=source['sha256']:
            fail('run_history_unverifiable')
    if (Path(sources[0]['path']).name!='macro_host.py' or Path(sources[1]['path'])!=Path(row['session_path'])
            or sources[1]['sha256']!=_digest(Path(row['session_path']))):
        fail('run_history_unverifiable')
    bundle,_=read_macro_bundle(output/'source'/sources[2]['copy'])
    if type(bundle.get('schema_version')) is int and bundle['schema_version']==12:
        from .macro_catalog_bundle_v12 import KIND as CATALOG_KIND
        if bundle.get('kind')!=CATALOG_KIND:fail('run_history_unverifiable')
        base=_local_path(Path(bundle['base_bundle']));base_rows=[r for r in sources if Path(r['path']).resolve()==base]
        if (len(base_rows)!=1 or base_rows[0]['sha256']!=bundle['pins'].get(str(base))
                or _digest(base)!=base_rows[0]['sha256']):fail('run_history_unverifiable')
        archived,_=read_object(source_root/base_rows[0]['copy'],2*1024*1024)
        if (type(archived.get('schema_version')) is not int or archived['schema_version']!=11
                or archived.get('kind')!='verified_macro_fixed_consumer_bootstrap'):fail('run_history_unverifiable')
    elif not isinstance(bundle.get('kind'),str) or not bundle['kind'].startswith('verified_macro_') or not bundle['kind'].endswith('_bootstrap'):
        fail('run_history_unverifiable')
    manifest_path=_local_path(Path(bundle.get('build',''))/'build-manifest.json')
    if _digest(manifest_path)!=bundle.get('pins',{}).get(str(manifest_path)):
        fail('run_history_unverifiable')
    manifest,_=read_object(manifest_path)
    epoch=native_epoch(manifest)
    if type(epoch) is not int or epoch<=0 or manifest.get('package_sha256')!=binding.mod_sha256:
        fail('run_history_unverifiable')
    return manifest


def frozen_epoch(row,session,binding):return native_epoch(frozen_manifest(row,session,binding))


def run_records(backend):
    try:
        result=[]
        for row in backend._db.execute('SELECT * FROM launches ORDER BY rowid').fetchall():
            binding=SessionBinding.from_dict(json.loads(row['binding_json']))
            session,_=read_object(_local_path(Path(row['session_path'])))
            ticks=session.get('process_creation_filetime')
            if (session.get('session_id')!=binding.session_id or session.get('pid')!=binding.game_process_id or type(session.get('pid')) is not int
                    or session.get('start_time')!=binding.game_process_start or session.get('mod_sha256')!=binding.mod_sha256):
                fail('run_history_unverifiable')
            status=backend._status(row)
            if status.get('run_id')!=row['run_id'] or status.get('session_id')!=binding.session_id:
                fail('run_history_unverifiable')
            metadata={};start=None
            if hasattr(backend.journal,'get_command') and 'request_id' in row.keys():
                start=backend.journal.get_command(row['run_id'],row['request_id'])
            if start is not None and status.get('no_native_execution_started') is True:
                receipt=start.get('receipt')or{}
                if (start.get('operation')!='host_start' or start.get('status')!='cancelled'
                        or receipt.get('reason_code')!='host_launch_cancelled_before_dispatch'
                        or receipt.get('host_spawn_attempted') is not False or receipt.get('native_delivery_attempted') is not False
                        or len(backend.journal.commands_for_run(row['run_id']))!=1
                        or backend.journal.unresolved(row['run_id'])):fail('run_history_unverifiable')
                epoch=None
                metadata=dict(history_protocol='trusted_never_dispatched_host_v1',original_process_start=binding.game_process_start,
                    history_review_sha256=hashlib.sha256(canonical_json(dict(binding=binding.public(),start=start,session=session)).encode()).hexdigest())
                if ticks is not None:require_creation(binding.game_process_start,ticks)
            elif start is not None and (start.get('payload')or{}).get('capabilities',{}).get('native_macro') is not True:
                from .session_history_review import validate_review,PROTOCOL
                _,review_sha=validate_review(backend,row,binding,session)
                epoch=None;metadata=dict(history_protocol=PROTOCOL,history_review_sha256=review_sha,
                    original_process_start=binding.game_process_start)
                if ticks is not None:require_creation(binding.game_process_start,ticks)
            else:
                require_creation(binding.game_process_start,ticks)
                epoch=frozen_epoch(row,session,binding)
            unresolved=backend.journal.unresolved(row['run_id']);ownership_count=len(unresolved)
            # Native5's complete return can settle control ownership while its
            # original delivery records remain uncertain. It grants no effect
            # or retry and never qualifies another use of the same process.
            if epoch in (5,6) and status.get('native_release_verified') is True and unresolved:
                from .strategic_unified_unknown_return_v5 import covered_unknown_ownership
                stop=backend.journal.get_command(row['run_id'],'macro-stop')
                if covered_unknown_ownership(unresolved,backend.journal.commands_for_run(row['run_id']),stop):
                    ownership_count=0;metadata['historical_unknown_count']=len(unresolved)
            result.append(RunRecord(row['run_id'],status['state'],status.get('native_release_verified') is True,
                                    ownership_count,binding.game_process_id,ticks,epoch,
                                    native_delivery_attempted=status.get('no_native_execution_started') is not True,**metadata))
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


def register_policy(session,bundle,state_dir,session_root,*,replace_stopped=False):
    session,bundle,state_dir,session_root=map(Path,(session,bundle,state_dir,session_root))
    record=policy_record(session,bundle,state_dir,session_root)
    path=state_dir/NAME
    if path.exists() or path.is_symlink():
        try:
            old,_=read_object(_local_path(path),16384)
            identifier(old.get('policy_id'))
        except ContractError:
            if not replace_stopped:raise
            old=None
        comparable=lambda value:{key:item for key,item in value.items() if key!='policy_id'}
        if old is not None and comparable(old)==comparable(record):
            return dict(schema_version=1,registered=True,policy_id=old['policy_id'],policy_sha256=_digest(path),
                        game_access=False,model_calls=0,credentials_accessed=False,restart_required=True)
        if not replace_stopped:fail('session_registration_conflict')
        from .desktop_backend import DesktopBackend
        # Status/release inspection uses only the explicit state-dir index and
        # bound host identities. No protected connection Library is opened.
        backend=DesktopBackend(SimpleNamespace(state_dir=state_dir))
        try:
            for row in run_records(backend):
                if row.state not in TERMINAL or not row.native_release_verified or row.unresolved_count:
                    fail('run_state_conflict')
        finally:backend.close()
    register_root(session_root,state_dir)
    from .desktop_backend import _atomic
    _atomic(path,record)
    return dict(schema_version=1,registered=True,policy_id=record['policy_id'],policy_sha256=_digest(path),
                game_access=False,model_calls=0,credentials_accessed=False,restart_required=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('session','macro-bundle','state-dir','session-root'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--replace-stopped',action='store_true')
    args=parser.parse_args(argv)
    try:
        result=register_policy(args.session,args.macro_bundle,args.state_dir,args.session_root,
                               replace_stopped=args.replace_stopped)
        print(json.dumps(result,ensure_ascii=True));return 0
    except ContractError as error:
        code=error.code if re.fullmatch(r'[a-z][a-z0-9_]{0,79}',error.code) else 'session_discovery_policy_registration_failed'
        print(json.dumps(dict(registered=False,reason_code=code)));return 2
    except (OSError,ValueError,TypeError,KeyError):
        print(json.dumps(dict(registered=False,reason_code='session_discovery_policy_registration_failed')));return 2


if __name__=='__main__':raise SystemExit(main())
