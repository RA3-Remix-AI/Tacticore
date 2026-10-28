#pragma once
// Fresh, paired native weapon facts. This reader never invokes a getter/SDK
// and never changes the selected slot or request limit.
#include "near_combat.h"
#include "memory_io.h"
#include <set>
#include <cstring>

namespace tacticore::runtime::near_combat {
class WeaponPolicy {
public:
    virtual ~WeaponPolicy()=default;
    // Expected asset range, used only to check the independently read native
    // schema value. This policy value is never itself a weapon observation.
    virtual float reviewed_range(const Binding&,uint32_t,uint32_t)const{return 0;}
};
struct WeaponSnapshot {
    uint32_t frame=0,thread=0,container=0,slot=0,index=0,entry=0,template_ptr=0,
        schema=0,header=0,asset=0,ammo=0,request_limit=0,state_machine=0,state=0,
        state_vtable=0,state_id=0,requested=0,flags=0;
    uint64_t monotonic_ms=0;Weapon facts{};
    std::array<uint32_t,5> range_words{};
};
// Diagnostic observations are never executable weapon facts. The same reader
// and the same admission checks produce these failure reasons; no retry or
// alternate selector is attempted when a read is refused.
enum class WeaponReadFailure:uint32_t {
    None=0,BindingOrActor=1,ActorIdentity=2,Container=3,Slot=4,Entry=5,
    RangeGetterOrRead=6,RangePolicy=7,RangeModifiers=8,TemplateVtable=9,
    HeaderType=10,StateMachineVtable=11,StateMachineActor=12,
    StateMachineEntry=13,StateOwner=14,StateEntry=15,Asset=16,Ammo=17,
    FinalIdentity=18,UnreadableWord=19,PairChanged=20,PairClock=21,
    CurrentClock=22,RangeBounds=23
};
struct WeaponReadDiagnostic {
    WeaponReadFailure failure=WeaponReadFailure::None;
    uint32_t pass=0,last_address=0,last_value=0,unreadable_address=0;
    float expected_range=0;WeaponSnapshot observed{};
};
class WeaponReader {
    Binding binding_;NativeBinding native_;Memory& memory_;const WeaponPolicy& policy_;bool okay_=false;
    WeaponReadFailure failure_=WeaponReadFailure::None;
    uint32_t last_address_=0,last_value_=0,unreadable_address_=0;float expected_range_=0;
    uint32_t word(uint32_t p){uint32_t v=0;if(p<0x10000||!memory_.read(p,&v,4)){okay_=false;if(!unreadable_address_)unreadable_address_=p;}last_address_=p;last_value_=v;return v;}
    bool matches(uint32_t address,uint32_t expected,WeaponReadFailure failure){failure_=failure;return word(address)==expected;}
    bool root(){
        return memory_.current_binding()==binding_&&memory_.thread()==binding_.thread
            &&word(0xcd8ce4)==native_.logic&&word(native_.logic)==0xbeb630
            &&word(native_.owner)==0xc5bce0&&word(native_.owner+0x20)==binding_.player
            &&word(native_.owner+0x10)==native_.player_template&&word(native_.owner+0x90)==native_.ai
            &&word(native_.ai)==0xc60f60&&word(native_.ai+8)==native_.owner
            &&word(native_.ai+0x8b0)==native_.personality&&word(native_.personality+0x18)==native_.personality_id;
    }
    bool once(const Actor& a,WeaponSnapshot& s){
        okay_=true;last_address_=last_value_=unreadable_address_=0;expected_range_=0;
        failure_=WeaponReadFailure::BindingOrActor;s={};s.thread=memory_.thread();s.monotonic_ms=memory_.monotonic_ms();
        if(!root()||!a.object_id||!a.thing||!a.template_ptr||!a.update||a.owner!=native_.owner||a.type_hash!=0x19ab11af)return false;
        failure_=WeaponReadFailure::ActorIdentity;
        s.frame=word(native_.logic+0x50);
        if(!s.frame||word(native_.logic+0x15c)||word(a.thing)!=0xc4db60||word(a.thing+0xdc)!=a.object_id
            ||word(a.thing+4)!=a.template_ptr||word(a.template_ptr+8)!=a.type_hash||word(a.thing+0x418)!=a.owner
            ||word(a.thing+0x374)!=a.update||word(a.update)!=0xc48670||word(a.update+8)!=a.thing||word(a.update+0x24)!=0xc48528)return false;
        failure_=WeaponReadFailure::Container;s.container=word(a.thing+0x37c);auto first=word(s.container+0x24),end=word(s.container+0x28);
        if(word(s.container+8)!=a.thing||!first||end<=first||end-first>256||(end-first)%4)return false;
        // Match the native active-slot traversal, not a model-chosen address.
        for(auto cursor=first;cursor<end;cursor+=4){
            failure_=WeaponReadFailure::Slot;
            auto slot=word(cursor),index=word(slot+0x14);
            if(word(slot)!=0xc3a6e0||word(0xc3a704)!=0x6dbe80||word(0xc3a708)!=0x6f88e0||index>5)return false;
            if(index==5)continue;
            auto entry=word(word(slot+0x94)+4*index);if(!entry)continue;
            s.slot=slot;s.index=index;s.entry=entry;break;
        }
        failure_=WeaponReadFailure::Entry;
        if(!s.entry||word(s.entry)!=0xc2e324||word(s.entry+8)!=s.slot||word(s.entry+0xc)!=a.object_id)return false;
        s.template_ptr=word(s.entry+4);s.schema=word(s.template_ptr+4);s.header=word(s.schema);s.asset=word(s.header+4);
        s.ammo=word(s.entry+0x1c);s.request_limit=word(s.entry+0x24);s.state_machine=word(s.entry+0x64);s.state=word(s.state_machine+4);
        s.state_vtable=word(s.state);s.state_id=word(s.state+4);s.flags=word(s.state_machine+0x78);
        uint8_t requested=0xff;if(!memory_.read(s.entry+0x60,&requested,1))okay_=false;s.requested=requested;
        auto expected_range=policy_.reviewed_range(binding_,a.type_hash,s.asset);expected_range_=expected_range;
        // 0x6dc370 is the exact native base-range getter. Mirror its reads;
        // never invoke it. The static audit also verifies its entry-template
        // consumer and the separate minimum/height-bonus field accesses.
        const uint8_t signature[]={0x8b,0x41,0x04,0xd9,0x40,0x04,0xc3};uint8_t actual[sizeof(signature)]{};
        failure_=WeaponReadFailure::RangeGetterOrRead;
        if(!memory_.read(0x6dc370,actual,sizeof(actual))||std::memcmp(signature,actual,sizeof(actual))
            ||!memory_.read(s.schema+4,s.range_words.data(),sizeof(s.range_words)))return false;
        float values[5]{};std::memcpy(values,s.range_words.data(),sizeof(values));auto range=values[0];
        failure_=WeaponReadFailure::RangePolicy;
        if(!std::isfinite(expected_range)||expected_range<=0||expected_range>150||range!=expected_range)return false;
        // This ground AK47 scope excludes minimum-range and height bonuses.
        // An unexpected compiled configuration refuses rather than falling
        // back to the source asset or extrapolating a new effective range.
        failure_=WeaponReadFailure::RangeModifiers;
        for(unsigned i=1;i<5;i++)if(!std::isfinite(values[i])||values[i]!=0)return false;
        if(!matches(s.template_ptr,0xc37534,WeaponReadFailure::TemplateVtable)
            ||!matches(s.header,0x94d4d96e,WeaponReadFailure::HeaderType)
            ||!matches(s.state_machine,0xc1fc50,WeaponReadFailure::StateMachineVtable)
            ||!matches(s.state_machine+0x24,a.thing,WeaponReadFailure::StateMachineActor)
            ||!matches(s.state_machine+0x80,s.entry,WeaponReadFailure::StateMachineEntry)
            ||!matches(s.state+0x18,s.state_machine,WeaponReadFailure::StateOwner)
            ||!matches(s.state+0x20,s.entry,WeaponReadFailure::StateEntry))return false;
        failure_=WeaponReadFailure::RangeBounds;if(!std::isfinite(range)||range<=0||range>150)return false;
        failure_=WeaponReadFailure::Asset;if(s.asset!=0x447ea26e)return false;
        failure_=WeaponReadFailure::Ammo;if(s.ammo>3)return false;
        s.facts.identity_verified=s.facts.ground_target_supported=true;s.facts.ammo=s.ammo;s.facts.range=range;
        s.facts.ready=s.ammo>0&&s.state_vtable==0xc1fd18&&s.state_id==0&&s.requested==0&&!(s.flags&0xffff);
        failure_=WeaponReadFailure::FinalIdentity;
        if(!(root()&&word(native_.logic+0x50)==s.frame&&word(a.thing+0xdc)==a.object_id
            &&word(a.thing+4)==a.template_ptr&&word(a.thing+0x374)==a.update&&word(a.thing+0x418)==a.owner
            &&word(a.thing+0x37c)==s.container&&word(s.entry+4)==s.template_ptr&&word(s.entry+8)==s.slot
            &&word(s.entry+0x64)==s.state_machine&&word(s.state_machine+4)==s.state))return false;
        failure_=WeaponReadFailure::UnreadableWord;if(!okay_)return false;
        failure_=WeaponReadFailure::None;return true;
    }
    static bool equal(const WeaponSnapshot& a,const WeaponSnapshot& b){
        return a.frame==b.frame&&a.thread==b.thread&&a.container==b.container&&a.slot==b.slot&&a.index==b.index
            &&a.entry==b.entry&&a.template_ptr==b.template_ptr&&a.schema==b.schema&&a.header==b.header&&a.asset==b.asset
            &&a.ammo==b.ammo&&a.request_limit==b.request_limit&&a.state_machine==b.state_machine&&a.state==b.state
            &&a.state_vtable==b.state_vtable&&a.state_id==b.state_id&&a.requested==b.requested&&a.flags==b.flags
            &&a.range_words==b.range_words&&a.facts.range==b.facts.range&&a.facts.ready==b.facts.ready;
    }
public:
    WeaponReader(Binding b,NativeBinding n,Memory& m,const WeaponPolicy& p):binding_(b),native_(n),memory_(m),policy_(p){}
    WeaponSnapshot sample(const Actor& a,WeaponReadDiagnostic* diagnostic=nullptr){
        if(diagnostic)*diagnostic={};
        WeaponSnapshot before{},after{};
        auto refused=[&](const WeaponSnapshot& observed,uint32_t pass){
            if(diagnostic){diagnostic->failure=failure_;diagnostic->pass=pass;diagnostic->last_address=last_address_;diagnostic->last_value=last_value_;
                diagnostic->unreadable_address=unreadable_address_;diagnostic->expected_range=expected_range_;diagnostic->observed=observed;diagnostic->observed.facts={};}
            return WeaponSnapshot{};
        };
        if(!once(a,before))return refused(before,1);
        if(!once(a,after))return refused(after,2);
        failure_=WeaponReadFailure::PairChanged;if(!equal(before,after))return refused(after,2);
        failure_=WeaponReadFailure::PairClock;
        if(after.monotonic_ms<before.monotonic_ms||after.monotonic_ms-before.monotonic_ms>250)return refused(after,2);
        auto now=memory_.monotonic_ms();
        failure_=WeaponReadFailure::CurrentClock;if(now<after.monotonic_ms||now-before.monotonic_ms>250)return refused(after,2);
        return after;
    }
};
}
