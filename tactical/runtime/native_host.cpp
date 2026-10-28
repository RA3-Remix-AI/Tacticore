// The helper only transports messages. All actor admission and SDK calls occur
// independently inside the pinned target game thread.
#include "shared_channel.h"
#include <wincrypt.h>
#include <cstdio>
#include <cstdlib>
#include <cerrno>
#include <climits>

namespace ch=tacticore::runtime::channel;
static DWORD wanted_pid=0;
static HWND game_window=nullptr;
static unsigned windows_found=0;
static BOOL CALLBACK find_window(HWND candidate,LPARAM){
    DWORD pid=0;GetWindowThreadProcessId(candidate,&pid);
    if(pid==wanted_pid&&IsWindowVisible(candidate)&&!GetWindow(candidate,GW_OWNER)){game_window=candidate;windows_found++;}
    return TRUE;
}
static bool number(const char* text,uint32_t& value){
    if(!text||!*text||*text=='-')return false;
    char* end=nullptr;errno=0;unsigned long parsed=std::strtoul(text,&end,10);
    if(errno||!end||*end||!parsed||parsed>UINT32_MAX)return false;
    value=static_cast<uint32_t>(parsed);return true;
}
static bool game_identity(const tacticore::runtime::Binding& binding){
    HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,binding.pid);
    if(!process)return false;
    FILETIME created{},exit{},kernel{},user{};DWORD code=0;
    bool valid=GetProcessTimes(process,&created,&exit,&kernel,&user)&&GetExitCodeProcess(process,&code)&&code==STILL_ACTIVE
        &&((static_cast<uint64_t>(created.dwHighDateTime)<<32)|created.dwLowDateTime)==binding.process_start;
    char path[32768]{};DWORD length=sizeof(path);
    valid=valid&&QueryFullProcessImageNameA(process,0,path,&length);CloseHandle(process);
    const char* name=std::strrchr(path,'\\');
    if(!valid||!name||_stricmp(name+1,"ra3_1.12.game"))return false;
    HANDLE file=CreateFileA(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;
    HCRYPTPROV provider=0;HCRYPTHASH hash=0;bool okay=false;
    if(CryptAcquireContextA(&provider,nullptr,nullptr,PROV_RSA_AES,CRYPT_VERIFYCONTEXT)&&CryptCreateHash(provider,CALG_SHA_256,0,0,&hash)){
        BYTE buffer[65536]{};DWORD received=0;BOOL result=TRUE;
        while((result=ReadFile(file,buffer,sizeof(buffer),&received,nullptr))&&received)
            if(!CryptHashData(hash,buffer,received,0)){result=FALSE;break;}
        BYTE digest[32]{};DWORD size=sizeof(digest);char hex[65]{};
        if(result&&CryptGetHashParam(hash,HP_HASHVAL,digest,&size,0)){
            for(unsigned i=0;i<32;i++)std::sprintf(hex+i*2,"%02x",digest[i]);
            okay=!std::strcmp(hex,"ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165");
        }
    }
    if(hash)CryptDestroyHash(hash);
    if(provider)CryptReleaseContext(provider,0);
    CloseHandle(file);return okay;
}
static bool terminal(ch::SharedChannel& channel){
    auto state=static_cast<ch::State>(channel.state);
    return (state==ch::State::Refused||state==ch::State::Released)&&channel.hooks_restored
        &&channel.active_callbacks==0&&channel.receipt.held==0;
}
static void layout(){
    std::printf("{\"schema_version\":1,\"protocol\":%u,\"shared\":%u,\"bootstrap\":%u,\"command\":%u,\"wire_receipt\":%u,\"event\":%u,\"command_offset\":%u,\"receipt_offset\":%u,\"events_offset\":%u,\"hook_trace\":%u,\"trace_capacity\":%u,\"traces_offset\":%u}\n",
        ch::version,static_cast<unsigned>(sizeof(ch::SharedChannel)),static_cast<unsigned>(sizeof(ch::Bootstrap)),
        static_cast<unsigned>(sizeof(tacticore::runtime::Command)),static_cast<unsigned>(sizeof(ch::WireReceipt)),
        static_cast<unsigned>(sizeof(ch::WireEvent)),static_cast<unsigned>(offsetof(ch::SharedChannel,command)),
        static_cast<unsigned>(offsetof(ch::SharedChannel,receipt)),static_cast<unsigned>(offsetof(ch::SharedChannel,events)),
        static_cast<unsigned>(sizeof(ch::WireHookTrace)),ch::trace_capacity,static_cast<unsigned>(offsetof(ch::SharedChannel,traces)));
}
int main(int argc,char** argv){
    if(argc==2&&!std::strcmp(argv[1],"--layout")){layout();return 0;}
    uint32_t pid=0,token=0;
    if(argc!=3||!number(argv[1],pid)||!number(argv[2],token))return 2;
    char mapping_name[100]{};std::snprintf(mapping_name,sizeof(mapping_name),"Local\\TacticoreRuntime1_%u_%u",pid,token);
    HANDLE mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,mapping_name);
    if(!mapping)return 3;
    auto* shared=static_cast<ch::SharedChannel*>(MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(ch::SharedChannel)));
    if(!shared){CloseHandle(mapping);return 4;}
    const auto frozen=shared->bootstrap;
    if(shared->magic_word!=ch::magic||shared->protocol!=ch::version||shared->structure_size!=sizeof(ch::SharedChannel)
        ||shared->token!=token||frozen.binding.pid!=pid||shared->state!=0||!game_identity(frozen.binding))return 5;
    wanted_pid=pid;EnumWindows(find_window,0);
    if(windows_found!=1||GetWindowThreadProcessId(game_window,nullptr)!=frozen.binding.thread)return 6;
    char dll[MAX_PATH]{};if(!GetModuleFileNameA(nullptr,dll,sizeof(dll)))return 7;
    char* slash=std::strrchr(dll,'\\');if(!slash||static_cast<size_t>(slash-dll)+sizeof("TacticoreRuntime1.dll")>=sizeof(dll))return 7;
    std::strcpy(slash+1,"TacticoreRuntime1.dll");
    HMODULE module=LoadLibraryA(dll);HOOKPROC callback=nullptr;
    if(module){FARPROC entry=GetProcAddress(module,"TacticoreRuntimeControl");std::memcpy(&callback,&entry,sizeof(callback));}
    HHOOK hook=callback?SetWindowsHookExA(WH_GETMESSAGE,callback,module,frozen.binding.thread):nullptr;
    if(!hook)return 8;
    bool posted=PostMessageA(game_window,ch::bootstrap_message,ch::magic,token);
    ULONGLONG start=GetTickCount64(),last_post=0,ack_started=0;
    LONG nonce=0,pending=0;bool stopping=false;
    while(posted&&!terminal(*shared)&&GetTickCount64()-start<180000){
        ULONGLONG now=GetTickCount64();
        if(!(shared->bootstrap==frozen)||shared->token!=token||shared->protocol!=ch::version){InterlockedExchange(&shared->stop_requested,1);stopping=true;}
        if(pending&&shared->pulse_acknowledged==pending){pending=0;ack_started=0;}
        if(pending&&now-ack_started>3000){InterlockedExchange(&shared->stop_requested,1);stopping=true;}
        if(!pending&&now-last_post>=100){
            if(nonce==LONG_MAX){InterlockedExchange(&shared->stop_requested,1);break;}
            pending=++nonce;last_post=ack_started=now;
            InterlockedExchange(&shared->pulse_requested,pending);
            if(!PostMessageA(game_window,ch::pulse_message,token,pending)){InterlockedExchange(&shared->stop_requested,1);break;}
        }
        if(stopping&&now-start>170000)break;
        Sleep(10);
    }
    if(!terminal(*shared)){
        InterlockedExchange(&shared->stop_requested,1);
        auto deadline=GetTickCount64()+10000;
        while(!terminal(*shared)&&GetTickCount64()<deadline){PostMessageA(game_window,ch::pulse_message,token,0);Sleep(100);}
    }
    bool safe=terminal(*shared);
    std::printf("{\"schema_version\":1,\"state\":%ld,\"safe_terminal\":%s,\"physical_home\":%u,\"control_released\":%u,\"hooks_restored\":%u,\"active_callbacks\":%ld,\"events_overwritten\":%ld}\n",
        shared->state,safe?"true":"false",shared->receipt.physical_home,shared->receipt.control_released,
        shared->hooks_restored,shared->active_callbacks,shared->events_overwritten);std::fflush(stdout);
    // The target DLL pins itself and owns its own mapping view. Even an unknown
    // result here cannot unload its inner hooks or discard the target's lease.
    UnhookWindowsHookEx(hook);UnmapViewOfFile(shared);CloseHandle(mapping);if(module)FreeLibrary(module);
    return safe?0:9;
}
