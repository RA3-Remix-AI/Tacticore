#include "trace_shared.h"
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
static const char* fields[]={"kind","seq","wall_ms","frame","thread","caller","factory","owner","module","node","queue_id","template","template_hash","cost","paid_before","paid_after","resource","cash_before_raw","cash_after_raw","requested","actual","returned","object","object_id","object_owner","object_hash","head_before","head_after","progress_before_bits","progress_after_bits","context_valid","node_kind","object_x_bits","object_y_bits","object_z_bits","factory_x_bits","factory_y_bits","factory_z_bits","object_hp_bits"};
static void emit(TraceEvent& event){printf("{\"record\":\"event\"");for(unsigned i=0;i<FIELD_COUNT;i++)printf(",\"%s\":%u",fields[i],event.v[i]);puts("}");fflush(stdout);}
int main(int argc,char** argv){
 if(argc!=10){fprintf(stderr,"Use guarded trace_production.py wrapper only\n");return 2;}
 target=strtoul(argv[1],NULL,0);if(!valid_executable(target))return 3;int seconds=atoi(argv[9]);if(seconds<10||seconds>300)return 3;
 EnumWindows(find_window,0);if(!window)return 4;
 char name[80];snprintf(name,sizeof(name),"Local\\RA3ProductionTrace_%lu",target);HANDLE mapping=CreateFileMappingA(INVALID_HANDLE_VALUE,NULL,PAGE_READWRITE,0,sizeof(TraceState),name);if(!mapping||GetLastError()==ERROR_ALREADY_EXISTS){fprintf(stderr,"Trace already used in this process\n");return 5;}
 TraceState* s=(TraceState*)MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(TraceState));if(!s)return 6;memset(s,0,sizeof(*s));s->magic=TRACE_MAGIC;s->pid=target;s->factory=strtoul(argv[2],NULL,0);s->owner=strtoul(argv[3],NULL,0);s->ai=strtoul(argv[4],NULL,0);s->iface=strtoul(argv[5],NULL,0);s->start_low=strtoul(argv[6],NULL,0);s->start_high=strtoul(argv[7],NULL,0);s->thread=strtoul(argv[8],NULL,0);s->seconds=seconds;
 if(s->thread!=GetWindowThreadProcessId(window,NULL))return 7;
 char dll[MAX_PATH];GetModuleFileNameA(NULL,dll,sizeof(dll));char* slash=strrchr(dll,'\\');if(!slash)return 8;strcpy(slash+1,"NativeProductionTrace.dll");HMODULE library=LoadLibraryA(dll);HOOKPROC callback=NULL;if(library){FARPROC proc=GetProcAddress(library,"ProductionTraceControl");memcpy(&callback,&proc,sizeof(callback));}HHOOK hook=callback?SetWindowsHookExA(WH_GETMESSAGE,callback,library,s->thread):NULL;if(!hook)return 9;
 s->requested_tick=GetTickCount();s->request=1;PostMessageA(window,TRACE_MESSAGE,TRACE_MAGIC,0);DWORD began=GetTickCount();while(!s->ack&&GetTickCount()-began<10000)Sleep(10);
 printf("{\"record\":\"installed\",\"pid\":%lu,\"state\":%ld,\"error\":%u,\"callback_thread\":%u,\"passive_only\":true}\n",target,s->state,s->error,s->callback_thread);fflush(stdout);
 LONG cursor=0;began=GetTickCount();while(s->state==1&&GetTickCount()-began<(DWORD)(seconds+5)*1000){LONG count=s->event_count;if(count>TRACE_CAP)count=TRACE_CAP;while(cursor<count&&s->events[cursor].ready){emit(s->events[cursor]);cursor++;}Sleep(10);}
 if(s->state==1){InterlockedExchange(&s->request,2);PostMessageA(window,TRACE_MESSAGE,TRACE_MAGIC,0);DWORD wait=GetTickCount();while(s->state==1&&GetTickCount()-wait<5000)Sleep(10);}
 LONG count=s->event_count;if(count>TRACE_CAP)count=TRACE_CAP;while(cursor<count&&s->events[cursor].ready){emit(s->events[cursor]);cursor++;}
 printf("{\"record\":\"stopped\",\"pid\":%lu,\"state\":%ld,\"error\":%u,\"active_detours\":%ld,\"restore_mask\":%u,\"total_events\":%ld,\"emitted_events\":%ld,\"dropped\":%ld,\"passive_only\":true,\"lifetime\":\"DLL and trampolines pinned until process exit\"}\n",target,s->state,s->error,s->active,s->restore_mask,s->event_count,cursor,s->dropped);fflush(stdout);
 bool okay=s->state==2&&s->restore_mask==31&&!s->error&&!s->active&&!s->dropped&&cursor==count;UnhookWindowsHookEx(hook);UnmapViewOfFile(s);CloseHandle(mapping);if(library)FreeLibrary(library);return okay?0:10;
}

