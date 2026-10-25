"""Read-only selection of a free previously observed OWN ground route point."""
import argparse,importlib.util,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('approach_ground_backend',HERE.parent/'ground-normal-aux/lease.py');b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--routes',type=Path,required=True);p.add_argument('--object-id',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();pre,s,raw,*rest=b.readiness(a.session,a.object_id);m=rest[-1]
 try:
  candidates=b.own_candidates(m,3,b.load_catalog())['candidates'];homes=[u for u in candidates if u['type_hash']=='0xc16ff13f']
  if len(homes)!=1:raise ValueError('one_own_ground_home_required')
  origin=homes[0]['xyz'];actor=pre['selected'];now_progress=math.dist(actor['xyz'][:2],origin[:2]);choices=[]
  for path in a.routes.glob('*.json'):
   source=json.loads(path.read_text(encoding='utf-8-sig'))
   if source.get('session_id')!=s['session_id'] or source.get('pid')!=s['pid'] or source.get('player_id')!=3 or not 0<source.get('logic_frame_candidate',0)<=pre['frame']:continue
   for point in source.get('own_objects',[]):
    xyz=point['xyz']
    if point['type_hash'] not in ('0x33026fa1','0x19ab11af','0x2c358c61') or point['hp']<=0 or not all(math.isfinite(x) for x in xyz):continue
    distance=math.dist(actor['xyz'][:2],xyz[:2]);progress=math.dist(xyz[:2],origin[:2]);occupied=[u['object_id'] for u in candidates if u['object_id']!=actor['object_id'] and math.dist(u['xyz'][:2],xyz[:2])<30 and abs(u['xyz'][2]-xyz[2])<10]
    if not 30<=distance<=550 or abs(xyz[2]-actor['xyz'][2])>2 or progress<now_progress+50 or occupied:continue
    choices.append(dict(path=str(path.resolve()),source_object_id=point['object_id'],point=xyz,observed_frame=source['logic_frame_candidate'],distance=distance,progress_from_own_home=progress))
  choices.sort(key=lambda x:(x['progress_from_own_home'],x['observed_frame']),reverse=True)
  report=dict(session_id=s['session_id'],pid=s['pid'],frame=pre['frame'],actor=actor,own_home=origin,candidates=choices[:12],status='candidate' if choices else 'no_forward_known_free_point',model_eligible=False,sdk_calls=0,note='Own observed ground route only; path reachability still requires native actual arrival. No hidden or current enemy position is consulted.')
  b.durable(a.output,report);print(json.dumps(report,ensure_ascii=False))
 finally:m.close()
if __name__=='__main__':main()
