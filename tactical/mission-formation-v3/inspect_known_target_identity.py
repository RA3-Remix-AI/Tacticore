"""Research-only identity/live registration of one previously observed target.

Never reads any enemy position or health. Never exports model intelligence.
"""
import argparse,hashlib,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise ValueError('evidence_preserved')
 s=json.loads(a.session.read_text(encoding='utf-8-sig'));raw=a.report.read_bytes();r=json.loads(raw.decode('utf-8-sig'))
 if r['session_id']!=s['session_id'] or r['preflight']['pid']!=s['pid']:raise ValueError('wrong_scene')
 sp=importlib.util.spec_from_file_location('known_identity_bridge',HERE/'lease.py');b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b);m=b.b.Memory(s['pid'],s)
 try:
  target=r['private_target'];tid=target['object_id'];t=target['address'];t=int(t,0) if isinstance(t,str) else t;logic=m.u32(0xcd8ce4);frame=m.u32(logic+0x50);first=m.u32(logic+0xb4);cur=first;seen=set();found=False
  while cur:
   if cur in seen or len(seen)>=20000 or m.u32(cur)!=0xc4db60:raise ValueError('invalid_live_list')
   seen.add(cur);oid=m.u32(cur+0xdc)
   if not oid:raise ValueError('invalid_live_id')
   if oid==tid:found=True
   cur=m.u32(cur+0x7c)
  stable=m.u32(logic+0x50)==frame and m.u32(0xcd8ce4)==logic and m.u32(logic+0xb4)==first
  identity={}
  try:identity=dict(vtable=hex(m.u32(t)),object_id=m.u32(t+0xdc),same_id=m.u32(t+0xdc)==tid,status_words=[hex(m.u32(t+0x80+4*i)) for i in range(7)])
  except Exception as e:identity={'unreadable':type(e).__name__}
  out=dict(session_id=s['session_id'],pid=s['pid'],report_sha256=hashlib.sha256(raw).hexdigest(),native_frame=frame,expected_target_id=tid,live_list_stable=stable,live_list_count=len(seen),target_id_registered=found,address_identity=identity,enemy_positions_read=False,enemy_health_read=False,mutations=False,model_eligible=False,scope='research_current_registration_only_not_retrospective_loss_reason')
  a.output.write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out))
 finally:m.close()
if __name__=='__main__':main()
