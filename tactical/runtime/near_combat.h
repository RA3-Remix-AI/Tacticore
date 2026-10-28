#pragma once
// Native near-combat subroutine under development. Not part of the published
// v1 ABI, native DLL or capability catalog. No Win32/SDK calls live here.
#include "protocol.h"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <stdexcept>

namespace tacticore::runtime::near_combat {

// A private native registry identity, never a model-supplied address. The
// incarnation is independently observed, not an alleged engine generation.
struct Target {
    Id key{};
    uint32_t object_id=0,thing=0,template_ptr=0,update=0,owner=0,type_hash=0,observed_frame=0;
    uint64_t incarnation=0;
    bool operator==(const Target& x)const{return key==x.key&&object_id==x.object_id&&thing==x.thing
        &&template_ptr==x.template_ptr&&update==x.update&&owner==x.owner&&type_hash==x.type_hash
        &&observed_frame==x.observed_frame&&incarnation==x.incarnation;}
};
struct Intent {
    Id command{},task{},lease{},target_key{};
    uint64_t sequence=0;
    Actor actor{};
    uint32_t expires_frame=0,lease_deadline_frame=0;
    uint64_t expires_monotonic_ms=0;
    // Finite count is a contract, not a caller-selectable burst/unlimited mode.
    bool operator==(const Intent& x)const{return command==x.command&&task==x.task&&lease==x.lease&&target_key==x.target_key
        &&sequence==x.sequence&&actor==x.actor&&expires_frame==x.expires_frame
        &&lease_deadline_frame==x.lease_deadline_frame&&expires_monotonic_ms==x.expires_monotonic_ms;}
};
struct Lease {
    Binding binding{};Actor actor{};Id task{},lease{};
    Point home{};
    uint32_t original_begin_frame=0,original_deadline_frame=0,original_stance=0,foreign_epoch=0;
    uint64_t original_begin_ms=0,native_sequence=0;
    bool held=false,private_home_verified=false,ready_at_owned_endpoint=false,owner_uncertain=false;
};
struct Weapon {
    bool identity_verified=false,ready=false,ground_target_supported=false;
    uint32_t ammo=0;float range=0;
};
struct TargetSample {
    Target identity{};Point xyz{};float hp=0;
    uint32_t visibility_frame=0;uint64_t visibility_monotonic_ms=0;
    bool identity_verified=false,live=false,grounded=false,enemy=false,visible=false,visibility_complete=false;
};
enum class Origin:uint32_t {Unknown=0,Task=1,Native=2,Other=3};
struct AttackAcknowledgement {
    Delivery delivery=Delivery::Unknown;
    Binding binding{};Actor actor{};Target target{};Id command{},task{},lease{};
    uint64_t sequence=0,monotonic_ms=0;uint32_t frame=0,shots=0;
    bool own_scope_verified=false;
};
struct Damage {
    uint64_t ticket=0;
    Binding binding{};Actor actor{};Target target{};Id attack_command{},task{},lease{};
    uint32_t source_object_id=0,frame=0;uint64_t monotonic_ms=0;
    uint64_t shot_event_id=0,shot_monotonic_ms=0;uint32_t weapon_instance=0,shot_frame=0;
    float hp_before=0,hp_after=0,reported_damage=0;
    Origin origin=Origin::Unknown;
    bool identity_before=false,identity_after=false,visible_before=false,visible_after=false;
    bool source_verified=false,complete=false;
    bool shot_command_link_verified=false,shot_target_link_verified=false,damage_shot_link_verified=false;
};
struct Observation {
    Sample actor{};TargetSample target{};Weapon actor_weapon{};Damage damage{};
    uint32_t damage_overwritten=0;
    NativePreemption native_preemption=NativePreemption::None;
};
struct Withdrawal {
    Binding binding{};Actor actor{};Id task{},lease{};
    Point xyz{};uint32_t frame=0,original_deadline_frame=0,stance=0;
    uint64_t monotonic_ms=0;
    bool complete=false,released=false,control_released=false,stance_restored=false,held=true,physical_home=false;
};
enum class Phase:uint32_t {Idle=0,Prepared=1,WaitingDamage=2,Withdrawing=3,Released=4,Uncertain=5};
struct Result {
    Phase phase=Phase::Idle;const char* reason="idle";
    Id command{},task{},lease{};uint64_t sequence=0;
    uint32_t frame=0;uint64_t monotonic_ms=0;
    uint32_t attack_attempts=0,withdrawal_requests=0;
    bool accepted=false,attributed_hit=false,physical_home=false,control_released=false,stance_restored=false,held=false;
    bool cancelled=false,task_completed=false;
    float attributed_damage=0;
};
struct Limits {
    float max_target_distance=120,max_distance_from_home=300,arrival_radius=15,height_delta=2,damage_tolerance=.05f;
    uint32_t max_visibility_age_frames=2,attack_observation_frames=60,max_original_lease_frames=900;
    uint64_t max_visibility_age_ms=250,max_observation_gap_ms=10000,max_original_lease_ms=120000;
};
class IO {
public:
    virtual ~IO()=default;
    // The owner supplies the original Reserve lease; this layer cannot Borrow,
    // manufacture a new home, change deadlines or allocate a global sequence.
    virtual Lease lease()=0;
    virtual Observation sample(const Id& target_key)=0;
    // Native implementation must independently reread exact target/FOV/weapon
    // and ownership immediately before the SDK call. Default denial is real.
    virtual bool independent_attack_admission(const Intent&,const Observation&){return false;}
    virtual AttackAcknowledgement attack_once(const Intent&,const Target&)=0;
    // The existing owner performs Stop3/physical Return/stance/transfer. This
    // is a single command submission, not a success receipt or a new lease.
    virtual Delivery request_withdrawal(const Intent&)=0;
    virtual Withdrawal poll_withdrawal(const Intent&)=0;
    virtual void mark_control_unknown(const Intent&,const char*)=0;
    virtual void event(const Result&,const char*,const Observation&,const Withdrawal* receipt=nullptr)=0;
};

class Controller {
    Binding binding_;IO& io_;Limits limits_;Lease lease_{};Intent intent_{};Target target_{};Result result_{};
    uint64_t high_water_=0,last_ms_=0,attack_ms_=0,last_damage_ticket_=0;
    uint32_t last_frame_=0,attack_frame_=0,withdraw_frame_=0;uint64_t withdraw_ms_=0;
    bool clock_seen_=false,stop_=false,abort_=false;
    bool nonnull(const Target& t)const{return nonzero(t.key)&&t.object_id&&t.thing&&t.template_ptr&&t.update&&t.owner&&t.type_hash&&t.observed_frame&&t.incarnation;}
    bool binding_valid()const{
        uint32_t digest=0;for(auto n:binding_.binding_hash)digest|=n;
        return nonzero(binding_.session)&&nonzero(binding_.commander)&&nonzero(binding_.host)&&digest
            &&binding_.pid&&binding_.thread&&binding_.process_start&&binding_.player<20;
    }
    void emit(const char* kind,const Observation& o){result_.frame=o.actor.frame;result_.monotonic_ms=o.actor.monotonic_ms;io_.event(result_,kind,o);}
    bool clocks(const Observation& o){
        auto f=o.actor.frame;auto m=o.actor.monotonic_ms;
        bool okay=!clock_seen_||(f>=last_frame_&&m>=last_ms_&&m-last_ms_<=limits_.max_observation_gap_ms);
        last_frame_=f;last_ms_=m;clock_seen_=true;return okay;
    }
    const char* actor_guard(const Observation& o)const{
        const auto& s=o.actor;
        if(!(s.binding==binding_)||s.current_thread!=binding_.thread||!(s.actor==lease_.actor)||!s.identity
            ||s.frame<s.actor.born_frame||!s.actor_birth_verified||!s.live_list_member||!s.grounded||!s.interference_guard_ready)return "actor_binding_or_identity_unverified";
        if(!s.script_team||!s.default_team||s.script_team==s.default_team||s.team!=s.script_team||s.foreign_epoch!=lease_.foreign_epoch)return "actor_control_or_foreign_command_changed";
        if(!finite(s.xyz))return "actor_position_invalid";
        return nullptr;
    }
    bool target_guard(const Observation& o,bool ready)const{
        const auto& t=o.target;const auto& s=o.actor;const auto& w=o.actor_weapon;
        return t.identity==target_&&t.identity_verified&&t.live&&t.grounded&&t.enemy&&t.visible&&t.visibility_complete
            &&t.identity.owner!=lease_.actor.owner&&std::isfinite(t.hp)&&t.hp>0&&finite(t.xyz)
            &&s.frame>=t.visibility_frame&&s.frame-t.visibility_frame<=limits_.max_visibility_age_frames
            &&s.monotonic_ms>=t.visibility_monotonic_ms&&s.monotonic_ms-t.visibility_monotonic_ms<=limits_.max_visibility_age_ms
            &&w.identity_verified&&w.ground_target_supported&&std::isfinite(w.range)&&w.range>0
            &&(!ready||(w.ready&&w.ammo>0))
            &&distance(s.xyz,t.xyz)<=std::min(w.range,limits_.max_target_distance)
            &&std::fabs(s.xyz.z-t.xyz.z)<=limits_.height_delta;
    }
    bool lease_current()const{
        auto l=io_.lease();
        return l.binding==lease_.binding&&l.actor==lease_.actor&&l.task==lease_.task&&l.lease==lease_.lease&&l.home==lease_.home
            &&l.original_begin_frame==lease_.original_begin_frame&&l.original_deadline_frame==lease_.original_deadline_frame&&l.original_begin_ms==lease_.original_begin_ms
            &&l.native_sequence>=lease_.native_sequence&&(l.native_sequence<=intent_.sequence||result_.phase==Phase::Withdrawing)
            &&l.original_stance==lease_.original_stance&&l.foreign_epoch==lease_.foreign_epoch&&l.held&&l.private_home_verified&&!l.owner_uncertain
            &&(result_.phase!=Phase::Prepared||l.ready_at_owned_endpoint);
    }
    void unknown(const Observation& o,const char* why){
        if(result_.phase==Phase::Uncertain)return;
        result_.phase=Phase::Uncertain;result_.reason=why;result_.held=true;result_.task_completed=false;
        io_.mark_control_unknown(intent_,why);emit("control_unknown_no_retry",o);
    }
    void withdraw(const Observation& o,const char* why,bool abort){
        if(result_.phase==Phase::Withdrawing||result_.phase==Phase::Released||result_.phase==Phase::Uncertain)return;
        abort_=abort_||abort;result_.phase=Phase::Withdrawing;result_.reason=why;result_.withdrawal_requests++;
        withdraw_frame_=o.actor.frame;withdraw_ms_=o.actor.monotonic_ms;
        emit("withdrawal_intent",o);
        Delivery delivered=Delivery::Unknown;
        try{delivered=io_.request_withdrawal(intent_);}catch(...){unknown(o,"withdrawal_delivery_exception_unknown");return;}
        if(delivered!=Delivery::Sent){unknown(o,delivered==Delivery::NotSent?"withdrawal_not_sent_requires_new_recovery":"withdrawal_delivery_unknown");return;}
        emit("withdrawal_submitted",o);
    }
    bool hit(const Damage& d,const Observation& now)const{
        return d.ticket>last_damage_ticket_&&d.complete&&d.origin==Origin::Task&&d.source_verified
            &&d.shot_event_id&&d.weapon_instance&&d.shot_command_link_verified&&d.shot_target_link_verified&&d.damage_shot_link_verified
            &&d.binding==binding_&&d.actor==lease_.actor&&d.target==target_&&d.attack_command==intent_.command
            &&d.task==intent_.task&&d.lease==intent_.lease&&d.source_object_id==lease_.actor.object_id
            &&d.identity_before&&d.identity_after&&d.visible_before&&d.visible_after
            &&d.frame>=attack_frame_&&d.monotonic_ms>=attack_ms_
            &&d.shot_frame>=attack_frame_&&d.shot_frame<=d.frame&&d.shot_monotonic_ms>=attack_ms_&&d.shot_monotonic_ms<=d.monotonic_ms
            &&d.frame<=now.actor.frame&&d.monotonic_ms<=now.actor.monotonic_ms
            &&d.frame-attack_frame_<=limits_.attack_observation_frames
            &&std::isfinite(d.hp_before)&&std::isfinite(d.hp_after)&&std::isfinite(d.reported_damage)
            &&d.hp_before>0&&d.hp_after>=0&&d.hp_before>d.hp_after&&d.reported_damage>0
            &&std::fabs((d.hp_before-d.hp_after)-d.reported_damage)<=limits_.damage_tolerance;
    }
    bool finish_withdrawal(Observation& o){
        if(result_.phase!=Phase::Withdrawing)return false;
        Withdrawal r;
        try{r=io_.poll_withdrawal(intent_);}catch(...){unknown(o,"withdrawal_observation_exception_unknown");return true;}
        if(!r.complete)return false;
        // A return can already be complete when the next sample sees a native
        // squad or a later actor incarnation. Validate the original receipt,
        // not a fabricated current-owner sample or an impossible equal frame.
        if(r.frame>o.actor.frame||r.monotonic_ms>o.actor.monotonic_ms){
            o=io_.sample(intent_.target_key);
            if(!clocks(o)){unknown(o,"withdrawal_fresh_clock_unverified");return true;}
        }
        if(!(r.binding==binding_)||!(r.actor==lease_.actor)||r.task!=lease_.task||r.lease!=lease_.lease
            ||r.original_deadline_frame!=lease_.original_deadline_frame||!r.released||r.held||!r.control_released||!r.stance_restored
            ||r.stance!=lease_.original_stance||r.frame<withdraw_frame_||r.monotonic_ms<withdraw_ms_
            ||r.frame>o.actor.frame||r.monotonic_ms>o.actor.monotonic_ms
            ||r.monotonic_ms<lease_.original_begin_ms||r.monotonic_ms-lease_.original_begin_ms>=limits_.max_original_lease_ms){
            unknown(o,"withdrawal_receipt_identity_or_release_unverified");return true;
        }
        result_.physical_home=r.physical_home&&finite(r.xyz)&&distance(r.xyz,lease_.home)<=limits_.arrival_radius
            &&std::fabs(r.xyz.z-lease_.home.z)<=limits_.height_delta;
        result_.control_released=true;result_.stance_restored=true;result_.held=false;result_.phase=Phase::Released;
        result_.task_completed=result_.attributed_hit&&result_.physical_home&&!abort_&&!result_.cancelled;
        result_.reason=result_.task_completed?"attributed_hit_physical_home_and_control_returned":
            !result_.physical_home?"control_returned_home_unproven":"control_returned_without_complete_task";
        result_.frame=o.actor.frame;result_.monotonic_ms=o.actor.monotonic_ms;
        io_.event(result_,"near_combat_released",o,&r);return true;
    }
public:
    Controller(Binding binding,IO& io,uint64_t global_high_water,Limits limits={}):binding_(binding),io_(io),limits_(limits),high_water_(global_high_water){
        if(!std::isfinite(limits.max_target_distance)||limits.max_target_distance<=0||limits.max_target_distance>120
            ||!std::isfinite(limits.max_distance_from_home)||limits.max_distance_from_home<20||limits.max_distance_from_home>300
            ||!std::isfinite(limits.arrival_radius)||limits.arrival_radius<=0||limits.arrival_radius>15
            ||!std::isfinite(limits.height_delta)||limits.height_delta<=0||limits.height_delta>2
            // Compare against the exact binary32 value; x87 may otherwise
            // retain a .05f literal at excess precision and reject its default.
            ||!std::isfinite(limits.damage_tolerance)||limits.damage_tolerance<0||static_cast<double>(limits.damage_tolerance)>0.05000000074505806
            ||!limits.max_visibility_age_frames||limits.max_visibility_age_frames>2
            ||!limits.attack_observation_frames||limits.attack_observation_frames>60
            ||!limits.max_original_lease_frames||limits.max_original_lease_frames>900
            ||!limits.max_visibility_age_ms||limits.max_visibility_age_ms>250
            ||!limits.max_observation_gap_ms||limits.max_observation_gap_ms>10000
            ||!limits.max_original_lease_ms||limits.max_original_lease_ms>120000)
            throw std::invalid_argument("near_combat_limits_exceed_native_scope");
    }
    Result status()const{return result_;}
    uint64_t last_sequence()const{return high_water_;}
    Result submit(const Intent& intent){
        // Replaying the accepted immutable command observes it; it cannot call
        // the SDK or replace its target, task, lease or original clock budget.
        if(result_.accepted){
            if(intent==intent_)return result_;
            auto reply=result_;reply.accepted=false;reply.reason="near_combat_owner_already_used";return reply;
        }
        lease_=io_.lease();
        auto refuse=[&](const char* why){Result reply;reply.reason=why;reply.command=intent.command;reply.sequence=intent.sequence;
            reply.task=lease_.task;reply.lease=lease_.lease;reply.held=lease_.held;return reply;};
        if(!binding_valid()||!nonzero(intent.command)||!nonzero(intent.task)||!nonzero(intent.lease)||!nonzero(intent.target_key)
            ||!lease_.native_sequence||!intent.sequence||intent.sequence<=std::max(high_water_,lease_.native_sequence))return refuse("near_combat_identity_or_sequence_invalid");
        auto o=io_.sample(intent.target_key);target_=o.target.identity;
        if(!(lease_.binding==binding_)||!lease_.held||lease_.owner_uncertain||!lease_.private_home_verified||!lease_.ready_at_owned_endpoint
            ||lease_.task!=intent.task||lease_.lease!=intent.lease||!(lease_.actor==intent.actor)
            ||!finite(lease_.home)||lease_.original_deadline_frame!=intent.lease_deadline_frame
            ||!lease_.original_begin_frame||lease_.original_deadline_frame<=lease_.original_begin_frame
            ||lease_.original_deadline_frame-lease_.original_begin_frame>std::min(900u,limits_.max_original_lease_frames)
            ||lease_.actor.type_hash!=0x19ab11af||!lease_.actor.generation||!lease_.actor.born_frame)return refuse("original_ready_lease_required");
        if(auto why=actor_guard(o))return refuse(why);
        if(!clocks(o)||o.actor.paused||o.native_preemption!=NativePreemption::None||o.actor.frame>=intent.expires_frame||o.actor.monotonic_ms>=intent.expires_monotonic_ms
            ||o.actor.frame<lease_.original_begin_frame||o.actor.frame>=lease_.original_deadline_frame||o.actor.monotonic_ms<lease_.original_begin_ms
            ||o.actor.monotonic_ms-lease_.original_begin_ms>=limits_.max_original_lease_ms)return refuse("near_combat_clock_or_expiry_invalid");
        if(!o.actor.settled||o.actor.stance!=2||o.actor.path||o.actor.command_source!=1
            ||distance(o.actor.xyz,lease_.home)<20||distance(o.actor.xyz,lease_.home)>limits_.max_distance_from_home
            ||std::fabs(o.actor.xyz.z-lease_.home.z)>limits_.height_delta)return refuse("owned_approach_and_stop_required");
        if(!nonnull(target_)||target_.key!=intent.target_key||!target_guard(o,true)
            ||!io_.independent_attack_admission(intent,o))return refuse("fresh_enemy_visibility_weapon_or_scope_unverified");
        intent_=intent;high_water_=intent.sequence;result_.accepted=true;result_.held=true;
        result_.command=intent.command;result_.task=intent.task;result_.lease=intent.lease;result_.sequence=intent.sequence;
        result_.phase=Phase::Prepared;result_.reason="near_combat_prepared";emit("near_combat_admitted",o);return result_;
    }
    Result tick(){
        if(!result_.accepted||result_.phase==Phase::Released||result_.phase==Phase::Uncertain)return result_;
        auto o=io_.sample(intent_.target_key);
        if(!clocks(o)){unknown(o,"near_combat_clock_regressed_or_watchdog");return result_;}
        if(finish_withdrawal(o))return result_;
        if(!lease_current()){unknown(o,"original_lease_replaced_or_renewed");return result_;}
        if(auto why=actor_guard(o)){unknown(o,why);return result_;}
        if(o.actor.monotonic_ms<lease_.original_begin_ms||o.actor.monotonic_ms-lease_.original_begin_ms>=limits_.max_original_lease_ms){unknown(o,"original_lease_wall_limit");return result_;}
        emit("near_combat_observation",o);
        if(o.actor.paused){result_.reason="game_paused_no_sdk";return result_;}
        if(o.native_preemption==NativePreemption::UnverifiedYield){unknown(o,"near_combat_native_yield_unverified");return result_;}
        if(o.native_preemption==NativePreemption::WaitingYield){result_.reason="near_combat_native_yield_waiting_no_sdk";return result_;}
        if(o.native_preemption==NativePreemption::VerifiedYield){withdraw(o,"native_yield_aborts_near_combat",true);return result_;}
        if(result_.phase!=Phase::Withdrawing&&(stop_||o.actor.frame>=lease_.original_deadline_frame
            ||o.actor.frame>=intent_.expires_frame||o.actor.monotonic_ms>=intent_.expires_monotonic_ms)){
            withdraw(o,stop_?"user_stop_withdrawal":"work_expired_withdrawal",true);return result_;
        }
        if(result_.phase==Phase::Prepared){
            if(!o.actor.settled||o.actor.stance!=2||o.actor.path||o.actor.command_source!=1
                ||!target_guard(o,true)||!io_.independent_attack_admission(intent_,o)){
                withdraw(o,"attack_preflight_changed_no_shot",true);return result_;
            }
            result_.attack_attempts++;emit("attack_once_intent",o);
            AttackAcknowledgement ack;
            try{ack=io_.attack_once(intent_,target_);}catch(...){unknown(o,"attack_delivery_exception_unknown");return result_;}
            if(ack.delivery==Delivery::NotSent){withdraw(o,"attack_not_sent_no_retry",true);return result_;}
            if(ack.delivery!=Delivery::Sent||!ack.own_scope_verified||!(ack.binding==binding_)||!(ack.actor==lease_.actor)
                ||!(ack.target==target_)||ack.command!=intent_.command||ack.task!=intent_.task||ack.lease!=intent_.lease
                ||ack.sequence!=intent_.sequence||ack.shots!=1||ack.frame<o.actor.frame||ack.monotonic_ms<o.actor.monotonic_ms
                ||ack.frame>=intent_.expires_frame||ack.monotonic_ms>=intent_.expires_monotonic_ms
                ||ack.frame>=lease_.original_deadline_frame||ack.monotonic_ms<lease_.original_begin_ms
                ||ack.monotonic_ms-lease_.original_begin_ms>=limits_.max_original_lease_ms){
                unknown(o,"attack_delivery_or_scope_unknown");return result_;
            }
            attack_frame_=ack.frame;attack_ms_=ack.monotonic_ms;result_.phase=Phase::WaitingDamage;
            result_.reason="attack_once_sent_waiting_attribution";emit("attack_once_acknowledged",o);return result_;
        }
        if(result_.phase==Phase::WaitingDamage){
            if(o.damage_overwritten){withdraw(o,"damage_evidence_lost_no_effect_credit",true);return result_;}
            if(hit(o.damage,o)){
                result_.attributed_hit=true;result_.attributed_damage=o.damage.reported_damage;last_damage_ticket_=o.damage.ticket;
                emit("attributed_hit_observed",o);withdraw(o,"attributed_hit_withdrawal",false);return result_;
            }
            if(o.damage.ticket>last_damage_ticket_){last_damage_ticket_=o.damage.ticket;emit("unattributed_damage_no_credit",o);}
            if(!target_guard(o,false)){withdraw(o,"target_or_visibility_changed_withdrawal",true);return result_;}
            if(o.actor.frame<attack_frame_||o.actor.monotonic_ms<attack_ms_){unknown(o,"attack_ack_clock_ahead_of_observation");return result_;}
            if(o.actor.frame-attack_frame_>=limits_.attack_observation_frames){withdraw(o,"no_attributable_hit_in_window",true);return result_;}
        }
        return result_;
    }
    Result request_stop(){stop_=true;result_.cancelled=true;result_.task_completed=false;return result_;}
};
}
