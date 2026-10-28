#pragma once
// Composite owner under development. The original motion controller and its
// private home, Stop3 and release implementation are reused without editing v1.
// This is not the published wire ABI or a game SDK capability grant.
#include "near_combat.h"
#include "controller.h"
#include <memory>
#include <vector>

namespace tacticore::runtime::near_combat {
namespace motion = ::tacticore::runtime;
struct CombatFacts {
    TargetSample target{};Weapon weapon{};Damage damage{};uint32_t damage_overwritten=0;
};
class Execution {
public:
    virtual ~Execution()=default;
    virtual CombatFacts facts(const Sample&,const Id&)=0;
    virtual bool independent_attack_admission(const Lease&,const Intent&,const Observation&){return false;}
    virtual AttackAcknowledgement attack_once(const Lease&,const Intent&,const Target&)=0;
    virtual void mark_control_unknown(const Intent&,const char*)=0;
    virtual void event(const Result&,const char*,const Observation&,const Withdrawal*)=0;
};
class Owner final:private motion::IO,private near_combat::IO {
    Binding binding_;motion::IO& movement_;Execution& execution_;
    motion::Controller movement_controller_;std::unique_ptr<near_combat::Controller> combat_;
    Lease original_{};Sample remembered_{};Withdrawal release_{};Command withdrawal_{};Intent attack_{};
    std::vector<Id> combat_ids_,motion_ids_;uint64_t high_water_=0;bool unknown_=false,home_recorded_=false;
    const char* unknown_reason_="idle";
    bool active()const{return combat_&&combat_->status().accepted&&combat_->status().phase!=Phase::Released;}
    bool used(const Id& id)const{for(const auto& prior:combat_ids_)if(prior==id)return true;return false;}
    bool motion_used(const Id& id)const{for(const auto& prior:motion_ids_)if(prior==id)return true;return false;}
    Result refuse_near(const Intent& i,const char* why)const{
        Result r;r.command=i.command;r.sequence=i.sequence;r.task=original_.task;r.lease=original_.lease;
        r.held=movement_controller_.status().held;r.reason=why;return r;
    }
    Receipt refuse_motion(const Command& c,const char* why)const{
        auto r=movement_status();r.accepted=false;r.command=c.command;r.sequence=c.sequence;r.reason=why;return r;
    }
    // Original motion IO, including its independent last-frame admissions.
    Sample sample()override{return movement_.sample();}
    bool ground_target(Point p)override{return movement_.ground_target(p);}
    bool independent_borrow_permitted(const Sample& s)override{return movement_.independent_borrow_permitted(s);}
    bool remember_home(const Sample& s)override{
        if(!movement_.remember_home(s))return false;
        remembered_=s;home_recorded_=true;return true;
    }
    bool return_home_clear(const Sample& s,Point p)override{return movement_.return_home_clear(s,p);}
    Delivery issue(Action a,Point p,uint32_t stance)override{return movement_.issue(a,p,stance);}
    void event(const Event& e)override{
        // Capture the original actual release observation before native AI can
        // recruit the actor into a new squad. Never mint a later receipt.
        if(e.receipt.phase==motion::Phase::Released&&e.receipt.control_released&&!e.receipt.held){
            release_.binding=e.observation.binding;release_.actor=e.observation.actor;
            release_.task=e.receipt.task;release_.lease=e.receipt.lease;release_.xyz=e.observation.xyz;
            release_.frame=e.receipt.frame;release_.monotonic_ms=e.receipt.monotonic_ms;
            release_.original_deadline_frame=original_.original_deadline_frame;release_.stance=e.observation.stance;
            release_.complete=release_.released=true;release_.held=false;release_.control_released=e.receipt.control_released;
            release_.physical_home=e.receipt.physical_home;release_.stance_restored=e.receipt.stance_restored;
        }
        movement_.event(e);
    }
    bool independent_recovery_permitted(const Sample& s)override{return movement_.independent_recovery_permitted(s);}
    NativePreemption take_native_preemption(const Sample& s)override{return movement_.take_native_preemption(s);}
    void clear_native_preemption()override{movement_.clear_native_preemption();}
    // Deliberately no diagnostic-fault forwarding through this new owner.
    Lease lease()override{
        auto l=original_;auto r=movement_controller_.status();l.held=r.held;
        l.owner_uncertain=unknown_||r.phase==motion::Phase::Uncertain;
        l.native_sequence=high_water_;l.ready_at_owned_endpoint=r.phase==motion::Phase::Holding&&!unknown_;
        return l;
    }
    Observation sample(const Id& target_key)override{
        Observation o;o.actor=movement_.sample();auto facts=execution_.facts(o.actor,target_key);
        o.target=facts.target;o.actor_weapon=facts.weapon;o.damage=facts.damage;o.damage_overwritten=facts.damage_overwritten;
        // An admission refusal must not consume a native-yield receipt that
        // the original motion owner still needs to process on its next tick.
        o.native_preemption=active()?movement_.take_native_preemption(o.actor):NativePreemption::None;return o;
    }
    bool independent_attack_admission(const Intent& i,const Observation& o)override{
        return !unknown_&&execution_.independent_attack_admission(lease(),i,o);
    }
    AttackAcknowledgement attack_once(const Intent& i,const Target& t)override{
        return execution_.attack_once(lease(),i,t);
    }
    Delivery request_withdrawal(const Intent& i)override{
        if(unknown_||!(i==attack_)||withdrawal_.sequence<=high_water_)return Delivery::NotSent;
        auto r=movement_controller_.submit(withdrawal_);
        if(!r.accepted)return Delivery::NotSent;
        high_water_=withdrawal_.sequence;return Delivery::Sent;
    }
    Withdrawal poll_withdrawal(const Intent&)override{
        if(movement_controller_.status().phase==motion::Phase::Uncertain){Withdrawal r;r.complete=true;return r;}
        return release_;
    }
    void mark_control_unknown(const Intent& i,const char* why)override{
        unknown_=true;unknown_reason_=why;execution_.mark_control_unknown(i,why);
    }
    void event(const Result& r,const char* kind,const Observation& o,const Withdrawal* receipt)override{
        execution_.event(r,kind,o,receipt);
    }
public:
    Owner(Binding binding,motion::IO& movement,Execution& execution,uint64_t persisted_sequence,motion::Limits limits={}):
        binding_(binding),movement_(movement),execution_(execution),movement_controller_(binding,*this,limits,persisted_sequence),high_water_(persisted_sequence){}
    // Trusted native admission obtains this private owner's current lease,
    // never a lease reconstructed from an IPC dictionary. This is read-only.
    Lease original_lease_snapshot(){return lease();}
    bool accepted_attack_current(const Intent& i)const{
        if(unknown_||!combat_||!(i==attack_))return false;
        auto r=combat_->status();auto m=movement_controller_.status();
        return r.accepted&&!r.cancelled&&(r.phase==Phase::Prepared||r.phase==Phase::WaitingDamage)
            &&m.phase==motion::Phase::Holding&&m.held&&high_water_==i.sequence;
    }
    uint64_t last_sequence()const{return high_water_;}
    Receipt movement_status()const{
        auto r=movement_controller_.status();
        if(unknown_){r.phase=motion::Phase::Uncertain;r.reason=unknown_reason_;r.held=true;r.control_released=false;}
        return r;
    }
    Result combat_status()const{return combat_?combat_->status():Result{};}
    Receipt submit(const Command& c){
        if(unknown_||active())return refuse_motion(c,"near_combat_owns_original_lease");
        if(c.sequence<=high_water_||used(c.command)||motion_used(c.command)||motion_ids_.size()>=1024)return refuse_motion(c,"composite_command_identity_or_sequence_invalid");
        auto r=movement_controller_.submit(c);
        if(r.accepted){
            high_water_=c.sequence;
            motion_ids_.push_back(c.command);
            if(c.operation==Operation::Reserve){
                // remember_home was called by the original controller during
                // this exact Reserve admission, before any Borrow SDK call.
                original_={};original_.binding=binding_;original_.actor=c.actor;original_.task=c.task;original_.lease=c.lease;
                original_.home=remembered_.xyz;original_.original_begin_frame=remembered_.frame;
                original_.original_begin_ms=remembered_.monotonic_ms;original_.original_deadline_frame=c.lease_deadline_frame;
                original_.original_stance=remembered_.stance;original_.foreign_epoch=remembered_.foreign_epoch;
                original_.private_home_verified=home_recorded_;release_={};combat_.reset();
            }
        }
        return r;
    }
    Result submit(const Intent& i,const Command& withdrawal){
        if(combat_&&i==attack_&&withdrawal==withdrawal_)return combat_->status();
        if(unknown_||active()||used(i.command)||used(withdrawal.command)||motion_used(i.command)||motion_used(withdrawal.command)||combat_ids_.size()>=1024)
            return refuse_near(i,"composite_near_command_conflict_or_capacity");
        if(movement_controller_.status().phase!=motion::Phase::Holding||i.sequence<=high_water_
            ||withdrawal.operation!=Operation::ReturnHome||!nonzero(withdrawal.command)||withdrawal.command==i.command
            ||withdrawal.task!=i.task||withdrawal.lease!=i.lease||!(withdrawal.actor==i.actor)
            ||withdrawal.sequence<=i.sequence||withdrawal.lease_deadline_frame!=original_.original_deadline_frame
            ||!(withdrawal.target==Point{})||withdrawal.hold_frames
            ||withdrawal.expires_monotonic_ms< i.expires_monotonic_ms
            ||withdrawal.expires_monotonic_ms<original_.original_begin_ms
            ||withdrawal.expires_monotonic_ms-original_.original_begin_ms>120000
            ||withdrawal.expires_frame<i.expires_frame)
            return refuse_near(i,"owned_endpoint_and_explicit_original_return_required");
        auto candidate=std::make_unique<near_combat::Controller>(binding_,static_cast<near_combat::IO&>(*this),high_water_);
        auto r=candidate->submit(i);
        if(r.accepted){
            attack_=i;withdrawal_=withdrawal;high_water_=i.sequence;
            combat_ids_.push_back(i.command);combat_ids_.push_back(withdrawal.command);combat_=std::move(candidate);
        }
        return r;
    }
    void tick(){
        if(unknown_)return;
        if(active()){
            // The old Holding guard must not misclassify our admitted attack
            // as a changed Stop state. Its original return path resumes once.
            // A real paused sample can safely flow through the original
            // controller: it records its clock and returns before Holding or
            // any SDK action. Keep its watchdog current without inventing a
            // settled state during admitted fire. All work wall limits stay.
            if(combat_->status().phase==Phase::Withdrawing||movement_.sample().paused)movement_controller_.tick();
            combat_->tick();
        }else movement_controller_.tick();
    }
    void request_stop(){if(active())combat_->request_stop();else movement_controller_.request_stop();}
};
}
