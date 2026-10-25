"""Read-only frontier candidates from this session's actual own-unit trajectories."""
import argparse,hashlib,importlib.util,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('runner_recon',HERE/'probe.py');r=importlib.util.module_from_spec(sp);sp.loader.exec_module(r)
def own_history(run,session_id):
 points=[]
 for path in sorted(Path(run).glob('*.json')):
  try:d=json.loads(path.read_text(encoding='utf-8-sig'))
  except (OSError,ValueError):continue
  if d.get('session_id')!=session_id:continue
  source=hashlib.sha256(path.read_bytes()).hexdigest()
  if isinstance(d.get('preflight'),dict) and d['preflight'].get('player_id')==3:
   own_ids={u.get('id') for u in d.get('units',[]) if u.get('hash') in (0x19ab11af,0x2c358c61)}
   selected=d['preflight'].get('selected',{})
   if selected.get('type_hash') in ('0x19ab11af','0x2c358c61'):own_ids.add(selected.get('object_id'))
   for event in d.get('events',[]):
    if event.get('kind')!=3 or ('unit_id' in event and event['unit_id'] not in own_ids):continue
    if event.get('owner')!=int(d['preflight']['owner'],0):continue
    points.append(dict(xyz=[event['x'],event['y'],event['z']],frame=event['frame'],source=str(path.resolve()),source_sha256=source,origin='same_session_native_own_position_event'))
  if path.name.endswith('-observations.json'):
   selection=path.with_name(path.name.replace('-observations.json','-selection.json'))
   try:sel=json.loads(selection.read_text(encoding='utf-8-sig'))
   except (ValueError,OSError):continue
   if sel.get('session_id')!=session_id or sel.get('unit',{}).get('type_hash') not in ('0x19ab11af','0x2c358c61'):continue
   for sample in d.get('samples',[]):points.append(dict(xyz=sample['own_xyz'],frame=sample['frame'],source=str(path.resolve()),source_sha256=source,origin='same_session_identity_checked_own_position'))
 return points

def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 pre,s,*rest=r.b.readiness(a.session);m=rest[-1]
 try:
  grid=r.ShroudReader(m);_,clear,_=r.vision_grid_snapshot(m,grid,3,pre['frame']);history=own_history(s['run_directory'],s['session_id']);matches=[];seen=set()
  for point in history:
   if point['frame']>=pre['frame'] or r.cell_for(point['xyz'],grid) in seen or grid.query(3,point['xyz'])!=0:continue
   cell=r.cell_for(point['xyz'],grid);x,y=cell%grid.width,cell//grid.width;neighbors=([cell-1] if x else [])+([cell+1] if x+1<grid.width else [])+([cell-grid.width] if y else [])+([cell+grid.width] if y+1<grid.height else [])
   for u in pre['units']:
    if not u['eligible'] or u['hp']<40 or abs(u['xyz'][2]-point['xyz'][2])>2:continue
    distance=math.dist(u['xyz'][:2],point['xyz'][:2])
    if 20<=distance<=590:matches.append(dict(unit_id=u['object_id'],distance=distance,target=point,grid_cell=cell,region_id=r.region_for(cell,grid),adjacent_current_clear=any(n in clear for n in neighbors)))
   seen.add(cell)
  matches.sort(key=lambda v:(not v['adjacent_current_clear'],v['distance']))
  out=dict(session_id=s['session_id'],frame=pre['frame'],paused=pre['paused'],model_eligible=False,history_point_count=len(history),known_fog_cells=len(seen),candidate_count=len(matches),candidates=matches[:20],commands_dispatched=0)
  r.write(a.output,out);print(json.dumps(dict(output=str(a.output),history_points=len(history),known_fog_cells=len(seen),candidate_count=len(matches),best=matches[:1])))
 finally:m.close()
if __name__=='__main__':main()
