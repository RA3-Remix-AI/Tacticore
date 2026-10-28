#pragma once
#include "controller.h"
#include <functional>
#include <memory>
#include <vector>
#include <stdexcept>
namespace tacticore::runtime::channel {struct Bootstrap;}
namespace tacticore::runtime {
class FactoryError:public std::runtime_error {
public:
    const bool safe_no_hooks;
    FactoryError(const char* reason,bool safe):std::runtime_error(reason),safe_no_hooks(safe){}
};
class NativeRuntime {
public:
    virtual ~NativeRuntime()=default;
    virtual Controller& controller()=0;
    virtual Actor actor()const=0;
    virtual bool close_verified()=0;
    virtual uint32_t active_callbacks()const=0;
    virtual uint32_t restored_mask()const=0;
    virtual void observe_endpoints()=0;
    virtual std::vector<Point> approved_targets()const=0;
    virtual Sample observation()=0;
};
// Must be called on the real game thread. Throws stable reason only. Bootstrap
// Actor is an expected tuple, never an admission or caller-provided generation.
// Keep ownership forever if close_verified()==false; never unhook on an error.
std::unique_ptr<NativeRuntime> create_runtime(const channel::Bootstrap&,std::function<void(const Event&)>,std::function<void(const HookTrace&)>);
}
