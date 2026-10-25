#include "shared.h"
#include "MinHook.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <stddef.h>
#include <float.h>
static Probe *p;static HANDLE mapping;static HMODULE pin;static HWND window;static UINT_PTR timer;
static Probe frozen;static uint32_t tag,start_tick,last_advance=0xffffffffu,last_pulse,install_tick;static bool has_pulse,busy,used;
static bool read(uint32_t a,void* b,SIZE_T n){SIZE_T got=0;return a&&ReadProcessMemory(GetCurrentProcess(),(void*)(uintptr_t)a,b,n,&got)&&got==n;}
static uint32_t word(uint32_t a){uint32_t v=0;read(a,&v,4);return v;}
static uint32_t frame(){return word(p->logic+0x50);}
static float distance(const float* a,const float* b){float x=a[0]-b[0],y=a[1]-b[1];return sqrtf(x*x+y*y);}
static bool finite_xyz(const float* a){return isfinite(a[0])&&isfinite(a[1])&&isfinite(a[2]);}
static bool world(){return word(0xcd8ce4)==p->logic&&word(p->logic)==0xbeb630&&word(p->owner)==0xc5bce0&&word(p->owner+0x20)==3&&word(p->owner+0x10)==p->player_template&&word(p->owner+0x90)==p->ai&&word(p->ai)==0xc60f60&&word(p->ai+8)==p->owner&&word(p->ai+0x8b0)==p->personality&&word(p->personality+0x18)==p->personality_id;}
static bool actor(){float hp=0;return word(p->thing)==0xc4db60&&word(p->thing+0xdc)==p->object_id&&word(p->thing+0x418)==p->owner&&word(p->thing+4)==p->template_ptr&&word(p->template_ptr+8)==p->type_hash&&word(p->thing+0x374)==p->update&&word(p->update)==0xc48670&&word(p->update+0x24)==0xc48528&&word(p->update+8)==p->thing&&read(word(p->thing+0x33c)+4,&hp,4)&&isfinite(hp)&&hp>0;}
static bool module(){return actor()&&word(p->thing+0x380)==p->stance_module&&word(p->stance_module)==0xc37f90&&word(p->stance_module+8)==p->thing&&word(0xc37f98)==0x71d3f0&&word(p->stance_module+0x38)<=3;}
static bool sample_once(Sample& out){
 memset(&out,0,sizeof(out));if(!actor())return false;uint32_t t=p->thing,u=p->update,m=p->stance_module;
 out.frame=frame();out.thing=t;out.id=word(t+0xdc);out.owner=word(t+0x418);out.template_ptr=word(t+4);out.type_hash=word(out.template_ptr+8);out.update=word(t+0x374);out.update_vtable=word(u);out.update_backref=word(u+8);out.team=word(t+0x414);
 out.stance_module=word(t+0x380);out.stance_vtable=word(m);out.stance_backref=word(m+8);out.stance_data=word(m+4);out.stance=word(m+0x38);
 out.stance_enum_list=word(word(out.stance_data+8));out.stance_enum_count=word(out.stance_enum_list+4);if(out.stance_enum_count>4)return false;if(!read(word(out.stance_enum_list+8),out.stance_enum_entries,out.stance_enum_count*8))return false;
 out.sm=word(u+0x3c);out.sm_owner=word(out.sm+0x24);out.sm_flags=word(out.sm+0x78);out.state=word(out.sm+4);out.state_id=word(out.state+4);out.state_vtable=word(out.state);out.state_owner_sm=word(out.state+0x18);out.path=word(u+0x150);out.source=word(u+0x50);
 if(out.state_id==16||out.state_id==94){out.child_sm=word(out.state+0x20);out.child_sm_vtable=word(out.child_sm);out.child_state=word(out.child_sm+4);out.child_state_id=word(out.child_state+4);out.child_state_vtable=word(out.child_state);out.child_state_owner_sm=word(out.child_state+0x18);}
 out.holder=word(t+0x238);if(!read(t+0x80,out.status_words,28))return false;out.height_flags=word(t+0x48);if(!read(t+0x5c,&out.height,4)||!read(word(t+0x33c)+4,&out.hp,4)||!read(t+0x38,out.xyz,12))return false;
 out.auto_acquire=word(u+0x484);if(out.auto_acquire){uint16_t flags=0;read(out.auto_acquire+0x9e,&flags,2);out.auto_acquire_flags_9e=flags;out.auto_acquire_24=word(out.auto_acquire+0x24);out.auto_acquire_28=word(out.auto_acquire+0x28);out.auto_acquire_2c=word(out.auto_acquire+0x2c);out.auto_acquire_70=word(out.auto_acquire+0x70);}
 return frame()==out.frame&&actor()&&module()&&word(t+0x380)==out.stance_module&&out.owner==p->owner&&out.id==p->object_id&&finite_xyz(out.xyz);
}
static bool sample(Sample& out){Sample first={},second={};if(!sample_once(first)||!sample_once(second)||memcmp(&first,&second,sizeof(first)))return false;out=first;return true;}
static uint32_t emit(uint32_t kind,uint32_t arg=0,uint32_t caller=0,uint32_t self=0,uint32_t source=0,uint32_t result=0,const MoveProof* move=NULL,const Sample* fixed_sample=NULL){
 LONG i=InterlockedIncrement(&p->count)-1;if(i<0||i>=T_CAP){p->overflow=1;p->stop_requested=1;return 0;}Event& e=p->events[i];memset(&e,0,sizeof(e));e.kind=kind;e.tag=tag;e.frame=frame();e.tick=GetTickCount();e.thread=GetCurrentThreadId();e.caller=caller;e.self=self;e.arg=arg;e.source=source;e.result=result;e.stage=p->stage;e.sdk_calls=p->sdk_calls;e.error=p->error;e.explicit_stops=p->explicit_stops;e.private_explicit_stops=p->private_explicit_stops;e.automatic_stop2=p->automatic_stop2;e.private_automatic_stop2=p->private_automatic_stop2;if(fixed_sample)memcpy(&e.sample,fixed_sample,sizeof(*fixed_sample));else sample(e.sample);if(move)memcpy(&e.move,move,sizeof(*move));if(kind==64)e.move.facade_seq=i+1;MemoryBarrier();InterlockedExchange((LONG*)&e.seq,i+1);return i+1;
}
typedef void (__attribute__((thiscall))*Transfer)(void*,void*,uint32_t);static Transfer old_transfer;
typedef void (__attribute__((thiscall))*Member)(void*,void*);static Member old_add,old_remove;
typedef void (__attribute__((thiscall))*Stop)(void*,uint32_t);static Stop old_facade,old_private;
typedef bool (__attribute__((thiscall))*Stance)(void*,uint32_t);static Stance old_stance;
static void __attribute__((fastcall)) transfer_hook(void* self,void*,void* thing,uint32_t to_ai){InterlockedIncrement(&p->active);bool ours=(uintptr_t)thing==p->thing;if(ours)emit(10,to_ai,(uintptr_t)__builtin_return_address(0),(uintptr_t)self);old_transfer(self,thing,to_ai);if(ours)emit(11,to_ai,0,(uintptr_t)self);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) add_hook(void* self,void*,void* thing){InterlockedIncrement(&p->active);bool ours=(uintptr_t)thing==p->thing;if(ours)emit(12,0,(uintptr_t)__builtin_return_address(0),(uintptr_t)self);old_add(self,thing);if(ours)emit(13,0,0,(uintptr_t)self);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) remove_hook(void* self,void*,void* thing){InterlockedIncrement(&p->active);bool ours=(uintptr_t)thing==p->thing;if(ours)emit(14,0,(uintptr_t)__builtin_return_address(0),(uintptr_t)self);old_remove(self,thing);if(ours)emit(15,0,0,(uintptr_t)self);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) facade_hook(void* self,void*,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update+0x24;if(ours){if(source==2&&(tag==2||tag==5))p->automatic_stop2++;emit(30,0,(uintptr_t)__builtin_return_address(0),(uintptr_t)self,source);}old_facade(self,source);if(ours)emit(31,0,0,(uintptr_t)self,source);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) private_hook(void* self,void*,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update;uint32_t caller=(uintptr_t)__builtin_return_address(0);if(ours)emit(32,0,caller,(uintptr_t)self,source);old_private(self,source);if(ours){if(source==1&&(tag==3||tag==4||tag==8)&&caller==0x787791){p->private_explicit_stops++;p->private_stop_frame=frame();}if(source==2&&(tag==2||tag==5))p->private_automatic_stop2++;emit(33,0,caller,(uintptr_t)self,source);}InterlockedDecrement(&p->active);}
static bool __attribute__((fastcall)) stance_hook(void* self,void*,uint32_t value){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->stance_module;if(ours)emit(20,value,(uintptr_t)__builtin_return_address(0),(uintptr_t)self);bool result=old_stance(self,value);if(ours)emit(21,value,0,(uintptr_t)self,0,result);InterlockedDecrement(&p->active);return result;}
static uint32_t sdk(uint32_t,uint32_t);
#include "rally.cpp.inc"
struct Hook{uint32_t a;void* fn;void** original;const char* signature;uint32_t n;BYTE before[24];bool made,enabled;};
static Hook hooks[]={
 {0x838820,(void*)transfer_hook,(void**)&old_transfer,"\x8b\x81\x8c\x00\x00\x00\x85\xc0\x74\x4f\x56\x8b\xb1\x90\x00\x00\x00",17,{},false,false},
 {0x8d8880,(void*)add_hook,(void**)&old_add,"\x83\xec\x24\x56\x8b\x74\x24\x2c\x8b\x46\x04",11,{},false,false},
 {0x8cd630,(void*)remove_hook,(void**)&old_remove,"\x83\xec\x34\x53\x57\x8b\x7c\x24\x40\x8b\x47\x04",12,{},false,false},
 {0x54b0a0,(void*)facade_hook,(void**)&old_facade,"\x83\xec\x5c\x8b\x44\x24\x60\x56\x6a\x01\x50\x8b\xf1",13,{},false,false},
 {0x721ad0,(void*)private_hook,(void**)&old_private,"\x83\xec\x08\x55\x8b\xe9\x8b\x45\x08\x8b\x48\x04",12,{},false,false},
 {0x7640f0,(void*)stance_hook,(void**)&old_stance,"\x83\xec\x14\x53\x8b\xd9\x8b\x43\x08",9,{},false,false},
 {0x571d90,(void*)move_facade_hook,(void**)&old_move_facade,"\x83\xec\x5c\x8b\x44\x24\x64\x56\x6a\x01\x50\x8b\xf1",13,{},false,false},
 {0x76d9d0,(void*)move_hook,(void**)&old_move,"\x56\x8b\xf1\x57\x8b\x7e\x08\x8b\xcf",9,{},false,false}};
static void finish(){if(timer){KillTimer(window,timer);timer=0;}p->stage=5;emit(4);for(unsigned i=0;i<8;i++){Hook& h=hooks[i];if(h.enabled){MH_DisableHook((void*)(uintptr_t)h.a);h.enabled=false;}BYTE b[24]={};if(read(h.a,b,h.n)&&!memcmp(b,h.signature,h.n))p->restore_mask|=1u<<i;}p->phase=p->error?4:3;}
static uint32_t sdk(uint32_t code,uint32_t value=0){p->sdk_calls++;return emit(50,code,0,0,0,value);}
static bool set_stance(uint32_t value,uint32_t which){if(!module())return false;tag=which;p->stance_calls++;sdk(which==2?2:5,value);bool result=((Stance)0x7640f0)((void*)(uintptr_t)p->stance_module,value);tag=0;return result&&module()&&word(p->stance_module+0x38)==value;}
static void stop(uint32_t which){p->stable_samples=0;p->last_sample_frame=0;p->stop_issue_frame=frame();read(p->thing+0x38,p->stopped_xyz,12);tag=which;p->explicit_stops++;sdk(which==3?3:which==8?8:4);((Stop)0x54b0a0)((void*)(uintptr_t)(p->update+0x24),1);tag=0;}
static void transfer(uint32_t to_ai){tag=to_ai?6:1;if(to_ai)p->return_calls++;else p->detach_calls++;sdk(to_ai?6:1);((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->thing,to_ai);tag=0;}
static void cleanup(uint32_t error){if(error&&!p->error)p->error=error;if(p->stage==3||p->stage==4||p->stage==5)return;p->stage=3;p->cleanup_started=frame();stop(4);}
#include "logic.cpp.inc"
#include "scheduler.cpp.inc"
static void install(HWND hwnd){p->callback_thread=GetCurrentThreadId();FILETIME a,b,c,d;window=hwnd;
 if(p->magic!=T_MAGIC||p->version!=5||p->pid!=GetCurrentProcessId()||p->thread!=p->callback_thread||!GetProcessTimes(GetCurrentProcess(),&a,&b,&c,&d)||a.dwLowDateTime!=p->start_low||a.dwHighDateTime!=p->start_high||!world()||!actor()||!module()||used||!p->token||!p->seq){p->error=10;finish();return;}
 for(unsigned i=0;i<8;i++)if(!read(hooks[i].a,hooks[i].before,hooks[i].n)||memcmp(hooks[i].before,hooks[i].signature,hooks[i].n)){p->error=12+i;finish();return;}
 if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCSTR)(uintptr_t)&install,&pin)){p->error=11;finish();return;}
 MH_STATUS status=MH_Initialize();if(status!=MH_OK&&status!=MH_ERROR_ALREADY_INITIALIZED){p->error=20;finish();return;}
 for(unsigned i=0;i<8;i++){Hook& h=hooks[i];if(MH_CreateHook((void*)(uintptr_t)h.a,h.fn,h.original)!=MH_OK){p->error=21;finish();return;}h.made=true;}
 for(unsigned i=0;i<8;i++){if(MH_EnableHook((void*)(uintptr_t)hooks[i].a)!=MH_OK){p->error=22;finish();return;}hooks[i].enabled=true;}
 memcpy(&frozen,p,offsetof(Probe,phase));memcpy(frozen.production_command,p->production_command,80);memcpy(&frozen.rally,&p->rally,32);rally_reset();used=true;last_advance=0xffffffffu;last_pulse=0;has_pulse=busy=false;start_tick=install_tick=GetTickCount();p->pulse_requested=p->pulse_acknowledged=0;p->phase=5;timer=SetTimer(hwnd,0x52535635,T_PULSE_PERIOD_MS,tick);if(!timer){p->error=23;finish();return;}emit(0);advance();
}
extern "C" __declspec(dllexport) LRESULT CALLBACK TacticalReserve5Control(int code,WPARAM wp,LPARAM lp){if(code>=0&&wp==PM_REMOVE&&lp){MSG* msg=(MSG*)lp;if(msg->message==T_PULSE_MESSAGE&&p&&msg->hwnd==window)pulse(msg->wParam,msg->lParam);if(msg->message==T_MESSAGE&&msg->wParam==T_MAGIC&&msg->lParam&&!p){char name[100];snprintf(name,sizeof(name),"Local\\RA3TacticalReserve5_%lu_%u",GetCurrentProcessId(),(uint32_t)msg->lParam);mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);p=mapping?(Probe*)MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Probe)):NULL;if(p)install(msg->hwnd);}}return CallNextHookEx(NULL,code,wp,lp);}
BOOL WINAPI DllMain(HINSTANCE h,DWORD why,LPVOID){if(why==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(h);return TRUE;}
