"""Read-only terminal audit of the exact fc04 ordered-combo calibration."""
import ctypes as c,hashlib,importlib.util,json,re,struct,sys,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path[:0]=[str(ROOT),str(ROOT.parent/'production')]
from readonly_disposal import module_base
from observe_production import Memory
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 report_path=Path(sys.argv[1]);report=json.loads(report_path.read_text(encoding='utf-8-sig'));session=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8-sig'))
 dll=ROOT/'ordered-combo/bin/TacticalOrderedCombo.dll';digest=hashlib.sha256(dll.read_bytes()).hexdigest()
 if digest!='fc04e6675d42983b3fa603fcb402652c73d4637e4cb6d9ae2a9cc280d32d3ebe' or report['native_binary_sha256']!=digest or session['session_id']!=report['session_id']:raise ValueError('binding')
 rt=load('combo_terminal_runtime',ROOT/'ordered-combo/lease.py');memory=Memory(session['pid'],session)
 try:
  base=module_base(memory,dll);timer=memory.u32(base+0x14278);ptr=memory.u32(base+0x14288);state=rt.Tactical();data=memory.read(ptr,rt.Tactical.events.offset);c.memmove(c.addressof(state),data,len(data));entries=[]
  text=(ROOT/'ordered-combo/lease.cpp').read_text();block=text.split('static Hook hooks[]={',1)[1].split(';',1)[0]
  for address,escaped,length in re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)",(\d+),',block):
   expected=bytes.fromhex(escaped.replace('\\x',''));actual=memory.read(int(address,0),int(length));entries.append(dict(address=address,expected=expected.hex(),actual=actual.hex(),restored=actual==expected))
  identity=lambda x:str(uuid.UUID(bytes=struct.pack('<4I',*getattr(state,x))))
  checks=dict(timer_zero=timer==0,twelve_entries=len(entries)==12 and all(x['restored'] for x in entries),native_terminal=state.phase==3 and state.error==0 and state.restore_mask==4095 and state.active==0 and state.return_verified==1,binding=state.pid==session['pid'] and identity('session')==session['session_id'] and identity('command')==report['request']['command_id'] and state.seq==report['request']['seq'])
  output=dict(source_report=str(report_path.resolve()),source_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest(),pid=session['pid'],session_id=session['session_id'],dll_sha256=digest,module_base=hex(base),timer=timer,phase=state.phase,error=state.error,restore_mask=state.restore_mask,active=state.active,return_verified=state.return_verified,entries=entries,checks=checks,mutations=False)
  target=report_path.with_name(report_path.stem+'-terminal-readonly.json');target.write_text(json.dumps(output,indent=2),encoding='utf-8');print(json.dumps(dict(output=str(target),checks=checks)))
 finally:memory.close()
if __name__=='__main__':main()
