#include "bridge.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
static DWORD target_pid;
static HWND found_window;
static BOOL CALLBACK find_window(HWND window,LPARAM) {
    DWORD pid=0;GetWindowThreadProcessId(window,&pid);
    if(pid==target_pid && IsWindowVisible(window) && !GetWindow(window,GW_OWNER)) {found_window=window;return FALSE;}
    return TRUE;
}
int main(int argc,char** argv) {
    if(argc<3) {fprintf(stderr,"usage: controller PID ping | read THING | move THING OWNER HASH X Y Z\n");return 2;}
    target_pid=strtoul(argv[1],NULL,10);
    if(!target_pid) return 2;
    uint32_t operation=!strcmp(argv[2],"ping")?0:!strcmp(argv[2],"read")?1:!strcmp(argv[2],"move")?2:99;
    if(operation==99 || (operation==1 && argc!=4) || (operation==2 && argc!=9)) return 2;
    HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,target_pid);
    char executable[32768]; DWORD length=sizeof(executable);
    if(!process || !QueryFullProcessImageNameA(process,0,executable,&length)) return 3;
    CloseHandle(process);
    const char* basename=strrchr(executable,'\\');
    if(!basename || _stricmp(basename+1,"ra3_1.12.game")) return 3;
    EnumWindows(find_window,0);
    if(!found_window) {fprintf(stderr,"No visible game window\n");return 3;}
    DWORD thread=GetWindowThreadProcessId(found_window,NULL);
    char name[80];snprintf(name,sizeof(name),"Local\\RA3BridgeProbe_%lu",target_pid);
    HANDLE mapping=CreateFileMappingA(INVALID_HANDLE_VALUE,NULL,PAGE_READWRITE,0,sizeof(Request),name);
    if(!mapping || GetLastError()==ERROR_ALREADY_EXISTS) {fprintf(stderr,"Mapping busy\n");return 4;}
    Request* r=(Request*)MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Request));
    if(!r) return 4;
    memset(r,0,sizeof(*r));r->magic=BRIDGE_MAGIC;r->operation=operation;
    if(operation) r->thing=strtoul(argv[3],NULL,0);
    if(operation==2) {
        r->owner=strtoul(argv[4],NULL,0);r->hash=strtoul(argv[5],NULL,0);
        for(int i=0;i<3;i++) { char* end=NULL;r->target[i]=strtof(argv[6+i],&end);if(!end || *end || !isfinite(r->target[i])) return 2; }
    }
    char dll[MAX_PATH];GetModuleFileNameA(NULL,dll,sizeof(dll));
    char* slash=strrchr(dll,'\\');if(!slash) return 5;strcpy(slash+1,"bridge.dll");
    HMODULE module=LoadLibraryA(dll);
    HOOKPROC callback=NULL;
    if(module) {FARPROC symbol=GetProcAddress(module,"BridgeHook");static_assert(sizeof(callback)==sizeof(symbol));memcpy(&callback,&symbol,sizeof(callback));}
    if(!callback) {fprintf(stderr,"DLL/export load failed %lu\n",GetLastError());return 5;}
    HHOOK hook=SetWindowsHookExA(WH_GETMESSAGE,callback,module,thread);
    if(!hook) {fprintf(stderr,"Hook failed %lu\n",GetLastError());return 6;}
    PostMessageA(found_window,BRIDGE_MESSAGE,0,0);
    DWORD started=GetTickCount();while(r->done!=1 && GetTickCount()-started<10000) Sleep(10);
    bool completed=r->done==1;
    if(completed) printf("{\"operation\":%u,\"result\":%u,\"window_thread\":%lu,\"callback_thread\":%u,\"owner\":\"0x%08x\",\"hash\":\"0x%08x\",\"ai\":\"0x%08x\",\"hp\":%.3f,\"before\":[%.4f,%.4f,%.4f]}\n",operation,r->result,thread,r->thread,r->actual_owner,r->actual_hash,r->ai,r->hp,r->before[0],r->before[1],r->before[2]);
    else fprintf(stderr,"Callback timeout; request outcome unknown\n");
    // Keep destination storage mapped briefly after an experimental move.
    if(completed && r->result==2) Sleep(3000);
    UnhookWindowsHookEx(hook);
    bool ok=completed && (r->result==1 || r->result==2);
    UnmapViewOfFile(r);CloseHandle(mapping);FreeLibrary(module);
    return ok?0:7;
}

