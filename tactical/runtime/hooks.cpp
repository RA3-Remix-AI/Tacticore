#include "hooks.h"
#include "lineage.h"
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
using Yield=void(__attribute__((thiscall))*)(void*,void*,float*,uint32_t);
class Observer;Observer* current=nullptr;
class Observer:public NativeObserver {
public:
    Binding binding;NativeBinding native;Actor actor;MoveLineage lineage;
    YieldReader yield_reader;YieldContext yield_context{};PendingNativeYield pending_yield;bool yield_experiment=false,fault_experiment=false;
    volatile LONG active=0;bool installed=false,scope=false,borrow_attempted=false,return_observed=false;std::atomic<bool> held{false};Action operation=Action::Stop;uint32_t desired_stance=0,mask=0;
    Move move=nullptr;PrivateMove private_move=nullptr;Stop stop=nullptr,private_stop=nullptr;Transfer transfer=nullptr;Member add=nullptr,remove=nullptr;Stance stance=nullptr;Copy copy=nullptr,dispatch=nullptr;Unpack unpack=nullptr;Attack attack=nullptr;
    Yield yield=nullptr;
    struct Hook {uint32_t address;void* detour;void** original;const char* signature;size_t count;unsigned char before[20];bool made=false,enabled=false;};
    std::vector<Hook> hooks;
    std::function<void(const HookTrace&)> trace_sink;
    Observer(Binding b,NativeBinding n,Actor a,Memory& memory,bool experiment,std::function<void(const HookTrace&)> sink,bool fault):binding(b),native(n),actor(a),lineage(b.thread,a.thing,a.update),yield_reader(b,n,a,memory),yield_experiment(experiment),fault_experiment(fault),trace_sink(std::move(sink)){}
    ~Observer()override{if(no_hooks_enabled()){for(auto& hook:hooks)if(hook.made)MH_RemoveHook(reinterpret_cast<void*>(hook.address));if(current==this)current=nullptr;}}
    bool ours(uintptr_t self,bool facade=false)const{return held&&self==actor.update+(facade?0x24:0);}
    bool own(Action a)const{return GetCurrentThreadId()==binding.thread&&scope&&operation==a;}
    void foreign(){if(GetCurrentThreadId()==binding.thread){pending_yield.clear();lineage.foreign();}else lineage.external_thread_foreign();}
    uint32_t frame()const{return word(native.logic+0x50);}
    bool automatic_stop(uint32_t source)const{return source==2&&(own(Action::HoldStance)||own(Action::RestoreStance));}
    bool stopping(uint32_t source)const{return (source==1&&own(Action::Stop))||automatic_stop(source);}
    void trace(uint32_t kind,uint32_t self,uint32_t target,uint32_t caller,uint32_t source,uint32_t before,const void* raw=nullptr,uint32_t count=0){
        if(!trace_sink)return;
        HookTrace t{};t.frame=frame();t.thread=GetCurrentThreadId();t.kind=kind;t.self=self;t.target=target;t.caller=caller;
        t.operation=static_cast<uint32_t>(operation);t.scope=scope;t.source=source;t.epoch_before=before;t.epoch_after=lineage.epoch();
        if(raw&&count<=24&&read(reinterpret_cast<uintptr_t>(raw),t.words.data(),count*4))t.word_count=count;
        trace_sink(t);
    }
    bool installed_and_originals_verified()const override{return installed&&current==this;}
    uint32_t foreign_epoch()const override{return lineage.epoch();}
    bool normal_move_owned()const override{return lineage.delivered();}
    bool normal_stop_owned()const override{return lineage.stop_delivered();}
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
        if(a==Action::Borrow){borrow_attempted=true;return_observed=false;held=true;}
        if(a==Action::Move&&!lineage.arm(point,GetCurrentThreadId(),frame()))throw std::runtime_error("normal_move_arm_failed");
        if(a==Action::Stop&&!lineage.arm_stop(GetCurrentThreadId(),frame()))throw std::runtime_error("normal_stop_arm_failed");
    }
    void end(Action a)override{
        scope=false;
        if(a==Action::TransferBack&&word(actor.thing+0x414)==native.default_team
            &&word(word(native.default_team+4)+8)==native.owner){return_observed=true;held=false;}
    }
    bool independent_quiescence_verified()const override{return installed&&!scope&&active==0&&!lineage.pending()&&!pending_yield.pending()&&!yield_context.active;}
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
            team,native.default_team,return_observed,owned,native.script_team))return false;
        for(unsigned i=0;i<hooks.size();i++){auto& h=hooks[i];if(h.enabled){if(MH_DisableHook(reinterpret_cast<void*>(h.address))!=MH_OK)return false;h.enabled=false;}
            unsigned char observed[20]={};if(!read(h.address,observed,h.count)||std::memcmp(observed,h.before,h.count))return false;mask|=1u<<i;}
        if(active)return false;
        installed=false;current=nullptr;return true;
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
void __attribute__((fastcall)) attack_hook(void* self,void*,void* target,uint32_t shots,uint32_t source){Callback cb;auto o=cb.o;bool ours=o->ours(reinterpret_cast<uintptr_t>(self));auto before=o->lineage.epoch();if(ours){o->foreign();o->trace(9,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(target),reinterpret_cast<uintptr_t>(__builtin_return_address(0)),source,before,&shots,1);}o->attack(self,target,shots,source);}
void __attribute__((fastcall)) dispatch_hook(void* self,void*,void* command){
    Callback cb;auto o=cb.o;auto thread=GetCurrentThreadId();auto caller=reinterpret_cast<uintptr_t>(__builtin_return_address(0));
    auto prior=thread==o->binding.thread?o->lineage.context():MoveLineage::Context{};
    bool owned=false,yield_dispatch=false,observe_yield=false;bool ours=o->ours(reinterpret_cast<uintptr_t>(self),true);auto before=o->lineage.epoch();
    if(ours){
        uint32_t words[23]={};bool got=read(reinterpret_cast<uintptr_t>(command),words,92);
        bool expected_stop=got&&words[0]==5&&o->automatic_stop(words[1]);
        observe_yield=thread==o->binding.thread&&got&&o->yield_context.active&&words[0]==48&&caller==0x6939aa;
        if(thread==o->binding.thread&&got&&native_yield_admissible(o->yield_context,words,reinterpret_cast<uintptr_t>(self),caller,thread,o->frame())){
            o->yield_context.dispatched=true;yield_dispatch=true;
        }else if(!expected_stop){
            owned=got&&o->lineage.dispatch_enter(reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(command),words,caller,thread,o->frame(),o->own(Action::Move)||o->own(Action::Stop));
            if(!got)o->foreign();
        }
        o->trace(10,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(command),caller,words[1],before,command,23);
    }
    o->dispatch(self,command);
    if(owned)o->lineage.dispatch_exit(prior);
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
    c.own_stop_idle=o->lineage.stopped_context_idle();c.frame=o->frame();c.thread=thread;c.self=reinterpret_cast<uintptr_t>(self);
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
void __attribute__((fastcall)) copy_hook(void* self,void*,void* command){Callback cb;auto o=cb.o;bool ours=o->held&&reinterpret_cast<uintptr_t>(self)==o->actor.update+0x310;uint32_t before[24]={},input[23]={};auto epoch=o->lineage.epoch();bool valid=false;if(ours){valid=read(reinterpret_cast<uintptr_t>(self),before,96)&&read(reinterpret_cast<uintptr_t>(command),input,92)&&o->lineage.copy_before(reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(command),before,input,reinterpret_cast<uintptr_t>(__builtin_return_address(0)),GetCurrentThreadId(),o->frame(),o->own(Action::Move)||o->own(Action::Stop));if(!valid)o->foreign();}if(ours){o->trace(11,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(command),reinterpret_cast<uintptr_t>(__builtin_return_address(0)),0,epoch,command,23);o->trace(13,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(command),reinterpret_cast<uintptr_t>(__builtin_return_address(0)),0,epoch,before,24);}o->copy(self,command);if(valid){uint32_t after[24]={};if(read(reinterpret_cast<uintptr_t>(self),after,96))o->lineage.copy_after(before,after,input);else o->foreign();}if(ours)o->trace(14,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(command),reinterpret_cast<uintptr_t>(__builtin_return_address(0)),0,epoch,self,24);}
bool __attribute__((fastcall)) unpack_hook(void* self,void*,void* thing,void* output){Callback cb;auto o=cb.o;bool ours=o->held&&reinterpret_cast<uintptr_t>(self)==o->actor.update+0x310&&o->lineage.pending();auto epoch=o->lineage.epoch();bool valid=false;if(ours){uint32_t stored[24]={};valid=read(reinterpret_cast<uintptr_t>(self),stored,96)&&o->lineage.unpack_before(reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(thing),reinterpret_cast<uintptr_t>(output),stored,reinterpret_cast<uintptr_t>(__builtin_return_address(0)),GetCurrentThreadId(),o->frame(),o->scope);if(!valid)o->foreign();}if(ours)o->trace(12,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(thing),reinterpret_cast<uintptr_t>(__builtin_return_address(0)),reinterpret_cast<uintptr_t>(output),epoch,self,24);bool result=o->unpack(self,thing,output);if(valid){uint32_t decoded[23]={};if(read(reinterpret_cast<uintptr_t>(output),decoded,92))o->lineage.unpack_after(result,decoded);else o->foreign();}if(ours)o->trace(15,reinterpret_cast<uintptr_t>(self),reinterpret_cast<uintptr_t>(thing),reinterpret_cast<uintptr_t>(__builtin_return_address(0)),result?1:0,epoch,output,23);return result;}
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
std::unique_ptr<NativeObserver> make_native_observer(Binding b,NativeBinding n,Actor a,Memory& memory,bool experiment,std::function<void(const HookTrace&)> sink,bool fault){return std::make_unique<Observer>(b,n,a,memory,experiment,std::move(sink),fault);}
}
