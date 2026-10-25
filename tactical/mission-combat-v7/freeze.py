"""Freeze built MCT7 files and independent read-only layout. No game access."""
import hashlib,json,re,struct,subprocess
from pathlib import Path
D=Path(__file__).resolve().parent;P=D.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def freeze():
 files={'native_binary_sha256':D/'bin/TacticalMissionCombat7.dll','native_host_sha256':D/'bin/tactical_host.exe','wrapper_sha256':D/'lease.py','native_source_sha256':D/'lease.cpp','native_shared_sha256':D/'shared.h','mission_contract_sha256':D/'mission_contract.py','origin_resolution_helper_sha256':D/'origin_resolution.py','pre_dispatch_helper_sha256':P/'pre_dispatch_v7_contract.py'}
 revision={k:sha(v) for k,v in files.items()};revision['native_includes_sha256']={'mission_tick.inc':sha(D/'mission_tick.inc')};revision['qualification_dependencies_sha256']={name:sha(P/name) for name in ['mission_actor_admission_v2.py','grounded_status_v2.py','grounded_status.py','combo_qualification.py','stop_sequence.py']}
 (D/'revision.json').write_text(json.dumps(revision,indent=2))
 data=(D/'bin/TacticalMissionCombat7.dll').read_bytes();pe=struct.unpack_from('<I',data,0x3c)[0];base=struct.unpack_from('<I',data,pe+52)[0];symbols=subprocess.check_output([str(P.parent/'toolchain/w64devkit/bin/nm.exe'),str(D/'bin/TacticalMissionCombat7.dll')],text=True)
 def locate(name):return int(re.search(r'^([0-9a-f]+) b '+name+r'$',symbols,re.M).group(1),16)-base
 source=(D/'lease.cpp').read_text().split('static Hook hooks[]={',1)[1].split(';',1)[0];entries=[dict(address=int(a,0),expected=b.replace('\\x','')) for a,b,length in re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)",(\d+),',source)]
 assert len(entries)==len({e['address'] for e in entries})==14
 layout=dict(dll_sha256=revision['native_binary_sha256'],timer_rva=locate('__ZL5timer'),shared_pointer_rva=locate('__ZL1p'),entries=entries);(D/'inert-layout.json').write_text(json.dumps(layout,indent=2))
 reader=P/'mission_v7_readonly_disposal.py';text=reader.read_text();text=re.sub(r'MISSION_LAYOUT=\{[^\n]+\}','MISSION_LAYOUT='+repr({k:v for k,v in layout.items() if k!='entries'}),text);text=re.sub(r"MISSION_LAYOUT_SHA='[^']+'","MISSION_LAYOUT_SHA='"+sha(D/'inert-layout.json')+"'",text);reader.write_text(text)
 manifest=dict(directory=D.name,magic='0x4d435437',version=15,message='WM_APP+0x384',dll='TacticalMissionCombat7.dll',mapping_prefix='RA3TacticalMissionCombat7_',restore_mask=16383,layout=json.loads(subprocess.check_output([str(D/'bin/tactical_host.exe'),'--layout'],text=True)),revision=revision,qualifier_sha256=sha(P/'mission_combat_v7_qualification.py'),gate_reader_sha256=sha(P/'mission_v7_gate_no_lease.py'),disposal_reader_sha256=sha(reader),status='offline_only_no_field_capability')
 manifest.update(runtime_qualifier_sha256=sha(P/'mission_combat_v7_runtime_qualification.py'),profile=dict(name='brief_raid_single_order_native_burst',damage_goal_cap=30.,damage_goal_fraction=.2,engage_frames=60,engage_frames_is_limit=True,default_retreat_hp_fraction=.8),admission_scope=[1,10,16],field_state10_effect_capability=False)
 manifest['field_helper_sha256']=sha(P/'mission-formation-v3/field_combat_v7.py')
 (D/'build-manifest.json').write_text(json.dumps(manifest,indent=2));return manifest
if __name__=='__main__':print(json.dumps(freeze(),indent=2))
