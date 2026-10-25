#include "common.cpp.inc"
#include "breadcrumb.cpp.inc"
static void combat_tick(uint32_t now){
 float f[3],s[3];role_pos(0,f);role_pos(1,s);float spacing=distance(f,s);p->actual_gap=spacing;
 if(spacing>=25&&spacing<=350&&distance(s,frozen_goals[1])<=15)p->combat_geometry_samples++;
 else if(p->lease_stage==1){begin_retreat(6);return;}
 if(!visible_target()){begin_retreat(2);return;}
 if(now-p->combat_started>=p->combat_frames){begin_retreat(5);return;}
 if(p->lease_stage==0){bool a=stop_settled(now),b=support_settled(now);if(a&&b){
   role_pos(1,frozen_goals[1]);memcpy(p->support_goal,frozen_goals[1],12);memcpy(frozen_goals[0],memory_target,12);memcpy(p->front_goal,memory_target,12);event(86);event(86,0,0,0,0,0,1);event(37);
   uint32_t e=0,ammo=0,asset=current_weapon(&e,&ammo);
   if(asset==0x447ea26e){p->prepare_gate_frame=now;event(42);issue_stop(4);}
   else if(asset==0x41872ecc&&word(p->unit+0x26c)==0){p->lease_stage=3;tag=5;p->toggle_calls++;p->toggle_frame=now;((Button)0x790990)((void*)(uintptr_t)p->unit,(void*)(uintptr_t)p->button,1,0);event(39);tag=0;}
   else begin_retreat(7);
  }else if(now-p->stop_issue_frame>60)request_cleanup(44,now);return;
 }
 if(p->lease_stage==3){if(now!=p->last_ak_frame){p->last_ak_frame=now;p->observed_weapon_asset=current_weapon(&p->observed_weapon_entry,&p->observed_ammo);bool idle=idle_role(0);p->ak_samples=p->observed_weapon_asset==0x447ea26e&&now-p->toggle_frame>=15&&idle?p->ak_samples+1:0;if(p->ak_samples>=3){p->prepare_gate_frame=now;event(42);issue_stop(4);}else if(now-p->toggle_frame>60)begin_retreat(7);}return;}
 if(p->lease_stage==4){if(stop_settled(now)){if(spacing<25||spacing>350||distance(s,frozen_goals[1])>15){begin_retreat(6);return;}event(43);uint32_t e=0,ammo=0;if(current_weapon(&e,&ammo)!=0x447ea26e||!ammo||ammo>3){begin_retreat(7);return;}p->lease_stage=1;tag=2;p->attack_calls++;p->attack_facade_calls++;((Attack)0x572280)((void*)(uintptr_t)(p->update+0x24),(void*)(uintptr_t)p->target_unit,0x7fffffff,1);event(2);tag=0;}else if(now-p->stop_issue_frame>60)request_cleanup(44,now);return;}
 if(p->lease_stage==1){sample_weapon();if(p->damage_count&&p->commit_own_calls)begin_retreat(1);}
}
static void CALLBACK tick(HWND,UINT,UINT_PTR,DWORD){
 if(GetCurrentThreadId()!=p->thread){p->error=30;return;}
 if(p->phase==2){if(!identity()||!unit()||!support_valid()||frame()-p->returned_frame>=p->post_frames)finish();return;}
 if(!identity()){p->error=31;finish();return;}
 if(p->phase==7){if(paused()){p->paused_samples++;return;}fatal_cleanup(frame());return;}
 if(p->phase==5&&(!unit()||!support_valid())){p->error=34;finish();return;}
 if(!unit()||!support_valid()){p->error=32;p->lifecycle_fail++;p->phase=7;p->cleanup_started=frame();fatal_cleanup(frame());return;}
 if(paused()){p->paused_samples++;if(GetTickCount()-start_tick>330000)p->return_pending=1;return;}
 uint32_t now=frame();
 if(p->phase==5){
  if(p->stop_requested||GetTickCount()-start_tick>60000||p->route_ready||p->route_count||p->route_generation||p->memory_ttl_frames!=900||p->approach_limit!=2100||p->retreat_limit!=1800||p->hold_timeout_frames!=60||p->combat_frames<30||p->combat_frames>300||frozen_deadline<=now+120||frozen_deadline-now>4500||now<p->target_observed_frame||now-p->target_observed_frame>60||!admissible_actor(p->unit,p->update)||!admissible_actor(p->support.thing,p->support.update)||!button_identity()||!visible_target()||!p->planning_threat_clear||now<p->planning_threat_frame||now-p->planning_threat_frame>60||p->support.id==p->object_id||p->support.hash!=0x2c358c61||word(p->owner+0xac)!=p->default_team||word(word(p->owner+0x8c)+0x10)!=p->script_team){p->error=34;finish();return;}
  role_pos(0,frozen_origins[0]);role_pos(1,frozen_origins[1]);memcpy(p->safe_front,frozen_origins[0],12);memcpy(p->safe_support,frozen_origins[1],12);float gap=distance(p->safe_front,p->safe_support);if(gap<25||gap>180){p->error=34;finish();return;}
  p->native_move=p->native_attack=p->native_add=p->native_remove=p->native_stop=0;p->support.native_move=p->support.native_attack=p->support.native_add=p->support.native_remove=p->support.native_stop=0;
  memset(frozen_crumbs,0,sizeof(frozen_crumbs));memset(frozen_crumb_counts,0,sizeof(frozen_crumb_counts));memset(last_progress,0,sizeof(last_progress));memset(last_pose_frame,0,sizeof(last_pose_frame));memset(role_arrivals,0,sizeof(role_arrivals));memset(last_arrival_frame,0,sizeof(last_arrival_frame));frozen_follow_role=0;frozen_follow_index=0xffffffffu;regroup_phase=phase_regroups=0;
  p->issued_frame=now;event(71);event(71,0,0,0,0,0,1);p->phase=1;p->original_team=word(p->unit+0x414);p->support.original_team=word(p->support.thing+0x414);
  tag=1;p->detach_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->unit,0);event(1);p->support.detach_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->support.thing,0);event(1,0,0,0,0,0,1);tag=0;
  if(word(p->unit+0x414)!=p->script_team||word(p->support.thing+0x414)!=p->script_team){request_cleanup(35,now);return;}
  read(p->target_unit+0x38,memory_target,12);memory_seen_frame=now;memcpy(p->last_seen_target,memory_target,12);p->target_last_seen_frame=now;memory_hidden=false;p->initial_target_distance=distance(frozen_origins[0],memory_target);p->approach_distance=p->initial_target_distance;
  p->mission_stage=1;p->trail_phase=1;p->leader_role=0;p->follower_role=1;p->motion_state=0;p->nav_frame=now;p->motion_last_tick=0;stop_both(5);event(76);event(76,0,0,0,0,0,1);return;
 }
 event(3);event(3,0,0,0,0,0,1);
 if(p->phase!=1)return;
 if(p->mission_deadline_frame!=frozen_deadline||p->lease_frames!=frozen_lease_frames||p->route_count||p->route_ready||p->route_generation||p->memory_ttl_frames!=900||p->approach_limit!=2100||p->retreat_limit!=1800||p->hold_timeout_frames!=60||p->crumb_count[0]!=frozen_crumb_counts[0]||p->crumb_count[1]!=frozen_crumb_counts[1]){request_cleanup(48,now);return;}
 if(!no_override()||!runtime_ground(0)||!runtime_ground(1)){request_cleanup(38,now);return;}
 for(uint32_t r=0;r<2;r++)if(word(role_update(r)+0x50)!=1){event(96,word(role_update(r)+0x50),0,0,0,0,r);request_cleanup(38,now);return;}
 if(p->follow_active&&(p->follow_crumb_role!=frozen_follow_role||p->follow_crumb_index!=frozen_follow_index)){request_cleanup(48,now);return;}
 if(p->error||p->overflow){request_cleanup(p->error?p->error:60,now);return;}
 if(now+p->post_frames+5>=frozen_deadline||now-p->issued_frame>=frozen_lease_frames||GetTickCount()-start_tick>320000){request_cleanup(48,now);return;}
 if((p->stop_requested||GetTickCount()-p->heartbeat_tick>5000)&&p->mission_stage!=5){p->error=p->stop_requested?49:50;request_cleanup(p->error,now);return;}
 if(now==p->motion_last_tick)return;p->motion_last_tick=now;
 float hp[2]={};for(uint32_t r=0;r<2;r++)read(word(role_thing(r)+0x33c)+4,&hp[r],4);
 if((p->retreat_requested||p->return_pending||hp[0]<=25||hp[1]<=25)&&p->mission_stage<3)begin_retreat(p->retreat_requested?4:3);
 if(p->mission_stage==1&&now-p->issued_frame>2100)begin_retreat(8);
 if(p->mission_stage==3&&now-p->retreat_started>1800){request_cleanup(53,now);return;}
 if(p->mission_stage==1||p->mission_stage==3){navigation_tick(now);return;}
 if(p->mission_stage==4){bool a=stop_settled(now),b=support_settled(now);if(a&&b){float f[3],s[3];role_pos(0,f);role_pos(1,s);if(distance(f,frozen_origins[0])>15||distance(s,frozen_origins[1])>15||fabsf(f[2]-frozen_origins[0][2])>10||fabsf(s[2]-frozen_origins[1][2])>10){request_cleanup(53,now);return;}p->front_retreat_arrivals=p->support_retreat_arrivals=3;event(66);event(66,0,0,0,0,0,1);normal_return();}else if(now-p->stop_issue_frame>60)request_cleanup(45,now);return;}
 if(p->mission_stage==2)combat_tick(now);
}
