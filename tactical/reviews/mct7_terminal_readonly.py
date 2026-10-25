"""Immediate independent successful-terminal RPM capture, no SDK or writes."""
import argparse,ctypes as c,hashlib,importlib.util,json,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(P))
import mission_v7_readonly_disposal as d
import mission_v7_gate_no_lease as gate
def collect(raw_path,session_path,output):
 raw_path=Path(raw_path);data=raw_path.read_bytes();r=json.loads(data.decode('utf-8-sig'));session=json.loads(Path(session_path).read_text(encoding='utf-8-sig'));pre=r['preflight'];n=r['native'];output=Path(output)
 if output.exists():raise ValueError('existing_readonly_capture_preserved')
 if session['pid']!=pre['pid'] or session['session_id']!=r['session_id']:raise ValueError('wrong_session')
 d.verify_session_package(session);profile=d.profile(r);folder=P/profile['directory'];runtime=d.runtime(profile['directory']);memory=d.Memory(session['pid'],session);evidence=dict(source_report=str(raw_path.resolve()),source_sha256=hashlib.sha256(data).hexdigest(),session_id=r['session_id'],pid=pre['pid'],reader_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),snapshots=[],mutations=False)
 try:
  base=d.module_base(memory,folder/'bin'/profile['dll'])
  for index in range(2):
   snap=gate.snapshot(memory,r,base,runtime);state=runtime.Tactical();block=memory.read(int(snap['shared_pointer'],0),runtime.Tactical.events.offset);c.memmove(c.addressof(state),block,len(block));snap.update(return_verified=state.return_verified,personality=hex(state.personality),personality_id=hex(state.personality_id),type_hash=hex(state.type_hash),update=hex(state.update),observed_monotonic_ns=time.monotonic_ns());evidence['snapshots'].append(snap)
   if not index:time.sleep(.12)
  entries={x['address']:x['expected'] for x in d.trusted_entries(r)}
  evidence['checks']=dict(actual_current_binary=r['native_binary_sha256']==d.sha(folder/'bin'/profile['dll'])==profile['layout']['dll_sha256'],same_native_request=all(s['binding_verified'] and s['personality']==pre['personality'] and s['personality_id']==pre['personality_id'] and s['type_hash']==pre['selected']['type_hash'] and s['update']==pre['selected']['ai_address'] for s in evidence['snapshots']),terminal_success=all(s['timer']==0 and s['phase']==3 and s['error']==0 and s['restore_mask']==16383 and s['active']==0 and s['return_verified']==1 for s in evidence['snapshots']),actual_fourteen_pristine=all(len(s['entries'])==len({e['address'] for e in s['entries']})==14 and {e['address']:e['actual'] for e in s['entries']}==entries and all(e['actual']==e['expected'] for e in s['entries']) for s in evidence['snapshots']),same_counters_and_return_frame=all(s['counters']['returned_frame']==n['returned_frame'] and all(s['counters'][k]==n[k] for k in ['issued_frame','detach_calls','return_calls','attack_calls','attack_facade_calls','attack_private_calls','normal_move_facade_calls','normal_move_private_calls','stop_calls','private_stop_calls','toggle_calls','toggle_hook_calls']) for s in evidence['snapshots']))
 finally:memory.close()
 with output.open('x',encoding='utf-8') as f:json.dump(evidence,f,indent=2)
 return evidence
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('raw');p.add_argument('--session',required=True);p.add_argument('--output',required=True);a=p.parse_args();result=collect(a.raw,a.session,a.output);print(json.dumps(result['checks']))
