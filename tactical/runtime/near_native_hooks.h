#pragma once
// Development observer only. No published bootstrap/ABI or field capability.
#include "hooks.h"
#include "near_attack_lineage.h"

namespace tacticore::runtime {
enum class AttackBoundary:uint32_t {Facade=1,PrivateDelivery=2};
class NativeAttackAdmission {
public:
    virtual ~NativeAttackAdmission()=default;
    // A trusted implementation must independently read the current original
    // lease, actor/target registry, own FOV, exact weapon and native clocks.
    // Caller dictionaries, saved samples and a scope flag cannot grant this.
    virtual bool permit(const near_combat::Lease&,const near_combat::Intent&,const near_combat::Target&,AttackBoundary){return false;}
};
class NearNativeObserver:public NativeObserver {
public:
    virtual near_combat::AttackAcknowledgement attack_once(const near_combat::Lease&,const near_combat::Intent&,const near_combat::Target&)=0;
    virtual bool attack_delivered()const=0;
    // Exact current getter observations, NOT live weapon pointers for the
    // model and NOT evidence that a round was fired or damage was attributed.
    struct WeaponSelection {uint32_t frame=0,thread=0,entry=0,template_ptr=0,slot=0,ammo=0,limit_before=0,limit_after=0,asset_id=0,state_machine=0,state=0,state_id=0;bool ready_state=false,verified=false,after_verified=false;};
    virtual WeaponSelection weapon_selection()const=0;
};
std::unique_ptr<NearNativeObserver> make_near_native_observer(Binding,NativeBinding,Actor,Memory&,NativeAttackAdmission&,std::function<void(const HookTrace&)> = {});
}
