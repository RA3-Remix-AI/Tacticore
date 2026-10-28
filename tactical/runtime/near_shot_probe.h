#pragma once
// Passive natural-AI call observation only. No command or unit-control wire.
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include "near_build_policy.h"
#include <windows.h>
#include <cstddef>
namespace tacticore::runtime::shot_probe {
constexpr uint32_t magic=0x54535031,version=1,capacity=4096,restore_mask=7;
constexpr UINT bootstrap_message=WM_APP+0x4b1,pulse_message=WM_APP+0x4b2;
struct Bootstrap {
    Binding binding{};NativeBinding native{};uint32_t duration_ms=0,policy_schema=2;
    wchar_t mod_path[1024]{},capability_path[1024]{},safety_path[1024]{};
};
enum class Kind:uint32_t {PrivateEnter=1,PrivateExit=2,FireEnter=3,FireExit=4,DamageEnter=5,DamageExit=6,Heartbeat=7,WeaponRefusal=8};
struct Row {
    LONG ticket=0;uint32_t kind=0,frame=0,thread=0;uint64_t monotonic_ms=0,call_id=0,parent_id=0;
    std::array<uint32_t,96> words{};
};
struct Shared {
    uint32_t magic_word=magic,protocol=version,structure_size=sizeof(Shared),token=0;Bootstrap bootstrap{};
    volatile LONG state=0,error=0,active=0,stop=0,count=0,overflow=0;
    uint32_t callback_thread=0;volatile LONG pulse_requested=0,pulse_acknowledged=0;
    uint64_t started_ms=0,last_ms=0;uint32_t hooks_restored=0,installed_count=0,rejected=0,skipped_damage=0,max_callback_ms=0;
    Row rows[capacity]{};
};
inline bool same(const Bootstrap&a,const Bootstrap&b){return !std::memcmp(&a,&b,sizeof(a));}
inline bool closed(const Shared&s){return !s.active&&((s.state==3&&s.hooks_restored==restore_mask)||(s.state==4&&s.hooks_restored==1&&!s.installed_count));}
}
