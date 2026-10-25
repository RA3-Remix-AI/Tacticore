"""Bounded natural visibility transition observer; read-only and research only.
An enemy object enters this diagnostic report only after becoming fully visible.
Hidden samples never carry its coordinates, HP, type or owner details. The last
pre-visibility status can be attached retrospectively after the sighting.
"""
import argparse,json,struct,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT.parent/'production'))
from observe_production import Memory
from native_read import ShroudReader,walk_live_things,cached_object_shroud,read_player_relation,runtime_invisibility_safe,object_footprint_status

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--session',type=Path,required=True);ap.add_argument('--player',type=int,required=True);ap.add_argument('--seconds',type=float,default=30);ap.add_argument('--interval',type=float,default=.5);ap.add_argument('--safety',type=Path,default=ROOT/'template-safety-2d7873e1.json');ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 if not 0<a.seconds<=60 or not .2<=a.interval<=2:raise ValueError('Bounded observation only')
 session=json.loads(a.session.read_text(encoding='utf-8-sig'));safety=json.loads(a.safety.read_text(encoding='utf-8-sig'))
 if safety['package_sha256']!=session['mod_sha256']:raise ValueError('Safety package mismatch')
 m=Memory(session['pid'],session);start=time.monotonic();history={};published={};events=[];samples=[];error=None
 try:
  plist=m.u32(0xce8c9c);player=m.u32(plist+0x30+4*a.player)
  if m.u32(player)!=0xc5bce0 or m.u32(player+0x20)!=a.player or not m.u32(player+0x90):raise ValueError('Computer viewpoint required')
  first_frame=m.u32(m.u32(0xcd8ce4)+0x50)
  while True:
   logic=m.u32(0xcd8ce4);frame=m.u32(logic+0x50);grid=ShroudReader(m);visible_count=0
   if frame<first_frame:raise ValueError('Match reset')
   for obj in walk_live_things(m,logic):
    owner=m.u32(obj+0x418)
    if not owner or m.u32(owner)!=0xc5bce0:continue
    index=m.u32(owner+0x20)
    if index==a.player or read_player_relation(m,player,index)!='enemy':continue
    oid=m.u32(obj+0xdc);template=m.u32(obj+4);h=hex(m.u32(template+8));safe=safety['templates'].get(h)
    if not safe or not runtime_invisibility_safe(m,obj):continue
    xyz=struct.unpack('<fff',m.read(obj+0x38,12));terrain=grid.query(a.player,xyz);cache=cached_object_shroud(m,obj,a.player);footprint=object_footprint_status(m,obj,a.player,grid)
    current=(terrain,footprint);previous=history.get(oid);history[oid]={'frame':frame,'terrain_shroud':terrain,'object_shroud_cached':cache,'object_shroud_reconstructed':footprint}
    if current==(1,1):
     visible_count+=1
     if oid not in published:
      published[oid]={'first_seen_frame':frame,'object_id_research':oid,'template_at_sighting':safe['template'],'first_seen_xyz':list(xyz)}
      if previous:events.append({'object_id_research':oid,'kind':'previous_state_before_first_sighting',**previous})
      events.append({'object_id_research':oid,'kind':'first_full_sighting','frame':frame,'terrain_shroud':1,'object_shroud_cached':cache,'object_shroud_reconstructed':1,'visible_xyz':list(xyz)})
     elif previous and (previous['terrain_shroud'],previous['object_shroud_reconstructed'])!=(1,1):events.append({'object_id_research':oid,'kind':'reacquired','frame':frame,'terrain_shroud':1,'object_shroud_cached':cache,'object_shroud_reconstructed':1,'visible_xyz':list(xyz)})
    elif oid in published and previous and (previous['terrain_shroud'],previous['object_shroud_reconstructed'])==(1,1):events.append({'object_id_research':oid,'kind':'lost_visibility','frame':frame,'terrain_shroud':terrain,'object_shroud_cached':cache,'object_shroud_reconstructed':footprint})
   samples.append({'frame':frame,'pause_type':m.u32(logic+0x15c),'visible_safe_enemy_count':visible_count})
   if time.monotonic()-start>=a.seconds:break
   time.sleep(a.interval)
 except Exception as e:error=type(e).__name__+': '+str(e)
 finally:m.close()
 report={'session_id':session['session_id'],'pid':session['pid'],'viewer_player_id':a.player,'duration_seconds':round(time.monotonic()-start,3),'samples':samples,'sighted_objects':list(published.values()),'events':events,'error':error,'mutations':False,'diagnostic_only':True,'model_eligible':False,'note':'Contains native IDs and coordinates only for objects actually seen. Never pass research artifact to model. No detection claim for excluded intrinsic/active-invisibility templates.'}
 a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'output':str(a.output),'samples':len(samples),'sighted':len(published),'events':len(events),'error':error}))
if __name__=='__main__':main()
