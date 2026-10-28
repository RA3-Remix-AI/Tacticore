#include "near_target.h"
#include <string>
#include <functional>
#include <iostream>
#include <map>
#include <stdexcept>
namespace rt=tacticore::runtime;namespace nc=rt::near_combat;
#define CHECK(x) do{if(!(x))throw std::runtime_error(std::string(__func__)+":"+std::to_string(__LINE__)+":"+#x);}while(0)
static rt::Id id(uint32_t n){return {n,2,3,4};}
static rt::Binding binding(){rt::Binding b;b.session=id(1);b.commander=id(2);b.host=id(3);b.binding_hash[0]=4;b.player=3;b.pid=10;b.thread=20;b.process_start=123;return b;}
static rt::NativeBinding native(){return {0x10000,0x20000,0x30000,0x40000,1,0x50000,0x60000,0x70000};}
static nc::Target target(){return {id(50),77,0x90000,0xa0000,0xb0000,0xc0000,0x19ab11af,95,1};}
struct Memory:rt::Memory {
    std::map<uint32_t,uint8_t> data;std::map<uint32_t,uint32_t> calls;
    std::function<void(uint32_t,uint32_t)> before_read;
    template<class T>void put(uint32_t p,const T& v){auto b=reinterpret_cast<const uint8_t*>(&v);for(unsigned i=0;i<sizeof(T);i++)data[p+i]=b[i];}
    void u(uint32_t p,uint32_t v){put(p,v);}void f(uint32_t p,float v){put(p,v);}void h(uint32_t p,uint16_t v){put(p,v);}void b(uint32_t p,uint8_t v){put(p,v);}
    bool read(uint32_t p,void* output,uint32_t count)override{
        auto n=++calls[p];if(before_read)before_read(p,n);
        for(uint32_t i=0;i<count;i++){auto it=data.find(p+i);if(it==data.end())return false;static_cast<uint8_t*>(output)[i]=it->second;}return true;
    }
    rt::Binding current_binding()override{return binding();}
    uint32_t thread()override{return 20;}
    uint64_t monotonic_ms()override{return 1000;}
    Memory(){
        auto n=native();auto t=target();u(0xcd8ce4,n.logic);u(n.logic,0xbeb630);u(n.logic+0x50,100);u(n.logic+0x15c,0);u(n.logic+0xb4,t.thing);
        u(n.owner,0xc5bce0);u(n.owner+0x20,3);u(n.owner+0x10,n.player_template);u(n.owner+0x90,n.ai);
        u(n.ai,0xc60f60);u(n.ai+8,n.owner);u(n.ai+0x8b0,n.personality);u(n.personality+0x18,1);
        u(t.thing,0xc4db60);u(t.thing+0xdc,t.object_id);u(t.thing+4,t.template_ptr);u(t.template_ptr+8,t.type_hash);
        u(t.thing+0x374,t.update);u(t.update,0xc48670);u(t.update+8,t.thing);u(t.update+0x24,0xc48528);
        u(t.thing+0x418,t.owner);u(t.owner,0xc5bce0);u(t.owner+0x20,4);u(t.thing+0x7c,0);
        u(t.thing+0x33c,0xd0000);f(0xd0004,120);f(t.thing+0x5c,0);put(t.thing+0x38,rt::Point{50,50,0});
        u(t.thing+0x238,0);u(t.thing+0x48,4);for(unsigned i=0;i<7;i++)u(t.thing+0x80+4*i,0);u(t.thing+0xc8,0);
        u(n.owner+0xfc,0x140000);u(0x140010,1);u(0x140008,0x150000);u(0x14000c,8);u(0x150010,0x160000);
        u(0x160000,4);u(0x160004,0);u(0x160008,0);
        u(0xce2fa0,0x110000);u(0x110000,0xc6aefc);u(0x110028,0x120000);f(0x120004,0);f(0x120008,0);f(0x120038,.01f);
        u(0x12003c,2);u(0x120040,2);u(0x120044,0x130000);u(0xd074a4,1);
        for(unsigned i=0;i<4;i++){auto cell=0x130000+i*0x34;b(cell+0x32,0);h(cell+4+2*3,1);}
        u(t.thing+0x9c,0xe0000);u(0xe0000,0x120000);b(0xe00f8,0);b(0xe00f9,0);u(0xe001c,0xf0000);u(0xe0020,2);
        u(0xf0000,0x130000);u(0xf0010,0x130034);
    }
};
struct Policy:nc::TemplatePolicy {bool admitted=true;bool reviewed(const rt::Binding& b,uint32_t tpl,uint32_t hash)const override{return admitted&&b==binding()&&tpl==target().template_ptr&&hash==0x19ab11af;}};
static nc::ContactCandidate candidate(){auto t=target();return {t.key,t.object_id,t.thing,t.template_ptr,t.update,t.owner,t.type_hash};}
static nc::TargetSample sample(Memory& m,const Policy& p){
    nc::TargetRegistry registry(binding());nc::TargetReader r(binding(),native(),m,p,registry);auto pair=r.observe_candidate(candidate());
    if(!pair.valid())return {};
    auto registered=registry.admit(pair);return r.sample(registered);
}
static void native_footprint_pair_and_default_policy(){
    Memory m;Policy p;auto s=sample(m,p);CHECK(s.visible&&s.visibility_complete&&s.enemy&&s.live&&s.grounded&&s.hp==120&&s.xyz.x==50);
    nc::TemplatePolicy denied;nc::TargetRegistry registry(binding());nc::TargetReader r(binding(),native(),m,denied,registry);
    CHECK(!r.observe_candidate(candidate()).valid());CHECK(!r.sample(target()).identity_verified);
}
static void center_clear_does_not_grant_full_footprint(){
    Memory m;Policy p;m.h(0x130034+10,0);auto s=sample(m,p);CHECK(!s.visible&&!s.visibility_complete&&s.hp==0&&s.xyz.x==0);
    m.h(0x130034+10,1);m.b(0xe00f9,1);CHECK(!sample(m,p).visible);
}
static void observer_counters_and_native_fallback_never_leak(){
    Memory m;Policy p;m.h(0x130000+10,0);m.h(0x130000+8,1);CHECK(!sample(m,p).visible);
    m.h(0x130000+10,0xffff);for(uint32_t fallback:{0u,3u,2u}){m.u(0xd074a4,fallback);CHECK(!sample(m,p).visible);}
    m.u(0xd074a4,1);CHECK(sample(m,p).visible);
}
static void active_or_intrinsic_invisibility_is_denied(){
    Memory m;Policy p;m.u(target().thing+0xc8,1u<<11);CHECK(!sample(m,p).visible);
    m.u(target().thing+0xc8,1u<<12);CHECK(!sample(m,p).visible);
    m.u(target().thing+0xc8,0);p.admitted=false;CHECK(!sample(m,p).visible);
}
static void target_reuse_container_unknown_class_and_non_enemy_denied(){
    for(unsigned mode=0;mode<6;mode++){
        Memory m;Policy p;switch(mode){case 0:m.u(target().thing+4,0xa1000);break;case 1:m.u(target().thing+0x238,0x999);break;
        case 2:m.u(0x160004,2);break;case 3:m.u(target().owner+0x20,3);break;
        case 4:m.u(target().template_ptr+8,0xbad);break;case 5:m.f(0xd0004,std::numeric_limits<float>::quiet_NaN());break;}
        CHECK(!sample(m,p).visible);
    }
}
static void changing_frame_hp_or_grid_denies_paired_result(){
    for(unsigned mode=0;mode<3;mode++){
        Memory m;Policy p;m.before_read=[&](uint32_t address,uint32_t count){
            if(mode==0&&address==native().logic+0x50&&count==2)m.u(address,101);
            if(mode==1&&address==0xd0004&&count==2)m.f(address,114);
            if(mode==2&&address==0x120044&&count==2)m.u(address,0x131000);
        };CHECK(!sample(m,p).visible);
    }
}
static void corrupt_list_footprint_or_paused_game_denied(){
    for(unsigned mode=0;mode<5;mode++){
        Memory m;Policy p;switch(mode){case 0:m.u(target().thing+0x7c,target().thing);break;
        case 1:m.u(0xf0010,0x130001);break;case 2:m.u(0xe0020,4097);break;case 3:m.b(0xe00f8,1);break;case 4:m.u(native().logic+0x15c,1);break;}
        CHECK(!sample(m,p).visible);
    }
}
static void registry_refuses_unsealed_pairs_forged_generations_and_reused_keys(){
    Memory m;Policy p;nc::TargetRegistry registry(binding());nc::TargetReader r(binding(),native(),m,p,registry);
    bool refused=false;try{registry.admit(nc::VisiblePair{});}catch(const std::invalid_argument&){refused=true;}CHECK(refused);
    auto pair=r.observe_candidate(candidate());CHECK(pair.valid());auto t=registry.admit(pair);CHECK(t.incarnation==1&&t.observed_frame==100);
    nc::Target resolved{};CHECK(registry.resolve(binding(),t.key,resolved)&&resolved==t);
    auto wrong=binding();wrong.host[0]++;CHECK(!registry.resolve(wrong,t.key,resolved)&&!rt::nonzero(resolved.key));
    auto forged=t;forged.incarnation++;CHECK(!r.sample(forged).visible);CHECK(r.sample(t).visible);
    refused=false;try{registry.admit(pair);}catch(const std::invalid_argument&){refused=true;}CHECK(refused);
}
static void lost_visibility_revokes_old_contact_and_fresh_pair_mints_new_handle(){
    Memory m;Policy p;nc::TargetRegistry registry(binding());nc::TargetReader r(binding(),native(),m,p,registry);
    auto t=registry.admit(r.observe_candidate(candidate()));m.h(0x130034+10,0);CHECK(!r.sample(t).visible);
    nc::Target resolved{};CHECK(!registry.resolve(binding(),t.key,resolved)&&!rt::nonzero(resolved.key));
    m.h(0x130034+10,1);CHECK(!r.sample(t).visible);
    auto c=candidate();c.key=id(51);auto fresh=registry.admit(r.observe_candidate(c));CHECK(fresh.incarnation==2&&r.sample(fresh).visible);
    CHECK(!registry.current(binding(),t));CHECK(!r.sample(t).visible);
}
static void object_id_reuse_at_another_address_needs_a_new_identity_audit(){
    Memory m;Policy p;nc::TargetRegistry registry(binding());nc::TargetReader r(binding(),native(),m,p,registry);
    auto t=registry.admit(r.observe_candidate(candidate()));registry.retire(t);
    auto c=candidate();c.key=id(52);c.thing=0x98000;
    for(uint32_t i=0;i<0x420;i++){auto it=m.data.find(target().thing+i);if(it!=m.data.end())m.data[c.thing+i]=it->second;}
    m.u(native().logic+0xb4,c.thing);m.u(target().update+8,c.thing);
    auto pair=r.observe_candidate(c);CHECK(pair.valid());
    bool refused=false;try{registry.admit(pair);}catch(const std::invalid_argument&){refused=true;}CHECK(refused);
}
static void registry_capacity_never_evicts_or_reuses_old_handles(){
    Memory m;Policy p;nc::TargetRegistry registry(binding(),2);nc::TargetReader r(binding(),native(),m,p,registry);
    auto t=registry.admit(r.observe_candidate(candidate()));registry.retire(t);
    auto c=candidate();c.key=id(51);auto second=registry.admit(r.observe_candidate(c));registry.retire(second);
    c.key=id(52);bool refused=false;try{registry.admit(r.observe_candidate(c));}catch(const std::invalid_argument&){refused=true;}
    CHECK(refused&&!r.sample(t).visible&&!r.sample(second).visible);
    for(size_t capacity:{size_t(0),size_t(1025)}){refused=false;try{nc::TargetRegistry invalid(binding(),capacity);}catch(const std::invalid_argument&){refused=true;}CHECK(refused);}
}
struct SourceReviewedFlak:Policy {
    bool reviewed(const rt::Binding& b,uint32_t tpl,uint32_t hash)const override{return admitted&&b==binding()&&tpl==target().template_ptr&&(hash==0x19ab11af||hash==0x2c358c61);}
};
struct ExplicitDiagnosticFlak:SourceReviewedFlak {
    bool target_class_supported(const rt::Binding& b,uint32_t hash)const override{return b==binding()&&(hash==0x19ab11af||hash==0x2c358c61);}
};
static void source_review_alone_cannot_expand_the_ordinary_target_class(){
    Memory m;SourceReviewedFlak p;nc::TargetRegistry registry(binding());nc::TargetReader r(binding(),native(),m,p,registry);
    auto c=candidate();c.type_hash=0x2c358c61;m.u(c.template_ptr+8,c.type_hash);CHECK(!r.observe_candidate(c).valid());
    CHECK(p.target_class_supported(binding(),0x19ab11af)&&!p.target_class_supported(binding(),0x2c358c61));
}
static void explicit_diagnostic_class_still_requires_complete_current_footprint(){
    Memory m;ExplicitDiagnosticFlak p;nc::TargetRegistry registry(binding());nc::TargetReader r(binding(),native(),m,p,registry);
    auto c=candidate();c.type_hash=0x2c358c61;m.u(c.template_ptr+8,c.type_hash);auto pair=r.observe_candidate(c);CHECK(pair.valid());
    auto registered=registry.admit(pair);CHECK(r.sample(registered).visible);
    m.h(0x130034+10,0);CHECK(!r.sample(registered).visible);m.h(0x130034+10,1);CHECK(!r.sample(registered).visible);
    CHECK(!p.target_class_supported(rt::Binding{},0x2c358c61)&&!p.target_class_supported(binding(),0xbad));
}
int main(){try{native_footprint_pair_and_default_policy();center_clear_does_not_grant_full_footprint();observer_counters_and_native_fallback_never_leak();
    active_or_intrinsic_invisibility_is_denied();target_reuse_container_unknown_class_and_non_enemy_denied();changing_frame_hp_or_grid_denies_paired_result();
    corrupt_list_footprint_or_paused_game_denied();registry_refuses_unsealed_pairs_forged_generations_and_reused_keys();
    lost_visibility_revokes_old_contact_and_fresh_pair_mints_new_handle();
    object_id_reuse_at_another_address_needs_a_new_identity_audit();
    registry_capacity_never_evicts_or_reuses_old_handles();
    source_review_alone_cannot_expand_the_ordinary_target_class();explicit_diagnostic_class_still_requires_complete_current_footprint();
    std::cout<<"13 native target-reader replay groups passed; fake read-only memory, no SDK or field authority\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
