// Reuse the explicit byte-addressed target fixture. Its original 11 groups
// remain callable; no running process, game SDK or actual payment is used.
#define main original_target_fixture_main
#include "test_near_target.cpp"
#undef main
#include "near_native_admission.h"

static rt::Actor own_actor(){return {55,0x190000,0x1a0000,0x1b0000,native().owner,0x19ab11af,100,1};}
struct NativeBytes:Memory {
    uint32_t tid=20;uint64_t ms=1000;rt::Binding bound=binding();
    rt::Binding current_binding()override{return bound;}uint32_t thread()override{return tid;}
    uint64_t monotonic_ms()override{return ms;}
    void zero(uint32_t p,uint32_t size){for(uint32_t n=0;n<size;n++)data[p+n]=0;}
    NativeBytes(){
        auto a=own_actor();auto n=native();
        for(auto p:{a.thing,a.template_ptr,a.update,0x1c0000u,0x1d0000u,0x1d1000u,
            0x1e0000u,0x1e1000u,0x1e2000u,0x1e3000u,0x1e4000u,
            0x210000u,0x220000u,0x230000u,0x240000u,0x250000u,0x260000u,0x270000u,0x280000u,0x290000u,0x2a0000u})zero(p,0x500);
        u(n.owner+0xac,n.default_team);u(n.owner+0x8c,0x80000);u(0x80010,n.script_team);
        u(n.default_team+4,0x61000);u(0x61008,n.owner);u(n.script_team+4,0x71000);u(0x71008,n.owner);
        u(n.logic+0xb4,a.thing);u(a.thing,0xc4db60);u(a.thing+0xdc,a.object_id);u(a.thing+4,a.template_ptr);u(a.template_ptr+8,a.type_hash);
        u(a.thing+0x418,a.owner);u(a.thing+0x414,n.default_team);u(a.thing+0x374,a.update);u(a.thing+0x7c,target().thing);
        u(a.update,0xc48670);u(a.update+8,a.thing);u(a.update+0x24,0xc48528);u(a.update+0x3c,0x1d0000);u(a.update+0x50,2);
        u(0x1d0004,0x1d1000);u(0x1d0024,a.thing);u(0x1d1000,0xc55130);u(0x1d1004,16);u(0x1d1018,0x1d0000);
        u(a.update+0x310,0xffffffffu);u(a.thing+0x33c,0x1c0000);f(0x1c0004,120);u(a.thing+0x48,4);
        u(a.thing+0x380,0x1e0000);u(0x1e0000,0xc37f90);u(0x1e0004,0x1e1000);u(0x1e0008,a.thing);
        u(0x1e1008,0x1e2000);u(0x1e2000,0x1e3000);u(0x1e3004,2);u(0x1e3008,0x1e4000);u(0x1e4000,0);u(0x1e4008,2);u(0xc37f98,0x71d3f0);
        u(a.thing+0x37c,0x210000);u(0x210008,a.thing);u(0x210024,0x220000);u(0x210028,0x220004);u(0x220000,0x230000);
        u(0x230000,0xc3a6e0);u(0xc3a704,0x6dbe80);u(0xc3a708,0x6f88e0);u(0x230014,0);u(0x230094,0x240000);u(0x240000,0x250000);
        u(0x250000,0xc2e324);u(0x250004,0x260000);u(0x250008,0x230000);u(0x25000c,a.object_id);u(0x25001c,3);u(0x250024,0x7fffffff);u(0x250064,0x290000);
        u(0x260000,0xc37534);u(0x260004,0x270000);u(0x270000,0x280000);u(0x280000,0x94d4d96e);u(0x280004,0x447ea26e);
        f(0x270004,150);const uint8_t getter[]={0x8b,0x41,0x04,0xd9,0x40,0x04,0xc3};
        for(unsigned i=0;i<sizeof(getter);i++)data[0x6dc370+i]=getter[i];
        u(0x290000,0xc1fc50);u(0x290004,0x2a0000);u(0x290024,a.thing);u(0x290080,0x250000);
        u(0x2a0000,0xc1fd18);u(0x2a0018,0x290000);u(0x2a0020,0x250000);
    }
    void advance(){u(native().logic+0x50,++frame);ms+=50;}
    uint32_t frame=100;
};
struct WeaponReview:nc::WeaponPolicy {
    bool allowed=true;
    float reviewed_range(const rt::Binding& b,uint32_t type,uint32_t asset)const override{
        return allowed&&b==binding()&&type==0x19ab11af&&asset==0x447ea26e?150.0f:0;
    }
};
struct Witness:rt::CommandWitness {
    bool stop=false,move=false,installed=true;uint32_t epoch=0;
    bool installed_and_originals_verified()const override{return installed;}
    uint32_t foreign_epoch()const override{return epoch;}
    bool normal_move_owned()const override{return move;}bool normal_stop_owned()const override{return stop;}
    void begin(rt::Action,rt::Point,uint32_t)override{}void end(rt::Action)override{}
    bool independent_quiescence_verified()const override{return true;}
};
struct Calls:rt::NativeCalls {
    NativeBytes& m;Witness& w;uint32_t calls=0;
    Calls(NativeBytes& bytes,Witness& witness):m(bytes),w(witness){}
    rt::Delivery call(rt::Action action,const rt::Actor& a,const rt::NativeBinding& n,rt::Point p,uint32_t stance)override{
        calls++;
        switch(action){
        case rt::Action::Borrow:m.u(a.thing+0x414,n.script_team);break;
        case rt::Action::TransferBack:m.u(a.thing+0x414,n.default_team);break;
        case rt::Action::HoldStance:case rt::Action::RestoreStance:m.u(0x1e0038,stance);break;
        case rt::Action::Move:m.put(a.thing+0x38,p);w.move=true;w.stop=false;break;
        case rt::Action::Stop:m.u(0x1d1000,0xc551a0);m.u(0x1d1004,94);m.u(a.update+0x50,1);w.stop=true;break;
        }
        return rt::Delivery::Sent;
    }
};
struct Surface:rt::SurfacePoints {bool contains(const rt::Binding& b,rt::Point p)const override{return b==binding()&&p==rt::Point{40,0,0};}};
struct Execution:nc::Execution {
    nc::TargetReader& targets;nc::WeaponReader& weapons;nc::Target registered{};nc::NativeAdmission* gate=nullptr;
    uint32_t sdk_simulations=0;Execution(nc::TargetReader& t,nc::WeaponReader& w):targets(t),weapons(w){}
    nc::CombatFacts facts(const rt::Sample& s,const rt::Id& key)override{
        nc::CombatFacts f;if(key==registered.key)f.target=targets.sample(registered);f.weapon=weapons.sample(s.actor).facts;return f;
    }
    bool independent_attack_admission(const nc::Lease& l,const nc::Intent& i,const nc::Observation&)override{return gate&&gate->prepare(l,i,registered);}
    nc::AttackAcknowledgement attack_once(const nc::Lease& l,const nc::Intent& i,const nc::Target& t)override{
        nc::AttackAcknowledgement a;a.delivery=rt::Delivery::NotSent;
        if(!gate||!gate->permit(l,i,t,rt::AttackBoundary::Facade))return a;
        ++sdk_simulations;return a; // Explicitly no native observer/SDK call.
    }
    void mark_control_unknown(const nc::Intent&,const char*)override{}
    void event(const nc::Result&,const char*,const nc::Observation&,const nc::Withdrawal*)override{}
};
struct Fixture {
    NativeBytes m;Witness witness;Calls calls{m,witness};Surface surface;rt::Incarnations births;Policy policy;WeaponReview weapon_policy;
    nc::TargetRegistry registry{binding()};nc::TargetReader targets{binding(),native(),m,policy,registry};nc::WeaponReader weapons{binding(),native(),m,weapon_policy};
    Execution execution{targets,weapons};rt::Actor actor{};std::unique_ptr<rt::MemoryIO> movement;std::unique_ptr<nc::Owner> owner;std::unique_ptr<nc::NativeAdmission> gate;
    Fixture(){
        auto first=own_actor();first.born_frame=0;first.generation=0;
        rt::MemoryIO birth(binding(),native(),first,births,m,calls,witness,surface,{});auto a=birth.birth_observation(),b=birth.birth_observation();
        CHECK(a.identity&&a.grounded&&a.live_list_member);
        rt::PaidBirth receipt{id(60),id(61),1,first.object_id,first.thing,first.owner,first.type_hash,100,99,85,85,true,true,true};
        actor=births.register_paid_birth(receipt,a,b);movement=std::make_unique<rt::MemoryIO>(binding(),native(),actor,births,m,calls,witness,surface,[](const rt::Event&){});
        execution.registered=registry.admit(targets.observe_candidate(candidate()));owner=std::make_unique<nc::Owner>(binding(),*movement,execution,0);
        gate=std::make_unique<nc::NativeAdmission>(binding(),*owner,*movement,m,targets,weapons);execution.gate=gate.get();
    }
    rt::Command command(uint32_t seq,rt::Operation op){rt::Command c;c.command=id(100+seq);c.task=id(10);c.lease=id(11);c.sequence=seq;c.actor=actor;c.operation=op;
        c.expires_frame=800;c.lease_deadline_frame=800;c.expires_monotonic_ms=70000;if(op==rt::Operation::MoveHold){c.target={40,0,0};c.hold_frames=700;}return c;}
    nc::Intent intent(){nc::Intent i;i.command=id(103);i.task=id(10);i.lease=id(11);i.sequence=3;i.actor=actor;i.target_key=execution.registered.key;i.expires_frame=500;i.lease_deadline_frame=800;i.expires_monotonic_ms=20000;return i;}
    void tick(){m.advance();owner->tick();}
    void approach(){CHECK(owner->submit(command(1,rt::Operation::Reserve)).accepted);
        for(unsigned n=0;n<25&&owner->movement_status().phase!=rt::Phase::Ready;n++)tick();
        CHECK(owner->movement_status().phase==rt::Phase::Ready);CHECK(owner->submit(command(2,rt::Operation::MoveHold)).accepted);
        for(unsigned n=0;n<25&&owner->movement_status().phase!=rt::Phase::Holding;n++)tick();
        CHECK(owner->movement_status().phase==rt::Phase::Holding);}
    void admit(){approach();CHECK(owner->submit(intent(),command(4,rt::Operation::ReturnHome)).accepted);}
    bool permit(rt::AttackBoundary b=rt::AttackBoundary::Facade){return gate->permit(owner->original_lease_snapshot(),intent(),execution.registered,b);}
};
static void weapon_exact_native_identity_and_ready_are_paired(){
    Fixture f;auto w=f.weapons.sample(f.actor);CHECK(w.facts.identity_verified&&w.facts.ready&&w.facts.ammo==3&&w.entry==0x250000&&w.request_limit==0x7fffffff);
    CHECK(w.facts.range==150&&w.range_words[0]==0x43160000&&w.range_words[1]==0);
    // The current request counter is an observation, never finite-shot proof.
    f.m.u(0x25001c,0);w=f.weapons.sample(f.actor);CHECK(w.facts.identity_verified&&!w.facts.ready);
    f.m.u(0x25001c,3);f.m.b(0x250060,1);CHECK(!f.weapons.sample(f.actor).facts.ready);
}
static void source_range_cannot_replace_missing_or_changed_native_range(){
    for(float value:{0.0f,-1.0f,149.0f,151.0f,std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity()}){
        Fixture f;f.m.f(0x270004,value);CHECK(!f.weapons.sample(f.actor).facts.identity_verified);
    }
    Fixture missing;missing.m.data.erase(0x270004);CHECK(!missing.weapons.sample(missing.actor).facts.identity_verified);
    Fixture changed;changed.m.data[0x6dc370]=0xe9;CHECK(!changed.weapons.sample(changed.actor).facts.identity_verified);
}
static void unexpected_minimum_or_height_bonus_and_torn_range_deny(){
    for(auto address:{0x270008u,0x27000cu,0x270010u,0x270014u}){
        Fixture f;f.m.f(address,1);CHECK(!f.weapons.sample(f.actor).facts.identity_verified);
    }
    Fixture torn;torn.m.before_read=[&](uint32_t p,uint32_t count){if(p==0x270004&&count==2)torn.m.f(p,140);};
    CHECK(!torn.weapons.sample(torn.actor).facts.identity_verified);
}
static void sdk_boundary_cannot_use_source_range_after_native_schema_changes(){
    Fixture f;f.admit();f.m.f(0x270004,80);CHECK(!f.permit()&&f.execution.sdk_simulations==0);
    f.m.f(0x270004,150);CHECK(f.permit());f.m.f(0x270008,50);CHECK(!f.permit()&&f.execution.sdk_simulations==0);
}
static void weapon_read_failures_policy_and_reverse_links_deny(){
    for(auto address:{0x25000cu,0x290024u,0x290080u,0x2a0018u,0x2a0020u,0x280004u,0x230014u}){
        Fixture f;f.m.u(address,0xbad);CHECK(!f.weapons.sample(f.actor).facts.identity_verified);
    }
    Fixture f;f.weapon_policy.allowed=false;CHECK(!f.weapons.sample(f.actor).facts.identity_verified);
    f.weapon_policy.allowed=true;f.m.data.erase(0x250024);CHECK(!f.weapons.sample(f.actor).facts.identity_verified);
}
static void weapon_changes_between_reads_and_clock_regression_deny(){
    Fixture f;f.m.before_read=[&](uint32_t p,uint32_t count){if(p==0x25001c&&count==2)f.m.u(p,2);};
    CHECK(!f.weapons.sample(f.actor).facts.identity_verified);
    Fixture g;g.m.before_read=[&](uint32_t p,uint32_t count){if(p==0x25001c&&count==2)g.m.ms=999;};
    CHECK(!g.weapons.sample(g.actor).facts.identity_verified);
}
static void sdk_boundary_requires_the_actual_owner_accepted_attack(){
    Fixture f;CHECK(!f.permit());f.approach();CHECK(f.gate->prepare(f.owner->original_lease_snapshot(),f.intent(),f.execution.registered));CHECK(!f.permit());
    CHECK(f.owner->submit(f.intent(),f.command(4,rt::Operation::ReturnHome)).accepted);CHECK(f.permit());CHECK(f.permit(rt::AttackBoundary::PrivateDelivery));
    auto lease=f.owner->original_lease_snapshot();auto forged=f.intent();forged.command=id(999);CHECK(!f.gate->permit(lease,forged,f.execution.registered,rt::AttackBoundary::Facade));
    lease.home.x++;CHECK(!f.gate->permit(lease,f.intent(),f.execution.registered,rt::AttackBoundary::Facade));CHECK(f.execution.sdk_simulations==0);
}
static void stop_invalidates_authority_before_the_next_tick(){Fixture f;f.admit();CHECK(f.permit());f.owner->request_stop();CHECK(!f.permit()&&!f.permit(rt::AttackBoundary::PrivateDelivery));CHECK(f.execution.sdk_simulations==0);}
static void sdk_boundary_rereads_target_visibility_and_weapon(){
    {Fixture f;f.admit();f.m.h(0x130034+10,0);CHECK(!f.permit());f.m.h(0x130034+10,1);CHECK(!f.permit());}
    {Fixture f;f.admit();f.m.u(0x25001c,0);CHECK(!f.permit());}
    {Fixture f;f.admit();f.m.u(0x2a0000,0xc1fde8);f.m.u(0x2a0004,2);CHECK(!f.permit());}
    {Fixture f;f.admit();f.m.f(target().thing+0x38,1000);CHECK(!f.permit());}
}
static void sdk_boundary_rechecks_original_clocks_control_and_identity(){
    for(unsigned mode=0;mode<8;mode++){
        Fixture f;f.admit();switch(mode){case 0:f.m.tid++;break;case 1:f.m.ms=20000;break;case 2:f.m.u(native().logic+0x50,800);break;
        case 3:f.m.u(native().logic+0x15c,1);break;case 4:f.m.u(f.actor.update+0x50,2);break;case 5:f.witness.epoch++;break;
        case 6:f.m.u(f.actor.thing+0x414,native().default_team);break;case 7:f.m.u(f.actor.thing+4,0x2b0000);break;}
        CHECK(!f.permit()&&f.execution.sdk_simulations==0);
    }
}
static void final_reread_changes_refuse_without_an_sdk_attempt(){
    Fixture f;f.admit();f.m.calls.clear();f.m.before_read=[&](uint32_t p,uint32_t count){if(p==0x25001c&&count==2)f.witness.epoch++;};CHECK(!f.permit());
    Fixture g;g.admit();g.m.calls.clear();g.m.before_read=[&](uint32_t p,uint32_t count){if(p==0x25001c&&count==2)g.m.ms=20000;};CHECK(!g.permit());
    CHECK(f.execution.sdk_simulations==0&&g.execution.sdk_simulations==0);
}
static void unreviewed_weapon_diagnostic_never_becomes_an_executable_fact(){
    Fixture f;f.m.u(0x280004,0x41872ecc);auto bytes=f.m.data;nc::WeaponReadDiagnostic d;
    auto w=f.weapons.sample(f.actor,&d);
    CHECK(!w.facts.identity_verified&&!w.facts.ready&&d.failure==nc::WeaponReadFailure::RangePolicy&&d.pass==1);
    CHECK(d.observed.asset==0x41872ecc&&d.expected_range==0&&!d.observed.facts.identity_verified&&!d.observed.facts.ready);
    CHECK(f.m.data==bytes&&f.execution.sdk_simulations==0);
}
static void state_backpointer_failures_report_the_exact_failed_comparison(){
    const std::pair<uint32_t,nc::WeaponReadFailure> cases[]={
        {0x290024,nc::WeaponReadFailure::StateMachineActor},{0x290080,nc::WeaponReadFailure::StateMachineEntry},
        {0x2a0018,nc::WeaponReadFailure::StateOwner},{0x2a0020,nc::WeaponReadFailure::StateEntry}};
    for(const auto& c:cases){Fixture f;f.m.u(c.first,0xdead);nc::WeaponReadDiagnostic d;
        CHECK(!f.weapons.sample(f.actor,&d).facts.identity_verified&&d.failure==c.second&&d.last_address==c.first&&d.last_value==0xdead);
        CHECK(d.pass==1&&d.observed.entry==0x250000&&!d.observed.facts.identity_verified);}
}
static void torn_and_missing_reads_remain_refused_with_diagnostic_evidence(){
    Fixture f;f.m.before_read=[&](uint32_t p,uint32_t count){if(p==0x25001c&&count==2)f.m.u(p,2);};nc::WeaponReadDiagnostic d;
    CHECK(!f.weapons.sample(f.actor,&d).facts.identity_verified&&d.failure==nc::WeaponReadFailure::PairChanged&&d.pass==2&&d.observed.ammo==2);
    Fixture g;g.m.data.erase(0x250024);CHECK(!g.weapons.sample(g.actor,&d).facts.identity_verified);
    CHECK(d.failure==nc::WeaponReadFailure::UnreadableWord&&d.unreadable_address==0x250024&&!d.observed.facts.identity_verified);
}
static void successful_sampling_clears_old_failure_and_diagnostics_cannot_authorize(){
    Fixture f;nc::WeaponReadDiagnostic d;f.m.u(0x290080,0xdead);CHECK(!f.weapons.sample(f.actor,&d).facts.identity_verified);
    f.m.u(0x290080,0x250000);CHECK(f.weapons.sample(f.actor,&d).facts.ready&&d.failure==nc::WeaponReadFailure::None&&d.pass==0&&d.observed.entry==0);
    f.admit();f.m.u(0x2a0020,0xdead);CHECK(!f.weapons.sample(f.actor,&d).facts.identity_verified&&!f.permit());
    CHECK(!d.observed.facts.identity_verified&&f.execution.sdk_simulations==0);
}
int main(){try{
    weapon_exact_native_identity_and_ready_are_paired();weapon_read_failures_policy_and_reverse_links_deny();weapon_changes_between_reads_and_clock_regression_deny();
    sdk_boundary_requires_the_actual_owner_accepted_attack();stop_invalidates_authority_before_the_next_tick();sdk_boundary_rereads_target_visibility_and_weapon();
    sdk_boundary_rechecks_original_clocks_control_and_identity();final_reread_changes_refuse_without_an_sdk_attempt();
    source_range_cannot_replace_missing_or_changed_native_range();unexpected_minimum_or_height_bonus_and_torn_range_deny();sdk_boundary_cannot_use_source_range_after_native_schema_changes();
    unreviewed_weapon_diagnostic_never_becomes_an_executable_fact();state_backpointer_failures_report_the_exact_failed_comparison();
    torn_and_missing_reads_remain_refused_with_diagnostic_evidence();successful_sampling_clears_old_failure_and_diagnostics_cannot_authorize();
    std::cout<<"15 native admission/weapon groups passed; explicit fake byte memory and SDK, no field authority\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
