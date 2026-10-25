"""Bound MF12 loss-of-sight/own-health withdrawal monitor.

No import-time attachment, thread, SDK, game-memory write or outcome certificate.
The sole possible write is 1 to the reviewed MF12 shared retreat_requested word.
Call poll explicitly every 50--100ms; close never changes a shared flag.
Activation is limited to the separately reviewed calibration/formal caller.
"""
import ctypes as c
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import time
import uuid

LIVE_MONITOR_ENABLED = True
ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / 'tactical/mission-formation-v12'
PYTHON_SEAL = '02fe669f36b343e873748d7cb0d144ee017d6733a02eff9168028ab7ec04378b'
NATIVE_SEAL = '7d518ff988b4974bf0494f338cae0730eba817997ce127b7cfd38da2bf8ff9bb'
LAYOUT_SHA = 'e4671ad9f4bd22a8ee9029764b0e20f3ea137277da341548a51e4a3160b00994'
DLL_SHA = '66e26b0e967469d83ba5f92f0e61ba41eb3f8e41a58932cd1a188e14ee192514'
EXE_SHA = 'ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'
TYPES = (0x19ab11af, 0x2c358c61)
MAX_POLL_GAP = .2
MAX_SAMPLE_AGE_MS = 250
CAP = 8192


class RiskError(ValueError):
    pass


class NotReady(RiskError):
    pass


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def integer(value):
    value = int(value, 0) if isinstance(value, str) else value
    if type(value) is not int or not 0 <= value <= 0xffffffff:
        raise RiskError('invalid_u32')
    return value


def ident(words):
    return str(uuid.UUID(bytes=struct.pack('<4I', *words)))


def _static_report(report):
    names = ('session_id', 'executable_sha256', 'package_sha256', 'native_binary_sha256',
             'native_host_sha256', 'native_source_sha256', 'native_shared_sha256',
             'native_revision_sha256', 'native_includes_sha256', 'wrapper_sha256',
             'supplemental_sources', 'native_layout_sha256', 'mission_contract_sha256',
             'preflight', 'request', 'original_entries', 'initial_admission',
             'native_launch_intent_persisted')
    return {name: report.get(name) for name in names}


def source_files(report):
    """Exact frozen execution/source set, without importing a live executor."""
    if sha(FOLDER / 'python-revision.json') != PYTHON_SEAL or sha(FOLDER / 'revision.json') != NATIVE_SEAL:
        raise RiskError('frozen_revision_changed')
    frozen = json.loads((FOLDER / 'python-revision.json').read_text(encoding='utf-8-sig'))
    revision = json.loads((FOLDER / 'revision.json').read_text(encoding='utf-8-sig'))
    files = {ROOT / name.replace('\\', '/'): digest for name, digest in frozen['files'].items()}
    primary = {'native_binary_sha256': FOLDER / 'bin/TacticalMissionFormation12.dll',
               'native_host_sha256': FOLDER / 'bin/tactical_host.exe',
               'native_source_sha256': FOLDER / 'lease.cpp',
               'native_shared_sha256': FOLDER / 'shared.h'}
    for key, path in primary.items():
        if report.get(key) != revision.get(key):
            raise RiskError('compiled_source_mismatch')
        files[path] = revision[key]
    if report.get('native_binary_sha256') != DLL_SHA or report.get('native_revision_sha256') != NATIVE_SEAL:
        raise RiskError('native_version_unapproved')
    includes = revision['native_includes_sha256']
    if report.get('native_includes_sha256') != includes or {x.name for x in FOLDER.glob('*.cpp.inc')} != set(includes):
        raise RiskError('compiled_include_set_changed')
    files.update({FOLDER / name: digest for name, digest in includes.items()})
    local = ['wait_anchor_replan.py', 'retreat_departure.py', 'pending_lineage.py',
             'stance_ownership.py', 'stance_admission.py', 'native_layout.py',
             'mission_contract.py', 'formation_mission_qualification.py', 'inert-layout.json']
    external = ['mobility_guard.py', 'mission_actor_admission_v2.py', 'mission_actor_admission.py',
                'grounded_status_v2.py', 'grounded_status.py', 'ordered-combo/lease.py',
                'ordered_qualification.py', 'combo_qualification.py', 'stop_sequence.py',
                'readonly_disposal.py', 'recon/read_own_command_buttons.py']
    paths = [FOLDER / name for name in includes] + [FOLDER / name for name in local] + [FOLDER.parent / name for name in external]
    supplements = report.get('supplemental_sources', {})
    if not isinstance(supplements, dict) or set(supplements) != {x.name for x in paths}:
        raise RiskError('supplemental_set_changed')
    for path in paths:
        if path in files and files[path] != supplements[path.name]:
            raise RiskError('python_source_revision_mismatch')
        files[path] = supplements[path.name]
    for key, name in [('wrapper_sha256', 'lease.py'), ('native_layout_sha256', 'native_layout.py'), ('mission_contract_sha256', 'mission_contract.py')]:
        if report.get(key) != files[FOLDER / name]:
            raise RiskError('wrapper_source_mismatch')
    files[FOLDER / 'python-revision.json'] = PYTHON_SEAL
    files[FOLDER / 'revision.json'] = NATIVE_SEAL
    for path, digest in files.items():
        if sha(path) != digest:
            raise RiskError('source_file_changed')
    return files


def _load_layout():
    if sha(FOLDER / 'native_layout.py') != LAYOUT_SHA:
        raise RiskError('layout_changed')
    spec = importlib.util.spec_from_file_location('local_risk_frozen_mf12_layout', FOLDER / 'native_layout.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class Header(c.Structure):
        _fields_ = module.Tactical._fields_[:-1]
    module.Header = Header
    if (c.sizeof(Header), c.sizeof(module.Event), c.sizeof(module.Tactical), module.Tactical.events.offset) != (28132, 1616, 13266404, 28132):
        raise RiskError('abi_changed')
    return module


def report_binding(report, session):
    pre, rq, n = report['preflight'], report['request'], report.get('native', {})
    if report.get('native_launch_intent_persisted') is not True:
        raise NotReady('waiting_native_launch_intent')
    if report.get('host_exit') is not None or report.get('status') in ('finished', 'dispatch_failed_native_terminal'):
        raise RiskError('native_host_or_report_terminal')
    if report.get('executable_sha256') != EXE_SHA or report.get('package_sha256') != session.get('mod_sha256'):
        raise RiskError('game_package_changed')
    if pre.get('player_id') != 3 or pre.get('pid') != session.get('pid') or pre.get('session_id') != report.get('session_id') or report['session_id'] != session['session_id']:
        raise RiskError('session_identity_changed')
    if pre.get('commander_id') != session['scenario']['commander_id']:
        raise RiskError('commander_changed')
    if not n.get('issued_frame'):
        raise NotReady('waiting_issued_native_header')
    b = {key: integer(n[key]) for key in ('pid', 'thread', 'callback_thread', 'owner', 'ai', 'logic',
         'personality', 'personality_id', 'player_template', 'start_low', 'start_high', 'issued_frame')}
    if b['pid'] != session['pid'] or b['thread'] != b['callback_thread'] or b['thread'] != pre['window_thread']:
        raise RiskError('native_thread_changed')
    for key in ('owner', 'ai', 'logic', 'personality', 'personality_id', 'player_template'):
        if b[key] != integer(pre[key]):
            raise RiskError('native_owner_changed')
    for key in ('session_id', 'commander_id', 'command_id', 'task_id'):
        value = report['session_id'] if key == 'session_id' else pre['commander_id'] if key == 'commander_id' else rq[key]
        if str(uuid.UUID(value)) != value or n.get(key) != value:
            raise RiskError('native_uuid_changed')
        b[key] = value
    b.update(seq=integer(rq['seq']), token=integer(rq['token']), deadline=integer(rq['expires_frame']), script_team=integer(pre['script_team']))
    if not b['seq'] or not b['token'] or not b['issued_frame'] < b['deadline'] or b['deadline'] - pre['frame'] > 4500:
        raise RiskError('invalid_committed_window')
    if n.get('seq') != b['seq'] or n.get('token') != b['token'] or n.get('mission_deadline_frame') != b['deadline']:
        raise RiskError('native_request_changed')
    b['actors'] = []
    for role, key in enumerate(('selected', 'support')):
        actor = pre[key]
        values = dict(thing=integer(actor['address']), object_id=integer(actor['object_id']), type_hash=integer(actor['type_hash']), update=integer(actor['ai_address']))
        native = dict(thing=n.get('unit'), object_id=n.get('object_id'), type_hash=n.get('type_hash'), update=n.get('update')) if role == 0 else dict(thing=n['support']['thing'], object_id=n['support']['id'], type_hash=n['support']['hash'], update=n['support']['update'])
        if values != native or values['object_id'] != rq['support_id' if role else 'front_id'] or values['type_hash'] != TYPES[role] or not all(values.values()):
            raise RiskError('actor_identity_changed')
        b['actors'].append(values)
    if b['actors'][0]['object_id'] == b['actors'][1]['object_id']:
        raise RiskError('duplicate_actor')
    return b


def check_header(h, b):
    if h.magic != 0x4d463132 or h.version != 12:
        raise RiskError('unsupported_native_namespace')
    if any(getattr(h, key) != b[key] for key in ('pid', 'thread', 'callback_thread', 'owner', 'ai', 'logic', 'personality', 'personality_id', 'player_template', 'start_low', 'start_high', 'issued_frame', 'seq', 'token')):
        raise RiskError('live_native_binding_changed')
    for field, key in (('session', 'session_id'), ('commander', 'commander_id'), ('command', 'command_id'), ('task', 'task_id')):
        if ident(getattr(h, field)) != b[key]:
            raise RiskError('live_native_uuid_changed')
    for role, a in enumerate(b['actors']):
        native = (h.unit, h.object_id, h.type_hash, h.update) if role == 0 else (h.support.thing, h.support.id, h.support.hash, h.support.update)
        if native != (a['thing'], a['object_id'], a['type_hash'], a['update']):
            raise RiskError('live_actor_changed')
    if h.mission_deadline_frame != b['deadline'] or h.overflow or not 0 <= h.count <= CAP:
        raise RiskError('deadline_or_log_changed')


def check_event(e, b, baseline=False):
    role = e.role
    if role not in (0, 1):
        raise RiskError('invalid_event_role')
    a = b['actors'][role]
    if e.unit_id != a['object_id'] or e.owner != b['owner'] or e.thread != b['thread'] or e.mission_deadline_frame != b['deadline'] or not math.isfinite(e.own_hp) or e.own_hp <= 0:
        raise RiskError('event_identity_or_alive_changed')
    w = list(e.stack_words[:68])
    if e.stack_word_count != 68 or w[:2] != [0x53544e31, 1] or w[3:6] != [role, e.frame, e.frame]:
        raise RiskError('stance_raw_shape_changed')
    if w[6:13] != [a['thing'], a['object_id'], a['type_hash'], b['owner'], a['update'], 0xc48670, a['thing']]:
        raise RiskError('event_actor_raw_changed')
    count = w[18]
    if not 1 <= count <= 4 or w[13] == 0 or w[14:16] != [0xc37f90, a['thing']] or not w[16] or not w[17]:
        raise RiskError('event_stance_module_changed')
    enums = w[19:19+count*2:2]
    if not {0, 2} <= set(enums) or len(enums) != len(set(enums)) or any(x > 3 for x in enums) or w[52:56] != [w[13], w[16], w[17], count] or w[19:27] != w[56:64] or w[28] != 0 or w[65] != 1 or w[66] != 0:
        raise RiskError('event_stance_definition_changed')
    if w[29:38] != [e.sm, a['thing'], e.state, e.state_id, w[33], e.sm, e.sm_flags, e.path, e.source]:
        raise RiskError('event_common_view_changed')
    if not baseline and (w[27] != 2 or e.source != 1 or e.team != b['script_team'] or e.mission_stage != 1):
        raise RiskError('event_not_owned_approach')
    if baseline and (e.kind != 71 or e.tag != 0 or e.mission_stage != 0 or e.frame != b['issued_frame'] or w[27] != 0):
        raise RiskError('not_actual_issued_baseline')
    return w


class _WindowsChannel:
    """Only shared-memory access plus read-only process identity/liveness APIs."""
    def __init__(self, binding, layout, session):
        if os.name != 'nt':
            raise RiskError('windows_required')
        from ctypes import wintypes as w
        self.c, self.w, self.layout, self.binding = c, w, layout, binding
        self.k = c.WinDLL('kernel32', use_last_error=True)
        self.mapping = self.view = self.write_view = self.game = self.host = None
        self.written = False
        k = self.k
        k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]; k.OpenProcess.restype = w.HANDLE
        k.CloseHandle.argtypes = [w.HANDLE]; k.CloseHandle.restype = w.BOOL
        k.GetExitCodeProcess.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]; k.GetExitCodeProcess.restype = w.BOOL
        k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)]; k.QueryFullProcessImageNameW.restype = w.BOOL
        k.GetProcessTimes.argtypes = [w.HANDLE] + [c.POINTER(w.FILETIME)]*4; k.GetProcessTimes.restype = w.BOOL
        k.OpenFileMappingW.argtypes = [w.DWORD, w.BOOL, w.LPCWSTR]; k.OpenFileMappingW.restype = w.HANDLE
        k.MapViewOfFile.argtypes = [w.HANDLE, w.DWORD, w.DWORD, w.DWORD, c.c_size_t]; k.MapViewOfFile.restype = c.c_void_p
        k.UnmapViewOfFile.argtypes = [c.c_void_p]; k.UnmapViewOfFile.restype = w.BOOL
        k.GetTickCount.restype = w.DWORD
        try:
            self.game = k.OpenProcess(0x1000 | 0x100000, False, binding['pid'])
            if not self.game or self._image(self.game) != Path(session['game']).resolve() or sha(session['game']) != EXE_SHA:
                raise RiskError('game_process_image_changed')
            times = [w.FILETIME() for _ in range(4)]
            if not k.GetProcessTimes(self.game, *[c.byref(x) for x in times]) or (times[0].dwLowDateTime, times[0].dwHighDateTime) != (binding['start_low'], binding['start_high']):
                raise RiskError('game_process_start_changed')
            self.host = self._find_host()
            self.mapping = k.OpenFileMappingW(6, False, 'Local\\RA3TacticalMissionFormation12_' + str(binding['pid']) + '_' + str(binding['token']))
            if not self.mapping:
                raise RiskError('native_mapping_missing')
            self.view = k.MapViewOfFile(self.mapping, 4, 0, 0, c.sizeof(layout.Tactical))
            if not self.view:
                raise RiskError('native_read_mapping_failed')
        except Exception:
            self.close()
            raise

    def _image(self, handle):
        length = self.w.DWORD(32768); buffer = c.create_unicode_buffer(length.value)
        if not self.k.QueryFullProcessImageNameW(handle, 0, buffer, c.byref(length)):
            raise RiskError('process_image_unavailable')
        return Path(buffer.value).resolve()

    def _command(self, handle):
        class Unicode(c.Structure):
            _fields_ = [('length', c.c_ushort), ('maximum', c.c_ushort), ('buffer', c.c_void_p)]
        nt = c.WinDLL('ntdll').NtQueryInformationProcess
        nt.argtypes = [self.w.HANDLE, c.c_ulong, c.c_void_p, c.c_ulong, c.POINTER(c.c_ulong)]; nt.restype = c.c_long
        size = c.c_ulong(); nt(handle, 60, None, 0, c.byref(size))
        if not c.sizeof(Unicode) < size.value <= 65536:
            raise RiskError('host_command_unavailable')
        buffer = c.create_string_buffer(size.value)
        if nt(handle, 60, buffer, size.value, c.byref(size)) != 0:
            raise RiskError('host_command_unavailable')
        value = Unicode.from_buffer(buffer); pointer = value.buffer or 0; start = c.addressof(buffer)
        if value.length % 2 or not start <= pointer <= pointer + value.length <= start + len(buffer):
            raise RiskError('host_command_bounds')
        command = c.wstring_at(pointer, value.length // 2)
        shell = c.WinDLL('shell32'); shell.CommandLineToArgvW.argtypes = [c.c_wchar_p, c.POINTER(c.c_int)]; shell.CommandLineToArgvW.restype = c.POINTER(c.c_wchar_p)
        count = c.c_int(); args = shell.CommandLineToArgvW(command, c.byref(count))
        if not args:
            raise RiskError('host_command_unavailable')
        self.k.LocalFree.argtypes = [c.c_void_p]
        try:
            return [args[i] for i in range(count.value)]
        finally:
            self.k.LocalFree(args)

    def _find_host(self):
        ps = c.WinDLL('psapi'); ids = (self.w.DWORD * 8192)(); used = self.w.DWORD()
        ps.EnumProcesses.argtypes = [c.POINTER(self.w.DWORD), self.w.DWORD, c.POINTER(self.w.DWORD)]; ps.EnumProcesses.restype = self.w.BOOL
        if not ps.EnumProcesses(ids, c.sizeof(ids), c.byref(used)) or used.value >= c.sizeof(ids):
            raise RiskError('host_inventory_unavailable')
        expected = (FOLDER / 'bin/tactical_host.exe').resolve(); found = []
        try:
            for pid in ids[:used.value // 4]:
                handle = self.k.OpenProcess(0x1000 | 0x100000, False, pid)
                if not handle:
                    continue
                keep = False
                try:
                    if self._image(handle) == expected:
                        args = self._command(handle)
                        if len(args) == 3 and Path(args[0]).resolve() == expected and args[1:] == [str(self.binding['pid']), str(self.binding['token'])]:
                            found.append(handle); keep = True
                except (OSError, RiskError):
                    pass
                finally:
                    if not keep:
                        self.k.CloseHandle(handle)
            if len(found) != 1:
                raise RiskError('bound_native_host_not_unique')
            return found.pop()
        finally:
            for handle in found:
                self.k.CloseHandle(handle)

    def alive(self):
        for handle in (self.game, self.host):
            code = self.w.DWORD()
            if not handle or not self.k.GetExitCodeProcess(handle, c.byref(code)) or code.value != 259:
                return False
        return True

    def tick(self):
        return int(self.k.GetTickCount())

    def header(self):
        return self.layout.Header.from_buffer_copy(c.string_at(self.view, c.sizeof(self.layout.Header)))

    def event(self, index):
        address = self.view + self.layout.Tactical.events.offset + index * c.sizeof(self.layout.Event)
        expected = index + 1
        if c.c_uint32.from_address(address).value != expected:
            raise NotReady('waiting_native_publication')
        block = c.string_at(address, c.sizeof(self.layout.Event))
        if c.c_uint32.from_address(address).value != expected or struct.unpack_from('<I', block)[0] != expected:
            raise NotReady('waiting_native_publication')
        return self.layout.Event.from_buffer_copy(block)

    def request(self):
        if self.written:
            raise RiskError('duplicate_flag_write')
        if not self.write_view:
            self.write_view = self.k.MapViewOfFile(self.mapping, 2, 0, 0, c.sizeof(self.layout.Header))
        if not self.write_view:
            raise RiskError('native_flag_mapping_failed')
        # This module's sole store to mapped memory. Never reset this word.
        c.c_uint32.from_address(self.write_view + self.layout.Tactical.retreat_requested.offset).value = 1
        self.written = True

    def close(self):
        for name in ('write_view', 'view'):
            value = getattr(self, name, None)
            if value:
                self.k.UnmapViewOfFile(value); setattr(self, name, None)
        for name in ('mapping', 'host', 'game'):
            value = getattr(self, name, None)
            if value:
                self.k.CloseHandle(value); setattr(self, name, None)


def _open_channel(binding, layout, session):
    return _WindowsChannel(binding, layout, session)


class MissionRiskMonitor:
    def __init__(self, report_path, session_path, output_path):
        self.report_path = Path(report_path).resolve()
        self.session_path = Path(session_path).resolve()
        self.output_path = Path(output_path).resolve()
        self.channel = self.layout = self.binding = self.log = None
        self.files = {}; self.signatures = {}; self.baseline = {}; self.latest = {}
        self.last_seq = self.last_frame = 0
        self.approach_seen = False
        self.static_digest = self.session_digest = self.report_digest = None
        self.report_signature = None
        self.monitor_digest = sha(__file__)
        self.state = 'candidate_disabled' if not LIVE_MONITOR_ENABLED else 'waiting_report'
        self.reason = None; self.requested = False; self.closed = False; self.last_poll = None
        self.poll_started = None; self.poll_interval = None

    def _result(self, written=False, frame=None):
        return dict(state=self.state, request_written=written, reason=self.reason,
                    observed_frame=frame, request_frame=frame if written else None,
                    native_acknowledged=False, completed=False, effect_verified=False,
                    bound_report_sha256=self.report_digest, monitor_sha256=self.monitor_digest,
                    poll_interval_seconds=self.poll_interval,
                    poll_duration_seconds=time.monotonic()-self.poll_started if self.poll_started is not None else 0)

    def _record(self, event, **facts):
        if self.log is None:
            self.log = self.output_path.open('x', encoding='utf-8')
        record = dict(protocol='local_mission_risk_v1', event=event,
                      monitor_sha256=self.monitor_digest, bound_report_sha256=self.report_digest,
                      session_sha256=self.session_digest, binding_sha256=canonical(self.binding) if self.binding else None,
                      source_report=str(self.report_path), sdk_calls=0, game_memory_writes=0,
                      completion_claim=False, effect_verified=False,
                      poll_interval_seconds=self.poll_interval,
                      poll_duration_seconds=time.monotonic()-self.poll_started if self.poll_started is not None else 0, **facts)
        self.log.write(json.dumps(record, sort_keys=True, allow_nan=False) + '\n'); self.log.flush()
        if event in ('attached', 'retreat_request_intent', 'retreat_flag_written', 'stopped', 'closed'):
            os.fsync(self.log.fileno())

    def _sources(self, force=False):
        if sha(__file__) != self.monitor_digest or sha(self.session_path) != self.session_digest:
            raise RiskError('monitor_or_session_source_changed')
        for path, digest in self.files.items():
            stat = path.stat(); signature = (stat.st_size, stat.st_mtime_ns)
            if force or signature != self.signatures.get(path):
                if sha(path) != digest:
                    raise RiskError('frozen_source_changed')
                self.signatures[path] = signature

    def _report(self):
        stat = self.report_path.stat(); signature = (stat.st_size, stat.st_mtime_ns)
        if signature == self.report_signature:
            return None
        raw = self.report_path.read_bytes(); report = json.loads(raw.decode('utf-8-sig'))
        if self.static_digest is not None and canonical(_static_report(report)) != self.static_digest:
            raise RiskError('bound_report_identity_or_source_changed')
        if report.get('host_exit') is not None or report.get('status') in ('finished', 'dispatch_failed_native_terminal'):
            raise RiskError('native_host_or_report_terminal')
        self.report_signature = signature
        self.report_digest = hashlib.sha256(raw).hexdigest()
        return report

    def _attach(self, report):
        session_raw = self.session_path.read_bytes(); session = json.loads(session_raw.decode('utf-8-sig'))
        if not self.report_path.is_relative_to(Path(session['run_directory']).resolve()):
            raise RiskError('report_outside_bound_run')
        files = source_files(report); binding = report_binding(report, session)
        mission = Path(report['request']['mission_source_path']).resolve()
        if not mission.is_relative_to(Path(session['run_directory']).resolve()):
            raise RiskError('mission_outside_bound_run')
        files[mission] = report['request']['mission_source_sha256']
        files[Path(session['registry']).resolve()] = session['registry_revision']
        files[Path(session['mod_big']).resolve()] = session['mod_sha256']
        self.files = files; self.binding = binding
        self.session_digest = hashlib.sha256(session_raw).hexdigest()
        self.static_digest = canonical(_static_report(report))
        self._sources(force=True)
        self.layout = _load_layout()
        self.channel = _open_channel(binding, self.layout, session)
        check_header(self.channel.header(), binding)
        self.state = 'observing'; self.reason = None
        self._record('attached', binding=binding, source_hashes={str(path): digest for path, digest in files.items()})

    def _stop(self, reason):
        self.state = 'stopped'; self.reason = reason
        try:
            self._record('stopped', reason=reason, last_published_seq=self.last_seq)
        finally:
            self.close(preserve_state=True)
        return self._result()

    def poll(self):
        """No sleep/thread/SDK. Nominal50--100ms, fail closed above200ms; no JSON risk input."""
        if self.closed:
            return self._result()
        if not LIVE_MONITOR_ENABLED:
            self.state = 'candidate_disabled'; return self._result()
        if self.requested:
            return self._result()
        now = time.monotonic(); self.poll_started = now
        self.poll_interval = now-self.last_poll if self.last_poll is not None else None
        if self.last_poll is not None and now - self.last_poll > MAX_POLL_GAP:
            return self._stop('poll_cadence_exceeded')
        self.last_poll = now
        try:
            report = self._report()
            if self.channel is None:
                if report is None:
                    # A launch-intent report may be unchanged while its first
                    # actual header publication is still pending.
                    raw = self.report_path.read_bytes(); report = json.loads(raw.decode('utf-8-sig'))
                self._attach(report)
                self.last_poll = time.monotonic()
            self._sources()
            if not self.channel.alive():
                return self._stop('bound_process_exited')
            h = self.channel.header(); check_header(h, self.binding)
            if not self.approach_seen and h.phase in (1,5) and h.mission_stage == 0 and not(h.error or h.stop_requested or h.return_pending or h.retreat_requested):
                raise NotReady('waiting_native_initial_acquisition')
            if h.phase != 1 or h.mission_stage != 1 or h.error or h.stop_requested or h.return_pending or h.retreat_requested or h.return_calls or h.support.return_calls:
                return self._stop('native_not_unrequested_active_approach')
            if h.count < self.last_seq:
                raise RiskError('published_prefix_regressed')
            # Scan only the newly published immutable prefix. Its maximum is
            # the original8192 capacity, never arbitrary actor/game memory.
            for index in range(self.last_seq, min(h.count, self.last_seq+256)):
                e = self.channel.event(index)
                if e.kind == 71:
                    check_event(e, self.binding, baseline=True)
                    if e.role in self.baseline:
                        raise RiskError('duplicate_issued_baseline')
                    self.baseline[e.role] = e
                elif e.kind == 3:
                    if e.frame >= self.last_frame:
                        self.latest[e.role] = e
                self.last_seq = index + 1
            h2 = self.channel.header(); check_header(h2, self.binding)
            if h2.count < h.count or h2.phase != 1 or h2.mission_stage != 1 or h2.error or h2.stop_requested or h2.return_pending or h2.retreat_requested or h2.return_calls or h2.support.return_calls:
                return self._stop('native_state_changed_during_sample')
            if set(self.baseline) != {0, 1} or set(self.latest) != {0, 1}:
                raise NotReady('waiting_actual_dual_samples')
            pair = [self.latest[role] for role in (0, 1)]
            if pair[0].frame != pair[1].frame or pair[0].tick != pair[1].tick or pair[0].seq + 1 != pair[1].seq:
                raise NotReady('waiting_same_round_role_pair')
            frame = pair[0].frame
            self.approach_seen = True
            if frame <= self.last_frame:
                self.state = 'observing'; return self._result(frame=frame)
            if frame >= self.binding['deadline']:
                return self._stop('original_deadline_reached')
            if h2.motion_last_tick != frame or h2.count != self.last_seq:
                raise NotReady('waiting_current_complete_native_round')
            for e in pair:
                w = check_event(e, self.binding)
                base = list(self.baseline[e.role].stack_words)
                if w[13:27] != base[13:27] or w[52:65] != base[52:65]:
                    raise RiskError('private_stance_capture_changed')
            tick = self.channel.tick()
            age = (tick - pair[1].tick) & 0xffffffff
            ack_age = (tick - h2.pulse_acknowledged) & 0xffffffff
            if not h2.pulse_acknowledged or ack_age > 1000:
                return self._stop('host_pulse_liveness_lost')
            if age > MAX_SAMPLE_AGE_MS:
                raise NotReady('waiting_fresh_native_role_pair')
            if pair[0].target_visible != pair[1].target_visible or pair[0].target_visible not in (0, 1):
                raise NotReady('waiting_coherent_current_visibility')
            hp = [float(e.own_hp) for e in pair]
            baseline = [float(self.baseline[role].own_hp) for role in (0, 1)]
            risk = pair[0].target_visible == 0 and any(current < initial for current, initial in zip(hp, baseline))
            self._record('observed', observed_frame=frame, native_sequences=[e.seq for e in pair],
                         own_hp=hp, issued_baseline_hp=baseline, target_currently_visible=bool(pair[0].target_visible),
                         sample_age_ms=age, risk_triggered=risk)
            self.last_frame = frame
            self.state = 'observing'; self.reason = None
            if not risk:
                return self._result(frame=frame)
            self._sources(force=True)
            # Recheck static report identity immediately before the sole write.
            self._report()
            self._record('retreat_request_intent', observed_frame=frame, reason='target_lost',
                         native_sequences=[e.seq for e in pair], raw_pair_hex=[bytes(e).hex() for e in pair],
                         raw_issued_baseline_hex=[bytes(self.baseline[role]).hex() for role in (0,1)],
                         request_written=False)
            h3 = self.channel.header(); check_header(h3, self.binding)
            if not self.channel.alive() or h3.phase != 1 or h3.mission_stage != 1 or h3.error or h3.stop_requested or h3.return_pending or h3.retreat_requested:
                return self._stop('native_changed_before_request')
            if h3.motion_last_tick != frame or h3.count != self.last_seq or ((self.channel.tick()-pair[1].tick)&0xffffffff)>MAX_SAMPLE_AGE_MS:
                raise NotReady('native_round_advanced_before_request')
            self.channel.request()
            self.requested = True; self.state = 'retreat_requested'; self.reason = 'target_lost'
            try:
                self._record('retreat_flag_written', observed_frame=frame, request_frame=frame,
                             request_frame_source='bound_native_motion_last_tick', reason='target_lost',
                             own_hp=hp, issued_baseline_hp=baseline, native_sequences=[e.seq for e in pair],
                             raw_pair_hex=[bytes(e).hex() for e in pair],
                             raw_issued_baseline_hex=[bytes(self.baseline[role]).hex() for role in (0, 1)],
                             native_acknowledged=False, shared_flag='retreat_requested', written_value=1)
            except OSError:
                # The durable intent precedes the store. A failed outcome-log
                # write cannot erase the truthful fact that flag1 was written.
                self.state='stopped'
                result=self._result(written=True,frame=frame);result['audit_commit_failed']=True
                result['audit_error_type']='OSError'
                try:self.close(preserve_state=True)
                except OSError:result['close_error_type']='OSError'
                return result
            return self._result(written=True, frame=frame)
        except FileNotFoundError:
            if self.channel is None:
                self.state = 'waiting_report'; return self._result()
            return self._stop('bound_source_missing')
        except NotReady as error:
            self.state = 'waiting_native'; self.reason = str(error); return self._result()
        except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError) as error:
            return self._stop(str(error) if isinstance(error, RiskError) else type(error).__name__)

    def close(self, preserve_state=False):
        if self.closed:
            return
        self.closed = True
        if self.channel is not None:
            self.channel.close(); self.channel = None
        if not preserve_state:
            self.state = 'closed'
        if self.log is not None:
            self.log.close(); self.log = None
