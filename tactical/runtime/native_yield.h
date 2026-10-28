#pragma once
#include "memory_io.h"
#include <set>
#include <array>
#include <cstring>
#include <algorithm>

namespace tacticore::runtime {
// Trace18 = neighbor words, trace19/20/22 = actor words. These are passive
// snapshots. A label alone cannot grant native authority or prove a return.
namespace yield_words {
enum ActorWord {ASchema,AThing,AUpdate,AId,AOwner,ATeam,AX,AY,AZ,AState,AVtable,APath,ASource,AFlags,AStance,ASlot,AHp,AHeight,AThingVt,AUpdateVt,AFacadeVt,ALinks,ALive,AComplete};
enum NeighborWord {NSchema,NThing,NId,NOwner,NTeam,NHash,NTemplate,NUpdate,NX,NY,NZ,NHp,NHeight,NThingVt,NUpdateVt,NFacadeVt,NTeamOwner,NState,NVtable,NPath,NFlags,NLinks,NGrounded,NComplete};
}
struct YieldSnapshot {
    uint32_t frame=0,yield_neighbor_id=0;bool verified=false;
    std::array<uint32_t,24> actor{},neighbor{},neighbor_physical{};
};
class YieldReader {
    Binding binding_;NativeBinding native_;Actor actor_;Memory& memory_;bool okay_=true;
    uint32_t word(uint32_t p){uint32_t n=0;if(!p||!memory_.read(p,&n,4))okay_=false;return n;}
    uint32_t bits(float f){uint32_t n=0;std::memcpy(&n,&f,4);return n;}
    float scalar(uint32_t p){float f=0;if(!p||!memory_.read(p,&f,4))okay_=false;return f;}
    Point point(uint32_t p){Point xyz{};if(!p||!memory_.read(p,&xyz,12))okay_=false;return xyz;}
    bool root(){return memory_.current_binding()==binding_&&memory_.thread()==binding_.thread
        &&word(0xcd8ce4)==native_.logic&&word(native_.logic)==0xbeb630
        &&word(native_.owner)==0xc5bce0&&word(native_.owner+0x20)==binding_.player
        &&word(native_.owner+0x10)==native_.player_template&&word(native_.owner+0x90)==native_.ai
        &&word(native_.ai)==0xc60f60&&word(native_.ai+8)==native_.owner
        &&word(native_.ai+0x8b0)==native_.personality&&word(native_.personality+0x18)==native_.personality_id;}
    bool ground(uint32_t t,float& hp,float& height,std::array<uint32_t,24>* facts=nullptr){
        auto body=word(t+0x33c);hp=scalar(body+4);height=scalar(t+0x5c);uint32_t f[7]={};
        if(!memory_.read(t+0x80,f,28))okay_=false;
        auto container=word(t+0x238),height_cache=word(t+0x48);
        bool result=container==0&&!(f[0]&0x181)&&!(f[1]&0x20080000)&&!(f[5]&2)&&!(f[6]&0x88000)
            &&(height_cache&4)&&std::isfinite(hp)&&hp>0&&std::isfinite(height)&&std::fabs(height)<=.5f;
        if(facts){auto& r=*facts;r[0]=1;r[1]=t;r[2]=body;r[3]=bits(hp);r[4]=bits(height);r[5]=container;r[6]=height_cache;
            std::copy(f,f+7,r.begin()+7);r[14]=result;r[15]=okay_;}
        return result;
    }
public:
    YieldReader(Binding b,NativeBinding n,Actor a,Memory& m):binding_(b),native_(n),actor_(a),memory_(m){}
    YieldSnapshot capture(uint32_t neighbor){
        using namespace yield_words;YieldSnapshot out;okay_=true;
        out.actor[ASchema]=out.neighbor[NSchema]=1;out.neighbor[NThing]=neighbor;
        if(!root()||neighbor<0x10000||neighbor%4||neighbor==actor_.thing)return out;
        out.frame=word(native_.logic+0x50);auto& a=out.actor;auto& n=out.neighbor;auto t=actor_.thing,u=actor_.update;
        auto xyz=point(t+0x38);auto team=word(t+0x414);auto sm=word(u+0x3c),state=word(sm+4);float hp=0,height=0;
        bool own=word(t)==0xc4db60&&word(t+0xdc)==actor_.object_id&&word(t+4)==actor_.template_ptr
            &&word(actor_.template_ptr+8)==actor_.type_hash&&actor_.type_hash==0x19ab11af
            &&word(t+0x374)==u&&word(t+0x418)==native_.owner&&word(u)==0xc48670&&word(u+0x24)==0xc48528&&word(u+8)==t
            &&team==native_.script_team&&word(word(team+4)+8)==native_.owner&&finite(xyz)&&ground(t,hp,height);
        bool links=word(sm+0x24)==t&&word(state+0x18)==sm;
        auto stance=word(t+0x380);
        own=own&&word(stance)==0xc37f90&&word(stance+8)==t&&links;
        a[AThing]=t;a[AUpdate]=u;a[AId]=actor_.object_id;a[AOwner]=word(t+0x418);a[ATeam]=team;
        a[AX]=bits(xyz.x);a[AY]=bits(xyz.y);a[AZ]=bits(xyz.z);a[AState]=word(state+4);a[AVtable]=word(state);
        a[APath]=word(u+0x150);a[ASource]=word(u+0x50);a[AFlags]=word(sm+0x78);a[AStance]=word(stance+0x38);
        a[ASlot]=word(u+0x310);a[AHp]=bits(hp);a[AHeight]=bits(height);a[AThingVt]=word(t);a[AUpdateVt]=word(u);a[AFacadeVt]=word(u+0x24);a[ALinks]=links;
        out.yield_neighbor_id=word(u+0x1e8);
        n[NOwner]=word(neighbor+0x418);if(n[NOwner]!=native_.owner)return out;
        auto ntpl=word(neighbor+4),nu=word(neighbor+0x374),nsm=word(nu+0x3c),ns=word(nsm+4);auto nxyz=point(neighbor+0x38);
        n[NId]=word(neighbor+0xdc);n[NTeam]=word(neighbor+0x414);n[NHash]=word(ntpl+8);n[NTemplate]=ntpl;n[NUpdate]=nu;
        n[NX]=bits(nxyz.x);n[NY]=bits(nxyz.y);n[NZ]=bits(nxyz.z);
        float nhp=0,nheight=0;n[NGrounded]=ground(neighbor,nhp,nheight,&out.neighbor_physical);n[NHp]=bits(nhp);n[NHeight]=bits(nheight);
        n[NThingVt]=word(neighbor);n[NUpdateVt]=word(nu);n[NFacadeVt]=word(nu+0x24);n[NTeamOwner]=word(word(n[NTeam]+4)+8);
        n[NState]=word(ns+4);n[NVtable]=word(ns);n[NPath]=word(nu+0x150);n[NFlags]=word(nsm+0x78);
        n[NLinks]=word(nu+8)==neighbor&&word(nsm+0x24)==neighbor&&word(ns+0x18)==nsm;
        // The neighbor is provenance for an abort request, never an actor we
        // move or an endpoint. 0x7e2a90 proves Thing+0x48 bit4 validates the
        // cached height at +0x5c. A moving neighbor may lack that cache. Do not
        // call its lazy getter or award ground/endpoint authority from this.
        auto& physical=out.neighbor_physical;
        bool live_source=std::isfinite(nhp)&&nhp>0&&physical[5]==0&&!(physical[7]&0x181)
            &&!(physical[8]&0x20080000)&&!(physical[12]&2)&&!(physical[13]&0x88000);
        physical[16]=live_source;
        bool other=n[NId]&&n[NId]!=actor_.object_id&&n[NTeam]&&n[NTeam]!=native_.script_team&&n[NTeamOwner]==native_.owner
            &&(n[NHash]==0x19ab11af||n[NHash]==0x2c358c61||n[NHash]==0x33026fa1)
            &&n[NThingVt]==0xc4db60&&n[NUpdateVt]==0xc48670&&n[NFacadeVt]==0xc48528&&n[NLinks]&&live_source&&finite(nxyz);
        auto head=word(native_.logic+0xb4),cursor=head;uint32_t found=0;std::set<uint32_t> seen;
        while(cursor){
            if(cursor%4||seen.size()>=20000||!seen.insert(cursor).second||word(cursor)!=0xc4db60)return out;
            auto ident=word(cursor+0xdc);
            if(ident==actor_.object_id){if(cursor!=t)return out;found|=1;}
            if(ident==n[NId]){if(cursor!=neighbor)return out;found|=2;}
            cursor=word(cursor+0x7c);
        }
        a[ALive]=found;
        out.verified=own&&other&&found==3&&word(native_.logic+0x50)==out.frame&&word(native_.logic+0xb4)==head&&root()&&okay_;
        a[AComplete]=n[NComplete]=out.verified;return out;
    }
};
struct YieldContext {
    bool active=false,enabled=false,own_scope=false,own_stop_idle=false,dispatched=false,accepted=false;
    uint32_t frame=0,thread=0,self=0,outer_caller=0,source=0,neighbor=0,epoch=0;
    Point goal{};YieldSnapshot before{};
};
inline bool native_yield_outer_caller(uint32_t c){return c==0x694a00||c==0x694a50||c==0x6981c4||c==0x71c433||c==0x755dad||c==0x77c36e;}
// Ordinary admission is limited to the complete043207 source/abort/home/release
// witness. Policy eligibility is not acceptance: dispatch, typed identity and
// the fresh state26 confirmation below remain mandatory. Other source families
// and callers stay diagnostic-only until their corresponding field evidence.
inline bool ordinary_native_yield_source(const YieldContext& c){
    using namespace yield_words;
    return c.active&&c.before.verified&&c.outer_caller==0x694a00&&c.source==2
        &&c.before.neighbor[NHash]==0x2c358c61;
}
inline bool native_yield_policy_enabled(const YieldContext& c,bool diagnostic_experiment,bool already_pending){
    return c.active&&c.before.verified&&!already_pending&&(diagnostic_experiment||ordinary_native_yield_source(c));
}
inline bool native_yield_admissible(const YieldContext& c,const uint32_t* words,uint32_t self,uint32_t caller,uint32_t thread,uint32_t frame){
    using namespace yield_words;auto& a=c.before.actor;auto& n=c.before.neighbor;
    if(!words)return false;
    for(unsigned i:{6u,7u,8u,9u,11u,12u,13u,15u,16u,17u,18u,20u,21u})if(words[i])return false;
    return c.active&&c.enabled&&!c.own_scope&&c.own_stop_idle&&!c.dispatched&&c.before.verified&&native_yield_outer_caller(c.outer_caller)
        &&c.thread==thread&&c.frame==frame&&c.before.frame==frame&&c.self==self&&self==a[AUpdate]+0x24&&c.source==2
        &&a[AState]==94&&a[AVtable]==0xc551a0&&a[APath]==0&&a[ASource]==1&&!(a[AFlags]&0xffff)&&a[AStance]==2&&a[ASlot]==0xffffffffu
        &&words[0]==48&&words[1]==2&&words[5]==c.neighbor&&c.neighbor==n[NThing]
        &&caller==0x6939aa&&finite(c.goal)&&!std::memcmp(words+2,&c.goal,12)&&reinterpret_cast<const unsigned char*>(words)[0x58]==0;
}
inline bool native_yield_after(const YieldContext& c,const YieldSnapshot& after,uint32_t epoch){
    using namespace yield_words;
    return c.active&&c.dispatched&&c.before.verified&&after.verified&&after.frame==c.frame&&epoch==c.epoch
        &&after.actor[AThing]==c.before.actor[AThing]&&after.actor[AUpdate]==c.before.actor[AUpdate]
        &&after.actor[AId]==c.before.actor[AId]&&after.actor[ATeam]==c.before.actor[ATeam]
        &&after.actor[AStance]==2&&after.actor[ASlot]==0xffffffffu
        &&after.neighbor[NThing]==c.before.neighbor[NThing]&&after.neighbor[NId]==c.before.neighbor[NId]
        &&after.neighbor[NTemplate]==c.before.neighbor[NTemplate]&&after.neighbor[NUpdate]==c.before.neighbor[NUpdate]
        &&after.yield_neighbor_id==c.before.neighbor[NId];
}
// A facade receipt is only a candidate. The independently reread state26 and
// current actor sample must agree before the controller can abort and return.
class PendingNativeYield {
    YieldContext context_{};uint64_t began_=0;bool armed_=false;
public:
    bool pending()const{return armed_;}
    void clear(){armed_=false;context_={};began_=0;}
    bool arm(const YieldContext& c,uint64_t now){
        if(armed_||!c.enabled||!c.accepted||!c.dispatched)return false;
        context_=c;began_=now;armed_=true;return true;
    }
    const YieldContext& context()const{return context_;}
    NativePreemption inspect(const Sample& s,const YieldSnapshot& fresh,uint32_t epoch){
        using namespace yield_words;
        if(!armed_)return NativePreemption::None;
        auto& c=context_;auto& a=fresh.actor;auto& n=fresh.neighbor;
        bool bound=s.identity&&s.actor_birth_verified&&s.live_list_member&&s.grounded
            &&s.current_thread==c.thread&&s.actor.thing==c.before.actor[AThing]&&s.actor.update==c.before.actor[AUpdate]
            &&s.actor.object_id==c.before.actor[AId]&&s.team==s.script_team&&s.team==c.before.actor[ATeam]
            &&s.foreign_epoch==c.epoch&&epoch==c.epoch&&s.frame>=c.frame&&s.frame-c.frame<=2
            &&s.monotonic_ms>=began_&&s.monotonic_ms-began_<=250&&fresh.verified&&fresh.frame==s.frame
            &&a[AThing]==s.actor.thing&&a[AUpdate]==s.actor.update&&a[AId]==s.actor.object_id&&a[ATeam]==s.team
            &&n[NThing]==c.before.neighbor[NThing]&&n[NId]==c.before.neighbor[NId]
            &&n[NTemplate]==c.before.neighbor[NTemplate]&&n[NUpdate]==c.before.neighbor[NUpdate]
            &&fresh.yield_neighbor_id==n[NId]&&a[ASlot]==0xffffffffu&&s.stance==2&&a[AStance]==2
            &&s.command_source==1&&a[ASource]==1&&!(s.state_flags&0xffff)&&!(a[AFlags]&0xffff)
            &&a[AState]==s.state_id&&a[AVtable]==s.state_vtable&&a[APath]==s.path;
        if(!bound){clear();return NativePreemption::UnverifiedYield;}
        if(s.state_id==26&&s.state_vtable==0xc553d0){clear();return NativePreemption::VerifiedYield;}
        if(s.state_id!=94||s.state_vtable!=0xc551a0||s.path||s.frame-c.frame==2){clear();return NativePreemption::UnverifiedYield;}
        return NativePreemption::WaitingYield;
    }
};
}
