#include "oneshot_shared.h"
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
 if(argc!=10){fprintf(stderr,"Use guarded run_flak.py wrapper only\n");return 2;}
 target=strtoul(argv[1],NULL,0);if(!valid_executable(target))return 3;
 EnumWindows(find_window,0);if(!window)return 4;
 char name[80];snprintf(name,sizeof(name),"Local\\RA3FlakOneShot_%lu",target);
 HANDLE m=CreateFileMappingA(INVALID_HANDLE_VALUE,NULL,PAGE_READWRITE,0,sizeof(OneState),name);
 if(!m||GetLastError()==ERROR_ALREADY_EXISTS)return 5;
 OneState* s=(OneState*)MapViewOfFile(m,FILE_MAP_ALL_ACCESS,0,0,sizeof(OneState));if(!s)return 6;
 memset(s,0,sizeof(*s));s->magic=ONE_MAGIC;s->pid=target;s->factory=strtoul(argv[2],NULL,0);s->owner=strtoul(argv[3],NULL,0);s->ai=strtoul(argv[4],NULL,0);s->iface=strtoul(argv[5],NULL,0);s->start_low=strtoul(argv[6],NULL,0);s->start_high=strtoul(argv[7],NULL,0);s->thread=strtoul(argv[8],NULL,0);
 s->queue_limit=strtoul(argv[9],NULL,0);if(s->queue_limit>2)return 7;
 if(s->thread!=GetWindowThreadProcessId(window,NULL))return 7;
 char dll[MAX_PATH];GetModuleFileNameA(NULL,dll,sizeof(dll));char* slash=strrchr(dll,'\\');if(!slash)return 8;strcpy(slash+1,"FlakOneShot.dll");
 HMODULE library=LoadLibraryA(dll);HOOKPROC callback=NULL;if(library){FARPROC proc=GetProcAddress(library,"FlakOneShotControl");memcpy(&callback,&proc,sizeof(callback));}
 HHOOK hook=callback?SetWindowsHookExA(WH_GETMESSAGE,callback,library,s->thread):NULL;if(!hook)return 9;
 s->requested_tick=GetTickCount();PostMessageA(window,ONE_MESSAGE,ONE_MAGIC,0);DWORD began=GetTickCount();while(!s->state&&GetTickCount()-began<12000)Sleep(5);
 printf("{\"pid\":%lu,\"state\":%ld,\"error\":%u,\"claimed\":%ld,\"callback_thread\":%u,\"template\":\"0x%08x\",\"queue_id\":%u,\"node\":\"0x%08x\",\"native_cost\":%u,\"cash_before\":%d,\"cash_after\":%d,\"head_before\":\"0x%08x\",\"tail_before\":\"0x%08x\",\"head_after\":\"0x%08x\",\"tail_after\":\"0x%08x\",\"hp\":%.3f,\"queue_limit\":%u,\"prior_count\":%u,\"queue_preserved\":%s,\"initial_paid\":%u,\"prior_ids\":[",target,s->state,s->error,s->claimed,s->callback_thread,s->template_pointer,s->queue_id,s->node,s->cost,s->cash_before,s->cash_after,s->head_before,s->tail_before,s->head_after,s->tail_after,s->hp,s->queue_limit,s->prior_count,s->queue_preserved?"true":"false",s->initial_paid);
 for(uint32_t i=0;i<s->prior_count&&i<2;i++){printf("%s%u",i?",":"",s->prior_ids[i]);}
 printf("],\"active_enqueue_attempted\":%s,\"spend_attributed\":false}\n",(s->error==0||s->error==12||s->error==13)?"true":"false");
 bool okay=s->state==2&&s->queue_id&&s->node;UnhookWindowsHookEx(hook);UnmapViewOfFile(s);CloseHandle(m);if(library)FreeLibrary(library);return okay?0:10;
}

