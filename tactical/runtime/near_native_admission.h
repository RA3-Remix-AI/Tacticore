#pragma once
// Independent native boundary guard. No caller-supplied Sample/Weapon/FOV bool
// is accepted here: reread through the original MemoryIO and native readers.
#include "near_native_hooks.h"
#include "near_owner.h"
#include "near_target.h"
#include "near_weapon.h"

namespace tacticore::runtime::near_combat {
class NativeAdmission final:public ::tacticore::runtime::NativeAttackAdmission {
    Binding binding_;Owner& owner_;MemoryIO& movement_;Memory& memory_;
    TargetReader& targets_;WeaponReader& weapons_;
    const char* reason_="unexamined";WeaponSnapshot weapon_{};
    bool deny(const char* why){reason_=why;return false;}
    static bool lease_equal(const Lease& a,const Lease& b){
        return a.binding==b.binding&&a.actor==b.actor&&a.task==b.task&&a.lease==b.lease&&a.home==b.home
            &&a.original_begin_frame==b.original_begin_frame&&a.original_begin_ms==b.original_begin_ms
            &&a.original_deadline_frame==b.original_deadline_frame&&a.original_stance==b.original_stance
            &&a.foreign_epoch==b.foreign_epoch;
    }
    bool check(const Lease& supplied,const Intent& i,const Target& t,bool sdk){
        weapon_={};auto l=owner_.original_lease_snapshot();
        if(!(memory_.current_binding()==binding_)||memory_.thread()!=binding_.thread)return deny("admission_binding_or_thread");
        if(!lease_equal(l,supplied)||!(l.binding==binding_)||!(l.actor==i.actor)||l.task!=i.task||l.lease!=i.lease
            ||!nonzero(i.command)||!nonzero(i.task)||!nonzero(i.lease)||!nonzero(i.target_key)||i.target_key!=t.key
            ||!l.held||l.owner_uncertain||!l.private_home_verified||!l.ready_at_owned_endpoint
            ||!l.actor.generation||!l.actor.born_frame||!finite(l.home)||!l.original_begin_frame
            ||l.original_deadline_frame<=l.original_begin_frame||l.original_deadline_frame-l.original_begin_frame>900
            ||i.lease_deadline_frame!=l.original_deadline_frame)return deny("admission_original_lease");
        if(sdk?!owner_.accepted_attack_current(i):
            (i.sequence<l.native_sequence||(i.sequence==l.native_sequence&&!owner_.accepted_attack_current(i))))
            return deny("admission_owner_command_or_sequence");
        if(!i.sequence||!l.native_sequence||l.native_sequence>i.sequence)return deny("admission_high_water");
        auto a=movement_.sample();
        if(!(a.binding==binding_)||a.current_thread!=binding_.thread||!(a.actor==l.actor)||!a.identity
            ||!a.actor_birth_verified||!a.live_list_member||!a.grounded||!a.interference_guard_ready
            ||!a.script_team||!a.default_team||a.script_team==a.default_team||a.team!=a.script_team
            ||a.foreign_epoch!=l.foreign_epoch||a.stance!=2||a.command_source!=1||a.path||a.state_flags&0xffff
            ||!a.settled||a.state_id!=94||a.state_vtable!=0xc551a0||!finite(a.xyz))return deny("admission_owned_stop_or_identity");
        auto before=memory_.monotonic_ms();
        if(a.paused||a.frame<l.actor.born_frame||a.frame<l.original_begin_frame||a.frame>=l.original_deadline_frame
            ||a.frame>=i.expires_frame||a.monotonic_ms<l.original_begin_ms||a.monotonic_ms-l.original_begin_ms>=120000
            ||a.monotonic_ms>=i.expires_monotonic_ms||before<a.monotonic_ms||before-a.monotonic_ms>250)
            return deny("admission_original_clock_limit");
        auto target=targets_.sample(t);auto w=weapons_.sample(l.actor);auto after=movement_.sample();auto now=memory_.monotonic_ms();
        if(!target.visible||!target.visibility_complete||!target.identity_verified||!(target.identity==t)
            ||!target.enemy||!target.live||!target.grounded||target.identity.owner==l.actor.owner||!finite(target.xyz)
            ||!std::isfinite(target.hp)||target.hp<=0||target.visibility_frame!=a.frame
            ||target.visibility_monotonic_ms<a.monotonic_ms)return deny("admission_current_own_fov_target");
        if(!w.facts.identity_verified||!w.facts.ready||!w.facts.ground_target_supported||!w.facts.ammo
            ||w.frame!=a.frame||w.thread!=binding_.thread||w.monotonic_ms<target.visibility_monotonic_ms
            ||distance(a.xyz,target.xyz)>std::min(120.0f,w.facts.range)||std::fabs(a.xyz.z-target.xyz.z)>2
            ||distance(a.xyz,l.home)<20||distance(a.xyz,l.home)>300||std::fabs(a.xyz.z-l.home.z)>2)
            return deny("admission_ready_weapon_or_distance");
        auto latest=owner_.original_lease_snapshot();
        if(!(after.binding==a.binding)||!(after.actor==a.actor)||after.frame!=a.frame||after.current_thread!=a.current_thread
            ||!after.identity||!after.actor_birth_verified||!after.live_list_member||!after.grounded||!after.interference_guard_ready
            ||after.paused||!after.settled||after.team!=a.team||after.stance!=a.stance||after.path!=a.path
            ||after.command_source!=a.command_source||after.foreign_epoch!=a.foreign_epoch||!(after.xyz==a.xyz)
            ||after.monotonic_ms<w.monotonic_ms||now<after.monotonic_ms
            ||now<before||now-before>250||now>=i.expires_monotonic_ms||now<l.original_begin_ms
            ||now-l.original_begin_ms>=120000||!lease_equal(l,latest)||!latest.held||latest.owner_uncertain
            ||!latest.private_home_verified||!latest.ready_at_owned_endpoint||latest.native_sequence!=l.native_sequence
            ||((sdk||i.sequence==latest.native_sequence)&&!owner_.accepted_attack_current(i)))
            return deny("admission_changed_during_reread");
        weapon_=w;reason_="native_original_lease_target_weapon_revalidated";return true;
    }
public:
    NativeAdmission(Binding b,Owner& o,MemoryIO& io,Memory& m,TargetReader& t,WeaponReader& w):
        binding_(b),owner_(o),movement_(io),memory_(m),targets_(t),weapons_(w){}
    bool prepare(const Lease& l,const Intent& i,const Target& t){return check(l,i,t,false);}
    bool permit(const Lease& l,const Intent& i,const Target& t,AttackBoundary boundary)override{
        if(boundary!=AttackBoundary::Facade&&boundary!=AttackBoundary::PrivateDelivery)return deny("admission_boundary_invalid");
        return check(l,i,t,true);
    }
    const char* reason()const{return reason_;}
    WeaponSnapshot admitted_weapon()const{return weapon_;}
};
}
