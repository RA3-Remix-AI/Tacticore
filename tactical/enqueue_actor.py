"""Developer actor preparation using real, paid native Conscript production.
Parent/sole runner only. Never spawns or changes resources/prices.
"""
import argparse,hashlib,json,sys,time,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parent
sys.path[:0]=[str(BRIDGE/'production/persistent'),str(BRIDGE/'integration'),str(BRIDGE/'production')]
from client import ProductionExecutor
from own_candidates import own_candidates,load_catalog
from observe_production import Memory,EXPECTED

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--session',type=Path,default=BRIDGE/'acceptance/active-session.json');ap.add_argument('--natural',type=Path,required=True);ap.add_argument('--count',type=int,default=1);ap.add_argument('--reserve',type=int,default=500);ap.add_argument('--after-report',type=Path,required=True);args=ap.parse_args()
 if not 1<=args.count<=2:raise ValueError('actor_count_bounds')
 if not 50<=args.reserve<=10000:raise ValueError('reserve_bounds')
 session=json.loads(args.session.read_text(encoding='utf-8-sig'));previous=json.loads(args.after_report.read_text(encoding='utf-8-sig'));n=previous.get('native',previous.get('final_mapping',{}))
 lease_ok=n.get('phase') in [2,3,4] and n.get('active')==0 and n.get('restore_mask') in [31,63,127]
 observer_ok=previous.get('pid')==session['pid'] and previous.get('state')==2 and previous.get('error')==0 and previous.get('original_bytes_restored') is True and previous.get('active_detours')==0 and type(previous.get('window_thread')) is int and previous['window_thread']>0 and previous.get('callback_thread')==previous['window_thread']
 if not lease_ok and not observer_ok:raise ValueError('previous_native_component_not_restored')
 m=Memory(session['pid'],session)
 try:
  if m.u32(m.u32(0xcd8ce4)+0x15c):raise ValueError('game_paused')
  signatures={0x6eff70:'568bf18b4e3c8b018b5038ffd2',0x76e690:'837c24040055568bf18b6e08',0x838820:'8b818c00000085c0744f568bb190000000',0x8d8880:'83ec24568b74242c8b4604',0x8cd630:'83ec3453578b7c24408b4704'}
  for repeat in range(2):
   if any(m.read(address,len(bytes.fromhex(code)))!=bytes.fromhex(code) for address,code in signatures.items()):raise ValueError('tactical_entry_not_original_do_not_overlap')
  snap=own_candidates(m,3,load_catalog());factories=[x for x in snap['candidates'] if int(x['type_hash'],0)==0x80d4ea1e and m.f32(m.u32(int(x['address'],0)+0x33c)+4)>0]
  if len(factories)!=1:raise ValueError('require_one_live_own_soviet_barracks')
 finally:m.close()
 run=Path(session['run_directory']);snapshot=run/('actor-own-snapshot-'+uuid.uuid4().hex+'.json');snapshot.write_text(json.dumps(dict(snap,pid=session['pid'],sha256=EXPECTED),indent=2),encoding='utf-8');executor=ProductionExecutor(args.session,snapshot,factories[0]['address'],session['scenario']['commander_id'],args.natural,total_budget=85*args.count,reserve_floor=args.reserve,min_interval_frames=150);results=[]
 try:
  executor.start();start=time.monotonic()
  for index in range(args.count):
   if index:
    until=time.monotonic()+11
    while time.monotonic()<until:time.sleep(.2)
   mem=Memory(session['pid'],session)
   try:frame=mem.u32(mem.u32(0xcd8ce4)+0x50)
   finally:mem.close()
   task=str(uuid.uuid4());command=dict(session_id=session['session_id'],player_id=3,commander_id=session['scenario']['commander_id'],command_id=str(uuid.uuid4()),task_id=task,seq=index+1,unit='conscript',budget=85,reserve=args.reserve,expires_frame=frame+450);receipt=executor.submit(command);results.append(receipt)
   if not receipt.get('accepted'):break
   deadline=time.monotonic()+40
   while time.monotonic()<deadline:
    status=executor.status();entry=next((x for x in status['ledger'] if x['task_id']==task),None)
    if entry and entry.get('completed'):results[-1]=entry;break
    if status.get('native_phase')!=1:break
    time.sleep(.2)
 finally:stopped=executor.stop();output=run/('paid-actor-'+time.strftime('%Y%m%d-%H%M%S')+'.json');output.write_text(json.dumps(dict(session_id=session['session_id'],results=results,stopped=stopped,prior_schema='restored_production_observer' if observer_ok else 'restored_tactical_lease',scope='diagnostic_actor_real_paid_production_not_macro_direction'),indent=2),encoding='utf-8');print(json.dumps(dict(report=str(output),results=results,stop_phase=stopped.get('native_phase'),restore_mask=stopped.get('restore_mask'),active=stopped.get('active_callbacks'))))
if __name__=='__main__':main()
