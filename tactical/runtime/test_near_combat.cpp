#include "near_combat.h"
#include <string>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>
namespace rt=tacticore::runtime;
namespace nc=rt::near_combat;
#define CHECK(x) do{if(!(x))throw std::runtime_error(std::string(__func__)+":"+std::to_string(__LINE__)+":"+#x);}while(0)
static rt::Id id(uint32_t n){return {n,2,3,4};}
static rt::Binding binding(){rt::Binding b;b.session=id(1);b.commander=id(2);b.host=id(3);b.binding_hash[0]=4;b.player=3;b.pid=10;b.thread=20;b.process_start=123;return b;}
static rt::Actor actor(){return {55,0x5000,0x7000,0x6000,0x2000,0x19ab11af,90,1};}
static nc::Target target(){return {id(50),77,0x9000,0xa000,0xb000,0xc000,0x19ab11af,95,1};}
static nc::Intent intent(){nc::Intent i;i.command=id(100);i.task=id(10);i.lease=id(11);i.target_key=target().key;i.sequence=5;i.actor=actor();i.expires_frame=400;i.lease_deadline_frame=800;i.expires_monotonic_ms=20000;return i;}
struct Fake:nc::IO {
    nc::Lease l;nc::Observation o;nc::Withdrawal r;
    bool gate=true,throw_attack=false,throw_return=false,ack_scope=true;uint32_t attack_calls=0,return_calls=0,unknown_calls=0;
    rt::Delivery delivery=rt::Delivery::Sent,return_delivery=rt::Delivery::Sent;
    std::vector<std::string> events;bool release_receipt_recorded=false;
    Fake(){
        l.binding=binding();l.actor=actor();l.task=id(10);l.lease=id(11);l.home={0,0,0};l.original_deadline_frame=800;
        l.original_begin_frame=90;l.original_begin_ms=500;l.native_sequence=4;l.original_stance=0;l.held=l.private_home_verified=l.ready_at_owned_endpoint=true;
        auto& a=o.actor;a.binding=binding();a.actor=actor();a.frame=100;a.monotonic_ms=1000;a.current_thread=20;
        a.team=a.script_team=0x4000;a.default_team=0x3000;a.stance=2;a.command_source=1;a.xyz={40,0,0};a.paused=false;
        a.identity=a.actor_birth_verified=a.live_list_member=a.grounded=a.settled=a.interference_guard_ready=true;
        auto& t=o.target;t.identity=target();t.xyz={80,0,0};t.hp=120;t.visibility_frame=100;t.visibility_monotonic_ms=1000;
        t.identity_verified=t.live=t.grounded=t.enemy=t.visible=t.visibility_complete=true;
        o.actor_weapon.identity_verified=o.actor_weapon.ready=o.actor_weapon.ground_target_supported=true;o.actor_weapon.ammo=3;o.actor_weapon.range=100;
    }
    nc::Lease lease()override{return l;}
    nc::Observation sample(const rt::Id&)override{return o;}
    bool independent_attack_admission(const nc::Intent&,const nc::Observation&)override{return gate;}
    nc::AttackAcknowledgement attack_once(const nc::Intent& i,const nc::Target& t)override{
        ++attack_calls;if(throw_attack)throw std::runtime_error("injected native delivery exception");
        return {delivery,binding(),actor(),t,i.command,i.task,i.lease,i.sequence,o.actor.monotonic_ms,o.actor.frame,1,ack_scope};
    }
    rt::Delivery request_withdrawal(const nc::Intent&)override{++return_calls;if(throw_return)throw std::runtime_error("injected withdrawal exception");return return_delivery;}
    nc::Withdrawal poll_withdrawal(const nc::Intent&)override{return r;}
    void mark_control_unknown(const nc::Intent&,const char*)override{++unknown_calls;}
    void event(const nc::Result&,const char* kind,const nc::Observation&,const nc::Withdrawal* receipt)override{events.emplace_back(kind);if(receipt)release_receipt_recorded=true;}
    void advance(uint32_t frames=1,uint64_t ms=50){o.actor.frame+=frames;o.actor.monotonic_ms+=ms;o.target.visibility_frame=o.actor.frame;o.target.visibility_monotonic_ms=o.actor.monotonic_ms;}
    void damage(nc::Origin origin=nc::Origin::Task,uint32_t source=55){
        auto i=intent();auto& d=o.damage;d.ticket=1;d.binding=binding();d.actor=actor();d.target=target();d.attack_command=i.command;d.task=i.task;d.lease=i.lease;
        d.source_object_id=source;d.frame=o.actor.frame;d.monotonic_ms=o.actor.monotonic_ms;d.hp_before=120;d.hp_after=114;d.reported_damage=6;d.origin=origin;
        d.identity_before=d.identity_after=d.visible_before=d.visible_after=d.source_verified=d.complete=true;
        d.shot_event_id=1;d.weapon_instance=0xd000;d.shot_frame=o.actor.frame-1;d.shot_monotonic_ms=o.actor.monotonic_ms-50;
        d.shot_command_link_verified=d.shot_target_link_verified=d.damage_shot_link_verified=true;
    }
    void released(bool home=true){
        r.binding=binding();r.actor=actor();r.task=id(10);r.lease=id(11);r.xyz=home?rt::Point{0,0,0}:rt::Point{40,0,0};
        r.frame=o.actor.frame;r.monotonic_ms=o.actor.monotonic_ms;r.original_deadline_frame=800;r.stance=0;
        r.complete=r.released=r.control_released=r.stance_restored=true;r.held=false;r.physical_home=home;
    }
};
static void admit_and_fire(Fake& f,nc::Controller& c){CHECK(c.submit(intent()).accepted);f.advance();CHECK(c.tick().phase==nc::Phase::WaitingDamage);CHECK(f.attack_calls==1);}
static void attributable_hit_and_physical_return(){
    Fake f;nc::Controller c(binding(),f,4);admit_and_fire(f,c);f.advance();f.damage();CHECK(c.tick().phase==nc::Phase::Withdrawing);
    CHECK(c.status().attributed_hit&&!c.status().task_completed&&f.return_calls==1);f.advance();f.released();auto r=c.tick();
    CHECK(r.phase==nc::Phase::Released&&r.task_completed&&r.attributed_hit&&r.physical_home&&r.control_released&&!r.held);
    CHECK(r.attributed_damage==6&&r.attack_attempts==1&&r.withdrawal_requests==1&&c.last_sequence()==5);
    auto before=f.events.size();CHECK(c.submit(intent()).task_completed);c.tick();CHECK(f.attack_calls==1&&f.return_calls==1&&f.events.size()==before);
}
static void validation_and_fresh_preflight_deny_without_attack(){
    for(unsigned mode=0;mode<12;mode++){
        Fake f;switch(mode){case 0:f.gate=false;break;case 1:f.o.target.visible=false;break;case 2:f.o.target.enemy=false;break;
        case 3:f.o.target.visibility_frame=90;break;case 4:f.o.target.visibility_monotonic_ms=1;break;case 5:f.o.actor_weapon.ammo=0;break;
        case 6:f.o.actor_weapon.range=10;break;case 7:f.o.actor.xyz={0,0,0};break;case 8:f.l.original_deadline_frame=900;break;
        case 9:f.o.target.identity.incarnation=0;break;case 10:f.o.actor.foreign_epoch=1;break;case 11:f.o.actor.paused=true;break;}
        nc::Controller c(binding(),f,4);CHECK(!c.submit(intent()).accepted);CHECK(f.attack_calls==0&&f.return_calls==0);
    }
    Fake f;nc::Controller c(binding(),f,4);CHECK(c.submit(intent()).accepted);f.advance();f.o.target.identity.incarnation=2;
    CHECK(c.tick().phase==nc::Phase::Withdrawing&&f.attack_calls==0&&f.return_calls==1);
}
static void unknown_attack_is_never_retried_or_auto_returned(){
    for(unsigned mode=0;mode<3;mode++){
        Fake f;f.delivery=mode==0?rt::Delivery::Unknown:rt::Delivery::Sent;f.throw_attack=mode==1;f.ack_scope=mode!=2;
        nc::Controller c(binding(),f,4);CHECK(c.submit(intent()).accepted);f.advance();CHECK(c.tick().phase==nc::Phase::Uncertain);
        auto before=f.events.size();c.tick();c.request_stop();c.tick();CHECK(c.submit(intent()).phase==nc::Phase::Uncertain);
        CHECK(f.attack_calls==1&&f.return_calls==0&&f.unknown_calls==1&&f.events.size()==before);
    }
}
static void not_sent_attack_withdraws_without_retry_or_success(){
    Fake f;f.delivery=rt::Delivery::NotSent;nc::Controller c(binding(),f,4);CHECK(c.submit(intent()).accepted);f.advance();
    CHECK(c.tick().phase==nc::Phase::Withdrawing&&f.attack_calls==1&&f.return_calls==1);f.advance();f.released();auto r=c.tick();
    CHECK(r.phase==nc::Phase::Released&&!r.task_completed&&!r.attributed_hit&&r.physical_home);c.tick();CHECK(f.attack_calls==1);
}
static void native_external_or_invalid_damage_cannot_be_task_effect(){
    for(unsigned mode=0;mode<7;mode++){
        Fake f;nc::Controller c(binding(),f,4);admit_and_fire(f,c);f.advance();f.damage();
        switch(mode){case 0:f.o.damage.origin=nc::Origin::Native;break;case 1:f.o.damage.source_object_id=99;break;
        case 2:f.o.damage.visible_before=false;break;case 3:f.o.damage.target.incarnation=2;break;
        case 4:f.o.damage.attack_command=id(999);break;case 5:f.o.damage.reported_damage=7;break;case 6:f.o.damage.hp_after=std::numeric_limits<float>::quiet_NaN();break;}
        CHECK(!c.tick().attributed_hit);f.advance(60);CHECK(c.tick().phase==nc::Phase::Withdrawing);f.advance();f.released();CHECK(!c.tick().task_completed);
    }
}
static void visibility_loss_and_evidence_loss_withdraw_without_fabricated_hit(){
    for(unsigned mode=0;mode<3;mode++){
        Fake f;nc::Controller c(binding(),f,4);admit_and_fire(f,c);f.advance();
        if(mode==0)f.o.target.visible=false;else if(mode==1)f.o.damage_overwritten=1;else f.o.target.live=false;
        CHECK(c.tick().phase==nc::Phase::Withdrawing&&!c.status().attributed_hit);CHECK(f.attack_calls==1&&f.return_calls==1);
    }
}
static void pause_stop_and_original_lease_clock_are_not_renewable(){
    Fake f;nc::Controller c(binding(),f,4);CHECK(c.submit(intent()).accepted);f.advance();f.o.actor.paused=true;
    c.tick();CHECK(f.attack_calls==0);c.request_stop();c.tick();CHECK(f.return_calls==0);f.o.actor.paused=false;f.advance();
    CHECK(c.tick().phase==nc::Phase::Withdrawing&&f.attack_calls==0&&f.return_calls==1);
    Fake g;g.l.original_begin_ms=1;g.o.actor.monotonic_ms=119900;g.o.target.visibility_monotonic_ms=119900;
    auto i=intent();i.expires_monotonic_ms=200000;nc::Controller d(binding(),g,4);CHECK(d.submit(i).accepted);
    g.advance(1,101);CHECK(d.tick().phase==nc::Phase::Uncertain&&g.attack_calls==0&&g.return_calls==0);
}
static void home_control_and_hit_are_independent_facts(){
    Fake f;nc::Controller c(binding(),f,4);admit_and_fire(f,c);f.advance();f.damage();c.tick();f.advance();f.released(false);auto r=c.tick();
    CHECK(r.phase==nc::Phase::Released&&r.attributed_hit&&r.control_released&&!r.physical_home&&!r.task_completed);
    Fake g;nc::Controller d(binding(),g,4);admit_and_fire(g,d);g.advance();g.damage();d.tick();g.advance();g.released();g.r.control_released=false;
    CHECK(d.tick().phase==nc::Phase::Uncertain&&!d.status().task_completed);
}
static void wrong_actor_or_foreign_command_blocks_every_new_write(){
    for(unsigned mode=0;mode<2;mode++){
        Fake f;nc::Controller c(binding(),f,4);admit_and_fire(f,c);f.advance();
        if(mode==0)f.o.actor.actor.generation++;else f.o.actor.foreign_epoch++;
        CHECK(c.tick().phase==nc::Phase::Uncertain&&f.return_calls==0&&f.attack_calls==1);
    }
}
static void unknown_withdrawal_is_not_resubmitted(){
    Fake f;f.return_delivery=rt::Delivery::Unknown;nc::Controller c(binding(),f,4);admit_and_fire(f,c);f.advance();f.damage();
    CHECK(c.tick().phase==nc::Phase::Uncertain);c.tick();c.request_stop();c.tick();CHECK(f.return_calls==1&&f.unknown_calls==1);
}
static void damage_needs_owned_shot_link_and_current_clock(){
    for(unsigned mode=0;mode<7;mode++){
        Fake f;nc::Controller c(binding(),f,4);admit_and_fire(f,c);f.advance();f.damage();
        switch(mode){case 0:f.o.damage.shot_event_id=0;break;case 1:f.o.damage.shot_command_link_verified=false;break;
        case 2:f.o.damage.damage_shot_link_verified=false;break;case 3:f.o.damage.shot_frame-=2;break;
        case 4:f.o.damage.frame++;break;case 5:f.o.damage.monotonic_ms++;break;case 6:f.o.damage.shot_target_link_verified=false;break;}
        CHECK(!c.tick().attributed_hit);CHECK(f.attack_calls==1);
    }
}
static void completed_return_receipt_precedes_later_native_owner_sample(){
    Fake f;nc::Controller c(binding(),f,4);admit_and_fire(f,c);f.advance();f.damage();c.tick();f.advance();f.released();
    auto actual_frame=f.r.frame;f.advance(2);f.o.actor.team=f.o.actor.default_team;f.o.actor.actor.generation=2;f.l.held=false;
    auto r=c.tick();CHECK(r.phase==nc::Phase::Released&&r.task_completed&&f.release_receipt_recorded);
    CHECK(actual_frame<r.frame&&f.unknown_calls==0&&f.return_calls==1);
}
static void original_lease_cannot_be_changed_while_target_remains_valid(){
    for(unsigned mode=0;mode<7;mode++){
        Fake f;nc::Controller c(binding(),f,4);CHECK(c.submit(intent()).accepted);f.advance();
        switch(mode){case 0:f.l.lease=id(99);break;case 1:f.l.original_begin_ms++;break;
        case 2:f.l.original_deadline_frame++;break;case 3:f.l.home={1,0,0};break;
        case 4:f.l.original_begin_frame++;break;case 5:f.l.native_sequence=3;break;case 6:f.l.native_sequence=6;break;}
        CHECK(c.tick().phase==nc::Phase::Uncertain&&f.attack_calls==0&&f.return_calls==0);
    }
}
static void refusal_preserves_parent_control_and_sequence_frame_fences(){
    for(unsigned mode=0;mode<10;mode++){
        Fake f;auto i=intent();auto b=binding();
        switch(mode){case 0:i.command={};break;case 1:i.sequence=4;break;case 2:f.l.native_sequence=0;break;
        case 3:f.l.native_sequence=6;break;case 4:f.l.original_begin_frame=0;break;
        case 5:f.l.original_begin_frame=101;break;case 6:f.l.original_deadline_frame=i.lease_deadline_frame=1000;break;
        case 7:b.thread=0;f.l.binding=b;f.o.actor.binding=b;f.o.actor.current_thread=0;break;
        case 8:b.binding_hash={};f.l.binding=b;f.o.actor.binding=b;break;case 9:b.session={};f.l.binding=b;f.o.actor.binding=b;break;}
        nc::Controller c(b,f,0);auto r=c.submit(i);CHECK(!r.accepted&&r.held&&!r.control_released);
        CHECK(r.task==f.l.task&&r.lease==f.l.lease&&f.attack_calls==0&&f.return_calls==0);
    }
    Fake f;nc::Controller c(binding(),f,4);CHECK(c.submit(intent()).accepted);f.l.native_sequence=5;f.advance();
    CHECK(c.tick().phase==nc::Phase::WaitingDamage&&f.attack_calls==1);
}
static void configurable_limits_cannot_expand_reviewed_scope(){
    for(unsigned mode=0;mode<9;mode++){
        Fake f;nc::Limits l;
        switch(mode){case 0:l.max_original_lease_ms++;break;case 1:l.max_original_lease_frames++;break;
        case 2:l.max_visibility_age_ms++;break;case 3:l.max_target_distance++;break;case 4:l.attack_observation_frames++;break;
        case 5:l.max_observation_gap_ms++;break;case 6:l.arrival_radius++;break;case 7:l.height_delta=std::numeric_limits<float>::quiet_NaN();break;
        case 8:l.damage_tolerance=1;break;}
        bool refused=false;try{nc::Controller c(binding(),f,4,l);}catch(const std::invalid_argument&){refused=true;}CHECK(refused&&f.attack_calls==0);
    }
    Fake f;f.l.actor.born_frame=f.o.actor.actor.born_frame=200;auto i=intent();i.actor.born_frame=200;
    nc::Controller c(binding(),f,4);CHECK(!c.submit(i).accepted);
}
int main(){
    try{attributable_hit_and_physical_return();validation_and_fresh_preflight_deny_without_attack();unknown_attack_is_never_retried_or_auto_returned();
        not_sent_attack_withdraws_without_retry_or_success();native_external_or_invalid_damage_cannot_be_task_effect();
        visibility_loss_and_evidence_loss_withdraw_without_fabricated_hit();pause_stop_and_original_lease_clock_are_not_renewable();
        home_control_and_hit_are_independent_facts();wrong_actor_or_foreign_command_blocks_every_new_write();unknown_withdrawal_is_not_resubmitted();
        damage_needs_owned_shot_link_and_current_clock();completed_return_receipt_precedes_later_native_owner_sample();
        original_lease_cannot_be_changed_while_target_remains_valid();
        refusal_preserves_parent_control_and_sequence_frame_fences();
        configurable_limits_cannot_expand_reviewed_scope();
        std::cout<<"15 near-combat replay groups passed; explicit fake IO, no native game calls\n";return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
