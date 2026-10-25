"""Read-only live observations -> model-safe battlefield contract.
No observer data, calls, commands, injection, hidden-object dump, or new memory
reads of hidden HP/death events. Unknown capability templates are excluded.
"""
import math,struct
from native_read import ShroudReader,walk_live_things,cached_object_shroud,read_player_relation,runtime_invisibility_safe,object_footprint_status,vision_grid_snapshot
class VisibilityCollector:
 def __init__(self,memory,session,player_id,projection,region_size=512):
  if player_id!=projection.player or session['session_id']!=projection.session or session['mod_sha256']!=projection.sha:raise ValueError('Visibility identity mismatch')
  if not 128<=region_size<=2048:raise ValueError('Region size bounds')
  self.m=memory;self.session=session;self.player_id=player_id;self.projection=projection;self.region_size=region_size;self.last_frame=None;self.private_targets={};self.region_points={};self.vision_metrics={};self.private_clear_cells=frozenset();self.frontier_points={};self.frontier_regions=[]
 def collect(self,game_seconds):
  self.private_targets={};self.region_points={};self.vision_metrics={};self.private_clear_cells=frozenset();self.frontier_points={};self.frontier_regions=[]
  m=self.m;logic=m.u32(0xcd8ce4)
  if m.u32(logic)!=0xbeb630:raise ValueError('GameLogic vtable')
  frame=m.u32(logic+0x50)
  if not math.isfinite(game_seconds) or abs(game_seconds-frame/15)>0.25:raise ValueError('Snapshot clock differs from native frame/15; discard stale sample')
  if self.last_frame is not None and frame<self.last_frame:self.projection.seen.clear();raise ValueError('New match; invalidate collector')
  self.last_frame=frame
  playerlist=m.u32(0xce8c9c);player=m.u32(playerlist+0x30+self.player_id*4)
  if not player or m.u32(player)!=0xc5bce0 or m.u32(player+0x20)!=self.player_id:raise ValueError('Target Player identity')
  ai=m.u32(player+0x90)
  if not ai or m.u32(ai)!=0xc60f60:raise ValueError('Target must be computer AI; observer rejected')
  # Version-pinned read-only patterns. Never call the underlying lazy getter.
  if m.read(0x992130,8)!=bytes.fromhex('8b4928e9b8f1ffff') or m.read(0x990379,7)!=bytes.fromhex('8b448124c20400') or m.read(0x6fda40,6)!=bytes.fromhex('8b81c8000000'):raise ValueError('Visibility native signature mismatch')
  handshake=self.projection.proof.get('handshake')
  if handshake and (logic!=handshake['game_logic'] or player!=handshake['player'] or ai!=handshake['ai_player'] or frame<handshake['frame_min']):raise ValueError('Visibility proof belongs to another native match')
  verified=self.projection.verified()
  grid=ShroudReader(m)
  if handshake and (grid.manager!=handshake['shroud_manager'] or grid.impl!=handshake['shroud_impl']):raise ValueError('Visibility proof shroud context changed')
  metrics,clear_cells,frontiers=vision_grid_snapshot(m,grid,self.player_id,frame,self.region_size)
  observations=[];seen_ids=set();targets={};points={};own_regions={}
  def region_of(xyz):
   def slug(n):return 'm'+str(-n) if n<0 else str(n)
   return 'region_'+slug(math.floor(xyz[0]/self.region_size))+'_'+slug(math.floor(xyz[1]/self.region_size))
  for thing in walk_live_things(m,logic):
   owner=m.u32(thing+0x418)
   if not owner or m.u32(owner)!=0xc5bce0:continue
   owner_index=m.u32(owner+0x20)
   if owner_index==self.player_id:
    own_xyz=struct.unpack('<fff',m.read(thing+0x38,12));body=m.u32(thing+0x33c)
    if body and all(math.isfinite(x) for x in own_xyz) and m.f32(body+4)>0 and grid.query(self.player_id,own_xyz)==1:
     rid=region_of(own_xyz);points.setdefault(rid,list(own_xyz));own_regions[rid]={'region_id':rid,'relation':'self','observed_at_game_seconds':game_seconds,'currently_visible':verified,'role_counts':{}}
    continue
   if not verified or read_player_relation(m,player,owner_index)!='enemy':continue
   template=m.u32(thing+4);type_hash=hex(m.u32(template+8))
   safe=self.projection.safety.get('templates',{}).get(type_hash)
   if not safe or not safe.get('source_audited_no_intrinsic_stealth') or not runtime_invisibility_safe(m,thing):continue
   footprint=object_footprint_status(m,thing,self.player_id,grid)
   if footprint!=1:continue
   xyz=struct.unpack('<fff',m.read(thing+0x38,12))
   if not all(math.isfinite(x) for x in xyz) or grid.query(self.player_id,xyz)!=1:continue
   oid=m.u32(thing+0xdc)
   if not oid or oid in seen_ids:continue
   body=m.u32(thing+0x33c)
   hp=m.f32(body+4) if body else 0
   if not math.isfinite(hp) or hp<=0:continue
   # Revalidate admission and immutable identity after reading visible fields.
   if m.u32(thing)!=0xc4db60 or m.u32(thing+4)!=template or m.u32(thing+0x418)!=owner or m.u32(thing+0xdc)!=oid:continue
   now_xyz=struct.unpack('<fff',m.read(thing+0x38,12))
   if now_xyz!=xyz or object_footprint_status(m,thing,self.player_id,grid)!=1 or grid.query(self.player_id,now_xyz)!=1 or not runtime_invisibility_safe(m,thing):continue
   if read_player_relation(m,player,owner_index)!='enemy':continue
   seen_ids.add(oid);region=region_of(xyz)
   cid=self.projection.contact_id(owner_index,oid)
   targets[cid]={'address':thing,'object_id':oid,'type_hash':type_hash,'owner':owner,'owner_player_id':owner_index,'xyz':list(xyz),'hp':hp,'observed_frame':frame,'region_id':region}
   points.setdefault(region,list(xyz))
   observations.append({'object_id':oid,'owner_player_id':owner_index,'relation':'enemy','type_hash':type_hash,'terrain_shroud':1,'object_shroud_cached':cached_object_shroud(m,thing,self.player_id),'object_shroud_reconstructed':1,'object_visibility_method':'native_footprint_reconstruction','runtime_stealth_safe':True,'identity_stable':True,'alive':True,'observer_fallback':False,'region_id':region})
  end=m.u32(logic+0x50)
  if m.u32(0xcd8ce4)!=logic or end<frame or end-frame>2 or m.u32(player+0x90)!=ai or m.u32(playerlist+0x30+self.player_id*4)!=player or not grid.stable():raise ValueError('Non-atomic visibility snapshot changed; discard whole sample')
  result=self.projection.project(observations,game_seconds)
  # Publish private execution lookup only after complete sample validation.
  # Last-seen contacts intentionally have no commandable native target entry.
  current={c['contact_id'] for c in result['contacts'] if c['currently_visible']}
  self.private_targets={cid:target for cid,target in targets.items() if cid in current}
  self.region_points=points
  self.vision_metrics=metrics;self.private_clear_cells=clear_cells
  own_z=next((p[2] for p in points.values()),0.0)
  self.frontier_points={rid:[p[0],p[1],own_z] for rid,p in frontiers.items() if rid not in points}
  self.frontier_regions=[{'region_id':rid,'relation':'unknown','observed_at_game_seconds':game_seconds,'currently_visible':False,'role_counts':{}} for rid in self.frontier_points]
  known={r['region_id'] for r in result['regions']}
  result['regions'].extend(r for rid,r in own_regions.items() if rid not in known)
  return result
