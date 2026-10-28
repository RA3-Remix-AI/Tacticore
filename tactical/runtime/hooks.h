#pragma once
#include "memory_io.h"
#include <memory>
#include <functional>
namespace tacticore::runtime {
class NativeObserver:public NativeCalls,public CommandWitness {
public:
    virtual bool install()=0;
    // False retains hooks/module/channel ownership. Unknown is NON-terminal.
    // Never unhook or destroy while a lease, callback or stored command exists.
    virtual bool close_after_verified_release()=0;
    virtual uint32_t active_callbacks()const=0;
    virtual uint32_t restored_mask()const=0;
    virtual bool no_hooks_enabled()const=0;
};
std::unique_ptr<NativeObserver> make_native_observer(Binding,NativeBinding,Actor,Memory&,bool yield_abort_experiment=false,std::function<void(const HookTrace&)> = {},bool diagnostic_fault=false);
}
