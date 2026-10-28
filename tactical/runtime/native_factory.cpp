#include "native_factory.h"
#include "shared_channel.h"
#include "hooks.h"
#include "endpoints.h"
#include "geometry.h"
#include "land_geometry.h"
#include "../../production/persistent/shared.h"
#include <windows.h>
#include <wincrypt.h>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <vector>
#include <algorithm>
namespace tacticore::runtime {
namespace {
[[noreturn]] void refuse(const char* reason){throw FactoryError(reason,true);}
bool local_read(const void* source,void* destination,size_t count){SIZE_T n=0;return source&&ReadProcessMemory(GetCurrentProcess(),source,destination,count,&n)&&n==count;}
class LiveMemory:public Memory {
    Binding binding_;
public:
    explicit LiveMemory(Binding b):binding_(b){}
    bool read(uint32_t address,void* destination,uint32_t n)override{return local_read(reinterpret_cast<void*>(address),destination,n);}
    Binding current_binding()override{
        auto b=binding_;b.pid=GetCurrentProcessId();b.thread=GetCurrentThreadId();FILETIME create{},exit{},kernel{},user{};
        b.process_start=GetProcessTimes(GetCurrentProcess(),&create,&exit,&kernel,&user)?(static_cast<uint64_t>(create.dwHighDateTime)<<32)|create.dwLowDateTime:0;return b;
    }
    uint32_t thread()override{return GetCurrentThreadId();}uint64_t monotonic_ms()override{return GetTickCount64();}
};
bool exact_game(){
    char path[32768]={};if(!GetModuleFileNameA(nullptr,path,sizeof(path)))return false;
    HANDLE file=CreateFileA(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);if(file==INVALID_HANDLE_VALUE)return false;
    HCRYPTPROV provider=0;HCRYPTHASH hash=0;bool okay=false;
    if(CryptAcquireContextA(&provider,nullptr,nullptr,PROV_RSA_AES,CRYPT_VERIFYCONTEXT)&&CryptCreateHash(provider,CALG_SHA_256,0,0,&hash)){
        unsigned char bytes[65536];DWORD n=0;BOOL result=TRUE;
        while((result=ReadFile(file,bytes,sizeof(bytes),&n,nullptr))&&n){if(!CryptHashData(hash,bytes,n,0)){result=FALSE;break;}}
        unsigned char digest[32]={};DWORD size=32;char text[65]={};
        if(result&&CryptGetHashParam(hash,HP_HASHVAL,digest,&size,0)){for(unsigned i=0;i<32;i++)std::snprintf(text+2*i,3,"%02x",digest[i]);okay=!std::strcmp(text,"ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165");}
    }
    if(hash){CryptDestroyHash(hash);}if(provider){CryptReleaseContext(provider,0);}CloseHandle(file);return okay;
}
struct ProducerHeader {
    uint32_t magic,version,pid,thread,owner,ai,personality,personality_id,player_template,start_low,start_high,session[4],commander[4],total_budget,reserve_floor,min_interval,start_frame;
    LONG phase,stop_requested,active,heartbeat,request_state;::Command request;
    uint32_t reply_index,reply_error,last_seq,last_frame,last_accepted_frame,spent,count,restore_mask,error,callback_thread;
};
static_assert(sizeof(ProducerHeader)==offsetof(::Persistent,ledger),"Original producer header layout changed");
struct ProducerSnapshot {ProducerHeader header{};::Receipt receipt{};};
ProducerSnapshot producer(const channel::Bootstrap& boot){
    char name[100]={};std::snprintf(name,sizeof(name),"Local\\RA3ProductionPersistent_%u",boot.binding.pid);
    HANDLE mapping=OpenFileMappingA(FILE_MAP_READ,FALSE,name);if(!mapping)refuse("runtime_producer_mapping_unavailable");
    auto view=static_cast<const ::Persistent*>(MapViewOfFile(mapping,FILE_MAP_READ,0,0,sizeof(::Persistent)));if(!view){CloseHandle(mapping);refuse("runtime_producer_mapping_unreadable");}
    ProducerSnapshot a{},b{};bool read=false;
    if(boot.producer.receipt_index<P_CAP){
        read=local_read(view,&a.header,offsetof(::Persistent,ledger))&&local_read(&view->ledger[boot.producer.receipt_index],&a.receipt,sizeof(::Receipt))&&local_read(&view->ledger[boot.producer.receipt_index],&b.receipt,sizeof(::Receipt))&&local_read(view,&b.header,offsetof(::Persistent,ledger));
    }
    UnmapViewOfFile(view);CloseHandle(mapping);
    auto& h=a.header;auto& r=a.receipt;auto& c=r.command;const auto& n=boot.native;
    bool header=read&&!std::memcmp(&a.header,&b.header,offsetof(::Persistent,ledger))&&!std::memcmp(&a.receipt,&b.receipt,sizeof(::Receipt))&&h.magic==P_MAGIC&&h.version==1&&h.pid==boot.binding.pid&&h.thread==boot.binding.thread&&h.callback_thread==h.thread&&((static_cast<uint64_t>(h.start_high)<<32)|h.start_low)==boot.binding.process_start&&h.owner==n.owner&&h.ai==n.ai&&h.personality==n.personality&&h.personality_id==n.personality_id&&h.player_template==n.player_template&&!std::memcmp(h.session,boot.binding.session.data(),16)&&!std::memcmp(h.commander,boot.binding.commander.data(),16)&&h.phase==1&&!h.stop_requested&&!h.error&&h.count<=P_CAP&&boot.producer.receipt_index<h.count&&GetTickCount()-static_cast<DWORD>(h.heartbeat)<=2000;
    bool paid=header&&!r.updates&&r.version>0&&r.state==2&&!r.error&&r.attempted==1&&r.preserved==1&&c.seq==boot.producer.sequence&&!std::memcmp(c.id,boot.producer.command.data(),16)&&!std::memcmp(c.task,boot.producer.task.data(),16)&&!std::memcmp(c.session,boot.binding.session.data(),16)&&!std::memcmp(c.commander,boot.binding.commander.data(),16)&&c.hash==0x19ab11af&&c.budget>=85&&c.budget<=1000&&c.reserve>=h.reserve_floor&&r.cost==85&&r.quoted_cost==85&&r.paid==85&&r.debit_count>0&&r.debit_count<=85&&!r.payment_error&&r.queue_id&&r.node&&r.created==1&&r.object&&r.object_id&&r.object_owner==n.owner&&r.object_hash==c.hash&&r.completed==1&&r.completion_frame&&r.live_samples&&static_cast<uint64_t>(r.cash)>=static_cast<uint64_t>(r.cost)+r.liability+c.reserve;
    if(!header){refuse("runtime_producer_header_unverified");}
    if(!paid){refuse("runtime_paid_native_birth_not_verified");}return a;
}
class Runtime:public NativeRuntime {
    Binding binding_;NativeBinding native_;LiveMemory memory_;Incarnations incarnations_;Endpoints endpoints_;
    GroundGeometry geometry_;
    NativeLandEndpoints land_;
    std::unique_ptr<NativeObserver> observer_;std::unique_ptr<MemoryIO> io_;std::unique_ptr<Controller> controller_;Actor actor_{};
    std::function<void(const HookTrace&)> catalogue_sink_;
    std::array<uint32_t,24> last_catalogue_summary_{};
    std::vector<std::array<uint32_t,24>> last_catalogue_keys_;
    uint32_t catalogue_emitted_=0;bool catalogue_truncated_=false;
    void trace_land(const NativeLandEndpoints::Proof& proof){
        if(!catalogue_sink_)return;
        for(uint32_t i=0;i<3;i++){
            HookTrace t{};t.kind=29+i;t.frame=proof.frame;t.thread=memory_.thread();t.self=actor_.update;t.target=actor_.thing;
            t.epoch_before=t.epoch_after=observer_->foreign_epoch();t.word_count=24;
            t.words=i==0?proof.actor:i==1?proof.raster:proof.cell;catalogue_sink_(t);
        }
    }
    void emit_catalogue(uint32_t kind,const std::array<uint32_t,24>& words){
        if(!catalogue_sink_||catalogue_truncated_)return;
        HookTrace t{};t.frame=0;memory_.read(native_.logic+0x50,&t.frame,4);t.thread=memory_.thread();
        t.self=actor_.update;t.target=actor_.thing;t.epoch_before=t.epoch_after=observer_->foreign_epoch();t.word_count=24;
        if(catalogue_emitted_>=512){t.kind=28;t.words[0]=1;t.words[1]=512;t.words[2]=catalogue_emitted_;catalogue_truncated_=true;}
        else {t.kind=kind;t.words=words;catalogue_emitted_++;}
        catalogue_sink_(t);
    }
    void trace_catalogue(){
        Point home{};if(!catalogue_sink_||!memory_.read(actor_.thing+0x38,&home,12)||!finite(home))return;
        auto data=endpoints_.diagnostics(home);data.summary[9]=controller_->status().held;
        auto summary_key=data.summary;std::fill(summary_key.begin()+10,summary_key.end(),0);
        if(summary_key!=last_catalogue_summary_){emit_catalogue(26,data.summary);last_catalogue_summary_=summary_key;}
        for(size_t i=0;i<data.points.size();i++){
            auto key=data.points[i];key[2]=0;std::fill(key.begin()+8,key.end(),0);key[18]=data.points[i][18];
            if(i>=last_catalogue_keys_.size()){last_catalogue_keys_.push_back(key);emit_catalogue(27,data.points[i]);}
            else if(last_catalogue_keys_[i]!=key){last_catalogue_keys_[i]=key;emit_catalogue(27,data.points[i]);}
        }
    }
public:
    Runtime(const channel::Bootstrap& boot,std::function<void(const Event&)> sink,std::function<void(const HookTrace&)> trace):binding_(boot.binding),native_(boot.native),memory_(boot.binding),endpoints_(boot.binding),geometry_(boot.binding,boot.native,memory_),land_(boot.binding,boot.native,memory_,endpoints_,[this](const NativeLandEndpoints::Proof& p){trace_land(p);}),catalogue_sink_(trace){
        if(!(memory_.current_binding()==binding_)||!exact_game()||boot.actor.generation||boot.actor.born_frame||boot.experimental_flags>2)refuse("runtime_bootstrap_identity_unverified");
        auto production=producer(boot);auto& r=production.receipt;
        Actor candidate=boot.actor;
        if(candidate.thing!=r.object||candidate.object_id!=r.object_id||candidate.owner!=r.object_owner||candidate.type_hash!=r.object_hash)refuse("runtime_birth_actor_tuple_mismatch");
        // A dormant observer supplies no authority during the read-only birth
        // samples. Only successfully installed originals enable action admission.
        auto dormant=make_native_observer(binding_,native_,candidate,memory_);
        MemoryIO birth(binding_,native_,candidate,incarnations_,memory_,*dormant,*dormant,endpoints_,{});
        auto a=birth.birth_observation(),b=birth.birth_observation();
        PaidBirth paid{boot.producer.command,boot.producer.task,boot.producer.sequence,r.object_id,r.object,r.object_owner,r.object_hash,a.frame,r.completion_frame,r.cost,r.paid,true,r.created==1,r.completed==1};
        actor_=incarnations_.register_paid_birth(paid,a,b);endpoints_.record(a,b);
        land_.bind_actor(actor_);
        observer_=make_native_observer(binding_,native_,actor_,memory_,boot.experimental_flags==1,std::move(trace),boot.experimental_flags==2);
        io_=std::make_unique<MemoryIO>(binding_,native_,actor_,incarnations_,memory_,*observer_,*observer_,land_,std::move(sink),catalogue_sink_);
        // Construct all potentially throwing holders before installing hooks.
        controller_=std::make_unique<Controller>(binding_,*io_,Limits{},boot.persisted_sequence);
    }
    bool activate(){return observer_->install();}
    bool safe_no_hooks()const{return observer_->no_hooks_enabled();}
    Controller& controller()override{return *controller_;}Actor actor()const override{return actor_;}
    bool close_verified()override{return !controller_->status().held&&observer_->close_after_verified_release();}
    uint32_t active_callbacks()const override{return observer_->active_callbacks();}uint32_t restored_mask()const override{return observer_->restored_mask();}
    void observe_endpoints()override{
        auto a=geometry_.sample(),b=geometry_.sample();
        bool valid=a.verified&&b.verified&&a.frame==b.frame&&a.occupied==b.occupied;
        endpoints_.begin_frame(valid);if(!valid){trace_catalogue();return;}
        for(auto p:b.occupied)endpoints_.occupy(p);
        // Continue independent native-foot observations during the lease.
        // Script-controlled units cannot create destinations with our motion.
        for(const auto& first:a.foot){
            auto found=std::find_if(b.foot.begin(),b.foot.end(),[&](const Sample& s){return s.actor==first.actor;});
            if(found!=b.foot.end())endpoints_.record_native_foot(first,*found,native_.script_team);
        }
        trace_catalogue();
    }
    std::vector<Point> approved_targets()const override{
        Point home{};if(!local_read(reinterpret_cast<void*>(actor_.thing+0x38),&home,12))return {};
        return land_.candidates(home);
    }
    Sample observation()override{return io_->sample();}
};
}
std::unique_ptr<NativeRuntime> create_runtime(const channel::Bootstrap& boot,std::function<void(const Event&)> sink,std::function<void(const HookTrace&)> trace){
    std::unique_ptr<Runtime> runtime;
    try{runtime=std::make_unique<Runtime>(boot,std::move(sink),std::move(trace));}
    catch(const FactoryError&){throw;}
    catch(const BirthAdmissionError& error){throw FactoryError(error.what(),true);}
    catch(const std::exception&){throw FactoryError("runtime_native_admission_refused",true);}
    bool activated=false;try{activated=runtime->activate();}catch(const std::exception&){}
    if(activated)return runtime;
    bool safe=runtime->safe_no_hooks();
    if(!safe){runtime->close_verified();safe=runtime->safe_no_hooks();}
    if(!safe){
        // Intentionally retain full owning state in this pinned process. Error
        // propagation must never free an object still referenced by trampolines.
        static auto* quarantined=new std::vector<std::unique_ptr<NativeRuntime>>;
        quarantined->push_back(std::move(runtime));
    }
    throw FactoryError("runtime_observer_install_refused",safe);
}
}
