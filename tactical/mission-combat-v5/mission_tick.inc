// Mission stages: 1 initial Stop,2 approach,3 prepare Stop,4 toggle,5 ready Stop,
// 6 engage,7 retreat Stop,8 retreat movement,9 final Stop,10 native restored.
// Reasons:0 active,1 source damage,2 FOV lost,3 approach stalled,4 approach limit,
// 5 low HP,6 engagement limit,7 retreat failed,8 deadline,9 cancelled,10 override,
// 11 prepare failed,12 host heartbeat lost,13 target invalid,14 initial binding.
static bool finite3(const float* v){return isfinite(v[0])&&isfinite(v[1])&&isfinite(v[2]);}
static float distance(const float* a,const float* b){float x=a[0]-b[0],y=a[1]-b[1];return sqrtf(x*x+y*y);}
static void mission_stage(uint32_t stage){p->mission_stage=stage;p->stage_frame=frame();p->stage_revision++;event(50,stage);}
static bool retreat_anchor(){
 if(!finite3(p->retreat_goal)||p->retreat_observed_frame>frame()||frame()-p->retreat_observed_frame>4500)return false;
 if(p->retreat_source==2)return p->checkpoint_count&&distance(p->retreat_goal,p->checkpoint[0])<=15&&fabsf(p->retreat_goal[2]-p->checkpoint[0][2])<=15;
 if(p->retreat_source!=1||p->retreat_anchor_hash!=0xc16ff13f||word(p->retreat_anchor)!=0xc4db60||word(p->retreat_anchor+0xdc)!=p->retreat_anchor_id||word(p->retreat_anchor+0x418)!=p->owner||word(word(p->retreat_anchor+4)+8)!=p->retreat_anchor_hash)return false;
 float xyz[3],hp=0;return read(p->retreat_anchor+0x38,xyz,12)&&finite3(xyz)&&read(word(p->retreat_anchor+0x33c)+4,&hp,4)&&isfinite(hp)&&hp>0&&distance(xyz,p->retreat_goal)<=300&&distance(xyz,p->retreat_goal)>=80&&fabsf(xyz[2]-p->retreat_goal[2])<=300;
}
static void waypoint_to(const float* destination,bool retreat){
 float xyz[3];read(p->unit+0x38,xyz,12);
// Use the actual visible target / actual historical checkpoint. Normal game
// pathfinding owns detours. No unvisited linear midpoint is asserted reachable.
memcpy(p->waypoint,destination,12);memcpy(p->move_progress_xyz,xyz,12);
 p->lease_stage=retreat?8:5;p->move_started=p->move_last_progress_frame=frame();p->move_best_distance=distance(xyz,p->waypoint);p->waypoint_samples=p->arrival_last_frame=0;p->move_index++;
 tag=6;p->move_calls++;p->normal_move_facade_calls++;if(retreat)p->retreat_move_calls++;else p->approach_move_calls++;
 ((NormalMoveFacade)0x571d90)((void*)(uintptr_t)(p->update+0x24),p->waypoint,1);event(56,retreat?1:0);tag=0;
}
static bool waypoint_arrived(uint32_t now,const float* xyz){
 if(now==p->arrival_last_frame)return false;p->arrival_last_frame=now;float d=distance(xyz,p->waypoint);
 if(distance(xyz,p->move_progress_xyz)>=10){p->move_best_distance=d;p->move_last_progress_frame=now;memcpy(p->move_progress_xyz,xyz,12);}
 if(d<=15)p->waypoint_samples++;else p->waypoint_samples=0;
 if(p->waypoint_samples>=3){event(57);return true;}return false;
}
static void begin_retreat(uint32_t reason){if(!p->reason_code)p->reason_code=reason;p->retreat_started=frame();p->retreat_arrival_samples=p->retreat_last_frame=p->retreat_replans=p->retreat_mode=0;p->retreat_index=p->checkpoint_count;mission_stage(7);issue_stop(7);}
static void final_stop(uint32_t reason){if(reason)p->reason_code=reason;mission_stage(9);issue_stop(2);}
static void CALLBACK tick(HWND,UINT,UINT_PTR,DWORD){
 if(GetCurrentThreadId()!=p->thread){p->error=30;finish();return;}
 if(!identity()&&p->phase==2&&p->return_verified){p->post_scene_changed=1;finish();return;}
 if(!identity()){p->error=31;p->lifecycle_fail++;finish();return;}
 if(!unit()&&p->phase==2&&p->return_verified){p->post_actor_disposed=1;finish();return;}
 if(!unit()){p->error=32;p->lifecycle_fail++;finish();return;}
 if(paused()){p->paused_samples++;if(p->phase==1&&(p->stop_requested||GetTickCount()-p->heartbeat_tick>5000))p->return_pending=1;return;}
 uint32_t now=frame();float xyz[3];read(p->unit+0x38,xyz,12);read(word(p->unit+0x33c)+4,&p->own_hp,4);
 if(!finite3(xyz)||!isfinite(p->own_hp)){p->error=48;finish();return;}
 if(p->phase==5){
  if(p->stop_requested||GetTickCount()-start_tick>60000){p->error=33;finish();return;}
  p->checkpoint_count=1;memcpy(p->checkpoint[0],xyz,12);
  if(p->mission_deadline_frame<=now+300||p->mission_deadline_frame-now>4500||p->approach_limit>2100||p->approach_limit<30||p->engage_limit>300||p->engage_limit<30||p->retreat_limit>1800||p->retreat_limit<60||!retreat_anchor()||p->retreat_observed_frame>now||now-p->retreat_observed_frame>60){p->error=49;finish();return;}
  if((word(p->unit+0x84)&0x20080000)||!button_identity()||word(p->unit+0x238)||word(p->update)!=0xc48670||word(p->update+0x24)!=0xc48528||word(0xc48528)!=0x787500||word(0xc48670+0x58)!=0x76d9d0||word(0xc48670+0x8c)!=0x721ad0||!visible_target()||now<p->target_observed_frame||now-p->target_observed_frame>60||word(p->owner+0xac)!=p->default_team||word(word(p->owner+0x8c)+0x10)!=p->script_team||word(word(p->default_team+4)+8)!=p->owner||word(word(p->script_team+4)+8)!=p->owner){p->error=34;finish();return;}
  p->current_visible=1;read(p->target_unit+0x38,p->target,12);if(!finite3(p->target)){p->error=34;finish();return;}p->target_last_seen_frame=now;event(64);
  uint32_t ammo=0;p->initial_weapon_asset=current_weapon(&p->initial_weapon_entry,&ammo);if(p->initial_weapon_asset!=0x447ea26e&&p->initial_weapon_asset!=0x41872ecc){p->error=46;finish();return;}
  p->initial_hp=p->own_hp;p->phase=6;p->original_team=word(p->unit+0x414);p->issued_frame=now;tag=1;p->detach_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->unit,0);event(1);tag=0;
  p->phase=1;if(!unit()||word(p->unit+0x414)!=p->script_team){p->error=35;final_stop(14);return;}
  mission_stage(1);issue_stop(0);return;
 }
 if(p->phase==2){if(now-p->returned_frame>=p->post_frames)finish();return;}
 if(p->phase!=1)return;
 p->current_visible=0;if(p->mission_stage<=6&&visible_target()){p->current_visible=1;read(p->target_unit+0x38,p->target,12);p->target_last_seen_frame=now;p->memory_wait_started=0;p->approach_distance=distance(xyz,p->target);}
 event(3);
 if(p->retreat_requested&&p->mission_stage<7){begin_retreat(9);return;}
 bool emergency=p->stop_requested||p->return_pending||GetTickCount()-p->heartbeat_tick>5000;
 if(emergency&&p->mission_stage!=9){final_stop(p->stop_requested?9:12);return;}
 if(now+35>=p->mission_deadline_frame&&p->mission_stage!=9){final_stop(8);return;}
 if((p->native_move||p->native_attack||p->native_add||p->native_remove)&&p->mission_stage<7){begin_retreat(10);return;}
 if(p->mission_stage<7&&p->own_hp<=p->initial_hp*p->retreat_hp_fraction){begin_retreat(5);return;}
 if(p->mission_stage<7&&now+p->retreat_limit+90>=p->mission_deadline_frame){begin_retreat(8);return;}
 if(p->mission_stage==1){
  if(stop_settled(now)){event(37);p->approach_started=now;mission_stage(2);}
  else if(now-p->stop_issue_frame>=30){p->stop_failed=1;begin_retreat(11);}return;
 }
 if(p->mission_stage==2){
  if(now-p->approach_started>=p->approach_limit){begin_retreat(4);return;}
  // Memory is navigation only: never refresh hidden XYZ/HP or issue Attack.
  if(!p->target_last_seen_frame||now<p->target_last_seen_frame||now-p->target_last_seen_frame>900){event(65,1);begin_retreat(2);return;}
  float remaining=distance(xyz,p->target);
  if(p->current_visible&&remaining<=125){mission_stage(3);issue_stop(6);return;}
  if(!p->current_visible&&remaining<=125){
   if(!p->memory_wait_started)p->memory_wait_started=now;
   if(now-p->memory_wait_started>=45){event(65,2);begin_retreat(2);return;}
   return;
  }
  if(p->approach_move_calls>=12){begin_retreat(4);return;}
  if(distance(xyz,p->checkpoint[p->checkpoint_count-1])>=120){
   if(p->checkpoint_count>=32){begin_retreat(4);return;}
   memcpy(p->checkpoint[p->checkpoint_count++],xyz,12);event(61,p->checkpoint_count-1);
  }
  if(!p->approach_move_calls){waypoint_to(p->target,false);return;}
  if(waypoint_arrived(now,xyz)){
   if(p->current_visible)waypoint_to(p->target,false);return;
  }
  if(now-p->move_last_progress_frame>=250){begin_retreat(3);return;}return;
 }
 if(p->mission_stage==3){
  if(!visible_target()){begin_retreat(2);return;}
  if(stop_settled(now)){event(58);uint32_t entry=0,ammo=0,asset=current_weapon(&entry,&ammo);
   if(asset==0x447ea26e){p->prepare_gate_frame=now;event(42);mission_stage(5);issue_stop(4);}
   else if(asset==0x41872ecc&&button_identity()&&!word(p->unit+0x26c)){mission_stage(4);p->lease_stage=3;tag=5;p->toggle_calls++;p->toggle_frame=now;((Button)0x790990)((void*)(uintptr_t)p->unit,(void*)(uintptr_t)p->button,1,0);event(39);tag=0;}
   else begin_retreat(11);
  }else if(now-p->stop_issue_frame>=30){p->stop_failed=1;begin_retreat(11);}return;
 }
 if(p->mission_stage==4){
  if(!visible_target()){begin_retreat(2);return;}
  if(now!=p->last_ak_frame){p->last_ak_frame=now;p->observed_weapon_asset=current_weapon(&p->observed_weapon_entry,&p->observed_ammo);uint32_t sm=word(p->update+0x3c);bool idle=word(word(sm+4)+4)==16&&!(word(sm+0x78)&0xffff)&&!word(p->update+0x150)&&!word(p->unit+0x238)&&word(p->update+0x50)==1;
   if(p->observed_weapon_asset==0x447ea26e&&now-p->toggle_frame>=15&&idle)p->ak_samples++;else p->ak_samples=0;
   if(p->ak_samples>=3){p->prepare_gate_frame=now;event(42);mission_stage(5);issue_stop(4);}else if(now-p->toggle_frame>=60)begin_retreat(11);
  }return;
 }
 if(p->mission_stage==5){
  if(!visible_target()){begin_retreat(2);return;}
  if(stop_settled(now)){event(43);uint32_t e=0,a=0;if(current_weapon(&e,&a)!=0x447ea26e||!a||a>3||word(p->unit+0x238)){begin_retreat(11);return;}
   mission_stage(6);p->lease_stage=1;p->engage_started=now;tag=2;p->attack_calls++;p->attack_facade_calls++;((Attack)0x572280)((void*)(uintptr_t)(p->update+0x24),(void*)(uintptr_t)p->target_unit,0x7fffffff,1);event(2);tag=0;
  }else if(now-p->stop_issue_frame>=30){p->stop_failed=1;begin_retreat(11);}return;
 }
 if(p->mission_stage==6){
  sample_weapon();if(p->damage_count||p->commit_own_calls){begin_retreat(1);return;}
  if(!visible_target()){begin_retreat(2);return;}
  uint32_t e=0,a=0;if(current_weapon(&e,&a)!=0x447ea26e){begin_retreat(11);return;}
  if(now-p->engage_started>=p->engage_limit){begin_retreat(6);return;}return;
 }
 if(p->mission_stage==7){
  if(stop_settled(now)){event(59);if(!retreat_anchor()){final_stop(7);return;}mission_stage(8);p->retreat_index=0;waypoint_to(p->retreat_goal,true);}
  else if(now-p->stop_issue_frame>=30){p->stop_failed=1;final_stop(7);}return;
 }
 if(p->mission_stage==8){
  if(!retreat_anchor()||now-p->retreat_started>=p->retreat_limit){final_stop(7);return;}
  if(now!=p->retreat_last_frame){
   p->retreat_last_frame=now;
   if(distance(xyz,p->retreat_goal)<=15&&fabsf(xyz[2]-p->retreat_goal[2])<=10)p->retreat_arrival_samples++;else p->retreat_arrival_samples=0;
  }
  if(p->retreat_arrival_samples>=3){event(60);final_stop(0);return;}
  bool arrived=waypoint_arrived(now,xyz);
  if(p->retreat_mode==1){
   float moved=distance(xyz,p->retreat_attempt_xyz),gain=p->retreat_attempt_home_distance-distance(xyz,p->retreat_goal);
   if(moved>=120||gain>=80||arrived){
    if(p->retreat_replans>=2||p->retreat_move_calls>=3){final_stop(7);return;}
    p->retreat_replans++;p->retreat_mode=0;event(63,arrived?2:1);waypoint_to(p->retreat_goal,true);return;
   }
  }
  if(now-p->move_last_progress_frame>=250){
   uint32_t sm=word(p->update+0x3c),selected=0xffffffffu;float best=1e30f,home=distance(xyz,p->retreat_goal);
   if(p->retreat_mode==0&&p->retreat_replans==0&&word(word(sm+4)+4)==16&&!word(p->update+0x150)){
    for(uint32_t i=0;i<p->checkpoint_count;i++){
     float d=distance(xyz,p->checkpoint[i]),to_home=distance(p->checkpoint[i],p->retreat_goal);
     if(d>=80&&to_home<=home-80&&to_home>15&&d<best){best=d;selected=i;}
    }
   }
   if(selected!=0xffffffffu){
    p->retreat_replans++;p->retreat_mode=1;p->fallback_checkpoint_index=selected;memcpy(p->retreat_attempt_xyz,xyz,12);p->retreat_attempt_home_distance=home;event(62,selected);waypoint_to(p->checkpoint[selected],true);return;
   }
   final_stop(7);return;
  }return;
 }
 if(p->mission_stage==9&&(stop_settled(now)||now-p->stop_issue_frame>=30)){
  if(p->stable_samples<3){p->stop_failed=1;p->error=45;}else event(38);
  if(p->native_add){p->error=36;finish();return;}
  tag=3;p->return_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->unit,1);event(5);tag=0;p->returned_frame=now;p->return_pending=0;p->return_verified=unit()&&word(p->unit+0x414)==p->default_team;p->phase=2;
  if(!p->return_verified){p->error=37;finish();return;}mission_stage(10);
 }
}

