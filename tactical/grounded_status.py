"""Native status-only ground evidence. No SDK or memory writes.
Positive locomotor state is not proof that an edge between points is walkable.
"""
import hashlib,struct
from pathlib import Path
EXPECTED="ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165"
FLAGS={
 'AIRBORNE_TARGET':(0xbdaeb0,7), 'PARACHUTING':(0xbdb340,8),
 'GROUND_LOCOMOTOR_ACTIVE':(0xbdb0f8,160), 'AIR_LOCOMOTOR_ACTIVE':(0xbdaec0,161),
 'LANDING_IN_PROGRESS':(0xbdb258,207), 'LIFTED_INTO_AIR':(0xbdb270,211),
 'INSIDE_GARRISON':(0xbdb1a8,61), 'IMMOBILE':(0xbdb180,51),
}

def sha(data):return hashlib.sha256(data).hexdigest()

def static_proof(path):
 data=Path(path).read_bytes()
 if sha(data)!=EXPECTED:raise ValueError('executable_revision')
 pe=struct.unpack_from('<I',data,0x3c)[0];count=struct.unpack_from('<H',data,pe+6)[0];size=struct.unpack_from('<H',data,pe+20)[0];base=struct.unpack_from('<I',data,pe+52)[0];sections=[struct.unpack_from('<8sIIII',data,pe+24+size+40*i) for i in range(count)]
 def read(address,length):
  for name,vs,va,n,raw in sections:
   if base+va<=address and address+length<=base+va+n:return data[raw+address-base-va:raw+address-base-va+length]
  raise ValueError('not_file_backed')
 rows=[]
 for name,(record,index) in FLAGS.items():
  pointer,actual=struct.unpack('<II',read(record,8));text=read(pointer,len(name)+1)
  if actual!=index or text!=name.encode()+b'\0':raise ValueError('status_name_record_changed')
  rows.append(dict(name=name,native_enum=index,name_record=hex(record),name_pointer=hex(pointer),record_bytes=read(record,8).hex(),word_offset=hex(0x80+4*(index>>5)),mask=hex(1<<(index&31))))
 # Native SetObjectStatus(index,bool) establishes the generic packed mapping.
 expected='8b7c24108bc18bcf83e11f807c241400741fbe01000000d3e68bcfc1e90585b488800000000f94c309b48880000000'
 if read(0x7274c3,len(bytes.fromhex(expected))).hex()!=expected:raise ValueError('generic_status_setter_changed')
 return dict(executable_sha256=EXPECTED,records=rows,generic_setter=dict(address='0x7274c0',mapping='Thing+0x80+4*(native_enum>>5), mask 1<<(native_enum&31)',mapping_bytes_address='0x7274c3',mapping_bytes=expected),airborne_direct_setter=dict(address='0x73af31',bytes=read(0x73af31,29).hex(),notification_enum=7),mutations=False)

def decode(words):
 flags={name:bool(words[index>>5]&(1<<(index&31))) for name,(record,index) in FLAGS.items()}
 not_ground=any(flags[k] for k in ['AIRBORNE_TARGET','PARACHUTING','AIR_LOCOMOTOR_ACTIVE','LANDING_IN_PROGRESS','LIFTED_INTO_AIR'])
 ground=flags['GROUND_LOCOMOTOR_ACTIVE'];mobile=not (flags['INSIDE_GARRISON'] or flags['IMMOBILE']);valid=ground and not not_ground and mobile
 return dict(flags=flags,known_air_state=not_ground,ground_positive=ground,independently_movable=mobile,grounded_verified=valid,walkable_route_verified=False,interpretation='native_ground_locomotor_and_air_exclusions' if valid else 'known_air_state_exclude_from_ground_history' if not_ground else 'unknown_or_ineligible_ground_state')


def grounded_status(memory,thing):
 """Same-frame, same-identity seven-word sample; unknown is always ineligible."""
 try:
  logic=memory.u32(0xcd8ce4)
  if memory.u32(logic)!=0xbeb630:raise ValueError('not_live_logic')
  start=memory.u32(logic+0x50);vt=memory.u32(thing);oid=memory.u32(thing+0xdc);owner=memory.u32(thing+0x418);template=memory.u32(thing+4);kind=memory.u32(template+8)
  if vt!=0xc4db60 or not oid or memory.u32(owner)!=0xc5bce0 or memory.u32(owner+0x20)!=3:raise ValueError('not_owned_live_thing')
  block=memory.read(thing+0x80,28);words=list(struct.unpack('<7I',block));end=memory.u32(logic+0x50)
  if start!=end or memory.u32(0xcd8ce4)!=logic or memory.u32(thing)!=vt or memory.u32(thing+0xdc)!=oid or memory.u32(thing+0x418)!=owner or memory.u32(thing+4)!=template or memory.u32(template+8)!=kind or memory.u32(owner+0x20)!=3 or memory.read(thing+0x80,28)!=block:raise ValueError('ground_status_changed_during_read')
  return dict(decode(words),status='verified_native_status',frame=start,end_frame=end,object_id=oid,owner=hex(owner),type_hash=hex(kind),status_words=[hex(w) for w in words],word_offsets=[hex(0x80+4*i) for i in range(7)],source='native_name_value_records_plus_generic_setter7274c0',mutations=False)
 except Exception as error:return dict(status='unknown',grounded_verified=False,ground_positive=False,walkable_route_verified=False,reason_code=type(error).__name__,mutations=False)
