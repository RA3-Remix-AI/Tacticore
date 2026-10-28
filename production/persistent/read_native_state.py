"""Read-only, process-pinned production channel capture; never loads an executor.

Raw headers and stable native receipt bytes are retained for independent review.
This observation grants no capability, game action, or natural-result credit.
"""
import argparse
import ctypes as c
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from observe_production import Memory,k,w
from session_package import verify_session_package
from client import Persistent,Receipt,uuid_string,uuid_words


def capture(session):
    verify_session_package(session)
    memory=Memory(session['pid'],session)
    k.OpenFileMappingW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];k.OpenFileMappingW.restype=w.HANDLE
    k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p
    k.UnmapViewOfFile.argtypes=[c.c_void_p]
    handle=None;view=None
    try:
        handle=k.OpenFileMappingW(4,False,'Local\\RA3ProductionPersistent_'+str(session['pid']))
        if not handle:raise ValueError('production_channel_unavailable')
        view=k.MapViewOfFile(handle,4,0,0,c.sizeof(Persistent))
        if not view:raise ValueError('production_channel_unreadable')
        offset=Persistent.ledger.offset
        for attempt in range(10):
            before=c.string_at(view,offset)
            first=Persistent.from_buffer_copy(before+bytes(c.sizeof(Persistent)-offset))
            if not 0<=first.count<=1024:raise ValueError('production_native_count_invalid')
            rows=[]
            for index in range(first.count):
                address=view+offset+index*c.sizeof(Receipt)
                raw=c.string_at(address,c.sizeof(Receipt));receipt=Receipt.from_buffer_copy(raw)
                if receipt.updates or receipt.version<=0 or c.string_at(address,c.sizeof(Receipt))!=raw:break
                rows.append(dict(index=index,raw_hex=raw.hex(),command_id=uuid_string(receipt.command.id),
                    task_id=uuid_string(receipt.command.task),sequence=receipt.command.seq,
                    state=receipt.state,error=receipt.error,attempted=receipt.attempted,paid=receipt.paid,
                    cost=receipt.cost,created=receipt.created,completed=receipt.completed,object_id=receipt.object_id))
            after=c.string_at(view,offset)
            final=Persistent.from_buffer_copy(after+bytes(c.sizeof(Persistent)-offset))
            if len(rows)==first.count and first.count==final.count:
                break
            time.sleep(.01)
        else:raise ValueError('production_native_capture_unstable')
        immutable=('magic','version','pid','thread','owner','ai','personality','personality_id','player_template','start_low','start_high')
        if any(getattr(first,name)!=getattr(final,name) for name in immutable):raise ValueError('production_native_binding_changed')
        delta=datetime.fromisoformat(session['start_time']).astimezone(timezone.utc)-datetime(1601,1,1,tzinfo=timezone.utc)
        recorded=(delta.days*86400+delta.seconds)*10000000+delta.microseconds*10
        if (first.magic!=0x50434d44 or first.version!=1 or first.pid!=session['pid'] or first.thread<=0
            or first.callback_thread!=first.thread or abs((first.start_low|(first.start_high<<32))-recorded)>9
            or tuple(first.session)!=uuid_words(session['session_id'])
            or tuple(first.commander)!=uuid_words(session['scenario']['commander_id'])):
            raise ValueError('production_native_binding_unverified')
        owner=memory.u32(memory.u32(0xce8c9c)+0x30+4*session['scenario']['computer_player_index'])
        if owner!=first.owner or memory.u32(owner+0x20)!=3:raise ValueError('production_native_owner_changed')
        return dict(schema_version=1,kind='read_only_native_production_capture',session_id=session['session_id'],
            pid=session['pid'],process_start=session['start_time'],commander_id=session['scenario']['commander_id'],
            game_sha256=hashlib.sha256(Path(memory.path).read_bytes()).hexdigest(),mod_sha256=session['mod_sha256'],
            reader_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),header_size=offset,receipt_size=c.sizeof(Receipt),
            header_before_hex=before.hex(),header_after_hex=after.hex(),receipts=rows,
            native_phase=final.phase,native_error=final.error,restore_mask=final.restore_mask,active_callbacks=final.active,
            spent_committed=final.spent,native_count=final.count,game_frame=memory.u32(memory.u32(0xcd8ce4)+0x50),
            native_writes=0,sdk_game_calls=0,execution_authority_granted=False,natural_result_verified=False)
    finally:
        if view:k.UnmapViewOfFile(view)
        if handle:k.CloseHandle(handle)
        memory.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--session',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();raw=args.session.read_bytes();session=json.loads(raw.decode('utf-8-sig'))
    if args.output.exists():raise ValueError('capture_output_must_be_new')
    result=capture(session)
    if args.session.read_bytes()!=raw:raise ValueError('capture_session_changed')
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(dict(native_phase=result['native_phase'],native_count=result['native_count'],spent=result['spent_committed'],sdk_game_calls=0)))


if __name__=='__main__':main()
