"""Read-only own-unit move/FSM/path diagnostics; offsets remain hypotheses."""
import argparse,json,math,struct,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parent
sys.path[:0]=[str(BRIDGE/'production'),str(BRIDGE/'integration'),str(HERE/'reusable')]
from observe_production import Memory
from own_candidates import own_candidates,load_catalog
from lease import durable

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--session',type=Path,default=BRIDGE/'acceptance/active-session.json');ap.add_argument('--unit-id',type=int,action='append',required=True);ap.add_argument('--samples',type=int,default=250);ap.add_argument('--interval',type=float,default=.1);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 if not 1<=a.samples<=1000 or not .05<=a.interval<=1:raise ValueError('sample_bounds')
 raw=a.session.read_bytes();session=json.loads(raw.decode('utf-8-sig'));m=Memory(session['pid'],session);snapshot=own_candidates(m,3,load_catalog());selected=[u for u in snapshot['candidates'] if u['object_id'] in a.unit_id]
 if len(selected)!=len(set(a.unit_id)):raise ValueError('require_live_unique_own_ids')
 identities={u['object_id']:(int(u['address'],0),int(u['owner_address'],0),int(u['type_hash'],0),int(u['ai_address'],0)) for u in selected};rows=[]
 try:
  for index in range(a.samples):
   if a.session.read_bytes()!=raw:raise ValueError('session_changed')
   logic=m.u32(0xcd8ce4);frame=m.u32(logic+0x50);row=dict(frame=frame,paused=m.u32(logic+0x15c),units=[])
   for oid,(thing,owner,hash_,update) in identities.items():
    if m.u32(thing)!=0xc4db60 or m.u32(thing+0xdc)!=oid or m.u32(thing+0x418)!=owner or m.u32(m.u32(thing+4)+8)!=hash_ or m.u32(thing+0x374)!=update:row['units'].append(dict(object_id=oid,identity_lost=True));continue
    value=dict(object_id=oid,xyz=struct.unpack('<fff',m.read(thing+0x38,12)),team=hex(m.u32(thing+0x414)),source=m.u32(update+0x50))
    sm=m.u32(update+0x3c);value['state_machine']=hex(sm)
    for label,ptr,size,format_ in [('sm_plus_2c_xyz',sm+0x2c,12,'<fff'),('sm_plus_48_xyz',sm+0x48,12,'<fff'),('update_plus_168_xyz_candidate',update+0x168,12,'<fff')]:
     try:
      floats=struct.unpack(format_,m.read(ptr,size));value[label]=list(floats) if all(math.isfinite(x) and abs(x)<1000000 for x in floats) else None
     except RuntimeError:value[label]=None
    for label,ptr in [('sm_plus_78_raw',sm+0x78),('state_pointer_candidate',sm+4),('path_pointer_candidate',update+0x150)]:
     try:value[label]=m.u32(ptr)
     except RuntimeError:value[label]=None
    try:value['state_plus_4_id_candidate']=m.u32(value['state_pointer_candidate']+4)
    except (RuntimeError,TypeError):value['state_plus_4_id_candidate']=None
    try:
     node=m.u32(value['path_pointer_candidate']+0x10);coords=struct.unpack('<ff',m.read(node+0xc,8));value['path_node_candidate']=hex(node);value['node_plus_c_10_xy_candidate']=list(coords) if all(math.isfinite(x) and abs(x)<1000000 for x in coords) else None
    except (RuntimeError,TypeError):value['node_plus_c_10_xy_candidate']=None
    row['units'].append(value)
   if m.u32(0xcd8ce4)==logic and m.u32(logic+0x50)-frame<=1:rows.append(row)
   durable(a.output,dict(session_id=session['session_id'],pid=session['pid'],mutations=False,semantics='FSM request fields copied natively; state/path fields explicitly unverified candidates',samples=rows))
   if index+1<a.samples:time.sleep(a.interval)
 finally:m.close()
if __name__=='__main__':main()
