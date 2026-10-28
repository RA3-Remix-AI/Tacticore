#include "controller.h"
#include "incarnations.h"
#include "memory_io.h"
#include "lineage.h"
#include "membership.h"
#include "endpoints.h"
#include "geometry.h"
#include "native_yield.h"
#include "land_geometry.h"
#include <cstring>
#include <iostream>
#include <map>
#include <stdexcept>
#include <vector>
#include <algorithm>
#include <limits>
#include <type_traits>
using namespace tacticore::runtime;
#define CHECK(x) do{if(!(x))throw std::runtime_error(std::string(__func__)+":"+std::to_string(__LINE__)+":"+#x);}while(0)
static Id id(uint32_t x){return Id{x,2,3,4};}
static Binding binding(){Binding b;b.session=id(1);b.commander=id(2);b.host=id(3);b.binding_hash[0]=4;b.player=7;b.pid=10;b.thread=20;b.process_start=123456;return b;}
static Actor actor(){return Actor{55,0x5000,0x7000,0x6000,0x2000,0x19ab11af,90,1};}
static std::vector<HookTrace> home_fixture;
struct Fake:IO {
    Sample s{};bool surface=true,apply=true,recovery=false,home_clear=true,lender=true;Delivery delivery=Delivery::Sent;NativePreemption preemption=NativePreemption::None;
    std::vector<Action> calls;std::vector<Event> events;
    bool fault=false;Delivery fault_delivery=Delivery::Sent;std::vector<Command> faults;
    Fake(){s.binding=binding();s.actor=actor();s.frame=100;s.monotonic_ms=1000;s.current_thread=20;s.team=s.default_team=0x3000;s.script_team=0x4000;s.identity=s.actor_birth_verified=s.live_list_member=s.grounded=s.settled=s.interference_guard_ready=true;s.paused=false;}
    Sample sample()override{return s;}
    bool ground_target(Point)override{return surface;}
    bool remember_home(const Sample&)override{return surface;}
    bool independent_borrow_permitted(const Sample&)override{return lender;}
    bool diagnostic_fault_enabled()const override{return fault;}
    Delivery diagnostic_foreign_move(const Command& c)override{faults.push_back(c);if(fault_delivery==Delivery::Sent){s.xyz=c.target;s.foreign_epoch++;s.settled=false;s.normal_move_owned=false;}return fault_delivery;}
    bool return_home_clear(const Sample&,Point)override{return home_clear;}
    Delivery issue(Action a,Point p,uint32_t stance)override{
        calls.push_back(a);if(apply&&delivery==Delivery::Sent)switch(a){
        case Action::Borrow:s.team=s.script_team;break;
        case Action::TransferBack:s.team=s.default_team;break;
        case Action::HoldStance:case Action::RestoreStance:s.stance=stance;break;
        case Action::Move:s.xyz=p;s.normal_move_owned=true;break;
        case Action::Stop:s.settled=true;break;}
        return delivery;
    }
    void event(const Event& e)override{events.push_back(e);}
    bool independent_recovery_permitted(const Sample&)override{return recovery;}
    NativePreemption take_native_preemption(const Sample&)override{auto result=preemption;if(result!=NativePreemption::WaitingYield)preemption=NativePreemption::None;return result;}
    void clear_native_preemption()override{preemption=NativePreemption::None;}
    Receipt tick(Controller& c,bool new_frame=true){if(new_frame)s.frame++;s.monotonic_ms+=10;return c.tick();}
};
static Command command(uint32_t n,Operation op=Operation::Reserve){Command c;c.command=id(n+100);c.task=id(10);c.lease=id(11);c.actor=actor();c.sequence=n;c.operation=op;c.target=Point{100,0,0};c.expires_frame=900;c.lease_deadline_frame=800;c.expires_monotonic_ms=90000;c.hold_frames=3;return c;}
static void ready(Fake& io,Controller& c){CHECK(c.submit(command(1)).accepted);for(int i=0;i<20&&c.status().phase!=Phase::Ready;i++){io.tick(c);}CHECK(c.status().phase==Phase::Ready);}
static void happy_and_repeat(){
    Fake io;Controller c(binding(),io);ready(io,c);CHECK(c.submit(command(2,Operation::MoveHold)).accepted);
    for(int i=0;i<80&&c.status().phase!=Phase::Released;i++)io.tick(c);
    auto r=c.status();CHECK(r.phase==Phase::Released&&r.physical_home&&r.control_released&&r.stance_restored&&!r.held);
    CHECK(r.sdk_calls[0]==1&&r.sdk_calls[1]==1&&r.sdk_calls[2]==4&&r.sdk_calls[3]==2&&r.sdk_calls[4]==1&&r.sdk_calls[5]==1);
    CHECK(!io.events.empty());for(auto& e:io.events)CHECK(e.receipt.frame>=100&&e.receipt.monotonic_ms>=1000);
    auto next=command(3);next.task=id(12);next.lease=id(13);CHECK(c.submit(next).accepted);
    for(int i=0;i<20&&c.status().phase!=Phase::Ready;i++){io.tick(c);}CHECK(c.status().phase==Phase::Ready);
    auto old=command(4,Operation::MoveHold);CHECK(!c.submit(old).accepted);
}
static void query_acknowledges_itself_without_changing_task_action(){
    Fake io;Controller c(binding(),io);ready(io,c);
    auto before=c.status();auto calls=io.calls.size();auto query=command(2,Operation::Query);
    auto reply=c.submit(query);CHECK(reply.accepted&&reply.command==query.command&&reply.sequence==2);
    CHECK(reply.task==query.task&&reply.lease==query.lease&&reply.phase==Phase::Ready);
    CHECK(c.status().command==before.command&&c.status().sequence==before.sequence);
    CHECK(c.last_sequence()==2&&io.calls.size()==calls);
    CHECK(!c.submit(query).accepted&&io.calls.size()==calls);
    CHECK(c.submit(command(3,Operation::MoveHold)).accepted);
}
static void duplicated_unknown_never_replays(){
    Fake io;Controller c(binding(),io);auto cmd=command(1);CHECK(c.submit(cmd).accepted);auto count=io.calls.size();CHECK(!c.submit(cmd).accepted);CHECK(io.calls.size()==count);
    cmd.target.x++;CHECK(std::string(c.submit(cmd).reason)=="command_identity_conflict");
    io.delivery=Delivery::Unknown;io.tick(c);CHECK(c.status().phase==Phase::Uncertain);count=io.calls.size();
    for(int i=0;i<100;i++){io.tick(c);}CHECK(io.calls.size()==count);
    CHECK(!c.submit(command(2,Operation::EmergencyRelease)).accepted);
}
static void admission_and_clocks(){
    {Fake io;Controller c(binding(),io);io.s.binding.player=3;CHECK(!c.submit(command(1)).accepted);CHECK(io.calls.empty());}
    {Fake io;Controller c(binding(),io);io.s.actor.generation++;CHECK(!c.submit(command(1)).accepted);}
    {Fake io;Controller c(binding(),io);io.s.actor_birth_verified=false;CHECK(!c.submit(command(1)).accepted);}
    {Fake io;Controller c(binding(),io);io.s.current_thread++;CHECK(!c.submit(command(1)).accepted);}
    {Fake io;Controller c(binding(),io);io.s.paused=true;CHECK(!c.submit(command(1)).accepted);}
    {Fake io;Controller c(binding(),io);auto expired=command(1);expired.expires_monotonic_ms=1000;CHECK(!c.submit(expired).accepted);}
    {Fake io;Controller c(binding(),io);ready(io,c);io.s.monotonic_ms=0;io.tick(c);CHECK(c.status().phase==Phase::Uncertain);}
    {Fake io;Controller c(binding(),io);ready(io,c);io.s.frame=0;io.tick(c);CHECK(c.status().phase==Phase::Uncertain);}
}
static void bounded_target_and_ready(){
    Fake io;Controller c(binding(),io);CHECK(!c.submit(command(1,Operation::MoveHold)).accepted);ready(io,c);
    auto bad=command(2,Operation::MoveHold);bad.target.x=500;CHECK(!c.submit(bad).accepted);bad.target.x=NAN;CHECK(!c.submit(bad).accepted);
    bad=command(2,Operation::MoveHold);io.surface=false;CHECK(!c.submit(bad).accepted);io.surface=true;
    bad.lease_deadline_frame++;CHECK(!c.submit(bad).accepted);CHECK(io.calls.size()==3);
}
static void pause_watchdog_and_same_frame(){
    Fake io;Controller c(binding(),io);CHECK(c.submit(command(1)).accepted);
    for(int i=0;i<6;i++){io.tick(c);}CHECK(c.status().phase==Phase::Braking);
    for(int i=0;i<20;i++){io.tick(c,false);}CHECK(c.status().phase==Phase::Braking);
    for(int i=0;i<3;i++){io.tick(c);}CHECK(c.status().phase==Phase::Ready);
    auto count=io.calls.size();io.s.paused=true;for(int i=0;i<20;i++)io.tick(c);CHECK(io.calls.size()==count);
    io.s.monotonic_ms+=11000;io.tick(c);CHECK(c.status().phase==Phase::Uncertain&&io.calls.size()==count);
}
static void interference_and_delivery_timeout(){
    {Fake io;Controller c(binding(),io);ready(io,c);auto count=io.calls.size();io.s.foreign_epoch++;io.tick(c);CHECK(c.status().phase==Phase::Uncertain&&io.calls.size()==count);CHECK(!c.status().control_released);}
    {Fake io;Controller c(binding(),io);io.apply=false;CHECK(c.submit(command(1)).accepted);for(int i=0;i<70;i++)io.tick(c);CHECK(c.status().phase==Phase::Uncertain);CHECK(io.calls.size()==1);}
    {Fake io;Controller c(binding(),io);ready(io,c);CHECK(c.submit(command(2,Operation::MoveHold)).accepted);io.apply=false;for(int i=0;i<70;i++)io.tick(c);CHECK(c.status().phase==Phase::Uncertain);CHECK(c.status().sdk_calls[3]==1);}
}
static void emergency_release_is_not_home(){
    Fake io;Controller c(binding(),io);ready(io,c);io.s.xyz.x=100;
    CHECK(c.submit(command(2,Operation::EmergencyRelease)).accepted);
    for(int i=0;i<40&&c.status().phase!=Phase::Released;i++)io.tick(c);
    CHECK(c.status().control_released&&c.status().stance_restored&&!c.status().physical_home);CHECK(c.status().sdk_calls[3]==0);
}
static void explicit_recovery_and_private_stop_do_not_mint_sequences(){
    Fake io;Controller c(binding(),io);ready(io,c);io.s.foreign_epoch++;io.tick(c);CHECK(c.status().phase==Phase::Uncertain);
    auto recovery=command(2,Operation::ReconcileRelease);CHECK(!c.submit(recovery).accepted);CHECK(c.status().held);
    io.recovery=true;CHECK(c.submit(recovery).accepted);io.s.xyz.x=100;
    for(int i=0;i<40&&c.status().phase!=Phase::Released;i++){io.tick(c);}
    CHECK(c.status().control_released&&!c.status().physical_home&&c.status().sdk_calls[3]==0);
    Fake stopped;Controller c2(binding(),stopped);ready(stopped,c2);auto seq=c2.status().sequence;
    c2.request_stop();c2.request_stop();for(int i=0;i<60&&c2.status().phase!=Phase::Released;i++){stopped.tick(c2);}
    CHECK(c2.status().phase==Phase::Released&&c2.status().sequence==seq);
    CHECK(std::count_if(stopped.events.begin(),stopped.events.end(),[](const Event& event){return std::string(event.kind)=="native_safety_stop";})==1);
}
static std::array<uint32_t,23> move_words(Point goal){std::array<uint32_t,23> words{};words[1]=1;std::memcpy(words.data()+2,&goal,12);words[22]=1;return words;}
static void actual_normal_move_lineage(){
    Point goal{100,0,0};auto words=move_words(goal);float limit=std::numeric_limits<float>::max();
    MoveLineage direct(20,0x5000,0x6000);CHECK(direct.arm(goal,20,100));CHECK(direct.facade_enter(0x6024,goal,1,20,100,true));auto prior=direct.context();CHECK(direct.dispatch_enter(0x6024,0x10000,words.data(),0,20,100,true));
    CHECK(direct.private_move(0x6000,0x10008,goal,0,limit,1,0x6d3b7d,20,100,true));direct.dispatch_exit(prior);direct.facade_exit();CHECK(direct.delivered()&&direct.epoch()==0);
    CHECK(!direct.private_move(0x6000,0x10008,goal,0,limit,1,0x6d3b7d,20,100,true));CHECK(direct.epoch()==1);
    MoveLineage deferred(20,0x5000,0x6000);CHECK(deferred.arm(goal,20,100));CHECK(deferred.facade_enter(0x6024,goal,1,20,100,true));prior=deferred.context();CHECK(deferred.dispatch_enter(0x6024,0x10000,words.data(),0,20,100,true));
    std::array<uint32_t,24> before{},stored{};before[0]=0xffffffffu;std::memcpy(stored.data(),words.data(),24);stored[23]=1;
    CHECK(deferred.copy_before(0x6310,0x10000,before.data(),words.data(),0x787d42,20,100,true));CHECK(deferred.copy_after(before.data(),stored.data(),words.data()));deferred.dispatch_exit(prior);deferred.facade_exit();CHECK(deferred.pending());
    CHECK(deferred.unpack_before(0x6310,0x5000,0x20000,stored.data(),0x7da0b3,20,101,false));CHECK(deferred.unpack_after(true,words.data()));prior=deferred.context();CHECK(deferred.dispatch_enter(0x6024,0x20000,words.data(),0x7da0d9,20,101,false));
    CHECK(deferred.private_move(0x6000,0x20008,goal,0,limit,1,0x6d3b7d,20,101,false));deferred.dispatch_exit(prior);CHECK(deferred.delivered()&&!deferred.pending()&&deferred.epoch()==0);
    for(int change=0;change<8;change++){
        MoveLineage invalid(20,0x5000,0x6000);CHECK(invalid.arm(goal,20,100));CHECK(invalid.facade_enter(0x6024,goal,1,20,100,true));CHECK(invalid.dispatch_enter(0x6024,0x10000,words.data(),0,20,100,true));
        CHECK(!invalid.private_move(change==0?0x7000:0x6000,change==1?0x1000c:0x10008,change==2?Point{99,0,0}:goal,change==3?1:0,change==4?1:limit,change==5?2:1,change==6?0:0x6d3b7d,change==7?21:20,100,true));CHECK(invalid.epoch()>0);
    }
    MoveLineage unknown(20,0x5000,0x6000);CHECK(unknown.arm(goal,20,100));words[0]=7;CHECK(!unknown.dispatch_enter(0x6024,0x10000,words.data(),0,20,100,false));CHECK(unknown.epoch()==1);
}
static void paid_registry_no_reuse(){
    Fake io;auto a=io.s;a.actor.generation=0;a.actor.born_frame=0;auto b=a;
    PaidBirth paid{id(1),id(2),1,55,0x5000,0x2000,0x19ab11af,100,99,85,85,true,true,true};
    Incarnations registry;auto observed=registry.register_paid_birth(paid,a,b);CHECK(observed.generation==1&&observed.born_frame==100);
    auto s=a;s.actor=observed;CHECK(registry.current(observed,s));s.live_list_member=false;CHECK(!registry.current(observed,s));s.live_list_member=true;CHECK(!registry.current(observed,s));
    try{registry.register_paid_birth(paid,a,b);CHECK(false);}catch(const std::invalid_argument&){}
    paid.object_id++;a.actor.object_id++;b.actor.object_id++;try{registry.register_paid_birth(paid,a,b);CHECK(false);}catch(const std::invalid_argument&){}
    paid.thing+=0x1000;a.actor.thing=paid.thing;b.actor.thing=paid.thing;b.frame++;try{registry.register_paid_birth(paid,a,b);CHECK(false);}catch(const std::invalid_argument&){}
}
static void paid_birth_refusals_preserve_reason_and_generation(){
    Fake io;auto a=io.s;a.actor.generation=0;a.actor.born_frame=0;
    PaidBirth paid{id(1),id(2),1,55,0x5000,0x2000,0x19ab11af,100,99,85,85,true,true,true};
    for(int change=0;change<9;change++){
        Incarnations registry;auto p=paid;auto first=a,second=a;
        const char* expected=nullptr;
        switch(change){
        case 0:p.paid=84;expected="paid_birth_receipt_unverified";break;
        case 1:second.frame++;expected="paid_birth_frame_unstable";break;
        case 2:second.binding.player++;expected="paid_birth_binding_unstable";break;
        case 3:second.identity=false;expected="paid_birth_identity_unverified";break;
        case 4:second.live_list_member=false;expected="paid_birth_live_list_unverified";break;
        case 5:second.grounded=false;expected="paid_birth_grounded_unverified";break;
        case 6:second.actor.update++;expected="paid_birth_actor_unstable";break;
        case 7:second.xyz.x++;expected="paid_birth_position_unstable";break;
        case 8:p.object_id++;expected="paid_birth_actor_tuple_mismatch";break;
        }
        try{registry.register_paid_birth(p,first,second);CHECK(false);}
        catch(const BirthAdmissionError& error){CHECK(std::string(error.what())==expected);}
        // A refused observation consumes neither an incarnation nor an ID.
        auto accepted=registry.register_paid_birth(paid,a,a);
        CHECK(accepted.generation==1&&accepted.born_frame==100);
    }
}
static void native_lender_denial_never_claims_or_dispatches(){
    Fake io;io.lender=false;Controller c(binding(),io);
    auto denied=c.submit(command(1));
    CHECK(!denied.accepted&&std::string(denied.reason)=="native_lender_quiescence_unverified");
    CHECK(!c.status().held&&c.last_sequence()==0&&io.calls.empty());
    for(int i=0;i<10;i++)io.tick(c);
    CHECK(!c.status().held&&io.calls.empty());
}
static void borrow_not_sent_closes_only_the_untransferred_claim(){
    Fake io;io.delivery=Delivery::NotSent;Controller c(binding(),io);
    CHECK(c.submit(command(1)).accepted);io.tick(c);
    CHECK(c.status().phase==Phase::Released&&!c.status().held&&c.status().control_released);
    CHECK((!c.status().physical_home&&c.status().sdk_calls==std::array<uint32_t,6>{}));
    CHECK(std::string(c.status().reason)=="borrow_not_sent_no_control_transfer");
    CHECK(io.calls.size()==1&&io.calls[0]==Action::Borrow);
    for(int i=0;i<10;i++)io.tick(c);
    CHECK(io.calls.size()==1&&!c.submit(command(1)).accepted);
    Fake unknown;unknown.delivery=Delivery::Unknown;Controller uncertain(binding(),unknown);
    CHECK(uncertain.submit(command(1)).accepted);unknown.tick(uncertain);
    CHECK(uncertain.status().phase==Phase::Uncertain&&uncertain.status().held&&uncertain.status().sdk_calls[0]==1);
    Fake changed;changed.delivery=Delivery::NotSent;Controller foreign(binding(),changed);
    CHECK(foreign.submit(command(1)).accepted);changed.s.team=changed.s.script_team;changed.tick(foreign);
    CHECK(foreign.status().phase==Phase::Uncertain&&foreign.status().held&&!foreign.status().control_released);
}
struct Bytes:Memory {
    Binding b=binding();uint32_t tid=20;uint64_t ms=1000;std::map<uint32_t,unsigned char> data;
    void zero(uint32_t p,uint32_t n){for(uint32_t i=0;i<n;i++)data[p+i]=0;}
    template<class T>void set(uint32_t p,T value){for(size_t i=0;i<sizeof(T);i++)data[p+static_cast<uint32_t>(i)]=reinterpret_cast<unsigned char*>(&value)[i];}
    bool read(uint32_t p,void* target,uint32_t n)override{for(uint32_t i=0;i<n;i++){auto f=data.find(p+i);if(f==data.end())return false;static_cast<unsigned char*>(target)[i]=f->second;}return true;}
    Binding current_binding()override{return b;}uint32_t thread()override{return tid;}uint64_t monotonic_ms()override{return ms;}
};
struct Calls:NativeCalls {uint32_t count=0;Delivery call(Action,const Actor&,const NativeBinding&,Point,uint32_t)override{count++;return Delivery::Sent;}};
struct Witness:CommandWitness {bool ready=true,quiet=true,stop_owned=false;bool installed_and_originals_verified()const override{return ready;}uint32_t foreign_epoch()const override{return 0;}bool normal_move_owned()const override{return false;}bool normal_stop_owned()const override{return stop_owned;}void begin(Action,Point,uint32_t)override{}void end(Action)override{}bool independent_quiescence_verified()const override{return quiet;}};
struct Surfaces:SurfacePoints {bool contains(const Binding&,Point p)const override{return p==Point{100,0,0};}};
static void actual_native_yield_reader(Bytes m,NativeBinding native){
    using namespace yield_words;
    for(auto p:{0x11000u,0x12000u,0x13000u,0x14000u,0x15000u})m.zero(p,0x500);
    m.set(0x5414,0x4000u);m.set(0xe038,2u);m.set(0x6310,0xffffffffu);m.set(0x61e8,798u);
    m.set(0x507c,0x11000u);m.set(0x11000,0xc4db60u);m.set(0x11004,0x12000u);m.set(0x12008,0x2c358c61u);
    m.set(0x110dc,798u);m.set(0x11418,0x2000u);m.set(0x11414,0x3000u);m.set(0x11374,0x13000u);m.set(0x1133c,0x15000u);
    m.set(0x15004,100.f);m.set(0x11048,4u);m.set(0x11038,60.f);
    m.set(0x13000,0xc48670u);m.set(0x13024,0xc48528u);m.set(0x13008,0x11000u);m.set(0x1303c,0x14000u);
    m.set(0x14024,0x11000u);m.set(0x14004,0x14100u);m.set(0x14100,0xc548c0u);m.set(0x14104,10u);m.set(0x14118,0x14000u);
    YieldReader reader(binding(),native,actor(),m);auto before=reader.capture(0x11000);
    CHECK(before.verified&&before.actor[ALive]==3&&before.neighbor[NId]==798);
    CHECK(before.neighbor_physical[0]==1&&before.neighbor_physical[1]==0x11000&&before.neighbor_physical[6]==4&&before.neighbor_physical[14]==1&&before.neighbor_physical[15]==1);
    auto original=m.data;
    for(auto change:std::vector<std::pair<uint32_t,uint32_t>>{{0x11418,0x9999},{0x11414,0x4000},{0x12008,1},{0x110dc,55},{0x13008,0},{0x14118,0},{0x1107c,0x11000},{0x507c,0},{0x5414,0x3000},{0x9018,78}}){
        m.set(change.first,change.second);CHECK(!reader.capture(0x11000).verified);m.data=original;
    }
    m.data.erase(0x15004);CHECK(!reader.capture(0x11000).verified);m.data=original;
    m.set(0x11048,1u);auto uncached=reader.capture(0x11000);
    CHECK(uncached.verified&&uncached.neighbor[NGrounded]==0&&uncached.neighbor_physical[6]==1&&uncached.neighbor_physical[15]==1&&uncached.neighbor_physical[16]==1);
    // Invalid neighbor height cache is not a ground destination or a controlled
    // actor admission. The leased actor's own height must still be verified.
    m.set(0x5048,1u);CHECK(!reader.capture(0x11000).verified);m.data=original;
    for(auto change:std::vector<std::pair<uint32_t,uint32_t>>{{0x11238,1},{0x11080,1},{0x11084,0x20000000},{0x11094,2},{0x11098,0x80000}}){
        m.set(change.first,change.second);CHECK(!reader.capture(0x11000).verified);m.data=original;
    }
    m.set(0x15004,0.f);CHECK(!reader.capture(0x11000).verified);m.data=original;
    m.tid++;CHECK(!reader.capture(0x11000).verified);m.tid--;
    m.b.process_start++;CHECK(!reader.capture(0x11000).verified);m.b.process_start--;
    CHECK(!reader.capture(0x5000).verified&&!reader.capture(0x11001).verified);
    YieldContext c;c.active=c.enabled=c.own_stop_idle=true;c.frame=100;c.thread=20;c.self=0x6024;c.outer_caller=0x694a00;
    c.source=2;c.neighbor=0x11000;c.goal={60,0,0};c.before=before;
    std::array<uint32_t,23> words{};words[0]=48;words[1]=2;words[5]=c.neighbor;std::memcpy(words.data()+2,&c.goal,12);
    // Captured facade padding is uninitialized; semantic fields remain strict.
    words[10]=0x123456;words[14]=0xabcdef;words[19]=0xc1886c;words[22]=0x694900;
    auto valid=[&](const YieldContext& value){return native_yield_admissible(value,words.data(),0x6024,0x6939aa,20,100);};
    CHECK(valid(c));auto saved=c;
    // Policy promotion uses the actual typed Flak snapshot, not a UI boolean.
    CHECK(ordinary_native_yield_source(c)&&native_yield_policy_enabled(c,false,false));
    CHECK(!native_yield_policy_enabled(c,false,true)&&!native_yield_policy_enabled(c,true,true));
    auto ordinary=c;ordinary.enabled=native_yield_policy_enabled(ordinary,false,false);CHECK(valid(ordinary));
    for(auto hash:{0x33026fa1u,0x19ab11afu,0x12345678u}){
        auto other=c;other.before.neighbor[NHash]=hash;
        CHECK(!ordinary_native_yield_source(other)&&!native_yield_policy_enabled(other,false,false));
        CHECK(native_yield_policy_enabled(other,true,false));
    }
    for(auto caller:{0x694a50u,0x6981c4u,0x71c433u,0x755dadu,0x77c36eu,0x54b045u}){
        auto other=c;other.outer_caller=caller;CHECK(!native_yield_policy_enabled(other,false,false));
    }
    {auto other=c;other.source=1;CHECK(!native_yield_policy_enabled(other,false,false));}
    {auto other=c;other.before.verified=false;CHECK(!native_yield_policy_enabled(other,false,false)&&!native_yield_policy_enabled(other,true,false));}
    {auto other=c;other.before.actor[AState]=16;other.enabled=native_yield_policy_enabled(other,false,false);CHECK(other.enabled&&!valid(other));}
    c.before=uncached;CHECK(valid(c));c=saved;
    c.enabled=false;CHECK(!valid(c));c=saved;c.own_scope=true;CHECK(!valid(c));c=saved;
    c.own_stop_idle=false;CHECK(!valid(c));c=saved;c.outer_caller=0x54b045;CHECK(!valid(c));c=saved;
    c.dispatched=true;CHECK(!valid(c));c=saved;c.before.verified=false;CHECK(!valid(c));c=saved;
    c.goal.x++;CHECK(!valid(c));c=saved;c.before.actor[ASlot]=48;CHECK(!valid(c));c=saved;
    CHECK(!native_yield_admissible(c,words.data(),0x6025,0x6939aa,20,100));
    CHECK(!native_yield_admissible(c,words.data(),0x6024,0x6939ab,20,100));
    CHECK(!native_yield_admissible(c,words.data(),0x6024,0x6939aa,21,100));
    CHECK(!native_yield_admissible(c,words.data(),0x6024,0x6939aa,20,101));
    for(unsigned index:{0u,1u,5u,6u,11u,20u,22u}){auto old=words[index];words[index]++;CHECK(!valid(c));words[index]=old;}
    c.dispatched=true;auto after=reader.capture(c.neighbor);CHECK(native_yield_after(c,after,0));
    CHECK(!native_yield_after(c,after,1));after.yield_neighbor_id++;CHECK(!native_yield_after(c,after,0));after=before;
    c.accepted=true;PendingNativeYield pending;CHECK(pending.arm(c,1000)&&!pending.arm(c,1000));
    Fake f;auto s=f.s;s.team=s.script_team;s.stance=2;s.state_id=94;s.state_vtable=0xc551a0;s.command_source=1;
    CHECK(pending.inspect(s,after,0)==NativePreemption::WaitingYield&&pending.pending());
    s.frame=101;s.monotonic_ms=1030;after.frame=101;s.state_id=26;s.state_vtable=0xc553d0;s.path=0x66000;
    after.actor[AState]=26;after.actor[AVtable]=0xc553d0;after.actor[APath]=s.path;
    CHECK(pending.inspect(s,after,0)==NativePreemption::VerifiedYield&&!pending.pending());
    CHECK(pending.inspect(s,after,0)==NativePreemption::None);
    for(unsigned mode=0;mode<6;mode++){
        CHECK(pending.arm(c,1000));auto sample=s;auto fresh=after;
        if(mode==0)sample.foreign_epoch++;
        if(mode==1)sample.monotonic_ms=1251;
        if(mode==2)sample.frame=104;
        if(mode==3)fresh.neighbor[NId]++;
        if(mode==4)fresh.verified=false;
        if(mode==5)sample.state_vtable=0xc551a0;
        CHECK(pending.inspect(sample,fresh,0)==NativePreemption::UnverifiedYield&&!pending.pending());
    }
}
static void actual_readonly_ground_geometry(Bytes m,NativeBinding native){
    static_assert(!std::is_base_of<IO,GroundGeometry>::value,"Geometry must not become an actuator");
    auto add_foot=[&](uint32_t t,uint32_t tpl,uint32_t u,uint32_t body,uint32_t sm,uint32_t ident,uint32_t hash,float x){
        m.zero(t,0x500);m.zero(tpl,0x20);m.zero(u,0x500);m.zero(body,0x20);m.zero(sm,0x200);
        m.set(t,0xc4db60u);m.set(t+4,tpl);m.set(t+0xdc,ident);m.set(t+0x418,0x2000u);m.set(t+0x414,0x3000u);
        m.set(t+0x374,u);m.set(t+0x33c,body);m.set(t+0x38,x);m.set(t+0x48,4u);m.set(tpl+8,hash);m.set(body+4,100.f);
        m.set(u,0xc48670u);m.set(u+0x24,0xc48528u);m.set(u+8,t);m.set(u+0x3c,sm);
        m.set(sm+4,sm+0x100);m.set(sm+0x24,t);m.set(sm+0x100,0xc548c0u);m.set(sm+0x104,10u);m.set(sm+0x118,sm);
    };
    add_foot(0x11000,0x12000,0x13000,0x14000,0x15000,798,0x2c358c61,60);
    add_foot(0x16000,0x17000,0x18000,0x19000,0x1a000,803,0x33026fa1,100);
    m.set(0x507c,0x11000u);m.set(0x1107c,0x16000u);
    GroundGeometry geometry(binding(),native,m);auto frame=geometry.sample();
    CHECK(frame.verified&&frame.foot.size()==3&&frame.occupied.size()==3);
    for(auto s:frame.foot)CHECK(s.identity&&s.grounded&&s.live_list_member&&!s.actor_birth_verified&&!s.actor.generation);
    // Geometric observations cannot admit another class for actual control.
    Calls calls;Witness witness;Surfaces surfaces;Incarnations births;
    MemoryIO flak(binding(),native,frame.foot[1].actor,births,m,calls,witness,surfaces,{});
    CHECK(!flak.birth_observation().grounded&&flak.issue(Action::Borrow,{},0)==Delivery::NotSent&&calls.count==0);
    Endpoints endpoints(binding());
    auto observe=[&](){auto f=geometry.sample();endpoints.begin_frame(f.verified);for(auto p:f.occupied)endpoints.occupy(p);for(auto s:f.foot)endpoints.record(s,s);return f;};
    for(uint32_t i=0;i<3;i++){m.set(0x1050,100+i);observe();}
    CHECK(endpoints.available({0,0,0}).empty());
    m.set(0x11038,90.f);m.set(0x1050,103u);observe();
    CHECK(endpoints.contains(binding(),Point{60,0,0}));
    CHECK(!endpoints.contains(binding(),Point{100,0,0}));
    auto original=m.data;m.set(0x17008,0x99999999u);frame=observe();
    CHECK(frame.verified&&frame.foot.size()==2&&frame.occupied.size()==3);m.data=original;
    m.set(0x11418,0x9999u);frame=observe();CHECK(frame.verified&&frame.foot.size()==2&&frame.occupied.size()==2);m.data=original;
    m.set(0x1105c,20.f);frame=observe();CHECK(frame.verified&&!frame.foot[1].grounded);m.data=original;
    m.data.erase(0x16038);frame=observe();CHECK(!frame.verified&&endpoints.available({0,0,0}).empty()&&!endpoints.contains(binding(),Point{60,0,0}));m.data=original;
    m.set(0x1607c,0x16000u);CHECK(!geometry.sample().verified);m.data=original;
    m.tid++;CHECK(!geometry.sample().verified);m.tid--;
}
static void actual_memory_reader_admission(){
    Bytes m;for(auto p:{0x1000u,0x2000u,0x3000u,0x4000u,0x5000u,0x6000u,0x7000u,0x8000u,0x9000u,0xa000u,0xb000u,0xc000u,0xd000u,0xe000u})m.zero(p,0x500);
    m.set(0xcd8ce4,0x1000u);m.set(0x1000,0xbeb630u);m.set(0x1050,100u);m.set(0x10b4,0x5000u);
    m.set(0x2000,0xc5bce0u);m.set(0x2020,7u);m.set(0x2010,0xd000u);m.set(0x2090,0x8000u);m.set(0x208c,0xc000u);m.set(0xc010,0x4000u);m.set(0x20ac,0x3000u);
    m.set(0x3004,0xd100u);m.set(0xd108,0x2000u);m.set(0x4004,0xd200u);m.set(0xd208,0x2000u);
    m.set(0x8000,0xc60f60u);m.set(0x8008,0x2000u);m.set(0x88b0,0x9000u);m.set(0x9018,77u);
    m.set(0x5000,0xc4db60u);m.set(0x5004,0x7000u);m.set(0x50dc,55u);m.set(0x5418,0x2000u);m.set(0x5414,0x3000u);m.set(0x5374,0x6000u);m.set(0x533c,0xa000u);m.set(0xa004,100.f);m.set(0x7008,0x19ab11afu);m.set(0x5048,4u);
    m.set(0x6000,0xc48670u);m.set(0x6024,0xc48528u);m.set(0x6008,0x5000u);m.set(0x603c,0xb000u);m.set(0xb024,0x5000u);m.set(0xb004,0xb100u);m.set(0xb100,0xc551a0u);m.set(0xb104,94u);m.set(0xb118,0xb000u);m.set(0x6050,1u);
    m.set(0x5380,0xe000u);m.set(0xe000,0xc37f90u);m.set(0xe004,0xe100u);m.set(0xe008,0x5000u);m.set(0xe108,0xe200u);m.set(0xe200,0xe300u);m.set(0xe304,2u);m.set(0xe308,0xe400u);m.set(0xe400,0u);m.set(0xe408,2u);m.set(0xc37f98,0x71d3f0u);
    Calls calls;Witness witness;Surfaces surface;Incarnations registry;
    NativeBinding native{0x1000,0x2000,0x8000,0x9000,77,0xd000,0x3000,0x4000};
    actual_native_yield_reader(m,native);
    actual_readonly_ground_geometry(m,native);
    auto first_actor=actor();first_actor.generation=first_actor.born_frame=0;
    MemoryIO birth(binding(),native,first_actor,registry,m,calls,witness,surface,{});
    auto a=birth.birth_observation(),b=birth.birth_observation();CHECK(a.identity&&a.grounded&&a.live_list_member);
    PaidBirth paid{id(1),id(2),1,55,0x5000,0x2000,0x19ab11af,100,99,85,85,true,true,true};
    auto registered=registry.register_paid_birth(paid,a,b);
    std::vector<HookTrace> clearance;
    MemoryIO io(binding(),native,registered,registry,m,calls,witness,surface,{},[&](const HookTrace& h){clearance.push_back(h);});
    CHECK(!io.ground_target(Point{0,0,0}));
    auto private_home=io.sample();auto forged_home=private_home;forged_home.xyz.x=80;
    CHECK(!io.remember_home(forged_home)&&!io.ground_target(forged_home.xyz));
    CHECK(io.remember_home(private_home)&&io.ground_target(private_home.xyz));
    // The live Industrial list had790 Things; our actor was751st. World props
    // must not make a complete current own-census look like an empty prefix.
    {
        Bytes large=m;auto large_registry=registry;Witness large_witness;large_witness.stop_owned=true;
        large.set(0x10b4,0x20000u);large.set(0x5414,0x4000u);large.set(0xe038,2u);
        for(uint32_t i=0;i<750;i++){
            auto p=0x20000u+0x500u*i;large.set(p,0xc4db60u);large.set(p+0xdc,1000u+i);
            large.set(p+0x418,0u);large.set(p+0x7c,i==749?0x5000u:p+0x500u);large.zero(p+0x38,12);
        }
        std::vector<HookTrace> large_traces;
        MemoryIO large_io(binding(),native,registered,large_registry,large,calls,large_witness,surface,{},[&](const HookTrace& h){large_traces.push_back(h);});
        CHECK(large_io.remember_home(large_io.sample()));
        CHECK(large_io.return_home_clear(large_io.sample(),private_home.xyz));
        CHECK(large_traces.front().words[7]==751&&large_traces.front().words[8]==1&&large_traces.front().words[22]==2);
        CHECK(large_traces.size()==253&&large_traces.back().kind==34&&large_traces.back().words[1]==750);
        home_fixture=large_traces;
        for(int i=0;i<10;i++)CHECK(large_io.return_home_clear(large_io.sample(),private_home.xyz));
        CHECK(!large_io.return_home_clear(large_io.sample(),private_home.xyz));
        CHECK(large_traces.size()==2784&&(large_traces.back().words[16]&2)&&large_traces.back().words[1]==0);
        auto prior_calls=calls.count;
        CHECK(large_io.issue(Action::Move,private_home.xyz,0)==Delivery::NotSent&&calls.count==prior_calls);
    }
    m.set(0x6150,1u);CHECK(!io.remember_home(io.sample())&&!io.ground_target(private_home.xyz));m.set(0x6150,0u);
    CHECK(io.remember_home(io.sample()));
    // Captured second-lease precondition: another own class (Flak) already
    // stands on the private home. Reject BEFORE Borrow; a former home grant
    // must not survive this fresh rejection. No Flak AI layout is assumed.
    m.zero(0x11000,0x500);m.zero(0x12000,0x20);
    m.set(0x507c,0x11000u);m.set(0x11000,0xc4db60u);m.set(0x11004,0x12000u);
    m.set(0x110dc,798u);m.set(0x11418,0x2000u);m.set(0x12008,0x2c358c61u);
    CHECK(!io.remember_home(io.sample())&&!io.ground_target(private_home.xyz));
    m.set(0xb100,0xc55130u);m.set(0xb104,16u);m.set(0x6050,0u);m.set(0x6310,0xffffffffu);
    Controller unsafe_lender(binding(),io);auto request=command(1);request.actor=registered;
    auto unsafe=unsafe_lender.submit(request);
    CHECK(!unsafe.accepted&&std::string(unsafe.reason)=="native_lender_quiescence_unverified"&&!unsafe_lender.status().held&&calls.count==0);
    CHECK(!io.independent_borrow_permitted(io.sample()));
    m.set(0x6050,2u);CHECK(io.independent_borrow_permitted(io.sample()));
    m.set(0x6310,11u);CHECK(!io.independent_borrow_permitted(io.sample()));m.set(0x6310,0xffffffffu);
    witness.quiet=false;CHECK(!io.independent_borrow_permitted(io.sample()));witness.quiet=true;
    Controller occupied(binding(),io);
    auto refused=occupied.submit(request);
    CHECK(!refused.accepted&&calls.count==0&&!occupied.status().held);
    CHECK(std::string(refused.reason)=="private_home_ground_or_vacancy_unverified");
    m.set(0x11038,40.f);CHECK(io.remember_home(io.sample()));
    // Actual 032313 shape: the leased actor is away while another own Thing
    // occupies its private origin. Prior home admission cannot grant a Move.
    m.set(0x5038,40.f);m.set(0x11038,0.f);m.set(0x5414,0x4000u);m.set(0xe038,2u);witness.stop_owned=true;
    m.set(0xb100,0xc551a0u);m.set(0xb104,94u);m.set(0x6050,1u);
    auto return_sample=io.sample();CHECK(return_sample.settled);
    auto count_before=calls.count;
    CHECK(!io.return_home_clear(return_sample,private_home.xyz));
    CHECK(clearance.size()==2&&clearance[0].kind==32&&clearance[0].words[1]==2&&clearance[0].words[10]==0x11000);
    CHECK(clearance[1].kind==34);
    CHECK(io.issue(Action::Move,private_home.xyz,0)==Delivery::NotSent&&calls.count==count_before);
    m.set(0x11038,40.f);CHECK(io.return_home_clear(io.sample(),private_home.xyz));
    CHECK(clearance[clearance.size()-4].words[1]==1);
    m.data.erase(0x11418);CHECK(!io.return_home_clear(io.sample(),private_home.xyz));m.set(0x11418,0x2000u);
    auto malformed_registry=registry;
    MemoryIO malformed(binding(),native,registered,malformed_registry,m,calls,witness,surface,{});
    m.set(0x11038,80.f);
    CHECK(malformed.remember_home(malformed.sample()));
    m.set(0x1107c,0x11000u);CHECK(!malformed.return_home_clear(malformed.sample(),Point{40,0,0}));m.set(0x1107c,0u);
    m.set(0x11038,40.f);
    CHECK(!io.return_home_clear(io.sample(),Point{1,0,0}));
    m.set(0x5038,0.f);m.set(0x5414,0x3000u);m.set(0xe038,0u);witness.stop_owned=false;
    // Unknown reads fail closed rather than turning a partial list into an
    // empty one. Restoring the original list leaves the existing chain valid.
    m.data.erase(0x11418);CHECK(!io.remember_home(io.sample()));
    m.set(0x507c,0u);CHECK(io.remember_home(io.sample()));
    m.set(0xb100,0xc55130u);m.set(0xb104,16u);m.set(0x6050,2u);
    CHECK(io.sample().actor_birth_verified);CHECK(io.issue(Action::Borrow,{},0)==Delivery::Sent&&calls.count==1);
    // A native-assigned own squad is eligible, while another player's team
    // invalidates identity even if the actor's own owner word is unchanged.
    m.zero(0xf000,0x200);m.set(0xf004,0xf100u);m.set(0xf108,0x2000u);m.set(0x5414,0xf000u);
    CHECK(io.sample().identity&&io.issue(Action::Borrow,{},0)==Delivery::Sent&&calls.count==2);
    m.set(0xf108,0x9999u);CHECK(!io.sample().identity&&io.issue(Action::Borrow,{},0)==Delivery::NotSent);
    m.set(0x5414,0x3000u);
    // EACH call rereads pause, generation tuple, process binding, and game thread.
    m.set(0x115c,1u);CHECK(io.issue(Action::Borrow,{},0)==Delivery::NotSent);m.set(0x115c,0u);
    m.tid++;CHECK(io.issue(Action::Borrow,{},0)==Delivery::NotSent);m.tid--;
    m.b.process_start++;CHECK(io.issue(Action::Borrow,{},0)==Delivery::NotSent);m.b.process_start--;
    witness.ready=false;CHECK(io.issue(Action::Borrow,{},0)==Delivery::NotSent);witness.ready=true;
    CHECK(!io.ground_target(Point{99,0,0}));CHECK(io.ground_target(Point{100,0,0}));
    m.set(0x5414,0x4000u);m.set(0x6310,0xffffffffu);m.set(0xb100,0xc55130u);m.set(0xb104,16u);m.set(0x6050,2u);
    uint32_t recovery_clock=100;Sample recovery{};
    auto advance=[&](){m.set(0x1050,++recovery_clock);recovery=io.sample();return io.independent_recovery_permitted(recovery);};
    CHECK(!advance());for(int i=0;i<10;i++){recovery=io.sample();CHECK(!io.independent_recovery_permitted(recovery));}
    for(int i=0;i<4;i++){advance();}CHECK(io.independent_recovery_permitted(recovery));
    for(auto change:std::vector<std::pair<uint32_t,uint32_t>>{{0x6310,0},{0xb100,0xc551a0},{0xb104,94},{0x6050,1},{0xe038,1},{0x6150,1},{0xb078,1},{0xb024,0},{0xb118,0}}){
        auto old=m.data; m.set(change.first,change.second);CHECK(!advance());m.data=old;for(int i=0;i<4;i++){advance();}CHECK(io.independent_recovery_permitted(recovery));
    }
    witness.quiet=false;CHECK(!advance());witness.quiet=true;for(int i=0;i<4;i++){advance();}CHECK(io.independent_recovery_permitted(recovery));
    // A stopped native state without ownership of the old Stop may authorize
    // a fresh reconciliation brake, but it must not itself become Stop3/Ready.
    m.set(0xb100,0xc551a0u);m.set(0xb104,94u);m.set(0x6050,1u);m.set(0xe038,2u);
    for(int i=0;i<4;i++){advance();}
    CHECK(!recovery.settled&&io.independent_recovery_permitted(recovery));
    // Captured 073613 shape: source2 Stop94 after a foreign Move is stationary but
    // never becomes ownership of our old Stop. Only a new recovery may brake.
    m.set(0x6050,2u);
    for(int i=0;i<4;i++){advance();}
    CHECK(!recovery.settled&&io.independent_recovery_permitted(recovery));
    m.set(0x6050,0u);for(int i=0;i<4;i++){advance();}
    CHECK(!io.independent_recovery_permitted(recovery));
    m.set(0x6050,2u);m.set(0x6310,50u);for(int i=0;i<4;i++){advance();}
    CHECK(!io.independent_recovery_permitted(recovery));
    m.set(0x6310,0xffffffffu);for(int i=0;i<4;i++){advance();}
    CHECK(!recovery.settled&&io.independent_recovery_permitted(recovery));
    m.set(0x50dc,56u);CHECK(io.issue(Action::Borrow,{},0)==Delivery::NotSent);m.set(0x50dc,55u);
    CHECK(!io.sample().actor_birth_verified);CHECK(calls.count==2);
}
static void recovery_after_borrow_before_any_stop_is_new_emergency_only(){
    Fake io;Controller c(binding(),io);CHECK(c.submit(command(1)).accepted);io.tick(c);
    CHECK(io.calls==std::vector<Action>{Action::Borrow});io.s.settled=false;io.s.state_id=16;io.s.stance=0;io.s.foreign_epoch++;io.tick(c);
    CHECK(c.status().phase==Phase::Uncertain&&c.status().held);
    auto old=command(1);CHECK(!c.submit(old).accepted&&io.calls.size()==1);
    CHECK(!c.submit(command(2,Operation::ReconcileRelease)).accepted&&io.calls.size()==1);
    io.recovery=true;auto recovery=command(3,Operation::ReconcileRelease);CHECK(c.submit(recovery).accepted);
    for(int i=0;i<40&&c.status().phase!=Phase::Released;i++)io.tick(c);
    auto result=c.status();CHECK(result.command==recovery.command&&result.sequence==3&&result.control_released&&result.stance_restored&&!result.physical_home);
    CHECK(result.sdk_calls[0]==1&&result.sdk_calls[1]==1&&result.sdk_calls[2]==1&&result.sdk_calls[3]==0&&result.sdk_calls[4]==1&&result.sdk_calls[5]==1);
    CHECK(std::none_of(io.events.begin(),io.events.end(),[](const Event& e){return e.receipt.phase==Phase::Ready;}));
    CHECK(std::any_of(io.events.begin(),io.events.end(),[&](const Event& e){return std::string(e.kind)=="recovery_prior_unknown"&&e.receipt.command==old.command;}));
}
static void actual_roster_transfer_scope(){
    CHECK(owned_roster_member(false,0x1104,0x838877,9,9,0x1000,true,Action::Borrow));
    CHECK(owned_roster_member(true,0x1104,0x83885b,9,9,0x1000,true,Action::TransferBack));
    CHECK(!owned_roster_member(true,0x1104,0x83885b,9,9,0x1000,true,Action::Borrow));
    CHECK(!owned_roster_member(false,0x1104,0x838877,9,9,0x1000,true,Action::TransferBack));
    CHECK(!owned_roster_member(false,0x2200,0x838877,9,9,0x1000,true,Action::Borrow));
    CHECK(!owned_roster_member(false,0x1104,0x838876,9,9,0x1000,true,Action::Borrow));
    CHECK(!owned_roster_member(false,0x1104,0x838877,10,9,0x1000,true,Action::Borrow));
    CHECK(!owned_roster_member(false,0x1104,0x838877,9,9,0x1000,false,Action::Borrow));
}
static void captured_deferred_stop_lineage(){
    // Semantic payload and ignored padding are from the failed 151325 native
    // trace. Native copy stores only the defined fields; decode rewrites padding.
    std::array<uint32_t,23> command{};command[0]=5;command[1]=1;command[14]=0x7783863c;command[19]=0xc1886c;command[22]=0x1aeb01;
    std::array<uint32_t,24> before{},stored{};before[0]=0xffffffffu;before[11]=stored[11]=0xb7;before[15]=stored[15]=0xbb;before[20]=stored[20]=0xc1886c;before[23]=stored[23]=1;
    stored[0]=5;stored[1]=1;
    auto decoded=command;decoded[10]=0x30300;decoded[14]=4;decoded[22]=1;
    MoveLineage stop(20,0x5000,0x6000);CHECK(stop.arm_stop(20,100));CHECK(stop.stop_facade_enter(0x6024,1,20,100,true));auto prior=stop.context();
    CHECK(stop.dispatch_enter(0x6024,0x10000,command.data(),0x54b0c5,20,100,true));
    CHECK(stop.copy_before(0x6310,0x10000,before.data(),command.data(),0x787d42,20,100,true));CHECK(stop.copy_after(before.data(),stored.data(),command.data()));stop.dispatch_exit(prior);stop.facade_exit();
    CHECK(stop.pending()&&!stop.stop_delivered()&&!stop.delivered());
    CHECK(stop.unpack_before(0x6310,0x5000,0x20000,stored.data(),0x7da0b3,20,105,false));CHECK(stop.unpack_after(true,decoded.data()));prior=stop.context();
    CHECK(stop.dispatch_enter(0x6024,0x20000,decoded.data(),0x7da0d9,20,105,false));CHECK(stop.private_stop(0x6000,1,0x787791,20,105,false));stop.dispatch_exit(prior);
    CHECK(stop.stop_delivered()&&!stop.pending()&&!stop.delivered()&&stop.epoch()==0);
    CHECK(!stop.private_stop(0x6000,1,0x787791,20,106,false));CHECK(stop.epoch()>0);
    for(unsigned change=0;change<6;change++){
        MoveLineage bad(20,0x5000,0x6000);CHECK(bad.arm_stop(20,100));CHECK(bad.stop_facade_enter(0x6024,1,20,100,true));CHECK(bad.dispatch_enter(0x6024,0x10000,command.data(),0x54b0c5,20,100,true));
        CHECK(!bad.private_stop(change==0?0x6004:0x6000,change==1?2:1,change==2?0x787790:0x787791,change==3?21:20,change==4?1001:100,change==5?false:true)&&bad.epoch()>0);
    }
    MoveLineage foreign(20,0x5000,0x6000);CHECK(!foreign.stop_facade_enter(0x6024,1,20,100,false));CHECK(foreign.epoch()>0);
    MoveLineage wrong_caller(20,0x5000,0x6000);CHECK(wrong_caller.arm_stop(20,100));CHECK(wrong_caller.stop_facade_enter(0x6024,1,20,100,true));CHECK(!wrong_caller.dispatch_enter(0x6024,0x10000,command.data(),0x54b0c4,20,100,true));
}
struct CapturedPartialMove:Fake {
    unsigned moves=0;bool stall_return=false;std::vector<Point> goals;
    CapturedPartialMove(){s.xyz={2929.21826171875f,2920.251953125f,210.f};}
    Delivery issue(Action action,Point target,uint32_t stance)override{
        if(action!=Action::Move)return Fake::issue(action,target,stance);
        calls.push_back(action);goals.push_back(target);moves++;
        s.xyz=moves==1||stall_return?Point{2970.f,2930.f,210.f}:target;
        s.normal_move_owned=true;return Delivery::Sent;
    }
};
static void captured_partial_move_returns_without_claiming_goal(){
    CapturedPartialMove io;auto home=io.s.xyz;Controller c(binding(),io);ready(io,c);
    auto move=command(2,Operation::MoveHold);move.target={2952.4541015625f,2956.827880859375f,210.f};
    CHECK(c.submit(move).accepted);
    for(int i=0;i<200&&c.status().phase!=Phase::Released;i++)io.tick(c);
    auto result=c.status();CHECK(result.phase==Phase::Released&&result.physical_home&&result.control_released&&!result.held);
    CHECK(std::string(result.reason)=="native_control_release_without_goal_effect");
    CHECK(result.sequence==2&&io.goals.size()==2&&io.goals[0]==move.target&&io.goals[1]==home);
    CHECK(result.sdk_calls[3]==2&&result.sdk_calls[2]==3);
    CHECK(std::any_of(io.events.begin(),io.events.end(),[](const Event& e){return std::string(e.receipt.reason)=="outbound_stalled_return_home_without_goal_effect";}));
    CHECK(std::none_of(io.events.begin(),io.events.end(),[](const Event& e){return e.receipt.phase==Phase::Holding||e.receipt.phase==Phase::TargetBraking;}));
}
static void stalled_return_keeps_control_unknown_without_retry(){
    CapturedPartialMove io;io.stall_return=true;Controller c(binding(),io);ready(io,c);
    auto move=command(2,Operation::MoveHold);move.target={2952.4541015625f,2956.827880859375f,210.f};CHECK(c.submit(move).accepted);
    for(int i=0;i<250&&c.status().phase!=Phase::Uncertain;i++)io.tick(c);
    auto result=c.status();CHECK(result.phase==Phase::Uncertain&&result.held&&!result.control_released&&!result.physical_home);
    CHECK(std::string(result.reason)=="return_stalled_control_release_unknown"&&result.sdk_calls[3]==2);
    auto calls=io.calls.size();for(int i=0;i<100;i++)io.tick(c);CHECK(io.calls.size()==calls);
}
static void return_waits_for_current_vacancy_and_distinct_stop_samples(){
    Fake io;Controller c(binding(),io);ready(io,c);io.s.xyz.x=40;io.home_clear=false;
    CHECK(c.submit(command(2,Operation::ReturnHome)).accepted);
    for(int i=0;i<20&&c.status().phase!=Phase::Returning;i++)io.tick(c);
    CHECK(c.status().phase==Phase::Returning);
    for(int i=0;i<12;i++)io.tick(c);
    CHECK(std::count(io.calls.begin(),io.calls.end(),Action::Move)==0);
    io.home_clear=true;io.tick(c);
    for(int i=0;i<10;i++)io.tick(c,false);
    CHECK(std::count(io.calls.begin(),io.calls.end(),Action::Move)==0);
    io.tick(c);CHECK(std::count(io.calls.begin(),io.calls.end(),Action::Move)==0);
    io.home_clear=false;io.tick(c);io.home_clear=true;
    io.tick(c);io.tick(c);CHECK(std::count(io.calls.begin(),io.calls.end(),Action::Move)==0);
    io.tick(c);CHECK(std::count(io.calls.begin(),io.calls.end(),Action::Move)==1);
    for(int i=0;i<30&&c.status().phase!=Phase::Released;i++)io.tick(c);
    CHECK(c.status().physical_home&&c.status().control_released);
}
static void occupied_return_timeout_never_attempts_or_replays_move(){
    Fake io;Controller c(binding(),io);ready(io,c);io.s.xyz.x=40;io.home_clear=false;
    CHECK(c.submit(command(2,Operation::ReturnHome)).accepted);
    for(int i=0;i<210&&c.status().phase!=Phase::Uncertain;i++)io.tick(c);
    CHECK(c.status().phase==Phase::Uncertain&&c.status().held&&!c.status().physical_home&&!c.status().control_released);
    CHECK(std::string(c.status().reason)=="return_home_clearance_timeout_no_move");
    CHECK(std::count(io.calls.begin(),io.calls.end(),Action::Move)==0);
    auto count=io.calls.size();io.home_clear=true;
    for(int i=0;i<100;i++)io.tick(c);
    CHECK(io.calls.size()==count);
    io.recovery=true;CHECK(c.submit(command(3,Operation::ReconcileRelease)).accepted);
    for(int i=0;i<30&&c.status().phase!=Phase::Released;i++)io.tick(c);
    CHECK(c.status().control_released&&!c.status().physical_home);
    CHECK(std::count(io.calls.begin(),io.calls.end(),Action::Move)==0);
}
static void vacancy_after_old90frame_wait_can_return_without_move_retry(){
    Fake io;Controller c(binding(),io);ready(io,c);io.s.xyz.x=40;io.home_clear=false;
    CHECK(c.submit(command(2,Operation::ReturnHome)).accepted);
    for(int i=0;i<20&&c.status().phase!=Phase::Returning;i++)io.tick(c);
    auto start=io.s.frame;
    for(int i=0;i<115;i++)io.tick(c);
    CHECK(io.s.frame-start==115&&c.status().phase==Phase::Returning&&c.status().held);
    CHECK(std::count(io.calls.begin(),io.calls.end(),Action::Move)==0);
    io.home_clear=true;
    for(int i=0;i<30&&c.status().phase!=Phase::Released;i++)io.tick(c);
    CHECK(c.status().phase==Phase::Released&&c.status().physical_home&&c.status().control_released);
    CHECK(std::count(io.calls.begin(),io.calls.end(),Action::Move)==1);
}
static void extended_vacancy_wait_does_not_run_past_lease_deadline(){
    Fake io;Controller c(binding(),io);ready(io,c);io.s.xyz.x=40;io.home_clear=false;
    io.s.frame=700;
    CHECK(c.submit(command(2,Operation::ReturnHome)).accepted);
    for(int i=0;i<20&&c.status().phase!=Phase::Returning;i++)io.tick(c);
    io.s.frame=798;io.tick(c);CHECK(c.status().phase==Phase::Returning);
    io.home_clear=true;io.tick(c);
    CHECK(c.status().phase==Phase::Uncertain&&c.status().held&&!c.status().physical_home);
    CHECK(std::string(c.status().reason)=="return_home_clearance_lease_deadline_no_move");
    CHECK(std::count(io.calls.begin(),io.calls.end(),Action::Move)==0);
    for(int i=0;i<30;i++)io.tick(c);
    CHECK(std::count(io.calls.begin(),io.calls.end(),Action::Move)==0);
}
static void existing_safety_return_after_lease_expiry_still_uses_original_window(){
    Fake io;Controller c(binding(),io);ready(io,c);io.s.xyz.x=40;io.s.frame=800;
    CHECK(c.submit(command(2,Operation::ReturnHome)).accepted);
    for(int i=0;i<35&&c.status().phase!=Phase::Released;i++)io.tick(c);
    CHECK(c.status().phase==Phase::Released&&c.status().physical_home&&c.status().control_released);
    CHECK(std::count(io.calls.begin(),io.calls.end(),Action::Move)==1);
}
static void explicit_late_recovery_cannot_be_redirected_by_expired_lease(){
    Fake io;Controller c(binding(),io);ready(io,c);io.s.xyz.x=40;io.s.foreign_epoch++;io.tick(c);
    CHECK(c.status().phase==Phase::Uncertain);io.s.frame=1000;io.recovery=true;
    auto recovery=command(3,Operation::ReconcileRelease);recovery.expires_frame=2000;
    CHECK(c.submit(recovery).accepted);
    for(int i=0;i<40&&c.status().phase!=Phase::Released;i++)io.tick(c);
    CHECK(c.status().phase==Phase::Released&&c.status().control_released&&c.status().stance_restored&&!c.status().physical_home);
    CHECK(std::count(io.calls.begin(),io.calls.end(),Action::Move)==0);
    CHECK(std::none_of(io.events.begin(),io.events.end(),[](const Event& e){return std::string(e.receipt.reason)=="lease_deadline_return_home";}));
}
static Command recovery_home_command(uint32_t seq=3){
    auto r=command(seq,Operation::ReconcileReturnHome);r.target={};r.hold_frames=0;return r;
}
static void interrupted_hold(Fake& io,Controller& c){
    ready(io,c);auto move=command(2,Operation::MoveHold);move.hold_frames=675;CHECK(c.submit(move).accepted);
    for(int i=0;i<30&&c.status().phase!=Phase::Holding;i++)io.tick(c);
    CHECK(c.status().phase==Phase::Holding&&c.status().sdk_calls[3]==1);
    io.s.foreign_epoch++;io.tick(c);CHECK(c.status().phase==Phase::Uncertain);io.recovery=true;
}
static void recovery_first_home_move_keeps_old_failure_and_has_no_goal_credit(){
    Fake io;Controller c(binding(),io);interrupted_hold(io,c);auto r=recovery_home_command();
    CHECK(c.submit(r).accepted);auto calls=io.calls.size();CHECK(!c.submit(r).accepted&&io.calls.size()==calls);
    for(int i=0;i<50&&c.status().phase!=Phase::Released;i++)io.tick(c);
    auto done=c.status();CHECK(done.phase==Phase::Released&&done.physical_home&&done.control_released&&done.stance_restored&&!done.held);
    CHECK(done.sequence==3&&done.sdk_calls[3]==2&&std::count(io.calls.begin(),io.calls.end(),Action::Move)==2);
    CHECK(std::string(done.reason)=="native_control_release_without_goal_effect");
    CHECK(std::any_of(io.events.begin(),io.events.end(),[](const Event& e){return e.receipt.sequence==2&&e.receipt.phase==Phase::Uncertain;}));
    CHECK(std::none_of(io.events.begin(),io.events.end(),[](const Event& e){return std::string(e.receipt.reason)=="hold_interval_complete";}));
}
static void recovery_return_rejects_changed_target_lease_geometry_and_noncommit(){
    for(int variant=0;variant<5;variant++){
        Fake io;Controller c(binding(),io);interrupted_hold(io,c);auto r=recovery_home_command();
        if(variant==0)r.target.x=1;
        if(variant==1)r.lease_deadline_frame++;
        if(variant==2)r.hold_frames=1;
        if(variant==3)io.s.xyz.x=301;
        if(variant==4)io.s.xyz.z=3;
        auto calls=io.calls.size();CHECK(!c.submit(r).accepted&&io.calls.size()==calls&&c.status().phase==Phase::Uncertain);
    }
    Fake io;Controller c(binding(),io);ready(io,c);io.s.foreign_epoch++;io.tick(c);io.recovery=true;
    auto calls=io.calls.size();CHECK(!c.submit(recovery_home_command()).accepted&&io.calls.size()==calls);
}
static void recovery_home_denies_prior_sent_and_notsent_home_attempts(){
    for(bool notsent:{false,true}){
        Fake io;Controller c(binding(),io);ready(io,c);CHECK(c.submit(command(2,Operation::MoveHold)).accepted);
        for(int i=0;i<40&&c.status().phase!=Phase::Returning;i++)io.tick(c);
        CHECK(c.status().phase==Phase::Returning);
        if(notsent){io.delivery=Delivery::NotSent;for(int i=0;i<5&&c.status().phase!=Phase::Uncertain;i++)io.tick(c);}
        else {for(int i=0;i<5&&c.status().sdk_calls[3]<2;i++)io.tick(c);io.s.foreign_epoch++;io.tick(c);}
        CHECK(c.status().phase==Phase::Uncertain&&c.status().sdk_calls[3]==(notsent?1u:2u));
        io.delivery=Delivery::Sent;io.recovery=true;auto calls=io.calls.size();
        auto denied=c.submit(recovery_home_command());CHECK(!denied.accepted&&std::string(denied.reason)=="recovery_return_requires_unattempted_home"&&io.calls.size()==calls);
    }
}
static void recovery_home_at_origin_needs_no_move_and_late_lease_does_not_redirect(){
    for(bool already_home:{false,true}){
        Fake io;Controller c(binding(),io);interrupted_hold(io,c);io.s.frame=1000;if(already_home)io.s.xyz={};
        auto r=recovery_home_command();r.expires_frame=2000;CHECK(c.submit(r).accepted);
        for(int i=0;i<50&&c.status().phase!=Phase::Released;i++)io.tick(c);
        CHECK(c.status().phase==Phase::Released&&c.status().physical_home&&c.status().control_released);
        CHECK(c.status().sdk_calls[3]==(already_home?1u:2u));
        CHECK(std::none_of(io.events.begin(),io.events.end(),[](const Event& e){return std::string(e.receipt.reason)=="lease_deadline_return_home";}));
    }
}
static void recovery_home_uses_fresh_vacancy_and_distinct_stop_frames(){
    Fake io;Controller c(binding(),io);interrupted_hold(io,c);io.home_clear=false;CHECK(c.submit(recovery_home_command()).accepted);
    for(int i=0;i<20&&c.status().phase!=Phase::Returning;i++)io.tick(c);
    CHECK(c.status().phase==Phase::Returning);
    for(int i=0;i<10;i++){io.tick(c);}CHECK(c.status().sdk_calls[3]==1);
    io.home_clear=true;io.tick(c);for(int i=0;i<10;i++)io.tick(c,false);CHECK(c.status().sdk_calls[3]==1);
    io.tick(c);CHECK(c.status().sdk_calls[3]==1);io.home_clear=false;io.tick(c);io.home_clear=true;
    io.tick(c);io.tick(c);CHECK(c.status().sdk_calls[3]==1);io.tick(c);CHECK(c.status().sdk_calls[3]==2);
    for(int i=0;i<30&&c.status().phase!=Phase::Released;i++)io.tick(c);
    CHECK(c.status().physical_home&&c.status().control_released);
}
static void recovery_home_total_budget_does_not_extend_to_original_work_budget(){
    Fake io;Controller c(binding(),io);interrupted_hold(io,c);io.home_clear=false;CHECK(c.submit(recovery_home_command()).accepted);
    for(int i=0;i<29;i++){io.s.frame++;io.s.monotonic_ms+=1000;c.tick();}
    CHECK(c.status().phase==Phase::Returning&&c.status().sdk_calls[3]==1);
    for(int i=0;i<2;i++){io.s.frame++;io.s.monotonic_ms+=1000;c.tick();}
    CHECK(c.status().phase==Phase::Uncertain&&std::string(c.status().reason)=="runtime_watchdog_expired");
    auto calls=io.calls.size();for(int i=0;i<30;i++)io.tick(c);CHECK(io.calls.size()==calls);
}
static void recovery_unknown_home_move_is_not_reissued_and_can_only_release(){
    Fake io;Controller c(binding(),io);interrupted_hold(io,c);CHECK(c.submit(recovery_home_command()).accepted);
    for(int i=0;i<20&&c.status().phase!=Phase::Returning;i++)io.tick(c);
    io.delivery=Delivery::Unknown;for(int i=0;i<5&&c.status().phase!=Phase::Uncertain;i++)io.tick(c);
    CHECK(c.status().phase==Phase::Uncertain&&c.status().sdk_calls[3]==2);
    auto calls=io.calls.size();CHECK(!c.submit(recovery_home_command(4)).accepted&&io.calls.size()==calls);
    io.delivery=Delivery::Sent;CHECK(c.submit(command(5,Operation::ReconcileRelease)).accepted);
    for(int i=0;i<30&&c.status().phase!=Phase::Released;i++)io.tick(c);
    CHECK(c.status().control_released&&!c.status().physical_home&&c.status().sdk_calls[3]==2);
}
static void active_home_recovery_rejects_overrides_and_preemption_cannot_repeat_move(){
    Fake io;Controller c(binding(),io);interrupted_hold(io,c);CHECK(c.submit(recovery_home_command()).accepted);
    CHECK(c.submit(command(4,Operation::Query)).accepted);auto calls=io.calls.size();
    auto denied=c.submit(command(5,Operation::ReturnHome));CHECK(!denied.accepted&&std::string(denied.reason)=="safety_recovery_already_active"&&io.calls.size()==calls);
    for(int i=0;i<25&&c.status().sdk_calls[3]<2;i++)io.tick(c);
    CHECK(c.status().sdk_calls[3]==2);io.preemption=NativePreemption::VerifiedYield;io.tick(c);
    CHECK(c.status().phase==Phase::Uncertain&&std::string(c.status().reason)=="recovery_home_interrupted_no_retry");
    calls=io.calls.size();for(int i=0;i<30;i++)io.tick(c);CHECK(io.calls.size()==calls);
}
static void holding_for_fault(Fake& io,Controller& c){
    ready(io,c);auto r=command(2,Operation::MoveHold);r.hold_frames=675;CHECK(c.submit(r).accepted);
    for(int i=0;i<30&&c.status().phase!=Phase::Holding;i++)io.tick(c);
    CHECK(c.status().phase==Phase::Holding);
}
static Command fault_command(uint32_t seq=3){auto r=command(seq,Operation::DiagnosticForeignMove);r.target={140,0,0};r.hold_frames=0;return r;}
static void default_disabled_fault_never_calls_or_consumes_a_sequence(){
    Fake io;Controller c(binding(),io);holding_for_fault(io,c);auto prior=c.status();
    auto denied=c.submit(fault_command());CHECK(!denied.accepted&&std::string(denied.reason)=="diagnostic_fault_disabled_or_used");
    CHECK(io.faults.empty()&&c.last_sequence()==2&&c.status().command==prior.command&&c.status().phase==Phase::Holding);
}
static void diagnostic_fault_rejects_nonholding_identity_expiry_and_bad_points(){
    for(int variant=0;variant<10;variant++){
        Fake io;Controller c(binding(),io);holding_for_fault(io,c);io.fault=true;auto r=fault_command();
        if(variant==0)r.target={110,0,0};
        if(variant==1)r.target={0,0,0};
        if(variant==2)r.target={221,0,0};
        if(variant==3)io.surface=false;
        if(variant==4)r.lease_deadline_frame++;
        if(variant==5)r.hold_frames=1;
        if(variant==6)io.s.foreign_epoch++;
        if(variant==7)r.actor.object_id++;
        if(variant==8)io.s.frame=800;
        if(variant==9)io.s.settled=false;
        CHECK(!c.submit(r).accepted&&io.faults.empty()&&c.last_sequence()==2);
    }
    Fake io;Controller c(binding(),io);ready(io,c);io.fault=true;CHECK(!c.submit(fault_command()).accepted&&io.faults.empty());
}
static void one_fault_has_own_ack_but_guard_unknown_still_names_original_work(){
    Fake io;Controller c(binding(),io);holding_for_fault(io,c);io.fault=true;auto prior=c.status();auto fault=fault_command();
    auto ack=c.submit(fault);CHECK(ack.accepted&&ack.command==fault.command&&ack.sequence==3);
    CHECK(c.status().command==prior.command&&c.status().sequence==2&&c.status().phase==Phase::Holding&&c.status().sdk_calls[3]==1&&c.last_sequence()==3);
    CHECK(!c.submit(fault).accepted&&!c.submit(fault_command(4)).accepted&&io.faults.size()==1);
    io.tick(c);CHECK(c.status().phase==Phase::Uncertain&&c.status().sequence==2&&std::string(c.status().reason)=="unknown_native_command_observed");
    io.recovery=true;CHECK(c.submit(recovery_home_command(5)).accepted);
    for(int i=0;i<50&&c.status().phase!=Phase::Released;i++)io.tick(c);
    CHECK(c.status().physical_home&&c.status().control_released&&c.status().sdk_calls[3]==2&&io.faults.size()==1);
    CHECK(std::count(io.calls.begin(),io.calls.end(),Action::Move)==2);
    CHECK(std::string(c.status().reason)=="native_control_release_without_goal_effect");
}
static void refused_or_unknown_fault_never_reuses_its_intent_or_old_work_identity(){
    for(auto delivery:{Delivery::NotSent,Delivery::Unknown}){
        Fake io;Controller c(binding(),io);holding_for_fault(io,c);io.fault=true;io.fault_delivery=delivery;
        auto ack=c.submit(fault_command());CHECK(ack.accepted==(delivery!=Delivery::NotSent)&&c.last_sequence()==3&&io.faults.size()==1&&c.status().sequence==2);
        CHECK(c.status().phase==(delivery==Delivery::Unknown?Phase::Uncertain:Phase::Holding));
        CHECK(!c.submit(fault_command(4)).accepted&&io.faults.size()==1);
    }
}
static void endpoints_require_distinct_stable_frames_then_vacancy(){
    // State/vtable pair observed on stationary own native conscripts in the
    // read-only 161304 capture. This fixture tests point selection, not Stop3.
    Endpoints endpoints(binding());Fake io;auto sample=io.s;sample.xyz={60,0,0};sample.state_id=10;sample.state_vtable=0xc548c0;
    endpoints.begin_frame();endpoints.record(sample,sample);
    for(int i=0;i<10;i++)endpoints.record(sample,sample);
    CHECK(!endpoints.contains(binding(),sample.xyz));
    sample.frame++;endpoints.begin_frame();endpoints.record(sample,sample);CHECK(!endpoints.contains(binding(),sample.xyz));
    sample.frame++;endpoints.begin_frame();endpoints.record(sample,sample);CHECK(!endpoints.contains(binding(),sample.xyz));
    CHECK(endpoints.available({0,0,0}).empty());
    sample.frame++;sample.xyz={90,0,0};endpoints.begin_frame();endpoints.record(sample,sample);
    CHECK(endpoints.available({0,0,0}).size()==1&&endpoints.available({0,0,0})[0]==Point({60,0,0}));
    Endpoints walking(binding());
    for(int i=0;i<10;i++){sample.frame++;sample.xyz.x++;walking.begin_frame();walking.record(sample,sample);}
    CHECK(walking.available({0,0,0}).empty()&&!walking.contains(binding(),sample.xyz));
    Endpoints active_path(binding());sample.path=0x6bbce88;
    for(int i=0;i<4;i++){sample.frame++;active_path.begin_frame();active_path.record(sample,sample);}
    CHECK(!active_path.contains(binding(),sample.xyz));
}
static void never_borrowed_native_team_does_not_block_observer_detach(){
    CHECK(observer_detach_admissible(false,false,false,0,false,0x5459dc0,0x54566c0));
    CHECK(!observer_detach_admissible(true,false,false,0,false,0x5459dc0,0x54566c0));
    CHECK(observer_detach_admissible(true,false,false,0,false,0x54566c0,0x54566c0));
    CHECK(!observer_detach_admissible(true,false,false,0,false,0,0));
    CHECK(!observer_detach_admissible(false,true,false,0,false,0,0));
    CHECK(!observer_detach_admissible(false,false,true,0,false,0,0));
    CHECK(!observer_detach_admissible(false,false,false,1,false,0,0));
    CHECK(!observer_detach_admissible(false,false,false,0,true,0,0));
    CHECK(observer_detach_admissible(true,false,false,0,false,0x5459dc0,0x54566c0,true,true,0x54557c0));
    CHECK(!observer_detach_admissible(true,false,false,0,false,0x5459dc0,0x54566c0,false,true,0x54557c0));
    CHECK(!observer_detach_admissible(true,false,false,0,false,0x5459dc0,0x54566c0,true,false,0x54557c0));
    CHECK(!observer_detach_admissible(true,false,false,0,false,0x54557c0,0x54566c0,true,true,0x54557c0));
}
static void admitted_native_squad_returns_to_common_pool(){
    Fake io;io.s.team=0x5459dc0;Controller c(binding(),io);ready(io,c);
    CHECK(io.s.team==io.s.script_team&&c.status().held);
    CHECK(c.submit(command(2,Operation::ReturnHome)).accepted);
    for(int i=0;i<60&&c.status().phase!=Phase::Released;i++)io.tick(c);
    CHECK(c.status().control_released&&io.s.team==io.s.default_team&&!c.status().held);
    CHECK(std::count(io.calls.begin(),io.calls.end(),Action::Borrow)==1&&std::count(io.calls.begin(),io.calls.end(),Action::TransferBack)==1);
}
static void synchronous_pool_return_is_recorded_before_native_recruitment(){
    Fake io;Controller c(binding(),io);ready(io,c);CHECK(c.submit(command(2,Operation::MoveHold)).accepted);
    for(int i=0;i<100&&c.status().phase!=Phase::Releasing;i++)io.tick(c);
    CHECK(c.status().phase==Phase::Releasing);io.tick(c);
    CHECK(c.status().phase==Phase::Released&&c.status().control_released);
    CHECK(io.events.back().observation.team==io.s.default_team);
    io.s.team=0x5459dc0;io.tick(c);
    CHECK(c.status().phase==Phase::Released&&c.status().control_released&&!c.status().held);
    CHECK(io.events.back().observation.team==io.s.default_team);
}
static void foreign_command_invalidates_prior_delivery_ownership(){
    Point goal{60,0,0};MoveLineage move(20,0x5000,0x6000);auto words=move_words(goal);
    CHECK(move.arm(goal,20,100)&&move.facade_enter(0x6024,goal,1,20,100,true));auto prior=move.context();
    CHECK(move.dispatch_enter(0x6024,0x10000,words.data(),0x571dcd,20,100,true));
    float limit=std::numeric_limits<float>::max();CHECK(move.private_move(0x6000,0x10008,goal,0,limit,1,0x6d3b7d,20,100,true));
    move.dispatch_exit(prior);move.facade_exit();CHECK(move.delivered());move.foreign();CHECK(!move.delivered()&&!move.stop_delivered());
    MoveLineage stop(20,0x5000,0x6000);words=move_words({});words[0]=5;
    CHECK(stop.arm_stop(20,101)&&stop.stop_facade_enter(0x6024,1,20,101,true));prior=stop.context();
    CHECK(stop.dispatch_enter(0x6024,0x10000,words.data(),0x54b0c5,20,101,true));
    CHECK(stop.private_stop(0x6000,1,0x787791,20,101,true));stop.dispatch_exit(prior);stop.facade_exit();CHECK(stop.stop_delivered());
    CHECK(stop.stopped_context_idle());stop.clear_for_verified_native_preemption();
    CHECK(!stop.stop_delivered()&&!stop.delivered()&&stop.epoch()==0&&!stop.stopped_context_idle());
    stop.foreign();CHECK(!stop.stop_delivered()&&!stop.delivered());
}
static void verified_yield_aborts_goal_and_returns_without_retry(){
    Fake io;Controller c(binding(),io);ready(io,c);CHECK(c.submit(command(2,Operation::MoveHold)).accepted);
    for(int i=0;i<30&&c.status().phase!=Phase::Holding;i++)io.tick(c);
    CHECK(c.status().phase==Phase::Holding);auto calls=io.calls.size();
    io.preemption=NativePreemption::WaitingYield;io.s.settled=false;
    io.tick(c);CHECK(io.calls.size()==calls&&c.status().phase==Phase::Holding);
    io.preemption=NativePreemption::VerifiedYield;io.tick(c);
    CHECK(c.status().phase==Phase::ReturnBraking&&io.calls.back()==Action::Stop);
    for(int i=0;i<60&&c.status().phase!=Phase::Released;i++)io.tick(c);
    CHECK(c.status().phase==Phase::Released&&c.status().physical_home&&c.status().control_released);
    CHECK(std::string(c.status().reason)=="native_control_release_without_goal_effect");
    CHECK(std::count(io.calls.begin(),io.calls.end(),Action::Move)==2);
    for(unsigned mode=0;mode<2;mode++){
        Fake bad;Controller controller(binding(),bad);ready(bad,controller);auto count=bad.calls.size();
        bad.preemption=mode?NativePreemption::VerifiedYield:NativePreemption::UnverifiedYield;
        if(mode)bad.s.foreign_epoch++;
        bad.tick(controller);CHECK(controller.status().phase==Phase::Uncertain&&bad.calls.size()==count);
        CHECK(bad.preemption==NativePreemption::None);
    }
}
static void lease_geometry_uses_other_native_units_and_never_controlled_motion(){
    Endpoints points(binding());Fake f;Sample native=f.s;native.xyz={60,0,0};native.path=0;native.state_flags=0;
    // A currently controlled actor cannot seed a new point during its lease.
    native.team=native.script_team;
    for(uint32_t frame=100;frame<103;frame++){native.frame=frame;points.begin_frame();points.record_native_foot(native,native,native.script_team);}
    points.begin_frame();CHECK(!points.contains(binding(),Point{60,0,0}));
    // A different native own unit can establish a point after the lease began,
    // but it remains unavailable while occupied and needs three distinct frames.
    native.team=native.default_team;native.actor.thing=0x11000;native.actor.object_id=798;native.xyz={80,0,0};
    for(uint32_t frame=103;frame<106;frame++){
        native.frame=frame;points.begin_frame();points.record_native_foot(native,native,native.script_team);
        CHECK(!points.contains(binding(),Point{80,0,0}));
    }
    points.begin_frame();CHECK(points.contains(binding(),Point{80,0,0}));
    points.occupy({65,0,0});CHECK(!points.contains(binding(),Point{80,0,0}));
    points.begin_frame(false);CHECK(points.available({0,0,0}).empty());
}
static void safety_stop_cannot_turn_explicit_reconciliation_into_another_home_move(){
    Fake io;Controller c(binding(),io);ready(io,c);c.request_stop();io.s.foreign_epoch++;
    io.tick(c);CHECK(c.status().phase==Phase::Uncertain);io.s.xyz={60,0,0};io.recovery=true;
    CHECK(c.submit(command(2,Operation::ReconcileRelease)).accepted);
    for(int i=0;i<60&&c.status().phase!=Phase::Released;i++)io.tick(c);
    CHECK(c.status().phase==Phase::Released&&c.status().control_released&&c.status().stance_restored&&!c.status().physical_home);
    CHECK(std::count(io.calls.begin(),io.calls.end(),Action::Move)==0);
    CHECK(std::string(c.status().reason)=="native_control_release_without_goal_effect");
}
static void catalogue_diagnostics_explain_filters_without_changing_admission(){
    Endpoints points(binding());Fake f;auto sample=f.s;sample.xyz={80,0,0};sample.state_flags=0;
    for(uint32_t frame=100;frame<103;frame++){sample.frame=frame;points.begin_frame();points.record(sample,sample);}
    points.begin_frame();auto d=points.diagnostics({0,0,0});
    CHECK(d.summary[1]==1&&d.summary[2]==1&&d.points.size()==1&&d.points[0][4]==0&&d.points[0][18]==1);
    CHECK(points.contains(binding(),Point{80,0,0}));
    auto short_distance=points.diagnostics({60,0,0});CHECK(short_distance.points[0][4]==2&&short_distance.summary[2]==0);
    CHECK(points.contains(binding(),Point{80,0,0}));
    auto far=points.diagnostics({-100,0,0});CHECK(far.points[0][4]==4&&far.points[0][18]==0);
    points.occupy({70,0,0});auto occupied=points.diagnostics({0,0,0});CHECK(occupied.points[0][4]==8&&occupied.points[0][18]==0);
    points.begin_frame(false);auto unknown=points.diagnostics({0,0,0});CHECK(unknown.points[0][4]==1&&unknown.summary[3]==0&&unknown.points[0][18]==0);
    points.begin_frame();auto height=points.diagnostics({0,0,10});CHECK(height.points[0][4]==16&&height.points[0][18]==1);
}
static Bytes land_fixture(){
    Bytes m;auto a=actor();
    for(auto region:std::vector<std::pair<uint32_t,uint32_t>>{{a.thing,0x500},{a.update,0x500},{a.template_ptr,0x200},
        {0x10000,0x100},{0x20000,0x100},{0x30000,0x100},{0x110000,0x100},{0x120000,0x100},{0x130000,0x200}})m.zero(region.first,region.second);
    m.set(0xcd8ce4,0x10000u);m.set(0x10000,0xbeb630u);m.set(0x10050,100u);
    m.set(a.thing,0xc4db60u);m.set(a.thing+4,a.template_ptr);m.set(a.thing+0xdc,a.object_id);m.set(a.thing+0x374,a.update);m.set(a.thing+0x418,a.owner);
    m.set(a.template_ptr+8,0x19ab11afu);m.set(a.template_ptr+0x14,0x130000u);m.set(a.thing+0x120,5.f);m.set(0x130110,-1.f);
    m.set(a.update,0xc48670u);m.set(a.update+0x24,0xc48528u);m.set(a.update+8,a.thing);m.set(a.update+0x1fc,0xc37620u);m.set(a.update+0x210,1u);
    m.set(a.thing+0x38,Point{100,100,210});m.set(0xcb122c,std::array<uint32_t,11>{{9,10,12,24,40,72,72,136,8,520,1032}});
    const unsigned char coord[]={0x8b,0x54,0x24,0x08,0xf3,0x0f,0x10,0x02,0xf3,0x0f,0x59,0x05,0xf4,0x11,0xcb,0};
    const unsigned char cell[]={0x53,0x8b,0x5c,0x24,0x0c,0x56,0x8b,0xf1,0x3b,0x5e,0x0c,0x57};
    const unsigned char height[]={0x83,0xec,0x20,0x8b,0xc1,0x8b,0x48,0x14,0x85,0xc9,0x89,0x04,0x24};
    for(uint32_t i=0;i<sizeof(coord);i++)m.set(0x68d010+i,coord[i]);
    for(uint32_t i=0;i<sizeof(cell);i++)m.set(0x544720+i,cell[i]);
    for(uint32_t i=0;i<sizeof(height);i++)m.set(0x8ed070+i,height[i]);
    m.set(0xcb11f4,0x3d4ccccdu);m.set(0xce3e30,0x20000u);m.set(0x20000,0xc18e20u);m.set(0x20028,0x30000u);
    m.set(0x30008,1u);m.set(0x3000c,0u);m.set(0x30010,0u);m.set(0x30014,20u);m.set(0x30018,20u);m.set(0x30004,0x40000u);
    for(uint32_t col=0;col<=20;col++){
        auto start=0x300000+col*0x1000;m.set(0x40000+col*4,start);m.zero(start,21*48);
        for(uint32_t row=0;row<=20;row++)m.set(start+row*48+12,0x10u);
    }
    m.set(0xce9c40,0x110000u);m.set(0x110000,0xc0a6f0u);m.set(0xc0a744,0x8ed070u);m.set(0x110014,0x120000u);
    m.set(0xbe6670,0x3dcccccdu);m.set(0xc0930c,0x3d200000u);m.set(0x120024,64u);m.set(0x120028,64u);m.set(0x12002c,2u);m.set(0x120044,0x200000u);
    for(uint32_t i=0;i<64*64;i++)m.set(0x200000+i*2,static_cast<uint16_t>(5376));
    return m;
}
static void actual_native_empty_land_endpoints_and_negative_cells(){
    auto m=land_fixture();NativeBinding n{};n.logic=0x10000;Endpoints occupied(binding());
    std::vector<NativeLandEndpoints::Proof> proofs;NativeLandEndpoints land(binding(),n,m,occupied,[&](const NativeLandEndpoints::Proof& p){proofs.push_back(p);});land.bind_actor(actor());
    auto points=land.candidates({100,100,210});CHECK(points.size()>=6&&proofs.empty());auto chosen=points.front();
    CHECK(land.contains(binding(),chosen)&&proofs.size()==1&&proofs[0].actor[9]==1&&proofs[0].raster[16]==0x43520000);
    auto cell_address=proofs[0].cell[8];auto original=m.data;
    for(auto change:std::vector<std::pair<uint32_t,uint32_t>>{{cell_address,0x99999},{cell_address+12,0x11},{cell_address+12,0x12},
        {cell_address+12,0x40010},{cell_address+12,0x20},{actor().update+0x210,3},{actor().update+0x1fc,0},
        {actor().thing+0x120,0x40c00000},{0x130110,0},{0x30008,0},{0x10050,0},{0xbe6670,0}}){
        m.set(change.first,change.second);CHECK(!land.contains(binding(),chosen));m.data=original;
    }
    occupied.occupy({chosen.x+10,chosen.y,chosen.z});CHECK(!land.contains(binding(),chosen));occupied.begin_frame(false);CHECK(!land.contains(binding(),chosen));
    occupied.begin_frame();auto wrong=chosen;wrong.z+=1;CHECK(!land.contains(binding(),wrong));
    CHECK(!land.contains(binding(),Point{120,120,210}));auto other=binding();other.pid++;CHECK(!land.contains(other,chosen));
    m.tid++;CHECK(!land.contains(binding(),chosen));m.tid--;
    // Ignored-object IDs do not alter the actor's real surface mask.
    m.set(actor().update+0x180,353u);m.set(actor().update+0x184,999u);CHECK(land.contains(binding(),chosen));
}
static void changing_native_land_cells_cannot_survive_the_paired_read(){
    struct Changing:Bytes {bool change=false;uint32_t cell=0,reads=0;
        bool read(uint32_t address,void* to,uint32_t size)override{
            if(change&&address==cell&&++reads==2)set(cell+12,0x11u);
            return Bytes::read(address,to,size);
        }
    }m;auto base=land_fixture();m.data=base.data;NativeBinding n{};n.logic=0x10000;Endpoints occupied(binding());
    std::vector<NativeLandEndpoints::Proof> proofs;NativeLandEndpoints land(binding(),n,m,occupied,[&](const NativeLandEndpoints::Proof& p){proofs.push_back(p);});land.bind_actor(actor());
    auto points=land.candidates({100,100,210});CHECK(!points.empty());CHECK(land.contains(binding(),points[0]));
    m.cell=proofs.back().cell[8];m.change=true;auto before=proofs.size();CHECK(!land.contains(binding(),points[0])&&proofs.size()==before);
}
int main(int argc,char** argv){try{
    if(argc==2&&std::string(argv[1])=="--home-clearance-fixture"){
        actual_memory_reader_admission();
        std::cout<<"{\"game_access\":false,\"logic\":4096,\"script_team\":16384,\"traces\":[";
        for(size_t i=0;i<home_fixture.size();i++){
            const auto& t=home_fixture[i];if(i)std::cout<<",";
            std::cout<<"{\"kind\":"<<t.kind<<",\"frame\":"<<t.frame<<",\"self\":"<<t.self<<",\"target\":"<<t.target<<",\"words\":[";
            for(size_t j=0;j<24;j++){if(j)std::cout<<",";std::cout<<t.words[j];}std::cout<<"]}";
        }
        std::cout<<"]}"<<std::endl;return 0;
    }
    if(argc==2&&std::string(argv[1])=="--land-evidence-fixture"){
        auto m=land_fixture();NativeBinding n{};n.logic=0x10000;Endpoints occupied(binding());std::vector<NativeLandEndpoints::Proof> proofs;
        NativeLandEndpoints land(binding(),n,m,occupied,[&](const NativeLandEndpoints::Proof& p){proofs.push_back(p);});land.bind_actor(actor());
        auto points=land.candidates({100,100,210});CHECK(!points.empty()&&land.contains(binding(),points[0])&&proofs.size()==1);
        std::cout<<"{\"game_access\":false,\"logic\":65536,\"frame\":"<<proofs[0].frame<<",\"proofs\":[";
        for(unsigned i=0;i<3;i++){
            auto& words=i==0?proofs[0].actor:i==1?proofs[0].raster:proofs[0].cell;
            if(i){std::cout<<",";}
            std::cout<<"{\"kind\":"<<29+i<<",\"words\":[";
            for(unsigned j=0;j<24;j++){if(j)std::cout<<",";std::cout<<words[j];}std::cout<<"]}";
        }
        std::cout<<"]}"<<std::endl;return 0;
    }
    happy_and_repeat();query_acknowledges_itself_without_changing_task_action();duplicated_unknown_never_replays();admission_and_clocks();bounded_target_and_ready();pause_watchdog_and_same_frame();interference_and_delivery_timeout();emergency_release_is_not_home();explicit_recovery_and_private_stop_do_not_mint_sequences();paid_registry_no_reuse();actual_memory_reader_admission();actual_normal_move_lineage();
    actual_roster_transfer_scope();
    captured_deferred_stop_lineage();
    recovery_after_borrow_before_any_stop_is_new_emergency_only();
    captured_partial_move_returns_without_claiming_goal();stalled_return_keeps_control_unknown_without_retry();
    endpoints_require_distinct_stable_frames_then_vacancy();
    never_borrowed_native_team_does_not_block_observer_detach();
    admitted_native_squad_returns_to_common_pool();
    synchronous_pool_return_is_recorded_before_native_recruitment();
    foreign_command_invalidates_prior_delivery_ownership();
    verified_yield_aborts_goal_and_returns_without_retry();
    lease_geometry_uses_other_native_units_and_never_controlled_motion();
    safety_stop_cannot_turn_explicit_reconciliation_into_another_home_move();
    catalogue_diagnostics_explain_filters_without_changing_admission();
    actual_native_empty_land_endpoints_and_negative_cells();changing_native_land_cells_cannot_survive_the_paired_read();
    return_waits_for_current_vacancy_and_distinct_stop_samples();
    occupied_return_timeout_never_attempts_or_replays_move();
    vacancy_after_old90frame_wait_can_return_without_move_retry();
    extended_vacancy_wait_does_not_run_past_lease_deadline();
    existing_safety_return_after_lease_expiry_still_uses_original_window();
    explicit_late_recovery_cannot_be_redirected_by_expired_lease();
    recovery_first_home_move_keeps_old_failure_and_has_no_goal_credit();
    recovery_return_rejects_changed_target_lease_geometry_and_noncommit();
    recovery_home_denies_prior_sent_and_notsent_home_attempts();
    recovery_home_at_origin_needs_no_move_and_late_lease_does_not_redirect();
    recovery_home_uses_fresh_vacancy_and_distinct_stop_frames();
    recovery_home_total_budget_does_not_extend_to_original_work_budget();
    recovery_unknown_home_move_is_not_reissued_and_can_only_release();
    active_home_recovery_rejects_overrides_and_preemption_cannot_repeat_move();
    default_disabled_fault_never_calls_or_consumes_a_sequence();
    diagnostic_fault_rejects_nonholding_identity_expiry_and_bad_points();
    one_fault_has_own_ack_but_guard_unknown_still_names_original_work();
    refused_or_unknown_fault_never_reuses_its_intent_or_old_work_identity();
    paid_birth_refusals_preserve_reason_and_generation();
    native_lender_denial_never_claims_or_dispatches();
    borrow_not_sent_closes_only_the_untransferred_claim();
    std::cout<<"{\"protocol\":\"tactical_runtime_v1\",\"actual_cpp_function_suites\":51,\"passed\":true,\"game_access\":false,\"field_verified\":false}"<<std::endl;return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 1;}}
