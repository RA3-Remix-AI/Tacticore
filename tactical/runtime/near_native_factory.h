#pragma once
// Isolated development native factory. The active v1 factory/ABI is untouched.
#include "native_factory.h"
#include "shared_channel.h"
#include "near_owner.h"
#include <array>

namespace tacticore::runtime::near_combat {
struct NativeBootstrap {
    uint32_t schema=2;
    channel::Bootstrap original{};
    wchar_t mod_path[1024]{},visibility_path[1024]{},template_audit_path[1024]{};
};
struct ContactView {
    Id key{};uint32_t type_hash=0,frame=0;uint64_t monotonic_ms=0;Point xyz{};float hp=0;
};
using CombatSink=std::function<void(const Result&,const char*,const Observation&,const Withdrawal*)>;
class NearRuntime {
public:
    virtual ~NearRuntime()=default;
    virtual Receipt submit(const Command&)=0;
    virtual Result submit(const Intent&,const Command& original_return)=0;
    virtual void tick()=0;
    virtual void request_stop()=0;
    virtual Receipt movement_status()const=0;
    virtual Result combat_status()const=0;
    virtual uint64_t last_sequence()const=0;
    virtual Actor actor()const=0;
    virtual Sample observation()=0;
    virtual void observe_endpoints()=0;
    virtual std::vector<Point> approved_targets()const=0;
    virtual std::vector<ContactView> visible_contacts()const=0;
    virtual bool close_verified()=0;
    virtual uint32_t active_callbacks()const=0;
    virtual uint32_t restored_mask()const=0;
};
// Game-thread-only; independently verifies actual original producer mapping,
// paid birth and pinned build policy before installing any hooks. The owner
// must stay alive while close_verified is false, including every unknown path.
// The factory pins its module before activation and quarantines partial hooks.
std::unique_ptr<NearRuntime> create_near_runtime(const NativeBootstrap&,
    std::function<void(const Event&)>,std::function<void(const HookTrace&)>,CombatSink);
}
