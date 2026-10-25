#include "shared.h"
#include "MinHook.h"
#include <string.h>
#include <stdio.h>
#include <math.h>
static Tactical* p;static HANDLE mapping;static HMODULE pin;static HWND window;static UINT_PTR timer;static uint32_t tag,start_tick,last_seq,used_count;static uint32_t used_commands[128][4],used_tasks[128][4],used_tokens[128];
static bool read(uint32_t a,void* b,SIZE_T n){SIZE_T got=0;return ReadProcessMemory(GetCurrentProcess(),(void*)(uintptr_t)a,b,n,&got)&&got==n;}
static uint32_t word(uint32_t a){uint32_t v=0;read(a,&v,4);return v;}
static uint32_t frame(){return word(p->logic+0x50);}static bool paused(){return word(p->logic+0x15c)!=0;}
static bool identity(){return word(0xcd8ce4)==p->logic&&word(p->logic)==0xbeb630&&word(p->owner)==0xc5bce0&&word(p->owner+0x20)==3&&word(p->owner+0x10)==p->player_template&&word(p->owner+0x90)==p->ai&&word(p->ai)==0xc60f60&&word(p->ai+8)==p->owner&&word(p->ai+0x8b0)==p->personality&&word(p->personality+0x18)==p->personality_id;}
static bool unit(Unit& u){float hp=0;return word(u.thing)==0xc4db60&&word(u.thing+0xdc)==u.id&&word(u.thing+0x418)==p->owner&&word(word(u.thing+4)+8)==u.hash&&word(u.thing+0x374)==u.update&&word(u.update+8)==u.thing&&read(word(u.thing+0x33c)+4,&hp,4)&&isfinite(hp)&&hp>0;}
static Unit* by_thing(uint32_t t){for(unsigned i=0;i<2;i++)if(p->units[i].thing==t)return &p->units[i];return NULL;}
static Unit* by_update(uint32_t a){for(unsigned i=0;i<2;i++)if(p->units[i].update==a)return &p->units[i];return NULL;}
static float distance(const float a[3],const float b[3]){float x=a[0]-b[0],y=a[1]-b[1];return sqrtf(x*x+y*y);}
static void event(Unit* u,uint32_t kind,uint32_t arg=0,uint32_t caller=0){LONG i=InterlockedIncrement(&p->count)-1;if(i>=T_CAP){p->overflow=1;return;}Event e={};e.kind=kind;e.tag=tag;e.stage=p->stage;e.frame=frame();e.tick=GetTickCount();e.thread=GetCurrentThreadId();e.caller=caller;e.arg=arg;if(u){e.unit_id=u->id;if(word(u->thing)==0xc4db60&&word(u->thing+0xdc)==u->id&&word(u->thing+0x418)==p->owner&&word(word(u->thing+4)+8)==u->hash){e.team=word(u->thing+0x414);e.owner=p->owner;e.source=word(u->update+0x50);read(u->thing+0x38,&e.x,12);e.sm=word(u->update+0x3c);e.sm_flags=word(e.sm+0x78);e.state=word(e.sm+4);e.state_id=word(e.state+4);e.path=word(u->update+0x150);e.path_node=word(e.path+0x10);read(e.sm+0x2c,e.requested,12);read(e.sm+0x48,e.effective,12);read(e.path_node+0xc,e.path_xy,8);}}p->events[i]=e;MemoryBarrier();InterlockedExchange((LONG*)&p->events[i].seq,i+1);}
typedef void (__attribute__((thiscall))*Move)(void*,float*,uint32_t);typedef void (__attribute__((thiscall))*Attack)(void*,void*,uint32_t,uint32_t);typedef void (__attribute__((thiscall))*Transfer)(void*,void*,uint32_t);typedef void (__attribute__((thiscall))*Member)(void*,void*);
typedef void (__attribute__((thiscall))*Stop)(void*,uint32_t);static Stop old_stop_facade,old_stop_private;
static Move old_move;static Attack old_attack;static Transfer old_transfer;static Member old_add,old_remove;
static void __attribute__((fastcall)) move_hook(void* self,void*,float* xyz,uint32_t source){InterlockedIncrement(&p->active);Unit* u=by_update((uintptr_t)self);if(u){if(!tag)u->native_move++;event(u,10,source,(uintptr_t)__builtin_return_address(0));}old_move(self,xyz,source);if(u)event(u,11,source);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) attack_hook(void* self,void*,void* victim,uint32_t shots,uint32_t source){InterlockedIncrement(&p->active);Unit* u=by_update((uintptr_t)self);if(u){if(!tag)u->native_attack++;event(u,12,source,(uintptr_t)__builtin_return_address(0));}old_attack(self,victim,shots,source);if(u)event(u,13,source);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) transfer_hook(void* self,void*,void* target,uint32_t to_ai){InterlockedIncrement(&p->active);Unit* u=by_thing((uintptr_t)target);if(u)event(u,14,to_ai,(uintptr_t)__builtin_return_address(0));old_transfer(self,target,to_ai);if(u)event(u,15,to_ai);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) add_hook(void* self,void*,void* target){InterlockedIncrement(&p->active);Unit* u=by_thing((uintptr_t)target);if(u){if(!tag)u->native_add++;event(u,16,(uintptr_t)self,(uintptr_t)__builtin_return_address(0));}old_add(self,target);if(u)event(u,17,(uintptr_t)self);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) remove_hook(void* self,void*,void* target){InterlockedIncrement(&p->active);Unit* u=by_thing((uintptr_t)target);if(u){if(!tag)u->native_remove++;event(u,18,(uintptr_t)self,(uintptr_t)__builtin_return_address(0));}old_remove(self,target);if(u)event(u,19,(uintptr_t)self);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) stop_facade_hook(void* self,void*,uint32_t source){InterlockedIncrement(&p->active);Unit* u=by_update((uintptr_t)self-0x24);if(u){if(!tag)u->native_stop++;event(u,20,source,(uintptr_t)__builtin_return_address(0));}old_stop_facade(self,source);if(u)event(u,21,source);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) stop_private_hook(void* self,void*,uint32_t source){InterlockedIncrement(&p->active);Unit* u=by_update((uintptr_t)self);uint32_t caller=(uintptr_t)__builtin_return_address(0);bool expected=u&&(p->phase==1||p->phase==6)&&p->stage==0&&u->stop_calls&&source==1&&caller==0x787791;if(u){if(!tag&&!expected)u->native_stop++;event(u,22,source,caller);}old_stop_private(self,source);if(u){if(expected){u->private_stop_calls++;u->private_stop_frame=frame();}event(u,23,source,caller);}InterlockedDecrement(&p->active);}
struct Hook {uint32_t a;void* fn;void** original;const char* signature;uint32_t n;BYTE before[24];bool made,enabled;};
static Hook hooks[]={
{0x6eff70,(void*)move_hook,(void**)&old_move,"\x56\x8b\xf1\x8b\x4e\x3c\x8b\x01\x8b\x50\x38\xff\xd2",13,{},false,false},
{0x76e690,(void*)attack_hook,(void**)&old_attack,"\x83\x7c\x24\x04\x00\x55\x56\x8b\xf1\x8b\x6e\x08",12,{},false,false},
{0x838820,(void*)transfer_hook,(void**)&old_transfer,"\x8b\x81\x8c\x00\x00\x00\x85\xc0\x74\x4f\x56\x8b\xb1\x90\x00\x00\x00",17,{},false,false},
{0x8d8880,(void*)add_hook,(void**)&old_add,"\x83\xec\x24\x56\x8b\x74\x24\x2c\x8b\x46\x04",11,{},false,false},
{0x8cd630,(void*)remove_hook,(void**)&old_remove,"\x83\xec\x34\x53\x57\x8b\x7c\x24\x40\x8b\x47\x04",12,{},false,false},
{0x54b0a0,(void*)stop_facade_hook,(void**)&old_stop_facade,"\x83\xec\x5c\x8b\x44\x24\x60\x56\x6a\x01\x50\x8b\xf1",13,{},false,false},
{0x721ad0,(void*)stop_private_hook,(void**)&old_stop_private,"\x83\xec\x08\x55\x8b\xe9\x8b\x45\x08\x8b\x48\x04",12,{},false,false}};
static void finish(){if(timer){KillTimer(window,timer);timer=0;}event(NULL,4);for(unsigned i=0;i<7;i++){Hook& h=hooks[i];if(h.enabled){MH_DisableHook((void*)(uintptr_t)h.a);h.enabled=false;}BYTE b[24];if(h.made&&read(h.a,b,h.n)&&!memcmp(b,h.before,h.n))p->restore_mask|=1u<<i;}p->phase=p->error?4:3;}
static uint32_t disposed(Unit& u){
 if(!identity())return 0;
 uint32_t now=frame();
 if(word(u.thing)==0xc4db60&&word(u.thing+0xdc)==u.id&&word(u.thing+0x418)==p->owner&&word(word(u.thing+4)+8)==u.hash){float hp=1;if(read(word(u.thing+0x33c)+4,&hp,4)&&isfinite(hp)&&hp<=0){u.disposed_hp=hp;u.disposed_frame=now;return 1;}}
 uint32_t thing=word(p->logic+0xb4),count=0;
 while(thing){uint32_t vt=0,id=0,next=0;if(count++>=20000||thing%4||!read(thing,&vt,4)||vt!=0xc4db60||!read(thing+0xdc,&id,4)||!id||id==u.id||!read(thing+0x7c,&next,4)||next==thing)return 0;thing=next;}
 if(!identity()||frame()!=now)return 0;
 u.disposed_frame=now;u.disposed_list_count=count;return 2;
}
static void return_all(){for(unsigned i=0;i<2;i++){Unit& u=p->units[i];if(!u.detach_calls||u.return_calls)continue;if(!identity()){p->error=31;break;}if(!unit(u)){uint32_t why=disposed(u);if(why){u.disposed_verified=1;u.disposed_reason=why;event(&u,30,why);}p->error=32;continue;}if(u.native_add){p->error=36;continue;}tag=3;u.return_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)u.thing,1);event(&u,5);tag=0;u.returned=unit(u)&&word(u.thing+0x414)==p->default_team;if(!u.returned)p->error=37;}p->returned_frame=frame();p->phase=2;p->return_pending=0;}
static void issue_move(Unit& u,float* xyz){tag=2;u.move_calls++;((Move)0x6eff70)((void*)(uintptr_t)u.update,xyz,0);event(&u,2);tag=0;}
static void CALLBACK tick(HWND,UINT,UINT_PTR,DWORD){
 if(GetCurrentThreadId()!=p->thread){p->error=30;return;}if(!identity()){p->error=31;finish();return;}
 if(paused()){p->paused_samples++;if(p->phase==1&&(p->stop_requested||GetTickCount()-start_tick>60000))p->return_pending=1;return;}
 uint32_t now=frame();if(p->phase==5){
  if(p->stop_requested||GetTickCount()-start_tick>60000){p->error=33;finish();return;}
  if(!unit(p->units[0])||!unit(p->units[1])||p->units[0].thing==p->units[1].thing||p->units[0].id==p->units[1].id||p->units[0].hash!=0x19ab11af||p->units[1].hash!=0x2c358c61||word(p->owner+0xac)!=p->default_team||word(word(p->owner+0x8c)+0x10)!=p->script_team||word(word(p->default_team+4)+8)!=p->owner||word(word(p->script_team+4)+8)!=p->owner){p->error=34;finish();return;}
  for(unsigned i=0;i<2;i++){Unit& u=p->units[i];read(u.thing+0x38,u.initial,12);memcpy(u.hold,u.initial,12);float d=distance(u.initial,u.goal);if(!isfinite(d)||d<20||d>120||fabsf(u.initial[2]-u.goal[2])>2){p->error=34;finish();return;}}
  float spacing=distance(p->units[0].goal,p->units[1].goal);if(spacing<40||spacing>100){p->error=34;finish();return;}
  p->phase=6;p->issued_frame=now;p->stage=0;p->stage_frame=now;
  for(unsigned i=0;i<2;i++){Unit& u=p->units[i];u.original_team=word(u.thing+0x414);tag=1;u.detach_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)u.thing,0);event(&u,1);tag=0;if(!unit(u)||word(u.thing+0x414)!=p->script_team){p->error=35;p->phase=1;p->return_pending=1;return;}}
  for(unsigned i=0;i<2;i++){Unit& u=p->units[i];if(word(u.update)!=0xc48670||word(u.update+0x24)!=0xc48528||word(0xc48528)!=0x787500||word(0xc48670+0x8c)!=0x721ad0){p->error=43;p->phase=1;p->return_pending=1;return;}read(u.thing+0x38,u.stopped_xyz,12);tag=4;u.stop_calls++;((Stop)0x54b0a0)((void*)(uintptr_t)(u.update+0x24),1);event(&u,6);tag=0;}p->phase=1;return;
 }
 for(unsigned i=0;i<2;i++)event(&p->units[i],3);
 if(p->phase==1){
  bool valid=true;for(unsigned i=0;i<2;i++){Unit& u=p->units[i];valid&=unit(u)&&word(u.thing+0x414)==p->script_team&&!u.native_move&&!u.native_attack&&!u.native_add&&!u.native_remove&&!u.native_stop;}if(!valid){p->error=38;return_all();return;}
  if(p->stop_requested||p->return_pending||now-p->issued_frame>=p->lease_frames||GetTickCount()-start_tick>60000){return_all();return;}
  float front[3],support[3];read(p->units[0].thing+0x38,front,12);read(p->units[1].thing+0x38,support,12);float df=distance(front,p->units[0].goal),ds=distance(support,p->units[1].goal);
  if(p->stage==0){bool ready=true;for(unsigned i=0;i<2;i++){Unit& u=p->units[i];float xyz[3];read(u.thing+0x38,xyz,12);if(now!=u.last_sample_frame){u.last_sample_frame=now;uint32_t sm=word(u.update+0x3c);bool gate=u.private_stop_calls==1&&now>u.private_stop_frame&&word(u.update+0x50)==1&&!(word(sm+0x78)&0xffff)&&word(u.update+0x150)==0;float dx=xyz[0]-u.stopped_xyz[0],dy=xyz[1]-u.stopped_xyz[1];if(gate){u.gate_samples++;if(dx*dx+dy*dy<=1)u.stable_samples++;else u.stable_samples=0;}else{u.gate_samples=0;u.stable_samples=0;}memcpy(u.stopped_xyz,xyz,12);}ready&=u.stable_samples>=3&&u.gate_samples>=3;}
   if(ready){for(unsigned i=0;i<2;i++){Unit& u=p->units[i];memcpy(u.hold,u.stopped_xyz,12);event(&u,24);}p->stage=1;p->stage_frame=now;issue_move(p->units[0],p->units[0].goal);}
   else if(now-p->issued_frame>=30){p->error=44;return_all();}
   return;
  }
  if(p->stage==1){bool held=distance(support,p->units[1].hold)<=15;if(held)p->support_hold_samples++;else p->support_hold_samples=0;if(df<=15&&held)p->units[0].arrivals++;else p->units[0].arrivals=0;if(p->units[0].arrivals>=3&&p->support_hold_samples>=3){p->front_arrival_frame=now;p->stage=2;p->stage_frame=now;p->support_issued_frame=now;issue_move(p->units[1],p->units[1].goal);}}
  else if(p->stage==2){if(ds<=15)p->units[1].arrivals++;else p->units[1].arrivals=0;float spacing=distance(front,support);float vx=p->units[0].goal[0]-p->units[0].initial[0],vy=p->units[0].goal[1]-p->units[0].initial[1];float forward=(front[0]-support[0])*vx+(front[1]-support[1])*vy;if(df<=20&&ds<=15&&spacing>=p->min_spacing&&spacing<=p->max_spacing&&forward>0)p->goal_samples++;else p->goal_samples=0;if(p->goal_samples>=3&&p->units[1].arrivals>=3){p->stage=3;return_all();}}
 }else if(p->phase==2&&now-p->returned_frame>=p->post_frames)finish();
}
static void install(HWND hwnd){p->callback_thread=GetCurrentThreadId();FILETIME a,b,c,d;
 if(p->magic!=T_MAGIC||p->version!=3||p->pid!=GetCurrentProcessId()||p->thread!=p->callback_thread||!GetProcessTimes(GetCurrentProcess(),&a,&b,&c,&d)||a.dwLowDateTime!=p->start_low||a.dwHighDateTime!=p->start_high||!identity()||p->lease_frames<60||p->lease_frames>180||p->post_frames<30||p->post_frames>180||p->min_spacing<25||p->max_spacing>120||p->min_spacing>=p->max_spacing){p->error=10;p->phase=4;return;}
 if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCSTR)(uintptr_t)&install,&pin)){p->error=11;p->phase=4;return;}
 for(unsigned i=0;i<7;i++)if(!read(hooks[i].a,hooks[i].before,hooks[i].n)||memcmp(hooks[i].before,hooks[i].signature,hooks[i].n)){p->error=12+i;p->phase=4;return;}
 if(used_count>=128||!p->token||p->seq<=last_seq){p->error=40;p->restore_mask=127;p->phase=4;return;}for(unsigned i=0;i<used_count;i++)if(used_tokens[i]==p->token||!memcmp(used_commands[i],p->command,16)||!memcmp(used_tasks[i],p->task,16)){p->error=41;p->restore_mask=127;p->phase=4;return;}memcpy(used_commands[used_count],p->command,16);memcpy(used_tasks[used_count],p->task,16);used_tokens[used_count++]=p->token;last_seq=p->seq;
 MH_STATUS s=MH_Initialize();if(s!=MH_OK&&s!=MH_ERROR_ALREADY_INITIALIZED){p->error=20;p->phase=4;return;}for(unsigned i=0;i<7;i++){Hook& h=hooks[i];if(!h.made&&MH_CreateHook((void*)(uintptr_t)h.a,h.fn,h.original)!=MH_OK){p->error=21;finish();return;}h.made=true;}for(unsigned i=0;i<7;i++){Hook& h=hooks[i];if(MH_EnableHook((void*)(uintptr_t)h.a)!=MH_OK){p->error=22;finish();return;}h.enabled=true;}
 p->phase=5;window=hwnd;start_tick=GetTickCount();timer=SetTimer(window,0x52413374,100,tick);if(!timer){p->error=23;finish();return;}event(NULL,0);
}
extern "C" __declspec(dllexport) LRESULT CALLBACK TacticalFormationStopControl(int code,WPARAM wp,LPARAM lp){if(code>=0&&wp==PM_REMOVE&&lp&&((MSG*)lp)->message==T_MESSAGE&&((MSG*)lp)->wParam==T_MAGIC){MSG* msg=(MSG*)lp;uint32_t token=(uint32_t)msg->lParam;if(token&&(!p||((p->phase==3||p->phase==4)&&p->restore_mask==127&&!p->active&&!timer))){char name[100];snprintf(name,sizeof(name),"Local\\RA3TacticalFormationStop_%lu_%u",GetCurrentProcessId(),token);HANDLE next_mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);Tactical* next=next_mapping?(Tactical*)MapViewOfFile(next_mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Tactical)):NULL;if(next&&next->token==token&&next->pid==GetCurrentProcessId()&&next->magic==T_MAGIC){if(p)UnmapViewOfFile(p);if(mapping)CloseHandle(mapping);p=next;mapping=next_mapping;tag=0;install(msg->hwnd);}else{if(next)UnmapViewOfFile(next);if(next_mapping)CloseHandle(next_mapping);}}}return CallNextHookEx(NULL,code,wp,lp);}
BOOL WINAPI DllMain(HINSTANCE h,DWORD why,LPVOID){if(why==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(h);return TRUE;}
