"""Complete sampled own-foot roster, including ineligible and garrisoned actors.

This diagnostic never authorizes a lease. Absence from the own roster is not death.
Only addresses in the caller's current owned live-list snapshot are read.
"""
import math
import struct

FOOT={'0x19ab11af','0x2c358c61'}

def sample(memory, own):
 start=own['frame_start'];logic=memory.u32(0xcd8ce4);rows=[]
 if own['frame_end']!=start or memory.u32(logic+0x50)!=start:
  return dict(atomic=False,frame=start,rows=[],reason='owned_roster_frame_changed')
 for actor in own['candidates']:
  if actor['type_hash'] not in FOOT:continue
  thing=int(actor['address'],0);owner=int(actor['owner_address'],0)
  try:
   def read():
    if memory.u32(thing)!=0xc4db60 or memory.u32(thing+0xdc)!=actor['object_id'] or memory.u32(thing+0x418)!=owner:raise ValueError('not_current_owned_actor')
    if hex(memory.u32(memory.u32(thing+4)+8))!=actor['type_hash']:raise ValueError('owned_actor_type_changed')
    update=memory.u32(thing+0x374);body=memory.u32(thing+0x33c)
    if not update or memory.u32(update+8)!=thing:raise ValueError('bound_update_unavailable')
    sm=memory.u32(update+0x3c);state=memory.u32(sm+4)
    return dict(vtable=memory.u32(thing),object_id=memory.u32(thing+0xdc),owner=memory.u32(thing+0x418),
     type_hash=hex(memory.u32(memory.u32(thing+4)+8)),update=update,body=body,
     hp=memory.f32(body+4),xyz=list(struct.unpack('<3f',memory.read(thing+0x38,12))),
     team=memory.u32(thing+0x414),holder=memory.u32(thing+0x238),status_words=list(struct.unpack('<7I',memory.read(thing+0x80,28))),
     state_id=memory.u32(state+4),state_vtable=memory.u32(state),sm_flags=memory.u32(sm+0x78),
     path=memory.u32(update+0x150),command_source=memory.u32(update+0x50))
   before=read();after=read()
   if before!=after or before['vtable']!=0xc4db60 or before['object_id']!=actor['object_id'] or before['owner']!=owner or before['type_hash']!=actor['type_hash'] or not math.isfinite(before['hp']) or not all(math.isfinite(v) for v in before['xyz']):raise ValueError('owned_actor_sample_changed')
   words=before['status_words'];before.update(sample_status='current_owned_actor_observed',garrison_flag=bool(words[61>>5]&(1<<(61&31))),immobile_flag=bool(words[51>>5]&(1<<(51&31))),alive_at_sample=before['hp']>0,borrow_authorized=False)
   rows.append(before)
  except (ValueError,OSError,KeyError) as error:
   rows.append(dict(object_id=actor['object_id'],sample_status='unknown',reason=type(error).__name__,borrow_authorized=False))
 end=memory.u32(logic+0x50)
 if end!=start or memory.u32(0xcd8ce4)!=logic:
  return dict(atomic=False,frame=start,end_frame=end,rows=[],reason='actor_sampling_frame_changed')
 return dict(protocol='complete_sampled_owned_foot_roster_v1',atomic=True,frame=start,end_frame=end,
  rows=rows,all_current_owned_ids=[u['object_id'] for u in own['candidates']],mutations=False,
  borrow_authorized=False,missing_actor_means='unknown_not_currently_owned_never_death_proof')
