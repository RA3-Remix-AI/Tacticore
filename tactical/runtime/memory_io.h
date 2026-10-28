#pragma once
#include "protocol.h"
#include "incarnations.h"
#include "home_clearance.h"
#include <cstring>
#include <functional>
#include <vector>
#include <algorithm>

namespace tacticore::runtime {
struct NativeBinding {
    uint32_t logic=0,owner=0,ai=0,personality=0,personality_id=0,player_template=0,default_team=0,script_team=0;
};
class Memory {
public:
    virtual ~Memory()=default;
    virtual bool read(uint32_t,void*,uint32_t)=0;
    virtual Binding current_binding()=0; // PID/start/thread and immutable private channel.
    virtual uint32_t thread()=0;
    virtual uint64_t monotonic_ms()=0;
};
class NativeCalls {
public:
    virtual ~NativeCalls()=default;
    virtual Delivery call(Action,const Actor&,const NativeBinding&,Point,uint32_t)=0;
    virtual bool diagnostic_fault_enabled()const{return false;}
    virtual Delivery diagnostic_foreign_move(const Command&){return Delivery::NotSent;}
};
class CommandWitness {
public:
    virtual ~CommandWitness()=default;
    virtual bool installed_and_originals_verified()const=0;
    virtual uint32_t foreign_epoch()const=0;
    virtual bool normal_move_owned()const=0;
    virtual bool normal_stop_owned()const{return false;}
    virtual void begin(Action,Point,uint32_t)=0;
    virtual void end(Action)=0;
    virtual bool independent_quiescence_verified()const{return false;}
    virtual void recovery_observation(const Sample&,const std::array<uint32_t,24>&,const std::array<uint32_t,24>&){}
    virtual NativePreemption take_native_preemption(const Sample&){return NativePreemption::None;}
    virtual void clear_native_preemption(){}
};
class SurfacePoints {
public:
    virtual ~SurfacePoints()=default;
    // Must be independently read native ground geometry from this immutable
    // map binding. This proves the endpoint only; never a walkable route.
    virtual bool contains(const Binding&,Point)const=0;
};
class MemoryIO:public IO {
    Binding binding_;NativeBinding native_;Actor actor_;Incarnations& incarnations_;
    Memory& memory_;NativeCalls& calls_;CommandWitness& witness_;SurfacePoints& surfaces_;
    std::function<void(const Event&)> sink_;
    std::function<void(const HookTrace&)> home_clearance_sink_;
    uint32_t home_clearance_sequence_=0;
    uint32_t home_trace_frame_=0,home_trace_state_=home_clearance_unknown,home_trace_blocker_=0;
    uint32_t home_trace_rows_=0;
    bool reads_ok_=true;
    std::array<uint32_t,13> stance_definition_{};
    uint32_t recovery_frame_=0,recovery_epoch_=0,recovery_stable_=0;
    Point recovery_previous_{};
    Point admitted_home_{};bool home_admitted_=false;
    uint32_t word(uint32_t address){uint32_t v=0;if(!address||!memory_.read(address,&v,4))reads_ok_=false;return v;}
    float scalar(uint32_t address){float f=0;if(!address||!memory_.read(address,&f,4))reads_ok_=false;return f;}
    Point point(uint32_t address){Point p{};if(!address||!memory_.read(address,&p,12))reads_ok_=false;return p;}
    Sample raw(){
        reads_ok_=true;Sample s{};s.binding=memory_.current_binding();s.current_thread=memory_.thread();s.monotonic_ms=memory_.monotonic_ms();
        s.frame=word(native_.logic+0x50);s.paused=word(native_.logic+0x15c)!=0;
        s.identity=s.binding==binding_&&s.current_thread==binding_.thread&&word(0xcd8ce4)==native_.logic&&word(native_.logic)==0xbeb630&&word(native_.owner)==0xc5bce0&&word(native_.owner+0x20)==binding_.player&&word(native_.owner+0x10)==native_.player_template&&word(native_.owner+0x90)==native_.ai&&word(native_.ai)==0xc60f60&&word(native_.ai+8)==native_.owner&&word(native_.ai+0x8b0)==native_.personality&&word(native_.personality+0x18)==native_.personality_id;
        s.default_team=word(native_.owner+0xac);s.script_team=word(word(native_.owner+0x8c)+0x10);
        s.identity=s.identity&&s.default_team==native_.default_team&&s.script_team==native_.script_team&&word(word(s.default_team+4)+8)==native_.owner&&word(word(s.script_team+4)+8)==native_.owner;
        auto t=actor_.thing;auto u=word(t+0x374);auto tpl=word(t+4);auto body=word(t+0x33c);auto sm=word(u+0x3c);auto state=word(sm+4);
        s.actor=Actor{word(t+0xdc),t,tpl,u,word(t+0x418),word(tpl+8),actor_.born_frame,actor_.generation};
        s.team=word(t+0x414);s.xyz=point(t+0x38);float hp=scalar(body+4),height=scalar(t+0x5c);
        // Native AI squads differ from its common pool. Every current team
        // still needs an independently read owner link before any Borrow.
        s.identity=s.identity&&s.team&&word(word(s.team+4)+8)==native_.owner;
        uint32_t flags[7]={};if(!memory_.read(t+0x80,flags,28))reads_ok_=false;
        s.grounded=word(t)==0xc4db60&&word(u)==0xc48670&&word(u+0x24)==0xc48528&&word(u+8)==t&&s.actor.type_hash==0x19ab11af&&s.actor.owner==native_.owner&&word(t+0x238)==0&&!(flags[0]&0x181)&&!(flags[1]&0x20080000)&&!(flags[5]&2)&&!(flags[6]&0x88000)&&(word(t+0x48)&4)&&std::isfinite(height)&&std::fabs(height)<=.5f&&std::isfinite(hp)&&hp>0&&finite(s.xyz);
        auto stance_module=word(t+0x380),stance_data=word(stance_module+4),definition_list=word(word(stance_data+8)),definition_count=word(definition_list+4);
        std::array<uint32_t,13> definition{};
        definition[0]=stance_module;definition[1]=stance_data;definition[2]=definition_list;definition[3]=definition_count;definition[4]=word(definition_list+8);
        uint32_t enums=0;
        bool definition_ok=stance_module&&word(stance_module)==0xc37f90&&word(stance_module+8)==t&&word(0xc37f98)==0x71d3f0&&definition_count>=1&&definition_count<=4;
        if(definition_ok){
            if(!memory_.read(definition[4],definition.data()+5,definition_count*8))reads_ok_=false;
            for(uint32_t i=0;i<definition_count;i++){auto value=definition[5+2*i];if(value>3||(enums&(1u<<value))){definition_ok=false;break;}enums|=1u<<value;}
            definition_ok=definition_ok&&(enums&5)==5;
        }
        if(stance_definition_==std::array<uint32_t,13>{}&&definition_ok)stance_definition_=definition;
        s.grounded=s.grounded&&definition_ok&&definition==stance_definition_;
        s.stance=word(stance_module+0x38);
        s.state_id=word(state+4);s.state_vtable=word(state);s.state_flags=word(sm+0x78);s.path=word(u+0x150);s.command_source=word(u+0x50);
        s.settled=word(sm+0x24)==t&&word(state+0x18)==sm&&s.state_id==94&&s.state_vtable==0xc551a0&&!(s.state_flags&0xffff)&&s.path==0&&s.command_source==1&&witness_.normal_stop_owned();
        uint32_t first=word(native_.logic+0xb4),cursor=first,count=0,matches=0;
        for(;cursor&&count<20000;count++){
            if(cursor%4||word(cursor)!=0xc4db60){reads_ok_=false;break;}
            if(word(cursor+0xdc)==actor_.object_id){if(cursor!=t){reads_ok_=false;break;}matches++;}
            auto next=word(cursor+0x7c);if(next==cursor){reads_ok_=false;break;}cursor=next;
        }
        s.live_list_member=!cursor&&count>0&&matches==1&&word(native_.logic+0xb4)==first;
        s.normal_move_owned=witness_.normal_move_owned();s.foreign_epoch=witness_.foreign_epoch();s.interference_guard_ready=witness_.installed_and_originals_verified();
        if(word(native_.logic+0x50)!=s.frame||!reads_ok_)s.identity=false;
        return s;
    }
    static bool stable(const Sample& a,const Sample& b){return a.binding==b.binding&&a.actor==b.actor&&a.frame==b.frame&&a.current_thread==b.current_thread&&a.team==b.team&&a.default_team==b.default_team&&a.script_team==b.script_team&&a.stance==b.stance&&a.foreign_epoch==b.foreign_epoch&&a.xyz==b.xyz&&a.identity==b.identity&&a.live_list_member==b.live_list_member&&a.grounded==b.grounded&&a.paused==b.paused&&a.settled==b.settled&&a.normal_move_owned==b.normal_move_owned;}
    bool home_vacant(const Sample& s){
        // A previous ground observation does not establish present vacancy.
        // Include every current own Thing, not just the supported Conscript
        // class: the captured second lease had a Flak at the exact home point.
        // This conservative center clearance is not a collision/route proof
        // and cannot promise that another object will not enter later.
        reads_ok_=true;
        auto first=word(native_.logic+0xb4),cursor=first;uint32_t count=0,matches=0;
        for(;cursor&&count<20000;count++){
            if(cursor%4||word(cursor)!=0xc4db60)return false;
            if(cursor==actor_.thing)matches++;
            else if(word(cursor+0x418)==native_.owner){
                auto p=point(cursor+0x38);
                if(!finite(p)||(distance(p,s.xyz)<20&&std::fabs(p.z-s.xyz.z)<=2))return false;
            }
            auto next=word(cursor+0x7c);if(next==cursor)return false;cursor=next;
        }
        return !cursor&&count>0&&matches==1&&word(native_.logic+0xb4)==first
            &&word(native_.logic+0x50)==s.frame&&reads_ok_;
    }
public:
    MemoryIO(Binding binding,NativeBinding native,Actor actor,Incarnations& incarnations,Memory& memory,NativeCalls& calls,CommandWitness& witness,SurfacePoints& surfaces,std::function<void(const Event&)> sink,std::function<void(const HookTrace&)> home_sink={}):binding_(binding),native_(native),actor_(actor),incarnations_(incarnations),memory_(memory),calls_(calls),witness_(witness),surfaces_(surfaces),sink_(std::move(sink)),home_clearance_sink_(std::move(home_sink)){}
    bool diagnostic_fault_enabled()const override{return calls_.diagnostic_fault_enabled();}
    Delivery diagnostic_foreign_move(const Command& c)override{
        auto fresh=sample();
        if(!diagnostic_fault_enabled()||!fresh.identity||!fresh.actor_birth_verified||!fresh.live_list_member||!fresh.grounded||fresh.paused||!(c.actor==actor_)||fresh.team!=fresh.script_team||!fresh.settled||fresh.stance!=2||!witness_.independent_quiescence_verified()||!surfaces_.contains(binding_,c.target))return Delivery::NotSent;
        // Deliberately outside witness_.begin/end; the original hooks remain active.
        return calls_.diagnostic_foreign_move(c);
    }
    // First registration uses these same independent native reads, before the
    // private incarnation token exists. Caller binds original producer receipt.
    Sample birth_observation(){return raw();}
    Sample sample()override{
        auto a=raw(),b=raw();b.identity=b.identity&&a.identity&&stable(a,b);
        b.actor_birth_verified=incarnations_.current(actor_,b);
        if(b.frame!=recovery_frame_){
            // A fresh recovery command may brake an independently quiescent
            // pre-Stop actor. It does not assert that idle16 is Stop3 or home.
            bool idle=b.state_id==16&&b.state_vtable==0xc55130&&b.command_source==2&&!b.path&&!(b.state_flags&0xffff)&&(b.stance==0||b.stance==2);
            // This is physical quiescence for a NEW explicit recovery Stop.
            // It is not ownership of an earlier Stop, Ready, or a home claim.
            // 073613 provides four empty-slot, reverse-linked source2 Stop94
            // frames after an outside-scope Move. This is only a prerequisite
            // for a NEW release-only brake, never ownership of that old Stop.
            bool stopped_quiet=b.state_id==94&&b.state_vtable==0xc551a0&&(b.command_source==1||b.command_source==2)
                &&!b.path&&!(b.state_flags&0xffff)&&b.stance==2;
            std::array<uint32_t,24> slot{},paired_slot{},facts{};
            bool slot_read=memory_.read(actor_.update+0x310,slot.data(),96)
                &&memory_.read(actor_.update+0x310,paired_slot.data(),96)&&slot==paired_slot;
            bool empty=slot_read&&slot[0]==0xffffffffu;
            auto sm=word(actor_.update+0x3c),state=word(sm+4);
            facts[0]=sm;facts[1]=word(sm+0x24);facts[2]=state;facts[3]=word(state+0x18);facts[4]=b.state_flags;facts[5]=slot[0];facts[6]=b.stance;facts[7]=b.path;facts[8]=b.command_source;facts[9]=b.state_id;facts[10]=b.state_vtable;std::memcpy(facts.data()+11,&b.xyz,12);facts[14]=b.team;facts[15]=b.default_team;facts[16]=b.script_team;facts[17]=b.actor.object_id;facts[18]=b.actor.thing;facts[19]=b.actor.template_ptr;facts[20]=b.actor.update;facts[21]=b.actor.owner;facts[22]=b.actor.type_hash;facts[23]=slot_read?1:0;
            witness_.recovery_observation(b,slot,facts);
            bool safe=b.identity&&b.actor_birth_verified&&b.live_list_member&&b.grounded&&b.team==b.script_team&&(stopped_quiet||idle)&&empty&&!b.paused&&witness_.independent_quiescence_verified();
            safe=safe&&facts[1]==actor_.thing&&facts[3]==sm&&reads_ok_;
            recovery_stable_=safe&&b.foreign_epoch==recovery_epoch_&&distance(b.xyz,recovery_previous_)<=1&&std::fabs(b.xyz.z-recovery_previous_.z)<=.5f?recovery_stable_+1:0;
            recovery_frame_=b.frame;recovery_epoch_=b.foreign_epoch;
            recovery_previous_=b.xyz;
        }
        return b;
    }
    bool remember_home(const Sample& candidate)override{
        home_admitted_=false;
        auto fresh=sample();
        if(!candidate.identity||!candidate.actor_birth_verified||!fresh.identity||!fresh.actor_birth_verified
            ||!fresh.grounded||!fresh.live_list_member||fresh.paused||fresh.path||(fresh.state_flags&0xffff)||!(fresh.actor==actor_)
            ||!stable(candidate,fresh)||!home_vacant(fresh))return false;
        admitted_home_=fresh.xyz;home_admitted_=true;return true;
    }
    bool independent_borrow_permitted(const Sample& candidate)override{
        auto fresh=sample();
        // 064138: source0/idle16/path0 received a native attack immediately
        // after Borrow. It is not the independently observed source2 idle.
        if(!candidate.identity||!candidate.actor_birth_verified||!fresh.identity||!fresh.actor_birth_verified
            ||!fresh.grounded||!fresh.live_list_member||fresh.paused||!(fresh.actor==actor_)
            ||!stable(candidate,fresh)||fresh.team==fresh.script_team||fresh.stance!=0
            ||fresh.command_source!=2||fresh.state_id!=16||fresh.state_vtable!=0xc55130
            ||fresh.path||(fresh.state_flags&0xffff)||fresh.foreign_epoch
            ||!witness_.independent_quiescence_verified())return false;
        std::array<uint32_t,24> a{},b{};
        if(!memory_.read(actor_.update+0x310,a.data(),96)||!memory_.read(actor_.update+0x310,b.data(),96)
            ||a!=b||a[0]!=0xffffffffu)return false;
        auto sm=word(actor_.update+0x3c),state=word(sm+4);
        return word(sm+0x24)==actor_.thing&&word(state+0x18)==sm
            &&word(state)==fresh.state_vtable&&word(state+4)==fresh.state_id
            &&word(native_.logic+0x50)==fresh.frame&&reads_ok_;
    }
    bool ground_target(Point target)override{
        return finite(target)&&((home_admitted_&&target==admitted_home_)||surfaces_.contains(binding_,target));
    }
    bool return_home_clear(const Sample& candidate,Point target)override{
        auto fresh=sample();
        bool admitted=home_admitted_&&target==admitted_home_&&candidate.identity&&candidate.actor_birth_verified
            &&fresh.identity&&fresh.actor_birth_verified&&fresh.live_list_member&&fresh.grounded&&!fresh.paused
            &&fresh.team==fresh.script_team&&fresh.settled&&fresh.stance==2&&stable(candidate,fresh);
        using Node=std::array<uint32_t,8>; // Thing/vtable/ID/owner/next/xyz bits.
        reads_ok_=true;auto first=word(native_.logic+0xb4);
        auto scan=[&](){
            std::vector<Node> nodes;auto cursor=first;
            for(uint32_t i=0;cursor&&i<home_clearance_max_nodes;i++){
                if(cursor%4){reads_ok_=false;break;}
                Node n{cursor,word(cursor),word(cursor+0xdc),word(cursor+0x418),word(cursor+0x7c),0,0,0};
                auto p=point(cursor+0x38);std::memcpy(n.data()+5,&p,12);
                if(n[1]!=0xc4db60||!finite(p)){reads_ok_=false;break;}
                nodes.push_back(n);if(n[4]==cursor){reads_ok_=false;break;}cursor=n[4];
            }
            if(cursor||nodes.empty()||word(native_.logic+0xb4)!=first||word(native_.logic+0x50)!=fresh.frame)reads_ok_=false;
            return nodes;
        };
        auto before=scan(),after=scan();bool paired=reads_ok_&&before==after;
        auto ending=sample();paired=paired&&ending.identity&&ending.actor_birth_verified&&stable(fresh,ending);
        uint32_t matches=0,own=0,blocker=0;
        for(const auto& n:before){
            if(n[0]==actor_.thing){matches++;continue;}
            if(n[3]==native_.owner){
                own++;float xyz[3]{};std::memcpy(xyz,n.data()+5,12);Point p{xyz[0],xyz[1],xyz[2]};
                if(distance(p,target)<20&&std::fabs(p.z-target.z)<=2&&!blocker)blocker=n[0];
            }
        }
        bool complete=admitted&&paired&&matches==1;
        uint32_t needed=1+static_cast<uint32_t>((before.size()+2)/3)+own+1;
        bool proof_budget=needed<=home_clearance_max_group_rows&&home_trace_rows_+needed<=home_clearance_trace_budget;
        bool clear=complete&&!blocker&&proof_budget;
        auto state=clear?home_clearance_clear:complete?home_clearance_occupied:home_clearance_unknown;
        if(!blocker&&!proof_budget)state=home_clearance_unknown;
        // Preserve every clear admission and every transition. Repeated known
        // occupancy is sampled every ten frames to keep the bounded passive
        // trace ring available for cleanup; actual checks still run each tick.
        bool repeat_occupied=state!=home_clearance_clear&&home_trace_state_==state
            &&home_trace_blocker_==blocker&&fresh.frame>=home_trace_frame_&&fresh.frame-home_trace_frame_<10;
        if(home_clearance_sink_&&!repeat_occupied){
            HookTrace h{};h.kind=home_clearance_header_kind;h.frame=fresh.frame;h.thread=fresh.current_thread;h.self=actor_.update;h.target=actor_.thing;
            h.epoch_before=h.epoch_after=fresh.foreign_epoch;h.word_count=24;
            h.words[0]=++home_clearance_sequence_;h.words[1]=state;
            std::memcpy(h.words.data()+2,&target,12);h.words[5]=native_.logic;h.words[6]=first;
            h.words[7]=static_cast<uint32_t>(before.size());h.words[8]=matches;h.words[9]=own;h.words[10]=blocker;
            h.words[11]=actor_.object_id;h.words[12]=actor_.thing;h.words[13]=native_.owner;
            h.words[14]=fresh.team;h.words[15]=fresh.script_team;h.words[16]=(admitted?1u:0u)|(proof_budget?0u:2u);h.words[17]=paired?1:0;
            h.words[18]=static_cast<uint32_t>(after.size());h.words[19]=home_clearance_max_nodes;h.words[20]=20;h.words[21]=2;
            h.words[22]=2;h.words[23]=clear?static_cast<uint32_t>(before.size()):0;
            home_clearance_sink_(h);home_trace_rows_++;
            // Full paired pointer/next/owner closure is needed for a CLEAR
            // admission. Three global records fit one row; only own objects
            // need the separate full paired identity/position row.
            if(clear)for(size_t i=0;i<before.size();i+=3){
                HookTrace n=h;n.kind=home_clearance_node_kind;n.words.fill(0);n.words[0]=h.words[0];n.words[1]=static_cast<uint32_t>(i);
                for(size_t j=0;j<3&&i+j<before.size();j++)for(size_t k=0;k<3;k++){
                    auto field=k==0?0:k==1?4:3;
                    n.words[2+6*j+k]=before[i+j][field];n.words[5+6*j+k]=after[i+j][field];
                }
                home_clearance_sink_(n);home_trace_rows_++;
            }
            for(size_t i=0;i<before.size();i++)if((clear&&before[i][3]==native_.owner)
                    ||(state==home_clearance_occupied&&before[i][0]==blocker)){
                HookTrace n=h;n.kind=home_clearance_own_kind;n.words.fill(0);n.words[0]=h.words[0];n.words[1]=static_cast<uint32_t>(i);
                std::copy(before[i].begin(),before[i].end(),n.words.begin()+2);
                std::copy(after[i].begin(),after[i].end(),n.words.begin()+10);
                home_clearance_sink_(n);home_trace_rows_++;
            }
            home_trace_frame_=fresh.frame;home_trace_state_=state;home_trace_blocker_=blocker;
        }
        return clear;
    }
    Delivery issue(Action action,Point target,uint32_t stance)override{
        auto s=sample();
        if(!s.identity||!s.actor_birth_verified||!s.live_list_member||!s.grounded||s.paused||!s.interference_guard_ready||!(s.actor==actor_)||s.current_thread!=binding_.thread)return Delivery::NotSent;
        if(action==Action::Borrow){if(!independent_borrow_permitted(s))return Delivery::NotSent;}
        else if(s.team!=s.script_team)return Delivery::NotSent;
        if(action==Action::Move&&!ground_target(target))return Delivery::NotSent;
        if(action==Action::Move&&home_admitted_&&target==admitted_home_&&!return_home_clear(s,target))return Delivery::NotSent;
        witness_.begin(action,target,stance);auto result=calls_.call(action,actor_,native_,target,stance);witness_.end(action);return result;
    }
    void event(const Event& event)override{if(sink_)sink_(event);}
    bool independent_recovery_permitted(const Sample& s)override{return recovery_stable_>=3&&s.frame==recovery_frame_&&s.foreign_epoch==recovery_epoch_&&witness_.independent_quiescence_verified();}
    NativePreemption take_native_preemption(const Sample& s)override{return witness_.take_native_preemption(s);}
    void clear_native_preemption()override{witness_.clear_native_preemption();}
};
}
