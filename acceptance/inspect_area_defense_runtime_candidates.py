"""Own-state-only read diagnostics when strict native task observation is empty.

No execution, interpretation as success, hidden enemy records or unit orders.
"""
import ctypes as c
import struct
from macro_area_defense_observation import MBI,k,RUNTIME_VTABLES,sample_runtime,cache_scores
from read_selected_personality import inspect_player

def inspect_candidates(memory,owner,flags):
    native=inspect_player(memory.read,owner);scores=cache_scores(memory.read,int(native['ai_player'],0),flags)
    groups={int(r['group'],0) for r in scores.values()};needles=[struct.pack('<I',v) for v in RUNTIME_VTABLES]
    def locate(raw,start=0):return min((p for needle in needles if (p:=raw.find(needle,start))>=0),default=-1)
    ai=int(native['ai_player'],0);manager=memory.u32(ai+0x6f8)
    for at,expected in ((0x8a040c,'8b693c'),(0x8a0422,'69c0cc020000'),(0x8bdf62,'8b7f08')):
        if memory.read(at,len(bytes.fromhex(expected)))!=bytes.fromhex(expected):raise ValueError('own_target_slot_native_pin')
    start=memory.u32(manager+0x38);count=memory.u32(manager+0x3c)
    if not 0<=count<=256:raise ValueError('own_target_slot_bound')
    slots=[]
    for index in range(count):
        at=start+index*0x2cc;group=memory.u32(at+8)
        if group in groups:
            slots.append(dict(slot=index,group=hex(group),native_point_flag=memory.read(at+0x74,1)[0],
                own_state_bound=True))
    candidates=[];address=0x10000
    while address<0x100000000:
        info=MBI()
        if not k.VirtualQueryEx(memory.handle,address,c.byref(info),c.sizeof(info)):break
        base,length=info.base or 0,info.region_size
        if not length or base+length<=address:break
        if info.state==0x1000 and info.type==0x20000 and not info.protect&0x101:
            for offset in range(0,length,0x2000):
                try:raw=memory.read(base+offset,min(0x2000,length-offset))
                except RuntimeError:continue
                pos=locate(raw)
                while pos>=0:
                    at=base+offset+pos
                    try:
                        if at%4 or memory.u32(at+0x50) not in groups or memory.u32(at+0x2c) not in (0,owner):
                            pos=locate(raw,pos+4);continue
                        own=memory.read(at,0xa4)
                        try:sample_runtime(memory.read,at,owner,groups);reason=None
                        except (ValueError,RuntimeError) as error:reason=str(error)
                        candidates.append(dict(address=hex(at),runtime_vtable=hex(struct.unpack_from('<I',own)[0]),group=hex(struct.unpack_from('<I',own,0x50)[0]),
                            strict_rejection=reason,active_raw=own[0x14],cleanup_raw=own[0x30],
                            owner_bound=struct.unpack_from('<I',own,0x2c)[0]==owner,
                            owner_pending=struct.unpack_from('<I',own,0x2c)[0]==0,
                            component_vtables=[hex(struct.unpack_from('<I',own,o)[0]) for o in (0x58,0x5c)],
                            self_link_matches=struct.unpack_from('<I',own,0x94)[0]==at))
                        if len(candidates)>32:raise ValueError('own_runtime_diagnostic_bound')
                    except RuntimeError:pass
                    pos=locate(raw,pos+4)
        address=base+length
    return dict(source='own_state_bound_runtime_diagnostic',native_calls=0,process_writes=0,
        custom_target_slots=slots,candidates=candidates,execution_effect_verified=False)
