// Software execution of the actual native handshake, with all game interaction
// replaced by explicit stubs. Never loads/injects or accesses a game process.
#include "shared.h"
#include <map>
#include <vector>
#include <cmath>
#include <cstring>
#include <cassert>
#include <cstdio>
static Tactical value;static Tactical* p=&value;
static float frozen_route[16][3];static uint32_t frozen_route_count;
static std::map<uint32_t,uint32_t> words;static unsigned moves,cleanup;static std::vector<uint32_t> events;static bool settled=true,visible=true;
static uint32_t word(uint32_t a){return words[a];}
static bool read(uint32_t a,void* out,SIZE_T n){for(unsigned i=0;i<n;i+=4){uint32_t x=word(a+i);memcpy((char*)out+i,&x,4);}return true;}
static void number(uint32_t a,float f){uint32_t x;memcpy(&x,&f,4);words[a]=x;}
static void xyz(uint32_t a,float x,float y,float z){number(a,x);number(a+4,y);number(a+8,z);}
static float distance(const float a[3],const float b[3]){return hypotf(a[0]-b[0],a[1]-b[1]);}
static bool finite_point(const float x[3]){return std::isfinite(x[0])&&std::isfinite(x[1])&&std::isfinite(x[2]);}
static bool mobile(uint32_t,uint32_t){return true;}
static bool visible_target(){return visible;}
static bool stop_settled(uint32_t){return settled;}
static bool support_settled(uint32_t){return settled;}
static void request_cleanup(uint32_t error,uint32_t){p->error=error;cleanup++;}
static void event(uint32_t kind,uint32_t=0,uint32_t=0,float=0,float=0,float=0,uint32_t=0){events.push_back(kind);}
static void approach_leg(uint32_t){moves++;}
using std::isfinite;
#include "planning.cpp.inc"
static void reset(){
 memset(p,0,sizeof(*p));words.clear();events.clear();moves=cleanup=0;settled=visible=true;frozen_route_count=0;
 p->unit=0x1000;p->support.thing=0x2000;p->update=0x5000;p->support.update=0x6000;p->target_unit=0x7000;
 words[0x133c]=0x3000;words[0x233c]=0x4000;number(0x3004,100);number(0x4004,120);words[0x1048]=words[0x2048]=4;
 words[0x8024]=0x1000;words[0x9024]=0x2000;words[0xa018]=0x8000;words[0xb018]=0x9000;words[0x503c]=0x8000;words[0x603c]=0x9000;words[0x8004]=0xa000;words[0x9004]=0xb000;words[0xa004]=words[0xb004]=16;words[0x5050]=words[0x6050]=1;
 xyz(0x1038,0,0,210);xyz(0x2038,-60,0,210);xyz(0x7038,300,0,210);
 p->planning_front[2]=p->planning_support[2]=p->submitted_front[2]=p->submitted_support[2]=210;p->planning_support[0]=p->submitted_support[0]=-60;
 p->mission_stage=9;p->planning_ready=1;p->planning_ready_frame=99;p->planning_ready_tick=GetTickCount();p->planning_timeout_ms=6000;p->planning_threat_clear=1;p->planning_threat_frame=100;p->target_observed_frame=100;p->mission_deadline_frame=4500;
 p->route_count=2;p->route[0][0]=100;p->route[1][0]=200;p->route[0][2]=p->route[1][2]=210;
}
int main(){
 reset();assert(admissible_actor(p->unit,p->update));words[0xa004]=1;assert(admissible_actor(p->unit,p->update));words[0xa004]=10;words[0xa000]=0xc548c0;assert(admissible_actor(p->unit,p->update));words[0xa000]=0xc548c4;assert(!admissible_actor(p->unit,p->update));for(unsigned state:{7u,54u,77u}){words[0xa004]=state;assert(!admissible_actor(p->unit,p->update));}
 reset();words[0x1080]=1;assert(!admissible_actor(p->unit,p->update));
 reset();planning_tick(100);assert(moves==0&&cleanup==0&&!frozen_route_count);
 reset();p->route_ready=1;p->route_generation=2;planning_tick(100);assert(moves==1&&!cleanup&&frozen_route_count==2&&p->route_committed_generation==2&&p->route_commit_frame==100);p->route[0][0]=999;assert(frozen_route[0][0]==100);
 for(unsigned which=0;which<13;which++){
  reset();p->route_ready=1;p->route_generation=2;
  if(which==0)p->route_generation=1;
  if(which==1)p->route[0][0]=25;
  if(which==2)p->planning_ready_tick-=7000;
  if(which==3)p->retreat_requested=1;
  if(which==4)visible=false;
  if(which==5)p->planning_threat_clear=0;
  if(which==6)xyz(0x1038,2,0,210);
  if(which==7)p->route_count=17;
  if(which==8)xyz(0x7038,1000,0,210);
  if(which==9)p->submitted_front[0]=3;
  if(which==10)p->mission_deadline_frame=200;
  if(which==11)number(0x3004,25);
  if(which==12)settled=false;
  planning_tick(100);assert(!moves&&cleanup==1&&p->error==55);
 }
 reset();p->route_ready=1;p->route_generation=2;settled=false;p->stable_samples=p->support.stable_samples=3;p->last_sample_frame=p->support.last_sample_frame=100;planning_tick(100);assert(!moves&&!cleanup);
 reset();p->route_ready=1;p->route_generation=2;settled=false;p->stable_samples=p->support.stable_samples=3;p->last_sample_frame=p->support.last_sample_frame=99;planning_tick(100);assert(!moves&&cleanup==1);
 reset();p->mission_stage=8;p->planning_ready=0;p->route_ready=0;p->route_count=0;p->nav_frame=99;planning_tick(100);assert(!moves&&!cleanup&&p->planning_ready&&p->mission_stage==9&&p->planning_ready_frame==100);
 reset();p->mission_stage=8;settled=false;p->nav_frame=1;planning_tick(100);assert(!moves&&cleanup==1&&p->planning_failed==5);
 printf("{\"native_handshake_cases\":27,\"passed\":true,\"game_access\":false}\n");return 0;
}
