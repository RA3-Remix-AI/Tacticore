#include "shared_channel.h"
#include <cassert>
#include <cstdio>
#include <memory>

using namespace tacticore::runtime;
namespace channel=tacticore::runtime::channel;
int main(){
    auto shared=std::make_unique<channel::SharedChannel>();
    channel::Bootstrap original{},experimental{};experimental.experimental_flags=1;
    assert(!(original==experimental)&&original.experimental_flags==0);
    Command result{};LONG observed=0;
    shared->command.sequence=123;shared->command.command={1,2,3,4};
    shared->command_generation=1;
    assert(!channel::command_snapshot(*shared,0,result,observed));
    shared->command_generation=2;
    assert(channel::command_snapshot(*shared,0,result,observed)&&observed==2&&result.sequence==123);
    assert(!channel::command_snapshot(*shared,2,result,observed));
    Receipt receipt{};receipt.reason="physical_home_observed";receipt.physical_home=true;
    receipt.control_released=false;receipt.sequence=44;
    channel::receipt_publish(*shared,receipt);
    assert(shared->receipt_generation==2&&shared->receipt.physical_home==1&&shared->receipt.control_released==0);
    assert(!std::strcmp(shared->receipt.reason,"physical_home_observed"));
    for(uint32_t i=0;i<channel::event_capacity+5;i++){receipt.sequence=i+1;channel::event_publish(*shared,Event{receipt,"observation"},3);}
    assert(shared->events_written==static_cast<LONG>(channel::event_capacity+5)&&shared->events_overwritten==5);
    assert(shared->events[4].ticket==static_cast<LONG>(channel::event_capacity+5));
    assert(shared->events[4].receipt.sequence==channel::event_capacity+5);
    HookTrace trace{};trace.kind=7;trace.caller=0x838877;trace.word_count=24;trace.words[23]=0xfeed;
    assert(channel::trace_capacity>=2*Limits{}.max_lease_frames+256);
    for(uint32_t i=0;i<channel::trace_capacity+3;i++)channel::trace_publish(*shared,trace);
    assert(shared->traces_written==static_cast<LONG>(channel::trace_capacity+3)&&shared->traces_overwritten==3);
    assert(shared->traces[2].ticket==static_cast<LONG>(channel::trace_capacity+3)&&shared->traces[2].trace.words[23]==0xfeed);
    std::printf("{\"channel_tests\":7,\"shared_size\":%u,\"command_offset\":%u,\"receipt_offset\":%u,\"events_offset\":%u,\"wire_receipt\":%u}\n",
        static_cast<unsigned>(sizeof(channel::SharedChannel)),static_cast<unsigned>(offsetof(channel::SharedChannel,command)),
        static_cast<unsigned>(offsetof(channel::SharedChannel,receipt)),static_cast<unsigned>(offsetof(channel::SharedChannel,events)),static_cast<unsigned>(sizeof(channel::WireReceipt)));
}
