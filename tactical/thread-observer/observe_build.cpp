#include "production_shared.h"
#include <wincrypt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static DWORD target;
static HWND window;
static BOOL CALLBACK find_window(HWND candidate,LPARAM){DWORD pid=0;GetWindowThreadProcessId(candidate,&pid);if(pid==target&&IsWindowVisible(candidate)&&!GetWindow(candidate,GW_OWNER)){window=candidate;return FALSE;}return TRUE;}
static bool valid_executable(DWORD pid){
 HANDLE p=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,pid);char path[32768];DWORD size=sizeof(path);
 if(!p||!QueryFullProcessImageNameA(p,0,path,&size)){if(p)CloseHandle(p);return false;}CloseHandle(p);
 const char* base=strrchr(path,'\\');if(!base||_stricmp(base+1,"ra3_1.12.game"))return false;
 HANDLE file=CreateFileA(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);if(file==INVALID_HANDLE_VALUE)return false;
 HCRYPTPROV provider=0;HCRYPTHASH hash=0;bool okay=false;
 if(CryptAcquireContextA(&provider,NULL,NULL,PROV_RSA_AES,CRYPT_VERIFYCONTEXT)&&CryptCreateHash(provider,CALG_SHA_256,0,0,&hash)){
  BYTE data[65536];DWORD read=0;BOOL result;
  while((result=ReadFile(file,data,sizeof(data),&read,NULL))&&read)if(!CryptHashData(hash,data,read,0)){result=FALSE;break;}
  BYTE digest[32];DWORD n=sizeof(digest);char hex[65]={};
  if(result&&CryptGetHashParam(hash,HP_HASHVAL,digest,&n,0)){for(int i=0;i<32;i++)sprintf(hex+i*2,"%02x",digest[i]);okay=!strcmp(hex,"ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165");}
 }
 if(hash)CryptDestroyHash(hash);
 if(provider)CryptReleaseContext(provider,0);
 CloseHandle(file);return okay;
}
int main(int argc,char** argv){
 if(argc!=3){fprintf(stderr,"Usage: observe_build.exe PID SECONDS(1..30)\n");return 2;}
 target=strtoul(argv[1],NULL,10);int seconds=atoi(argv[2]);if(seconds<1||seconds>30||!valid_executable(target)){fprintf(stderr,"Unsupported target or duration\n");return 3;}
 EnumWindows(find_window,0);if(!window){fprintf(stderr,"Game window not found\n");return 4;}
 char name[80];snprintf(name,sizeof(name),"Local\\RA3TacticalThreadEvidence_%lu",target);
 HANDLE mapping=CreateFileMappingA(INVALID_HANDLE_VALUE,NULL,PAGE_READWRITE,0,sizeof(ObserverState),name);
 if(!mapping||GetLastError()==ERROR_ALREADY_EXISTS){fprintf(stderr,"Production observer already used in this process\n");return 5;}
 ObserverState* state=(ObserverState*)MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(ObserverState));if(!state)return 5;
 memset(state,0,sizeof(*state));state->magic=OBS_MAGIC;state->version=1;state->pid=target;state->seconds=seconds;state->window_thread=GetWindowThreadProcessId(window,NULL);state->request=1;
 char dll[MAX_PATH];GetModuleFileNameA(NULL,dll,sizeof(dll));char* slash=strrchr(dll,'\\');if(!slash)return 6;strcpy(slash+1,"TacticalThreadEvidence.dll");
 HMODULE library=LoadLibraryA(dll);HOOKPROC callback=NULL;if(library){FARPROC proc=GetProcAddress(library,"TacticalThreadEvidenceControl");memcpy(&callback,&proc,sizeof(callback));}
 HHOOK hook=callback?SetWindowsHookExA(WH_GETMESSAGE,callback,library,state->window_thread):NULL;
 if(!hook){fprintf(stderr,"Observer control hook failed %lu\n",GetLastError());return 6;}
 PostMessageA(window,OBS_MESSAGE,OBS_MAGIC,0);
 DWORD began=GetTickCount();while(!state->ack&&GetTickCount()-began<10000)Sleep(10);
 began=GetTickCount();while(state->state==1&&GetTickCount()-began<(DWORD)(seconds+5)*1000)Sleep(25);
 if(state->state==1){InterlockedExchange(&state->request,2);PostMessageA(window,OBS_MESSAGE,OBS_MAGIC,0);Sleep(100);}
 printf("{\"pid\":%lu,\"seconds\":%d,\"state\":%ld,\"error\":%u,\"original_bytes_restored\":%s,\"active_detours\":%ld,\"window_thread\":%u,\"callback_thread\":%u,\"total_build_calls\":%ld,\"mutates_arguments\":false,\"lifetime\":\"DLL and trampoline pinned until test process exit\",\"events\":[",target,seconds,state->state,state->error,state->restore_verified?"true":"false",state->active,state->window_thread,state->callback_thread,state->total_calls);
 LONG count=state->event_count;if(count>OBS_CAPACITY)count=OBS_CAPACITY;
 for(LONG i=0;i<count;i++){BuildEvent& e=state->events[i];printf("%s{\"tick\":%u,\"thread\":%u,\"interface\":\"0x%08x\",\"factory\":\"0x%08x\",\"owner\":\"0x%08x\",\"template\":\"0x%08x\",\"template_hash\":\"0x%08x\",\"caller\":\"0x%08x\",\"queue_before\":\"0x%08x\",\"queue_after\":\"0x%08x\",\"return_value\":%u,\"matched_node\":\"0x%08x\",\"node_cost\":%u,\"raw_args_after_template\":[",i?",":"",e.tick,e.thread,e.interface_address,e.factory,e.owner,e.template_address,e.template_hash,e.caller,e.queue_before,e.queue_after,e.return_value,e.matched_node,e.node_cost);for(int j=0;j<7;j++)printf("%s%u",j?",":"",e.args[j]);printf("],\"stack\":[");for(uint32_t j=0;j<e.stack_count&&j<8;j++)printf("%s\"0x%08x\"",j?",":"",e.stack[j]);printf("]}");}
 printf("]}\n");bool okay=state->ack==1&&state->state==2&&state->restore_verified&&state->active==0;
 UnhookWindowsHookEx(hook);UnmapViewOfFile(state);CloseHandle(mapping);if(library)FreeLibrary(library);return okay?0:7;
}
