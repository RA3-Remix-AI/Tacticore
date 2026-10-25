"""Pure RPM terminal audit of a completed MCT1/MCT2 case; never game calls."""
import argparse,ctypes as c,hashlib,importlib.util,json,struct,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--session',type=Path,required=True);ap.add_argument('--report',type=Path,required=True);ap.add_argument('--directory',choices=['mission-combat','mission-combat-v2','mission-combat-v3','mission-combat-v4','mission-combat-v5'],required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 if a.output.exists():raise ValueError('existing_terminal_audit_preserved')
 raw=a.report.read_bytes();report=json.loads(raw.decode('utf-8-sig'));session=json.loads(a.session.read_text(encoding='utf-8-sig'));folder=HERE.parent/a.directory;layout=json.loads((folder/'inert-layout.json').read_text());dll=folder/'bin'/{'mission-combat':'TacticalMissionCombat.dll','mission-combat-v2':'TacticalMissionCombat2.dll','mission-combat-v3':'TacticalMissionCombat3.dll','mission-combat-v4':'TacticalMissionCombat4.dll','mission-combat-v5':'TacticalMissionCombat5.dll'}[a.directory]
 if session['session_id']!=report['session_id'] or session['pid']!=report['preflight']['pid'] or hashlib.sha256(dll.read_bytes()).hexdigest()!=report['native_binary_sha256'] or layout['dll_sha256']!=report['native_binary_sha256']:raise ValueError('terminal_source_binding')
 rt=load('runner_terminal_combat',folder/'lease.py');helper=load('runner_terminal_lookup',HERE.parent/'readonly_disposal.py');memory=rt.Memory(session['pid'],session)
 try:
  base=helper.module_base(memory,dll);timer=memory.u32(base+layout['timer_rva']);ptr=memory.u32(base+layout['shared_pointer_rva']);state=rt.Tactical();data=memory.read(ptr,rt.Tactical.events.offset);c.memmove(c.addressof(state),data,len(data));entries=[]
  ident=lambda name:str(uuid.UUID(bytes=struct.pack('<4I',*getattr(state,name))))
  for row in layout['entries']:
   actual=memory.read(row['address'],len(bytes.fromhex(row['expected'])));entries.append(dict(row,actual=actual.hex(),restored=actual.hex()==row['expected']))
  checks=dict(timer_zero=timer==0,native_terminal=state.phase==3 and state.error==0 and state.restore_mask==16383 and state.active==0 and state.return_verified==1,fourteen_entry_bytes=len(entries)==14 and all(x['restored'] for x in entries),same_command=state.pid==session['pid'] and state.token==report['request']['token'] and state.seq==report['request']['seq'] and ident('session')==session['session_id'] and ident('command')==report['request']['command_id'] and ident('task')==report['request']['task_id'])
  output=dict(source_report=str(a.report.resolve()),source_sha256=hashlib.sha256(raw).hexdigest(),pid=session['pid'],session_id=session['session_id'],native_binary_sha256=report['native_binary_sha256'],module_base=hex(base),shared_pointer=hex(ptr),timer=timer,phase=state.phase,error=state.error,restore_mask=state.restore_mask,active=state.active,return_verified=state.return_verified,entries=entries,checks=checks,mutations=False)
  a.output.write_text(json.dumps(output,indent=2),encoding='utf-8');print(json.dumps(dict(output=str(a.output),checks=checks)))
 finally:memory.close()
if __name__=='__main__':main()
