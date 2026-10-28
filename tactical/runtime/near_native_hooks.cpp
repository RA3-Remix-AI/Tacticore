// Development fork of pinned v1 hooks.cpp; original remains unchanged.
// Adds strict normal attack lineage; not installed by any published runtime.
#include "near_native_hooks.h"
#include "near_move_lineage.h"
#include "membership.h"
#include "native_yield.h"
#include "MinHook.h"
#include <windows.h>
#include <cstring>
#include <stdexcept>
#include <algorithm>
namespace tacticore::runtime {
namespace {
bool read(uint32_t address,void* data,size_t count){SIZE_T n=0;return address&&ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(address),data,count,&n)&&n==count;}
uint32_t word(uint32_t address){uint32_t n=0;read(address,&n,4);return n;}
using Move=void(__attribute__((thiscall))*)(void*,float*,uint32_t);
using PrivateMove=void(__attribute__((thiscall))*)(void*,float*,void*,float,uint32_t);
using Stop=void(__attribute__((thiscall))*)(void*,uint32_t);
using Transfer=void(__attribute__((thiscall))*)(void*,void*,uint32_t);
using Member=void(__attribute__((thiscall))*)(void*,void*);
using Stance=bool(__attribute__((thiscall))*)(void*,uint32_t);
using Copy=void(__attribute__((thiscall))*)(void*,void*);
using Unpack=bool(__attribute__((thiscall))*)(void*,void*,void*);
using Attack=void(__attribute__((thiscall))*)(void*,void*,uint32_t,uint32_t);
using WeaponGet=uint32_t(__attribute__((thiscall))*)(void*,uint32_t);
using Yield=void(__attribute__((thiscall))*)(void*,void*,float*,uint32_t);
class Observer;std::atomic<Observer*> current{nullptr};
class Observer:public NearNativeObserver {
public:
    Binding binding;NativeBinding native;Actor actor;NearMoveLineage lineage;
    NativeAttackAdmission& attack_admission;near_combat::AttackLineage attack_lineage;
    near_combat::Lease attack_lease{};near_combat::Intent attack_intent{};near_combat::Target attack_target{};
    std::atomic<bool> attack_scope{false},attack_attempted{false},attack_stopping{false},private_attack_scope{false};
    WeaponSelection selection{};Attack attack_facade=nullptr;WeaponGet weapon_get=nullptr;
    YieldReader yield_reader;YieldContext yield_context{};PendingNativeYield pending_yield;bool yield_experiment=false,fault_experiment=false;
    volatile LONG active=0;std::atomic<bool> installed{false},scope{false};bool borrow_attempted=false,return_observed=false;std::atomic<bool> held{false};Action operation=Action::Stop;uint32_t desired_stance=0,mask=0;
    Move move=nullptr;PrivateMove private_move=nullptr;Stop stop=nullptr,private_stop=nullptr;Transfer transfer=nullptr;Member add=nullptr,remove=nullptr;Stance stance=nullptr;Copy copy=nullptr,dispatch=nullptr;Unpack unpack=nullptr;Attack attack=nullptr;
    Yield yield=nullptr;
    struct Hook {uint32_t address;void* detour;void** original;const char* signature;size_t count;unsigned char before[20];bool made=false,enabled=false;};
    std::vector<Hook> hooks;
    std::function<void(const HookTrace&)> trace_sink;
    Observer(Binding b,NativeBinding n,Actor a,Memory& memory,NativeAttackAdmission& admission,std::function<void(const HookTrace&)> sink):binding(b),native(n),actor(a),lineage(b.thread,a.thing,a.update),attack_admission(admission),attack_lineage(b,a),yield_reader(b,n,a,memory),trace_sink(std::move(sink)){}
    ~Observer()override{if(no_hooks_enabled()){for(auto& hook:hooks)if(hook.made)MH_RemoveHook(reinterpret_cast<void*>(hook.address));if(current==this)current=nullptr;}}
    bool ours(uintptr_t self,bool facade=false)const{return held&&self==actor.update+(facade?0x24:0);}
    bool own(Action a)const{return GetCurrentThreadId()==binding.thread&&scope&&!attack_scope&&operation==a;}
    bool own_attack()const{return GetCurrentThreadId()==binding.thread&&scope&&attack_scope;}
    void foreign(){attack_lineage.foreign();if(GetCurrentThreadId()==binding.thread){pending_yield.clear();lineage.foreign();}else lineage.external_thread_foreign();}
    uint32_t frame()const{return word(native.logic+0x50);}
    bool automatic_stop(uint32_t source)const{return source==2&&(own(Action::HoldStance)||own(Action::RestoreStance));}
    bool stopping(uint32_t source)const{return (source==1&&own(Action::Stop))||automatic_stop(source);}
    void trace(uint32_t kind,uint32_t self,uint32_t target,uint32_t caller,uint32_t source,uint32_t before,const void* raw=nullptr,uint32_t count=0){
        if(!trace_sink)return;
        HookTrace t{};t.frame=frame();t.thread=GetCurrentThreadId();t.kind=kind;t.self=self;t.target=target;t.caller=caller;
        t.operation=(attack_scope||private_attack_scope||(!scope&&attack_lineage.pending()))?0x1001u:static_cast<uint32_t>(operation);t.scope=scope;t.source=source;t.epoch_before=before;t.epoch_after=lineage.epoch();
        if(raw&&count<=24&&read(reinterpret_cast<uintptr_t>(raw),t.words.data(),count*4))t.word_count=count;
        trace_sink(t);
    }
    bool installed_and_originals_verified()const override{return installed&&current==this;}
    uint32_t foreign_epoch()const override{return lineage.epoch();}
    bool normal_move_owned()const override{return lineage.delivered();}
    // Submitting a deferred attack does not itself execute a state change.
    // Keep the proven Stop available to the independent pre-delivery guard;
    // invalidate it once the private attack is actually attributed/delivered.
    bool normal_stop_owned()const override{return lineage.stop_delivered()&&(!attack_lineage.delivered()||attack_stopping);}
    bool attack_delivered()const override{return attack_lineage.delivered();}
    WeaponSelection weapon_selection()const override{return selection;}
    bool admit_attack(AttackBoundary boundary){
        if(GetCurrentThreadId()!=binding.thread||!installed||!held||word(native.logic+0x15c))return false;
        auto f=frame();auto now=GetTickCount64();
        if(!(attack_lease.binding==binding)||!(attack_lease.actor==actor)||!attack_lease.held||attack_lease.owner_uncertain
            ||attack_intent.task!=attack_lease.task||attack_intent.lease!=attack_lease.lease||!(attack_intent.actor==actor)
            ||attack_intent.target_key!=attack_target.key||attack_intent.lease_deadline_frame!=attack_lease.original_deadline_frame
            ||f<attack_lease.original_begin_frame||f>=attack_lease.original_deadline_frame||f>=attack_intent.expires_frame
            ||now>=attack_intent.expires_monotonic_ms||now<attack_lease.original_begin_ms||now-attack_lease.original_begin_ms>=120000
            ||lineage.epoch()!=attack_lease.foreign_epoch)return false;
        try{return attack_admission.permit(attack_lease,attack_intent,attack_target,boundary);}catch(...){return false;}
    }
    bool capture_weapon(uint32_t entry){
        bool complete=true;
        auto w=[&](uint32_t address){uint32_t value=0;if(!address||!read(address,&value,4))complete=false;return value;};
        selection={};selection.frame=frame();selection.thread=GetCurrentThreadId();
        if(!private_attack_scope||selection.thread!=binding.thread||!entry||w(entry)!=0xc2e324)return false;
        auto container=w(actor.thing+0x37c),slot=w(entry+8),tpl=w(entry+4);
        auto first=w(container+0x24),end=w(container+0x28),index=w(slot+0x14),entries=w(slot+0x94);
        if(w(container+8)!=actor.thing||!first||end<=first||end-first>256||(end-first)%4||index>=5
            ||w(slot)!=0xc3a6e0||w(0xc3a704)!=0x6dbe80||w(0xc3a708)!=0x6f88e0||!entries||w(entries+4*index)!=entry
            ||!tpl||w(tpl)!=0xc37534)return false;
        bool found=false;for(auto cursor=first;cursor<end;cursor+=4)found=found||w(cursor)==slot;
        if(!found)return false;
        auto schema=w(tpl+4),header=w(schema),asset=w(header+4),ammo=w(entry+0x1c);
        if(!schema||!header||w(header)!=0x94d4d96e||asset!=0x447ea26e||ammo==0||ammo>3
            ||w(actor.thing+0x37c)!=container||w(entry+4)!=tpl||w(entry+8)!=slot||w(slot+0x14)!=index
            ||w(entries+4*index)!=entry||frame()!=selection.frame)return false;
        auto sm=w(entry+0x64),state=w(sm+4);
        uint8_t requested=1;if(!read(entry+0x60,&requested,1))complete=false;
        bool ready=sm&&state&&w(sm)==0xc1fc50&&w(sm+0x80)==entry&&w(sm+0x24)==actor.thing
            &&w(state)==0xc1fd18&&w(state+4)==0&&w(state+0x18)==sm&&w(state+0x20)==entry
            &&!(w(sm+0x78)&0xffff)&&requested==0&&w(entry+0xc)==actor.object_id;
        // c1fd18's pinned name getter is WeaponReadyState, registered as state0
        // in 6f8d80. Ammo alone never supplies this readiness assertion.
        if(!ready||!complete)return false;
        auto limit=w(entry+0x24);
        if(!complete||w(entry+0x64)!=sm||w(sm+4)!=state||frame()!=selection.frame||!complete)return false;
        selection.entry=entry;selection.template_ptr=tpl;selection.slot=slot;selection.ammo=ammo;
        selection.state_machine=sm;selection.state=state;selection.state_id=0;selection.ready_state=true;
        selection.limit_before=limit;selection.asset_id=asset;selection.verified=true;return true;
    }
    near_combat::AttackAcknowledgement attack_once(const near_combat::Lease& lease,const near_combat::Intent& intent,const near_combat::Target& target)override{
        near_combat::AttackAcknowledgement ack;ack.delivery=Delivery::NotSent;
        if(GetCurrentThreadId()!=binding.thread||!installed||scope||active||!held||attack_attempted||attack_lineage.failed())return ack;
        attack_lease=lease;attack_intent=intent;attack_target=target;
        if(!admit_attack(AttackBoundary::Facade)||!attack_lineage.arm(intent,target,GetCurrentThreadId(),frame()))return ack;
        attack_attempted=true;scope=attack_scope=true;
        ack.binding=binding;ack.actor=actor;ack.target=target;ack.command=intent.command;ack.task=intent.task;ack.lease=intent.lease;
        ack.sequence=intent.sequence;ack.frame=frame();ack.monotonic_ms=GetTickCount64();ack.shots=1;
        uint32_t stamp[24]={1,intent.command[0],intent.command[1],intent.command[2],intent.command[3],
            static_cast<uint32_t>(intent.sequence),static_cast<uint32_t>(intent.sequence>>32),target.object_id,target.thing,1,1};
        trace(40,actor.update+0x24,target.thing,0,1,lineage.epoch(),stamp,24);
        // Invoke the normal SDK facade, through its real installed hook. Never
        // call a private entry/trampoline or edit state, target or fire limit.
        try{reinterpret_cast<Attack>(0x572280)(reinterpret_cast<void*>(actor.update+0x24),reinterpret_cast<void*>(target.thing),1,1);ack.delivery=Delivery::Sent;}
        catch(...){ack.delivery=Delivery::Unknown;private_attack_scope=false;foreign();}
        ack.own_scope_verified=attack_lineage.submitted();scope=attack_scope=false;return ack;
    }
    NativePreemption take_native_preemption(const Sample& s)override{
        if(!pending_yield.pending())return NativePreemption::None;
        if(GetCurrentThreadId()!=binding.thread){foreign();return NativePreemption::UnverifiedYield;}
        auto context=pending_yield.context();auto fresh=yield_reader.capture(context.neighbor);
        auto result=pending_yield.inspect(s,fresh,lineage.epoch());
        trace(22,actor.update,actor.thing,context.outer_caller,fresh.yield_neighbor_id,context.epoch,fresh.actor.data(),24);
        trace(23,actor.update+0x24,context.neighbor,context.outer_caller,static_cast<uint32_t>(result),context.epoch,fresh.neighbor.data(),24);
        return result;
    }
    void clear_native_preemption()override{pending_yield.clear();}
    void begin(Action a,Point point,uint32_t stance_value)override{
        if(scope||GetCurrentThreadId()!=binding.thread){lineage.foreign();throw std::runtime_error("native_action_reentrancy_or_thread");}
        scope=true;operation=a;desired_stance=stance_value;
        if(a==Action::Stop&&attack_attempted)attack_stopping=true;
        if(a==Action::Borrow){borrow_attempted=true;return_observed=false;held=true;}
        if(a==Action::Move&&!lineage.arm(point,GetCurrentThreadId(),frame()))throw std::runtime_error("normal_move_arm_failed");
        if(a==Action::Stop&&!lineage.arm_stop(GetCurrentThreadId(),frame()))throw std::runtime_error("normal_stop_arm_failed");
    }
    void end(Action a)override{
        scope=false;
        if(a==Action::TransferBack&&word(actor.thing+0x414)==native.default_team
            &&word(word(native.default_team+4)+8)==native.owner){return_observed=true;held=false;}
    }
    bool independent_quiescence_verified()const override{return installed&&!scope&&active==0&&!lineage.pending()&&!attack_lineage.pending()&&!pending_yield.pending()&&!yield_context.active;}
    void recovery_observation(const Sample&,const std::array<uint32_t,24>& slot,const std::array<uint32_t,24>& facts)override{
        if(!held)return;
        auto epoch=lineage.epoch();trace(16,actor.update+0x310,actor.thing,0,0,epoch,slot.data(),24);
        trace(17,actor.update,actor.thing,0,0,epoch,facts.data(),24);
    }
    uint32_t active_callbacks()const override{return static_cast<uint32_t>(active);}
    uint32_t restored_mask()const override{return mask;}
    bool no_hooks_enabled()const override{return active==0&&std::none_of(hooks.begin(),hooks.end(),[](const Hook& h){return h.enabled;});}
    bool diagnostic_fault_enabled()const override{return fault_experiment;}
    Delivery diagnostic_foreign_move(const Command& c)override{
        if(!fault_experiment||!installed||scope||!held||active||GetCurrentThreadId()!=binding.thread||!(c.actor==actor)||word(native.logic+0x15c)||!independent_quiescence_verified())return Delivery::NotSent;
        uint32_t marker[24]={1,c.command[0],c.command[1],c.command[2],c.command[3],static_cast<uint32_t>(c.sequence),static_cast<uint32_t>(c.sequence>>32),2};
        std::memcpy(marker+8,&c.target,12);marker[11]=actor.object_id;marker[12]=actor.thing;marker[13]=actor.update;marker[14]=2;
        trace(35,actor.update+0x24,actor.thing,0,2,lineage.epoch(),marker,24);
        // Same existing SDK facade as ordinary Move, source2 and WITHOUT our
        // Move scope. No actor/state/epoch memory is written or hook bypassed.
        float goal[]={c.target.x,c.target.y,c.target.z};
        reinterpret_cast<Move>(0x571d90)(reinterpret_cast<void*>(actor.update+0x24),goal,2);
        return Delivery::Sent;
    }
    Delivery call(Action a,const Actor& actor_value,const NativeBinding& native_value,Point p,uint32_t stance_value)override{
        if(!installed||!scope||GetCurrentThreadId()!=binding.thread||!(actor_value==actor)||native_value.owner!=native.owner||word(native.logic+0x15c))return Delivery::NotSent;
        switch(a){
        case Action::Move:{float point[]={p.x,p.y,p.z};reinterpret_cast<Move>(0x571d90)(reinterpret_cast<void*>(actor.update+0x24),point,1);break;}
        case Action::Stop:reinterpret_cast<Stop>(0x54b0a0)(reinterpret_cast<void*>(actor.update+0x24),1);break;
        case Action::Borrow:case Action::TransferBack:reinterpret_cast<Transfer>(0x838820)(reinterpret_cast<void*>(native.owner),reinterpret_cast<void*>(actor.thing),a==Action::TransferBack?1:0);break;
        case Action::HoldStance:case Action::RestoreStance:reinterpret_cast<Stance>(0x7640f0)(reinterpret_cast<void*>(word(actor.thing+0x380)),stance_value);break;
        default:return Delivery::NotSent;}
        return Delivery::Sent;
    }
    bool install()override;
    bool close_after_verified_release()override{
        auto team=borrow_attempted?word(actor.thing+0x414):0;
        bool owned=team&&word(word(team+4)+8)==native.owner;
        if(!observer_detach_admissible(borrow_attempted,held,scope,static_cast<uint32_t>(active),lineage.pending()||pending_yield.pending()||yield_context.active,
            team,native.default_team,return_observed,owned,native.script_team)||attack_lineage.pending())return false;
        for(unsigned i=0;i<hooks.size();i++){auto& h=hooks[i];if(h.enabled){if(MH_DisableHook(reinterpret_cast<void*>(h.address))!=MH_OK)return false;h.enabled=false;}
            unsigned char observed[20]={};if(!read(h.address,observed,h.count)||std::memcmp(observed,h.before,h.count))return false;mask|=1u<<i;}
        if(active)return false;
        installed=false;if(current==this)current=nullptr;return true;
    }
};
struct Callback {Observer* o;Callback():o(current){if(o)InterlockedIncrement(&o->active);}~Callback(){if(o)InterlockedDecrement(&o->active);}};
void __attribute__((fastcall)) move_hook(void* self,void*,float* goal,uint32_t source){Callback cb;auto o=cb.o;bool ours=o->ours(reinterpret_cast<uintptr_t>(self),true);bool facade_owned=false;auto before=o->lineage.epoch();if(ours){Point p{};bool got=read(reinterpret_cast<uintptr_t>(goal),&p,12);facade_owned=got&&o->lineage.facade_enter(reinterpret_cast<uintptr_t>(self),p,source,GetCurrentThreadId(),o->frame(),o->own(Action::Move)||o->own(Action::Stop));if(!got)o->foreign();}if(ours)o->trace(1,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(goal),reinterpret_cast<uintptr_t>(__builtin_return_address(0)),source,before,goal,3);o->move(self,goal,source);if(ours&&facade_owned){o->lineage.facade_exit();}}
void __attribute__((fastcall)) private_move_hook(void* self,void*,float* goal,void* path,float limit,uint32_t source){Callback cb;auto o=cb.o;bool ours=o->ours(reinterpret_cast<uintptr_t>(self));auto before=o->lineage.epoch();if(ours){Point p{};if(read(reinterpret_cast<uintptr_t>(goal),&p,12))o->lineage.private_move(reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(goal),p,reinterpret_cast<uintptr_t>(path),limit,source,reinterpret_cast<uintptr_t>(__builtin_return_address(0)),GetCurrentThreadId(),o->frame(),o->own(Action::Move));else o->foreign();}if(ours){uint32_t raw[5]={};read(reinterpret_cast<uintptr_t>(goal),raw,12);raw[3]=reinterpret_cast<uintptr_t>(path);std::memcpy(raw+4,&limit,4);o->trace(2,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(goal),reinterpret_cast<uintptr_t>(__builtin_return_address(0)),source,before,raw,5);}o->private_move(self,goal,path,limit,source);}
void __attribute__((fastcall)) stop_hook(void* self,void*,uint32_t source){Callback cb;auto o=cb.o;bool ours=o->ours(reinterpret_cast<uintptr_t>(self),true);auto before=o->lineage.epoch();bool owned=false;if(ours){if(o->automatic_stop(source)){}else owned=o->lineage.stop_facade_enter(reinterpret_cast<uintptr_t>(self),source,GetCurrentThreadId(),o->frame(),o->own(Action::Stop));}if(ours)o->trace(3,reinterpret_cast<uintptr_t>(self),0,reinterpret_cast<uintptr_t>(__builtin_return_address(0)),source,before);o->stop(self,source);if(owned)o->lineage.facade_exit();}
void __attribute__((fastcall)) private_stop_hook(void* self,void*,uint32_t source){Callback cb;auto o=cb.o;bool ours=o->ours(reinterpret_cast<uintptr_t>(self));auto before=o->lineage.epoch();if(ours){if(o->automatic_stop(source)){if(reinterpret_cast<uintptr_t>(__builtin_return_address(0))!=0x787791)o->foreign();}else o->lineage.private_stop(reinterpret_cast<uintptr_t>(self),source,reinterpret_cast<uintptr_t>(__builtin_return_address(0)),GetCurrentThreadId(),o->frame(),o->own(Action::Stop));}if(ours)o->trace(4,reinterpret_cast<uintptr_t>(self),0,reinterpret_cast<uintptr_t>(__builtin_return_address(0)),source,before);o->private_stop(self,source);}
void __attribute__((fastcall)) transfer_hook(void* self,void*,void* thing,uint32_t to_ai){Callback cb;auto o=cb.o;bool ours=o->held&&reinterpret_cast<uintptr_t>(thing)==o->actor.thing;auto before=o->lineage.epoch();if(ours&&((!(o->own(Action::Borrow)&&to_ai==0)&&!(o->own(Action::TransferBack)&&to_ai==1))||reinterpret_cast<uintptr_t>(self)!=o->native.owner))o->foreign();if(ours)o->trace(5,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(thing),reinterpret_cast<uintptr_t>(__builtin_return_address(0)),to_ai,before);o->transfer(self,thing,to_ai);}
void member(bool add,void* self,void* thing,uint32_t caller){Callback cb;auto o=cb.o;bool ours=o->held&&reinterpret_cast<uintptr_t>(thing)==o->actor.thing;auto before=o->lineage.epoch();if(ours&&!owned_roster_member(add,reinterpret_cast<uintptr_t>(self),caller,GetCurrentThreadId(),o->binding.thread,o->native.ai,o->scope,o->operation))o->foreign();if(ours)o->trace(add?6:7,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(thing),caller,0,before);(add?o->add:o->remove)(self,thing);}
void __attribute__((fastcall)) add_hook(void* self,void*,void* thing){member(true,self,thing,reinterpret_cast<uintptr_t>(__builtin_return_address(0)));}void __attribute__((fastcall)) remove_hook(void* self,void*,void* thing){member(false,self,thing,reinterpret_cast<uintptr_t>(__builtin_return_address(0)));}
bool __attribute__((fastcall)) stance_hook(void* self,void*,uint32_t value){Callback cb;auto o=cb.o;bool ours=o->held&&reinterpret_cast<uintptr_t>(self)==word(o->actor.thing+0x380);auto before=o->lineage.epoch();if(ours&&(!(o->own(Action::HoldStance)||o->own(Action::RestoreStance))||value!=o->desired_stance))o->foreign();if(ours)o->trace(8,reinterpret_cast<uintptr_t>(self),0,reinterpret_cast<uintptr_t>(__builtin_return_address(0)),value,before);return o->stance(self,value);}
void __attribute__((fastcall)) attack_facade_hook(void* self,void*,void* target,uint32_t shots,uint32_t source){
    Callback cb;auto o=cb.o;bool ours=o->ours(reinterpret_cast<uintptr_t>(self),true);auto epoch=o->lineage.epoch();bool owned=false;
    if(ours){owned=o->attack_lineage.facade_enter(reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(target),shots,source,GetCurrentThreadId(),o->frame(),o->own_attack());if(!owned)o->foreign();o->trace(41,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(target),reinterpret_cast<uintptr_t>(__builtin_return_address(0)),source,epoch,&shots,1);}
    o->attack_facade(self,target,shots,source);
    if(owned&&!o->attack_lineage.facade_exit())o->foreign();
    if(ours)o->trace(42,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(target),0,source,epoch,&shots,1);
}
uint32_t __attribute__((fastcall)) weapon_get_hook(void* self,void*,uint32_t selector){
    Callback cb;auto o=cb.o;auto result=o->weapon_get(self,selector);
    if(GetCurrentThreadId()==o->binding.thread&&o->private_attack_scope&&reinterpret_cast<uintptr_t>(self)==word(o->actor.thing+0x37c)
        &&reinterpret_cast<uintptr_t>(__builtin_return_address(0))==0x76e6c6&&selector==0xffffffffu){
        o->capture_weapon(result);auto s=o->selection;
        uint32_t raw[24]={1,s.frame,s.thread,s.entry,s.template_ptr,s.slot,s.ammo,s.limit_before,s.asset_id,s.verified,s.state_machine,s.state,s.state_id,s.ready_state};
        o->trace(44,reinterpret_cast<uintptr_t>(self),result,0x76e6c6,selector,o->lineage.epoch(),raw,24);
    }
    return result;
}
void __attribute__((fastcall)) attack_hook(void* self,void*,void* target,uint32_t shots,uint32_t source){
    Callback cb;auto o=cb.o;bool ours=o->ours(reinterpret_cast<uintptr_t>(self));auto epoch=o->lineage.epoch();bool owned=false;
    if(ours){
        owned=o->admit_attack(AttackBoundary::PrivateDelivery)&&o->attack_lineage.private_attack(reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(target),shots,source,reinterpret_cast<uintptr_t>(__builtin_return_address(0)),GetCurrentThreadId(),o->frame(),o->own_attack());
        if(!owned)o->foreign();else{o->private_attack_scope=true;o->selection={};}
        o->trace(9,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(target),reinterpret_cast<uintptr_t>(__builtin_return_address(0)),source,epoch,&shots,1);
    }
    o->attack(self,target,shots,source); // Always forward the original once.
    if(owned){
        auto& s=o->selection;
        uint32_t observed[3]={};bool complete=s.verified&&read(s.entry,observed,12)&&read(s.entry+0x24,&s.limit_after,4);
        s.after_verified=complete&&s.limit_after==1&&GetCurrentThreadId()==s.thread&&o->frame()==s.frame
            &&observed[0]==0xc2e324&&observed[1]==s.template_ptr&&observed[2]==s.slot;
        if(!s.after_verified)o->foreign();
        uint32_t raw[24]={1,s.frame,s.thread,s.entry,s.template_ptr,s.slot,s.ammo,s.limit_before,s.limit_after,s.asset_id,s.verified,s.after_verified,s.state_machine,s.state,s.state_id,s.ready_state};
        o->trace(43,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(target),0,source,epoch,raw,24);
        o->private_attack_scope=false;
    }
}
void __attribute__((fastcall)) dispatch_hook(void* self,void*,void* command){
    Callback cb;auto o=cb.o;auto thread=GetCurrentThreadId();auto caller=reinterpret_cast<uintptr_t>(__builtin_return_address(0));
    auto prior=thread==o->binding.thread?o->lineage.context():NearMoveLineage::Context{};
    auto prior_attack=thread==o->binding.thread?o->attack_lineage.context():near_combat::AttackLineage::Context{};
    bool owned=false,owned_attack=false,yield_dispatch=false,observe_yield=false;bool ours=o->ours(reinterpret_cast<uintptr_t>(self),true);auto before=o->lineage.epoch();
    if(ours){
        uint32_t words[23]={};bool got=read(reinterpret_cast<uintptr_t>(command),words,92);
        bool expected_stop=got&&words[0]==5&&o->automatic_stop(words[1]);
        observe_yield=thread==o->binding.thread&&got&&o->yield_context.active&&words[0]==48&&caller==0x6939aa;
        if(got&&words[0]==11&&(o->own_attack()||o->attack_lineage.pending())){
            owned_attack=o->attack_lineage.dispatch_enter(reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(command),words,caller,thread,o->frame(),o->own_attack());
            if(!owned_attack)o->foreign();
        }else if(thread==o->binding.thread&&got&&native_yield_admissible(o->yield_context,words,reinterpret_cast<uintptr_t>(self),caller,thread,o->frame())){
            o->yield_context.dispatched=true;yield_dispatch=true;
        }else if(!expected_stop){
            owned=got&&o->lineage.dispatch_enter(reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(command),words,caller,thread,o->frame(),o->own(Action::Move)||o->own(Action::Stop));
            if(!got)o->foreign();
        }
        o->trace(10,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(command),caller,words[1],before,command,23);
    }
    o->dispatch(self,command);
    if(owned)o->lineage.dispatch_exit(prior);
    if(owned_attack&&!o->attack_lineage.dispatch_exit(prior_attack))o->foreign();
    if(observe_yield){
        auto after=o->yield_reader.capture(o->yield_context.neighbor);
        if(yield_dispatch){
            o->yield_context.accepted=native_yield_after(o->yield_context,after,o->lineage.epoch());
            if(!o->yield_context.accepted)o->foreign();
        }
        o->trace(20,reinterpret_cast<uintptr_t>(self),o->actor.thing,caller,after.yield_neighbor_id,before,after.actor.data(),24);
        o->trace(25,reinterpret_cast<uintptr_t>(self),o->yield_context.neighbor,caller,after.verified,before,after.neighbor_physical.data(),24);
    }
}
void __attribute__((fastcall)) yield_hook(void* self,void*,void* neighbor,float* goal,uint32_t source){
    Callback cb;auto o=cb.o;auto thread=GetCurrentThreadId();auto caller=reinterpret_cast<uintptr_t>(__builtin_return_address(0));
    bool ours=o->ours(reinterpret_cast<uintptr_t>(self),true);
    if(!ours){o->yield(self,neighbor,goal,source);return;}
    if(thread!=o->binding.thread||o->yield_context.active){o->foreign();o->yield(self,neighbor,goal,source);return;}
    YieldContext c;c.active=true;c.own_scope=o->scope;
    c.own_stop_idle=o->normal_stop_owned()&&o->lineage.stopped_context_idle();c.frame=o->frame();c.thread=thread;c.self=reinterpret_cast<uintptr_t>(self);
    c.outer_caller=caller;c.source=source;c.neighbor=reinterpret_cast<uintptr_t>(neighbor);c.epoch=o->lineage.epoch();
    bool got=read(reinterpret_cast<uintptr_t>(goal),&c.goal,12);c.before=o->yield_reader.capture(c.neighbor);
    if(!got)c.before.verified=false;
    c.enabled=native_yield_policy_enabled(c,o->yield_experiment,o->pending_yield.pending());
    o->yield_context=c;
    o->trace(18,c.self,c.neighbor,caller,source,c.epoch,c.before.neighbor.data(),24);
    o->trace(19,c.self,o->actor.thing,caller,source,c.epoch,c.before.actor.data(),24);
    o->trace(24,c.self,c.neighbor,caller,c.before.verified,c.epoch,c.before.neighbor_physical.data(),24);
    // The original native call is always forwarded once, even on refusal.
    o->yield(self,neighbor,goal,source);
    auto result=o->yield_context;
    bool accepted=result.enabled&&result.accepted&&result.dispatched&&o->lineage.epoch()==result.epoch;
    if(accepted){
        accepted=o->pending_yield.arm(result,GetTickCount64());
        if(accepted)o->lineage.clear_for_verified_native_preemption();else o->foreign();
    }
    uint32_t stamp[24]={1,c.frame,c.thread,c.self,c.outer_caller,c.source,c.neighbor,c.epoch,
        result.enabled,result.own_scope,result.own_stop_idle,result.dispatched,result.accepted,accepted,o->lineage.epoch()};
    std::memcpy(stamp+15,&c.goal,12);
    stamp[18]=o->yield_experiment?1:0;stamp[19]=ordinary_native_yield_source(c)?1:0;stamp[20]=1;
    o->trace(21,c.self,c.neighbor,caller,source,c.epoch,stamp,24);
    o->yield_context={};
}
void __attribute__((fastcall)) copy_hook(void* self,void*,void* command){
    Callback cb;auto o=cb.o;bool ours=o->held&&reinterpret_cast<uintptr_t>(self)==o->actor.update+0x310;
    uint32_t before[24]={},input[23]={};auto epoch=o->lineage.epoch();bool valid=false,attack_copy=ours&&o->own_attack();
    near_combat::AttackLineage::PendingReplacement replacement;
    if(ours){
        bool got=read(reinterpret_cast<uintptr_t>(self),before,96)&&read(reinterpret_cast<uintptr_t>(command),input,92);
        if(got&&o->own(Action::Stop))replacement=o->attack_lineage.pending_replacement(before,GetCurrentThreadId(),o->frame());
        if(got)valid=attack_copy?o->attack_lineage.copy_before(reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(command),before,input,reinterpret_cast<uintptr_t>(__builtin_return_address(0)),GetCurrentThreadId(),o->frame(),true):
            o->lineage.copy_before(reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(command),before,input,reinterpret_cast<uintptr_t>(__builtin_return_address(0)),GetCurrentThreadId(),o->frame(),o->own(Action::Move)||o->own(Action::Stop),replacement.valid()?&replacement:nullptr);
        if(!valid)o->foreign();
        o->trace(11,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(command),reinterpret_cast<uintptr_t>(__builtin_return_address(0)),attack_copy?11:0,epoch,command,23);
        o->trace(13,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(command),0,attack_copy?11:0,epoch,before,24);
    }
    o->copy(self,command);
    if(valid){uint32_t after[24]={};if(!read(reinterpret_cast<uintptr_t>(self),after,96))o->foreign();
        else if(attack_copy){if(!o->attack_lineage.copy_after(before,after,input))o->foreign();}
        else {
            bool copied=o->lineage.copy_after(before,after,input);
            if(copied&&replacement.valid()){
                bool cancelled=o->attack_lineage.cancel_after_stop_copy(replacement,before,after,input,GetCurrentThreadId(),o->frame());
                if(!cancelled)o->foreign();
                uint32_t stamp[24]={1,o->attack_intent.command[0],o->attack_intent.command[1],o->attack_intent.command[2],o->attack_intent.command[3],
                    static_cast<uint32_t>(o->attack_intent.sequence),static_cast<uint32_t>(o->attack_intent.sequence>>32),cancelled};
                o->trace(45,reinterpret_cast<uintptr_t>(self),o->attack_target.thing,0,5,epoch,stamp,24);
            }
        }}
    if(ours)o->trace(14,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(command),0,attack_copy?11:0,epoch,self,24);
}
bool __attribute__((fastcall)) unpack_hook(void* self,void*,void* thing,void* output){
    Callback cb;auto o=cb.o;bool slot=o->held&&reinterpret_cast<uintptr_t>(self)==o->actor.update+0x310;
    bool attack_unpack=slot&&o->attack_lineage.pending(),movement_unpack=slot&&o->lineage.pending();
    bool ours=attack_unpack||movement_unpack;auto epoch=o->lineage.epoch();bool valid=false;
    if(ours){uint32_t stored[24]={};bool got=read(reinterpret_cast<uintptr_t>(self),stored,96);
        if(got&&attack_unpack!=movement_unpack)valid=attack_unpack?o->attack_lineage.unpack_before(reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(thing),reinterpret_cast<uintptr_t>(output),stored,reinterpret_cast<uintptr_t>(__builtin_return_address(0)),GetCurrentThreadId(),o->frame(),o->scope):
            o->lineage.unpack_before(reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(thing),reinterpret_cast<uintptr_t>(output),stored,reinterpret_cast<uintptr_t>(__builtin_return_address(0)),GetCurrentThreadId(),o->frame(),o->scope);
        if(!valid)o->foreign();
        o->trace(12,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(thing),reinterpret_cast<uintptr_t>(__builtin_return_address(0)),reinterpret_cast<uintptr_t>(output),epoch,self,24);
    }
    bool result=o->unpack(self,thing,output);
    if(valid){uint32_t decoded[23]={};if(!read(reinterpret_cast<uintptr_t>(output),decoded,92))o->foreign();
        else if(attack_unpack){if(!o->attack_lineage.unpack_after(result,decoded))o->foreign();}else o->lineage.unpack_after(result,decoded);}
    if(ours)o->trace(15,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(thing),0,result?1:0,epoch,output,23);
    return result;
}
bool Observer::install(){
    if(current||GetCurrentThreadId()!=binding.thread||GetCurrentProcessId()!=binding.pid||!actor.generation)return false;
    hooks={
    {0x571d90,reinterpret_cast<void*>(move_hook),reinterpret_cast<void**>(&move),"\x83\xec\x5c\x8b\x44\x24\x64\x56\x6a\x01\x50\x8b\xf1",13,{}},
    {0x76d9d0,reinterpret_cast<void*>(private_move_hook),reinterpret_cast<void**>(&private_move),"\x56\x8b\xf1\x57\x8b\x7e\x08\x8b\xcf",9,{}},
    {0x54b0a0,reinterpret_cast<void*>(stop_hook),reinterpret_cast<void**>(&stop),"\x83\xec\x5c\x8b\x44\x24\x60\x56\x6a\x01\x50\x8b\xf1",13,{}},
    {0x721ad0,reinterpret_cast<void*>(private_stop_hook),reinterpret_cast<void**>(&private_stop),"\x83\xec\x08\x55\x8b\xe9\x8b\x45\x08\x8b\x48\x04",12,{}},
    {0x838820,reinterpret_cast<void*>(transfer_hook),reinterpret_cast<void**>(&transfer),"\x8b\x81\x8c\0\0\0\x85\xc0\x74\x4f\x56\x8b\xb1\x90\0\0\0",17,{}},
    {0x8d8880,reinterpret_cast<void*>(add_hook),reinterpret_cast<void**>(&add),"\x83\xec\x24\x56\x8b\x74\x24\x2c\x8b\x46\x04",11,{}},
    {0x8cd630,reinterpret_cast<void*>(remove_hook),reinterpret_cast<void**>(&remove),"\x83\xec\x34\x53\x57\x8b\x7c\x24\x40\x8b\x47\x04",12,{}},
    {0x7640f0,reinterpret_cast<void*>(stance_hook),reinterpret_cast<void**>(&stance),"\x83\xec\x14\x53\x8b\xd9\x8b\x43\x08",9,{}},
    {0x76e690,reinterpret_cast<void*>(attack_hook),reinterpret_cast<void**>(&attack),"\x83\x7c\x24\x04\0\x55\x56\x8b\xf1\x8b\x6e\x08",12,{}},
    {0x572280,reinterpret_cast<void*>(attack_facade_hook),reinterpret_cast<void**>(&attack_facade),"\x83\xec\x5c\x8b\x44\x24\x68\x56\x6a\x01\x50\x8b\xf1",13,{}},
    {0x6f7c60,reinterpret_cast<void*>(weapon_get_hook),reinterpret_cast<void**>(&weapon_get),"\x53\x8b\x59\x28\x56\x8b\x71\x24\x3b\xf3\x57",11,{}},
    {0x830220,reinterpret_cast<void*>(copy_hook),reinterpret_cast<void**>(&copy),"\x53\x55\x56\x8b\xf1\x57\x8b\x7c\x24\x14",10,{}},
    {0x830320,reinterpret_cast<void*>(unpack_hook),reinterpret_cast<void**>(&unpack),"\x83\xec\x0c\x53\x56\x8b\xf1\x8b\x46\x14",10,{}},
    {0x787500,reinterpret_cast<void*>(dispatch_hook),reinterpret_cast<void**>(&dispatch),"\x83\xec\x60\x53\x55\x8b\xd9\x8b\x43\xdc",10,{}},
    {0x693960,reinterpret_cast<void*>(yield_hook),reinterpret_cast<void**>(&yield),"\x83\xec\x5c\x8b\x44\x24\x68\x56\x6a\x01\x50\x8b\xf1",13,{}}};
    for(auto& h:hooks)if(!read(h.address,h.before,h.count)||std::memcmp(h.before,h.signature,h.count))return false;
    auto init=MH_Initialize();if(init!=MH_OK&&init!=MH_ERROR_ALREADY_INITIALIZED)return false;
    for(auto& h:hooks){if(MH_CreateHook(reinterpret_cast<void*>(h.address),h.detour,h.original)!=MH_OK)return false;h.made=true;}
    current=this;for(auto& h:hooks){if(MH_EnableHook(reinterpret_cast<void*>(h.address))!=MH_OK){close_after_verified_release();return false;}h.enabled=true;}
    installed=true;return true;
}
}
std::unique_ptr<NearNativeObserver> make_near_native_observer(Binding b,NativeBinding n,Actor a,Memory& memory,NativeAttackAdmission& admission,std::function<void(const HookTrace&)> sink){return std::make_unique<Observer>(b,n,a,memory,admission,std::move(sink));}
}
