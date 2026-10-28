// Windows transport memory only. No game process, hooks or SDK are accessed.
#include "near_channel.h"
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <atomic>
namespace rt=tacticore::runtime;namespace nc=rt::near_combat;namespace nw=nc::wire;namespace ch=rt::channel;
#define CHECK(x) do{if(!(x))throw std::runtime_error(std::string(__func__)+":"+std::to_string(__LINE__)+":"+#x);}while(0)
static rt::Id id(uint32_t n){return {n,2,3,4};}
static nw::NearCommand command(uint32_t n){
    nw::NearCommand c;c.intent.command=id(n);c.intent.task=id(10);c.intent.lease=id(11);c.intent.sequence=n;c.intent.target_key=id(12);
    c.original_return.command=id(n+1);c.original_return.task=c.intent.task;c.original_return.lease=c.intent.lease;
    c.original_return.sequence=n+1;c.original_return.operation=rt::Operation::ReturnHome;return c;
}
static void separate_version_preserves_original_v1_layout(){
    auto s=std::make_unique<nw::Shared>();CHECK(s->movement.magic_word==nw::magic&&s->movement.protocol==2&&s->movement.structure_size==sizeof(nw::Shared));
    CHECK(nw::magic!=ch::magic&&nw::bootstrap_message!=ch::bootstrap_message&&nw::pulse_message!=ch::pulse_message);
    CHECK(sizeof(ch::SharedChannel)==1624056&&offsetof(ch::SharedChannel,command)==280&&offsetof(ch::SharedChannel,receipt)==648);
    CHECK(offsetof(nw::Shared,movement)==0&&sizeof(nc::ContactView)==48&&s->bootstrap.schema==2);
}
static void paired_attack_and_return_have_one_publication_generation(){
    auto s=std::make_unique<nw::Shared>();nw::NearCommand observed;LONG g=0;
    s->near_command=command(3);s->near_command_generation=1;CHECK(!nw::command_snapshot(*s,0,observed,g));
    InterlockedExchange(&s->near_command_generation,2);CHECK(nw::command_snapshot(*s,0,observed,g)&&g==2&&nw::same(observed,command(3)));
    CHECK(!nw::command_snapshot(*s,g,observed,g));s->near_command_generation=-2;CHECK(!nw::command_snapshot(*s,0,observed,g));
}
static void concurrent_pair_read_never_combines_two_published_intents(){
    auto s=std::make_unique<nw::Shared>();s->near_command=command(1);s->near_command_generation=2;
    std::atomic<bool> finished{false};std::thread writer([&]{for(uint32_t n=2;n<3000;n++){
        InterlockedExchange(&s->near_command_generation,static_cast<LONG>(2*n-1));MemoryBarrier();s->near_command=command(n);
        MemoryBarrier();InterlockedExchange(&s->near_command_generation,static_cast<LONG>(2*n));}finished=true;});
    bool coherent=true;uint32_t reads=0;LONG last=0;
    do{nw::NearCommand value;LONG g=0;if(nw::command_snapshot(*s,last,value,g)){
        coherent=coherent&&value.original_return.sequence==value.intent.sequence+1&&value.intent.command[0]==value.intent.sequence
            &&value.original_return.command[0]==value.original_return.sequence&&value.original_return.task==value.intent.task;
        last=g;reads++;}}while(!finished);
    writer.join();nw::NearCommand final;LONG g=0;if(nw::command_snapshot(*s,last,final,g)){coherent=coherent&&nw::same(final,command(2999));reads++;}
    CHECK(coherent&&reads>0);
}
static void result_and_withdrawal_copy_values_and_fixed_reason(){
    auto s=std::make_unique<nw::Shared>();nc::Result result;result.command=id(3);result.sequence=3;result.held=true;
    std::string reason(150,'x');result.reason=reason.c_str();nw::result_publish(*s,result);
    CHECK(s->near_receipt_generation==2&&s->near_receipt.sequence==3&&s->near_receipt.reason[95]==0&&s->near_receipt.held==1);
    nc::Observation observation;observation.actor.frame=77;nc::Withdrawal withdrawal;withdrawal.frame=80;withdrawal.complete=true;
    nw::combat_publish(*s,result,"withdrawal",observation,&withdrawal);auto& event=s->combat[0];
    CHECK(event.ticket==1&&event.withdrawal_present==1&&event.withdrawal.frame==80&&event.observation.actor.frame==77);
    CHECK(event.result.reason[95]==0&&std::string(event.event_type)=="withdrawal");
}
static void overflow_and_both_held_states_prevent_false_release(){
    auto s=std::make_unique<nw::Shared>();nc::Result r;nc::Observation o;
    for(unsigned n=0;n<nw::combat_capacity+3;n++)nw::combat_publish(*s,r,"read",o,nullptr);
    CHECK(s->combat_written==515&&s->combat_overwritten==3&&s->combat[2].ticket==515&&s->combat[2].withdrawal_present==0);
    s->movement.state=static_cast<LONG>(ch::State::Released);s->movement.hooks_restored=32767;CHECK(nw::terminal(*s));
    s->near_receipt.held=1;CHECK(!nw::terminal(*s));s->near_receipt.held=0;s->movement.receipt.held=1;CHECK(!nw::terminal(*s));
    s->movement.receipt.held=0;s->movement.hooks_restored=8191;CHECK(!nw::terminal(*s));s->movement.hooks_restored=32767;
    s->movement.active_callbacks=1;CHECK(!nw::terminal(*s));s->movement.active_callbacks=0;s->movement.state=static_cast<LONG>(ch::State::Uncertain);CHECK(!nw::terminal(*s));
    s->movement.state=static_cast<LONG>(ch::State::Refused);s->movement.hooks_restored=1;CHECK(nw::terminal(*s));
}
static void bootstrap_and_saved_target_key_changes_are_not_equal(){
    nc::NativeBootstrap a,b;CHECK(nw::same(a,b));b.visibility_path[20]=L'x';CHECK(!nw::same(a,b));b=a;
    b.original.binding.process_start=1;CHECK(!nw::same(a,b));b=a;b.schema=1;CHECK(!nw::same(a,b));
    auto c=command(3),d=c;d.intent.target_key=id(99);CHECK(!nw::same(c,d));d=c;d.original_return.sequence++;CHECK(!nw::same(c,d));
}
int main(){try{
    separate_version_preserves_original_v1_layout();paired_attack_and_return_have_one_publication_generation();concurrent_pair_read_never_combines_two_published_intents();
    result_and_withdrawal_copy_values_and_fixed_reason();overflow_and_both_held_states_prevent_false_release();bootstrap_and_saved_target_key_changes_are_not_equal();
    std::cout<<"6 near channel groups passed; local Windows transport only, no game SDK or field capability\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
