#include "shared_channel.h"
#include "native_factory.h"
#include <cstdio>
#include <memory>
#include <algorithm>

namespace rt=tacticore::runtime;
namespace ch=rt::channel;
static ch::SharedChannel* shared=nullptr;
static HANDLE mapping=nullptr;
static HMODULE pinned=nullptr;
static ch::Bootstrap frozen{};
static std::unique_ptr<rt::NativeRuntime> runtime;
static LONG command_generation=0;
static ULONGLONG last_host_pulse=0,last_tick=0;
static bool closing=false;

static void reason(const char* code){
    if(!shared)return;
    std::memset(shared->reason,0,sizeof(shared->reason));
    std::strncpy(shared->reason,code,sizeof(shared->reason)-1);
}
static void event(const rt::Event& value){if(shared)ch::event_publish(*shared,value,0);}
static void trace(const rt::HookTrace& value){if(shared)ch::trace_publish(*shared,value);}
static bool identity(){
    return shared&&shared->magic_word==ch::magic&&shared->protocol==ch::version&&shared->structure_size==sizeof(ch::SharedChannel)
        &&shared->token&&shared->bootstrap==frozen&&GetCurrentThreadId()==frozen.binding.thread&&GetCurrentProcessId()==frozen.binding.pid;
}
static void publish_targets(){
    auto targets=runtime->approved_targets();
    InterlockedIncrement(&shared->targets_generation);MemoryBarrier();
    shared->targets_count=static_cast<uint32_t>(std::min<size_t>(64,targets.size()));
    std::fill(std::begin(shared->approved_targets),std::end(shared->approved_targets),rt::Point{});
    for(uint32_t i=0;i<shared->targets_count;i++)shared->approved_targets[i]=targets[i];
    MemoryBarrier();InterlockedIncrement(&shared->targets_generation);
}
static void step(){
    if(!runtime||!shared)return;
    if(!identity()){
        reason("channel_binding_changed_unknown");InterlockedExchange(&shared->state,static_cast<LONG>(ch::State::Uncertain));
        // Do not follow edited addresses or discard the private old owner.
        return;
    }
    if(shared->stop_requested||GetTickCount64()-last_host_pulse>3000){closing=true;runtime->controller().request_stop();}
    auto observation=runtime->observation();
    InterlockedIncrement(&shared->observation_generation);MemoryBarrier();shared->current_observation=observation;
    shared->native_last_sequence=runtime->controller().last_sequence();MemoryBarrier();InterlockedIncrement(&shared->observation_generation);
    if(!closing){runtime->observe_endpoints();publish_targets();}
    rt::Command command{};LONG generation=0;
    if(ch::command_snapshot(*shared,command_generation,command,generation)){
        rt::Receipt receipt{};
        if(closing&&command.operation!=rt::Operation::ReconcileRelease&&command.operation!=rt::Operation::Query){
            receipt=runtime->controller().status();receipt.command=command.command;receipt.task=command.task;
            receipt.lease=command.lease;receipt.sequence=command.sequence;receipt.accepted=false;receipt.reason="runtime_stopping_no_new_action";
        }else receipt=runtime->controller().submit(command);
        InterlockedIncrement(&shared->command_receipt_generation);MemoryBarrier();shared->command_receipt=ch::wire(receipt);
        MemoryBarrier();InterlockedIncrement(&shared->command_receipt_generation);
        command_generation=generation;InterlockedExchange(&shared->command_acknowledged,generation);
    }
    auto receipt=runtime->controller().tick();ch::receipt_publish(*shared,receipt);
    if(receipt.phase==rt::Phase::Uncertain){
        reason("native_result_requires_reconciliation");InterlockedExchange(&shared->state,static_cast<LONG>(ch::State::Uncertain));
        // A new explicit reconciliation command may be admitted later. Nothing
        // here resends a previous SDK call or releases an unknown actor claim.
    }
    if(closing&&!receipt.held){
        if(runtime->close_verified()){
            shared->hooks_restored=runtime->restored_mask();runtime.reset();
            reason("native_hooks_and_control_released");InterlockedExchange(&shared->state,static_cast<LONG>(ch::State::Released));
        }else{
            reason("native_hooks_restore_pending");InterlockedExchange(&shared->state,static_cast<LONG>(ch::State::Uncertain));
        }
    }
}
static void bootstrap(uint32_t token){
    // Existing uncertain/held ownership is never displaced by another channel.
    if(runtime||(shared&&shared->state==static_cast<LONG>(ch::State::Uncertain)&&!shared->hooks_restored))return;
    char name[100]{};std::snprintf(name,sizeof(name),"Local\\TacticoreRuntime1_%lu_%u",GetCurrentProcessId(),token);
    HANDLE candidate_mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);
    if(!candidate_mapping)return;
    auto* candidate=static_cast<ch::SharedChannel*>(MapViewOfFile(candidate_mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(ch::SharedChannel)));
    if(!candidate){CloseHandle(candidate_mapping);return;}
    if(candidate->magic_word!=ch::magic||candidate->protocol!=ch::version||candidate->structure_size!=sizeof(ch::SharedChannel)
        ||candidate->token!=token||candidate->state!=0||candidate->bootstrap.binding.pid!=GetCurrentProcessId()
        ||candidate->bootstrap.binding.thread!=GetCurrentThreadId()){
        UnmapViewOfFile(candidate);CloseHandle(candidate_mapping);return;
    }
    if(shared){UnmapViewOfFile(shared);CloseHandle(mapping);}
    shared=candidate;mapping=candidate_mapping;frozen=shared->bootstrap;command_generation=0;closing=false;
    shared->callback_thread=GetCurrentThreadId();last_host_pulse=GetTickCount64();last_tick=0;
    InterlockedExchange(&shared->state,static_cast<LONG>(ch::State::Initializing));
    if(!pinned&&!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,
        reinterpret_cast<LPCSTR>(&bootstrap),&pinned)){
        reason("runtime_module_pin_failed");shared->hooks_restored=1;
        InterlockedExchange(&shared->state,static_cast<LONG>(ch::State::Refused));return;
    }
    try{
        runtime=rt::create_runtime(frozen,event,trace);shared->admitted_actor=runtime->actor();
        reason("runtime_ready_no_actor_borrowed");InterlockedExchange(&shared->state,static_cast<LONG>(ch::State::Active));
    }catch(const rt::FactoryError& error){
        reason(error.what());shared->hooks_restored=error.safe_no_hooks?1:0;
        InterlockedExchange(&shared->state,static_cast<LONG>(error.safe_no_hooks?ch::State::Refused:ch::State::Uncertain));
    }catch(...){reason("runtime_factory_unknown");InterlockedExchange(&shared->state,static_cast<LONG>(ch::State::Uncertain));}
}
extern "C" __declspec(dllexport) LRESULT CALLBACK TacticoreRuntimeControl(int code,WPARAM wp,LPARAM lp){
    if(code>=0&&wp==PM_REMOVE&&lp){
        auto* message=reinterpret_cast<MSG*>(lp);
        if(message->message==ch::bootstrap_message&&message->wParam==ch::magic&&message->lParam)
            bootstrap(static_cast<uint32_t>(message->lParam));
        auto* current=shared;
        if(current&&GetCurrentThreadId()==frozen.binding.thread){
            InterlockedIncrement(&current->active_callbacks);
            if(message->message==ch::pulse_message&&message->wParam==current->token){
                LONG nonce=static_cast<LONG>(message->lParam);
                if(nonce>0&&current->pulse_requested==nonce){last_host_pulse=GetTickCount64();InterlockedExchange(&current->pulse_acknowledged,nonce);}
            }
            auto now=GetTickCount64();
            if(now-last_tick>=80){last_tick=now;try{step();}catch(...){reason("runtime_callback_unknown");InterlockedExchange(&current->state,static_cast<LONG>(ch::State::Uncertain));}}
            InterlockedDecrement(&current->active_callbacks);
        }
    }
    return CallNextHookEx(nullptr,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD why,LPVOID){if(why==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(module);return TRUE;}
