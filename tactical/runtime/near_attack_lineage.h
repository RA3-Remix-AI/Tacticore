#pragma once
// Native opcode11 provenance, separate from MoveLineage and published v1.
// This proves a submitted/delivered command, never a shot or damage event.
#include "near_combat.h"
#include <atomic>

namespace tacticore::runtime::near_combat {
class AttackLineage {
public:
    struct Context {uint32_t command=0,kind=0;};
    class PendingReplacement {
        Id command_{};uint32_t thread_=0,frame_=0,update_=0;std::array<uint32_t,24> before_{};bool valid_=false;
        PendingReplacement(const Intent& i,uint32_t thread,uint32_t frame,const uint32_t* before):command_(i.command),thread_(thread),frame_(frame),update_(i.actor.update),valid_(true){std::memcpy(before_.data(),before,96);}
        friend class AttackLineage;
    public:
        PendingReplacement()=default;
        bool valid()const{return valid_;}
        bool matches(const uint32_t* before,uint32_t update,uint32_t thread,uint32_t frame)const{
            return valid_&&before&&update==update_&&thread==thread_&&frame==frame_&&!std::memcmp(before,before_.data(),96);
        }
    };
private:
    Binding binding_;Actor actor_;Intent intent_{};Target target_{};
    std::atomic<bool> failed_{false};
    bool used_=false,armed_=false,facade_=false,facade_closed_=false,dispatched_=false,pending_=false,unpacking_=false,unpacked_=false,delivered_=false,copying_=false,cancelled_=false;
    uint32_t issued_frame_=0,input_=0,output_=0;
    Context context_{};
    std::array<uint32_t,23> command_{},decoded_{};
    std::array<uint32_t,24> stored_{},copy_before_{};
    static bool zeros(const uint32_t* x,unsigned a,unsigned b){for(unsigned i=a;i<=b;i++)if(x[i])return false;return true;}
    bool reject(){failed_.store(true,std::memory_order_release);return false;}
    bool current(uint32_t thread,uint32_t frame)const{
        return !failed_.load(std::memory_order_acquire)&&armed_&&thread==binding_.thread&&frame>=issued_frame_
            &&frame<intent_.expires_frame&&frame<intent_.lease_deadline_frame&&frame-issued_frame_<=60;
    }
    bool pure(const uint32_t* c)const{
        return c&&c[0]==11&&c[1]==1&&zeros(c,2,4)&&c[5]==target_.thing&&zeros(c,6,9)&&zeros(c,11,13)
            &&c[15]==0&&c[16]==0&&c[17]==1&&c[18]==0&&c[20]==0&&c[21]==0
            &&reinterpret_cast<const uint8_t*>(c)[0x58]==1;
    }
    bool stored_payload(const uint32_t* s,const uint32_t* c)const{
        // Native 830220 converts c+14 target pointer into object ID; unpack
        // 830320 later resolves it again. Preserve the actual native mapping.
        return s&&pure(c)&&!std::memcmp(s,c,20)&&s[5]==target_.object_id&&zeros(s,6,10)&&zeros(s,12,14)
            &&!std::memcmp(s+16,c+15,16)&&s[21]==0&&s[22]==c[21]
            &&reinterpret_cast<const uint8_t*>(s)[0x5c]==reinterpret_cast<const uint8_t*>(c)[0x58];
    }
public:
    AttackLineage(Binding b,Actor a):binding_(b),actor_(a){}
    void foreign(){failed_.store(true,std::memory_order_release);}
    bool failed()const{return failed_.load(std::memory_order_acquire);}
    bool pending()const{return !failed()&&pending_;}
    bool submitted()const{return !failed()&&facade_closed_&&(pending_||delivered_);}
    bool delivered()const{return !failed()&&delivered_;}
    bool cancelled()const{return !failed()&&cancelled_;}
    Context context()const{return context_;}
    bool arm(const Intent& i,const Target& t,uint32_t thread,uint32_t frame){
        if(failed()||used_||thread!=binding_.thread||!binding_.thread||!(i.actor==actor_)||!nonzero(i.command)||!nonzero(i.task)
            ||!nonzero(i.lease)||!i.sequence||i.target_key!=t.key||!nonzero(t.key)||!t.object_id||!t.thing||!t.incarnation
            ||!t.observed_frame||frame<t.observed_frame||!actor_.generation||!actor_.born_frame||frame<actor_.born_frame
            ||frame>=i.expires_frame||frame>=i.lease_deadline_frame)return reject();
        used_=armed_=true;intent_=i;target_=t;issued_frame_=frame;return true;
    }
    bool facade_enter(uint32_t self,uint32_t target,uint32_t count,uint32_t source,uint32_t thread,uint32_t frame,bool own_scope){
        if(!current(thread,frame)||!own_scope||facade_||facade_closed_||self!=actor_.update+0x24||target!=target_.thing||count!=1||source!=1)return reject();
        facade_=true;return true;
    }
    bool facade_exit(){
        if(failed()||!facade_||(!pending_&&!delivered_))return reject();
        facade_=false;facade_closed_=true;return true;
    }
    bool dispatch_enter(uint32_t self,uint32_t address,const uint32_t* c,uint32_t caller,uint32_t thread,uint32_t frame,bool own_scope){
        if(!current(thread,frame)||!address||self!=actor_.update+0x24||!pure(c))return reject();
        bool direct=own_scope&&facade_&&!dispatched_&&!delivered_&&caller==0x5722b5;
        bool deferred=!own_scope&&!facade_&&facade_closed_&&pending_&&unpacked_&&!delivered_&&caller==0x7da0d9
            &&address==output_&&!std::memcmp(c,decoded_.data(),92);
        if(direct){input_=address;dispatched_=true;std::memcpy(command_.data(),c,92);context_={address,1};return true;}
        if(deferred){unpacked_=false;context_={address,2};return true;}
        return reject();
    }
    bool dispatch_exit(Context prior){
        if(failed()||!context_.kind||(context_.kind==2&&!delivered_))return reject();
        context_=prior;return true;
    }
    bool copy_before(uint32_t self,uint32_t address,const uint32_t* before,const uint32_t* c,uint32_t caller,uint32_t thread,uint32_t frame,bool own_scope){
        if(!current(thread,frame)||!own_scope||!facade_||context_.kind!=1||context_.command!=address||input_!=address
            ||self!=actor_.update+0x310||caller!=0x787d42||pending_||delivered_||copying_||!before||before[0]!=0xffffffffu
            ||!pure(c)||std::memcmp(c,command_.data(),92))return reject();
        std::memcpy(copy_before_.data(),before,96);copying_=true;return true;
    }
    bool copy_after(const uint32_t* before,const uint32_t* after,const uint32_t* c){
        if(failed()||!copying_||!before||!after||!c||std::memcmp(before,copy_before_.data(),96)||!std::memcmp(before,after,96)
            ||std::memcmp(c,command_.data(),92)||!stored_payload(after,c))return reject();
        std::memcpy(stored_.data(),after,96);copying_=false;pending_=true;return true;
    }
    bool unpack_before(uint32_t self,uint32_t thing,uint32_t output,const uint32_t* stored,uint32_t caller,uint32_t thread,uint32_t frame,bool own_scope){
        if(!current(thread,frame)||own_scope||!pending_||!facade_closed_||facade_||unpacking_||unpacked_||context_.kind||delivered_
            ||self!=actor_.update+0x310||thing!=actor_.thing||!output||caller!=0x7da0b3||!stored||std::memcmp(stored,stored_.data(),96))return reject();
        output_=output;unpacking_=true;return true;
    }
    bool unpack_after(bool native_return,const uint32_t* decoded){
        if(failed()||!unpacking_||!native_return||!stored_payload(stored_.data(),decoded))return reject();
        std::memcpy(decoded_.data(),decoded,92);unpacking_=false;unpacked_=true;return true;
    }
    bool private_attack(uint32_t self,uint32_t target,uint32_t count,uint32_t source,uint32_t caller,uint32_t thread,uint32_t frame,bool own_scope){
        bool direct=own_scope&&facade_&&context_.kind==1;
        bool deferred=!own_scope&&pending_&&context_.kind==2&&context_.command==output_;
        if(!current(thread,frame)||delivered_||self!=actor_.update||target!=target_.thing||count!=1||source!=1
            ||caller!=0x785dd0||(!direct&&!deferred))return reject();
        delivered_=true;pending_=false;return true;
    }
    PendingReplacement pending_replacement(const uint32_t* before,uint32_t thread,uint32_t frame)const{
        // Cancelling expired work is a safety Stop, never renewed attack work.
        // Caller still needs the original owner's native Stop admission.
        if(failed()||thread!=binding_.thread||!pending_||!facade_closed_||facade_||context_.kind||copying_||unpacking_||unpacked_||delivered_
            ||cancelled_||frame<issued_frame_||frame-issued_frame_>900||!before||std::memcmp(before,stored_.data(),96))return {};
        return PendingReplacement(intent_,thread,frame,before);
    }
    bool cancel_after_stop_copy(const PendingReplacement& proof,const uint32_t* before,const uint32_t* after,const uint32_t* stop,uint32_t thread,uint32_t frame){
        auto fresh=pending_replacement(before,thread,frame);
        bool pure_stop=stop&&stop[0]==5&&stop[1]==1&&zeros(stop,2,9)&&zeros(stop,11,13)&&zeros(stop,15,18)
            &&stop[20]==0&&stop[21]==0&&reinterpret_cast<const uint8_t*>(stop)[0x58]==1;
        bool stored_stop=after&&pure_stop&&!std::memcmp(after,stop,24)&&zeros(after,6,10)&&zeros(after,12,14)
            &&!std::memcmp(after+16,stop+15,16)&&after[21]==0&&after[22]==stop[21]
            &&reinterpret_cast<const uint8_t*>(after)[0x5c]==reinterpret_cast<const uint8_t*>(stop)[0x58];
        if(!fresh.valid()||proof.command_!=intent_.command||!proof.matches(before,actor_.update,thread,frame)||!stored_stop)return reject();
        pending_=armed_=false;cancelled_=true;return true;
    }
};
}
