#pragma once
#include "protocol.h"
#include <cstring>
#include <atomic>

namespace tacticore::runtime {
// Single actor and game thread. No TLS aggregates, ambient whitelist or native
// command suppression. Facts are produced by passive hook wrappers around the
// real facade/copy/unpack/dispatch/private Move pipeline.
class MoveLineage {
public:
    struct Context {uint32_t command=0,kind=0;};
private:
    Point goal_{};uint32_t thread_=0,thing_=0,update_=0,generation_=0,issued_frame_=0,kind_=0;std::atomic<uint32_t> epoch_{0};
    bool armed_=false,facade_=false,pending_=false,unpacked_=false,delivered_=false,dispatch_seen_=false;
    uint32_t input_=0,output_=0;std::array<uint32_t,23> command_{},decoded_{};std::array<uint32_t,24> stored_{};
    Context context_{};
    static bool zeros(const uint32_t* x,unsigned a,unsigned b){for(unsigned i=a;i<=b;i++)if(x[i])return false;return true;}
    bool current(uint32_t thread,uint32_t frame)const{return armed_&&thread==thread_&&frame>=issued_frame_&&frame-issued_frame_<=900;}
public:
    MoveLineage(uint32_t thread,uint32_t thing,uint32_t update):thread_(thread),thing_(thing),update_(update){}
    void external_thread_foreign(){epoch_.fetch_add(1,std::memory_order_relaxed);}
    void foreign(){external_thread_foreign();armed_=facade_=pending_=unpacked_=delivered_=dispatch_seen_=false;context_={};}
    uint32_t epoch()const{return epoch_.load(std::memory_order_relaxed);}bool delivered()const{return kind_==0&&delivered_;}
    bool stop_delivered()const{return kind_==5&&delivered_;}
    bool pending()const{return pending_;}
    bool stopped_context_idle()const{return stop_delivered()&&!facade_&&!pending_&&!unpacked_&&!context_.kind;}
    void clear_for_verified_native_preemption(){armed_=facade_=pending_=unpacked_=delivered_=dispatch_seen_=false;context_={};}
    void stop_observed_empty_slot(){armed_=facade_=pending_=unpacked_=false;context_={};}
    bool arm(Point goal,uint32_t thread,uint32_t frame){
        if(thread!=thread_){external_thread_foreign();return false;}
        if(thread!=thread_||!finite(goal)||generation_==0xffffffffu){foreign();return false;}
        goal_=goal;kind_=0;issued_frame_=frame;generation_++;armed_=true;facade_=pending_=unpacked_=delivered_=dispatch_seen_=false;input_=output_=0;context_={};return true;
    }
    bool arm_stop(uint32_t thread,uint32_t frame){if(!arm({},thread,frame))return false;kind_=5;return true;}
    bool stop_facade_enter(uint32_t self,uint32_t source,uint32_t thread,uint32_t frame,bool own_scope){
        if(thread!=thread_){external_thread_foreign();return false;}
        bool ok=kind_==5&&current(thread,frame)&&own_scope&&self==update_+0x24&&source==1&&!facade_;
        if(ok)facade_=true;else foreign();return ok;
    }
    bool facade_enter(uint32_t self,Point goal,uint32_t source,uint32_t thread,uint32_t frame,bool own_scope){
        if(thread!=thread_){external_thread_foreign();return false;}
        bool ok=kind_==0&&current(thread,frame)&&own_scope&&self==update_+0x24&&goal==goal_&&source==1&&!facade_;if(ok)facade_=true;else foreign();return ok;
    }
    void facade_exit(){facade_=false;if(!pending_&&!delivered_)foreign();}
    bool pure(const uint32_t* c)const{return c&&c[0]==kind_&&c[1]==1&&!std::memcmp(c+2,&goal_,12)&&zeros(c,5,9)&&zeros(c,11,13)&&zeros(c,15,18)&&c[20]==0&&c[21]==0&&reinterpret_cast<const unsigned char*>(c)[0x58]==1;}
    static bool stored_payload(const uint32_t* s,const uint32_t* c){return !std::memcmp(s,c,24)&&zeros(s,6,10)&&zeros(s,12,14)&&!std::memcmp(s+16,c+15,16)&&s[21]==0&&s[22]==c[21]&&reinterpret_cast<const unsigned char*>(s)[0x5c]==reinterpret_cast<const unsigned char*>(c)[0x58];}
    Context context()const{return context_;}
    bool dispatch_enter(uint32_t self,uint32_t address,const uint32_t* c,uint32_t caller,uint32_t thread,uint32_t frame,bool own_scope){
        if(thread!=thread_){external_thread_foreign();return false;}
        bool direct=current(thread,frame)&&self==update_+0x24&&facade_&&own_scope&&!dispatch_seen_&&!delivered_&&pure(c)&&(kind_!=5||caller==0x54b0c5);
        bool deferred=current(thread,frame)&&self==update_+0x24&&!own_scope&&!facade_&&pending_&&unpacked_&&!delivered_&&caller==0x7da0d9&&address==output_&&c&&!std::memcmp(c,decoded_.data(),92)&&pure(c);
        if(direct){dispatch_seen_=true;input_=address;std::memcpy(command_.data(),c,92);context_={address,1};return true;}
        if(deferred){unpacked_=false;context_={address,2};return true;}
        foreign();return false;
    }
    void dispatch_exit(Context prior){if(context_.kind==2&&!delivered_)foreign();context_=prior;}
    bool private_move(uint32_t self,uint32_t point_address,Point point,uint32_t path,float limit,uint32_t source,uint32_t caller,uint32_t thread,uint32_t frame,bool own_scope){
        if(thread!=thread_){external_thread_foreign();return false;}
        uint32_t bits=0;std::memcpy(&bits,&limit,4);
        bool ok=kind_==0&&current(thread,frame)&&!delivered_&&self==update_&&point==goal_&&source==1&&path==0&&bits==0x7f7fffff&&caller==0x6d3b7d&&point_address==context_.command+8&&((own_scope&&facade_&&context_.kind==1)||(!own_scope&&pending_&&context_.kind==2&&context_.command==output_));
        if(!ok){foreign();return false;}delivered_=true;pending_=false;return true;
    }
    bool private_stop(uint32_t self,uint32_t source,uint32_t caller,uint32_t thread,uint32_t frame,bool own_scope){
        if(thread!=thread_){external_thread_foreign();return false;}
        bool ok=kind_==5&&current(thread,frame)&&!delivered_&&self==update_&&source==1&&caller==0x787791&&
            ((own_scope&&facade_&&context_.kind==1)||(!own_scope&&pending_&&context_.kind==2&&context_.command==output_));
        if(!ok){foreign();return false;}delivered_=true;pending_=false;return true;
    }
    bool copy_before(uint32_t self,uint32_t address,const uint32_t* before,const uint32_t* c,uint32_t caller,uint32_t thread,uint32_t frame,bool own_scope){
        if(thread!=thread_){external_thread_foreign();return false;}
        bool ok=current(thread,frame)&&self==update_+0x310&&own_scope&&facade_&&context_.kind==1&&context_.command==address&&input_==address&&caller==0x787d42&&!pending_&&!delivered_&&before&&before[0]==0xffffffffu&&pure(c)&&!std::memcmp(c,command_.data(),92);if(!ok)foreign();return ok;
    }
    bool copy_after(const uint32_t* before,const uint32_t* after,const uint32_t* c){
        bool ok=armed_&&after&&before&&std::memcmp(before,after,96)&&stored_payload(after,c);if(ok){std::memcpy(stored_.data(),after,96);pending_=true;}else foreign();return ok;
    }
    bool unpack_before(uint32_t self,uint32_t thing,uint32_t output,const uint32_t* stored,uint32_t caller,uint32_t thread,uint32_t frame,bool own_scope){
        if(thread!=thread_){external_thread_foreign();return false;}
        bool ok=current(thread,frame)&&self==update_+0x310&&thing==thing_&&!own_scope&&pending_&&!unpacked_&&!facade_&&!context_.kind&&!delivered_&&caller==0x7da0b3&&stored&&!std::memcmp(stored,stored_.data(),96);
        if(ok)output_=output;else foreign();return ok;
    }
    bool unpack_after(bool native_return,const uint32_t* decoded){
        bool ok=armed_&&native_return&&pure(decoded)&&stored_payload(stored_.data(),decoded);if(ok){std::memcpy(decoded_.data(),decoded,92);unpacked_=true;}else foreign();return ok;
    }
};
}
