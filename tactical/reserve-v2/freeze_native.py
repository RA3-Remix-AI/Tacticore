"""Freeze actual compiled inputs/output and independently address inert globals."""
import hashlib,json,re,struct,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 dll=HERE/'bin/TacticalReserve2.dll';host=HERE/'bin/tactical_host.exe'
 data=dll.read_bytes();pe=struct.unpack_from('<I',data,0x3c)[0];base=struct.unpack_from('<I',data,pe+24+28)[0]
 nm=HERE.parent.parent/'toolchain/w64devkit/bin/nm.exe'
 symbols=subprocess.check_output([str(nm),'-a',str(dll)],text=True)
 def rva(name):
  found=re.findall(r'^([0-9a-fA-F]+) [bBdD] '+re.escape(name)+r'$',symbols,re.M)
  if len(found)!=1:raise ValueError('ambiguous_symbol_'+name)
  return int(found[0],16)-base
 inert=dict(dll_sha256=sha(dll),timer_rva=rva('__ZL5timer'),shared_pointer_rva=rva('__ZL1p'))
 (HERE/'inert-layout.json').write_text(json.dumps(inert,indent=2)+'\n',encoding='utf-8')
 layout=json.loads(subprocess.check_output([str(host),'--layout'],text=True))
 compiled=dict(native_binary_sha256=sha(dll),native_host_sha256=sha(host),native_source_sha256=sha(HERE/'lease.cpp'),native_shared_sha256=sha(HERE/'shared.h'),native_includes_sha256={p.name:sha(p) for p in sorted(HERE.glob('*.cpp.inc'))})
 revision=dict(protocol='single_actor_reserve_v2',magic='0x52535632',version=2,install_message='WM_APP+0x395',pulse_message='WM_APP+0x396',restore_mask=255,hook_count=8,layout=layout,**compiled,
  inert_layout_sha256=sha(HERE/'inert-layout.json'),host_source_sha256=sha(HERE/'host.cpp'),build_script_sha256=sha(HERE/'build.ps1'),
  tests={p.name:sha(p) for p in [HERE/'test_native.cpp',HERE/'test_scheduler.cpp',HERE/'bin/test_native.exe',HERE/'bin/test_scheduler.exe',HERE/'native-positive.bin']},
  software_checks=dict(actual_logic=83,actual_scheduler=26,field_verified=False),runtime_capability_authorized=False,
  rules=dict(admission_consecutive_frames=3,admission_deadline_frames=30,production_binding_words=20,test_stance=2,max_sdk_calls=8,stop_timeout_frames=60,rally_navigation_frames=90,rally_sideward_distance=100,hold_frames=90,hold_frame_gap=1,mission_frames=300,wall_ms=30000,period_ms=20,fallback_ms=100,host_loss_ms=1000))
 (HERE/'revision.json').write_text(json.dumps(revision,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(**inert,revision_sha256=sha(HERE/'revision.json'),**compiled)))
if __name__=='__main__':main()
