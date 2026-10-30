"""Independent no-acquisition evidence for Native5 before its constructor.

This never restores managers or claims a mission effect. It corroborates the
frozen no-constructor history with the exact OS incarnation, complete policy
module inventories and absent Native5 mapping/common lease, read twice.
"""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import time

from .contracts import ContractError

KIND='strategic_unified_no_attachment_v5'
ROOT=Path(__file__).resolve().parents[2]


def capture(memory,session,binding,run_id):
    from .strategic_unified_transport_v5 import native_module
    from .strategic_native_presence_v5 import query_macro_objects
    _,sdk=native_module()
    if memory is None:
        # Memory can acquire its handle before a later identity check fails.
        # Keep the partial object so that such failures still close that handle.
        reader=sdk.Memory.__new__(sdk.Memory)
        try:
            reader.__init__(session['pid'],session)
            return capture(reader,session,binding,run_id)
        finally:
            if getattr(reader,'handle',None):
                reader.close();reader.handle=None
    k=c.WinDLL('kernel32',use_last_error=True)
    k.GetProcessId.argtypes=[w.HANDLE];k.GetProcessId.restype=w.DWORD
    k.GetProcessTimes.argtypes=[w.HANDLE,*[c.POINTER(w.FILETIME)]*4];k.GetProcessTimes.restype=w.BOOL
    k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)]
    def image():
        value=c.create_unicode_buffer(32768);size=w.DWORD(len(value))
        if not k.QueryFullProcessImageNameW(memory.handle,0,value,c.byref(size)):
            raise ContractError('strategic_no_attachment_image_unknown')
        return str(Path(value.value).resolve(strict=True))
    def identity():
        times=[w.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(memory.handle,*[c.byref(v) for v in times]):raise ContractError('strategic_no_attachment_OS_unknown')
        return dict(pid=int(k.GetProcessId(memory.handle)),process_creation_filetime=int(times[0].dwLowDateTime)|(int(times[0].dwHighDateTime)<<32))
    started=time.monotonic_ns();before=identity();image_before=image()
    if Path(image_before)!=Path(session['game']).resolve(strict=True):raise ContractError('strategic_no_attachment_image_changed')
    image_sha256=hashlib.sha256(Path(image_before).read_bytes()).hexdigest()
    modules_before=sdk.policy_modules(memory)
    objects_before=query_macro_objects(session['pid'],'Local'+chr(92)+'RA3StrategicCommanderV5_')
    objects_after=query_macro_objects(session['pid'],'Local'+chr(92)+'RA3StrategicCommanderV5_')
    modules_after=sdk.policy_modules(memory);image_after=image();after=identity();ended=time.monotonic_ns()
    proof=dict(kind=KIND,schema_version=1,run_id=run_id,binding=binding.public(),
        actual_OS_before=before,actual_OS_after=after,policy_modules_before=modules_before,policy_modules_after=modules_after,
        objects_before=objects_before,objects_after=objects_after,started_monotonic_ns=started,ended_monotonic_ns=ended,
        image_before=image_before,image_after=image_after,image_sha256=image_sha256,
        capture_code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        no_control_acquired=True,manager_restoration_claimed=False,mission_effect_verified=False)
    if not verified_capture(proof,session,binding,run_id):raise ContractError('strategic_no_attachment_unverified')
    return proof


def verified_capture(proof,session,binding,run_id):
    try:
        expected=dict(pid=binding.game_process_id,process_creation_filetime=session['process_creation_filetime'])
        if (proof['kind']!=KIND or type(proof['schema_version']) is not int or proof['schema_version']!=1 or proof['run_id']!=run_id or proof['binding']!=binding.public()
                or proof['actual_OS_before']!=expected or proof['actual_OS_after']!=expected
                or proof['policy_modules_before']!=[] or proof['policy_modules_after']!=[]
                or proof['no_control_acquired'] is not True or proof['manager_restoration_claimed'] is not False
                or proof['mission_effect_verified'] is not False
                or Path(proof['image_before'])!=Path(session['game']).resolve() or proof['image_after']!=proof['image_before']
                or proof['image_sha256']!=binding.game_sha256
                or any(type(proof[k]) is not int for k in ('started_monotonic_ns','ended_monotonic_ns'))
                or proof['started_monotonic_ns']<0
                or not 0<=proof['ended_monotonic_ns']-proof['started_monotonic_ns']<=250_000_000):return False
        for key in ('objects_before','objects_after'):
            value=proof[key]
            if (value['source']!='win32_read_only_macro_channel_and_semaphore_v1'
                    or value['mapping_name']!='Local'+chr(92)+'RA3StrategicCommanderV5_'+str(binding.game_process_id)
                    or value['semaphore_name']!='Local'+chr(92)+'RA3MacroPolicyLease_'+str(binding.game_process_id)
                    or value['mapping_status']!='absent' or value['semaphore_status']!='absent'
                    or value['mapping_open_error']!=2 or value['semaphore_open_error']!=2
                    or type(value['native_writes']) is not int or value['native_writes']!=0
                    or type(value['acquire_or_wait_calls']) is not int or value['acquire_or_wait_calls']!=0):return False
        return True
    except (KeyError,TypeError,ValueError):return False


def verified_return(backend,row,binding,session,release,receipt,host_receipt):
    """File-only replay; actual exited Host identity is checked by its caller."""
    try:
        from .session_discovery_native import frozen_manifest,require_creation
        require_creation(binding.game_process_start,session['process_creation_filetime'])
        output=Path(row['output_path']);path=output/'native-no-attachment.json';raw=path.read_bytes()
        proof=json.loads(raw);digest=hashlib.sha256(raw).hexdigest();run_id=row['run_id']
        if (backend.journal.unresolved(run_id) or receipt.get('no_attachment_sha256')!=digest
                or release.get('no_attachment_sha256')!=digest or release.get('run_id')!=run_id
                or release.get('native_release_contract')!=KIND or release.get('kind')!='macro_policy_native_release'
                or release.get('native_release_verified') is not True
                or any(release.get(k)!=host_receipt.get(k) for k in ('host_pid','host_start_time'))
                or not verified_capture(proof,session,binding,run_id)):return False
        manifest=frozen_manifest(row,session,binding)
        if manifest.get('protocol_version')!=5 or manifest.get('kind')!='strategic_unified_transport_v5_candidate':return False
        records=json.loads((output/'sources.json').read_bytes())['sources'];host=records[0]
        bundle=json.loads((output/'source'/records[2]['copy']).read_bytes())
        if (bundle.get('schema_version')!=13 or host['sha256']!=bundle['pins'].get(str(ROOT/'integration/macro_host.py'))
                or proof['capture_code_sha256']!=bundle['pins'].get(str(Path(__file__).resolve()))):return False
        events=[json.loads(line) for line in (output/'host-events.jsonl').read_text().splitlines()]
        forbidden={'macro_native_transport_constructor_begin','macro_native_transport_constructor_returned',
            'commander_model_call_started','model_macro_dispatch_prepared','plan_applied'}
        if any(e['kind'] in forbidden for e in events):return False
        if not events or events[-1]['kind']!='host_stopped':return False
        allowed={'host_start','host_stop','macro_policy_stop'}
        if any(r['operation'] not in allowed or r['status'] not in ('completed','released')
                for r in backend.journal.commands_for_run(run_id)):return False
        return True
    except (OSError,ValueError,KeyError,TypeError,ContractError):return False
