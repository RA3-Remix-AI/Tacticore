#include "shared.h"
#include <stdio.h>
#include <string.h>
static Shared* p;static HANDLE mapping;static HMODULE pin;static HHOOK owned_hook;
static HANDLE policy_lease;
extern "C" __declspec(dllexport) LRESULT CALLBACK MacroPolicyControl(int,WPARAM,LPARAM);
static bool read(uint32_t address,void* out,SIZE_T n){SIZE_T got=0;return ReadProcessMemory(GetCurrentProcess(),(void*)(uintptr_t)address,out,n,&got)&&got==n;}
static uint32_t word(uint32_t address){uint32_t result=0;read(address,&result,4);return result;}
static bool bytes(uint32_t address,const char* value,SIZE_T n){BYTE buffer[32];return n<=sizeof(buffer)&&read(address,buffer,n)&&!memcmp(buffer,value,n);}
static bool unique_owner(){
 uint32_t manager=word(0xcdd1a0);if(!manager||word(manager)!=0xc07ab8)return false;
 unsigned matches=0;bool ours=false;
 for(unsigned i=0;i<20;i++){
  uint32_t player=word(manager+0x48+4*i);if(!player)continue;
  uint32_t ai=word(player+0x90),personality=ai?word(ai+0x8b0):0;
  if(personality&&word(personality+0x18)==PERSONALITY_ID){matches++;ours|=player==p->owner;}
 }
 return matches==1&&ours;
}
static bool identity(){
 FILETIME a,b,c,d;
 return GetCurrentProcessId()==p->pid&&GetCurrentThreadId()==p->thread&&GetProcessTimes(GetCurrentProcess(),&a,&b,&c,&d)&&
 a.dwLowDateTime==p->start_low&&a.dwHighDateTime==p->start_high&&word(0xcdd190)==p->engine&&p->engine&&
 word(p->owner)==0xc5bce0&&word(p->owner+0x20)==PLAYER_SLOT&&word(p->owner+0x10)==p->player_template&&word(p->owner+0x90)==p->ai&&
 p->personality_id==PERSONALITY_ID&&word(p->ai)==0xc60f60&&word(p->ai+8)==p->owner&&word(p->ai+0x8a8)==p->owner&&
 word(p->ai+0x8b0)==p->personality&&word(p->personality+0x18)==PERSONALITY_ID&&unique_owner();
}
static bool signatures(){
 return (uintptr_t)GetModuleHandleW(NULL)==0x400000&&
 bytes(0x58b240,"\x53\x55\x8b\x6c\x24\x0c\x83\x7d\x08\x00\x56\x57\x8b\xf1",14)&&
 bytes(0x58b2a9,"\x8b\x45\x10\x83\x78\x08\x00\x0f\x95\xc0\x88\x07",12)&&
 bytes(0x573b10,"\x83\xec\x10\x56\x57\x8b\xf9\x8d\x87\x60\x7d\x01\x00",13)&&
 bytes(0x574c80,"\x51\x53\x55\x56\x57\x8b\xf9\x33\xed\x39\x6f\x08",12)&&
 bytes(0x574d70,"\x53\x56\x57\x8b\xf9\x33\xdb\x39\x5f\x08",10)&&bytes(0x4cc910,"\x8b\x44\x24\x04",4);
}
typedef void (__attribute__((thiscall))*StringCtor)(void*,const char*);
typedef void* (__attribute__((thiscall))*FlagGet)(void*,uint32_t);
typedef void (__attribute__((thiscall))*ActionInit)(void*,uint32_t);
typedef void (__attribute__((thiscall))*ActionDestroy)(void*);
typedef void (__attribute__((thiscall))*FlagSet)(void*,void*,uint32_t);
static uint32_t get_flag(unsigned index){
 uint32_t native_string=0;((StringCtor)0x4cc910)(&native_string,FLAG_NAMES[index]);
 void* value=((FlagGet)0x573b10)((void*)(uintptr_t)p->engine,native_string);
 if(!value)return 2;
 BYTE result=0;if(!read((uintptr_t)value,&result,1)||result>1)return 3;
 return result;
}
static bool set_flag(unsigned index,bool value){
 uint32_t metadata=p->engine+0x48+0x80;char name[9]={};
 if(word(metadata+0x48)!=2||word(metadata+0x4c)!=5||word(metadata+0x50)!=8||!read(word(metadata+0xc),name,9)||memcmp(name,"SET_FLAG",9))return false;
 alignas(4) BYTE action[0x48]={};*(uint32_t*)action=0xbef87c;action[0x41]=1;
 ((ActionInit)0x574c80)(action,1);
 uint32_t count=*(uint32_t*)(action+8),first=*(uint32_t*)(action+0xc),second=*(uint32_t*)(action+0x10);
 bool valid=count==2&&first&&second&&word(first)==5&&word(second)==8;
 if(valid){
  ((StringCtor)0x4cc910)((void*)(uintptr_t)(first+0x10),FLAG_NAMES[index]);
  *(uint32_t*)(uintptr_t)(second+8)=value?1:0;p->attempted++;
  ((FlagSet)0x58b240)((void*)(uintptr_t)p->engine,action,0);
 }
 ((ActionDestroy)0x574d70)(action);return valid;
}
static bool read_mask(uint32_t* mask){
 uint32_t result=0;
 for(unsigned i=0;i<FLAG_COUNT;i++){uint32_t value=get_flag(i);if(value==3)return false;if(value==1)result|=1u<<i;}
 *mask=result;return true;
}
static bool clear_flags(){
 bool okay=true;
 for(unsigned i=0;i<FLAG_COUNT;i++){
  uint32_t value=get_flag(i);
  if(value==3){okay=false;continue;}
  if(value==1&&(!set_flag(i,false)||get_flag(i)!=0))okay=false;
 }
 uint32_t observed=0;if(!read_mask(&observed)||observed)okay=false;
 p->applied_mask=observed;p->deadline_frame=0;p->cleanup_verified=okay;
 return okay;
}
static void detach(){if(owned_hook){UnhookWindowsHookEx(owned_hook);owned_hook=NULL;}p->self_hook_installed=0;}
static void release_lease(){if(policy_lease&&p->lease_held){ReleaseSemaphore(policy_lease,1,NULL);p->lease_held=0;}}
static void fatal(uint32_t error){
 p->error=error;
 uint32_t game=word(0xcd8ce4);
 if(identity()&&signatures()&&game&&word(game+0x50)&&clear_flags())release_lease();
 InterlockedExchange(&p->phase,4);detach();
}
static void tick(){
 if(p->phase==2||p->phase==4)return;
 if(InterlockedCompareExchange(&p->active,1,0)!=0)return;
 p->callback_thread=GetCurrentThreadId();
 if(!identity()||!signatures()){fatal(10);p->active=0;return;}
 uint32_t game=word(0xcd8ce4),frame=word(game+0x50);
 if(!game||!frame||frame<p->last_frame){fatal(11);p->active=0;return;}
 p->last_frame=frame;if(!p->start_frame)p->start_frame=frame;
 if(p->phase==0){uint32_t initial=0;if(!read_mask(&initial)||initial){fatal(12);p->active=0;return;}p->cleanup_verified=1;p->phase=1;}
 if(p->emergency_stop||GetTickCount()-p->client_heartbeat>5000){
  p->watchdog_reason=p->emergency_stop?2:1;
  if(clear_flags()){release_lease();detach();InterlockedExchange(&p->active,0);InterlockedExchange(&p->phase,2);}else{fatal(14);p->active=0;}
  return;
 }
 if(p->applied_mask&&frame>=p->deadline_frame){if(!clear_flags()){fatal(14);p->active=0;return;}}
 LONG request=p->request;
 if(request>p->ack){
  uint32_t kind=p->kind,mask=p->mask,duration=p->duration_frames;
  if(request!=p->ack+1||request<=0||request>(LONG)MAX_REQUESTS||p->request!=request){fatal(15);p->active=0;return;}
  if(kind==2){if(!clear_flags()){fatal(14);p->active=0;return;}p->ack=request;release_lease();detach();InterlockedExchange(&p->active,0);InterlockedExchange(&p->phase,2);return;}
  if(kind!=1||!valid_mask(mask)||duration<1||duration>4500||word(game+0x15c)){fatal(16);p->active=0;return;}
  uint32_t observed=0;
  if(!read_mask(&observed)||observed!=p->applied_mask){fatal(17);p->active=0;return;}
  // Release previous high-level intents before enabling replacements. No unit
  // orders or raw native flag-table writes are exposed by this transport.
  for(unsigned pass=0;pass<2;pass++)for(unsigned i=0;i<FLAG_COUNT;i++){
   bool before=(p->applied_mask&(1u<<i))!=0,wanted=(mask&(1u<<i))!=0;
   if(before!=wanted&&wanted==(pass==1))if(!set_flag(i,wanted)||get_flag(i)!=(uint32_t)wanted){fatal(18);p->active=0;return;}
  }
  if(!read_mask(&observed)||observed!=mask){fatal(19);p->active=0;return;}
  p->applied_mask=mask;p->deadline_frame=mask?frame+duration:0;p->cleanup_verified=!mask;p->ack=request;
 }
 InterlockedExchange(&p->active,0);
}
static DWORD WINAPI watchdog(void*){
 DWORD started=GetTickCount();
 while(p->phase!=2&&p->phase!=4){
  if(GetTickCount()-started>HARD_WALL_MS)p->emergency_stop=1;
  PostThreadMessageA(p->thread,MESSAGE,MAGIC,0);Sleep(100);
 }
 return 0;
}
extern "C" __declspec(dllexport) LRESULT CALLBACK MacroPolicyControl(int code,WPARAM wp,LPARAM lp){
 if(code>=0&&wp==PM_REMOVE&&lp&&((MSG*)lp)->message==MESSAGE&&((MSG*)lp)->wParam==MAGIC){
  if(!p){
   char name[80];snprintf(name,sizeof(name),"%s%lu",MAPPING_PREFIX,GetCurrentProcessId());
   mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);
   if(mapping)p=(Shared*)MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Shared));
   if(p&&(p->magic!=MAGIC||p->version!=PROTOCOL_VERSION||p->pid!=GetCurrentProcessId()))p=NULL;
   if(p){
    if(!identity()||!signatures()){p->error=10;p->phase=4;}
    else if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCSTR)(uintptr_t)&tick,&pin)){p->error=20;p->phase=4;}
    else{
     char lease_name[80];snprintf(lease_name,sizeof(lease_name),"Local\\RA3MacroPolicyLease_%lu",GetCurrentProcessId());
     policy_lease=CreateSemaphoreA(NULL,1,1,lease_name);
     if(!policy_lease||WaitForSingleObject(policy_lease,0)!=WAIT_OBJECT_0){p->error=23;p->phase=4;}
     else{
     p->lease_held=1;
     // A hook owned by the game process survives loss of the external host.
     owned_hook=SetWindowsHookExA(WH_GETMESSAGE,MacroPolicyControl,pin,p->thread);
     if(!owned_hook){p->error=21;p->phase=4;release_lease();}
     else{
      p->self_hook_installed=1;HANDLE worker=CreateThread(NULL,0,watchdog,NULL,0,NULL);
      if(worker)CloseHandle(worker);else{p->error=22;p->phase=4;release_lease();detach();}
     }
     }
    }
   }
  }
  if(p)tick();
 }
 return CallNextHookEx(NULL,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID){if(reason==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(module);return TRUE;}
