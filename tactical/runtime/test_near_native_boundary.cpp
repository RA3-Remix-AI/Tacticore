// Link the actual Win32 observer, but never install hooks or open a game.
#include "near_native_hooks.h"
#include "near_build_policy.h"
#include "near_native_factory.h"
#include <windows.h>
#include <string>
#include <iostream>
#include <stdexcept>
namespace rt=tacticore::runtime;namespace nc=rt::near_combat;
#define CHECK(x) do{if(!(x))throw std::runtime_error(std::string(__func__)+":"+std::to_string(__LINE__)+":"+#x);}while(0)
static rt::Id id(uint32_t n){return {n,2,3,4};}
static rt::Binding binding(){rt::Binding b;b.session=id(1);b.commander=id(2);b.host=id(3);b.binding_hash[0]=4;b.player=3;b.pid=GetCurrentProcessId();b.thread=GetCurrentThreadId();b.process_start=123;return b;}
static rt::Actor actor(){return {55,0x50000,0x70000,0x60000,0x20000,0x19ab11af,90,1};}
static nc::Target target(){return {id(50),77,0x90000,0xa0000,0xb0000,0xc0000,0x19ab11af,95,1};}
struct Memory:rt::Memory {
    uint32_t reads=0;
    bool read(uint32_t,void*,uint32_t)override{++reads;throw std::runtime_error("uninstalled observer must not read a game");}
    rt::Binding current_binding()override{return binding();}
    uint32_t thread()override{return GetCurrentThreadId();}
    uint64_t monotonic_ms()override{return GetTickCount64();}
};
static void default_admission_cannot_be_elevated_by_packet_flags(){
    rt::NativeAttackAdmission admission;nc::Lease l;l.binding=binding();l.actor=actor();l.held=l.private_home_verified=l.ready_at_owned_endpoint=true;
    nc::Intent i;i.command=id(100);i.task=id(10);i.lease=id(11);i.sequence=3;i.actor=actor();i.target_key=target().key;
    CHECK(!admission.permit(l,i,target(),rt::AttackBoundary::Facade));CHECK(!admission.permit(l,i,target(),rt::AttackBoundary::PrivateDelivery));
}
static void actual_uninstalled_observer_never_calls_attack_or_motion_sdk(){
    Memory memory;rt::NativeAttackAdmission admission;auto o=rt::make_near_native_observer(binding(),{},actor(),memory,admission);
    CHECK(o->no_hooks_enabled()&&!o->installed_and_originals_verified()&&o->active_callbacks()==0&&!o->restored_mask());
    nc::Lease l;l.binding=binding();l.actor=actor();l.held=l.private_home_verified=l.ready_at_owned_endpoint=true;
    nc::Intent i;i.command=id(100);i.task=id(10);i.lease=id(11);i.sequence=3;i.actor=actor();i.target_key=target().key;
    auto ack=o->attack_once(l,i,target());CHECK(ack.delivery==rt::Delivery::NotSent&&!ack.own_scope_verified);
    CHECK(o->call(rt::Action::Move,actor(),{},rt::Point{40,0,0},0)==rt::Delivery::NotSent);
    CHECK(memory.reads==0&&!o->attack_delivered()&&!o->weapon_selection().verified&&o->foreign_epoch()==0);
}
static void uninstalled_close_and_destruction_keep_originals_untouched(){
    Memory memory;rt::NativeAttackAdmission admission;
    {auto o=rt::make_near_native_observer(binding(),{},actor(),memory,admission);
        CHECK(o->close_after_verified_release()&&o->no_hooks_enabled()&&!o->restored_mask());
        CHECK(!o->diagnostic_fault_enabled()&&o->diagnostic_foreign_move({})==rt::Delivery::NotSent);}
    CHECK(memory.reads==0);
}
static void exact_build_policy_cannot_be_minted_in_a_helper_process(){
    auto b=binding();FILETIME c{},e{},k{},u{};CHECK(GetProcessTimes(GetCurrentProcess(),&c,&e,&k,&u));
    b.process_start=(uint64_t(c.dwHighDateTime)<<32)|c.dwLowDateTime;
    CHECK(!nc::NearBuildPolicy::verify_current_game(b,L"unused",L"unused",L"unused"));
    b.pid++;CHECK(!nc::NearBuildPolicy::verify_current_game(b,L"unused",L"unused",L"unused"));
}
static void actual_near_factory_refuses_helper_and_invalid_bootstrap_before_hooks(){
    for(unsigned mode=0;mode<3;mode++){
        nc::NativeBootstrap boot;boot.original.binding=binding();boot.original.actor=actor();
        boot.original.actor.generation=boot.original.actor.born_frame=0;
        if(mode==1)boot.schema=1;
        if(mode==2)boot.original.experimental_flags=1;
        uint32_t events=0,traces=0,combat=0;bool denied=false;
        try{auto runtime=nc::create_near_runtime(boot,[&](const rt::Event&){events++;},[&](const rt::HookTrace&){traces++;},
            [&](const nc::Result&,const char*,const nc::Observation&,const nc::Withdrawal*){combat++;});}
        catch(const rt::FactoryError& e){denied=e.safe_no_hooks;}
        CHECK(denied&&events==0&&traces==0&&combat==0);
    }
}
int main(){try{default_admission_cannot_be_elevated_by_packet_flags();actual_uninstalled_observer_never_calls_attack_or_motion_sdk();
    uninstalled_close_and_destruction_keep_originals_untouched();
    exact_build_policy_cannot_be_minted_in_a_helper_process();
    actual_near_factory_refuses_helper_and_invalid_bootstrap_before_hooks();
    std::cout<<"5 actual Win32 native-boundary groups passed; observer uninstalled, fake memory, no game SDK\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
