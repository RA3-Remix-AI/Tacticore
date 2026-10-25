#include "production_shared.h"
#include "MinHook.h"
#include <string.h>
#include <stdio.h>
static ObserverState* state;static HANDLE mapping;static HMODULE pinned;
static const uintptr_t target_address=0x723f50;
static BYTE before[19];
typedef uintptr_t (__attribute__((thiscall)) *BuildFn)(void*,void*,uint32_t,void*,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t);
static BuildFn original_build;
static bool read(uintptr_t p,void* output,SIZE_T n){SIZE_T got=0;return ReadProcessMemory(GetCurrentProcess(),(void*)p,output,n,&got)&&got==n;}
static uint32_t word(uintptr_t p){uint32_t out=0;read(p,&out,4);return out;}
static uintptr_t __attribute__((fastcall)) observe_build(void* iface,void*,void* tmpl,uint32_t a2,void* a3,uint32_t a4,uint32_t a5,uint32_t a6,uint32_t a7,uint32_t a8){
 InterlockedIncrement(&state->active);InterlockedIncrement(&state->total_calls);
 BuildEvent* event=NULL;
 if(state->state==1){LONG index=InterlockedIncrement(&state->event_count)-1;if(index<OBS_CAPACITY){
  event=&state->events[index];event->tick=GetTickCount()-state->start_tick;event->thread=GetCurrentThreadId();event->interface_address=(uintptr_t)iface;event->factory=word((uintptr_t)iface-0x1c);event->owner=word(event->factory+0x418);event->template_address=(uintptr_t)tmpl;event->template_hash=word((uintptr_t)tmpl+8);event->caller=(uintptr_t)__builtin_return_address(0);
  uint32_t args[]={a2,(uint32_t)(uintptr_t)a3,a4,a5,a6,a7,a8};memcpy(event->args,args,sizeof(args));event->queue_before=word((uintptr_t)iface+0x10);
  void* frames[8]={};event->stack_count=CaptureStackBackTrace(0,8,frames,NULL);for(uint32_t i=0;i<event->stack_count;i++)event->stack[i]=(uintptr_t)frames[i];
 }}
 uintptr_t result=original_build(iface,tmpl,a2,a3,a4,a5,a6,a7,a8);
 if(event){event->return_value=result;event->queue_after=word((uintptr_t)iface+0x10);uint32_t node=event->queue_after;for(int i=0;node&&i<64;i++){
  if(word(node+0xc)==1&&word(node+0x10)==(uintptr_t)tmpl&&word(node+0x18)==result){event->matched_node=node;event->node_cost=word(node+0x30);break;}uint32_t next=word(node+0x54);if(next==node)break;node=next;
 }}
 InterlockedDecrement(&state->active);return result;
}
static void stop(){
 if(!state||InterlockedCompareExchange(&state->stop_owner,1,0)!=0)return;
 MH_STATUS result=MH_DisableHook((void*)target_address);if(result!=MH_OK&&result!=MH_ERROR_DISABLED){state->error=200+result;InterlockedExchange(&state->state,4);return;}
 BYTE current[sizeof(before)]={};state->restore_verified=read(target_address,current,sizeof(current))&&!memcmp(before,current,sizeof(before));
 DWORD began=GetTickCount();while(state->active&&GetTickCount()-began<2000)Sleep(1);state->stop_tick=GetTickCount();
 // Pinned DLL and trampoline intentionally retained until test process exits.
 InterlockedExchange(&state->state,state->restore_verified&&!state->active?2:3);
}
static DWORD WINAPI watchdog(void*){while(state&&state->state==1&&GetTickCount()-state->start_tick<state->seconds*1000)Sleep(25);stop();return 0;}
static void install(){
 const BYTE expected[]={0x81,0xec,0xa8,0,0,0,0x53,0x8b,0xd9,0x8b,0x43,0xdc,0x8b,0x50,0x58,0x55,0x8d,0x6b,0xdc};
 if((uintptr_t)GetModuleHandleW(NULL)!=0x400000||!read(target_address,before,sizeof(before))||memcmp(before,expected,sizeof(before))){state->error=10;InterlockedExchange(&state->state,4);return;}
 if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCSTR)(uintptr_t)&observe_build,&pinned)){state->error=11;InterlockedExchange(&state->state,4);return;}
 MH_STATUS result=MH_Initialize();if(result!=MH_OK&&result!=MH_ERROR_ALREADY_INITIALIZED){state->error=20+result;InterlockedExchange(&state->state,4);return;}
 result=MH_CreateHook((void*)target_address,(void*)&observe_build,(void**)&original_build);if(result!=MH_OK){state->error=40+result;InterlockedExchange(&state->state,4);return;}
 state->start_tick=GetTickCount();InterlockedExchange(&state->state,1);result=MH_EnableHook((void*)target_address);if(result!=MH_OK){state->error=60+result;InterlockedExchange(&state->state,4);return;}
 HANDLE worker=CreateThread(NULL,0,watchdog,NULL,0,NULL);if(!worker){state->error=80;stop();}else CloseHandle(worker);
}
extern "C" __declspec(dllexport) LRESULT CALLBACK TacticalThreadEvidenceControl(int code,WPARAM wp,LPARAM lp){
 if(code>=0&&wp==PM_REMOVE&&lp&&((MSG*)lp)->message==OBS_MESSAGE&&((MSG*)lp)->wParam==OBS_MAGIC){
  if(!state){char name[80];snprintf(name,sizeof(name),"Local\\RA3TacticalThreadEvidence_%lu",GetCurrentProcessId());mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);if(mapping)state=(ObserverState*)MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(ObserverState));}
  if(state&&state->magic==OBS_MAGIC&&state->pid==GetCurrentProcessId()){state->callback_thread=GetCurrentThreadId();LONG request=state->request;if(request==1&&state->ack==0)install();else if(request==2)stop();InterlockedExchange(&state->ack,request);}
 }
 return CallNextHookEx(NULL,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID){if(reason==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(instance);return TRUE;}
