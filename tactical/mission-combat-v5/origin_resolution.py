"""Read-only final implicit-origin sample; no game commands or input-file edits."""
import math,struct
def resolve(memory,pre):
 selected=pre['selected'];thing=int(selected['address'],0);owner=int(pre['owner'],0);logic=int(pre['logic'],0);ident=selected['object_id'];kind=int(selected['type_hash'],0);update=int(selected['ai_address'],0)
 def identity():return memory.u32(thing)==0xc4db60 and memory.u32(thing+0xdc)==ident and memory.u32(thing+0x418)==owner and memory.u32(owner+0x20)==3 and memory.u32(memory.u32(thing+4)+8)==kind and memory.u32(thing+0x374)==update and memory.u32(update+8)==thing
 before=memory.u32(logic+0x50)
 if memory.u32(0xcd8ce4)!=logic or memory.u32(logic+0x15c) or not identity():raise ValueError('implicit_origin_actor_changed_or_paused')
 flags=memory.u32(thing+0x84);hp=memory.f32(memory.u32(thing+0x33c)+4);xyz=list(struct.unpack('<fff',memory.read(thing+0x38,12)));after=memory.u32(logic+0x50)
 if flags&0x20080000 or not math.isfinite(hp) or hp<=0 or not all(math.isfinite(x) for x in xyz) or not before<=after<=before+1 or memory.u32(logic+0x15c) or not identity() or memory.u32(thing+0x84)!=flags:raise ValueError('implicit_origin_sample_unverified')
 return dict(method='last_pre_native_launch_own_actor_position',object_id=ident,address=hex(thing),owner=hex(owner),type_hash=hex(kind),update=hex(update),frame_start=before,frame_end=after,observed_frame=after,status84=flags,hp=hp,xyz=xyz,mutations=False)
