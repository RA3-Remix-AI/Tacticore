#pragma once
// Persistent transport ABI v1. This is not an execution capability or evidence.
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0601
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include "memory_io.h"
#include <windows.h>
#include <cstddef>
#include <cstring>
#include <type_traits>

namespace tacticore::runtime::channel {
constexpr uint32_t magic=0x54524331,version=1,event_capacity=2048;
// Two recovery facts per distinct observed frame must fit the full bounded
// 900-frame lease, in addition to the actual native command lineage.
constexpr uint32_t trace_capacity=4096;
constexpr UINT bootstrap_message=WM_APP+0x3d1,pulse_message=WM_APP+0x3d2;
enum class State:uint32_t {Unattached=0,Initializing=1,Active=2,Released=3,Refused=4,Uncertain=5};
struct ProducerReference {Id command{},task{};uint32_t sequence=0,receipt_index=0;};
struct Bootstrap {
    Binding binding{};
    NativeBinding native{};
    Actor actor{};
    ProducerReference producer{};
    uint64_t persisted_sequence=0;
    uint32_t experimental_flags=0;
    bool operator==(const Bootstrap& x)const {
        return binding==x.binding&&std::memcmp(&native,&x.native,sizeof(native))==0&&actor==x.actor
            &&producer.command==x.producer.command&&producer.task==x.producer.task
            &&producer.sequence==x.producer.sequence&&producer.receipt_index==x.producer.receipt_index
            &&persisted_sequence==x.persisted_sequence&&experimental_flags==x.experimental_flags;
    }
};
// No pointers or C++ process-local strings are ever published cross-process.
struct WireReceipt {
    Id command{},task{},lease{};
    uint64_t sequence=0,monotonic_ms=0;
    uint32_t phase=0,frame=0,accepted=0,physical_home=0,control_released=0,stance_restored=0,held=0;
    std::array<uint32_t,6> sdk_calls{};
    char reason[96]{};
};
inline WireReceipt wire(const Receipt& r){
    WireReceipt value{};value.command=r.command;value.task=r.task;value.lease=r.lease;
    value.sequence=r.sequence;value.monotonic_ms=r.monotonic_ms;value.phase=static_cast<uint32_t>(r.phase);
    value.frame=r.frame;value.accepted=r.accepted;value.physical_home=r.physical_home;
    value.control_released=r.control_released;value.stance_restored=r.stance_restored;value.held=r.held;
    value.sdk_calls=r.sdk_calls;if(r.reason)std::strncpy(value.reason,r.reason,sizeof(value.reason)-1);return value;
}
struct WireEvent {volatile LONG ticket=0;uint32_t kind=0;char event_type[48]{};WireReceipt receipt{};Sample observation{};};
struct WireHookTrace {volatile LONG ticket=0;HookTrace trace{};};
struct SharedChannel {
    uint32_t magic_word=magic,protocol=version,structure_size=sizeof(SharedChannel),token=0;
    Bootstrap bootstrap{};
    volatile LONG state=0,stop_requested=0,active_callbacks=0,callback_thread=0;
    volatile LONG pulse_requested=0,pulse_acknowledged=0;
    volatile LONG command_generation=0,command_acknowledged=0;
    Command command{};
    volatile LONG command_receipt_generation=0;
    WireReceipt command_receipt{};
    volatile LONG receipt_generation=0;
    WireReceipt receipt{};
    volatile LONG events_written=0,events_overwritten=0;
    uint32_t hooks_restored=0;
    char reason[96]{};
    Actor admitted_actor{};
    uint64_t native_last_sequence=0;
    volatile LONG observation_generation=0;
    Sample current_observation{};
    volatile LONG targets_generation=0;
    uint32_t targets_count=0;
    Point approved_targets[64]{};
    WireEvent events[event_capacity]{};
    volatile LONG traces_written=0,traces_overwritten=0;
    WireHookTrace traces[trace_capacity]{};
};
static_assert(std::is_trivially_copyable<Command>::value,"Command must remain a pointer-free fixed ABI");
static_assert(std::is_trivially_copyable<WireReceipt>::value,"Wire receipt cannot hold native pointers");

inline bool command_snapshot(SharedChannel& channel,LONG last,Command& output,LONG& generation){
    LONG first=InterlockedCompareExchange(&channel.command_generation,0,0);
    if(first<=0||(first&1)||first==last)return false;
    MemoryBarrier();Command a=channel.command;MemoryBarrier();Command b=channel.command;MemoryBarrier();
    LONG second=InterlockedCompareExchange(&channel.command_generation,0,0);
    if(first!=second||!(a==b))return false;
    output=a;generation=second;return true;
}
inline void receipt_publish(SharedChannel& channel,const Receipt& receipt){
    InterlockedIncrement(&channel.receipt_generation);MemoryBarrier();channel.receipt=wire(receipt);
    MemoryBarrier();InterlockedIncrement(&channel.receipt_generation);
}
inline void event_publish(SharedChannel& channel,const Event& event,uint32_t kind){
    LONG ticket=InterlockedIncrement(&channel.events_written);
    if(ticket<=0){InterlockedExchange(&channel.state,static_cast<LONG>(State::Uncertain));return;}
    auto& slot=channel.events[(static_cast<uint32_t>(ticket)-1)%event_capacity];
    InterlockedExchange(&slot.ticket,0);slot.kind=kind;std::memset(slot.event_type,0,sizeof(slot.event_type));
    if(event.kind)std::strncpy(slot.event_type,event.kind,sizeof(slot.event_type)-1);
    slot.receipt=wire(event.receipt);slot.observation=event.observation;
    MemoryBarrier();InterlockedExchange(&slot.ticket,ticket);
    if(static_cast<uint32_t>(ticket)>event_capacity)InterlockedIncrement(&channel.events_overwritten);
}
inline void trace_publish(SharedChannel& channel,const HookTrace& trace){
    LONG ticket=InterlockedIncrement(&channel.traces_written);
    if(ticket<=0){InterlockedExchange(&channel.state,static_cast<LONG>(State::Uncertain));return;}
    auto& slot=channel.traces[(static_cast<uint32_t>(ticket)-1)%trace_capacity];
    InterlockedExchange(&slot.ticket,0);slot.trace=trace;
    MemoryBarrier();InterlockedExchange(&slot.ticket,ticket);
    if(static_cast<uint32_t>(ticket)>trace_capacity)InterlockedIncrement(&channel.traces_overwritten);
}
}
