"""Bound native builder/job records, read only. No game calls or model grant.

Construction attribution requires the original request, native submission and
result chain; an object merely appearing is not sufficient proof.
"""
import math
import struct
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'production'))
from observe_production import queue_candidate

from macro_observation import word,pointer,cache_scores,registry_lookup
from read_selected_personality import inspect_player

PINS={
    0x894f22:'8b470c0fb7f0',            # build entry count in definition + c
    0x894fa1:'8d14d6',                  # compiled entry stride 56
    0x8c545d:'8b4f1803ce',              # runtime entry stride 8
    0x8c5462:'e86919ffff',              # normal entry evaluation
    0x8c556f:'f30f594504',              # multiply entry score by state score
    0x8d7c52:'8d8e08030000',            # manager relative to builder subobject
    0x8d7c58:'e833d8feff',              # normal aggregate build selection
    0x8d7dc4:'e8e7ddffff',              # selected result -> native submission
    0x8d5ce1:'e8faceffff',              # native normal build request
    0x8d2c13:'0f84ef000000',            # structure vs production branch
    0x8d2c19:'6807020000',              # native construction message 207
    0x8d2d08:'6805020000',              # native production message 205
    0x8d2c23:'8b8ef8020000',            # registered builder row vector end
    0x8d2c8f:'c644080a01',              # native accepted/busy row flag
    0x8cb77a:'894604',                  # native job owner
    0x8cb7d2:'8b8190030000',            # per-AI native job ID counter
    0x8cb7ed:'81c174030000',            # per-AI job map
    0x53cb30:'8b410c',                  # job tree root
    0x53cb48:'396810',                  # job tree key
    0x53cba3:'8d4214',                  # job tree payload
    0x6da6b0:'8b41e08b4030c3',          # production interface factory-type getter
    0x723f50:'81eca8000000538bd98b43dc8b5058558d6bdc', # normal production implementation
}
JOB_VTABLES={0xc60238,0xc60a48}

def verify_pins(read):
    for address,expected in PINS.items():
        raw=bytes.fromhex(expected)
        if read(address,len(raw))!=raw:raise ValueError('macro_builder_signature_changed')


def own_thing(read,thing,owner,expected_id=None):
    pointer(thing,0x41c)
    if word(read,thing)!=0xc4db60:raise ValueError('macro_builder_thing_signature')
    # No enemy type/health/position read is allowed through this path.
    if word(read,thing+0x418)!=owner:raise ValueError('macro_builder_foreign_thing')
    ident=word(read,thing+0xdc)
    if not ident or expected_id is not None and ident!=expected_id:raise ValueError('macro_builder_thing_id')
    template=pointer(word(read,thing+4),12)
    result=dict(address=hex(thing),thing_id=ident,type_hash=hex(word(read,template+8)))
    body=word(read,thing+0x33c)
    if body:
        hp=struct.unpack('<f',read(pointer(body,8)+4,4))[0]
        if not math.isfinite(hp) or hp<0:raise ValueError('macro_builder_thing_health')
        result['hp']=hp
    if (word(read,thing+0x418)!=owner or word(read,thing+0xdc)!=ident or word(read,thing+4)!=template):
        raise ValueError('macro_builder_thing_changed')
    return result


def thing_id(read,game,ident,owner):
    if not ident:return None
    thing=registry_lookup(read,game+0xbc,ident)
    return own_thing(read,thing,owner,ident) if thing else dict(thing_id=ident,not_currently_in_registry=True)


def builder_rows(read,ai,owner,game):
    if word(read,ai+0x3ec)!=0xc5f330:raise ValueError('macro_builder_registry_signature')
    header=read(ai+0x3f8,8);start,end=struct.unpack('<II',header)
    if end<start or end-start>1536 or (end-start)%12 or bool(start)!=bool(end):raise ValueError('macro_builder_rows_bounds')
    if start:pointer(start,max(end-start,4))
    raw=read(start,end-start) if end>start else b'';result=[];seen=set()
    for offset in range(0,len(raw),12):
        interface,ident=struct.unpack_from('<II',raw,offset)
        if interface in seen:raise ValueError('macro_builder_duplicate_factory')
        seen.add(interface);pointer(interface-0x24,0x28)
        if (word(read,interface)!=0xc3f8c8 or word(read,interface-0x24)!=0xc3fad0
                or word(read,0xc3f8c8+0xac)!=0x6da6b0):raise ValueError('macro_builder_interface_signature')
        thing=word(read,interface-0x1c)
        if registry_lookup(read,game+0xbc,ident)!=thing:raise ValueError('macro_builder_producer_registry_link')
        factory=own_thing(read,thing,owner,ident)
        if factory.get('hp',0)<=0:
            result.append(dict(factory=factory,production_interface=hex(interface),
                observation_available=False,reason='registered_producer_not_live'))
            continue
        # This getter returns a factory category, not a Thing ID. The vector
        # stores the producer's own Thing ID; neither word is a created child.
        definition=pointer(word(read,interface-0x20),0x34)
        category=word(read,definition+0x30)
        if word(read,0xc3f8c8+0x24)!=0x723f50:raise ValueError('macro_builder_queue_implementation')
        class Reader:
            def u32(self,address):return word(read,address)
            def read(self,address,size):return read(address,size)
        module=interface-0x24;queue_header=read(module+0x34,8)
        queue=queue_candidate(Reader(),module)
        if (read(module+0x34,8)!=queue_header or any(read(int(node['address'],0),0x70).hex()!=node['raw'] for node in queue['nodes'])):
            raise ValueError('macro_builder_queue_changed')
        result.append(dict(factory=factory,production_interface=hex(interface),queue_candidate=queue,
            observation_available=True,factory_category_raw=category,factory_category_semantics_verified=False,
            state_bytes_raw=list(raw[offset+8:offset+12])))
    if read(ai+0x3f8,8)!=header or raw and read(start,len(raw))!=raw:raise ValueError('macro_builder_rows_changed')
    return result


def job_records(read,ai,owner,game):
    table=ai+0x374;header=read(table,0x1c);root=struct.unpack_from('<I',header,0xc)[0]
    stack=[(root,None,None)] if root else [];seen=set();copies=[];result=[]
    while stack:
        node,low,high=stack.pop();pointer(node,24)
        if node in seen or len(seen)>=256:raise ValueError('macro_builder_job_tree_cycle_or_bound')
        seen.add(node);raw=read(node,24);right,left=struct.unpack_from('<II',raw)
        ident,job=struct.unpack_from('<II',raw,0x10)
        if (low is not None and ident<=low) or (high is not None and ident>=high):raise ValueError('macro_builder_job_tree_order')
        copies.append((node,raw))
        if right:stack.append((right,ident,high))
        if left:stack.append((left,low,ident))
        if not job:continue
        pointer(job,0x40)
        if word(read,job) not in JOB_VTABLES:continue
        if word(read,job+4)!=owner:raise ValueError('macro_builder_foreign_job')
        raw_job=read(job,0x40)
        if struct.unpack_from('<I',raw_job,0x2c)[0]!=ident:raise ValueError('macro_builder_job_id')
        producer,target,category=struct.unpack_from('<I',raw_job,0xc)[0],struct.unpack_from('<I',raw_job,0x10)[0],struct.unpack_from('<I',raw_job,0x18)[0]
        result.append(dict(native_job_id=ident,address=hex(job),vtable=hex(word(read,job)),
            target_type_hash_raw=hex(target),state_raw=struct.unpack_from('<I',raw_job,0x14)[0],
            producer_thing_id=producer,producer_thing=thing_id(read,game,producer,owner),
            factory_category_raw=category,linked_object_semantics_verified=False,
            native_word_20_raw=word(read,job+0x20),native_word_30_raw=word(read,job+0x30),
            flags_raw=list(raw_job[0x28:0x2c])))
        if read(job,0x40)!=raw_job:raise ValueError('macro_builder_job_changed')
    if read(table,0x1c)!=header or any(read(p,len(raw))!=raw for p,raw in copies):raise ValueError('macro_builder_job_tree_changed')
    return dict(total_native_jobs=len(seen),construction_jobs=result)


def macro_build_entries(read,ai,flags):
    scores=cache_scores(read,ai,flags,0x414,'construction');rows=[]
    for flag,state in scores.items():
        group=int(state['group'],0)
        if word(read,group)!=0xc5f668:raise ValueError('macro_builder_state_signature')
        definition=pointer(word(read,group+0x10),0x14)
        count=struct.unpack('<H',read(group+0x14,2))[0]
        if not 1<=count<=32 or count!=word(read,definition+0xc):raise ValueError('macro_builder_entry_count')
        start=pointer(word(read,group+0x18),count*8);serialized=pointer(word(read,definition+0x10),count*56)
        raw=read(start,count*8);entries=[]
        for i in range(count):
            entry,stamp=struct.unpack_from('<II',raw,i*8)
            if entry!=serialized+i*56:raise ValueError('macro_builder_entry_definition_link')
            data=read(entry,56);build,upgrade,heuristic=struct.unpack_from('<III',data)
            constant=struct.unpack_from('<f',data,0x30)[0]
            if not math.isfinite(constant):raise ValueError('macro_builder_constant_score')
            entries.append(dict(build_type_hash_raw=hex(build),upgrade_hash_raw=hex(upgrade),
                heuristic_raw=heuristic,constant_score_raw=constant,runtime_stamp_raw=stamp))
        if read(start,len(raw))!=raw:raise ValueError('macro_builder_entries_changed')
        rows.append(dict(flag=flag,state_score=state['score'],dirty=state['dirty'],entries=entries))
    return rows


class NativeBuildObserver:
    def __init__(self,memory,owner,flags):
        self.memory=memory;self.owner=owner;self.flags=flags;self.native=inspect_player(memory.read,owner)
        self.ai=int(self.native['ai_player'],0);self.game=word(memory.read,0xcd8ce4)
        verify_pins(memory.read)

    def sample(self):
        read=self.memory.read
        if inspect_player(read,self.owner)!=self.native or word(read,0xcd8ce4)!=self.game:raise ValueError('macro_builder_identity_changed')
        frame=word(read,self.game+0x50)
        if not frame:raise ValueError('macro_builder_match_not_running')
        builders=builder_rows(read,self.ai,self.owner,self.game)
        jobs=job_records(read,self.ai,self.owner,self.game)
        entries=macro_build_entries(read,self.ai,self.flags)
        if (inspect_player(read,self.owner)!=self.native or word(read,0xcd8ce4)!=self.game
                or not 0<=word(read,self.game+0x50)-frame<=2):raise ValueError('macro_builder_snapshot_changed')
        return dict(frame=frame,builders=builders,jobs=jobs,macro_entries=entries,
            source='native_macro_builder_read_only',process_writes=0,native_calls=0,
            submission_attribution_verified=False,payment_verified=False,product_capability_granted=False)
