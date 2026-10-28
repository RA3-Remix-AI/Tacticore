#pragma once
// Separate version2 transport. Active runtime1 memory/layout and names do not
// change. This transport is not a published capability or a model grant.
#include "near_native_factory.h"
#include <type_traits>

namespace tacticore::runtime::near_combat::wire {
constexpr uint32_t magic=0x544e5232,version=2,combat_capacity=512,contact_capacity=64;
constexpr UINT bootstrap_message=WM_APP+0x3e1,pulse_message=WM_APP+0x3e2;
inline bool same(const NativeBootstrap& a,const NativeBootstrap& b){
    return a.schema==b.schema&&a.original==b.original
        &&!std::memcmp(a.mod_path,b.mod_path,sizeof(a.mod_path))
        &&!std::memcmp(a.visibility_path,b.visibility_path,sizeof(a.visibility_path))
        &&!std::memcmp(a.template_audit_path,b.template_audit_path,sizeof(a.template_audit_path));
}
struct NearCommand {Intent intent{};Command original_return{};};
inline bool same(const NearCommand& a,const NearCommand& b){return a.intent==b.intent&&a.original_return==b.original_return;}
struct WireResult {
    Id command{},task{},lease{};uint64_t sequence=0,monotonic_ms=0;
    uint32_t phase=0,frame=0,attack_attempts=0,withdrawal_requests=0,accepted=0,
        attributed_hit=0,physical_home=0,control_released=0,stance_restored=0,held=0,cancelled=0,task_completed=0;
    float attributed_damage=0;char reason[96]{};
};
inline WireResult pack(const Result& r){
    WireResult w;w.command=r.command;w.task=r.task;w.lease=r.lease;w.sequence=r.sequence;w.monotonic_ms=r.monotonic_ms;
    w.phase=static_cast<uint32_t>(r.phase);w.frame=r.frame;w.attack_attempts=r.attack_attempts;w.withdrawal_requests=r.withdrawal_requests;
    w.accepted=r.accepted;w.attributed_hit=r.attributed_hit;w.physical_home=r.physical_home;w.control_released=r.control_released;
    w.stance_restored=r.stance_restored;w.held=r.held;w.cancelled=r.cancelled;w.task_completed=r.task_completed;w.attributed_damage=r.attributed_damage;
    if(r.reason)std::strncpy(w.reason,r.reason,sizeof(w.reason)-1);
    return w;
}
struct WireCombatEvent {
    volatile LONG ticket=0;uint32_t withdrawal_present=0;char event_type[48]{};
    WireResult result{};Observation observation{};Withdrawal withdrawal{};
};
struct Shared {
    channel::SharedChannel movement{};
    NativeBootstrap bootstrap{};
    volatile LONG near_command_generation=0,near_command_acknowledged=0;
    NearCommand near_command{};
    volatile LONG near_command_receipt_generation=0;WireResult near_command_receipt{};
    volatile LONG near_receipt_generation=0;WireResult near_receipt{};
    volatile LONG contacts_generation=0;uint32_t contacts_count=0;ContactView contacts[contact_capacity]{};
    volatile LONG combat_written=0,combat_overwritten=0;WireCombatEvent combat[combat_capacity]{};
    Shared(){movement.magic_word=magic;movement.protocol=version;movement.structure_size=sizeof(Shared);}
};
static_assert(std::is_trivially_copyable<NativeBootstrap>::value,"Bootstrap is a value ABI");
static_assert(std::is_trivially_copyable<NearCommand>::value,"Commands hold no native references");
static_assert(std::is_trivially_copyable<WireResult>::value,"Result replaces local reason pointer with fixed text");
static_assert(std::is_standard_layout<Shared>::value,"Offsets require standard layout");
inline bool terminal(const Shared& s){
    const auto& m=s.movement;
    const bool closed=m.state==static_cast<LONG>(channel::State::Released)&&m.hooks_restored==32767;
    const bool refused=m.state==static_cast<LONG>(channel::State::Refused)&&m.hooks_restored==1;
    return (closed||refused)&&m.active_callbacks==0&&m.receipt.held==0&&s.near_receipt.held==0;
}
inline bool command_snapshot(Shared& s,LONG last,NearCommand& output,LONG& generation){
    LONG first=InterlockedCompareExchange(&s.near_command_generation,0,0);
    if(first<=0||(first&1)||first==last)return false;
    MemoryBarrier();NearCommand a=s.near_command;MemoryBarrier();NearCommand b=s.near_command;MemoryBarrier();
    LONG second=InterlockedCompareExchange(&s.near_command_generation,0,0);
    if(first!=second||!same(a,b))return false;
    output=a;generation=second;return true;
}
inline void result_publish(Shared& s,const Result& r){
    InterlockedIncrement(&s.near_receipt_generation);MemoryBarrier();s.near_receipt=pack(r);
    MemoryBarrier();InterlockedIncrement(&s.near_receipt_generation);
}
inline void combat_publish(Shared& s,const Result& r,const char* kind,const Observation& o,const Withdrawal* w){
    LONG ticket=InterlockedIncrement(&s.combat_written);
    if(ticket<=0){InterlockedExchange(&s.movement.state,static_cast<LONG>(channel::State::Uncertain));return;}
    auto& slot=s.combat[(static_cast<uint32_t>(ticket)-1)%combat_capacity];InterlockedExchange(&slot.ticket,0);
    slot.withdrawal_present=w?1:0;std::memset(slot.event_type,0,sizeof(slot.event_type));
    if(kind)std::strncpy(slot.event_type,kind,sizeof(slot.event_type)-1);
    slot.result=pack(r);slot.observation=o;slot.withdrawal=w?*w:Withdrawal{};
    MemoryBarrier();InterlockedExchange(&slot.ticket,ticket);
    if(static_cast<uint32_t>(ticket)>combat_capacity)InterlockedIncrement(&s.combat_overwritten);
}
}
