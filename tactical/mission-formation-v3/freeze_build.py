"""Produce exact DLL layout metadata and offline ABI/source manifest."""
from pathlib import Path
import ctypes,hashlib,importlib.util,json,re,struct,subprocess
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parent.parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 dll=HERE/'bin/TacticalMissionFormation3.dll';raw=dll.read_bytes();pe=struct.unpack_from('<I',raw,0x3c)[0];base=struct.unpack_from('<I',raw,pe+24+28)[0]
 symbols=subprocess.check_output([str(BRIDGE/'toolchain/w64devkit/bin/nm.exe'),'-a',str(dll)],text=True)
 def rva(name):
  values=re.findall(r'^([0-9a-f]+) b '+re.escape(name)+r'$',symbols,re.M)
  if len(values)!=1:raise ValueError('exact_symbol_missing:'+name)
  return int(values[0],16)-base
 layout=dict(dll_sha256=sha(dll),timer_rva=rva('__ZL5timer'),shared_pointer_rva=rva('__ZL1p'))
 (HERE/'inert-layout.json').write_text(json.dumps(layout,indent=2))
 spec=importlib.util.spec_from_file_location('formation_mission_abi',HERE/'lease.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 py=dict(event=ctypes.sizeof(m.Event),tactical=ctypes.sizeof(m.Tactical),events=m.Tactical.events.offset,unused1=0,unused2=0)
 native=json.loads(subprocess.check_output([str(HERE/'bin/tactical_host.exe'),'--layout'],text=True))
 if native!=py:raise ValueError('ABI_layout_mismatch')
 paths=[HERE/'lease.cpp',HERE/'shared.h',HERE/'host.cpp',HERE/'lease.py',HERE/'formation_mission_qualification.py',HERE/'mission_route.py',HERE/'prepare_sources.py',HERE/'freeze_build.py',HERE/'inert-layout.json']+list(HERE.glob('*.cpp.inc'))+[dll,HERE/'bin/tactical_host.exe']
 report=dict(external_dependencies={'mobility_guard.py':sha(HERE.parent/'mobility_guard.py'),'pre_dispatch_formation_v3_contract.py':sha(HERE.parent/'pre_dispatch_formation_v3_contract.py')},schema_version=1,native_unexecuted=True,live_effect_verified=False,abi=py,layout=layout,files={str(p.relative_to(HERE)):sha(p) for p in paths})
 (HERE/'build-manifest.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':main()
