#include "shared.h"
#include <stdio.h>
#include <string.h>
static Shared* p;static HANDLE mapping;static HMODULE pin;
static bool read(uint32_t address,void* out,SIZE_T n){SIZE_T got=0;return ReadProcessMemory(GetCurrentProcess(),(void*)(uintptr_t)address,out,n,&got)&&got==n;}
static uint32_t word(uint32_t address){uint32_t result=0;read(address,&result,4);return result;}
static bool bytes(uint32_t address,const char* value,SIZE_T n){BYTE buffer[32];return n<=sizeof(buffer)&&read(address,buffer,n)&&!memcmp(buffer,value,n);}
static bool unique_owner(){
 uint32_t manager=word(0xcdd1a0);if(!manager||word(manager)!=0xc07ab8)return false;
 unsigned matches=0;bool ours=false;
 for(unsigned i=0;i<20;i++){uint32_t player=word(manager+0x48+4*i);if(!player)continue;
  uint32_t ai=word(player+0x90),personality=ai?word(ai+0x8b0):0;
  if(personality&&word(personality+0x18)==p->personality_id){matches++;ours|=player==p->owner;}
 }
 return matches==1&&ours;
}
static bool identity(){
 FILETIME a,b,c,d;
 return GetCurrentProcessId()==p->pid&&GetCurrentThreadId()==p->thread&&GetProcessTimes(GetCurrentProcess(),&a,&b,&c,&d)&&a.dwLowDateTime==p->start_low&&a.dwHighDateTime==p->start_high&&
 word(0xcdd190)==p->engine&&p->engine&&word(p->owner)==0xc5bce0&&word(p->owner+0x20)==3&&word(p->owner+0x10)==p->player_template&&word(p->owner+0x90)==p->ai&&
 p->personality_id==0x799613e0&&word(p->ai)==0xc60f60&&word(p->ai+8)==p->owner&&word(p->ai+0x8a8)==p->owner&&word(p->ai+0x8b0)==p->personality&&word(p->personality+0x18)==p->personality_id&&unique_owner();
}
static bool signatures(){
 return (uintptr_t)GetModuleHandleW(NULL)==0x400000&&
 bytes(0x58b240,"\x53\x55\x8b\x6c\x24\x0c\x83\x7d\x08\x00\x56\x57\x8b\xf1",14)&&
 bytes(0x58b2a9,"\x8b\x45\x10\x83\x78\x08\x00\x0f\x95\xc0\x88\x07",12)&&
 bytes(0x573b10,"\x83\xec\x10\x56\x57\x8b\xf9\x8d\x87\x60\x7d\x01\x00",13)&&
 bytes(0x574c80,"\x51\x53\x55\x56\x57\x8b\xf9\x33\xed\x39\x6f\x08",12)&&
 bytes(0x574d70,"\x53\x56\x57\x8b\xf9\x33\xdb\x39\x5f\x08",10)&&
 bytes(0x4cc910,"\x8b\x44\x24\x04",4);
}
typedef void (__attribute__((thiscall))*StringCtor)(void*,const char*);
typedef void* (__attribute__((thiscall))*FlagGet)(void*,uint32_t);
typedef void (__attribute__((thiscall))*ActionInit)(void*,uint32_t);
typedef void (__attribute__((thiscall))*ActionDestroy)(void*);
typedef void (__attribute__((thiscall))*FlagSet)(void*,void*,uint32_t);
static uint32_t get_flag(){
 uint32_t native_string=0;
 ((StringCtor)0x4cc910)(&native_string,FLAG_NAME);
 // Native getter takes the four-byte string by value and destroys that copy.
 // Ownership is transferred; do not destroy the stale local wrapper again.
 void* value=((FlagGet)0x573b10)((void*)(uintptr_t)p->engine,native_string);
 if(!value)return 2;
 BYTE result=0;if(!read((uintptr_t)value,&result,1)||result>1)return 3;
 return result;
}
static bool set_flag(bool value){
 // Use normal ScriptAction parameter construction/destruction, matching the
 // common-script SET_FLAG branch, rather than a bool memory write or Lua ack.
 uint32_t metadata=p->engine+0x48+0x80;
 char name[9]={};
 if(word(metadata+0x48)!=2||word(metadata+0x4c)!=5||word(metadata+0x50)!=8||!read(word(metadata+0xc),name,9)||memcmp(name,"SET_FLAG",9))return false;
 alignas(4) BYTE action[0x48]={};
 *(uint32_t*)action=0xbef87c;action[0x41]=1;
 ((ActionInit)0x574c80)(action,1);
 uint32_t count=*(uint32_t*)(action+8),first=*(uint32_t*)(action+0xc),second=*(uint32_t*)(action+0x10);
 bool valid=count==2&&first&&second&&word(first)==5&&word(second)==8;
 if(valid){
  ((StringCtor)0x4cc910)((void*)(uintptr_t)(first+0x10),FLAG_NAME);
  *(uint32_t*)(uintptr_t)(second+8)=value?1:0; // Local newly allocated ScriptParam, never the flag table.
  p->attempted++;
  ((FlagSet)0x58b240)((void*)(uintptr_t)p->engine,action,0);
 }
 ((ActionDestroy)0x574d70)(action);
 return valid;
}
static void command(){
 LONG request=p->request;
 if(request<1||request>3||request<=p->ack||p->phase==2)return;
 InterlockedIncrement(&p->active);
 p->callback_thread=GetCurrentThreadId();
 if(!identity()||!signatures()){p->error=10;InterlockedExchange(&p->phase,4);InterlockedDecrement(&p->active);return;}
 uint32_t game=word(0xcd8ce4),frame=word(game+0x50);
 if(!game||!frame||frame<p->last_frame){p->error=11;InterlockedExchange(&p->phase,4);InterlockedDecrement(&p->active);return;}
 p->last_frame=frame;
 if(!p->start_frame)p->start_frame=frame;
 if(request==2&&(p->ack!=1||p->phase!=1)){p->error=12;InterlockedExchange(&p->phase,4);InterlockedDecrement(&p->active);return;}
 if(request==2&&word(game+0x15c)){p->error=17;InterlockedExchange(&p->phase,4);InterlockedDecrement(&p->active);return;}
 p->before=get_flag();
 bool wanted=request==2;
 if(!set_flag(wanted)){p->error=13;InterlockedExchange(&p->phase,4);InterlockedDecrement(&p->active);return;}
 p->after=get_flag();
 if(p->after!=(uint32_t)wanted){p->error=14;InterlockedExchange(&p->phase,4);InterlockedDecrement(&p->active);return;}
 p->cleanup_verified=request==3&&p->after==0;
 InterlockedExchange(&p->ack,request);
 InterlockedExchange(&p->phase,request==3?2:1);
 InterlockedDecrement(&p->active);
}
static DWORD WINAPI watchdog(void*){
 while(p->phase!=2&&GetTickCount()-p->start_tick<LIFETIME_MS)Sleep(25);
 if(p->phase!=2){p->watchdog_requested=1;InterlockedExchange(&p->request,3);
  // Only the game thread may call native APIs. The worker merely posts a stop.
  for(int i=0;i<100&&p->phase!=2;i++){PostThreadMessageA(p->thread,MESSAGE,MAGIC,0);Sleep(100);}
 }
 return 0;
}
extern "C" __declspec(dllexport) LRESULT CALLBACK MacroFlagControl(int code,WPARAM wp,LPARAM lp){
 if(code>=0&&wp==PM_REMOVE&&lp&&((MSG*)lp)->message==MESSAGE&&((MSG*)lp)->wParam==MAGIC){
  if(!p){char name[80];snprintf(name,sizeof(name),"%s%lu",MAPPING_PREFIX,GetCurrentProcessId());mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);
   if(mapping)p=(Shared*)MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Shared));
   if(p&&(p->magic!=MAGIC||p->version!=1||p->pid!=GetCurrentProcessId()))p=NULL;
   if(p){
    if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCSTR)(uintptr_t)&command,&pin)){p->error=15;p->phase=4;}
    else{p->start_tick=GetTickCount();HANDLE t=CreateThread(NULL,0,watchdog,NULL,0,NULL);if(t)CloseHandle(t);else{p->error=16;p->phase=4;}}
   }
  }
  if(p&&p->error!=15&&p->error!=16)command();
 }
 return CallNextHookEx(NULL,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID){if(reason==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(module);return TRUE;}
