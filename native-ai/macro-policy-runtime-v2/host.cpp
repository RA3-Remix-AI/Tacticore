#include "shared.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>
#include <errno.h>
static DWORD target;static HWND window;
static BOOL CALLBACK find_window(HWND candidate,LPARAM){
 DWORD pid=0;GetWindowThreadProcessId(candidate,&pid);
 if(pid==target&&IsWindowVisible(candidate)&&!GetWindow(candidate,GW_OWNER)){window=candidate;return FALSE;}
 return TRUE;
}
int main(int argc,char** argv){
 if(argc==2&&!strcmp(argv[1],"--layout")){
  printf("{\"size\":%u,\"request\":%u,\"error\":%u,\"mask\":%u,\"heartbeat\":%u}\n",(unsigned)sizeof(Shared),
   (unsigned)offsetof(Shared,request),(unsigned)offsetof(Shared,error),(unsigned)offsetof(Shared,mask),(unsigned)offsetof(Shared,client_heartbeat));return 0;
 }
 if(argc==3&&!strcmp(argv[1],"--validate-mask")){char* end=NULL;errno=0;unsigned long long value=strtoull(argv[2],&end,0);return !errno&&end&&end!=argv[2]&&!*end&&argv[2][0]!='-'&&value<=0xffffffffULL&&valid_mask((uint32_t)value)?0:23;}
 if(argc!=2)return 2;
 target=strtoul(argv[1],NULL,10);EnumWindows(find_window,0);if(!window)return 3;
 char name[80];snprintf(name,sizeof(name),"%s%lu",MAPPING_PREFIX,target);
 HANDLE mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);if(!mapping)return 4;
 Shared* p=(Shared*)MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Shared));
 if(!p||p->magic!=MAGIC||p->version!=PROTOCOL_VERSION||p->pid!=target||p->thread!=GetWindowThreadProcessId(window,NULL)||p->personality_id!=PERSONALITY_ID)return 5;
 HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,target);FILETIME a,b,c,d;
 if(!process||!GetProcessTimes(process,&a,&b,&c,&d)||a.dwLowDateTime!=p->start_low||a.dwHighDateTime!=p->start_high)return 6;
 char path[32768];DWORD size=sizeof(path);
 if(!QueryFullProcessImageNameA(process,0,path,&size)||_stricmp(path,"E:\\RedRar3\\Data\\RA3_1.12.game"))return 6;
 char dll[MAX_PATH];GetModuleFileNameA(NULL,dll,sizeof(dll));char* slash=strrchr(dll,'\\');if(!slash)return 7;strcpy(slash+1,LIBRARY_NAME);
 HMODULE library=LoadLibraryA(dll);HOOKPROC callback=NULL;
 if(library){FARPROC proc=GetProcAddress(library,"MacroPolicyControl");memcpy(&callback,&proc,sizeof(callback));}
 HHOOK hook=callback?SetWindowsHookExA(WH_GETMESSAGE,callback,library,p->thread):NULL;if(!hook)return 8;
 DWORD started=GetTickCount();
 while(p->phase!=2&&p->phase!=4&&GetTickCount()-started<HARD_WALL_MS+10000){
  PostMessageA(window,MESSAGE,MAGIC,0);
  if(GetTickCount()-started>HARD_WALL_MS)p->emergency_stop=1;
  Sleep(25);
 }
 printf("{\"phase\":%ld,\"error\":%u,\"ack\":%ld,\"mask\":%u,\"cleanup_verified\":%u,\"active\":%ld,\"self_hook_installed\":%u}\n",
  p->phase,p->error,p->ack,p->applied_mask,p->cleanup_verified,p->active,p->self_hook_installed);
 bool okay=p->phase==2&&!p->applied_mask&&p->cleanup_verified&&!p->active&&!p->error&&!p->self_hook_installed&&!p->lease_held;
 UnhookWindowsHookEx(hook);UnmapViewOfFile(p);CloseHandle(mapping);CloseHandle(process);if(library)FreeLibrary(library);
 return okay?0:9;
}
