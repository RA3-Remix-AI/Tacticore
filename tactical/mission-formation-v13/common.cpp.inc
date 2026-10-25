// Actual pre-toggle weapon telemetry; never an SDK call or a substitute for prepare.
static uint32_t captured_initial_asset13,captured_initial_entry13;
static bool capture_initial_weapon13(uint32_t asset,uint32_t entry){
 if(captured_initial_asset13||captured_initial_entry13)return p->initial_weapon_asset==captured_initial_asset13&&p->initial_weapon_entry==captured_initial_entry13;
 if((asset!=0x447ea26e&&asset!=0x41872ecc)||!entry||p->initial_weapon_asset||p->initial_weapon_entry)return false;
 captured_initial_asset13=p->initial_weapon_asset=asset;captured_initial_entry13=p->initial_weapon_entry=entry;return true;
}
#ifndef MFM13_WEAPON_CAPTURE_ONLY
static float distance(const float a[3],const float b[3]){float x=a[0]-b[0],y=a[1]-b[1];return sqrtf(x*x+y*y);}
static bool finite_point(const float x[3]){return isfinite(x[0])&&isfinite(x[1])&&isfinite(x[2]);}
static bool support_settled(uint32_t now){Support& s=p->support;if(now==s.last_sample_frame)return false;s.last_sample_frame=now;uint32_t sm=word(s.update+0x3c);float xyz[3];read(s.thing+0x38,xyz,12);bool gate=s.private_stop_calls==s.stop_calls&&now>s.private_stop_frame&&word(s.update+0x50)==1&&!(word(sm+0x78)&0xffff)&&word(s.update+0x150)==0&&holding_stance(s.thing,s.update);float d=distance(xyz,s.stopped_xyz);if(gate){s.gate_samples++;s.stable_samples=d<=1?s.stable_samples+1:0;}else s.gate_samples=s.stable_samples=0;memcpy(s.stopped_xyz,xyz,12);return s.gate_samples>=3&&s.stable_samples>=3;}
static void stop_support(){Support& s=p->support;s.stable_samples=s.gate_samples=s.last_sample_frame=0;read(s.thing+0x38,s.stopped_xyz,12);tag=4;s.stop_calls++;((Stop)0x54b0a0)((void*)(uintptr_t)(s.update+0x24),1);event(36,0,0,0,0,0,1);tag=0;}
static void stop_both(uint32_t stage){issue_stop(stage);stop_support();}
static void move_role(bool support,const float* goal){tag=6;if(support)p->support.move_calls++;else p->move_calls++;((MoveFacade)0x571d90)((void*)(uintptr_t)((support?p->support.update:p->update)+0x24),(float*)goal,1);event(52,0,0,0,0,0,support);tag=0;}
static void normal_return(){
 invalidate_move_tickets(4);
 if(unit()&&!p->return_calls){restore_stance(0);tag=3;p->return_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->unit,1);p->return_verified=unit()&&word(p->unit+0x414)==p->default_team;event(5);tag=0;}
 if(support_valid()&&!p->support.return_calls){restore_stance(1);tag=3;p->support.return_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->support.thing,1);p->support.returned=support_valid()&&word(p->support.thing+0x414)==p->default_team;event(5,0,0,0,0,0,1);tag=0;}
 if(!p->return_verified||!p->support.returned)p->error=p->error?p->error:37;
 p->returned_frame=frame();p->return_pending=0;p->phase=2;
}
static void request_cleanup(uint32_t error,uint32_t now){invalidate_move_tickets(5);p->error=error;p->mission_stage=5;p->phase=7;p->cleanup_started=now;p->cleanup_front_stopped=p->cleanup_support_stopped=0;}
static bool no_override(){Support& s=p->support;return !p->native_move&&!p->native_attack&&!p->native_add&&!p->native_remove&&!p->native_stop&&!s.native_move&&!s.native_attack&&!s.native_add&&!s.native_remove&&!s.native_stop&&!p->stances[0].foreign_calls&&!p->stances[1].foreign_calls;}
static bool mobile(uint32_t t,uint32_t u){return !(word(t+0x84)&0x20080000)&&!word(t+0x238)&&word(u)==0xc48670&&word(u+0x24)==0xc48528&&word(u+8)==t;}
static bool absent_id(uint32_t id,uint32_t* count){
 uint32_t now=frame(),first=word(p->logic+0xb4),t=first;*count=0;
 while(t){if(t%4||*count>=20000||word(t)!=0xc4db60||!word(t+0xdc)||word(t+0xdc)==id)return false;uint32_t next=word(t+0x7c);if(next==t)return false;t=next;(*count)++;}
 return *count>0&&identity()&&frame()==now&&word(p->logic+0xb4)==first;
}
static void fatal_cleanup(uint32_t now){
 event(3);event(3,0,0,0,0,0,1);
 if(unit()&&p->detach_calls&&!p->return_calls){if(!p->cleanup_front_stopped){issue_stop(2);p->cleanup_front_stopped=1;}bool settled=stop_settled(now);if(settled||now-p->cleanup_started>=60){event(settled?68:69);restore_stance(0);tag=3;p->return_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->unit,1);p->return_verified=unit()&&word(p->unit+0x414)==p->default_team;event(5);tag=0;}}
 if(support_valid()&&p->support.detach_calls&&!p->support.return_calls){if(!p->cleanup_support_stopped){stop_support();p->cleanup_support_stopped=1;}bool settled=support_settled(now);if(settled||now-p->cleanup_started>=60){event(settled?68:69,0,0,0,0,0,1);restore_stance(1);tag=3;p->support.return_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->support.thing,1);p->support.returned=support_valid()&&word(p->support.thing+0x414)==p->default_team;event(5,0,0,0,0,0,1);tag=0;}}
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
 return mobile(thing,update)&&holding_stance(thing,update)&&word(update+0x50)==1&&!word(update+0x150)&&!(word(sm+0x78)&0xffff);
}

#endif
