// Actual ground-positive breadcrumbs and bounded leader/follower motion.
static uint32_t last_progress[2],last_pose_frame[2],last_arrival_frame[2],role_arrivals[2],completed_crumb[2],repair_resume_state;
static float progress_xyz[2][3],retreat_start_xyz[2][3];
static uint32_t regroup_phase,phase_regroups;
static bool memory_hidden;static float frozen_hold[3];static float memory_target[3];static uint32_t memory_seen_frame;
static uint32_t role_thing(uint32_t r){return r?p->support.thing:p->unit;}
static uint32_t role_update(uint32_t r){return r?p->support.update:p->update;}
static uint32_t role_id(uint32_t r){return r?p->support.id:p->object_id;}
static uint32_t role_hash(uint32_t r){return r?0x2c358c61u:0x19ab11afu;}
static float* role_goal(uint32_t r){return frozen_goals[r];}
static const float* role_origin(uint32_t r){return frozen_origins[r];}
static bool role_pos(uint32_t r,float xyz[3]){return read(role_thing(r)+0x38,xyz,12)&&finite_point(xyz);}
static void stop_role(uint32_t r){if(r)stop_support();else issue_stop(5);p->role_motion_mode[r]=3;}
static bool settled_role(uint32_t r,uint32_t now){return r?support_settled(now):stop_settled(now);}
static bool idle_role(uint32_t r){return planning_idle(role_thing(r),role_update(r));}
static void begin_retreat(uint32_t reason);
static float segment_distance(const float a[3],const float b[3],const float x[3]);
static bool raw_surface(uint32_t role,Breadcrumb& out,uint32_t now){
 uint32_t t=role_thing(role),u=role_update(role);Breadcrumb before={},after={};
 auto sample=[&](Breadcrumb& c){c.role=role;c.frame=frame();c.thing=t;c.object_id=word(t+0xdc);c.type_hash=word(word(t+4)+8);c.owner=word(t+0x418);c.update=word(t+0x374);c.holder=word(t+0x238);read(t+0x80,c.status_words,28);c.height_flags=word(t+0x48);return read(t+0x5c,&c.height,4)&&read(word(t+0x33c)+4,&c.hp,4)&&read(t+0x38,c.xyz,12);};
 if(!sample(before)||!sample(after)||memcmp(&before,&after,sizeof(before))||before.frame!=now||frame()!=now||word(t)!=0xc4db60||before.object_id!=role_id(role)||before.owner!=p->owner||before.type_hash!=role_hash(role)||before.update!=u||word(u+8)!=t||word(u)!=0xc48670||word(u+0x24)!=0xc48528)return false;
 if(before.holder||before.status_words[0]&0x181||before.status_words[1]&0x20080000||before.status_words[5]&2||before.status_words[6]&0x88000||!(before.height_flags&4)||!isfinite(before.height)||fabsf(before.height)>.5f||!isfinite(before.hp)||before.hp<=0||!finite_point(before.xyz))return false;
 out=before;out.mission_stage=p->mission_stage;out.surface_verified=1;return true;
}
static bool runtime_ground(uint32_t r){uint32_t t=role_thing(r);return mobile(t,role_update(r))&&!(word(t+0x80)&0x181)&&!(word(t+0x94)&2)&&!(word(t+0x98)&0x88000);}
static bool sample_owned_motion(uint32_t r,uint32_t now){
 float xyz[3];if(!role_pos(r,xyz)||frame()!=now){request_cleanup(57,now);return false;}
 float step=distance(xyz,p->role_last_xyz[r]);uint32_t elapsed=now-last_pose_frame[r];
 if(last_pose_frame[r]&&step>20.f+6.f*(float)elapsed){request_cleanup(57,now);return false;}
 if(last_pose_frame[r]){p->role_crumb_distance[r]+=step;if(p->mission_stage==1){if(r)p->support_travel+=step;else p->front_travel+=step;}}
 memcpy(p->role_last_xyz[r],xyz,12);last_pose_frame[r]=now;
 if(distance(xyz,progress_xyz[r])>=3){last_progress[r]=now;memcpy(progress_xyz[r],xyz,12);}return true;
}
static void sample_trail(uint32_t r,uint32_t now,bool force=false){
 Breadcrumb c;if(!raw_surface(r,c,now)){p->crumb_reject_count++;return;}
 uint32_t count=frozen_crumb_counts[r];if(count&&!force&&frozen_crumbs[r][count-1].mission_stage==p->mission_stage&&distance(c.xyz,frozen_crumbs[r][count-1].xyz)<80)return;
 if(count>=CRUMB_CAP){request_cleanup(58,now);return;}
 c.index=count;c.path_distance=p->role_crumb_distance[r];frozen_crumbs[r][count]=c;frozen_crumb_counts[r]++;p->crumb_count[r]=frozen_crumb_counts[r];p->crumbs[r][count]=c;event(80,count,0,0,0,0,r);
}
static bool physical_arrival(uint32_t r,const float goal[3],uint32_t now){
 if(last_arrival_frame[r]==now)return false;last_arrival_frame[r]=now;float x[3];bool okay=role_pos(r,x)&&distance(x,goal)<=15&&fabsf(x[2]-goal[2])<=10;role_arrivals[r]=okay?role_arrivals[r]+1:0;return role_arrivals[r]>=3;
}
static void start_move(uint32_t r,const float goal[3],uint32_t kind,uint32_t now){
 memcpy(role_goal(r),goal,12);memcpy(r?p->support_goal:p->front_goal,goal,12);role_arrivals[r]=last_arrival_frame[r]=0;last_progress[r]=now;role_pos(r,progress_xyz[r]);p->role_motion_mode[r]=1;
 if(r==p->leader_role){if(++p->leader_move_count>32){request_cleanup(59,now);return;}p->lead_move_started=now;}
 event(kind,0,0,0,0,0,r,goal);move_role(r!=0,goal);
}
static void update_memory(uint32_t now){
 bool visible=visible_target();if(visible){bool regained=memory_hidden;read(p->target_unit+0x38,memory_target,12);memory_seen_frame=now;memcpy(p->last_seen_target,memory_target,12);p->target_last_seen_frame=now;p->memory_wait_started=0;memory_hidden=false;if(regained)event(88);float f[3];role_pos(0,f);p->approach_distance=distance(f,memory_target);}
 else if(!memory_hidden){memory_hidden=true;event(87);}
}
static void initial_motion(uint32_t now){
 bool a=stop_settled(now),b=support_settled(now);if(!(a&&b)){if(now-p->nav_frame>60)request_cleanup(44,now);return;}
 Breadcrumb ground0,ground1;if(!raw_surface(0,ground0,now)||!raw_surface(1,ground1,now)){if(now-p->nav_frame>60)request_cleanup(57,now);return;}
 event(58);event(58,0,0,0,0,0,1);if(regroup_phase!=p->mission_stage){regroup_phase=p->mission_stage;phase_regroups=0;}p->follow_active=0;p->role_motion_mode[0]=p->role_motion_mode[1]=0;p->follow_arrivals=0;completed_crumb[p->leader_role]=0xffffffffu;
 for(uint32_t r=0;r<2;r++){p->role_crumb_distance[r]=0;last_pose_frame[r]=0;role_pos(r,p->role_last_xyz[r]);last_progress[r]=now;memcpy(progress_xyz[r],p->role_last_xyz[r],12);if(!sample_owned_motion(r,now))return;sample_trail(r,now,true);}
 if(p->phase!=1)return;
 if(p->mission_stage==1)update_memory(now);
 const float* goal=p->mission_stage==3?role_origin(p->leader_role):memory_target;float leader[3],follower[3];role_pos(p->leader_role,leader);role_pos(p->follower_role,follower);
 float dot=(goal[0]-leader[0])*(leader[0]-follower[0])+(goal[1]-leader[1])*(leader[1]-follower[1]);
 if((p->mission_stage==1&&dot<0)||segment_distance(leader,goal,follower)<25){request_cleanup(34,now);return;}
 p->motion_state=1;p->motion_frame=now;start_move(p->leader_role,goal,85,now);
}
static void follower_tick(uint32_t now){
 uint32_t f=p->follower_role,l=p->leader_role;
 if(p->role_motion_mode[f]==1&&p->follow_active){
  if(physical_arrival(f,role_goal(f),now)){event(84,frozen_follow_index,0,0,0,0,f);event(90,frozen_follow_index,0,0,0,0,0);event(90,frozen_follow_index,0,0,0,0,1);completed_crumb[l]=frozen_follow_index;if(p->mission_stage==1)p->approach_completed++;else p->retreat_completed++;stop_role(f);}
  else if(now-last_progress[f]>250){if(p->mission_stage==1)begin_retreat(8);else request_cleanup(53,now);}return;
 }
 if(p->role_motion_mode[f]==3){if(settled_role(f,now)){event(94,frozen_follow_index,0,0,0,0,f);p->role_motion_mode[f]=0;p->follow_active=0;}else if(now-(f?p->support.private_stop_frame:p->private_stop_frame)>60)request_cleanup(44,now);return;}
 if(p->role_motion_mode[f]!=0)return;
 for(uint32_t i=0;i<frozen_crumb_counts[l];i++){
  Breadcrumb& c=frozen_crumbs[l][i];if(c.mission_stage!=p->mission_stage||!c.published_seq||(completed_crumb[l]!=0xffffffffu&&i<=completed_crumb[l]))continue;
  bool first=true;for(uint32_t j=0;j<i;j++)if(frozen_crumbs[l][j].mission_stage==p->mission_stage)first=false;
  float leader_xyz[3];if(!role_pos(l,leader_xyz)||distance(leader_xyz,c.xyz)<25)continue;
  if(first?p->role_crumb_distance[l]<25:c.path_distance+100>p->role_crumb_distance[l])continue;
  if(++p->follow_move_count>128){request_cleanup(59,now);return;}frozen_follow_role=l;frozen_follow_index=i;p->follow_crumb_role=l;p->follow_crumb_index=i;p->follow_active=1;p->follow_started=now;p->follow_last_frame=p->follow_arrivals=0;start_move(f,c.xyz,81,now);return;
 }
}
static void begin_regroup(uint32_t now,uint32_t after=3){
 if(++p->regroup_count>16||++phase_regroups>8){if(p->mission_stage==1)begin_retreat(8);else request_cleanup(53,now);return;}
 stop_role(p->leader_role);p->motion_state=2;p->motion_frame=now;p->leader_hold_started=now;p->leader_hold_settled=0;repair_resume_state=after;event(82,0,0,0,0,0,p->leader_role);
}
static bool hold_repair(uint32_t now,uint32_t return_state){
 float x[3];role_pos(p->leader_role,x);if(distance(x,frozen_hold)<=15)return false;
 if(++p->hold_repair_count>2){if(p->mission_stage==1)begin_retreat(8);else request_cleanup(53,now);return true;}
 repair_resume_state=return_state;p->motion_state=4;p->motion_frame=now;start_move(p->leader_role,frozen_hold,92,now);return true;
}
static bool reanchor_wait(uint32_t now){
 if(p->motion_state!=3||(p->mission_stage!=1&&p->mission_stage!=3))return false;
 float xyz[3];if(!role_pos(p->leader_role,xyz)){request_cleanup(57,now);return true;}
 if(distance(xyz,frozen_hold)<=15)return false;
 if(wait_reanchor_count>=2){if(p->mission_stage==1)begin_retreat(8);else request_cleanup(53,now);return true;}
 ++wait_reanchor_count;event(96,wait_reanchor_count,0,0,0,0,p->leader_role);
 stop_role(p->leader_role);p->motion_state=11;p->motion_frame=now;return true;
}
static float segment_distance(const float a[3],const float b[3],const float x[3]){float vx=b[0]-a[0],vy=b[1]-a[1],v=vx*vx+vy*vy,t=v?((x[0]-a[0])*vx+(x[1]-a[1])*vy)/v:0;t=fmaxf(0,fminf(1,t));float q[3]={a[0]+t*vx,a[1]+t*vy,0};return distance(q,x);}
static void endpoint_tick(uint32_t now){
 uint32_t l=p->leader_role,f=p->follower_role;
 if(p->motion_state==6){if(settled_role(l,now)){role_pos(l,frozen_hold);memcpy(p->leader_hold_xyz,frozen_hold,12);p->role_motion_mode[l]=4;p->motion_state=7;event(83,0,0,0,0,0,l);}else if(now-p->motion_frame>60)request_cleanup(44,now);return;}
 if(hold_repair(now,7))return;
 if(p->role_motion_mode[f]!=0||p->actual_gap>200)return;
 if(p->mission_stage==1){p->mission_stage=2;p->combat_started=now;p->motion_state=8;p->nav_frame=now;stop_both(0);event(64);event(64,0,0,0,0,0,1);return;}
 float fxyz[3],lxyz[3];role_pos(f,fxyz);role_pos(l,lxyz);
 if(segment_distance(fxyz,role_origin(f),lxyz)<25){request_cleanup(53,now);return;}
 p->motion_state=9;p->motion_frame=now;start_move(f,role_origin(f),95,now);
}
static void begin_retreat(uint32_t reason){
 if(p->mission_stage>=3)return;p->retreat_reason=reason;p->retreat_started=frame();p->mission_stage=3;p->trail_phase=3;p->leader_role=1;p->follower_role=0;p->follow_active=0;p->motion_state=0;p->nav_frame=frame();
 for(uint32_t r=0;r<2;r++){role_pos(r,retreat_start_xyz[r]);p->retreat_displacement[r]=0;p->role_motion_mode[r]=0;}
 stop_both(5);event(89,reason);event(89,reason,0,0,0,0,1);
}
static void navigation_tick(uint32_t now){
 if(p->motion_state==0){initial_motion(now);return;}
 float a[3],b[3];role_pos(0,a);role_pos(1,b);p->actual_gap=distance(a,b);
 for(uint32_t r=0;r<2;r++){if(!sample_owned_motion(r,now))return;sample_trail(r,now);if(p->mission_stage==3){float x[3];role_pos(r,x);p->retreat_displacement[r]=distance(x,retreat_start_xyz[r]);}}
 if(p->phase!=1)return;
 if(p->mission_stage==1){update_memory(now);if(now-memory_seen_frame>900){begin_retreat(2);return;}}
 if(p->motion_state==9){uint32_t f=p->follower_role;if(physical_arrival(f,role_origin(f),now)){event(91,0,0,0,0,0,f);p->home_arrivals[f]=3;p->mission_stage=4;p->motion_state=10;stop_both(2);}else if(now-last_progress[f]>250)request_cleanup(53,now);return;}
 follower_tick(now);if(p->phase!=1||p->mission_stage>=4||p->motion_state==0)return;
 if(p->motion_state==11){
  if(settled_role(p->leader_role,now)){
   Breadcrumb current;if(raw_surface(p->leader_role,current,now)){
    current.index=current.published_seq=0;current.path_distance=p->role_crumb_distance[p->leader_role];reanchor_surface=current;
    memcpy(frozen_hold,current.xyz,12);memcpy(p->leader_hold_xyz,current.xyz,12);p->role_motion_mode[p->leader_role]=4;
    event(97,wait_reanchor_count,0,0,0,0,p->leader_role);p->motion_state=3;return;
   }
   if(now-p->motion_frame>60)request_cleanup(57,now);
  }else if(now-p->motion_frame>60)request_cleanup(44,now);
  return;
 }
 if(p->motion_state==4){if(physical_arrival(p->leader_role,frozen_hold,now)){stop_role(p->leader_role);p->motion_state=5;p->motion_frame=now;}else if(now-p->motion_frame>120)request_cleanup(53,now);return;}
 if(p->motion_state==5){if(settled_role(p->leader_role,now)){event(93,0,0,0,0,0,p->leader_role);p->role_motion_mode[p->leader_role]=4;p->motion_state=repair_resume_state;}else if(now-p->motion_frame>60)request_cleanup(44,now);return;}
 if(p->motion_state==6||p->motion_state==7){endpoint_tick(now);return;}
 if(p->motion_state==2){if(settled_role(p->leader_role,now)){role_pos(p->leader_role,frozen_hold);memcpy(p->leader_hold_xyz,frozen_hold,12);p->leader_hold_settled=1;p->role_motion_mode[p->leader_role]=4;p->motion_state=3;event(83,0,0,0,0,0,p->leader_role);}else if(now-p->motion_frame>60)request_cleanup(44,now);return;}
 if(p->motion_state==3){if(reanchor_wait(now))return;if(p->actual_gap<=200){p->motion_state=1;start_move(p->leader_role,p->mission_stage==3?role_origin(p->leader_role):memory_target,85,now);}else if(now-p->leader_hold_started>300){if(p->mission_stage==1)begin_retreat(8);else request_cleanup(53,now);}return;}
 if(p->mission_stage==1){
  bool visible=visible_target();float f[3];role_pos(0,f);
  if(visible&&idle_role(0)&&distance(f,memory_target)>150&&distance(frozen_goals[0],memory_target)>50){start_move(0,memory_target,85,now);return;}
  if((visible&&distance(f,memory_target)<=150)||(!visible&&distance(f,memory_target)<=45)){
   if(!visible){if(!p->memory_wait_started)p->memory_wait_started=now;if(now-p->memory_wait_started>=45){begin_retreat(2);return;}}
   if(visible){stop_role(0);p->motion_state=6;p->motion_frame=now;return;}
  }
 }else if(physical_arrival(p->leader_role,role_origin(p->leader_role),now)){event(91,0,0,0,0,0,p->leader_role);p->home_arrivals[p->leader_role]=3;stop_role(p->leader_role);p->motion_state=6;p->motion_frame=now;return;}
 if(p->actual_gap>240){begin_regroup(now);return;}
 if(now-last_progress[p->leader_role]>250){if(p->mission_stage==1)begin_retreat(8);else request_cleanup(53,now);}
}
