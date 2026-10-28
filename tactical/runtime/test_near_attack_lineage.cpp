#include "near_attack_lineage.h"
#include "near_move_lineage.h"
#include <string>
#include <iostream>
#include <stdexcept>
namespace rt=tacticore::runtime;namespace nc=rt::near_combat;
#define CHECK(x) do{if(!(x))throw std::runtime_error(std::string(__func__)+":"+std::to_string(__LINE__)+":"+#x);}while(0)
static rt::Id id(uint32_t n){return {n,2,3,4};}
static rt::Binding binding(){rt::Binding b;b.session=id(1);b.commander=id(2);b.host=id(3);b.binding_hash[0]=4;b.player=3;b.pid=10;b.thread=20;b.process_start=123;return b;}
static rt::Actor actor(){return {55,0x50000,0x70000,0x60000,0x20000,0x19ab11af,90,1};}
static nc::Target target(){return {id(50),77,0x90000,0xa0000,0xb0000,0xc0000,0x19ab11af,95,1};}
static nc::Intent intent(){nc::Intent i;i.command=id(100);i.task=id(10);i.lease=id(11);i.target_key=target().key;i.sequence=5;i.actor=actor();i.expires_frame=140;i.lease_deadline_frame=800;i.expires_monotonic_ms=20000;return i;}
struct Fixture {
    nc::AttackLineage l{binding(),actor()};std::array<uint32_t,23> c{};std::array<uint32_t,24> before{},after{};
    Fixture(){c[0]=11;c[1]=1;c[5]=target().thing;c[17]=1;c[22]=1;before[0]=0xffffffffu;
        std::memcpy(after.data(),c.data(),20);after[5]=target().object_id;std::memcpy(after.data()+16,c.data()+15,16);after[22]=c[21];after[23]=1;}
    void begin(){CHECK(l.arm(intent(),target(),20,100));CHECK(l.facade_enter(actor().update+0x24,target().thing,1,1,20,100,true));
        CHECK(l.dispatch_enter(actor().update+0x24,0x100000,c.data(),0x5722b5,20,100,true));}
    void stored(){begin();CHECK(l.copy_before(actor().update+0x310,0x100000,before.data(),c.data(),0x787d42,20,100,true));
        CHECK(l.copy_after(before.data(),after.data(),c.data()));CHECK(l.dispatch_exit({}));CHECK(l.facade_exit());CHECK(l.submitted()&&l.pending()&&!l.delivered());}
    void decoded(){stored();CHECK(l.unpack_before(actor().update+0x310,actor().thing,0x110000,after.data(),0x7da0b3,20,101,false));
        CHECK(l.unpack_after(true,c.data()));CHECK(l.dispatch_enter(actor().update+0x24,0x110000,c.data(),0x7da0d9,20,101,false));}
};
static void direct_and_deferred_pipeline_are_distinct(){
    Fixture f;f.begin();CHECK(f.l.private_attack(actor().update,target().thing,1,1,0x785dd0,20,100,true));CHECK(f.l.dispatch_exit({}));CHECK(f.l.facade_exit());CHECK(f.l.submitted()&&f.l.delivered()&&!f.l.pending());
    Fixture g;g.decoded();CHECK(g.l.private_attack(actor().update,target().thing,1,1,0x785dd0,20,101,false));CHECK(g.l.dispatch_exit({}));CHECK(g.l.delivered()&&!g.l.pending());
}
static void copy_must_convert_target_pointer_to_id(){
    Fixture f;f.begin();CHECK(f.l.copy_before(actor().update+0x310,0x100000,f.before.data(),f.c.data(),0x787d42,20,100,true));
    f.after[5]=target().thing;CHECK(!f.l.copy_after(f.before.data(),f.after.data(),f.c.data()));CHECK(f.l.failed()&&!f.l.submitted());
    Fixture g;g.stored();g.c[5]=target().thing+4;CHECK(g.l.unpack_before(actor().update+0x310,actor().thing,0x110000,g.after.data(),0x7da0b3,20,101,false));CHECK(!g.l.unpack_after(true,g.c.data()));
}
static void source_zero_unlimited_or_other_target_cannot_be_owned(){
    for(unsigned mode=0;mode<4;mode++){
        Fixture f;f.begin();uint32_t t=target().thing,n=1,s=1,caller=0x785dd0;
        switch(mode){case 0:s=0;break;case 1:n=0x7fffffff;break;case 2:t+=4;break;case 3:caller++;break;}
        CHECK(!f.l.private_attack(actor().update,t,n,s,caller,20,100,true)&&f.l.failed());
    }
}
static void a_scope_boolean_cannot_replace_dispatch_or_copy(){
    Fixture f;CHECK(f.l.arm(intent(),target(),20,100));CHECK(f.l.facade_enter(actor().update+0x24,target().thing,1,1,20,100,true));
    CHECK(!f.l.private_attack(actor().update,target().thing,1,1,0x785dd0,20,100,true));
    Fixture g;CHECK(g.l.arm(intent(),target(),20,100));CHECK(!g.l.copy_after(g.before.data(),g.after.data(),g.c.data()));
    Fixture h;h.begin();CHECK(!h.l.facade_exit());
}
static void pending_payload_and_decoded_address_are_immutable(){
    for(unsigned mode=0;mode<3;mode++){
        Fixture f;f.stored();if(mode==0)f.after[18]=0x7fffffff;
        bool ready=f.l.unpack_before(actor().update+0x310,actor().thing,0x110000,f.after.data(),0x7da0b3,20,101,false);
        if(mode==0){CHECK(!ready);continue;}CHECK(ready);if(mode==1)f.c[17]=2;
        bool decoded=f.l.unpack_after(true,f.c.data());if(mode==1){CHECK(!decoded);continue;}CHECK(decoded);
        CHECK(!f.l.dispatch_enter(actor().update+0x24,0x110004,f.c.data(),0x7da0d9,20,101,false));
    }
}
static void command_can_never_be_delivered_twice_or_rearmed(){
    Fixture f;f.decoded();CHECK(f.l.private_attack(actor().update,target().thing,1,1,0x785dd0,20,101,false));
    CHECK(!f.l.private_attack(actor().update,target().thing,1,1,0x785dd0,20,101,false));
    CHECK(!f.l.arm(intent(),target(),20,102));
}
static void wrong_thread_or_expired_command_never_dispatches(){
    for(unsigned mode=0;mode<4;mode++){
        Fixture f;f.stored();uint32_t thread=20,frame=101,caller=0x7da0b3;
        switch(mode){case 0:thread++;break;case 1:frame=99;break;case 2:frame=140;break;case 3:caller++;break;}
        CHECK(!f.l.unpack_before(actor().update+0x310,actor().thing,0x110000,f.after.data(),caller,thread,frame,false));
        CHECK(f.l.failed()&&!f.l.delivered());
    }
}
static void native_failure_or_foreign_preemption_never_mints_delivery(){
    Fixture f;f.stored();CHECK(f.l.unpack_before(actor().update+0x310,actor().thing,0x110000,f.after.data(),0x7da0b3,20,101,false));CHECK(!f.l.unpack_after(false,f.c.data()));
    Fixture g;g.decoded();CHECK(!g.l.dispatch_exit({})&&!g.l.delivered());
    Fixture h;h.decoded();h.l.foreign();CHECK(!h.l.private_attack(actor().update,target().thing,1,1,0x785dd0,20,101,false));
}
static std::array<uint32_t,23> stop_command(){std::array<uint32_t,23> c{};c[0]=5;c[1]=1;c[22]=1;return c;}
static std::array<uint32_t,24> stop_storage(const std::array<uint32_t,23>& c){std::array<uint32_t,24> s{};std::memcpy(s.data(),c.data(),24);std::memcpy(s.data()+16,c.data()+15,16);s[22]=c[21];s[23]=1;return s;}
static void owned_stop_can_replace_pending_attack_even_after_work_expiry(){
    Fixture f;f.stored();auto proof=f.l.pending_replacement(f.after.data(),20,140);CHECK(proof.valid());
    auto c=stop_command();auto after=stop_storage(c);rt::NearMoveLineage motion(20,actor().thing,actor().update);
    CHECK(motion.arm_stop(20,140));CHECK(motion.stop_facade_enter(actor().update+0x24,1,20,140,true));
    CHECK(motion.dispatch_enter(actor().update+0x24,0x120000,c.data(),0x54b0c5,20,140,true));
    CHECK(motion.copy_before(actor().update+0x310,0x120000,f.after.data(),c.data(),0x787d42,20,140,true,&proof));
    CHECK(motion.copy_after(f.after.data(),after.data(),c.data()));
    CHECK(f.l.cancel_after_stop_copy(proof,f.after.data(),after.data(),c.data(),20,140));
    motion.dispatch_exit({});motion.facade_exit();CHECK(f.l.cancelled()&&!f.l.delivered()&&!f.l.pending()&&motion.pending());
    CHECK(motion.unpack_before(actor().update+0x310,actor().thing,0x130000,after.data(),0x7da0b3,20,141,false));CHECK(motion.unpack_after(true,c.data()));
    CHECK(motion.dispatch_enter(actor().update+0x24,0x130000,c.data(),0x7da0d9,20,141,false));
    CHECK(motion.private_stop(actor().update,1,0x787791,20,141,false));motion.dispatch_exit({});CHECK(motion.stop_delivered()&&motion.epoch()==0);
}
static void unsealed_or_stale_replacement_never_relabels_a_busy_slot(){
    for(unsigned mode=0;mode<3;mode++){
        Fixture f;f.stored();auto proof=mode==0?nc::AttackLineage::PendingReplacement{}:f.l.pending_replacement(f.after.data(),20,101);
        if(mode==1){f.after[5]++;}
        auto c=stop_command();rt::NearMoveLineage motion(20,actor().thing,actor().update);
        CHECK(motion.arm_stop(20,mode==2?102:101));CHECK(motion.stop_facade_enter(actor().update+0x24,1,20,mode==2?102:101,true));
        CHECK(motion.dispatch_enter(actor().update+0x24,0x120000,c.data(),0x54b0c5,20,mode==2?102:101,true));
        CHECK(!motion.copy_before(actor().update+0x310,0x120000,f.after.data(),c.data(),0x787d42,20,mode==2?102:101,true,&proof));CHECK(motion.epoch()==1);
    }
}
static void replacement_authorizes_only_stop_and_exact_native_copy_result(){
    Fixture f;f.stored();auto proof=f.l.pending_replacement(f.after.data(),20,101);auto c=stop_command();c[0]=0;
    rt::NearMoveLineage motion(20,actor().thing,actor().update);CHECK(motion.arm({},20,101));CHECK(motion.facade_enter(actor().update+0x24,{},1,20,101,true));
    CHECK(motion.dispatch_enter(actor().update+0x24,0x120000,c.data(),0x571db5,20,101,true));
    CHECK(!motion.copy_before(actor().update+0x310,0x120000,f.after.data(),c.data(),0x787d42,20,101,true,&proof));
    Fixture g;g.stored();auto stop=stop_command();auto after=stop_storage(stop);after[0]=11;
    CHECK(!g.l.cancel_after_stop_copy(g.l.pending_replacement(g.after.data(),20,101),g.after.data(),after.data(),stop.data(),20,101));
}
static void already_unpacked_or_delivered_attack_cannot_be_claimed_cancelled(){
    Fixture f;f.stored();auto proof=f.l.pending_replacement(f.after.data(),20,101);auto c=stop_command();auto after=stop_storage(c);
    CHECK(f.l.unpack_before(actor().update+0x310,actor().thing,0x110000,f.after.data(),0x7da0b3,20,101,false));CHECK(f.l.unpack_after(true,f.c.data()));
    CHECK(!f.l.pending_replacement(f.after.data(),20,101).valid());CHECK(!f.l.cancel_after_stop_copy(proof,f.after.data(),after.data(),c.data(),20,101));
    Fixture g;g.decoded();CHECK(g.l.private_attack(actor().update,target().thing,1,1,0x785dd0,20,101,false));CHECK(!g.l.pending_replacement(g.after.data(),20,101).valid());
}
int main(){try{direct_and_deferred_pipeline_are_distinct();copy_must_convert_target_pointer_to_id();source_zero_unlimited_or_other_target_cannot_be_owned();
    a_scope_boolean_cannot_replace_dispatch_or_copy();pending_payload_and_decoded_address_are_immutable();command_can_never_be_delivered_twice_or_rearmed();
    wrong_thread_or_expired_command_never_dispatches();native_failure_or_foreign_preemption_never_mints_delivery();
    owned_stop_can_replace_pending_attack_even_after_work_expiry();unsealed_or_stale_replacement_never_relabels_a_busy_slot();
    replacement_authorizes_only_stop_and_exact_native_copy_result();already_unpacked_or_delivered_attack_cannot_be_claimed_cancelled();
    std::cout<<"12 attack-lineage replay groups passed; native ABI-shaped fake hooks, no SDK or field authority\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
