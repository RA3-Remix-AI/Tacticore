// Isolated original producer/geometry integration; active v1 source unchanged.
#include "near_native_factory.h"
#include "near_native_admission.h"
#include "near_build_policy.h"
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
#include <set>
#include <map>
namespace tacticore::runtime::near_combat {
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
class AdmissionRelay final:public NativeAttackAdmission {
    NativeAdmission* implementation_=nullptr;
public:
    void bind(NativeAdmission& a){
        if(implementation_)refuse("near_admission_already_bound");
        implementation_=&a;
    }
    bool permit(const Lease& l,const Intent& i,const Target& t,AttackBoundary b)override{
        return implementation_&&implementation_->permit(l,i,t,b);
    }
};
class NativeExecution final:public Execution {
    Binding binding_;TargetRegistry& registry_;TargetReader& targets_;WeaponReader& weapons_;
    NativeAdmission* admission_=nullptr;NearNativeObserver* observer_=nullptr;CombatSink sink_;
public:
    NativeExecution(Binding b,TargetRegistry& registry,TargetReader& targets,WeaponReader& weapons,CombatSink sink):
        binding_(b),registry_(registry),targets_(targets),weapons_(weapons),sink_(std::move(sink)){}
    void bind(NativeAdmission& a,NearNativeObserver& o){
        if(admission_||observer_)refuse("near_execution_already_bound");
        admission_=&a;observer_=&o;
    }
    CombatFacts facts(const Sample& actor,const Id& key)override{
        CombatFacts f;Target target{};
        if(actor.binding==binding_&&registry_.resolve(binding_,key,target))f.target=targets_.sample(target);
        f.weapon=weapons_.sample(actor.actor).facts;
        // No synthetic shot/damage producer: absence yields no effect credit.
        return f;
    }
    bool independent_attack_admission(const Lease& l,const Intent& i,const Observation&)override{
        Target t{};return admission_&&registry_.resolve(binding_,i.target_key,t)&&admission_->prepare(l,i,t);
    }
    AttackAcknowledgement attack_once(const Lease& l,const Intent& i,const Target& t)override{
        AttackAcknowledgement a;a.delivery=Delivery::NotSent;
        if(!admission_||!observer_||!admission_->permit(l,i,t,AttackBoundary::Facade))return a;
        return observer_->attack_once(l,i,t);
    }
    void mark_control_unknown(const Intent&,const char*)override{} // Owner retains the held/unknown state.
    void event(const Result& r,const char* kind,const Observation& o,const Withdrawal* w)override{
        if(sink_)sink_(r,kind,o,w);
    }
    WeaponSnapshot readonly_weapon(const Sample& actor,bool held){
        auto weapon=weapons_.sample(actor.actor);Observation o;o.actor=actor;o.actor_weapon=weapon.facts;
        Result r;r.frame=actor.frame;r.monotonic_ms=actor.monotonic_ms;r.held=held;
        r.reason=o.actor_weapon.identity_verified?"readonly_weapon_identity_observed":"readonly_weapon_unverified";
        // Unaccepted diagnostic event, not an Intent, effect or task receipt.
        event(r,"native_readonly_weapon",o,nullptr);
        return weapon;
    }
};
class Runtime final:public NearRuntime {
    Binding binding_;NativeBinding native_;LiveMemory memory_;Incarnations incarnations_;Endpoints endpoints_;
    GroundGeometry geometry_;NativeLandEndpoints land_;
    std::unique_ptr<NearBuildPolicy> policy_;TargetRegistry registry_;
    std::unique_ptr<TargetReader> targets_;std::unique_ptr<WeaponReader> weapons_;
    std::unique_ptr<NativeExecution> execution_;AdmissionRelay relay_;
    std::unique_ptr<NearNativeObserver> observer_;std::unique_ptr<MemoryIO> io_;
    std::unique_ptr<Owner> owner_;std::unique_ptr<NativeAdmission> admission_;Actor actor_{};
    std::function<void(const HookTrace&)> trace_;std::map<uint32_t,Target> contacts_;
    std::vector<ContactView> views_;uint32_t next_key_=1;uint64_t started_ms_=0;bool stopping_=false;
    uint32_t last_weapon_frame_=0,weapon_rows_=0;
    std::array<uint32_t,24> last_summary_{};std::vector<std::array<uint32_t,24>> last_keys_;
    uint32_t catalogue_rows_=0;bool catalogue_truncated_=false;
    void trace_land(const NativeLandEndpoints::Proof& p){
        if(!trace_)return;
        for(uint32_t i=0;i<3;i++){
            HookTrace t{};t.kind=29+i;t.frame=p.frame;t.thread=memory_.thread();t.self=actor_.update;t.target=actor_.thing;
            t.epoch_before=t.epoch_after=observer_->foreign_epoch();t.word_count=24;t.words=i==0?p.actor:i==1?p.raster:p.cell;trace_(t);
        }
    }
    void trace_weapon(const WeaponSnapshot& w){
        if(!trace_||!w.facts.identity_verified)return;
        // Dedicated diagnostic kind36, outside all original control witnesses.
        HookTrace t{};t.kind=36;t.frame=w.frame;t.thread=w.thread;t.self=w.entry;t.target=actor_.thing;t.word_count=24;
        t.epoch_before=t.epoch_after=observer_->foreign_epoch();
        t.words={actor_.object_id,w.frame,w.container,w.slot,w.index,w.entry,w.template_ptr,w.schema,w.header,w.asset,
            w.range_words[0],w.range_words[1],w.range_words[2],w.range_words[3],w.range_words[4],w.ammo,w.request_limit,
            w.state_machine,w.state,w.state_vtable,w.state_id,w.requested,w.flags,0x52564731};trace_(t);
    }
    void emit_catalogue(uint32_t kind,const std::array<uint32_t,24>& words){
        if(!trace_||catalogue_truncated_)return;
        HookTrace t{};memory_.read(native_.logic+0x50,&t.frame,4);t.thread=memory_.thread();t.self=actor_.update;t.target=actor_.thing;
        t.epoch_before=t.epoch_after=observer_->foreign_epoch();t.word_count=24;
        if(catalogue_rows_>=512){t.kind=28;t.words[0]=1;t.words[1]=512;t.words[2]=catalogue_rows_;catalogue_truncated_=true;}
        else {t.kind=kind;t.words=words;catalogue_rows_++;}trace_(t);
    }
    void trace_catalogue(){
        Point home{};if(!trace_||!memory_.read(actor_.thing+0x38,&home,12)||!finite(home))return;
        auto data=endpoints_.diagnostics(home);data.summary[9]=owner_->movement_status().held;
        auto key=data.summary;std::fill(key.begin()+10,key.end(),0);
        if(key!=last_summary_){emit_catalogue(26,data.summary);last_summary_=key;}
        for(size_t i=0;i<data.points.size();i++){
            auto point_key=data.points[i];point_key[2]=0;std::fill(point_key.begin()+8,point_key.end(),0);point_key[18]=data.points[i][18];
            if(i>=last_keys_.size()){last_keys_.push_back(point_key);emit_catalogue(27,data.points[i]);}
            else if(last_keys_[i]!=point_key){last_keys_[i]=point_key;emit_catalogue(27,data.points[i]);}
        }
    }
    void retire_all_contacts(){for(const auto& row:contacts_)registry_.retire(row.second);contacts_.clear();views_.clear();}
    void observe_contacts(){
        views_.clear();auto actor=io_->sample();
        if(!actor.identity||!actor.actor_birth_verified||!actor.live_list_member||actor.paused){retire_all_contacts();return;}
        auto start=memory_.monotonic_ms();uint32_t first=0;
        if(!memory_.read(native_.logic+0xb4,&first,4)){retire_all_contacts();return;}
        std::vector<uint32_t> things;std::set<uint32_t> seen;auto cursor=first;
        while(cursor){
            uint32_t vt=0,next=0;
            if(things.size()>=20000||cursor%4||!seen.insert(cursor).second||!memory_.read(cursor,&vt,4)||vt!=0xc4db60
                ||!memory_.read(cursor+0x7c,&next,4)){retire_all_contacts();return;}
            things.push_back(cursor);cursor=next;
        }
        uint32_t after=0,frame=0;
        if(!memory_.read(native_.logic+0xb4,&after,4)||after!=first||!memory_.read(native_.logic+0x50,&frame,4)||frame!=actor.frame){retire_all_contacts();return;}
        for(auto it=contacts_.begin();it!=contacts_.end();){
            if(!seen.count(it->second.thing)){registry_.retire(it->second);it=contacts_.erase(it);}else ++it;
        }
        for(auto thing:things){
            if(memory_.monotonic_ms()-start>50||views_.size()>=64)break;
            uint32_t tpl=0,hash=0,owner=0,id=0,update=0;
            if(!memory_.read(thing+4,&tpl,4)||!memory_.read(tpl+8,&hash,4)||hash!=0x19ab11af
                ||!memory_.read(thing+0x418,&owner,4)||owner==native_.owner||!memory_.read(thing+0xdc,&id,4)
                ||!memory_.read(thing+0x374,&update,4))continue;
            Target target{};auto found=contacts_.find(id);
            if(found!=contacts_.end())target=found->second;
            else {
                if(next_key_==UINT32_MAX)continue;
                ContactCandidate candidate{{binding_.host[0],binding_.host[1],0x4e43,next_key_++},id,thing,tpl,update,owner,hash};
                auto pair=targets_->observe_candidate(candidate);if(!pair.valid())continue;
                try{target=registry_.admit(pair);contacts_.emplace(id,target);}catch(const std::invalid_argument&){continue;}
            }
            auto observed=targets_->sample(target);
            if(!observed.visible){contacts_.erase(id);continue;}
            views_.push_back({target.key,target.type_hash,observed.visibility_frame,observed.visibility_monotonic_ms,observed.xyz,observed.hp});
        }
    }
    Receipt refuse_command(const Command& c,const char* why)const{
        auto r=owner_->movement_status();r.command=c.command;r.task=c.task;r.lease=c.lease;r.sequence=c.sequence;r.accepted=false;r.reason=why;return r;
    }
public:
    Runtime(const NativeBootstrap& request,std::function<void(const Event&)> events,std::function<void(const HookTrace&)> trace,CombatSink combat):
        binding_(request.original.binding),native_(request.original.native),memory_(binding_),endpoints_(binding_),geometry_(binding_,native_,memory_),
        land_(binding_,native_,memory_,endpoints_,[this](const NativeLandEndpoints::Proof& p){trace_land(p);}),registry_(binding_),trace_(std::move(trace)){
        const auto& boot=request.original;
        if(request.schema!=2||request.mod_path[1023]||request.visibility_path[1023]||request.template_audit_path[1023]
            ||!(memory_.current_binding()==binding_)||!exact_game()||boot.actor.generation||boot.actor.born_frame||boot.experimental_flags)
            refuse("near_bootstrap_identity_or_schema_unverified");
        policy_=NearBuildPolicy::verify_current_game(binding_,request.mod_path,request.visibility_path,request.template_audit_path);
        if(!policy_)refuse("near_exact_build_source_policy_unverified");
        auto production=producer(boot);auto& r=production.receipt;Actor candidate=boot.actor;
        if(candidate.thing!=r.object||candidate.object_id!=r.object_id||candidate.owner!=r.object_owner||candidate.type_hash!=r.object_hash)
            refuse("near_birth_actor_tuple_mismatch");
        auto dormant=make_near_native_observer(binding_,native_,candidate,memory_,relay_);
        MemoryIO birth(binding_,native_,candidate,incarnations_,memory_,*dormant,*dormant,endpoints_,{});
        auto a=birth.birth_observation(),b=birth.birth_observation();
        PaidBirth paid{boot.producer.command,boot.producer.task,boot.producer.sequence,r.object_id,r.object,r.object_owner,r.object_hash,a.frame,r.completion_frame,r.cost,r.paid,true,r.created==1,r.completed==1};
        actor_=incarnations_.register_paid_birth(paid,a,b);endpoints_.record(a,b);land_.bind_actor(actor_);
        targets_=std::make_unique<TargetReader>(binding_,native_,memory_,*policy_,registry_);
        weapons_=std::make_unique<WeaponReader>(binding_,native_,memory_,*policy_);
        execution_=std::make_unique<NativeExecution>(binding_,registry_,*targets_,*weapons_,std::move(combat));
        observer_=make_near_native_observer(binding_,native_,actor_,memory_,relay_,trace_);
        io_=std::make_unique<MemoryIO>(binding_,native_,actor_,incarnations_,memory_,*observer_,*observer_,land_,std::move(events),trace_);
        owner_=std::make_unique<Owner>(binding_,*io_,*execution_,boot.persisted_sequence,::tacticore::runtime::Limits{});
        admission_=std::make_unique<NativeAdmission>(binding_,*owner_,*io_,memory_,*targets_,*weapons_);
        execution_->bind(*admission_,*observer_);relay_.bind(*admission_);started_ms_=GetTickCount64();
    }
    bool activate(){return observer_->install();}
    bool safe_no_hooks()const{return observer_->no_hooks_enabled();}
    Receipt submit(const Command& c)override{
        if(c.operation==Operation::ReconcileRelease||c.operation==Operation::ReconcileReturnHome||c.operation==Operation::DiagnosticForeignMove)
            return refuse_command(c,"near_composite_recovery_not_qualified");
        const auto now=GetTickCount64();const bool work=c.operation==Operation::Reserve||c.operation==Operation::MoveHold;
        if(work&&(stopping_||now<started_ms_||now-started_ms_>=90000||c.expires_monotonic_ms>started_ms_+120000))
            return refuse_command(c,"near_runtime_no_new_work_at_lifetime_boundary");
        return owner_->submit(c);
    }
    Result submit(const Intent& i,const Command& withdrawal)override{
        auto now=GetTickCount64();
        if(stopping_||now<started_ms_||now-started_ms_>=90000||i.expires_monotonic_ms>started_ms_+120000){
            auto r=owner_->combat_status();r.command=i.command;r.task=i.task;r.lease=i.lease;r.sequence=i.sequence;
            r.held=owner_->movement_status().held;r.accepted=false;r.reason="near_runtime_no_new_attack_at_lifetime_boundary";return r;
        }
        return owner_->submit(i,withdrawal);
    }
    void tick()override{
        auto now=GetTickCount64();if(now<started_ms_||now-started_ms_>=150000)request_stop();owner_->tick();
    }
    void request_stop()override{stopping_=true;owner_->request_stop();}
    Receipt movement_status()const override{return owner_->movement_status();}
    Result combat_status()const override{return owner_->combat_status();}
    uint64_t last_sequence()const override{return owner_->last_sequence();}
    Actor actor()const override{return actor_;}Sample observation()override{return io_->sample();}
    bool close_verified()override{return !owner_->movement_status().held&&!owner_->combat_status().held&&observer_->close_after_verified_release();}
    uint32_t active_callbacks()const override{return observer_->active_callbacks();}uint32_t restored_mask()const override{return observer_->restored_mask();}
    void observe_endpoints()override{
        auto a=geometry_.sample(),b=geometry_.sample();bool valid=a.verified&&b.verified&&a.frame==b.frame&&a.occupied==b.occupied;
        endpoints_.begin_frame(valid);
        if(valid){
            for(auto point:b.occupied)endpoints_.occupy(point);
            for(const auto& first:a.foot){auto found=std::find_if(b.foot.begin(),b.foot.end(),[&](const Sample& s){return s.actor==first.actor;});
                if(found!=b.foot.end())endpoints_.record_native_foot(first,*found,native_.script_team);}
        }
        trace_catalogue();observe_contacts();
        auto own=io_->sample();
        if(own.identity&&own.actor_birth_verified&&own.frame>=last_weapon_frame_&&own.frame-last_weapon_frame_>=30&&weapon_rows_<128){
            last_weapon_frame_=own.frame;weapon_rows_++;trace_weapon(execution_->readonly_weapon(own,owner_->movement_status().held));
        }
    }
    std::vector<Point> approved_targets()const override{
        Point home{};if(!local_read(reinterpret_cast<void*>(actor_.thing+0x38),&home,12))return {};return land_.candidates(home);
    }
    std::vector<ContactView> visible_contacts()const override{
        std::vector<ContactView> result;uint32_t logic=0,frame=0;
        if(GetCurrentThreadId()!=binding_.thread||!local_read(reinterpret_cast<void*>(0xcd8ce4),&logic,4)||logic!=native_.logic
            ||!local_read(reinterpret_cast<void*>(logic+0x50),&frame,4))return result;
        const auto now=GetTickCount64();
        for(const auto& v:views_)if(frame>=v.frame&&frame-v.frame<=2&&now>=v.monotonic_ms&&now-v.monotonic_ms<=250)result.push_back(v);
        return result;
    }
};
}
std::unique_ptr<NearRuntime> create_near_runtime(const NativeBootstrap& boot,std::function<void(const Event&)> events,
    std::function<void(const HookTrace&)> trace,CombatSink combat){
    std::unique_ptr<Runtime> runtime;
    try{runtime=std::make_unique<Runtime>(boot,std::move(events),std::move(trace),std::move(combat));}
    catch(const FactoryError&){throw;}
    catch(const BirthAdmissionError& error){throw FactoryError(error.what(),true);}
    catch(const std::exception&){throw FactoryError("near_native_factory_admission_refused",true);}
    // Allocate quarantine capacity before activation, so even allocation failure
    // cannot discard a graph already referenced by an installed trampoline.
    static auto* quarantine=new std::vector<std::unique_ptr<NearRuntime>>;
    try{quarantine->reserve(quarantine->size()+1);}catch(...){throw FactoryError("near_quarantine_allocation_failed",true);}
    static HMODULE pinned=nullptr;
    if(!pinned&&!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,
        reinterpret_cast<LPCWSTR>(&create_near_runtime),&pinned))throw FactoryError("near_factory_module_pin_failed",true);
    bool activated=false;try{activated=runtime->activate();}catch(const std::exception&){}
    if(activated)return runtime;
    bool safe=runtime->safe_no_hooks();if(!safe){runtime->close_verified();safe=runtime->safe_no_hooks();}
    if(!safe)quarantine->push_back(std::move(runtime));
    throw FactoryError("near_observer_install_refused",safe);
}
}
