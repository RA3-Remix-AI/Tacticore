"""Offline source fork. Never loads a DLL or touches the game process."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
OUT=HERE/'mission-combat'
OUT.mkdir(exist_ok=True)
if (OUT/'revision.json').exists():raise SystemExit('refusing to overwrite a versioned mission fork; build its build.ps1 instead')
def replace_once(s,a,b):
 if s.count(a)!=1:raise ValueError(('nonunique_source_anchor',a[:80],s.count(a)))
 return s.replace(a,b,1)
for name in ['shared.h','lease.cpp','lease.py','host.cpp','build.ps1']:
 s=(HERE/'ordered-combo'/name).read_text(encoding='utf-8')
 s=s.replace('TacticalOrderedCombo','TacticalMissionCombat').replace('RA3TacticalOrderedCombo_','RA3TacticalMissionCombat_')
 if name=='shared.h':
  s=replace_once(s,'0x4f434231u','0x4d435431u');s=replace_once(s,'WM_APP+0x378','WM_APP+0x37a')
  s=replace_once(s,'uint32_t active_weapon_entry,active_weapon_asset,active_weapon_ammo,status84;','uint32_t active_weapon_entry,active_weapon_asset,active_weapon_ammo,status84;uint32_t mission_stage,stage_revision,stage_frame,move_index;float command_xyz[3],waypoint_distance,own_hp;')
  s=replace_once(s,'Event events[T_CAP];','uint32_t mission_deadline_frame,mission_stage,stage_revision,stage_frame,reason_code,approach_limit,engage_limit,retreat_limit,approach_started,engage_started,retreat_started,retreat_observed_frame,retreat_source,retreat_anchor,retreat_anchor_id,retreat_anchor_hash,normal_move_facade_calls,normal_move_private_calls,move_index,move_started,move_last_progress_frame,arrival_last_frame,waypoint_samples,retreat_arrival_samples,approach_move_calls,retreat_move_calls,checkpoint_count,retreat_index,heartbeat_tick;float retreat_goal[3],waypoint[3],checkpoint[16][3],move_best_distance,approach_distance,own_hp,initial_hp,retreat_hp_fraction;Event events[T_CAP];')
 if name=='lease.cpp':
  s=replace_once(s,'e.seq=0;p->events[i]=e;','e.mission_stage=p->mission_stage;e.stage_revision=p->stage_revision;e.stage_frame=p->stage_frame;e.move_index=p->move_index;memcpy(e.command_xyz,p->waypoint,12);float dx=e.x-p->waypoint[0],dy=e.y-p->waypoint[1];e.waypoint_distance=sqrtf(dx*dx+dy*dy);read(word(p->unit+0x33c)+4,&e.own_hp,4);e.seq=0;p->events[i]=e;')
  s=replace_once(s,'p->private_stop_calls++;p->private_stop_frame=frame();','p->private_stop_calls++;p->private_stop_frame=frame();') # explicit anchor checked
  s=s.replace('(p->lease_stage==0||p->lease_stage==4||p->lease_stage==2)','(p->lease_stage==0||p->lease_stage==4||p->lease_stage==2||p->lease_stage==6||p->lease_stage==7)')
  anchor='struct Hook {uint32_t a;'
  s=replace_once(s,anchor,'''typedef void (__attribute__((thiscall))*NormalMove)(void*,float*,void*,float,uint32_t);typedef void (__attribute__((thiscall))*NormalMoveFacade)(void*,float*,uint32_t);static NormalMove old_normal_move;static NormalMoveFacade old_normal_move_facade;
static void __attribute__((fastcall)) normal_move_hook(void* self,void*,float* xyz,void* path,float limit,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update;if(ours){if(tag==6&&source==1&&!path&&limit>1e30f)p->normal_move_private_calls++;else if(!tag)p->native_move++;event(52,source,(uintptr_t)__builtin_return_address(0));}old_normal_move(self,xyz,path,limit,source);if(ours)event(53,source);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) normal_move_facade_hook(void* self,void*,float* xyz,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update+0x24;if(ours)event(54,source,(uintptr_t)__builtin_return_address(0));old_normal_move_facade(self,xyz,source);if(ours)event(55,source);InterlockedDecrement(&p->active);}
struct Hook {uint32_t a;''')
  anchor='14,{},false,false}};'
  s=replace_once(s,anchor,'''14,{},false,false},
{0x76d9d0,(void*)normal_move_hook,(void**)&old_normal_move,"\\x56\\x8b\\xf1\\x57\\x8b\\x7e\\x08\\x8b\\xcf",9,{},false,false},
{0x571d90,(void*)normal_move_facade_hook,(void**)&old_normal_move_facade,"\\x83\\xec\\x5c\\x8b\\x44\\x24\\x64\\x56\\x6a\\x01\\x50\\x8b\\xf1",13,{},false,false}};''')
  s=s.replace('i<12;i++','i<14;i++').replace('p->restore_mask=4095','p->restore_mask=16383').replace('p->restore_mask==4095','p->restore_mask==16383')
  first=s.index('static void CALLBACK tick(');last=s.index('static void install(',first)
  s=s[:first]+(HERE/'mission-combat/mission_tick.inc').read_text(encoding='utf-8')+'\n'+s[last:]
  s=s.replace('p->version!=8','p->version!=9').replace('p->lease_frames>180||p->lease_frames<30','p->lease_frames>4500||p->lease_frames<300')
  s=s.replace('0x52413374','0x5241337a')
 if name=='host.cpp':
  s=s.replace('180000','660000').replace('p->restore_mask==4095','p->restore_mask==16383')
 (OUT/name).write_text(s,encoding='utf-8')
print('offline source fork complete; wrapper is adapted separately')
