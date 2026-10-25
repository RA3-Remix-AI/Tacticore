#include "shared.h"
#include "MinHook.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
static Tactical* p;static HANDLE mapping;static HMODULE pin;static HWND window;static UINT_PTR timer;static uint32_t tag,start_tick,last_seq,used_count;static uint32_t used_commands[128][4],used_tasks[128][4],used_tokens[128];
static bool read(uint32_t a,void* b,SIZE_T n){SIZE_T got=0;return ReadProcessMemory(GetCurrentProcess(),(void*)(uintptr_t)a,b,n,&got)&&got==n;}
static uint32_t word(uint32_t a){uint32_t v=0;read(a,&v,4);return v;}
static uint32_t frame(){return word(p->logic+0x50);}static bool paused(){return word(p->logic+0x15c)!=0;}
static bool identity(){return word(0xcd8ce4)==p->logic&&word(p->logic)==0xbeb630&&word(p->owner)==0xc5bce0&&word(p->owner+0x20)==3&&word(p->owner+0x10)==p->player_template&&word(p->owner+0x90)==p->ai&&word(p->ai)==0xc60f60&&word(p->ai+8)==p->owner&&word(p->ai+0x8b0)==p->personality&&word(p->personality+0x18)==p->personality_id;}
static bool unit(){float hp=0;return word(p->unit)==0xc4db60&&word(p->unit+0xdc)==p->object_id&&word(p->unit+0x418)==p->owner&&word(word(p->unit+4)+8)==p->type_hash&&word(p->unit+0x374)==p->update&&word(p->update+8)==p->unit&&read(word(p->unit+0x33c)+4,&hp,4)&&isfinite(hp)&&hp>0;}
static void event(uint32_t kind,uint32_t arg=0,uint32_t caller=0){LONG i=InterlockedIncrement(&p->count)-1;if(i>=T_CAP){p->overflow=1;return;}Event e={};e.seq=i+1;e.kind=kind;e.tag=tag;e.frame=frame();e.tick=GetTickCount();e.thread=GetCurrentThreadId();e.caller=caller;e.team=word(p->unit+0x414);e.owner=word(p->unit+0x418);e.source=word(p->update+0x50);e.arg=arg;read(p->unit+0x38,&e.x,12);e.seq=0;p->events[i]=e;MemoryBarrier();InterlockedExchange((LONG*)&p->events[i].seq,i+1);}
typedef void (__attribute__((thiscall))*Move)(void*,float*,uint32_t);typedef void (__attribute__((thiscall))*Attack)(void*,void*,uint32_t,uint32_t);typedef void (__attribute__((thiscall))*Transfer)(void*,void*,uint32_t);typedef void (__attribute__((thiscall))*Member)(void*,void*);
static Move old_move;static Attack old_attack;static Transfer old_transfer;static Member old_add,old_remove;
static void __attribute__((fastcall)) move_hook(void* self,void*,float* xyz,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update;if(ours){if(!tag)p->native_move++;event(10,source,(uintptr_t)__builtin_return_address(0));}old_move(self,xyz,source);if(ours)event(11,source);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) attack_hook(void* self,void*,void* target,uint32_t shots,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update;if(ours){if(!tag)p->native_attack++;event(12,source,(uintptr_t)__builtin_return_address(0));}old_attack(self,target,shots,source);if(ours)event(13,source);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) transfer_hook(void* self,void*,void* target,uint32_t to_ai){InterlockedIncrement(&p->active);bool ours=(uintptr_t)target==p->unit;if(ours)event(14,to_ai,(uintptr_t)__builtin_return_address(0));old_transfer(self,target,to_ai);if(ours)event(15,to_ai);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) add_hook(void* self,void*,void* target){InterlockedIncrement(&p->active);bool ours=(uintptr_t)target==p->unit;if(ours){if(!tag)p->native_add++;event(16,(uintptr_t)self,(uintptr_t)__builtin_return_address(0));}old_add(self,target);if(ours)event(17,(uintptr_t)self);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) remove_hook(void* self,void*,void* target){InterlockedIncrement(&p->active);bool ours=(uintptr_t)target==p->unit;if(ours){if(!tag)p->native_remove++;event(18,(uintptr_t)self,(uintptr_t)__builtin_return_address(0));}old_remove(self,target);if(ours)event(19,(uintptr_t)self);InterlockedDecrement(&p->active);}
struct Hook {uint32_t a;void* fn;void** original;const char* signature;uint32_t n;BYTE before[24];bool made,enabled;};
static Hook hooks[]={
{0x6eff70,(void*)move_hook,(void**)&old_move,"\x56\x8b\xf1\x8b\x4e\x3c\x8b\x01\x8b\x50\x38\xff\xd2",13,{},false,false},
{0x76e690,(void*)attack_hook,(void**)&old_attack,"\x83\x7c\x24\x04\x00\x55\x56\x8b\xf1\x8b\x6e\x08",12,{},false,false},
{0x838820,(void*)transfer_hook,(void**)&old_transfer,"\x8b\x81\x8c\x00\x00\x00\x85\xc0\x74\x4f\x56\x8b\xb1\x90\x00\x00\x00",17,{},false,false},
{0x8d8880,(void*)add_hook,(void**)&old_add,"\x83\xec\x24\x56\x8b\x74\x24\x2c\x8b\x46\x04",11,{},false,false},
{0x8cd630,(void*)remove_hook,(void**)&old_remove,"\x83\xec\x34\x53\x57\x8b\x7c\x24\x40\x8b\x47\x04",12,{},false,false}};
static void finish(){if(timer){KillTimer(window,timer);timer=0;}event(4);for(unsigned i=0;i<5;i++){Hook& h=hooks[i];if(h.enabled){MH_DisableHook((void*)(uintptr_t)h.a);h.enabled=false;}BYTE b[24];if(h.made&&read(h.a,b,h.n)&&!memcmp(b,h.before,h.n))p->restore_mask|=1u<<i;}p->phase=p->error?4:3;}
static void CALLBACK tick(HWND,UINT,UINT_PTR,DWORD){
 if(GetCurrentThreadId()!=p->thread){p->error=30;return;}if(!identity()){p->error=31;p->lifecycle_fail++;finish();return;}
 if(!unit()){p->error=32;p->lifecycle_fail++;finish();return;}
 if(paused()){p->paused_samples++;if(p->phase==1&&(p->stop_requested||GetTickCount()-start_tick>60000))p->return_pending=1;return;}
 uint32_t now=frame();
 if(p->phase==5){
  if(p->stop_requested||GetTickCount()-start_tick>60000){p->error=33;finish();return;}
  float xyz[3];read(p->unit+0x38,xyz,12);float dx=xyz[0]-p->target[0],dy=xyz[1]-p->target[1];
  if(dx*dx+dy*dy<400||dx*dx+dy*dy>14400||fabsf(xyz[2]-p->target[2])>2||word(p->owner+0xac)!=p->default_team||word(word(p->owner+0x8c)+0x10)!=p->script_team||word(word(p->default_team+4)+8)!=p->owner||word(word(p->script_team+4)+8)!=p->owner){p->error=34;finish();return;}
  p->phase=6;p->original_team=word(p->unit+0x414);p->issued_frame=now;tag=1;p->detach_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->unit,0);event(1);tag=0;
  if(!unit()||word(p->unit+0x414)!=p->script_team){p->error=35;p->phase=1;p->return_pending=1;return;}
  if(paused()){p->phase=1;p->return_pending=1;return;}tag=2;p->move_calls++;((Move)0x6eff70)((void*)(uintptr_t)p->update,p->target,0);event(2);tag=0;p->phase=1;return;
 }
 event(3);if(p->phase==1){float xyz[3];read(p->unit+0x38,xyz,12);float dx=xyz[0]-p->target[0],dy=xyz[1]-p->target[1];if(dx*dx+dy*dy<=225)p->arrival_samples++;
  if(p->stop_requested||p->return_pending||p->arrival_samples>=3||now-p->issued_frame>=p->lease_frames||GetTickCount()-start_tick>60000){
   if(p->native_add){p->error=36;finish();return;}
   tag=3;p->return_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->unit,1);event(5);tag=0;p->returned_frame=now;p->return_pending=0;p->return_verified=unit()&&word(p->unit+0x414)==p->default_team;p->phase=2;if(!p->return_verified){p->error=37;finish();}
  }
 }else if(p->phase==2&&now-p->returned_frame>=p->post_frames)finish();
}
static void install(HWND hwnd){p->callback_thread=GetCurrentThreadId();FILETIME a,b,c,d;
 if(p->magic!=T_MAGIC||p->version!=2||GetCurrentProcessId()!=p->pid||p->thread!=p->callback_thread||!GetProcessTimes(GetCurrentProcess(),&a,&b,&c,&d)||a.dwLowDateTime!=p->start_low||a.dwHighDateTime!=p->start_high||!identity()||!unit()||(p->type_hash!=0x19ab11af&&p->type_hash!=0x2c358c61)||p->lease_frames>180||p->lease_frames<30||p->post_frames<30||p->post_frames>180){p->error=10;p->phase=4;return;}
 if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCSTR)(uintptr_t)&install,&pin)){p->error=11;p->phase=4;return;}
 for(unsigned i=0;i<5;i++)if(!read(hooks[i].a,hooks[i].before,hooks[i].n)||memcmp(hooks[i].before,hooks[i].signature,hooks[i].n)){p->error=12+i;p->phase=4;return;}
 if(used_count>=128||!p->token||p->seq<=last_seq){p->error=40;p->restore_mask=31;p->phase=4;return;}for(unsigned i=0;i<used_count;i++)if(used_tokens[i]==p->token||!memcmp(used_commands[i],p->command,16)||!memcmp(used_tasks[i],p->task,16)){p->error=41;p->restore_mask=31;p->phase=4;return;}uint32_t nonzero_command=0,nonzero_task=0;for(unsigned i=0;i<4;i++){nonzero_command|=p->command[i];nonzero_task|=p->task[i];}if(!nonzero_command||!nonzero_task){p->error=42;p->restore_mask=31;p->phase=4;return;}memcpy(used_commands[used_count],p->command,16);memcpy(used_tasks[used_count],p->task,16);used_tokens[used_count++]=p->token;last_seq=p->seq;
 MH_STATUS s=MH_Initialize();if(s!=MH_OK&&s!=MH_ERROR_ALREADY_INITIALIZED){p->error=20;p->phase=4;return;}
 for(unsigned i=0;i<5;i++){Hook& h=hooks[i];if(!h.made&&MH_CreateHook((void*)(uintptr_t)h.a,h.fn,h.original)!=MH_OK){p->error=21;finish();return;}h.made=true;}
 for(unsigned i=0;i<5;i++){Hook& h=hooks[i];if(MH_EnableHook((void*)(uintptr_t)h.a)!=MH_OK){p->error=22;finish();return;}h.enabled=true;}
 p->phase=5;window=hwnd;start_tick=GetTickCount();timer=SetTimer(window,0x52413374,100,tick);if(!timer){p->error=23;finish();return;}event(0);
}
extern "C" __declspec(dllexport) LRESULT CALLBACK TacticalReusableControl(int code,WPARAM wp,LPARAM lp){
 if(code>=0&&wp==PM_REMOVE&&lp&&((MSG*)lp)->message==T_MESSAGE&&((MSG*)lp)->wParam==T_MAGIC){
  MSG* msg=(MSG*)lp;uint32_t token=(uint32_t)msg->lParam;
  if(token&&(!p||((p->phase==3||p->phase==4)&&p->restore_mask==31&&!p->active&&!timer))){
   char name[100];snprintf(name,sizeof(name),"Local\\RA3TacticalReusable_%lu_%u",GetCurrentProcessId(),token);HANDLE next_mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);Tactical* next=next_mapping?(Tactical*)MapViewOfFile(next_mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Tactical)):NULL;
   if(next&&next->token==token&&next->pid==GetCurrentProcessId()&&next->magic==T_MAGIC){if(p)UnmapViewOfFile(p);if(mapping)CloseHandle(mapping);p=next;mapping=next_mapping;tag=0;install(msg->hwnd);}else{if(next)UnmapViewOfFile(next);if(next_mapping)CloseHandle(next_mapping);}
  }
 }
 return CallNextHookEx(NULL,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE h,DWORD why,LPVOID){if(why==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(h);return TRUE;}
