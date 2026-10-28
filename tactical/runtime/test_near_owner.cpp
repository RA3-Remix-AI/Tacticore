#include "near_owner.h"
#include <string>
#include <iostream>
#include <stdexcept>
#include <vector>
namespace rt=tacticore::runtime;namespace nc=rt::near_combat;
#define CHECK(x) do{if(!(x))throw std::runtime_error(std::string(__func__)+":"+std::to_string(__LINE__)+":"+#x);}while(0)
static rt::Id id(uint32_t n){return {n,2,3,4};}
static rt::Binding binding(){rt::Binding b;b.session=id(1);b.commander=id(2);b.host=id(3);b.binding_hash[0]=4;b.player=3;b.pid=10;b.thread=20;b.process_start=123;return b;}
static rt::Actor actor(){return {55,0x5000,0x7000,0x6000,0x2000,0x19ab11af,90,1};}
static nc::Target target(){return {id(50),77,0x9000,0xa000,0xb000,0xc000,0x19ab11af,95,1};}
static rt::Command command(uint32_t seq,rt::Operation op){rt::Command c;c.command=id(100+seq);c.task=id(10);c.lease=id(11);c.sequence=seq;c.actor=actor();c.operation=op;c.expires_frame=800;c.lease_deadline_frame=800;c.expires_monotonic_ms=70000;if(op==rt::Operation::MoveHold){c.target={40,0,0};c.hold_frames=700;}return c;}
static nc::Intent intent(){nc::Intent i;i.command=id(103);i.task=id(10);i.lease=id(11);i.sequence=3;i.actor=actor();i.target_key=target().key;i.expires_frame=500;i.lease_deadline_frame=800;i.expires_monotonic_ms=20000;return i;}
struct Fake:rt::IO,nc::Execution {
    rt::Sample s{};nc::CombatFacts f{};std::vector<rt::Action> calls;std::vector<rt::Event> movement_events;
    uint32_t attack_calls=0,unknown_calls=0,shot_frame=0;uint64_t shot_ms=0;
    bool gate=true,recruit_after_release=false,receipt_seen=false;rt::Delivery attack_delivery=rt::Delivery::Sent,move_delivery=rt::Delivery::Sent;
    rt::NativePreemption preemption=rt::NativePreemption::None;
    Fake(){
        s.binding=binding();s.actor=actor();s.frame=100;s.monotonic_ms=1000;s.current_thread=20;
        s.team=s.default_team=0x3000;s.script_team=0x4000;s.identity=s.actor_birth_verified=s.live_list_member=s.grounded=s.settled=s.interference_guard_ready=true;s.paused=false;
        f.target.identity=target();f.target.xyz={80,0,0};f.target.hp=120;
        f.target.identity_verified=f.target.live=f.target.grounded=f.target.enemy=f.target.visible=f.target.visibility_complete=true;
        f.weapon.identity_verified=f.weapon.ready=f.weapon.ground_target_supported=true;f.weapon.ammo=3;f.weapon.range=100;
    }
    rt::Sample sample()override{return s;}
    bool ground_target(rt::Point)override{return true;}
    bool remember_home(const rt::Sample&)override{return true;}
    bool independent_borrow_permitted(const rt::Sample&)override{return true;}
    bool return_home_clear(const rt::Sample&,rt::Point)override{return true;}
    rt::Delivery issue(rt::Action a,rt::Point p,uint32_t stance)override{
        calls.push_back(a);if(move_delivery!=rt::Delivery::Sent)return move_delivery;
        switch(a){case rt::Action::Borrow:s.team=s.script_team;break;case rt::Action::TransferBack:s.team=s.default_team;break;
        case rt::Action::HoldStance:case rt::Action::RestoreStance:s.stance=stance;break;
        case rt::Action::Move:s.xyz=p;s.normal_move_owned=true;break;case rt::Action::Stop:s.settled=true;s.path=0;s.command_source=1;break;}
        return rt::Delivery::Sent;
    }
    void event(const rt::Event& e)override{
        movement_events.push_back(e);
        if(recruit_after_release&&e.receipt.phase==rt::Phase::Released){s.actor.generation++;s.team=0x8888;}
    }
    rt::NativePreemption take_native_preemption(const rt::Sample&)override{auto p=preemption;if(p!=rt::NativePreemption::WaitingYield)preemption=rt::NativePreemption::None;return p;}
    nc::CombatFacts facts(const rt::Sample& a,const rt::Id&)override{f.target.visibility_frame=a.frame;f.target.visibility_monotonic_ms=a.monotonic_ms;return f;}
    bool independent_attack_admission(const nc::Lease&,const nc::Intent&,const nc::Observation&)override{return gate;}
    nc::AttackAcknowledgement attack_once(const nc::Lease& l,const nc::Intent& i,const nc::Target& t)override{
        ++attack_calls;shot_frame=s.frame;shot_ms=s.monotonic_ms;s.settled=false;
        return {attack_delivery,l.binding,l.actor,t,i.command,i.task,i.lease,i.sequence,s.monotonic_ms,s.frame,1,true};
    }
    void mark_control_unknown(const nc::Intent&,const char*)override{++unknown_calls;}
    void event(const nc::Result&,const char*,const nc::Observation&,const nc::Withdrawal* receipt)override{if(receipt)receipt_seen=true;}
    void advance(nc::Owner& o){s.frame++;s.monotonic_ms+=50;o.tick();}
    void damage(){
        auto& d=f.damage;auto i=intent();d.ticket=1;d.binding=binding();d.actor=actor();d.target=target();d.attack_command=i.command;d.task=i.task;d.lease=i.lease;
        d.source_object_id=55;d.frame=s.frame;d.monotonic_ms=s.monotonic_ms;d.shot_event_id=1;d.weapon_instance=0xd000;
        d.shot_frame=shot_frame;d.shot_monotonic_ms=shot_ms;d.hp_before=120;d.hp_after=114;d.reported_damage=6;d.origin=nc::Origin::Task;
        d.identity_before=d.identity_after=d.visible_before=d.visible_after=d.source_verified=d.complete=true;
        d.shot_command_link_verified=d.shot_target_link_verified=d.damage_shot_link_verified=true;
    }
};
static void approach(Fake& f,nc::Owner& o){
    CHECK(o.submit(command(1,rt::Operation::Reserve)).accepted);
    for(unsigned n=0;n<25&&o.movement_status().phase!=rt::Phase::Ready;n++)f.advance(o);
    CHECK(o.movement_status().phase==rt::Phase::Ready);CHECK(o.submit(command(2,rt::Operation::MoveHold)).accepted);
    for(unsigned n=0;n<25&&o.movement_status().phase!=rt::Phase::Holding;n++)f.advance(o);
    CHECK(o.movement_status().phase==rt::Phase::Holding&&f.s.xyz.x==40);
}
static void admit(Fake& f,nc::Owner& o){approach(f,o);CHECK(o.submit(intent(),command(4,rt::Operation::ReturnHome)).accepted);}
static void finish(Fake& f,nc::Owner& o){for(unsigned n=0;n<45&&o.combat_status().phase!=nc::Phase::Released&&o.combat_status().phase!=nc::Phase::Uncertain;n++)f.advance(o);}
static void composite_reuses_actual_original_stop_home_and_release(){
    Fake f;nc::Owner o(binding(),f,f,0);admit(f,o);f.advance(o);CHECK(o.combat_status().phase==nc::Phase::WaitingDamage);
    CHECK(o.movement_status().phase==rt::Phase::Holding&&!f.s.settled);
    f.s.frame++;f.s.monotonic_ms+=50;f.damage();o.tick();CHECK(o.last_sequence()==4);finish(f,o);
    auto r=o.combat_status();auto m=o.movement_status();CHECK(r.task_completed&&r.physical_home&&r.control_released&&f.receipt_seen);
    CHECK((m.phase==rt::Phase::Released&&m.physical_home&&m.sdk_calls==std::array<uint32_t,6>{1,1,4,2,1,1}));
    CHECK(f.attack_calls==1&&o.last_sequence()==4&&f.unknown_calls==0);
}
static void stop_prepared_never_fires_and_uses_same_original_home(){
    Fake f;nc::Owner o(binding(),f,f,0);admit(f,o);o.request_stop();f.advance(o);finish(f,o);
    CHECK(o.combat_status().phase==nc::Phase::Released&&o.combat_status().cancelled&&!o.combat_status().task_completed);
    CHECK(o.combat_status().physical_home&&f.attack_calls==0&&o.movement_status().sdk_calls[0]==1);
}
static void unknown_attack_holds_both_owners_without_automatic_compensation(){
    Fake f;f.attack_delivery=rt::Delivery::Unknown;nc::Owner o(binding(),f,f,0);admit(f,o);f.advance(o);
    auto calls=f.calls.size();CHECK(o.combat_status().phase==nc::Phase::Uncertain&&o.movement_status().phase==rt::Phase::Uncertain);
    o.request_stop();for(unsigned n=0;n<10;n++)f.advance(o);
    CHECK(!o.submit(command(4,rt::Operation::ReturnHome)).accepted&&f.calls.size()==calls&&f.attack_calls==1&&f.unknown_calls==1);
}
static void shared_sequence_and_immutable_withdrawal_are_not_bypassed(){
    Fake f;nc::Owner o(binding(),f,f,0);approach(f,o);auto i=intent();auto back=command(4,rt::Operation::ReturnHome);
    auto duplicate=i;duplicate.command=id(101);CHECK(!o.submit(duplicate,back).accepted);
    auto reused=back;reused.command=id(102);CHECK(!o.submit(i,reused).accepted);
    auto bad=back;bad.lease_deadline_frame++;CHECK(!o.submit(i,bad).accepted);bad=back;bad.operation=rt::Operation::EmergencyRelease;CHECK(!o.submit(i,bad).accepted);
    CHECK(o.submit(i,back).accepted);auto count=f.calls.size();CHECK(o.submit(i,back).accepted);
    back.target={1,0,0};CHECK(!o.submit(i,back).accepted);CHECK(!o.submit(command(5,rt::Operation::Query)).accepted);
    CHECK(f.calls.size()==count&&o.last_sequence()==3&&f.attack_calls==0);
}
static void preparation_requires_original_holding_and_actual_target_admission(){
    Fake f;nc::Owner o(binding(),f,f,0);CHECK(!o.submit(intent(),command(4,rt::Operation::ReturnHome)).accepted);approach(f,o);
    f.gate=false;auto r=o.submit(intent(),command(4,rt::Operation::ReturnHome));CHECK(!r.accepted&&r.held&&o.last_sequence()==2&&f.attack_calls==0);
    f.gate=true;f.s.stance=0;r=o.submit(intent(),command(4,rt::Operation::ReturnHome));CHECK(!r.accepted&&r.held&&f.attack_calls==0);
}
static void native_yield_is_delegated_without_ignoring_unknown_sources(){
    {
        Fake f;nc::Owner o(binding(),f,f,0);approach(f,o);f.preemption=rt::NativePreemption::VerifiedYield;f.gate=false;
        CHECK(!o.submit(intent(),command(4,rt::Operation::ReturnHome)).accepted);
        CHECK(f.preemption==rt::NativePreemption::VerifiedYield);f.advance(o);
        CHECK(f.preemption==rt::NativePreemption::None&&o.movement_status().phase==rt::Phase::ReturnBraking&&f.attack_calls==0);
    }
    for(auto p:{rt::NativePreemption::VerifiedYield,rt::NativePreemption::UnverifiedYield,rt::NativePreemption::WaitingYield}){
        Fake f;nc::Owner o(binding(),f,f,0);admit(f,o);f.preemption=p;auto count=f.calls.size();f.advance(o);CHECK(f.attack_calls==0);
        if(p==rt::NativePreemption::VerifiedYield){finish(f,o);CHECK(o.combat_status().phase==nc::Phase::Released&&!o.combat_status().task_completed);}
        else if(p==rt::NativePreemption::UnverifiedYield)CHECK(o.combat_status().phase==nc::Phase::Uncertain&&f.calls.size()==count);
        else CHECK(o.combat_status().phase==nc::Phase::Prepared&&f.calls.size()==count);
    }
}
static void unknown_original_return_is_never_retried(){
    Fake f;nc::Owner o(binding(),f,f,0);admit(f,o);o.request_stop();f.advance(o);f.move_delivery=rt::Delivery::Unknown;f.advance(o);
    CHECK(o.combat_status().phase==nc::Phase::Uncertain);auto calls=f.calls.size();for(unsigned n=0;n<10;n++)f.advance(o);
    CHECK(f.calls.size()==calls&&f.unknown_calls==1&&o.combat_status().held);
}
static void original_release_receipt_survives_immediate_native_recruitment(){
    Fake f;f.recruit_after_release=true;nc::Owner o(binding(),f,f,0);admit(f,o);f.advance(o);
    f.s.frame++;f.s.monotonic_ms+=50;f.damage();o.tick();finish(f,o);
    CHECK(o.combat_status().task_completed&&o.combat_status().control_released&&f.receipt_seen&&f.s.actor.generation==2);
}
static void long_pause_keeps_real_motion_clock_without_renewing_work(){
    for(bool fired:{false,true}){
        Fake f;nc::Owner o(binding(),f,f,0);admit(f,o);if(fired)f.advance(o);
        f.s.paused=true;auto count=f.calls.size();auto attacks=f.attack_calls;auto frame=f.s.frame;
        for(unsigned n=0;n<6;n++){f.s.monotonic_ms+=5000;o.tick();CHECK(f.calls.size()==count&&f.attack_calls==attacks);}
        CHECK(f.s.frame==frame&&o.movement_status().phase==rt::Phase::Holding);
        f.s.paused=false;f.advance(o);CHECK(o.combat_status().phase==nc::Phase::Withdrawing);finish(f,o);
        CHECK(o.combat_status().phase==nc::Phase::Released&&!o.combat_status().task_completed&&o.combat_status().physical_home);
        CHECK(f.attack_calls==attacks&&f.unknown_calls==0&&o.last_sequence()==4);
    }
}
int main(){try{composite_reuses_actual_original_stop_home_and_release();stop_prepared_never_fires_and_uses_same_original_home();
    unknown_attack_holds_both_owners_without_automatic_compensation();shared_sequence_and_immutable_withdrawal_are_not_bypassed();
    preparation_requires_original_holding_and_actual_target_admission();native_yield_is_delegated_without_ignoring_unknown_sources();
    unknown_original_return_is_never_retried();original_release_receipt_survives_immediate_native_recruitment();
    long_pause_keeps_real_motion_clock_without_renewing_work();
    std::cout<<"9 composite-owner replay groups passed; original motion controller plus fake native IO, no SDK\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
