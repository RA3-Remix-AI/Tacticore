"""Read-only grounding diagnostics. No SDK, GUI, writes or walkability claim."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent/'production'),str(HERE.parent/'integration')]
from observe_production import Memory,EXPECTED
from session_package import verify_session_package
from grounded_status import FLAGS,static_proof,decode,grounded_status

def inspect(memory,object_id):
 logic=memory.u32(0xcd8ce4)
 if memory.u32(logic)!=0xbeb630:raise ValueError('not_live_logic')
 start=memory.u32(logic+0x50);head=memory.u32(logic+0xb4);p=head;seen=set();ids=set();selected=None
 while p:
  if p in seen or len(seen)>=20000:raise ValueError('bad_live_list')
  seen.add(p);vt=memory.u32(p);oid=memory.u32(p+0xdc)
  if vt!=0xc4db60 or not oid or oid in ids:raise ValueError('bad_live_identity')
  ids.add(oid)
  if oid==object_id:
   owner=memory.u32(p+0x418);template=memory.u32(p+4);kind=memory.u32(template+8);update=memory.u32(p+0x374);sm=memory.u32(update+0x3c) if update else 0;state=memory.u32(sm+4) if sm else 0;words=list(struct.unpack('<7I',memory.read(p+0x80,28)))
   if memory.u32(owner)!=0xc5bce0 or memory.u32(owner+0x20)!=3:raise ValueError('not_owned_player3')
   selected=dict(address=hex(p),object_id=oid,type_hash=hex(kind),owner=hex(owner),player_id=3,xyz=list(struct.unpack('<3f',memory.read(p+0x38,12))),status_words=[hex(w) for w in words],status_word_offsets=[hex(0x80+4*i) for i in range(7)],update=hex(update),state_pointer=hex(state),state_id=memory.u32(state+4) if state else None,path=hex(memory.u32(update+0x150)) if update else None,interpretation=decode(words))
   if memory.u32(p+0xdc)!=oid or memory.u32(p+0x418)!=owner or memory.u32(p+4)!=template or list(struct.unpack('<7I',memory.read(p+0x80,28)))!=words:raise ValueError('actor_changed_during_read')
  p=memory.u32(p+0x7c)
 end=memory.u32(logic+0x50)
 if end!=start or memory.u32(logic+0xb4)!=head or memory.u32(0xcd8ce4)!=logic:raise ValueError('not_same_frame_complete_scan')
 return dict(logic=hex(logic),frame=start,end_frame=end,complete_live_scan=True,count=len(ids),actor=selected,actor_absent_from_this_frame=selected is None,absence_is_not_a_death_certificate=True)

def main():
 a=argparse.ArgumentParser();a.add_argument('--session',type=Path,required=True);a.add_argument('--object-id',type=int,required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args();source=args.session.read_bytes();session=json.loads(source.decode('utf-8-sig'));verify_session_package(session)
 record=dict(session_id=session['session_id'],pid=session['pid'],start_time=session['start_time'],reader_sha256=sha(Path(__file__).read_bytes()),static_proof=static_proof(session['game']),mutations=False,grounded_verified=False,walkable_route_verified=False)
 memory=Memory(session['pid'],session)
 try:
  for attempt in range(5):
   try:record['sample']=inspect(memory,args.object_id);break
   except ValueError as error:record['sampling_error']=str(error)
  if args.session.read_bytes()!=source:raise ValueError('session_changed')
 finally:memory.close()
 with args.output.open('x',encoding='utf-8') as out:json.dump(record,out,indent=2,ensure_ascii=False,allow_nan=False)
 print(json.dumps(dict(output=str(args.output),sample=record.get('sample'),error=record.get('sampling_error')),ensure_ascii=False))

if __name__=='__main__':main()
