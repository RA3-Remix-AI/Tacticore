"""Bounded own-only route observations for calibration. No enemy reads or commands."""
import argparse,hashlib,importlib.util,json,math,struct,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('own_route_backend',HERE.parent/'ground-normal-aux/lease.py');b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--seconds',type=float,default=90);p.add_argument('--output',type=Path,required=True);a=p.parse_args();raw=a.session.read_bytes();s=json.loads(raw.decode('utf-8-sig'));m=b.Memory(s['pid'],s);a.output.mkdir(parents=True,exist_ok=False);last={};saved=0;end=time.monotonic()+min(max(a.seconds,1),180);catalog=b.load_catalog()
 try:
  while time.monotonic()<end:
   if a.session.read_bytes()!=raw:raise ValueError('session_changed')
   logic=m.u32(0xcd8ce4);frame=m.u32(logic+0x50)
   if not frame or m.u32(logic)!=0xbeb630:time.sleep(.2);continue
   snapshot=b.own_candidates(m,3,catalog);rows=[]
   for unit in snapshot['candidates']:
    if unit['type_hash'] not in ('0x19ab11af','0x2c358c61','0x33026fa1'):continue
    ptr=int(unit['address'],0);owner=int(unit['owner_address'],0);xyz=list(struct.unpack('<fff',m.read(ptr+0x38,12)));hp=m.f32(m.u32(ptr+0x33c)+4)
    status84=m.u32(ptr+0x84)
    if status84&(0x20000000|0x80000):continue
    if not all(math.isfinite(x) for x in xyz+[hp]) or hp<=0:continue
    if m.u32(ptr)!=0xc4db60 or m.u32(ptr+0xdc)!=unit['object_id'] or m.u32(ptr+0x418)!=owner or m.u32(owner+0x20)!=3 or m.u32(m.u32(ptr+4)+8)!=int(unit['type_hash'],0):continue
    if unit['object_id'] in last and math.dist(xyz,last[unit['object_id']])<20:continue
    if m.u32(ptr+0x84)!=status84:continue
    rows.append(dict(object_id=unit['object_id'],type_hash=unit['type_hash'],xyz=xyz,hp=hp,status84=hex(status84)))
   lastframe=m.u32(logic+0x50)
   if m.u32(0xcd8ce4)!=logic or not frame<=lastframe<=frame+2:time.sleep(.05);continue
   for row in rows:
    target=a.output/(str(frame).zfill(8)+'-'+str(row['object_id'])+'.json')
    b.durable(target,dict(session_id=s['session_id'],pid=s['pid'],player_id=3,logic_frame_candidate=frame,own_objects=[row],model_eligible=False,source_collector_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),method='live_owned_ground_identity_and_actual_position_only',mutations=False));last[row['object_id']]=row['xyz'];saved+=1
   if saved>=1200:break
   time.sleep(.2)
 finally:m.close();print(json.dumps(dict(directory=str(a.output),observations=saved,commands=0,model_eligible=False)))
if __name__=='__main__':main()
