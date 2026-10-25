#include "observer_shared.h"
#include "MinHook.h"
#include <string.h>
#include <stdio.h>
static ObserverState* state;
static HANDLE mapping;
static const uintptr_t move_address=0x6eff70;
static BYTE before[13];
typedef uintptr_t (__attribute__((thiscall)) *MoveFn)(void*,const float*,int);
static MoveFn original_move;
static HMODULE pinned_module;
static bool read_self(uintptr_t p,void* output,SIZE_T n){SIZE_T got=0;return ReadProcessMemory(GetCurrentProcess(),(void*)p,output,n,&got)&&got==n;}

static uintptr_t __attribute__((fastcall)) observe_move(void* ai,void*,const float* position,int source){
 InterlockedIncrement(&state->active);
 InterlockedIncrement(&state->total_moves);
 if(source==2 && state->state==1){
  InterlockedIncrement(&state->ai_moves);
  LONG index=InterlockedIncrement(&state->event_count)-1;
  if(index<OBS_CAPACITY){
   MoveEvent* event=&state->events[index];
   event->tick=GetTickCount()-state->start_tick;event->thread=GetCurrentThreadId();event->source=source;
   event->ai=(uint32_t)(uintptr_t)ai;event->caller=(uint32_t)(uintptr_t)__builtin_return_address(0);
   read_self((uintptr_t)position,event->xyz,12);
   void* frames[8]={};USHORT count=CaptureStackBackTrace(0,8,frames,NULL);event->stack_count=count;
   for(USHORT i=0;i<count;i++)event->stack[i]=(uint32_t)(uintptr_t)frames[i];
  }
 }
 uintptr_t result=original_move(ai,position,source);
 InterlockedDecrement(&state->active);
 return result;
}

static void stop_observer(){
 if(!state || InterlockedCompareExchange(&state->stop_owner,1,0)!=0)return;
 MH_STATUS status=MH_DisableHook((void*)move_address);
 if(status!=MH_OK && status!=MH_ERROR_DISABLED){state->error=200+(uint32_t)status;InterlockedExchange(&state->state,4);return;}
 BYTE now[sizeof(before)]={};state->restore_verified=read_self(move_address,now,sizeof(now))&&!memcmp(before,now,sizeof(now));
 DWORD started=GetTickCount();while(state->active && GetTickCount()-started<2000)Sleep(1);
 state->stop_tick=GetTickCount();
 // Deliberately DO NOT MH_RemoveHook/Uninitialize: detour and trampoline stay
 // allocated and the DLL is pinned until this test game exits. This remains
 // safe if a suspended/in-flight native call hasn't returned yet.
 InterlockedExchange(&state->state,state->restore_verified && !state->active?2:3);
}
static DWORD WINAPI watchdog(void*){
 while(state && state->state==1 && GetTickCount()-state->start_tick<state->seconds*1000)Sleep(25);
 stop_observer();return 0;
}
static void install_observer(){
 const BYTE expected[]={0x56,0x8b,0xf1,0x8b,0x4e,0x3c,0x8b,0x01,0x8b,0x50,0x38,0xff,0xd2};
 if((uintptr_t)GetModuleHandleW(NULL)!=0x400000 || !read_self(move_address,before,sizeof(before)) || memcmp(before,expected,sizeof(before))){state->error=10;InterlockedExchange(&state->state,4);return;}
 if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCSTR)(uintptr_t)&observe_move,&pinned_module)){state->error=11;InterlockedExchange(&state->state,4);return;}
 MH_STATUS result=MH_Initialize();
 if(result!=MH_OK && result!=MH_ERROR_ALREADY_INITIALIZED){state->error=20+result;InterlockedExchange(&state->state,4);return;}
 result=MH_CreateHook((void*)move_address,(void*)&observe_move,(void**)&original_move);
 if(result!=MH_OK){state->error=40+result;InterlockedExchange(&state->state,4);return;}
 state->start_tick=GetTickCount();InterlockedExchange(&state->state,1);
 result=MH_EnableHook((void*)move_address);
 if(result!=MH_OK){state->error=60+result;InterlockedExchange(&state->state,4);return;}
 HANDLE worker=CreateThread(NULL,0,watchdog,NULL,0,NULL);
 if(!worker){state->error=80;stop_observer();}else CloseHandle(worker);
}
extern "C" __declspec(dllexport) LRESULT CALLBACK ObserverControl(int code,WPARAM wp,LPARAM lp){
 if(code>=0 && wp==PM_REMOVE && lp && ((MSG*)lp)->message==OBS_MESSAGE && ((MSG*)lp)->wParam==OBS_MAGIC){
  if(!state){
   char name[80];snprintf(name,sizeof(name),"Local\\RA3NativeMoveObserver_%lu",GetCurrentProcessId());
   mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);
   if(mapping)state=(ObserverState*)MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(ObserverState));
  }
  if(state && state->magic==OBS_MAGIC && state->pid==GetCurrentProcessId()){
   state->callback_thread=GetCurrentThreadId();
   LONG request=state->request;
   if(request==1 && state->ack==0)install_observer();
   else if(request==2)stop_observer();
   InterlockedExchange(&state->ack,request);
  }
 }
 return CallNextHookEx(NULL,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID){if(reason==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(module);return TRUE;}
