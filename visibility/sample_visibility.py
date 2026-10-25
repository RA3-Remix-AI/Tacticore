"""Bounded read-only visibility research sample; never exports hidden contacts."""
import argparse,json,struct,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT.parent/'production'))
from observe_production import Memory
from native_read import ShroudReader,walk_live_things,cached_object_shroud,object_footprint_status

def sample(mem,player_index,points):
 logic=mem.u32(0xcd8ce4)
 if mem.u32(logic)!=0xbeb630:raise ValueError('GameLogic signature mismatch')
 frame=mem.u32(logic+0x50);grid=ShroudReader(mem)
 plist=mem.u32(0xce8c9c);player=mem.u32(plist+0x30+4*player_index)
 if not player or mem.u32(player)!=0xc5bce0 or mem.u32(player+0x20)!=player_index:raise ValueError('Target player missing')
 own=[];visible=[];blocked=0
 for obj in walk_live_things(mem,logic):
  owner=mem.u32(obj+0x418)
  if not owner or mem.u32(owner)!=0xc5bce0:continue
  oid=mem.u32(obj+0xdc);xyz=struct.unpack('<fff',mem.read(obj+0x38,12));status=grid.query(player_index,xyz)
  cached=cached_object_shroud(mem,obj,player_index)
  if owner==player:
   own.append({'object_id':oid,'xyz':xyz,'terrain_shroud':status,'object_shroud_cached':cached,'object_shroud_reconstructed':object_footprint_status(mem,obj,player_index,grid)})
  else:
   # Unvalidated stealth/detection: no enemy data exits this sampler.
   blocked+=1
 if mem.u32(0xcd8ce4)!=logic or mem.u32(logic+0x50)<frame or not grid.stable():raise ValueError('Lifecycle changed during visibility sample')
 return {'frame_start':frame,'frame_end':mem.u32(logic+0x50),'pause_type':mem.u32(logic+0x15c),'target_player_id':player_index,'grid':grid.metadata(),'points':[{'label':p['label'],'xy':p['xy'],'terrain_shroud':grid.query(player_index,p['xy'])} for p in points], 'own_objects':own,'battlefield':{'schema_version':1,'viewer_player_id':player_index,'visibility_verified':False,'regions':[],'contacts':[],'formations':[]},'diagnostic_only':True,'hidden_contacts_exported':False,'stealth_gate_verified':False,'note':'Enemy objects omitted until object visibility and stealth safety pass. Own units and explicitly supplied research points only.'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--session',type=Path,required=True);ap.add_argument('--player',type=int,required=True);ap.add_argument('--points',type=Path);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 if not 0<=a.player<20:raise ValueError('Player index range')
 session=json.loads(a.session.read_text(encoding='utf-8-sig'));points=json.loads(a.points.read_text(encoding='utf-8-sig')) if a.points else []
 mem=Memory(session['pid'],session)
 try:
  if mem.read(0x992130,8)!=bytes.fromhex('8b4928e9b8f1ffff') or mem.read(0x990379,7)!=bytes.fromhex('8b448124c20400'):raise ValueError('Native shroud signature mismatch')
  result={'session_id':session['session_id'],'pid':session['pid'],'sampled_wall_time':time.time(),'mutations':False,**sample(mem,a.player,points)}
  a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');print(json.dumps({'output':str(a.output),'frame':result['frame_start'],'own_units':len(result['own_objects']),'contacts':0}))
 finally:mem.close()
if __name__=='__main__':main()
