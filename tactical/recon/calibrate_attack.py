"""Wait read-only for a nearby visible target, invoke one bounded native attack order."""
import argparse,importlib.util,json,math,struct,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('runner_recon',HERE/'probe.py');r=importlib.util.module_from_spec(sp);sp.loader.exec_module(r)
from projection import VisibilityProjection
from collector import VisibilityCollector
sys.path.insert(0,str(HERE.parent))
from inspect_own_weapons import active_weapon

def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--natural',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--seconds',type=float,default=45);p.add_argument('--max-distance',type=float,default=600);p.add_argument('--post-frames',type=int,default=30);p.add_argument('--economy',action='store_true');p.add_argument('--static-only',action='store_true');p.add_argument('--object-id',type=int);p.add_argument('--ak-only',action='store_true');p.add_argument('--backend',choices=['combat-traced','combat-commit','ordered-attack','ordered-combo'],default='combat-traced');a=p.parse_args()
 if not 20<=a.max_distance<=800:raise ValueError('target_distance_policy_bounds')
 if not 30<=a.post_frames<=180:raise ValueError('post_frames_bounds')
 pre,s,raw,*rest=r.b.readiness(a.session);m=rest[-1]
 try:
  r.verify_original_entries(m);proof,safety=r.bind_session(m,s,3)
  projection=VisibilityProjection(s['session_id'],3,s['mod_sha256'],proof,safety);reader=VisibilityCollector(m,s,3,projection)
  proof_path=a.output.with_name(a.output.stem+'-proof.json');r.write(proof_path,proof)
  deadline=time.monotonic()+min(max(a.seconds,1),90);pairs=[];diagnostics=[]
  while time.monotonic()<deadline:
   if a.session.read_bytes()!=raw:raise ValueError('session_changed')
   frame=m.u32(int(pre['logic'],0)+0x50)
   if m.u32(int(pre['logic'],0)+0x15c):raise ValueError('game_paused')
   reader.collect(frame/15)
   fresh_pre,*newrest=r.b.readiness(a.session);newrest[-1].close()
   units=[]
   for u in fresh_pre['units']:
    if u['type_hash']=='0x19ab11af' and u['eligible'] and u['hp']>25 and (a.object_id is None or u['object_id']==a.object_id):
     try:
      if m.u32(int(u['address'],0)+0x84)&(0x20000000|0x80000):continue
      if a.backend in ('ordered-attack','ordered-combo') and m.u32(int(u['address'],0)+0x238)!=0:continue
      if a.ak_only:
       weapon=active_weapon(m,int(u['address'],0))
       if (weapon.get('selected') or {}).get('template_id')!='0x447ea26e':continue
       u=dict(u,active_weapon_read_only=weapon)
      units.append(r.refresh_own_unit(m,u,int(pre['owner'],0),int(pre['script_team'],0)))
     except (ValueError,RuntimeError):pass
   pairs=[]
   for cid,t in reader.private_targets.items():
    role=safety['templates'].get(t['type_hash'],{}).get('role')
    if a.static_only and role not in ('structure','economy'):continue
    if a.economy and t['type_hash']!='0xc45aaeab':continue
    if not a.economy and role not in ('infantry','armor','structure','economy'):continue
    for u in units:
     d=math.dist(u['xyz'][:2],t['xyz'][:2])
     if d<=a.max_distance:pairs.append((d,cid,u,t,role))
   diagnostics.append(dict(frame=frame,own_conscripts=len(units),visible_contacts=len(reader.private_targets)))
   if pairs:break
   time.sleep(.15)
  if not pairs:
   r.write(a.output.with_name(a.output.stem+'-selection.json'),dict(status='no_dispatch_no_near_visible_target',session_id=s['session_id'],model_eligible=False,diagnostics=diagnostics));print('No nearby visible target; no SDK dispatch');return
  distance,cid,u,t,role=min(pairs,key=lambda v:((v[4]!='infantry') if not a.static_only else False,v[0]));selection=dict(session_id=s['session_id'],frame=frame,distance=distance,unit=u,contact_id=cid,target=t,role=role,economy_exact_refinery_only=a.economy,static_only=a.static_only,requested_actor_id=a.object_id,policy_max_distance=a.max_distance,approach_is_native_attack=True,normal_burst_allowed=a.backend=='ordered-attack',model_eligible=False,diagnostics=diagnostics);r.write(a.output.with_name(a.output.stem+'-selection.json'),selection)
 finally:m.close()
 args=[sys.executable,str(HERE.parent/a.backend/'lease.py'),'--session',str(a.session),'--object-id',str(u['object_id']),'--natural',str(a.natural),'--proof-file',str(proof_path),'--contact-id',cid,'--seq',str(int(time.monotonic()*1000)&0x7fffffff),'--post-frames',str(a.post_frames),'--execute','--output',str(a.output)]
 print(json.dumps(dict(distance=distance,own_unit=u['object_id'],target_contact=cid,executing_single_native_order=True,normal_burst_allowed=a.backend=='ordered-attack')),flush=True)
 child=subprocess.Popen(args);monitor=dict(session_id=s['session_id'],unit_id=u['object_id'],contact_id=cid,model_eligible=False,samples=[],error=None)
 monitor_memory=r.b.Memory(s['pid'],s);reader.m=monitor_memory
 try:
  while child.poll() is None:
   if monitor['error'] is None:
    try:
     f=monitor_memory.u32(int(pre['logic'],0)+0x50);reader.collect(f/15)
     thing=int(u['address'],0)
     if monitor_memory.u32(thing)!=0xc4db60 or monitor_memory.u32(thing+0xdc)!=u['object_id'] or monitor_memory.u32(thing+0x418)!=int(pre['owner'],0) or monitor_memory.u32(monitor_memory.u32(thing+4)+8)!=int(u['type_hash'],0):raise ValueError('own_monitor_identity_changed')
     own_xyz=list(struct.unpack('<fff',monitor_memory.read(thing+0x38,12)))
     target_now=reader.private_targets.get(cid)
     monitor['samples'].append(dict(frame=f,own_xyz=own_xyz,target_currently_visible=target_now is not None,target_xyz=target_now['xyz'] if target_now else None,target_hp=target_now['hp'] if target_now else None,distance=math.dist(own_xyz[:2],target_now['xyz'][:2]) if target_now else None))
    except (RuntimeError,ValueError) as error:monitor['error']=str(error)
   time.sleep(.1)
 finally:monitor_memory.close();r.write(a.output.with_name(a.output.stem+'-observations.json'),monitor)
 raise SystemExit(child.returncode)
if __name__=='__main__':main()
