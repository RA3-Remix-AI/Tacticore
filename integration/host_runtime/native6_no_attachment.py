"""Independent no-acquisition evidence for Native6 before its constructor.

This never restores managers or claims a mission effect. It corroborates the
frozen no-constructor history with the exact OS incarnation, complete policy
module inventories and absent Native6 mapping/common lease, read twice.
"""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import time

from .contracts import ContractError

KIND='native6_no_attachment_v1'
ROOT=Path(__file__).resolve().parents[2]


def capture(memory,session,binding,run_id):
    from .native6_transport import native_module
    from .native6_presence import query_macro_objects
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
    objects_before=query_macro_objects(session['pid'],'Local'+chr(92)+'RA3StrategicCommanderV6_')
    objects_after=query_macro_objects(session['pid'],'Local'+chr(92)+'RA3StrategicCommanderV6_')
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
                    or value['mapping_name']!='Local'+chr(92)+'RA3StrategicCommanderV6_'+str(binding.game_process_id)
                    or value['semaphore_name']!='Local'+chr(92)+'RA3MacroPolicyLease_'+str(binding.game_process_id)
                    or value['mapping_status']!='absent' or value['semaphore_status']!='absent'
                    or value['mapping_open_error']!=2 or value['semaphore_open_error']!=2
                    or type(value['native_writes']) is not int or value['native_writes']!=0
                    or type(value['acquire_or_wait_calls']) is not int or value['acquire_or_wait_calls']!=0):return False
        return True
    except (KeyError,TypeError,ValueError):return False
