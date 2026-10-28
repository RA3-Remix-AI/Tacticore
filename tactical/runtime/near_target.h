#pragma once
// Read-only target admission for the near-combat feature under development.
// No SDK call, shroud cache write, observer fallback or weapon authority.
#include "near_combat.h"
#include "memory_io.h"
#include <array>
#include <cstring>
#include <limits>
#include <map>
#include <set>
#include <stdexcept>

namespace tacticore::runtime::near_combat {
struct ContactCandidate {
    Id key{};uint32_t object_id=0,thing=0,template_ptr=0,update=0,owner=0,type_hash=0;
};
class TargetReader;
class VisiblePair {
    Binding binding_{};TargetSample first_{},second_{};bool valid_=false;
    VisiblePair(Binding b,TargetSample a,TargetSample z):binding_(b),first_(a),second_(z),valid_(true){}
    friend class TargetReader;
    friend class TargetRegistry;
public:
    VisiblePair()=default;
    bool valid()const{return valid_;}
};
class TargetRegistry {
    Binding binding_;std::map<Id,Target> records_;std::set<Id> retired_;std::map<uint32_t,Target> objects_;uint64_t next_=1;
    size_t capacity_;
    static bool physical(const Target& a,const Target& b){return a.object_id==b.object_id&&a.thing==b.thing&&a.template_ptr==b.template_ptr
        &&a.update==b.update&&a.owner==b.owner&&a.type_hash==b.type_hash;}
public:
    explicit TargetRegistry(Binding binding,size_t capacity=1024):binding_(binding),capacity_(capacity){
        if(!capacity||capacity>1024)throw std::invalid_argument("target_registry_capacity_invalid");
    }
    Target admit(const VisiblePair& pair){
        const auto& a=pair.first_;const auto& b=pair.second_;
        if(!pair.valid_||!(pair.binding_==binding_)||!a.visible||!b.visible||!a.visibility_complete||!b.visibility_complete
            ||!(a.identity==b.identity)||!(a.xyz==b.xyz)||a.hp!=b.hp||a.visibility_frame!=b.visibility_frame
            ||a.identity.incarnation||!a.identity.observed_frame||!nonzero(a.identity.key))throw std::invalid_argument("visible_target_pair_required");
        const auto& t=a.identity;
        if(records_.count(t.key))throw std::invalid_argument("target_key_never_reused");
        if(records_.size()>=capacity_)throw std::invalid_argument("target_registry_full_no_eviction");
        auto old=objects_.find(t.object_id);
        if(old!=objects_.end()&&(!retired_.count(old->second.key)||!physical(old->second,t)))throw std::invalid_argument("target_id_reuse_requires_identity_audit");
        for(const auto& row:objects_)if(row.first!=t.object_id&&row.second.thing==t.thing)throw std::invalid_argument("target_address_reuse_requires_identity_audit");
        Target registered=t;registered.incarnation=next_++;
        records_.emplace(registered.key,registered);objects_[registered.object_id]=registered;return registered;
    }
    bool current(const Binding& b,const Target& t)const{
        auto found=records_.find(t.key);return b==binding_&&found!=records_.end()&&!retired_.count(t.key)&&found->second==t;
    }
    bool resolve(const Binding& b,const Id& key,Target& output)const{
        output={};auto found=records_.find(key);
        if(!(b==binding_)||found==records_.end()||retired_.count(key))return false;
        output=found->second;return true;
    }
    void retire(const Target& t){auto found=records_.find(t.key);if(found!=records_.end()&&found->second==t)retired_.insert(t.key);}
};
class TemplatePolicy {
public:
    virtual ~TemplatePolicy()=default;
    // The ordinary near-combat policy retains its original Conscript scope.
    // A separately verified passive diagnostic may explicitly support more.
    virtual bool target_class_supported(const Binding&,uint32_t hash)const{return hash==0x19ab11af;}
    // A trusted exact-build/source audit must implement this policy. Runtime
    // invisibility flags alone cannot prove absence of intrinsic stealth.
    virtual bool reviewed(const Binding&,uint32_t,uint32_t)const{return false;}
};
class TargetReader {
    Binding binding_;NativeBinding native_;Memory& memory_;const TemplatePolicy& policy_;TargetRegistry& registry_;bool okay_=true;
    uint32_t word(uint32_t p){uint32_t n=0;if(!p||!memory_.read(p,&n,4))okay_=false;return n;}
    uint16_t half(uint32_t p){uint16_t n=0;if(!p||!memory_.read(p,&n,2))okay_=false;return n;}
    uint8_t byte(uint32_t p){uint8_t n=0;if(!p||!memory_.read(p,&n,1))okay_=false;return n;}
    float scalar(uint32_t p){float n=0;if(!p||!memory_.read(p,&n,4))okay_=false;return n;}
    Point point(uint32_t p){Point n{};if(!p||!memory_.read(p,&n,12))okay_=false;return n;}
    static bool span(uint32_t p,uint64_t bytes){return p>=0x10000&&p%4==0&&bytes>0&&uint64_t(p)+bytes<=uint64_t(std::numeric_limits<uint32_t>::max());}
    bool root(){
        return memory_.current_binding()==binding_&&memory_.thread()==binding_.thread&&binding_.player<20
            &&word(0xcd8ce4)==native_.logic&&word(native_.logic)==0xbeb630
            &&word(native_.owner)==0xc5bce0&&word(native_.owner+0x20)==binding_.player
            &&word(native_.owner+0x10)==native_.player_template&&word(native_.owner+0x90)==native_.ai
            &&word(native_.ai)==0xc60f60&&word(native_.ai+8)==native_.owner
            &&word(native_.ai+0x8b0)==native_.personality&&word(native_.personality+0x18)==native_.personality_id;
    }
    bool enemy(uint32_t owner){
        if(owner==native_.owner||word(owner)!=0xc5bce0)return false;
        auto index=word(owner+0x20);if(index>=20||index==binding_.player)return false;
        auto container=word(native_.owner+0xfc);if(!container||!word(container+0x10))return false;
        auto buckets=word(container+8),count=word(container+0xc);
        if(!count||count>4096||!span(buckets,uint64_t(count)*4))return false;
        auto node=word(buckets+(index%count)*4);std::set<uint32_t> seen;
        while(node){
            if(!span(node,12)||seen.size()>=100||!seen.insert(node).second)return false;
            if(word(node)==index)return word(node+4)==0;
            node=word(node+8);
        }
        return false; // Native missing-key fallback is neutral, never enemy.
    }
    bool live(const Target& target){
        auto first=word(native_.logic+0xb4),cursor=first;uint32_t count=0,matches=0;std::set<uint32_t> seen;
        while(cursor){
            if(count++>=20000||!span(cursor,0x420)||!seen.insert(cursor).second||word(cursor)!=0xc4db60)return false;
            if(word(cursor+0xdc)==target.object_id){if(cursor!=target.thing)return false;matches++;}
            cursor=word(cursor+0x7c);
        }
        return matches==1&&count>0&&first==word(native_.logic+0xb4);
    }
    bool clear_cell(uint32_t cell,uint32_t fallback){
        if(byte(cell+0x32))return false;
        auto counter=half(cell+4+2*binding_.player);
        return counter!=0&&(counter!=0xffff||fallback==1);
    }
    bool current_footprint(uint32_t thing,Point xyz){
        auto manager=word(0xce2fa0);if(word(manager)!=0xc6aefc)return false;
        auto impl=word(manager+0x28);float ox=scalar(impl+4),oy=scalar(impl+8),scale=scalar(impl+0x38);
        auto width=word(impl+0x3c),height=word(impl+0x40),cells=word(impl+0x44),fallback=word(0xd074a4);
        if(!std::isfinite(ox)||!std::isfinite(oy)||!std::isfinite(scale)||scale<=0||scale>10||!width||!height
            ||width>4096||height>4096||uint64_t(width)*height>4000000||!span(cells,uint64_t(width)*height*0x34)
            ||(fallback!=0&&fallback!=1&&fallback!=3))return false;
        // Match native float32 subss/mulss and truncation. Bounds precede cast.
        volatile float dx=xyz.x-ox,dy=xyz.y-oy;
        volatile float px=dx*scale,py=dy*scale;
        if(!std::isfinite(px)||!std::isfinite(py)||px<=-2147483648.0f||px>=2147483648.0f||py<=-2147483648.0f||py>=2147483648.0f)return false;
        auto gx=static_cast<int32_t>(px),gy=static_cast<int32_t>(py);
        if(gx<0||gy<0||uint32_t(gx)>=width||uint32_t(gy)>=height)return false;
        if(!clear_cell(cells+(uint32_t(gy)*width+uint32_t(gx))*0x34,fallback))return false;
        auto record=word(thing+0x9c);
        if(!record||word(record)!=impl||byte(record+0xf8)||byte(record+0xf9))return false;
        auto first=word(record+0x1c),count=word(record+0x20);
        if(!count||count>4096||!span(first,uint64_t(count)*16))return false;
        uint32_t total=0;
        for(uint32_t i=0;i<count;i++){
            auto cell=word(first+16*i);if(!cell)continue;
            if(cell<cells||(cell-cells)%0x34||uint64_t(cell-cells)/0x34>=uint64_t(width)*height
                ||!clear_cell(cell,fallback))return false;
            total++;
        }
        return total>0&&word(thing+0x9c)==record&&word(record)==impl&&word(record+0x1c)==first&&word(record+0x20)==count
            &&!byte(record+0xf8)&&!byte(record+0xf9)&&word(0xce2fa0)==manager&&word(manager+0x28)==impl
            &&scalar(impl+4)==ox&&scalar(impl+8)==oy&&scalar(impl+0x38)==scale
            &&word(impl+0x3c)==width&&word(impl+0x40)==height&&word(impl+0x44)==cells&&word(0xd074a4)==fallback;
    }
    bool once(const Target& t,TargetSample& result,bool candidate=false){
        okay_=true;
        if(!nonzero(t.key)||!t.object_id||(!candidate&&(!t.incarnation||!t.observed_frame))
            ||(candidate&&(t.incarnation||t.observed_frame))||!span(t.thing,0x420)
            ||!span(t.template_ptr,12)||!span(t.update,0x30)||!span(t.owner,0x110)||!root())return false;
        auto frame=word(native_.logic+0x50);auto mono=memory_.monotonic_ms();
        if(!frame||frame<t.observed_frame||word(native_.logic+0x15c))return false;
        // Initial diagnostic target scope is one Soviet Conscript, not an
        // implied universal target class or an intrinsic-stealth inference.
        if(!policy_.target_class_supported(binding_,t.type_hash)||word(t.thing)!=0xc4db60||word(t.thing+0xdc)!=t.object_id
            ||word(t.thing+4)!=t.template_ptr||word(t.template_ptr+8)!=t.type_hash||word(t.thing+0x374)!=t.update
            ||word(t.update)!=0xc48670||word(t.update+8)!=t.thing||word(t.update+0x24)!=0xc48528
            ||word(t.thing+0x418)!=t.owner||!policy_.reviewed(binding_,t.template_ptr,t.type_hash)||!enemy(t.owner))return false;
        auto body=word(t.thing+0x33c);if(!span(body,8))return false;
        float hp=scalar(body+4),height=scalar(t.thing+0x5c);auto xyz=point(t.thing+0x38);
        std::array<uint32_t,7> flags{};if(!memory_.read(t.thing+0x80,flags.data(),28))okay_=false;
        if(word(t.thing+0x238)||!(word(t.thing+0x48)&4)||(flags[0]&0x181)||(flags[1]&0x20080000)
            ||(flags[5]&2)||(flags[6]&0x88000)||!std::isfinite(hp)||hp<=0||!std::isfinite(height)||std::fabs(height)>.5f
            ||!finite(xyz)||(word(t.thing+0xc8)&((1u<<11)|(1u<<12)))||!live(t)||!current_footprint(t.thing,xyz))return false;
        if(!root()||word(native_.logic+0x50)!=frame||!okay_||memory_.monotonic_ms()<mono||memory_.monotonic_ms()-mono>250)return false;
        result.identity=t;if(candidate)result.identity.observed_frame=frame;
        result.xyz=xyz;result.hp=hp;result.visibility_frame=frame;result.visibility_monotonic_ms=mono;
        result.identity_verified=result.live=result.grounded=result.enemy=result.visible=result.visibility_complete=true;
        return true;
    }
public:
    TargetReader(Binding binding,NativeBinding native,Memory& memory,const TemplatePolicy& policy,TargetRegistry& registry):binding_(binding),native_(native),memory_(memory),policy_(policy),registry_(registry){}
    VisiblePair observe_candidate(const ContactCandidate& candidate){
        Target t{candidate.key,candidate.object_id,candidate.thing,candidate.template_ptr,candidate.update,candidate.owner,candidate.type_hash,0,0};
        TargetSample a{},b{};
        if(!once(t,a,true)||!once(t,b,true)||!(a.identity==b.identity)||!(a.xyz==b.xyz)||a.hp!=b.hp
            ||a.visibility_frame!=b.visibility_frame||b.visibility_monotonic_ms<a.visibility_monotonic_ms
            ||b.visibility_monotonic_ms-a.visibility_monotonic_ms>250)return {};
        return VisiblePair(binding_,a,b);
    }
    TargetSample sample(const Target& t){
        if(!registry_.current(binding_,t))return {};
        TargetSample a{},b{};
        if(!once(t,a)||!once(t,b)||!(a.identity==b.identity)||!(a.xyz==b.xyz)||a.hp!=b.hp
            ||a.visibility_frame!=b.visibility_frame||b.visibility_monotonic_ms<a.visibility_monotonic_ms
            ||b.visibility_monotonic_ms-a.visibility_monotonic_ms>250){registry_.retire(t);return {};}
        return b;
    }
};
}
