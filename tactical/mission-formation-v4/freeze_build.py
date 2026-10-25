"""Snapshot the complete two-stage candidate; never grants game capability."""
from pathlib import Path
import hashlib,importlib.util,json,re,subprocess
HERE=Path(__file__).resolve().parent;TOOLS=HERE.parent.parent/'toolchain/w64devkit/bin'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 dll=HERE/'bin/TacticalMissionFormation4.dll'
 nm=subprocess.check_output([str(TOOLS/'nm.exe'),str(dll)],text=True);pe=subprocess.check_output([str(TOOLS/'objdump.exe'),'-p',str(dll)],text=True);base=int(re.search(r'ImageBase\s+([0-9a-fA-F]+)',pe)[1],16)
 offset=lambda name:int(re.search(r'^([0-9a-fA-F]+) b __ZL\d+'+name+r'$',nm,re.M)[1],16)-base
 layout=dict(dll_sha256=sha(dll),timer_rva=offset('timer'),shared_pointer_rva=offset('p'));(HERE/'inert-layout.json').write_text(json.dumps(layout,indent=2),encoding='utf-8')
 abi=json.loads(subprocess.check_output([str(HERE/'bin/tactical_host.exe'),'--layout'],text=True))
 spec=importlib.util.spec_from_file_location('mfm4_freeze_wrapper',HERE/'lease.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
 import ctypes
 if (abi['event'],abi['tactical'],abi['events'])!=(ctypes.sizeof(w.Event),ctypes.sizeof(w.Tactical),w.Tactical.events.offset):raise ValueError('native_python_abi_mismatch')
 hook=lambda p:Path(p).read_text().split('static Hook hooks[]={',1)[1].split(';',1)[0]
 if hook(HERE/'lease.cpp')!=hook(HERE.parent/'mission-formation-v3/lease.cpp'):raise ValueError('unreviewed_new_sdk_hook')
 local=[p for p in HERE.iterdir() if p.suffix in ('.py','.cpp','.h','.inc','.ps1') or p.name in ('inert-layout.json','primitive-provenance.json')]
 local += [dll,HERE/'bin/tactical_host.exe']
 external=[HERE.parent/'pre_dispatch_formation_v4_contract.py',HERE.parent/'mission_formation_v4_gate_no_lease.py',HERE.parent/'mission_actor_admission_v2.py',HERE.parent/'mission_actor_admission.py',HERE.parent/'grounded_status_v2.py',HERE.parent/'grounded_status.py',HERE.parent/'mobility_guard.py',HERE.parent/'ordered-combo/lease.py',HERE.parent/'ordered_qualification.py',HERE.parent/'stop_sequence.py',HERE.parent/'readonly_disposal.py',HERE.parent.parent/'integration/ground_history.py']
 manifest=dict(schema_version=1,native_unexecuted=True,live_effect_verified=False,abi=abi,layout=layout,magic='0x4d464d34',version=4,message='WM_APP+0x383',hooks_mask=8191,protocol='mfm4_stopped_route_commit_v1',hooks_identical_to_frozen_mfm3=True,files={str(p.relative_to(HERE)):sha(p) for p in local},external_dependencies={str(p.resolve()):sha(p) for p in external})
 (HERE/'build-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 (HERE/'revision.json').write_text(json.dumps(dict(wrapper_filename='lease.py',qualifier_filename='formation_mission_qualification.py',pre_dispatch_helper='pre_dispatch_formation_v4_contract.py',gate_reader='mission_formation_v4_gate_no_lease.py',actor_admission_filename='mission_actor_admission_v2.py',protocol=manifest['protocol'],native_binary_sha256=sha(dll),native_host_sha256=sha(HERE/'bin/tactical_host.exe'),wrapper_sha256=sha(HERE/'lease.py'),qualifier_sha256=sha(HERE/'formation_mission_qualification.py'),manifest_sha256=sha(HERE/'build-manifest.json')),indent=2),encoding='utf-8')
 print(json.dumps(dict(abi=abi,layout=layout,native=sha(dll),host=sha(HERE/'bin/tactical_host.exe'),wrapper=sha(HERE/'lease.py'),qualifier=sha(HERE/'formation_mission_qualification.py'))))
if __name__=='__main__':main()
