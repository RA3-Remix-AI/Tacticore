static float distance(const float a[3],const float b[3]){float x=a[0]-b[0],y=a[1]-b[1];return sqrtf(x*x+y*y);}
static bool finite_point(const float x[3]){return isfinite(x[0])&&isfinite(x[1])&&isfinite(x[2]);}
static bool support_settled(uint32_t now){Support& s=p->support;if(now==s.last_sample_frame)return false;s.last_sample_frame=now;uint32_t sm=word(s.update+0x3c);float xyz[3];read(s.thing+0x38,xyz,12);bool gate=s.private_stop_calls==s.stop_calls&&now>s.private_stop_frame&&word(s.update+0x50)==1&&!(word(sm+0x78)&0xffff)&&word(s.update+0x150)==0;float d=distance(xyz,s.stopped_xyz);if(gate){s.gate_samples++;s.stable_samples=d<=1?s.stable_samples+1:0;}else s.gate_samples=s.stable_samples=0;memcpy(s.stopped_xyz,xyz,12);return s.gate_samples>=3&&s.stable_samples>=3;}
static void stop_support(){Support& s=p->support;s.stable_samples=s.gate_samples=s.last_sample_frame=0;read(s.thing+0x38,s.stopped_xyz,12);tag=4;s.stop_calls++;((Stop)0x54b0a0)((void*)(uintptr_t)(s.update+0x24),1);event(36,0,0,0,0,0,1);tag=0;}
static void stop_both(uint32_t stage){issue_stop(stage);stop_support();}
static void move_role(bool support,const float* goal){tag=6;if(support)p->support.move_calls++;else p->move_calls++;((MoveFacade)0x571d90)((void*)(uintptr_t)((support?p->support.update:p->update)+0x24),(float*)goal,1);event(52,0,0,0,0,0,support);tag=0;}
static void normal_return(){
 if(unit()&&!p->return_calls){tag=3;p->return_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->unit,1);p->return_verified=unit()&&word(p->unit+0x414)==p->default_team;event(5);tag=0;}
 if(support_valid()&&!p->support.return_calls){tag=3;p->support.return_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->support.thing,1);p->support.returned=support_valid()&&word(p->support.thing+0x414)==p->default_team;event(5,0,0,0,0,0,1);tag=0;}
 if(!p->return_verified||!p->support.returned)p->error=p->error?p->error:37;
 p->returned_frame=frame();p->return_pending=0;p->phase=2;
}
static void begin_retreat(uint32_t reason){
 if(p->mission_stage==3||p->mission_stage==4)return;
 p->retreat_reason=reason;p->retreat_started=frame();p->mission_stage=3;p->route_index=p->approach_completed?p->approach_completed-1:0;p->nav_step=0;p->nav_frame=frame();
 // Retrace only completed, actually observed own waypoints; finish at both initial safe positions.
 if(p->approach_completed>1){memcpy(p->front_goal,frozen_route[p->approach_completed-2],12);if(p->approach_completed>2)memcpy(p->support_goal,frozen_route[p->approach_completed-3],12);else memcpy(p->support_goal,p->safe_front,12);}
 else{memcpy(p->front_goal,p->safe_front,12);memcpy(p->support_goal,p->safe_support,12);}
 stop_both(5);event(63,reason);
}
static bool paired_geometry(const float front[3],const float support[3]){
 float spacing=distance(front,support),vx=p->front_goal[0]-p->support_goal[0],vy=p->front_goal[1]-p->support_goal[1];
 return distance(front,p->front_goal)<=15&&distance(support,p->support_goal)<=15&&spacing>=25&&spacing<=200&&(front[0]-support[0])*vx+(front[1]-support[1])*vy>0;
}
static void approach_leg(uint32_t index){p->mission_stage=1;p->route_index=index;p->nav_step=0;p->nav_frame=frame();p->nav_arrivals=p->nav_paired=p->nav_last_frame=0;memcpy(p->front_goal,frozen_route[index],12);memcpy(p->support_goal,index?frozen_route[index-1]:p->safe_front,12);stop_both(5);event(59,index);}
static void request_cleanup(uint32_t error,uint32_t now){p->error=error;p->mission_stage=5;p->phase=7;p->cleanup_started=now;p->cleanup_front_stopped=p->cleanup_support_stopped=0;}
static void advance_nav(uint32_t now){
 float f[3],s[3];read(p->unit+0x38,f,12);read(p->support.thing+0x38,s,12);
 if(p->nav_step==0){bool a=stop_settled(now),b=support_settled(now);if(a&&b){memcpy(p->front_hold,f,12);memcpy(p->support_hold,s,12);p->nav_step=1;p->nav_arrivals=p->nav_paired=0;p->nav_last_frame=0;event(58);event(58,0,0,0,0,0,1);if(p->mission_stage==1)move_role(false,p->front_goal);else move_role(true,p->support_goal);}else if(now-p->nav_frame>60){request_cleanup(44,now);}return;}
 if(now==p->nav_last_frame)return;
 p->nav_last_frame=now;
 bool approach=p->mission_stage==1;
 if(p->nav_step==1){bool held=distance(approach?s:f,approach?p->support_hold:p->front_hold)<=15;bool arrived=distance(approach?f:s,approach?p->front_goal:p->support_goal)<=15;
  p->nav_arrivals=held&&arrived?p->nav_arrivals+1:0;
  if(p->nav_arrivals>=3){event(61);event(61,0,0,0,0,0,1);p->nav_step=2;p->nav_arrivals=p->nav_paired=0;if(approach)move_role(true,p->support_goal);else move_role(false,p->front_goal);}
 }else if(p->nav_step==2){p->nav_paired=paired_geometry(f,s)?p->nav_paired+1:0;if(p->nav_paired>=3){event(60);event(60,0,0,0,0,0,1);
   if(approach){p->approach_completed++;if(p->approach_completed<frozen_route_count)approach_leg(p->approach_completed);else{p->mission_stage=2;p->combat_started=now;p->nav_step=0;stop_both(0);event(64);}}
   else{p->retreat_completed++;if(p->route_index>1){p->route_index--;memcpy(p->front_goal,frozen_route[p->route_index-1],12);memcpy(p->support_goal,p->route_index>1?frozen_route[p->route_index-2]:p->safe_front,12);p->nav_step=0;p->nav_frame=now;stop_both(5);}
    else if(p->route_index==1){p->route_index=0;memcpy(p->front_goal,p->safe_front,12);memcpy(p->support_goal,p->safe_support,12);p->nav_step=0;p->nav_frame=now;stop_both(5);}
    else{p->mission_stage=4;p->front_retreat_arrivals=p->support_retreat_arrivals=3;stop_both(2);event(65);}}
  }}
}
static bool no_override(){Support& s=p->support;return !p->native_move&&!p->native_attack&&!p->native_add&&!p->native_remove&&!p->native_stop&&!s.native_move&&!s.native_attack&&!s.native_add&&!s.native_remove&&!s.native_stop;}
static bool mobile(uint32_t t,uint32_t u){return !(word(t+0x84)&0x20080000)&&!word(t+0x238)&&word(u)==0xc48670&&word(u+0x24)==0xc48528&&word(u+8)==t;}
static bool absent_id(uint32_t id,uint32_t* count){
 uint32_t now=frame(),first=word(p->logic+0xb4),t=first;*count=0;
 while(t){if(t%4||*count>=20000||word(t)!=0xc4db60||!word(t+0xdc)||word(t+0xdc)==id)return false;uint32_t next=word(t+0x7c);if(next==t)return false;t=next;(*count)++;}
 return *count>0&&identity()&&frame()==now&&word(p->logic+0xb4)==first;
}
static void fatal_cleanup(uint32_t now){
 event(3);event(3,0,0,0,0,0,1);
 if(unit()&&p->detach_calls&&!p->return_calls){if(!p->cleanup_front_stopped){issue_stop(2);p->cleanup_front_stopped=1;}bool settled=stop_settled(now);if(settled||now-p->cleanup_started>=60){event(settled?68:69);tag=3;p->return_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->unit,1);p->return_verified=unit()&&word(p->unit+0x414)==p->default_team;event(5);tag=0;}}
 if(support_valid()&&p->support.detach_calls&&!p->support.return_calls){if(!p->cleanup_support_stopped){stop_support();p->cleanup_support_stopped=1;}bool settled=support_settled(now);if(settled||now-p->cleanup_started>=60){event(settled?68:69,0,0,0,0,0,1);tag=3;p->support.return_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->support.thing,1);p->support.returned=support_valid()&&word(p->support.thing+0x414)==p->default_team;event(5,0,0,0,0,0,1);tag=0;}}
 uint32_t count=0;
 if(!unit()&&!p->return_verified&&now!=p->front_last_absence_frame&&absent_id(p->object_id,&count)){p->front_last_absence_frame=now;p->front_absence_samples++;event(70,count);if(p->front_absence_samples>=2)p->front_disposed_verified=1;}
 if(!support_valid()&&!p->support.returned&&now!=p->support.last_absence_frame&&absent_id(p->support.id,&count)){p->support.last_absence_frame=now;p->support.absence_samples++;event(70,count,0,0,0,0,1);if(p->support.absence_samples>=2)p->support.disposed_verified=1;}
 if((!p->detach_calls||p->return_verified||p->front_disposed_verified)&&(!p->support.detach_calls||p->support.returned||p->support.disposed_verified)){p->returned_frame=now;finish();}
 else if(now-p->cleanup_started>=90){p->error=52;finish();}
}
// Acquisition and route publication are separate bounded phases. No Move is
// reachable while route_ready==0; every accepted route is privately frozen.
static bool positive_native_surface(uint32_t thing){
 float height=0,hp=0;uint32_t flags=word(thing+0x80);
 return !(flags&0x181)&&!(word(thing+0x94)&2)&&!(word(thing+0x98)&0x88000)&&!(word(thing+0x84)&0x20080000)&&!word(thing+0x238)&&(word(thing+0x48)&4)&&read(thing+0x5c,&height,4)&&isfinite(height)&&fabsf(height)<=.5f&&read(word(thing+0x33c)+4,&hp,4)&&isfinite(hp)&&hp>=50;
}
static bool admissible_actor(uint32_t thing,uint32_t update){
 uint32_t sm=word(update+0x3c),state=word(sm+4),id=word(state+4);
 return mobile(thing,update)&&positive_native_surface(thing)&&sm&&state&&word(sm+0x24)==thing&&word(state+0x18)==sm&&!(word(sm+0x78)&0xffff)&&word(update+0x50)<=3&&(id==1||(id==10&&word(state)==0xc548c0)||(id==16&&!word(update+0x150)));
}
static bool planning_idle(uint32_t thing,uint32_t update){
 uint32_t sm=word(update+0x3c);
 return mobile(thing,update)&&word(word(sm+4)+4)==16&&word(update+0x50)==1&&!word(update+0x150)&&!(word(sm+0x78)&0xffff);
}
static float clearance(const float a[3],const float b[3],const float point[3]){
 float x=b[0]-a[0],y=b[1]-a[1],d=x*x+y*y,t=d?((point[0]-a[0])*x+(point[1]-a[1])*y)/d:0;
 if(t<0)t=0;
 if(t>1)t=1;
 float dx=a[0]+t*x-point[0],dy=a[1]+t*y-point[1];return sqrtf(dx*dx+dy*dy);
}
static bool planned_geometry(const float route[16][3],uint32_t count,const float front[3],const float support[3]){
 if(count<2||count>16||distance(front,support)<25||distance(front,support)>180)return false;
 float prior_front[17][3],prior_support[17][3];memcpy(prior_front[0],front,12);memcpy(prior_support[0],support,12);
 for(unsigned i=0;i<count;i++){
  const float* f=prior_front[i];const float* s=prior_support[i];const float* goal=route[i];float length=distance(f,goal);
  float dot=(goal[0]-f[0])*(f[0]-s[0])+(goal[1]-f[1])*(f[1]-s[1]);
  if(!finite_point(goal)||length<(i?40:60)||length>(i?160:140)||fabsf(goal[2]-f[2])>100||dot<0||distance(f,s)<25)return false;
  memcpy(prior_front[i+1],goal,12);memcpy(prior_support[i+1],f,12);
 }
 for(unsigned i=count;i>0;i--)if(clearance(prior_support[i],prior_support[i-1],prior_front[i])<25||clearance(prior_front[i],prior_front[i-1],prior_support[i-1])<25)return false;
 return true;
}
static void planning_failure(uint32_t reason,uint32_t now){
 p->planning_failed=reason;request_cleanup(55,now);event(75,reason);event(75,reason,0,0,0,0,1);
}
static void planning_tick(uint32_t now){
 float fh=0,sh=0;read(word(p->unit+0x33c)+4,&fh,4);read(word(p->support.thing+0x33c)+4,&sh,4);if(fh<=25||sh<=25){planning_failure(10,now);return;}
 if(p->retreat_requested||p->return_pending){planning_failure(4,now);return;}
 if(!visible_target()||!p->planning_threat_clear||now<p->planning_threat_frame||now-p->planning_threat_frame>45){planning_failure(3,now);return;}
 bool fresh_front=now!=p->last_sample_frame,fresh_support=now!=p->support.last_sample_frame;
 bool a=stop_settled(now),b=support_settled(now),idle=planning_idle(p->unit,p->update)&&planning_idle(p->support.thing,p->support.update);
 if(p->mission_stage==8){
  if(a&&b&&idle){
   read(p->unit+0x38,p->safe_front,12);read(p->support.thing+0x38,p->safe_support,12);memcpy(p->planning_front,p->safe_front,12);memcpy(p->planning_support,p->safe_support,12);
   p->planning_ready_frame=now;p->planning_ready_tick=GetTickCount();p->mission_stage=9;MemoryBarrier();InterlockedExchange((LONG*)&p->planning_ready,1);event(72);event(72,0,0,0,0,0,1);
  }else if(now-p->nav_frame>60)planning_failure(5,now);
  return;
 }
 if(GetTickCount()-p->planning_ready_tick>6000||p->planning_timeout_ms!=6000){planning_failure(2,now);return;}
 if(p->planning_failed){planning_failure(p->planning_failed,now);return;}
 float current_front[3],current_support[3];read(p->unit+0x38,current_front,12);read(p->support.thing+0x38,current_support,12);
 if(!idle||distance(current_front,p->planning_front)>1||distance(current_support,p->planning_support)>1){planning_failure(6,now);return;}
 LONG ready=InterlockedCompareExchange((LONG*)&p->route_ready,0,0);
 if(!ready)return;
 if(!a||!b){if(((!a&&!fresh_front)||(!b&&!fresh_support))&&p->stable_samples>=3&&p->support.stable_samples>=3)return;planning_failure(7,now);return;}
 if(ready!=1||p->route_generation!=2||p->route_committed_generation||!positive_native_surface(p->unit)||!positive_native_surface(p->support.thing)){planning_failure(7,now);return;}
 uint32_t count=p->route_count;float route[16][3];memcpy(route,p->route,sizeof(route));MemoryBarrier();
 if(count!=p->route_count||p->route_generation!=2||count<2||count>16||memcmp(route,p->route,sizeof(route))||distance(current_front,p->submitted_front)>1||distance(current_support,p->submitted_support)>1||!planned_geometry(route,count,current_front,current_support)){planning_failure(8,now);return;}
 float current_target[3];read(p->target_unit+0x38,current_target,12);
 if(distance(route[count-1],current_target)>300||now<p->target_observed_frame||now-p->target_observed_frame>30||p->mission_deadline_frame<=now+120){planning_failure(9,now);return;}
 memcpy(frozen_route,route,sizeof(route));frozen_route_count=count;p->route_committed_generation=2;p->route_commit_frame=now;
 event(73,count);event(73,count,0,0,0,0,1);for(unsigned i=0;i<count;i++)event(74,i);
 approach_leg(0);
}

static void CALLBACK tick(HWND,UINT,UINT_PTR,DWORD){
 if(GetCurrentThreadId()!=p->thread){p->error=30;return;}
 if(p->phase==2){if(!identity()||!unit()||!support_valid()||frame()-p->returned_frame>=p->post_frames){finish();}return;}
 if(!identity()){p->error=31;finish();return;}
 if(p->phase==7){if(paused()){p->paused_samples++;return;}fatal_cleanup(frame());return;}
 if(p->phase==5&&(!unit()||!support_valid())){p->error=34;finish();return;}
 if(!unit()||!support_valid()){p->error=32;p->lifecycle_fail++;p->phase=7;p->cleanup_started=frame();fatal_cleanup(frame());return;}
 if(paused()){p->paused_samples++;if(GetTickCount()-start_tick>330000)p->return_pending=1;return;}
 uint32_t now=frame();
 if(p->phase==5){
  if(p->stop_requested||GetTickCount()-start_tick>60000||p->route_ready||p->route_count||p->planning_timeout_ms!=6000||frozen_deadline<=now+120||frozen_deadline-now>4500||now<p->target_observed_frame||now-p->target_observed_frame>60||!admissible_actor(p->unit,p->update)||!admissible_actor(p->support.thing,p->support.update)||!button_identity()||!visible_target()||!p->planning_threat_clear||now<p->planning_threat_frame||now-p->planning_threat_frame>60||p->support.id==p->object_id||p->support.hash!=0x2c358c61||word(p->owner+0xac)!=p->default_team||word(word(p->owner+0x8c)+0x10)!=p->script_team){p->error=34;finish();return;}
  read(p->unit+0x38,p->safe_front,12);read(p->support.thing+0x38,p->safe_support,12);float gap=distance(p->safe_front,p->safe_support);if(gap<25||gap>180){p->error=34;finish();return;}
  p->native_move=p->native_attack=p->native_add=p->native_remove=p->native_stop=0;p->support.native_move=p->support.native_attack=p->support.native_add=p->support.native_remove=p->support.native_stop=0;p->issued_frame=now;event(71);event(71,0,0,0,0,0,1);p->phase=1;p->original_team=word(p->unit+0x414);p->support.original_team=word(p->support.thing+0x414);
  tag=1;p->detach_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->unit,0);event(1);p->support.detach_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->support.thing,0);event(1,0,0,0,0,0,1);tag=0;
  if(word(p->unit+0x414)!=p->script_team||word(p->support.thing+0x414)!=p->script_team){request_cleanup(35,now);return;}p->mission_stage=8;p->nav_frame=now;stop_both(5);event(76);event(76,0,0,0,0,0,1);return;
 }
 event(3);event(3,0,0,0,0,0,1);
 if(p->phase!=1)return;
 if(p->mission_deadline_frame!=frozen_deadline||p->lease_frames!=frozen_lease_frames){request_cleanup(48,now);return;}
 if(!no_override()||!mobile(p->unit,p->update)||!mobile(p->support.thing,p->support.update)){request_cleanup(38,now);return;}
 if(now+p->post_frames+5>=frozen_deadline||now-p->issued_frame>=frozen_lease_frames||GetTickCount()-start_tick>320000){request_cleanup(48,now);return;}
 if((p->stop_requested||GetTickCount()-p->heartbeat_tick>5000)&&p->mission_stage!=5){p->error=p->stop_requested?49:50;p->retreat_reason=4;p->mission_stage=5;stop_both(2);}
 if(p->mission_stage==5){bool a=stop_settled(now),b=support_settled(now);if(a&&b){event(67);event(67,0,0,0,0,0,1);normal_return();}else if(now-p->stop_issue_frame>60){request_cleanup(45,now);}return;}
 if(p->mission_stage==8||p->mission_stage==9){planning_tick(now);return;}
 float front_hp=0,support_hp=0;read(word(p->unit+0x33c)+4,&front_hp,4);read(word(p->support.thing+0x33c)+4,&support_hp,4);
 if((p->retreat_requested||p->return_pending||front_hp<=25||support_hp<=25)&&p->mission_stage<3)begin_retreat(p->retreat_requested?4:3);
 if(p->mission_stage==1||p->mission_stage==3){if(now-p->nav_frame>300){if(p->mission_stage==1)begin_retreat(8);else{request_cleanup(53,now);}return;}advance_nav(now);return;}
 if(p->mission_stage==4){bool a=stop_settled(now),b=support_settled(now);if(a&&b){event(66);event(66,0,0,0,0,0,1);normal_return();}else if(now-p->stop_issue_frame>60){request_cleanup(45,now);}return;}
 if(p->mission_stage!=2)return;
 float f[3],s[3];read(p->unit+0x38,f,12);read(p->support.thing+0x38,s,12);float spacing=distance(f,s);
 if(spacing>=25&&spacing<=350&&distance(s,p->support_goal)<=15)p->combat_geometry_samples++;
 else if(p->lease_stage==1){begin_retreat(6);return;}
 if(!visible_target()){begin_retreat(2);return;}
 if(now-p->combat_started>=p->combat_frames){begin_retreat(5);return;}
 if(p->lease_stage==0){bool a=stop_settled(now),b=support_settled(now);if(a&&b){event(37);uint32_t e=0,ammo=0;uint32_t asset=current_weapon(&e,&ammo);if(asset==0x447ea26e){p->prepare_gate_frame=now;event(42);issue_stop(4);}else if(asset==0x41872ecc&&word(p->unit+0x26c)==0){p->lease_stage=3;tag=5;p->toggle_calls++;p->toggle_frame=now;((Button)0x790990)((void*)(uintptr_t)p->unit,(void*)(uintptr_t)p->button,1,0);event(39);tag=0;}else begin_retreat(7);}else if(now-p->stop_issue_frame>60){request_cleanup(44,now);}return;}
 if(p->lease_stage==3){if(now!=p->last_ak_frame){p->last_ak_frame=now;p->observed_weapon_asset=current_weapon(&p->observed_weapon_entry,&p->observed_ammo);uint32_t sm=word(p->update+0x3c);bool idle=word(word(sm+4)+4)==16&&!(word(sm+0x78)&0xffff)&&!word(p->update+0x150)&&!word(p->unit+0x238)&&word(p->update+0x50)==1;p->ak_samples=p->observed_weapon_asset==0x447ea26e&&now-p->toggle_frame>=15&&idle?p->ak_samples+1:0;if(p->ak_samples>=3){p->prepare_gate_frame=now;event(42);issue_stop(4);}else if(now-p->toggle_frame>60)begin_retreat(7);}return;}
 if(p->lease_stage==4){if(stop_settled(now)){event(43);uint32_t e=0,ammo=0;if(current_weapon(&e,&ammo)!=0x447ea26e||!ammo||ammo>3){begin_retreat(7);return;}p->lease_stage=1;tag=2;p->attack_calls++;p->attack_facade_calls++;((Attack)0x572280)((void*)(uintptr_t)(p->update+0x24),(void*)(uintptr_t)p->target_unit,0x7fffffff,1);event(2);tag=0;}else if(now-p->stop_issue_frame>60){request_cleanup(44,now);}return;}
 if(p->lease_stage==1){sample_weapon();if(p->damage_count&&p->commit_own_calls)begin_retreat(1);}
}
