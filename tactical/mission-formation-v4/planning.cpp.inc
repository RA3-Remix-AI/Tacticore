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
