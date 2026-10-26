#include "shared.h"
#include <wincrypt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>
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
#include "host_pulse.cpp.inc"
static int publish_commit(uint32_t pid,uint32_t token){
 if(!pid||!token)return 12;char name[100];snprintf(name,sizeof(name),"Local\\RA3TacticalMissionFormation17_%u_%u",pid,token);HANDLE m=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);if(!m)return 13;Tactical* view=(Tactical*)MapViewOfFile(m,FILE_MAP_ALL_ACCESS,0,0,sizeof(Tactical));if(!view){CloseHandle(m);return 14;}
 bool bound=view->magic==T_MAGIC&&view->version==17&&view->pid==pid&&view->token==token&&view->phase==1&&view->controller.stage==2&&view->controller.clock_frozen&&view->controller.held_mask==3&&view->controller.ready_mask==3&&view->slots[0].id&&view->slots[1].id&&view->slots[0].id!=view->slots[1].id&&!memcmp(view->command,view->controller_input.controller,16)&&!memcmp(view->task,view->controller_input.lease,16)&&!memcmp(view->mission_commit.body.controller,view->command,16)&&!memcmp(view->mission_commit.body.lease,view->task,16)&&view->mission_commit.body.front_id==view->slots[0].id&&view->mission_commit.body.support_id==view->slots[1].id;
 LONG previous=-1;if(bound){MemoryBarrier();previous=InterlockedCompareExchange((volatile LONG*)&view->mission_commit.generation,2,0);}
 printf("{\"publication_only\":true,\"sdk_calls\":0,\"game_memory_writes\":false,\"pid\":%u,\"token\":%u,\"bound\":%s,\"previous_generation\":%ld,\"published\":%s}\n",pid,token,bound?"true":"false",previous,bound&&previous==0?"true":"false");UnmapViewOfFile(view);CloseHandle(m);return bound&&previous==0?0:15;
}
int main(int argc,char** argv){
 if(argc==2&&!strcmp(argv[1],"--layout")){printf("{\"event\":%u,\"tactical\":%u,\"events\":%u,\"unused1\":%u,\"unused2\":%u}\n",(unsigned)sizeof(Event),(unsigned)sizeof(Tactical),(unsigned)offsetof(Tactical,events),0u,0u);return 0;}
 if(argc==2&&!strcmp(argv[1],"--controller-layout")){printf("{\"event\":%u,\"lineage\":%u,\"support_offset\":%u,\"legacy_header\":%u,\"input_size\":%u,\"state_size\":%u,\"slot_input\":%u,\"slot_output\":%u,\"commit_body\":%u,\"commit\":%u,\"sample\":%u,\"receipt\":%u,\"input_offset\":%u,\"state_offset\":%u,\"slots_offset\":%u,\"commit_offset\":%u,\"header\":%u,\"tactical\":%u}\n",sizeof(Event),sizeof(MoveLineage),offsetof(Tactical,support),offsetof(Tactical,controller_input),sizeof(ControllerInput13),sizeof(ControllerState13),sizeof(PaidSlotInput13),sizeof(PaidSlotOutput13),sizeof(MissionCommitBody13),sizeof(MissionCommit13),sizeof(ReserveSample13),sizeof(ProductionReceipt13),offsetof(Tactical,controller_input),offsetof(Tactical,controller),offsetof(Tactical,slots),offsetof(Tactical,mission_commit),offsetof(Tactical,events),sizeof(Tactical));return 0;}
 if(argc==4&&!strcmp(argv[1],"--publish-commit"))return publish_commit(strtoul(argv[2],NULL,0),strtoul(argv[3],NULL,0));
 if(argc!=3)return 2;
 target=strtoul(argv[1],NULL,0);if(!valid_executable(target))return 3;EnumWindows(find_window,0);if(!window)return 4;
 uint32_t token=strtoul(argv[2],NULL,0);char name[100];snprintf(name,sizeof(name),"Local\\RA3TacticalMissionFormation17_%lu_%u",target,token);HANDLE m=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);if(!m)return 5;Tactical* p=(Tactical*)MapViewOfFile(m,FILE_MAP_ALL_ACCESS,0,0,sizeof(Tactical));if(!p||p->magic!=T_MAGIC||p->version!=17||p->pid!=target||p->token!=token||p->thread!=GetWindowThreadProcessId(window,NULL))return 6;
 uint32_t bound_command[4],bound_task[4],bound_seq=p->seq;memcpy(bound_command,p->command,16);memcpy(bound_task,p->task,16);
 char dll[MAX_PATH];GetModuleFileNameA(NULL,dll,sizeof(dll));char* slash=strrchr(dll,'\\');if(!slash)return 7;strcpy(slash+1,"TacticalMissionFormation17.dll");HMODULE lib=LoadLibraryA(dll);HOOKPROC callback=NULL;if(lib){FARPROC proc=GetProcAddress(lib,"TacticalMissionFormation17Control");memcpy(&callback,&proc,sizeof(callback));}HHOOK hook=callback?SetWindowsHookExA(WH_GETMESSAGE,callback,lib,p->thread):NULL;if(!hook)return 8;
 PostMessageA(window,T_MESSAGE,T_MAGIC,token);DWORD start=GetTickCount();while(!p->callback_thread&&GetTickCount()-start<10000)Sleep(10);printf("{\"phase\":%ld,\"error\":%u,\"thread\":%u}\n",p->phase,p->error,p->callback_thread);fflush(stdout);
 HostPulse pulse={};pulse.last_post_tick=GetTickCount()-T_PULSE_PERIOD_MS;
 start=GetTickCount();while(p->phase!=3&&p->phase!=4&&GetTickCount()-start<400000){host_pulse_step(p,window,token,bound_seq,bound_command,bound_task,pulse);Sleep(10);}
 if(p->phase!=3&&p->phase!=4){InterlockedExchange(&p->stop_requested,1);DWORD stop=GetTickCount();while(p->phase!=3&&p->phase!=4&&GetTickCount()-stop<10000)Sleep(25);}
 printf("{\"phase\":%ld,\"error\":%u,\"restore_mask\":%u,\"active\":%ld}\n",p->phase,p->error,p->restore_mask,p->active);fflush(stdout);
 DWORD drain=GetTickCount();while(p->active&&GetTickCount()-drain<2000)Sleep(1);
 bool okay=p->phase==3&&p->restore_mask==131071&&!p->active;UnhookWindowsHookEx(hook);UnmapViewOfFile(p);CloseHandle(m);if(lib)FreeLibrary(lib);return okay?0:9;
}

