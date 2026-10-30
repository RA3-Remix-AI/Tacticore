#include "shared.h"
#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include <errno.h>
static DWORD target;static HWND window;
static BOOL CALLBACK find_window(HWND candidate,LPARAM){DWORD pid=0;GetWindowThreadProcessId(candidate,&pid);if(pid==target&&IsWindowVisible(candidate)&&!GetWindow(candidate,GW_OWNER)){if(window){window=NULL;return FALSE;}window=candidate;}return TRUE;}
int main(int argc,char** argv){
 if(argc==2&&!strcmp(argv[1],"--all-masks")){
  putchar('[');bool first=true;for(uint32_t mask=0;mask<1026;mask++)if(valid_mask(mask)){if(!first)putchar(',');printf("%u",mask);first=false;}puts("]");return 0;
 }
 if(argc==3&&!strcmp(argv[1],"--validate-mask")){char* end=NULL;errno=0;unsigned long long value=strtoull(argv[2],&end,0);return !errno&&end&&end!=argv[2]&&!*end&&argv[2][0]!='-'&&value<=0xffffffffULL&&valid_mask((uint32_t)value)?0:23;}
 if(argc==2&&!strcmp(argv[1],"--check-export")){
  wchar_t path[1024];if(!GetModuleFileNameW(NULL,path,1024))return 7;wchar_t* slash=wcsrchr(path,L'\\');if(!slash)return 7;wcscpy(slash+1,L"StrategicCommanderV5.dll");
  HMODULE module=LoadLibraryW(path);bool valid=module&&GetProcAddress(module,"StrategicCommanderControl");if(module)FreeLibrary(module);return valid?0:8;
 }
 if(argc==2&&!strcmp(argv[1],"--layout")){
  printf("{\"size\":%u,\"binding\":%u,\"request\":%u,\"error\":%u,\"gates\":%u,\"gate_size\":%u,\"audit_size\":%u,\"journal_size\":%u,\"journal_audit\":%u,\"journal_end\":%u,\"flag_audit_size\":%u,\"journal_flags\":%u,\"requested_mask\":%u,\"not_after_frame\":%u,\"journal_intent\":%u,\"journal_binding\":%u}\n",
   (unsigned)sizeof(Shared),(unsigned)offsetof(Shared,binding),(unsigned)offsetof(Shared,request),(unsigned)offsetof(Shared,error),(unsigned)offsetof(Shared,gates),(unsigned)sizeof(GateStatus),
   (unsigned)sizeof(ra3_strategic_manager_enable_candidate_v2::Audit),(unsigned)sizeof(JournalRecord),(unsigned)offsetof(JournalRecord,audit),(unsigned)offsetof(JournalRecord,end),(unsigned)sizeof(FlagAudit),(unsigned)offsetof(JournalRecord,flags),(unsigned)offsetof(Shared,requested_mask),(unsigned)offsetof(Shared,not_after_frame),(unsigned)offsetof(JournalRecord,intent_not_after_frame),(unsigned)offsetof(JournalRecord,binding));return 0;
 }
 if(argc!=2)return 2;char* end=NULL;target=strtoul(argv[1],&end,10);if(!target||!end||*end)return 2;
 EnumWindows(find_window,0);if(!window)return 3;
 wchar_t name[96];swprintf(name,96,L"Local\\RA3StrategicCommanderV5_%lu",target);
 HANDLE mapping=OpenFileMappingW(FILE_MAP_ALL_ACCESS,FALSE,name);if(!mapping)return 4;
 Shared* p=(Shared*)MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Shared));
 if(!p||p->magic!=MAGIC||p->version!=5||p->size!=sizeof(Shared)||p->binding.pid!=target||p->binding.thread!=GetWindowThreadProcessId(window,NULL))return 5;
 HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,target);FILETIME a,b,c,d;
 if(!process||!GetProcessTimes(process,&a,&b,&c,&d)||a.dwLowDateTime!=p->binding.start_low||a.dwHighDateTime!=p->binding.start_high)return 6;
 wchar_t path[32768];DWORD size=32768;
 if(!QueryFullProcessImageNameW(process,0,path,&size)||_wcsicmp(path,L"E:\\RedRar3\\Data\\RA3_1.12.game"))return 6;
 wchar_t dll[1024];if(!GetModuleFileNameW(NULL,dll,1024))return 7;wchar_t* slash=wcsrchr(dll,L'\\');if(!slash)return 7;wcscpy(slash+1,L"StrategicCommanderV5.dll");
 HMODULE library=LoadLibraryW(dll);HOOKPROC callback=NULL;
 if(library){FARPROC function=GetProcAddress(library,"StrategicCommanderControl");memcpy(&callback,&function,sizeof(callback));}
 HHOOK hook=callback?SetWindowsHookExW(WH_GETMESSAGE,callback,library,p->binding.thread):NULL;if(!hook)return 8;
 DWORD started=GetTickCount();
 while(p->phase!=2&&p->phase!=4&&GetTickCount()-started<HARD_WALL_MS+15000){PostMessageW(window,MESSAGE,MAGIC,0);if(GetTickCount()-started>HARD_WALL_MS)p->stop=1;Sleep(25);}
 printf("{\"phase\":%ld,\"error\":%u,\"lease_held\":%u,\"hook_held\":%u,\"cleanup_verified\":%u}\n",p->phase,p->error,p->lease_held,p->hook_held,p->cleanup_verified);
 bool okay=p->phase==2&&!p->active&&!p->lease_held&&!p->hook_held&&!p->applied_mask&&p->cleanup_verified;
 UnhookWindowsHookEx(hook);UnmapViewOfFile(p);CloseHandle(mapping);CloseHandle(process);if(library)FreeLibrary(library);return okay?0:9;
}
