#include "production_shared.h"
#include "MinHook.h"
#include <string.h>
#include <stdio.h>
static ObserverState* state;static HANDLE mapping;static HMODULE pinned;
static const uintptr_t target_address=0x764e20;
static BYTE before[16];
typedef void (__attribute__((thiscall)) *BuildFn)(void*,void*);
static BuildFn original_build;
static bool read(uintptr_t p,void* output,SIZE_T n){SIZE_T got=0;return ReadProcessMemory(GetCurrentProcess(),(void*)p,output,n,&got)&&got==n;}
static uint32_t word(uintptr_t p){uint32_t out=0;read(p,&out,4);return out;}
static void __attribute__((fastcall)) observe_build(void* self,void*,void* info){
 InterlockedIncrement(&state->active);InterlockedIncrement(&state->total_calls);BuildEvent* event=NULL;uint32_t body=(uintptr_t)self,thing=word(body-8),players=word(0xce8c9c),owner=word(players+0x30+3*4);
 if(state->state==1&&word(body)==0xc37fe8&&word(thing)==0xc4db60&&word(thing+0x418)==owner&&word(owner)==0xc5bce0&&word(owner+0x20)==3&&word(thing+0x33c)==body){LONG index=InterlockedIncrement(&state->event_count)-1;if(index<OBS_CAPACITY){event=&state->events[index];event->tick=GetTickCount()-state->start_tick;event->frame=word(word(0xcd8ce4)+0x50);event->thread=GetCurrentThreadId();event->body=body;event->thing=thing;event->object_id=word(thing+0xdc);event->owner=owner;event->source_id=word((uintptr_t)info+8);event->caller=(uintptr_t)__builtin_return_address(0);event->info=(uintptr_t)info;event->info_kind=word((uintptr_t)info+0x1c);read(body+4,&event->before,4);}}
 original_build(self,info);
 if(event){read(body+4,&event->after,4);read((uintptr_t)info+0x8c,&event->calculated,4);read((uintptr_t)info+0x90,&event->reported,4);MemoryBarrier();event->complete=1;}
 InterlockedDecrement(&state->active);
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
 const BYTE expected[]={0x83,0xec,0x14,0x55,0x57,0x8b,0xf9,0x8b,0x47,0xf0,0x8b,0x50,0x64,0x8d,0x4f,0xf0};
 if((uintptr_t)GetModuleHandleW(NULL)!=0x400000||!read(target_address,before,sizeof(before))||memcmp(before,expected,sizeof(before))){state->error=10;InterlockedExchange(&state->state,4);return;}
 if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCSTR)(uintptr_t)&observe_build,&pinned)){state->error=11;InterlockedExchange(&state->state,4);return;}
 MH_STATUS result=MH_Initialize();if(result!=MH_OK&&result!=MH_ERROR_ALREADY_INITIALIZED){state->error=20+result;InterlockedExchange(&state->state,4);return;}
 result=MH_CreateHook((void*)target_address,(void*)&observe_build,(void**)&original_build);if(result!=MH_OK){state->error=40+result;InterlockedExchange(&state->state,4);return;}
 state->start_tick=GetTickCount();InterlockedExchange(&state->state,1);result=MH_EnableHook((void*)target_address);if(result!=MH_OK){state->error=60+result;InterlockedExchange(&state->state,4);return;}
 HANDLE worker=CreateThread(NULL,0,watchdog,NULL,0,NULL);if(!worker){state->error=80;stop();}else CloseHandle(worker);
}
extern "C" __declspec(dllexport) LRESULT CALLBACK OwnDamageObserverControl(int code,WPARAM wp,LPARAM lp){
 if(code>=0&&wp==PM_REMOVE&&lp&&((MSG*)lp)->message==OBS_MESSAGE&&((MSG*)lp)->wParam==OBS_MAGIC){
  if(!state){char name[80];snprintf(name,sizeof(name),"Local\\RA3OwnDamageObserver_%lu",GetCurrentProcessId());mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);if(mapping)state=(ObserverState*)MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(ObserverState));}
  if(state&&state->magic==OBS_MAGIC&&state->pid==GetCurrentProcessId()){state->callback_thread=GetCurrentThreadId();LONG request=state->request;if(request==1&&state->ack==0)install();else if(request==2)stop();InterlockedExchange(&state->ack,request);}
 }
 return CallNextHookEx(NULL,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID){if(reason==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(instance);return TRUE;}
