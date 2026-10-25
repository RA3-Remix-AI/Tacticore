"""Read-only own-player snapshot; no hidden enemy observations are exported."""
import argparse,hashlib,json,math,struct,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'production'))
from observe_production import Memory,read_owner,read_factory
from session_package import verify_session_package

def sample(session,snapshot,player_index):
 if snapshot['pid']!=session['pid']:raise ValueError('Snapshot PID mismatch')
 owners={int(x['owner_address'],0) for x in snapshot['candidates'] if x['owner_index_candidate']==player_index}
 if len(owners)!=1:raise ValueError('Require one owned player')
 owner=next(iter(owners));memory=Memory(session['pid'],session)
 try:
  player=read_owner(memory,owner,player_index)
  logic=memory.u32(0xcd8ce4)
  if not 0x400000<=memory.u32(logic)<0xd3b000:raise ValueError('GameLogic vtable unavailable')
  frame=memory.u32(logic+0x50);map_pointer=memory.u32(logic+0x98);pause_type=memory.u32(logic+0x15c)
  map_name=memory.read(map_pointer,260).split(b'\0',1)[0].decode('ascii',errors='replace') if map_pointer else ''
  own=[];factories=[];seen=set()
  for candidate in snapshot['candidates']:
   if candidate['owner_index_candidate']!=player_index:continue
   thing=int(candidate['address'],0)
   try:
    if memory.u32(thing)!=0xc4db60 or memory.u32(thing+0x418)!=owner:continue
    h=memory.u32(memory.u32(thing+4)+8)
    if h!=int(candidate['type_hash'],0):continue
    hp=memory.f32(memory.u32(thing+0x33c)+4)
    if not math.isfinite(hp) or hp<=0:continue
    ident=memory.u32(thing+0xdc)
    if not ident or ident in seen:continue
    seen.add(ident)
    own.append(dict(object_id=ident,type_hash=hex(h),template_annotation=candidate['catalog'].get('template'),hp=hp,xyz=struct.unpack('<fff',memory.read(thing+0x38,12))))
    if candidate['catalog'].get('cls')==5:
     try:
      factory=read_factory(memory,candidate,owner)
      if factory.get('production_interface_available'):factories.append(factory)
     except RuntimeError:pass
   except RuntimeError:continue
  if memory.u32(0xcd8ce4)!=logic or memory.u32(owner+0x90)!=int(player['ai_player'],0):raise ValueError('Lifecycle changed during sample')
  return dict(session_id=session['session_id'],pid=session['pid'],player_id=player_index,sampled_wall_time=time.time(),game_logic=hex(logic),game_logic_vtable=hex(memory.u32(logic)),logic_frame_candidate=frame,pause_type_candidate=pause_type,frame_rate_verified=False,map_path=map_name,resources=player,own_objects=own,factories=factories,enemy_observations=[],visibility_filter_verified=False,note='Read-only. Own objects only. Catalog labels and frame interpretation remain provisional. No enemy intelligence exported.')
 finally:memory.close()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--session',type=Path,required=True);ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--player',type=int,default=3);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 session=json.loads(a.session.read_text(encoding='utf-8-sig'));snapshot=json.loads(a.snapshot.read_text(encoding='utf-8-sig'))
 package=verify_session_package(session)
 if hashlib.sha256(package.read_bytes()).hexdigest()!=session['mod_sha256']:raise ValueError('Package changed')
 result=sample(session,snapshot,a.player)
 a.output.parent.mkdir(parents=True,exist_ok=True);tmp=a.output.with_suffix('.tmp');tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(a.output)
 print(json.dumps(dict(output=str(a.output),frame=result['logic_frame_candidate'],map=result['map_path'],own_objects=len(result['own_objects']),factories=len(result['factories']))))
if __name__=='__main__':main()
