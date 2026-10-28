#include "near_channel.h"
#include <cstdio>
#include <memory>
#include <algorithm>
namespace rt=tacticore::runtime;namespace nc=rt::near_combat;namespace nw=nc::wire;namespace ch=rt::channel;
static nw::Shared* shared=nullptr;static HANDLE mapping=nullptr;static HMODULE pinned=nullptr;
static nc::NativeBootstrap frozen{};static std::unique_ptr<nc::NearRuntime> runtime;
static LONG command_generation=0,near_generation=0;
static ULONGLONG started=0,last_host_pulse=0,last_tick=0;static bool closing=false,fault_latched=false;
static void reason(const char* code){
    if(!shared)return;
    std::memset(shared->movement.reason,0,sizeof(shared->movement.reason));
    std::strncpy(shared->movement.reason,code,sizeof(shared->movement.reason)-1);
}
static bool identity(){
    if(!shared)return false;
    auto& m=shared->movement;
    return m.magic_word==nw::magic&&m.protocol==nw::version&&m.structure_size==sizeof(nw::Shared)&&m.token
        &&nw::same(shared->bootstrap,frozen)&&m.bootstrap==frozen.original
        &&GetCurrentThreadId()==frozen.original.binding.thread&&GetCurrentProcessId()==frozen.original.binding.pid;
}
static void movement_event(const rt::Event& e){if(shared)ch::event_publish(shared->movement,e,0);}
static void trace(const rt::HookTrace& t){if(shared)ch::trace_publish(shared->movement,t);}
static void combat_event(const nc::Result& r,const char* kind,const nc::Observation& o,const nc::Withdrawal* w){
    if(shared)nw::combat_publish(*shared,r,kind,o,w);
}
static void catalogues(){
    auto points=runtime->approved_targets();auto contacts=runtime->visible_contacts();auto& m=shared->movement;
    InterlockedIncrement(&m.targets_generation);MemoryBarrier();
    m.targets_count=static_cast<uint32_t>(std::min<size_t>(64,points.size()));
    std::fill(std::begin(m.approved_targets),std::end(m.approved_targets),rt::Point{});
    for(uint32_t i=0;i<m.targets_count;i++)m.approved_targets[i]=points[i];
    MemoryBarrier();InterlockedIncrement(&m.targets_generation);
    InterlockedIncrement(&shared->contacts_generation);MemoryBarrier();
    shared->contacts_count=static_cast<uint32_t>(std::min<size_t>(nw::contact_capacity,contacts.size()));
    std::fill(std::begin(shared->contacts),std::end(shared->contacts),nc::ContactView{});
    for(uint32_t i=0;i<shared->contacts_count;i++)shared->contacts[i]=contacts[i];
    MemoryBarrier();InterlockedIncrement(&shared->contacts_generation);
}
static void step(){
    if(!runtime||!shared)return;
    auto& m=shared->movement;
    if(fault_latched)return; // Retain the old graph; no automatic retry or new SDK.
    if(!identity()){fault_latched=true;reason("near_channel_binding_changed_unknown");InterlockedExchange(&m.state,static_cast<LONG>(ch::State::Uncertain));return;}
    const auto now=GetTickCount64();
    if(m.stop_requested||now<started||now-started>=150000||now<last_host_pulse||now-last_host_pulse>3000
        ||m.events_overwritten||m.traces_overwritten||shared->combat_overwritten){closing=true;runtime->request_stop();}
    auto observed=runtime->observation();
    InterlockedIncrement(&m.observation_generation);MemoryBarrier();m.current_observation=observed;m.native_last_sequence=runtime->last_sequence();
    MemoryBarrier();InterlockedIncrement(&m.observation_generation);
    if(!closing){runtime->observe_endpoints();catalogues();}
    rt::Command command{};LONG generation=0;
    if(ch::command_snapshot(m,command_generation,command,generation)){
        rt::Receipt receipt{};
        if(closing&&command.operation!=rt::Operation::ReturnHome&&command.operation!=rt::Operation::EmergencyRelease&&command.operation!=rt::Operation::Query){
            receipt=runtime->movement_status();receipt.command=command.command;receipt.task=command.task;receipt.lease=command.lease;
            receipt.sequence=command.sequence;receipt.accepted=false;receipt.reason="near_stopping_no_new_movement";
        }else receipt=runtime->submit(command);
        InterlockedIncrement(&m.command_receipt_generation);MemoryBarrier();m.command_receipt=ch::wire(receipt);
        MemoryBarrier();InterlockedIncrement(&m.command_receipt_generation);command_generation=generation;InterlockedExchange(&m.command_acknowledged,generation);
    }
    nw::NearCommand attack{};
    if(nw::command_snapshot(*shared,near_generation,attack,generation)){
        nc::Result receipt;
        if(closing){
            receipt=runtime->combat_status();receipt.command=attack.intent.command;receipt.task=attack.intent.task;receipt.lease=attack.intent.lease;
            receipt.sequence=attack.intent.sequence;receipt.accepted=false;receipt.held=runtime->movement_status().held;receipt.reason="near_stopping_no_new_attack";
        }else receipt=runtime->submit(attack.intent,attack.original_return);
        InterlockedIncrement(&shared->near_command_receipt_generation);MemoryBarrier();shared->near_command_receipt=nw::pack(receipt);
        MemoryBarrier();InterlockedIncrement(&shared->near_command_receipt_generation);near_generation=generation;
        InterlockedExchange(&shared->near_command_acknowledged,generation);
    }
    runtime->tick();auto movement=runtime->movement_status();auto combat=runtime->combat_status();
    ch::receipt_publish(m,movement);nw::result_publish(*shared,combat);
    if(movement.phase==rt::Phase::Uncertain||combat.phase==nc::Phase::Uncertain){
        fault_latched=true;reason("near_native_result_requires_reconciliation");InterlockedExchange(&m.state,static_cast<LONG>(ch::State::Uncertain));
    }
    if(closing&&!movement.held&&!combat.held){
        if(runtime->close_verified()){
            m.hooks_restored=runtime->restored_mask();runtime.reset();reason("near_hooks_and_control_released");
            InterlockedExchange(&m.state,static_cast<LONG>(ch::State::Released));
        }else{reason("near_hook_restore_pending");InterlockedExchange(&m.state,static_cast<LONG>(ch::State::Uncertain));}
    }
}
static void bootstrap(uint32_t token){
    if(runtime||(shared&&shared->movement.state==static_cast<LONG>(ch::State::Uncertain)&&!shared->movement.hooks_restored))return;
    wchar_t name[100]{};std::swprintf(name,100,L"Local\\TacticoreNear2_%lu_%u",GetCurrentProcessId(),token);
    auto candidate_mapping=OpenFileMappingW(FILE_MAP_ALL_ACCESS,FALSE,name);if(!candidate_mapping)return;
    auto* candidate=static_cast<nw::Shared*>(MapViewOfFile(candidate_mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(nw::Shared)));
    if(!candidate){CloseHandle(candidate_mapping);return;}
    auto& m=candidate->movement;
    if(m.magic_word!=nw::magic||m.protocol!=nw::version||m.structure_size!=sizeof(nw::Shared)||m.token!=token||m.state!=0
        ||candidate->bootstrap.schema!=2||!(m.bootstrap==candidate->bootstrap.original)
        ||m.bootstrap.binding.pid!=GetCurrentProcessId()||m.bootstrap.binding.thread!=GetCurrentThreadId()){
        UnmapViewOfFile(candidate);CloseHandle(candidate_mapping);return;
    }
    if(shared){UnmapViewOfFile(shared);CloseHandle(mapping);}
    shared=candidate;mapping=candidate_mapping;frozen=shared->bootstrap;command_generation=near_generation=0;closing=fault_latched=false;
    m.callback_thread=GetCurrentThreadId();started=last_host_pulse=GetTickCount64();last_tick=0;
    InterlockedExchange(&m.state,static_cast<LONG>(ch::State::Initializing));
    if(!pinned&&!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,reinterpret_cast<LPCWSTR>(&bootstrap),&pinned)){
        reason("near_module_pin_failed");m.hooks_restored=1;InterlockedExchange(&m.state,static_cast<LONG>(ch::State::Refused));return;
    }
    try{
        runtime=nc::create_near_runtime(frozen,movement_event,trace,combat_event);m.admitted_actor=runtime->actor();
        reason("near_runtime_ready_no_actor_borrowed");InterlockedExchange(&m.state,static_cast<LONG>(ch::State::Active));
    }catch(const rt::FactoryError& e){reason(e.what());m.hooks_restored=e.safe_no_hooks?1:0;InterlockedExchange(&m.state,static_cast<LONG>(e.safe_no_hooks?ch::State::Refused:ch::State::Uncertain));}
    catch(...){reason("near_factory_unknown");InterlockedExchange(&m.state,static_cast<LONG>(ch::State::Uncertain));}
}
extern "C" __declspec(dllexport) LRESULT CALLBACK TacticoreNearControl(int code,WPARAM wp,LPARAM lp){
    if(code>=0&&wp==PM_REMOVE&&lp){auto* message=reinterpret_cast<MSG*>(lp);
        if(message->message==nw::bootstrap_message&&message->wParam==nw::magic&&message->lParam)bootstrap(static_cast<uint32_t>(message->lParam));
        auto* current=shared;
        if(current&&GetCurrentThreadId()==frozen.original.binding.thread){
            auto& m=current->movement;InterlockedIncrement(&m.active_callbacks);
            if(message->message==nw::pulse_message&&message->wParam==m.token){
                LONG nonce=static_cast<LONG>(message->lParam);if(nonce>0&&m.pulse_requested==nonce){last_host_pulse=GetTickCount64();InterlockedExchange(&m.pulse_acknowledged,nonce);}
            }
            auto now=GetTickCount64();if(now-last_tick>=80){last_tick=now;
                try{step();}catch(...){fault_latched=true;reason("near_callback_unknown");InterlockedExchange(&m.state,static_cast<LONG>(ch::State::Uncertain));}}
            InterlockedDecrement(&m.active_callbacks);
        }
    }
    return CallNextHookEx(nullptr,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD why,LPVOID){if(why==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(module);return TRUE;}
