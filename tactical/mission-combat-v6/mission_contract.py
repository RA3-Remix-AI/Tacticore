"""Trusted local mission inputs, never model-generated coordinates."""
import math
def validate_mission(value,pre,memory,expires_frame=None):
 if not isinstance(value,dict) or value.get('schema_version')!=1:raise ValueError('mission_schema')
 now=pre['frame'];deadline=expires_frame if expires_frame is not None else value.get('expires_frame',now+4500)
 if type(deadline) is not int or not 300<=deadline-now<=4500:raise ValueError('mission_deadline')
 limits={key:value.get(key,default) for key,default in [('approach_frames',2100),('engage_frames',300),('retreat_frames',1800)]}
 if any(type(limits[k]) is not int or not lo<=limits[k]<=hi for k,lo,hi in [('approach_frames',30,2100),('engage_frames',180,300),('retreat_frames',60,1800)]):raise ValueError('mission_phase_limit')
 fraction=value.get('retreat_hp_fraction',.4)
 if type(fraction) not in [float,int] or isinstance(fraction,bool) or not math.isfinite(fraction) or not .2<=fraction<=.8:raise ValueError('mission_health_limit')
 point=value.get('retreat_point');selected=pre['selected'];implicit=point is None or value.get('origin_policy')=='implicit_actor_origin'
 if implicit:point=None
 if point is None:point=dict(xyz=selected['xyz'],observed_frame=now,source='own_actor_history',anchor_object_id=selected['object_id'])
 if not isinstance(point,dict) or set(point)-{'xyz','observed_frame','source','anchor_object_id'} or not isinstance(point.get('xyz'),(list,tuple)) or len(point['xyz'])!=3 or any(type(x) not in [int,float] or isinstance(x,bool) or not math.isfinite(x) for x in point['xyz']) or type(point.get('observed_frame')) is not int or not 0<=now-point['observed_frame']<=60:raise ValueError('retreat_point_invalid')
 point=dict(point,xyz=list(point['xyz']));anchor_address=anchor_hash=0
 if point['source']=='own_actor_history':
  if point.get('anchor_object_id',selected['object_id'])!=selected['object_id'] or math.dist(point['xyz'],selected['xyz'])>15:raise ValueError('retreat_origin_not_actual_actor_position')
 elif point['source']=='own_home_base':
  oid=point.get('anchor_object_id');matches=[x for x in pre['units'] if x['object_id']==oid]
  # Infantry-only readiness does not enumerate buildings. Scan the live list by ID.
  logic=int(pre['logic'],0);cursor=memory.u32(logic+0xb4);seen=set();anchor=None;start=memory.u32(logic+0x50)
  for _ in range(20000):
   if not cursor:break
   if cursor in seen:raise ValueError('retreat_anchor_list_cycle')
   seen.add(cursor)
   if memory.u32(cursor+0xdc)==oid:anchor=cursor
   cursor=memory.u32(cursor+0x7c)
  if cursor or start!=memory.u32(logic+0x50) or not anchor:raise ValueError('retreat_anchor_not_same_frame_live')
  anchor_address=anchor;anchor_hash=memory.u32(memory.u32(anchor+4)+8)
  # Exact Soviet construction yard hash is supplied by the audited own catalog.
  from own_candidates import load_catalog
  catalog=load_catalog();entry=catalog.get(anchor_hash,{})
  if memory.u32(anchor)!=0xc4db60 or memory.u32(anchor+0x418)!=int(pre['owner'],0) or entry.get('template')!='SovietConstructionYard' or anchor_hash!=0xc16ff13f:raise ValueError('retreat_anchor_not_own_construction_yard')
  pos=[memory.f32(anchor+0x38+4*i) for i in range(3)];d=math.hypot(pos[0]-point['xyz'][0],pos[1]-point['xyz'][1])
  if not 80<=d<=300 or abs(pos[2]-point['xyz'][2])>300 or memory.f32(memory.u32(anchor+0x33c)+4)<=0:raise ValueError('retreat_point_inside_anchor_or_out_of_bound')
 else:raise ValueError('retreat_source_invalid')
 return dict(schema_version=1,origin_policy='implicit_actor_origin' if implicit else 'explicit_fixed_point',expires_frame=deadline,retreat_point=point,anchor_address=anchor_address,anchor_hash=anchor_hash,retreat_hp_fraction=float(fraction),engagement_policy='bounded_single_order_native_burst',damage_goal_fraction=.2,damage_goal_cap=150.,**limits)
