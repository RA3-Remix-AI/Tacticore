#pragma once
// Research-only, separate message channel. No command or actor-control field.
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include "near_target.h"
#include <windows.h>
#include <cstddef>

namespace tacticore::runtime::readonly_probe {
constexpr uint32_t magic=0x54525031,version=1,capacity=16384;
constexpr UINT bootstrap_message=WM_APP+0x4a1,pulse_message=WM_APP+0x4a2;
struct Bootstrap {
    Binding binding{};NativeBinding native{};
    uint32_t duration_ms=0,policy_schema=2;
    wchar_t mod_path[1024]{},capability_path[1024]{},safety_path[1024]{};
};
struct Row {
    LONG ticket=0;uint32_t kind=0,frame=0,thread=0;uint64_t monotonic_ms=0;
    std::array<uint32_t,40> words{};Point xyz{};float hp=0;
};
struct Shared {
    uint32_t magic_word=magic,protocol=version,structure_size=sizeof(Shared),token=0;
    Bootstrap bootstrap{};
    volatile LONG state=0,error=0,active=0,stop=0,count=0,overflow=0;
    uint32_t callback_thread=0;volatile LONG pulse_requested=0,pulse_acknowledged=0;
    uint64_t started_ms=0,last_ms=0;
    uint32_t own_rejected=0,visible_samples=0,registry_refusals=0,max_step_ms=0;
    Row rows[capacity]{};
};
inline bool same(const Bootstrap& a,const Bootstrap& b){return !std::memcmp(&a,&b,sizeof(a));}
}
