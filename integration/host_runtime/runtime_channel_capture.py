"""Process-pinned read-only original channel capture. No commands or grants."""
from __future__ import annotations
import argparse
import ctypes as c
import hashlib
import json
from pathlib import Path
import struct
import time

from .contracts import SessionBinding
from .runtime_evidence import _decode, _layout, verify_build_artifacts,verify_bootstrap_paid


def capture_bytes(layout, read, bootstrap, actor, token):
    """One coherent read attempt; read accepts mapping-relative offsets only."""
    limit=layout.SharedChannel.events.offset
    before=read(0,limit)
    header=_decode(layout.SharedChannel,before.hex(),limit)
    if (header.magic_word!=layout.MAGIC or header.protocol!=layout.VERSION
            or header.structure_size!=c.sizeof(layout.SharedChannel) or header.token!=token
            or bytes(header.bootstrap)!=bootstrap or bytes(header.admitted_actor)!=actor):
        raise ValueError('capture_native_binding_changed')
    counters=read(layout.SharedChannel.traces_written.offset,8)
    written,lost=struct.unpack('<ii',counters)
    if (header.events_overwritten or lost or not 0<=header.events_written<=layout.CAPACITY
            or not 0<=written<=layout.TRACE_CAPACITY):
        raise ValueError('capture_original_stream_lost')
    def rows(cls,offset,count,capacity):
        result=[]
        for ticket in range(1,count+1):
            address=offset+((ticket-1)%capacity)*c.sizeof(cls)
            raw=read(address,c.sizeof(cls))
            entry=cls.from_buffer_copy(raw)
            if entry.ticket!=ticket or read(address,len(raw))!=raw:
                raise ValueError('capture_native_slot_unstable')
            result.append(dict(ticket=ticket,raw_hex=raw.hex()))
        return result
    events=rows(layout.WireEvent,layout.SharedChannel.events.offset,header.events_written,layout.CAPACITY)
    traces=rows(layout.WireHookTrace,layout.SharedChannel.traces.offset,written,layout.TRACE_CAPACITY)
    after=read(0,limit)
    counter_after=read(layout.SharedChannel.traces_written.offset,8)
    if before!=after or counters!=counter_after:
        raise ValueError('capture_native_stream_changed')
    return dict(schema_version=1,protocol='tactical_runtime_original_channel_readonly_v1',
        header_before_hex=before.hex(),header_after_hex=after.hex(),
        trace_counters_before_hex=counters.hex(),trace_counters_after_hex=counter_after.hex(),
        events=events,hook_traces=traces,events_written=header.events_written,
        events_overwritten=header.events_overwritten,traces_written=written,traces_overwritten=lost,
        state=header.state,held=header.receipt.held,control_released=header.receipt.control_released,
        physical_home=header.receipt.physical_home,hooks_restored=header.hooks_restored,
        active_callbacks=header.active_callbacks,native_writes=0,sdk_game_calls=0,
        ordinary_execution_granted=False)


def capture(session_path,source_path):
    from live_state import Memory,verify_session_package
    session_bytes=session_path.read_bytes();source_bytes=source_path.read_bytes()
    session=json.loads(session_bytes.decode('utf-8-sig'));source=json.loads(source_bytes.decode('utf-8-sig'))
    verify_session_package(session)
    binding=SessionBinding.from_dict(source['binding']);layout=_layout()
    hashes=verify_build_artifacts(source['build_manifest'],layout)
    if (source.get('protocol')!='tactical_runtime_v1_diagnostic'
            or source.get('ordinary_execution_granted') is not False
            or source.get('field_verified') is not False
            or binding.session_id!=session['session_id'] or binding.game_process_id!=session['pid']
            or binding.game_process_start!=session['start_time']
            or binding.mod_sha256!=session['mod_sha256']
            or source.get('native_layout')!=layout.inventory()
            or source.get('executor_sha256')!=hashes['TacticoreRuntime1.dll']
            or source.get('native_host_sha256')!=hashes['runtime_host.exe']):
        raise ValueError('capture_context_binding_invalid')
    declared=_decode(layout.Bootstrap,source['bootstrap_hex'])
    def require(name,condition):
        if condition is not True:raise ValueError('capture_'+name)
    verify_bootstrap_paid(source,binding,layout,require,expected_experimental_flags=declared.experimental_flags)
    original=_decode(layout.SharedChannel,source['header_before_hex'],layout.SharedChannel.events.offset)
    bootstrap=bytes(_decode(layout.Bootstrap,source['bootstrap_hex']))
    actor=bytes(_decode(layout.Actor,source['admitted_actor_hex']))
    if bytes(original.bootstrap)!=bootstrap or original.token<=0:
        raise ValueError('capture_original_bootstrap_invalid')
    memory=Memory(session['pid'],session)
    kernel=c.WinDLL('kernel32',use_last_error=True)
    kernel.OpenFileMappingW.argtypes=[c.c_uint32,c.c_int,c.c_wchar_p];kernel.OpenFileMappingW.restype=c.c_void_p
    kernel.MapViewOfFile.argtypes=[c.c_void_p,c.c_uint32,c.c_uint32,c.c_uint32,c.c_size_t];kernel.MapViewOfFile.restype=c.c_void_p
    kernel.UnmapViewOfFile.argtypes=[c.c_void_p];kernel.CloseHandle.argtypes=[c.c_void_p]
    handle=view=None
    try:
        # FILE_MAP_READ only. This module never imports the atomic publisher,
        # loads the game DLL, posts pulses or constructs a native command.
        handle=kernel.OpenFileMappingW(4,False,f'Local\\TacticoreRuntime1_{session["pid"]}_{original.token}')
        if not handle:raise ValueError('capture_original_mapping_unavailable')
        view=kernel.MapViewOfFile(handle,4,0,0,c.sizeof(layout.SharedChannel))
        if not view:raise ValueError('capture_mapping_view_unavailable')
        def read(offset,size):
            if offset<0 or size<0 or offset+size>c.sizeof(layout.SharedChannel):
                raise ValueError('capture_mapping_bounds')
            return c.string_at(view+offset,size)
        for attempt in range(8):
            try:
                result=capture_bytes(layout,read,bootstrap,actor,original.token)
                break
            except ValueError as error:
                if str(error) not in ('capture_native_slot_unstable','capture_native_stream_changed') or attempt==7:
                    raise
                time.sleep(.02)
        if session_path.read_bytes()!=session_bytes or source_path.read_bytes()!=source_bytes:
            raise ValueError('capture_context_changed_during_read')
        # Recheck the actual process pin through the original process reader.
        memory.u32(0xcd8ce4)
        result.update(session_id=session['session_id'],pid=session['pid'],process_start=session['start_time'],
            context_report=str(source_path),context_report_sha256=hashlib.sha256(source_bytes).hexdigest(),
            reader_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        return result
    finally:
        if view:kernel.UnmapViewOfFile(view)
        if handle:kernel.CloseHandle(handle)
        memory.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('session','source','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();session=args.session.resolve();source=args.source.resolve();output=args.output.resolve()
    record=json.loads(session.read_text(encoding='utf-8-sig'));run=Path(record['run_directory']).resolve()
    if source.parent!=run or output.parent!=run or output.exists():
        raise ValueError('capture_paths_must_be_new_owned_run_output')
    result=capture(session,source)
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({name:result[name] for name in ('state','held','control_released','hooks_restored','events_written','traces_written')}))

if __name__=='__main__':main()
