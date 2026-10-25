// Pure fake-engine harness: includes the actual production state-machine file.
// It does not attach to a game, load a DLL, or invoke any game address.
#include "shared.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <stdlib.h>
static Probe storage,*p=&storage;static Sample current;static uint32_t now,tag,start_tick;
static bool world_ok,actor_ok,module_ok,sample_ok,stuck,stance_fail,restore_fail;static unsigned passed;
static uint32_t fake_tick(){return 10000+now*67;}
#define GetTickCount fake_tick
static uint32_t frame(){return now;}
static bool world(){return world_ok;}static bool actor(){return actor_ok;}static bool module(){return module_ok;}
static uint32_t word(uint32_t a){if(a==p->owner+0xac)return p->default_team;if(a==p->owner+0x8c)return 0x70000;if(a==0x70010)return p->script_team;if(a==p->thing+0x414)return current.team;if(a==p->stance_module+0x38)return current.stance;return 0;}
static bool finite_xyz(const float* a){return isfinite(a[0])&&isfinite(a[1])&&isfinite(a[2]);}
static bool sample(Sample& s){current.frame=now;s=current;return sample_ok;}
static float distance(const float* a,const float* b){float x=a[0]-b[0],y=a[1]-b[1];return sqrtf(x*x+y*y);}
static void emit(uint32_t kind,uint32_t arg=0,uint32_t caller=0,uint32_t self=0,uint32_t source=0,uint32_t result=0){if(p->count>=T_CAP)abort();Event& e=p->events[p->count];memset(&e,0,sizeof(e));e.kind=kind;e.arg=arg;e.caller=caller;e.self=self;e.source=source;e.result=result;e.tag=tag;e.frame=now;e.tick=fake_tick();e.thread=p->thread;e.stage=p->stage;e.sdk_calls=p->sdk_calls;e.error=p->error;e.explicit_stops=p->explicit_stops;e.private_explicit_stops=p->private_explicit_stops;e.automatic_stop2=p->automatic_stop2;e.private_automatic_stop2=p->private_automatic_stop2;sample(e.sample);e.seq=++p->count;}
static void sdk(uint32_t code,uint32_t value=0){p->sdk_calls++;emit(50,code,0,0,0,value);}
static void stop_callbacks(uint32_t source){uint32_t caller=source==2?0x76429b:0x900000;p->automatic_stop2+=source==2;emit(30,0,caller,p->update+0x24,source);emit(32,0,0x787791,p->update,source);current.source=source;current.path=stuck?0x1234:0;current.state_id=current.stance==2?94:16;current.state_vtable=current.stance==2?0xc551a0:0xc55130;if(source==1){p->private_explicit_stops++;p->private_stop_frame=now;}else p->private_automatic_stop2++;emit(33,0,0x787791,p->update,source);emit(31,0,0,p->update+0x24,source);}
static void stop(uint32_t which){p->stable_samples=0;p->last_sample_frame=0;p->stop_issue_frame=now;memcpy(p->stopped_xyz,current.xyz,12);tag=which;p->explicit_stops++;sdk(which==3?3:4);stop_callbacks(1);tag=0;}
static bool set_stance(uint32_t value,uint32_t which){tag=which;p->stance_calls++;sdk(which==2?2:5,value);emit(20,value,0x900100,p->stance_module);bool okay=!(which==2?stance_fail:restore_fail);if(okay){current.stance=value;stop_callbacks(2);}emit(21,value,0,p->stance_module,0,okay);tag=0;return okay;}
static void transfer(uint32_t to_ai){tag=to_ai?6:1;if(to_ai)p->return_calls++;else p->detach_calls++;sdk(to_ai?6:1);emit(10,to_ai,0x900200,p->owner);emit(14,p->ai+0x104,0x838877,p->ai+0x104);emit(15,p->ai+0x104,0,p->ai+0x104);emit(12,p->ai+0x104,0x83885b,p->ai+0x104);current.team=to_ai?p->default_team:p->script_team;emit(13,p->ai+0x104,0,p->ai+0x104);emit(11,to_ai,0,p->owner);tag=0;}
static void finish(){p->stage=5;emit(4);p->restore_mask=63;p->phase=p->error?4:3;}
static void cleanup(uint32_t error){if(error&&!p->error)p->error=error;if(p->stage>=3)return;p->stage=3;p->cleanup_started=now;stop(4);}
#include "logic.cpp.inc"
static void check(bool v,const char* why){if(!v){fprintf(stderr,"FAIL: %s\n",why);exit(1);}passed++;}
static void reset(){memset(p,0,sizeof(*p));memset(&current,0,sizeof(current));now=100;tag=0;start_tick=fake_tick();world_ok=actor_ok=module_ok=sample_ok=true;stuck=stance_fail=restore_fail=false;p->magic=T_MAGIC;p->version=1;p->pid=123;p->thread=456;p->token=77;p->seq=1;p->logic=0x1000;p->owner=0x2000;p->ai=0x3000;p->thing=0x4000;p->object_id=10;p->type_hash=0x19ab11af;p->template_ptr=0x5000;p->update=0x6000;p->stance_module=0x8000;p->original_team=0xa000;p->default_team=0xb000;p->script_team=0xc000;p->observed_frame=p->threat_frame=100;p->threat_clear=1;p->expires_frame=400;p->test_stance=2;p->phase=5;p->heartbeat_tick=fake_tick();
 for(unsigned i=0;i<4;i++){p->session[i]=i+1;p->commander[i]=i+10;p->command[i]=i+20;p->task[i]=i+30;}
 current.thing=p->thing;current.id=p->object_id;current.type_hash=p->type_hash;current.owner=p->owner;current.template_ptr=p->template_ptr;current.update=p->update;current.update_vtable=0xc48670;current.update_backref=p->thing;current.team=p->original_team;current.stance_module=p->stance_module;current.stance_vtable=0xc37f90;current.stance_backref=p->thing;current.stance_data=0xe000;current.stance=0;current.stance_enum_list=0xf000;current.stance_enum_count=4;for(unsigned i=0;i<4;i++)current.stance_enum_entries[2*i]=i;current.sm=0x11000;current.sm_owner=p->thing;current.state=0x12000;current.state_id=16;current.state_vtable=0xc55130;current.state_owner_sm=current.sm;current.source=0;current.height_flags=4;current.hp=100;current.xyz[0]=100;current.xyz[1]=200;current.xyz[2]=210;}
static void step(uint32_t delta=1){now+=delta;p->heartbeat_tick=fake_tick();probe_body();}
static void through_terminal(){for(unsigned i=0;i<400&&p->phase!=3&&p->phase!=4;i++)step();}
static void begin_hold(){probe_body();for(unsigned i=0;i<3;i++)step();check(p->stage==2&&p->initial_stop_verified,"initial real Stop3");}
int main(int argc,char** argv){
 reset();begin_hold();through_terminal();check(p->phase==3&&p->hold_verified&&p->cleanup_stop_verified,"hold90 and cleanup pass");check(p->sdk_calls==6&&p->detach_calls==1&&p->return_calls==1&&p->stance_calls==2&&p->explicit_stops==2,"exact six explicit SDK");check(p->automatic_stop2==2&&p->private_automatic_stop2==2&&p->private_explicit_stops==2,"automatic2 distinct from explicit1");check(p->hold_finished-p->hold_started==90&&p->hold_samples==91&&p->hold_max_gap==1&&!p->hold_missing_frames,"exact full90 sampled frames");check(p->stance_restored&&p->pool_before_enum==0&&p->return_verified,"original enum before live pool Return");if(argc>1){FILE* f=fopen(argv[1],"wb");if(!f)return 2;fwrite(p,1,sizeof(*p),f);fclose(f);}
 reset();current.hp=79;probe_body();check(p->error==34&&!p->sdk_calls,"Cons HP79 rejected");reset();current.hp=80;probe_body();check(p->detach_calls==1,"Cons HP80 accepted");reset();p->type_hash=current.type_hash=0x2c358c61;current.hp=95;probe_body();check(p->error==34&&!p->sdk_calls,"Flak95 rejected");reset();p->type_hash=current.type_hash=0x2c358c61;current.hp=96;probe_body();check(p->detach_calls==1,"Flak96 accepted");
 reset();current.stance=2;probe_body();check(p->error==34&&!p->sdk_calls,"same enum no change probe rejected");reset();current.state_id=54;probe_body();check(p->error==34&&!p->sdk_calls,"pending garrison rejected");reset();current.holder=1;probe_body();check(p->error==34&&!p->sdk_calls,"holder rejected");reset();current.height_flags=0;probe_body();check(p->error==34&&!p->sdk_calls,"unknown surface rejected");reset();current.sm_flags=1;probe_body();check(p->error==34&&!p->sdk_calls,"low lock rejected");reset();p->threat_clear=0;probe_body();check(p->error==34&&!p->sdk_calls,"threat rejected");reset();p->observed_frame=39;probe_body();check(p->error==34&&!p->sdk_calls,"stale observation rejected");
 reset();probe_body();step();step();check(p->stage==1&&p->stable_samples==2,"two Stop samples insufficient");probe_body();check(p->stage==1&&p->stable_samples==2,"same frame cannot add third");step();check(p->stage==2,"third distinct accepted");
 reset();begin_hold();step(2);check(p->stage==3&&!p->hold_verified&&p->hold_missing_frames==1,"missing logical frame fails hold");through_terminal();check(p->return_verified&&p->stance_restored,"gap failure still safe restore Return");
 reset();begin_hold();current.path=1234;step();check(p->stage==3&&!p->hold_verified,"state94 plus path fails");
 reset();begin_hold();current.xyz[0]+=1.01f;step();check(p->stage==3&&!p->hold_verified,"path0 but displacement fails");
 reset();begin_hold();for(unsigned i=0;i<16&&p->stage==2;i++){current.xyz[0]+=1;step();}check(p->stage==3&&!p->hold_verified&&p->max_hold_drift>15,"cumulative anchor drift fails despite <=1 steps");
 reset();stuck=true;probe_body();through_terminal();check(p->error==41&&!p->initial_stop_verified&&!p->cleanup_stop_verified&&p->return_verified&&p->stance_restored&&p->sdk_calls==6,"both60f stops fail but bounded release");
 reset();stance_fail=true;probe_body();through_terminal();check(p->error==36&&!p->hold_verified&&p->return_verified&&p->stance_calls==1,"setter failure no invented restore call");
 reset();begin_hold();restore_fail=true;through_terminal();check(p->error==46&&!p->stance_restored&&p->return_verified,"restore failure never reported restored");
 reset();probe_body();actor_ok=false;step();check(p->phase==4&&p->disposed&&!p->return_calls,"dead or invalid no stale Return");
 reset();probe_body();module_ok=false;through_terminal();check(p->phase==4&&p->error==36&&!p->stance_restored&&p->return_verified&&p->return_calls==1&&p->sdk_calls==5,"invalid module but live actor bounded Return without stale setter");
 reset();probe_body();sample_ok=false;through_terminal();check(p->phase==4&&p->error==33&&p->stance_restored&&p->return_verified&&p->return_calls==1&&p->sdk_calls==6,"persistent sample failure cannot bypass60frame release");
 reset();current.state_owner_sm=0;probe_body();check(p->error==34&&!p->sdk_calls,"broken state SM binding rejected");
 reset();probe_body();world_ok=false;step();check(p->phase==4&&p->scene_changed&&!p->return_calls,"scene gone no fake Return");
 reset();begin_hold();p->stop_requested=1;step();through_terminal();check(p->error==40&&p->stance_restored&&p->return_verified&&!p->hold_verified,"host stop bounded cleanup");
 reset();begin_hold();p->expires_frame=now+1;step();through_terminal();check(p->error==40&&!p->hold_verified&&p->return_verified,"deadline never renewed");
 printf("{\"scope\":\"pure_fake_engine_actual_logic\",\"tests\":%u,\"passed\":true,\"field_verified\":false}\n",passed);return 0;
}
