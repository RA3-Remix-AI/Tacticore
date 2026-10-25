"""Research-only aggregate census: terrain vs lazy cache vs footprint.
No hidden object IDs, positions, types or HP are written. Never send this
aggregate ground-truth diagnostic to a model/controller.
"""
import argparse,collections,json,struct,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT.parent/'production'))
from observe_production import Memory
from native_read import ShroudReader,walk_live_things,cached_object_shroud,object_footprint_status

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--session',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--safety',type=Path,default=ROOT/'template-safety-2d7873e1.json');a=ap.parse_args()
 s=json.loads(a.session.read_text(encoding='utf-8-sig'));safe=json.loads(a.safety.read_text(encoding='utf-8-sig'));m=Memory(s['pid'],s);rows=collections.Counter();errors=collections.Counter()
 try:
  logic=m.u32(0xcd8ce4);start=m.u32(logic+0x50)
  if start==0:raise ValueError('No live match frame; session ended/loading')
  grid=ShroudReader(m)
  for obj in walk_live_things(m,logic):
   owner=m.u32(obj+0x418)
   if not owner or m.u32(owner)!=0xc5bce0:continue
   oi=m.u32(owner+0x20)
   if oi not in (3,4):continue
   xyz=struct.unpack('<fff',m.read(obj+0x38,12));h=hex(m.u32(m.u32(obj+4)+8));audit=h in safe['templates'];record=m.u32(obj+0x9c);dirty=m.read(record+0xf8,1)[0] if record else None
   for viewer in (2,3,4):
    if viewer==oi:continue
    try:
     terrain=grid.query(viewer,xyz);cached=cached_object_shroud(m,obj,viewer);foot=object_footprint_status(m,obj,viewer,grid)
     rows[f'viewer{viewer}:owner{oi}:terrain{terrain}:cache{cached}:foot{foot}:dirty{dirty}:audited{int(audit)}']+=1
    except ValueError as e:errors[str(e)]+=1
  r={'session_id':s['session_id'],'pid':s['pid'],'frame_interval':[start,m.u32(logic+0x50)],'grid_stable':grid.stable(),'counts':dict(rows),'read_errors':dict(errors),'diagnostic_only':True,'model_eligible':False,'mutations':False,'note':'Aggregate truth research only; no hidden object list, coordinates, HP or types. Not model intelligence.'}
  a.output.write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r,indent=2))
 finally:m.close()
if __name__=='__main__':main()
