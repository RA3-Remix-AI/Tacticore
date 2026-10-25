"""Compile-input/source/binary binding for the independent native MFM12 backend.
No capability is granted and no game process is opened by this program.
"""
from pathlib import Path
import hashlib,json,re,subprocess,sys
H=Path(__file__).resolve().parent;TOOLS=H.parent.parent/'toolchain/w64devkit/bin'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def inputs():
 return dict(native_source_sha256=sha(H/'lease.cpp'),native_shared_sha256=sha(H/'shared.h'),native_includes_sha256={p.name:sha(p) for p in sorted(H.glob('*.cpp.inc'))},native_host_source_sha256=sha(H/'host.cpp'),build_script_sha256=sha(H/'build.ps1'))
def main():
 if '--record-inputs' in sys.argv:
  (H/'native-build-inputs.json').write_text(json.dumps(inputs(),indent=2),encoding='utf-8');return
 if json.loads((H/'native-build-inputs.json').read_text())!=inputs():raise ValueError('source_changed_during_or_since_compilation')
 if set(inputs()['native_includes_sha256'])!={'common.cpp.inc','event.cpp.inc','breadcrumb.cpp.inc','mission_state.cpp.inc','pending.cpp.inc','scheduler.cpp.inc','host_pulse.cpp.inc','stance.cpp.inc'}:raise ValueError('unknown_native_include')
 dll=H/'bin/TacticalMissionFormation12.dll';host=H/'bin/tactical_host.exe';nm=subprocess.check_output([str(TOOLS/'nm.exe'),str(dll)],text=True);pe=subprocess.check_output([str(TOOLS/'objdump.exe'),'-p',str(dll)],text=True);base=int(re.search(r'ImageBase\s+([0-9a-fA-F]+)',pe)[1],16)
 offset=lambda name:int(re.search(r'^([0-9a-fA-F]+) b __ZL\d+'+name+r'$',nm,re.M)[1],16)-base
 layout=dict(dll_sha256=sha(dll),timer_rva=offset('timer'),shared_pointer_rva=offset('p'))
 (H/'inert-layout.json').write_text(json.dumps(layout,indent=2),encoding='utf-8')
 abi=json.loads(subprocess.check_output([str(host),'--layout'],text=True))
 if (abi['event'],abi['tactical'],abi['events'])!=(1616,13266404,28132):raise ValueError('unreviewed_native_abi')
 hook=lambda path:Path(path).read_text().split('static Hook hooks[]={',1)[1].split(';',1)[0]
 entries=lambda p:re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)",(\d+),',hook(p))
 if entries(H/'lease.cpp')[:13]!=entries(H.parent/'mission-formation-v4/lease.cpp') or len(entries(H/'lease.cpp'))!=17:raise ValueError('changed_original_sdk_hook_table')
 r=dict(protocol='mfm12_native_stance_breadcrumb_v1',native_binary_sha256=sha(dll),native_host_sha256=sha(host),**inputs(),native_unexecuted=True,live_effect_verified=False,abi=abi,magic='0x4d463132',version=12,message='WM_APP+0x391',hooks_mask=131071,nonlethal_source_scope=True)
 (H/'revision.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
 block=hook(H/'lease.cpp');rows=[(int(a,0),e.replace('\\x','')) for a,e,n in re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)",(\d+),',block)]
 text='#pragma once\n#define NATIVE_TIMER_RVA '+str(layout['timer_rva'])+'u\n#define NATIVE_P_RVA '+str(layout['shared_pointer_rva'])+'u\n#define NATIVE_DLL_SHA "'+sha(dll)+'"\n'
 text+='struct ExpectedEntry {unsigned address;const char* bytes;};\nstatic ExpectedEntry expected_entries[]={'+','.join('{'+hex(a)+',"'+b+'"}' for a,b in rows)+'};\n'
 (H/'native_layout_rvas.h').write_text(text,encoding='utf-8')
 print(json.dumps(dict(native=r['native_binary_sha256'],host=r['native_host_sha256'],layout=layout,abi=abi)))
if __name__=='__main__':main()
