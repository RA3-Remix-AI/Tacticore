"""Read-only current own infantry surface evidence; never commands or hooks."""
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;TACTICAL=HERE.parent;BRIDGE=TACTICAL.parent
sys.path[:0]=[str(TACTICAL),str(BRIDGE/'integration'),str(BRIDGE/'production')]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise ValueError('original_evidence_preserved')
 b=load('surface_backend',HERE/'lease.py');g=load('surface_reader',TACTICAL/'grounded_status_v2.py');s=json.loads(a.session.read_text(encoding='utf-8-sig'));m=b.b.Memory(s['pid'],s)
 try:
  static=g.static_proof(m.path);own=b.b.own_candidates(m,3,b.b.load_catalog());rows=[]
  for u in own['candidates']:
   if u['type_hash'] not in ('0x19ab11af','0x2c358c61'):continue
   sample=g.grounded_status(m,int(u['address'],0));rows.append(sample)
  out=dict(session_id=s['session_id'],pid=s['pid'],ground_reader_sha256=hashlib.sha256((TACTICAL/'grounded_status_v2.py').read_bytes()).hexdigest(),static_proof=static,rows=rows,mutations=False,model_eligible=False,walkable_route_verified=False)
  a.output.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8');print(json.dumps(dict(output=str(a.output),rows=len(rows),positive_ids=[r['object_id'] for r in rows if r.get('grounded_verified')],unknown_or_ineligible=len([r for r in rows if not r.get('grounded_verified')]))))
 finally:m.close()
if __name__=='__main__':main()
