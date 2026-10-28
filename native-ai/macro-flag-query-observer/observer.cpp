// Passive native flag-query witness. Always forwards the original float result.
// No setters, game-order APIs, actor controls, or changed AI return values.
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wincrypt.h>
#ifndef OBSERVER_EPOCH
#define OBSERVER_EPOCH 1
#endif
static const uint32_t MAGIC=0x4d46514f,MESSAGE=WM_APP+0x343,ADDRESS=0x889bf0;
static const char PREFIX[]="/5TFMacro_57e668b44d8943bdbc920dd436f046ef_P3_";
struct Event{uint32_t frame,thread,self,vtable,definition,arg1,arg2,result,caller,stack_count,stack[8];char name[128];};
struct Shared{uint32_t magic,pid,thread,start_low,start_high,seconds,start_tick,error,restored;volatile LONG phase,active,count,total;BYTE before[17];Event events[256];};
static bool read(uint32_t address,void* out,SIZE_T n){SIZE_T got=0;return ReadProcessMemory(GetCurrentProcess(),(void*)(uintptr_t)address,out,n,&got)&&got==n;}
static uint32_t word(uint32_t address){uint32_t value=0;read(address,&value,4);return value;}
#ifdef FLAG_QUERY_DLL
#include "MinHook.h"
static Shared* p;static HANDLE mapping;static HMODULE pinned;static volatile LONG stop_owner;
typedef float (__attribute__((thiscall))*Query)(void*,uint32_t,uint32_t);static Query original;
static float __attribute__((fastcall)) witness(void* self,void*,uint32_t arg1,uint32_t arg2){
 InterlockedIncrement(&p->active);InterlockedIncrement(&p->total);
 char name[128]={};uint32_t definition=word((uintptr_t)self+4),address=word(definition+8);bool terminated=false;
 if(address){for(unsigned i=0;i<sizeof(name);i++){if(!read(address+i,&name[i],1))break;if(!name[i]){terminated=true;break;}}}
 bool ours=terminated&&!strncmp(name,PREFIX,sizeof(PREFIX)-1);
 uint32_t frame=word(word(0xcd8ce4)+0x50),caller=(uintptr_t)__builtin_return_address(0);
 float result=original(self,arg1,arg2);
 if(ours&&p->phase==1){LONG index=InterlockedIncrement(&p->count)-1;if(index<256){Event& e=p->events[index];e.frame=frame;e.thread=GetCurrentThreadId();e.self=(uintptr_t)self;e.vtable=word((uintptr_t)self);e.definition=definition;e.arg1=arg1;e.arg2=arg2;memcpy(&e.result,&result,4);e.caller=caller;memcpy(e.name,name,sizeof(name));void* stack[8]={};e.stack_count=CaptureStackBackTrace(0,8,stack,NULL);for(unsigned i=0;i<e.stack_count;i++)e.stack[i]=(uintptr_t)stack[i];}}
 InterlockedDecrement(&p->active);return result;
}
static void stop(){if(InterlockedCompareExchange(&stop_owner,1,0))return;MH_STATUS status=MH_DisableHook((void*)(uintptr_t)ADDRESS);if(status!=MH_OK&&status!=MH_ERROR_DISABLED)p->error=100+status;BYTE now[17]={};p->restored=read(ADDRESS,now,17)&&!memcmp(now,p->before,17);DWORD start=GetTickCount();while(p->active&&GetTickCount()-start<2000)Sleep(1);InterlockedExchange(&p->phase,p->restored&&!p->active&&!p->error?2:4);}
static DWORD WINAPI watchdog(void*){while(p->phase==1&&GetTickCount()-p->start_tick<p->seconds*1000)Sleep(25);stop();return 0;}
static void install(){
 FILETIME a,b,c,d;const BYTE expected[]={0x8b,0xc1,0x8b,0x40,0x04,0x8b,0x50,0x08,0x51,0x8b,0xcc,0x52,0xe8,0x0f,0x2d,0xc4,0xff};
 if((uintptr_t)GetModuleHandleW(NULL)!=0x400000||p->pid!=GetCurrentProcessId()||p->thread!=GetCurrentThreadId()||!GetProcessTimes(GetCurrentProcess(),&a,&b,&c,&d)||a.dwLowDateTime!=p->start_low||a.dwHighDateTime!=p->start_high||!read(ADDRESS,p->before,17)||memcmp(p->before,expected,17)){p->error=10;p->phase=4;return;}
 if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCSTR)(uintptr_t)&witness,&pinned)){p->error=11;p->phase=4;return;}
 MH_STATUS status=MH_Initialize();if(status!=MH_OK&&status!=MH_ERROR_ALREADY_INITIALIZED){p->error=20+status;p->phase=4;return;}
 status=MH_CreateHook((void*)(uintptr_t)ADDRESS,(void*)&witness,(void**)&original);if(status!=MH_OK){p->error=40+status;p->phase=4;return;}
 p->start_tick=GetTickCount();p->phase=1;status=MH_EnableHook((void*)(uintptr_t)ADDRESS);if(status!=MH_OK){p->error=60+status;stop();return;}
 HANDLE worker=CreateThread(NULL,0,watchdog,NULL,0,NULL);if(worker)CloseHandle(worker);else{p->error=80;stop();}
}
extern "C" __declspec(dllexport) LRESULT CALLBACK FlagQueryControl(int code,WPARAM wp,LPARAM lp){
 if(code>=0&&wp==PM_REMOVE&&lp&&((MSG*)lp)->message==MESSAGE&&((MSG*)lp)->wParam==MAGIC&&!p){char name[80];snprintf(name,sizeof(name),"Local\\RA3MacroFlagQueryV%u_%lu",OBSERVER_EPOCH,GetCurrentProcessId());mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);if(mapping)p=(Shared*)MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Shared));if(p&&p->magic==MAGIC&&p->seconds>=1&&p->seconds<=30)install();}
 return CallNextHookEx(NULL,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID){if(reason==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(module);return TRUE;}
#else
static DWORD target;static HWND window;
static BOOL CALLBACK find_window(HWND candidate,LPARAM){DWORD pid=0;GetWindowThreadProcessId(candidate,&pid);if(pid==target&&IsWindowVisible(candidate)&&!GetWindow(candidate,GW_OWNER)){window=candidate;return FALSE;}return TRUE;}
static bool executable(HANDLE process){
 char path[32768];DWORD size=sizeof(path);if(!QueryFullProcessImageNameA(process,0,path,&size)||_stricmp(path,"E:\\RedRar3\\Data\\RA3_1.12.game"))return false;
 HANDLE file=CreateFileA(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);if(file==INVALID_HANDLE_VALUE)return false;
 HCRYPTPROV provider=0;HCRYPTHASH hash=0;bool okay=false;
 if(CryptAcquireContextA(&provider,NULL,NULL,PROV_RSA_AES,CRYPT_VERIFYCONTEXT)&&CryptCreateHash(provider,CALG_SHA_256,0,0,&hash)){BYTE data[65536];DWORD got=0;BOOL result;while((result=ReadFile(file,data,sizeof(data),&got,NULL))&&got)if(!CryptHashData(hash,data,got,0)){result=FALSE;break;}BYTE digest[32];DWORD n=sizeof(digest);char hex[65]={};if(result&&CryptGetHashParam(hash,HP_HASHVAL,digest,&n,0)){for(int i=0;i<32;i++)sprintf(hex+i*2,"%02x",digest[i]);okay=!strcmp(hex,"ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165");}}
 if(hash)CryptDestroyHash(hash);if(provider)CryptReleaseContext(provider,0);CloseHandle(file);return okay;
}
int main(int argc,char** argv){
 if(argc!=3)return 2;target=strtoul(argv[1],NULL,10);int seconds=atoi(argv[2]);if(seconds<1||seconds>30)return 2;
 HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION|PROCESS_VM_READ,FALSE,target);FILETIME a,b,c,d;if(!process||!GetProcessTimes(process,&a,&b,&c,&d)||!executable(process))return 3;
 EnumWindows(find_window,0);if(!window)return 4;
 char name[80];snprintf(name,sizeof(name),"Local\\RA3MacroFlagQueryV%u_%lu",OBSERVER_EPOCH,target);HANDLE mapping=CreateFileMappingA(INVALID_HANDLE_VALUE,NULL,PAGE_READWRITE,0,sizeof(Shared),name);if(!mapping||GetLastError()==ERROR_ALREADY_EXISTS)return 5;
 Shared* p=(Shared*)MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Shared));if(!p)return 6;memset(p,0,sizeof(*p));p->magic=MAGIC;p->pid=target;p->thread=GetWindowThreadProcessId(window,NULL);p->start_low=a.dwLowDateTime;p->start_high=a.dwHighDateTime;p->seconds=seconds;
 char dll[MAX_PATH];GetModuleFileNameA(NULL,dll,sizeof(dll));char* slash=strrchr(dll,'\\');if(!slash)return 7;snprintf(slash+1,sizeof(dll)-(slash+1-dll),"MacroFlagQueryV%u.dll",OBSERVER_EPOCH);HMODULE library=LoadLibraryA(dll);HOOKPROC callback=NULL;if(library){FARPROC proc=GetProcAddress(library,"FlagQueryControl");memcpy(&callback,&proc,sizeof(callback));}HHOOK hook=callback?SetWindowsHookExA(WH_GETMESSAGE,callback,library,p->thread):NULL;if(!hook)return 8;
 PostMessageA(window,MESSAGE,MAGIC,0);DWORD start=GetTickCount();while(!p->phase&&GetTickCount()-start<10000)Sleep(10);while(p->phase==1&&GetTickCount()-start<(DWORD)(seconds+15)*1000)Sleep(25);
 BYTE restored[17]={};SIZE_T got=0;bool independent=ReadProcessMemory(process,(void*)(uintptr_t)ADDRESS,restored,17,&got)&&got==17&&!memcmp(restored,p->before,17);
 printf("{\"pid\":%lu,\"creation_filetime_low\":%lu,\"creation_filetime_high\":%lu,\"phase\":%ld,\"error\":%u,\"active\":%ld,\"original_restored\":%s,\"independent_restore_verified\":%s,\"total_queries\":%ld,\"matching_queries\":%ld,\"setters_called\":0,\"unit_control\":false,\"events\":[",target,a.dwLowDateTime,a.dwHighDateTime,p->phase,p->error,p->active,p->restored?"true":"false",independent?"true":"false",p->total,p->count);
 LONG count=p->count;if(count>256)count=256;for(LONG i=0;i<count;i++){Event& e=p->events[i];printf("%s{\"frame\":%u,\"thread\":%u,\"self\":\"0x%08x\",\"vtable\":\"0x%08x\",\"definition\":\"0x%08x\",\"arg1\":\"0x%08x\",\"arg2\":\"0x%08x\",\"result_bits\":%u,\"caller\":\"0x%08x\",\"name\":\"%s\",\"stack\":[",i?",":"",e.frame,e.thread,e.self,e.vtable,e.definition,e.arg1,e.arg2,e.result,e.caller,e.name);for(unsigned j=0;j<e.stack_count&&j<8;j++)printf("%s\"0x%08x\"",j?",":"",e.stack[j]);printf("]}");}printf("]}\n");
 bool okay=p->phase==2&&!p->error&&!p->active&&p->restored&&independent;UnhookWindowsHookEx(hook);UnmapViewOfFile(p);CloseHandle(mapping);CloseHandle(process);if(library)FreeLibrary(library);return okay?0:9;
}
#endif
