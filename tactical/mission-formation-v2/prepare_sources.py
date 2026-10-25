"""Generate an isolated formation mission revision from frozen proven primitives.
Never rewrites a loaded predecessor DLL or any sibling source.
"""
from pathlib import Path
import hashlib,json,re
HERE=Path(__file__).resolve().parent;TACTICAL=HERE.parent
def replace(text,old,new,count=1):
 if text.count(old)!=count:raise ValueError('source_contract_changed:'+old[:80])
 return text.replace(old,new)
def main():
 base=TACTICAL/'ordered-combo';ground=TACTICAL/'ground-normal-terrain-aux'
 source=(base/'lease.cpp').read_text();shared=(base/'shared.h').read_text();host=(base/'host.cpp').read_text()
 shared=shared.replace('0x4f434231u','0x4d464d32u').replace('0x378','0x37f').replace('#define T_CAP 4096','#define T_CAP 8192')
 shared=replace(shared,'struct Event {','struct Support {uint32_t thing,id,hash,update,original_team,detach_calls,return_calls,returned,move_calls,native_move,native_attack,native_add,native_remove,native_stop,stop_calls,private_stop_calls,private_stop_frame,stable_samples,gate_samples,last_sample_frame,disposed_verified,absence_samples,last_absence_frame;float stopped_xyz[3];};\nstruct Event {')
 shared=replace(shared,'uint32_t active_weapon_entry,active_weapon_asset,active_weapon_ammo,status84;','uint32_t active_weapon_entry,active_weapon_asset,active_weapon_ammo,status84;uint32_t unit_id,role,mission_stage,route_index,nav_step,target_visible,mission_deadline_frame,mission_reason,native_error;float own_hp,front_goal[3],support_goal[3],command_xyz[3],visible_target_xyz[3];uint32_t argument_path;float argument_limit;')
 shared=replace(shared,'Event events[T_CAP];','Support support;uint32_t route_count,mission_stage,route_index,nav_step,nav_frame,nav_arrivals,nav_paired,nav_last_frame,approach_completed,retreat_completed,combat_started,retreat_started,mission_deadline_frame,combat_frames,retreat_reason,native_stop,front_retreat_arrivals,support_retreat_arrivals,combat_geometry_samples,retreat_requested,heartbeat_tick,front_disposed_verified,front_absence_samples,front_last_absence_frame,cleanup_started,cleanup_front_stopped,cleanup_support_stopped;float route[16][3],safe_front[3],safe_support[3],front_goal[3],support_goal[3],front_hold[3],support_hold[3];Event events[T_CAP];')
 (HERE/'shared.h').write_text(shared)
 # Retain exact current target/FOV and DamageInfo capture primitives.
 source=source[:source.index('static void CALLBACK tick')]+(HERE/'mission_state.cpp.inc').read_text()+source[source.index('static void install'):]
 source=source.replace('TacticalOrderedCombo','TacticalMissionFormation2').replace('RA3TacticalOrderedCombo_','RA3TacticalMissionFormation2_')
 source=source.replace('p->version!=8','p->version!=2').replace('p->lease_frames>180||p->lease_frames<30','p->lease_frames>4500||p->lease_frames<120')
 source=source.replace('i<12','i<13').replace('restore_mask==4095','restore_mask==8191').replace('restore_mask=4095','restore_mask=8191')
 source=replace(source,'static bool unit(){', 'static bool support_valid(){Support& u=p->support;float hp=0;return word(u.thing)==0xc4db60&&word(u.thing+0xdc)==u.id&&word(u.thing+0x418)==p->owner&&word(word(u.thing+4)+8)==0x2c358c61&&word(u.thing+0x374)==u.update&&word(u.update+8)==u.thing&&read(word(u.thing+0x33c)+4,&hp,4)&&isfinite(hp)&&hp>0;}\nstatic bool unit(){')
 # Event publication is role-explicit; paired timer records are adjacent/same tick.
 begin=source.index('static void event(');end=source.index('\ntypedef void',begin)
 source=source[:begin]+(HERE/'event.cpp.inc').read_text()+source[end:]
 source=replace(source,'typedef void (__attribute__((thiscall))*Move)(void*,float*,uint32_t);','typedef void (__attribute__((thiscall))*Move)(void*,float*,void*,float,uint32_t);typedef void (__attribute__((thiscall))*MoveFacade)(void*,float*,uint32_t);static MoveFacade old_move_facade;')
 begin=source.index('static void __attribute__((fastcall)) move_hook');end=source.index('static bool weapon_identity',begin)
 source=source[:begin]+(HERE/'movement.cpp.inc').read_text()+source[end:]
 begin=source.index('static void __attribute__((fastcall)) attack_hook');end=source.index('\n',begin)
 attack=source[begin:end]
 attack=replace(attack,'old_attack(self,target,shots,source);','if((uintptr_t)self==p->support.update){if(!tag)p->support.native_attack++;event(12,word((uintptr_t)target+0xdc),(uintptr_t)__builtin_return_address(0),0,0,0,1);}old_attack(self,target,shots,source);if((uintptr_t)self==p->support.update)event(13,word((uintptr_t)target+0xdc),0,0,0,0,1);')
 source=source[:begin]+attack+source[end:]
 # Observe both leased members while preserving the proven front damage paths.
 for name in ['transfer','add','remove']:
  begin=source.index('static void __attribute__((fastcall)) '+name+'_hook');end=source.index('\n',begin)
  text=source[begin:end];needle='old_'+name+'('
  # The secondary actor is not handled through the front-only event identity.
  before,after=text.split(needle,1)
  rolekey='(uintptr_t)target==p->support.thing'
  kinds={'transfer':(14,15),'add':(16,17),'remove':(18,19)}[name]
  arg='to_ai' if name=='transfer' else '(uintptr_t)self'
  before+=f'if({rolekey}){{'+('' if name=='transfer' else f'if(!tag)p->support.native_{name}++;')+f'event({kinds[0]},{arg},(uintptr_t)__builtin_return_address(0),0,0,0,1);}}'
  ending='InterlockedDecrement(&p->active);'
  after=after.replace(ending,f'if({rolekey})event({kinds[1]},{arg},0,0,0,0,1);'+ending)
  source=source[:begin]+before+needle+after+source[end:]
 begin=source.index('static void __attribute__((fastcall)) stop_facade_hook');end=source.index('static void __attribute__((fastcall)) attack_facade_hook',begin)
 source=source[:begin]+(HERE/'stops.cpp.inc').read_text()+source[end:]
 source=replace(source,'{0x6eff70,(void*)move_hook,(void**)&old_move,"\\x56\\x8b\\xf1\\x8b\\x4e\\x3c\\x8b\\x01\\x8b\\x50\\x38\\xff\\xd2",13,{},false,false},','{0x76d9d0,(void*)move_hook,(void**)&old_move,"\\x56\\x8b\\xf1\\x57\\x8b\\x7e\\x08\\x8b\\xcf",9,{},false,false},')
 source=replace(source,'{0x790990,','{0x571d90,(void*)move_facade_hook,(void**)&old_move_facade,"\\x83\\xec\\x5c\\x8b\\x44\\x24\\x64\\x56\\x6a\\x01\\x50\\x8b\\xf1",13,{},false,false},\n{0x790990,')
 source=source.replace('&&word(result)==0xc2e324','&&p->mission_stage==2&&word(result)==0xc2e324')
 source=source.replace('bool observed=p->phase==1&&','bool observed=p->phase==1&&p->mission_stage==2&&p->lease_stage==1&&')
 (HERE/'lease.cpp').write_text(source)
 host=host.replace('TacticalOrderedCombo','TacticalMissionFormation2').replace('RA3TacticalOrderedCombo_','RA3TacticalMissionFormation2_').replace('180000','330000').replace('restore_mask==4095','restore_mask==8191')
 host=replace(host,'if(p->phase!=3&&p->phase!=4)InterlockedExchange(&p->stop_requested,1);','if(p->phase!=3&&p->phase!=4){InterlockedExchange(&p->stop_requested,1);DWORD stop=GetTickCount();while(p->phase!=3&&p->phase!=4&&GetTickCount()-stop<10000)Sleep(25);}')
 (HERE/'host.cpp').write_text(host)
 (HERE/'build.ps1').write_text((base/'build.ps1').read_text().replace('TacticalOrderedCombo.dll','TacticalMissionFormation2.dll'))
 provenance={str(path.relative_to(TACTICAL)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [base/'lease.cpp',base/'shared.h',base/'host.cpp',ground/'lease.cpp']}
 (HERE/'primitive-provenance.json').write_text(json.dumps(provenance,indent=2))
if __name__=='__main__':main()
