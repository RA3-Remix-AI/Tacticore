"""Sole runner picks a fresh own-only pair then invokes frozen formation CLI once."""
import argparse,importlib.util,json,math,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('runner_recon',HERE/'probe.py');r=importlib.util.module_from_spec(sp);sp.loader.exec_module(r)
def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--natural',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 pre,*rest=r.b.readiness(a.session);m=rest[-1]
 try:
  r.verify_original_entries(m)
  if pre['paused']:raise ValueError('resume_before_run')
  candidates=[]
  for f in pre['units']:
   if f['type_hash']!='0x19ab11af' or not f['eligible'] or f['hp']<40:continue
   for s in pre['units']:
    if s['type_hash']!='0x2c358c61' or not s['eligible'] or s['hp']<40 or abs(s['xyz'][2]-f['xyz'][2])>2:continue
    gap=math.dist(f['xyz'][:2],s['xyz'][:2])
    if 25<=gap<=118:candidates.append((gap,f,s))
  if not candidates:raise ValueError('no_fresh_pair_gap25_118')
  gap,f,s=min(candidates,key=lambda v:v[0]);dx=(f['xyz'][0]-s['xyz'][0])*80/gap;dy=(f['xyz'][1]-s['xyz'][1])*80/gap
  selection=dict(frame=pre['frame'],gap=gap,front=f,support=s,dx=dx,dy=dy,native_mutations=0);r.write(a.output.with_name(a.output.stem+'-selection.json'),selection)
 finally:m.close()
 args=[sys.executable,str(HERE.parent/'formation/lease.py'),'--session',str(a.session),'--natural',str(a.natural),'--front-id',str(f['object_id']),'--support-id',str(s['object_id']),'--dx',str(dx),'--dy',str(dy),'--rear-spacing','80','--seq',str(int(time.monotonic()*1000)&0x7fffffff),'--execute','--output',str(a.output)]
 print(json.dumps(dict(selection=selection,executing_frozen_formation_cli=True)),flush=True)
 raise SystemExit(subprocess.call(args))
if __name__=='__main__':main()
