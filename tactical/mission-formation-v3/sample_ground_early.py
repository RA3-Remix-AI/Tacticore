"""Own-only seven-word early ground status observation. No commands or hooks."""
import argparse,hashlib,importlib.util,json,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parent.parent
sys.path[:0]=[str(HERE.parent),str(BRIDGE/'integration'),str(BRIDGE/'production')]
from grounded_status import grounded_status,static_proof

def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--seconds',type=float,default=35);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise ValueError('existing_ground_evidence_preserved')
 sp=importlib.util.spec_from_file_location('ground_probe_bridge',HERE/'lease.py');b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b);raw=a.session.read_bytes();s=json.loads(raw.decode('utf-8-sig'));m=b.b.Memory(s['pid'],s);rows=[];until=time.monotonic()+a.seconds
 try:
  proof=static_proof(m.path)
  while time.monotonic()<until:
   if a.session.read_bytes()!=raw:raise ValueError('session_changed')
   own=b.b.own_candidates(m,3,b.b.load_catalog())
   for u in own['candidates']:
    if u['type_hash'] not in ('0x19ab11af','0x2c358c61','0x33026fa1'):continue
    t=int(u['address'],0);g=grounded_status(m,t)
    cache_flags=m.u32(t+0x48);cache_distance=m.f32(t+0x5c)
    hp=m.f32(m.u32(t+0x33c)+4)
    rows.append(dict(object_id=u['object_id'],type_hash=u['type_hash'],xyz=u['xyz'],hp=hp,grounded_status=g,height_cache_flags=hex(cache_flags),height_cache_valid=bool(cache_flags&4),cached_height_distance=cache_distance,height_cache_semantics='diagnostic_only_not_ground_eligibility'))
   time.sleep(.5)
 finally:m.close()
 out=dict(session_id=s['session_id'],pid=s['pid'],source='own_only_early_native_status_contrast',ground_reader_sha256=hashlib.sha256((HERE.parent/'grounded_status.py').read_bytes()).hexdigest(),static_proof=proof,rows=rows,normal_ground_positive_observed=any(x['grounded_status'].get('grounded_verified') for x in rows),mutations=False,model_eligible=False,walkable_route_verified=False)
 a.output.write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(dict(output=str(a.output),samples=len(rows),positives=sum(x['grounded_status'].get('grounded_verified',False) for x in rows),type_counts={k:sum(x['type_hash']==k for x in rows) for k in ['0x19ab11af','0x2c358c61','0x33026fa1']})))
if __name__=='__main__':main()
