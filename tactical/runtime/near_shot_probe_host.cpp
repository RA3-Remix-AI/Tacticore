#include "near_shot_probe.h"
#include <cstdio>
#include <cwchar>
#include <cstdlib>
namespace np=tacticore::runtime::shot_probe;
static DWORD target_pid=0;static HWND target_window=nullptr;static unsigned found=0;
static BOOL CALLBACK enumerate(HWND window,LPARAM){DWORD pid=0;GetWindowThreadProcessId(window,&pid);if(pid==target_pid&&IsWindowVisible(window)&&!GetWindow(window,GW_OWNER)){target_window=window;found++;}return TRUE;}
int main(int argc,char**argv){
    if(argc==2&&!std::strcmp(argv[1],"--layout")){
        std::printf("{\"bootstrap\":%u,\"row\":%u,\"shared\":%u,\"rows_offset\":%u,\"capacity\":%u,\"bootstrap_offset\":%u,\"restore_mask\":%u}\n",unsigned(sizeof(np::Bootstrap)),unsigned(sizeof(np::Row)),unsigned(sizeof(np::Shared)),unsigned(offsetof(np::Shared,rows)),np::capacity,unsigned(offsetof(np::Shared,bootstrap)),np::restore_mask);return 0;}
    if(argc!=3){return 2;}char*end=nullptr;target_pid=std::strtoul(argv[1],&end,10);if(!target_pid||!end||*end)return 2;
    uint32_t token=std::strtoul(argv[2],&end,10);if(!token||!end||*end)return 2;
    wchar_t mutex_name[100]{};std::swprintf(mutex_name,100,L"Local\\TacticoreShotExclusive_%lu",target_pid);
    HANDLE exclusive=CreateMutexW(nullptr,FALSE,mutex_name);if(!exclusive||WaitForSingleObject(exclusive,0)!=WAIT_OBJECT_0)return 3;
    wchar_t name[100]{};std::swprintf(name,100,L"Local\\TacticoreShot1_%lu_%u",target_pid,token);
    HANDLE mapping=OpenFileMappingW(FILE_MAP_ALL_ACCESS,FALSE,name);if(!mapping)return 4;
    auto s=static_cast<np::Shared*>(MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(np::Shared)));if(!s)return 5;auto boot=s->bootstrap;
    if(s->magic_word!=np::magic||s->protocol!=np::version||s->structure_size!=sizeof(np::Shared)||s->token!=token||s->state!=0||boot.binding.pid!=target_pid||boot.duration_ms<1000||boot.duration_ms>90000)return 6;
    HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,target_pid);FILETIME c{},e{},k{},u{};DWORD status=0;
    if(!process||!GetProcessTimes(process,&c,&e,&k,&u)||!GetExitCodeProcess(process,&status)||status!=STILL_ACTIVE||((uint64_t(c.dwHighDateTime)<<32)|c.dwLowDateTime)!=boot.binding.process_start)return 7;
    wchar_t game[32768]{};DWORD game_size=32768;if(!QueryFullProcessImageNameW(process,0,game,&game_size))return 7;
    auto basename=std::wcsrchr(game,L'\\');if(!basename||_wcsicmp(basename+1,L"RA3_1.12.game"))return 7;
    EnumWindows(enumerate,0);if(found!=1||GetWindowThreadProcessId(target_window,nullptr)!=boot.binding.thread)return 8;
    wchar_t dll[32768]{};GetModuleFileNameW(nullptr,dll,32768);auto slash=std::wcsrchr(dll,L'\\');if(!slash)return 9;std::wcscpy(slash+1,L"TacticoreShotProbe.dll");
    HMODULE module=LoadLibraryW(dll);HOOKPROC callback=nullptr;if(module){auto address=GetProcAddress(module,"TacticoreShotControl");std::memcpy(&callback,&address,sizeof(callback));}
    auto hook=callback?SetWindowsHookExW(WH_GETMESSAGE,callback,module,boot.binding.thread):nullptr;if(!hook)return 10;
    if(!PostMessageW(target_window,np::bootstrap_message,np::magic,token))return 11;
    auto began=GetTickCount64();LONG nonce=0;
    while(!np::closed(*s)&&GetTickCount64()-began<boot.duration_ms+5000){
        if(!np::same(s->bootstrap,boot))InterlockedExchange(&s->stop,1);
        if(!GetExitCodeProcess(process,&status)||status!=STILL_ACTIVE)break;
        auto next=++nonce;InterlockedExchange(&s->pulse_requested,next);
        if(!PostMessageW(target_window,np::pulse_message,token,next)){break;}Sleep(100);
    }
    if(!np::closed(*s)){InterlockedExchange(&s->stop,1);auto deadline=GetTickCount64()+10000;while(!np::closed(*s)&&GetTickCount64()<deadline){PostMessageW(target_window,np::pulse_message,token,++nonce);Sleep(100);}}
    bool safe=np::closed(*s);std::printf("{\"state\":%ld,\"error\":%ld,\"active\":%ld,\"rows\":%ld,\"overflow\":%ld,\"callback_thread\":%u,\"closed\":%s,\"hooks_restored\":%u,\"installed_count\":%u,\"module_game_sdk_calls\":0,\"game_entry_detours\":3}\n",s->state,s->error,s->active,s->count,s->overflow,s->callback_thread,safe?"true":"false",s->hooks_restored,s->installed_count);std::fflush(stdout);
    UnhookWindowsHookEx(hook);UnmapViewOfFile(s);CloseHandle(mapping);CloseHandle(process);ReleaseMutex(exclusive);CloseHandle(exclusive);if(module)FreeLibrary(module);
    return safe?0:13;
}
