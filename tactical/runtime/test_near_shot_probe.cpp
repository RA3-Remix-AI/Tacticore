// Actual x86 DLL refusal in this owned non-game process, not a game attach.
#include "near_shot_probe.h"
#include <cstdio>
#include <cwchar>
namespace np=tacticore::runtime::shot_probe;
int main(int argc,char**argv){
    if(argc!=2)return 2;
    auto storage=std::make_unique<np::Shared>();auto&closed=*storage;closed.state=3;closed.hooks_restored=7;if(!np::closed(closed))return 3;
    closed.active=1;if(np::closed(closed))return 4;closed.active=0;closed.hooks_restored=3;if(np::closed(closed))return 5;
    closed.state=5;closed.hooks_restored=7;if(np::closed(closed))return 6;
    closed.state=4;closed.hooks_restored=1;closed.installed_count=1;if(np::closed(closed))return 7;
    closed.installed_count=0;if(!np::closed(closed))return 8;
    auto pid=GetCurrentProcessId(),token=GetTickCount()&0x7fffffff;wchar_t name[100]{};std::swprintf(name,100,L"Local\\TacticoreShot1_%lu_%lu",pid,token);
    auto mapping=CreateFileMappingW(INVALID_HANDLE_VALUE,nullptr,PAGE_READWRITE,0,sizeof(np::Shared),name);if(!mapping||GetLastError()==ERROR_ALREADY_EXISTS)return 9;
    auto shared=static_cast<np::Shared*>(MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(np::Shared)));if(!shared)return 10;
    auto initial=std::make_unique<np::Shared>();std::memcpy(shared,initial.get(),sizeof(*initial));shared->token=token;shared->bootstrap.binding.pid=pid;shared->bootstrap.binding.thread=GetCurrentThreadId();shared->bootstrap.duration_ms=1000;
    auto module=LoadLibraryA(argv[1]);if(!module)return 11;auto address=GetProcAddress(module,"TacticoreShotControl");HOOKPROC callback=nullptr;std::memcpy(&callback,&address,sizeof(callback));if(!callback)return 12;
    MSG message{};message.message=np::bootstrap_message;message.wParam=np::magic;message.lParam=token;callback(0,PM_REMOVE,reinterpret_cast<LPARAM>(&message));
    if(shared->state!=4||shared->error!=10||shared->hooks_restored!=1||shared->installed_count||shared->active||!np::closed(*shared))return 13;
    std::puts("7 passive shot probe boundary groups passed; owned non-game process, no hooks or SDK");return 0;
}
