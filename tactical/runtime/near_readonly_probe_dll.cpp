// This DLL only reads native facts. It installs no game-entry detours, calls no
// game SDK function, and never acquires a unit. The outer WH_GETMESSAGE hook
// dispatches this private diagnostic protocol on the actual game thread.
#include "near_readonly_probe.h"
#include <wincrypt.h>
#include <cstdio>
#include <cwchar>
#include <memory>
#include <set>
#include <map>

namespace rt=tacticore::runtime;namespace np=rt::readonly_probe;namespace nc=rt::near_combat;
static np::Shared* shared=nullptr;static HANDLE mapping=nullptr;static HMODULE pin=nullptr;
static np::Bootstrap frozen{};static uint32_t last_frame=0,next_key=1,pulses=0;
static std::map<uint32_t,nc::Target> contacts;
static std::map<uint32_t,np::Row> prior_own;
static std::unique_ptr<nc::TargetRegistry> registry;
static bool local_read(uint32_t address,void* output,uint32_t bytes){
    SIZE_T got=0;return address>=0x10000&&bytes&&uint64_t(address)+bytes<=0xffffffffull
        &&ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(address),output,bytes,&got)&&got==bytes;
}
class LiveMemory:public rt::Memory {
public:
    bool read(uint32_t p,void* out,uint32_t bytes)override{return local_read(p,out,bytes);}
    rt::Binding current_binding()override{
        auto b=frozen.binding;b.pid=GetCurrentProcessId();b.thread=GetCurrentThreadId();FILETIME c{},e{},k{},u{};
        b.process_start=GetProcessTimes(GetCurrentProcess(),&c,&e,&k,&u)?(uint64_t(c.dwHighDateTime)<<32)|c.dwLowDateTime:0;return b;
    }
    uint32_t thread()override{return GetCurrentThreadId();}uint64_t monotonic_ms()override{return GetTickCount64();}
};
static LiveMemory memory;
class SourceReviewedConscript:public nc::TemplatePolicy {
public:
    // Exact build/visibility capability and conservative source audit are
    // independently hash-checked at bootstrap. This is not a compiled-stealth
    // decompilation or an attack capability. All unknown classes stay denied.
    bool reviewed(const rt::Binding& b,uint32_t tpl,uint32_t hash)const override{return b==frozen.binding&&tpl&&hash==0x19ab11af;}
};
static SourceReviewedConscript policy;
static bool file_hash(const wchar_t* path,const char* expected){
    HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;
    HCRYPTPROV provider=0;HCRYPTHASH hash=0;bool okay=false;
    if(CryptAcquireContextW(&provider,nullptr,nullptr,PROV_RSA_AES,CRYPT_VERIFYCONTEXT)&&CryptCreateHash(provider,CALG_SHA_256,0,0,&hash)){
        BYTE data[65536]{};DWORD count=0;BOOL result=TRUE;
        while((result=ReadFile(file,data,sizeof(data),&count,nullptr))&&count){if(!CryptHashData(hash,data,count,0)){result=FALSE;break;}}
        BYTE digest[32]{};DWORD size=32;char text[65]{};
        if(result&&CryptGetHashParam(hash,HP_HASHVAL,digest,&size,0)){for(unsigned i=0;i<32;i++)std::snprintf(text+2*i,3,"%02x",digest[i]);okay=!std::strcmp(text,expected);}
    }
    if(hash){CryptDestroyHash(hash);}if(provider){CryptReleaseContext(provider,0);}CloseHandle(file);return okay;
}
static uint32_t word(uint32_t address,bool& complete){uint32_t value=0;if(!local_read(address,&value,4))complete=false;return value;}
static bool root(){
    bool okay=true;auto& n=frozen.native;auto& b=frozen.binding;
    bool valid=memory.current_binding()==b&&b.player==3&&word(0xcd8ce4,okay)==n.logic&&word(n.logic,okay)==0xbeb630
        &&word(n.owner,okay)==0xc5bce0&&word(n.owner+0x20,okay)==3&&word(n.owner+0x10,okay)==n.player_template
        &&word(n.owner+0x90,okay)==n.ai&&word(n.ai,okay)==0xc60f60&&word(n.ai+8,okay)==n.owner
        &&word(n.ai+0x8b0,okay)==n.personality&&word(n.personality+0x18,okay)==n.personality_id;
    return valid&&okay;
}
static void publish(np::Row row){
    auto index=InterlockedIncrement(&shared->count)-1;
    if(index>=static_cast<LONG>(np::capacity)){InterlockedExchange(&shared->overflow,1);return;}
    row.ticket=0;shared->rows[index]=row;MemoryBarrier();InterlockedExchange(&shared->rows[index].ticket,index+1);
}
static bool own_once(uint32_t thing,np::Row& row){
    bool okay=true;auto w=[&](uint32_t p){return word(p,okay);};auto& n=frozen.native;auto& x=row.words;
    row={};row.kind=1;row.frame=w(n.logic+0x50);row.thread=GetCurrentThreadId();row.monotonic_ms=GetTickCount64();
    x[0]=w(thing+0xdc);x[1]=thing;x[2]=w(w(thing+4)+8);x[3]=w(thing+0x418);x[4]=w(thing+0x374);x[36]=w(thing+4);
    if(!root()||w(thing)!=0xc4db60||!x[0]||x[2]!=0x19ab11af||x[3]!=n.owner||w(x[4])!=0xc48670||w(x[4]+8)!=thing||w(x[4]+0x24)!=0xc48528)return false;
    x[37]=w(x[4]+0x3c);x[38]=w(x[37]+4);x[5]=w(x[38]+4);x[6]=w(x[38]);
    x[7]=w(w(thing+0x380)+0x38);x[8]=w(x[4]+0x50);x[9]=w(x[4]+0x150);
    x[32]=w(thing+0x414);x[33]=n.default_team;x[34]=n.script_team;
    auto body=w(thing+0x33c);if(!local_read(body+4,&row.hp,4)||!local_read(thing+0x38,&row.xyz,12))okay=false;
    x[35]=(w(thing+0x48)&4)&&!w(thing+0x238);
    if(!okay||!std::isfinite(row.hp)||row.hp<=0||!rt::finite(row.xyz))return false;
    x[10]=w(thing+0x37c);auto first=w(x[10]+0x24),end=w(x[10]+0x28);
    if(w(x[10]+8)!=thing||!first||end<first||end-first>256||(end-first)%4)return false;
    for(auto cursor=first;cursor<end;cursor+=4){
        auto slot=w(cursor);if(w(slot)!=0xc3a6e0||w(0xc3a704)!=0x6dbe80||w(0xc3a708)!=0x6f88e0)return false;
        auto index=w(slot+0x14);if(index>5)return false;if(index==5)continue;
        auto entry=w(w(slot+0x94)+4*index);if(!entry)continue;
        x[11]=slot;x[12]=index;x[13]=entry;break;
    }
    if(!x[13]||w(x[13])!=0xc2e324||w(x[13]+8)!=x[11])return false;
    x[14]=w(x[13]+4);x[15]=w(x[14]+4);x[16]=w(x[15]);x[17]=w(x[16]+4);x[18]=w(x[13]+0x1c);x[19]=w(x[13]+0x24);
    x[20]=w(x[13]+0x64);x[21]=w(x[20]+4);x[22]=w(x[21]);x[23]=w(x[21]+4);
    uint8_t requested=0xff;if(!local_read(x[13]+0x60,&requested,1))okay=false;x[24]=requested;
    x[25]=w(x[20]+0x24);x[26]=w(x[20]+0x80);x[27]=w(x[21]+0x18);x[28]=w(x[21]+0x20);x[29]=w(x[20]+0x78);
    x[30]=okay&&w(x[14])==0xc37534&&w(x[16])==0x94d4d96e&&w(x[13]+0xc)==x[0]
        &&x[25]==thing&&x[26]==x[13]&&x[27]==x[20]&&x[28]==x[13]&&w(x[20])==0xc1fc50;
    x[31]=x[30]&&x[17]==0x447ea26e&&x[18]>=1&&x[18]<=3&&x[22]==0xc1fd18&&x[23]==0&&x[24]==0&&!(x[29]&0xffff);
    return okay&&x[30]&&w(thing+0xdc)==x[0]&&w(thing+4)==x[36]&&w(thing+0x418)==x[3]
        &&w(thing+0x374)==x[4]&&w(thing+0x37c)==x[10]&&w(x[13]+4)==x[14]&&w(x[13]+8)==x[11]
        &&w(x[13]+0x64)==x[20]&&w(x[20]+4)==x[21]&&w(n.logic+0x50)==row.frame&&root()&&okay;
}
static void sample(){
    if(!root()){shared->error=20;shared->state=4;return;}
    bool okay=true;auto frame=word(frozen.native.logic+0x50,okay);auto paused=word(frozen.native.logic+0x15c,okay);
    np::Row heartbeat{};heartbeat.kind=4;heartbeat.frame=frame;heartbeat.thread=GetCurrentThreadId();heartbeat.monotonic_ms=GetTickCount64();heartbeat.words[0]=paused;
    if(!okay||!frame){shared->error=21;shared->state=4;return;}
    if(paused||frame==last_frame){if(++pulses%10==0)publish(heartbeat);return;}last_frame=frame;
    auto start=GetTickCount64();std::vector<uint32_t> things;std::set<uint32_t> seen;
    auto head=word(frozen.native.logic+0xb4,okay),cursor=head;
    while(cursor){
        if(things.size()>=20000||cursor%4||!seen.insert(cursor).second||word(cursor,okay)!=0xc4db60){shared->error=22;shared->state=4;return;}
        things.push_back(cursor);cursor=word(cursor+0x7c,okay);
    }
    if(!okay||word(frozen.native.logic+0xb4,okay)!=head){shared->error=23;shared->state=4;return;}
    nc::TargetReader reader(frozen.binding,frozen.native,memory,policy,*registry);
    for(auto thing:things){
        if(GetTickCount64()-start>50)break;
        auto tpl=word(thing+4,okay);if(word(tpl+8,okay)!=0x19ab11af)continue;
        auto owner=word(thing+0x418,okay),id=word(thing+0xdc,okay),update=word(thing+0x374,okay);
        if(!okay)break;
        if(owner==frozen.native.owner){
            np::Row a{},b{};bool valid=own_once(thing,a)&&own_once(thing,b)&&a.frame==b.frame&&a.words==b.words&&a.xyz==b.xyz&&a.hp==b.hp;
            if(!valid){shared->own_rejected++;np::Row rejected{};rejected.kind=5;rejected.frame=frame;rejected.thread=GetCurrentThreadId();rejected.monotonic_ms=GetTickCount64();rejected.words=a.words;rejected.words[30]=rejected.words[31]=0;
                if(prior_own.count(id)==0||prior_own[id].words!=rejected.words){publish(rejected);prior_own[id]=rejected;}continue;}
            auto prior=prior_own.find(id);
            if(prior==prior_own.end()||prior->second.words!=b.words||frame-prior->second.frame>=30){publish(b);prior_own[id]=b;}
            continue;
        }
        auto found=contacts.find(id);nc::Target t{};
        if(found==contacts.end()){
            nc::ContactCandidate candidate{{shared->token,next_key++,frozen.binding.session[0],0x524f},id,thing,tpl,update,owner,0x19ab11af};
            auto pair=reader.observe_candidate(candidate);if(!pair.valid())continue;
            try{t=registry->admit(pair);contacts.emplace(id,t);}catch(...){shared->registry_refusals++;continue;}
        }else t=found->second;
        auto target=reader.sample(t);
        if(!target.visible){np::Row lost{};lost.kind=3;lost.frame=frame;lost.thread=GetCurrentThreadId();lost.monotonic_ms=GetTickCount64();lost.words[0]=t.object_id;for(unsigned i=0;i<4;i++)lost.words[1+i]=t.key[i];publish(lost);contacts.erase(id);continue;}
        np::Row visible{};visible.kind=2;visible.frame=target.visibility_frame;visible.thread=GetCurrentThreadId();visible.monotonic_ms=target.visibility_monotonic_ms;
        visible.xyz=target.xyz;visible.hp=target.hp;visible.words[0]=id;visible.words[1]=thing;visible.words[2]=t.type_hash;visible.words[3]=owner;visible.words[4]=update;visible.words[5]=tpl;
        visible.words[6]=t.observed_frame;visible.words[7]=static_cast<uint32_t>(t.incarnation);visible.words[8]=static_cast<uint32_t>(t.incarnation>>32);
        visible.words[9]=target.visibility_frame;visible.words[10]=target.visibility_complete;visible.words[11]=frozen.binding.player;for(unsigned i=0;i<4;i++)visible.words[12+i]=t.key[i];
        publish(visible);shared->visible_samples++;
    }
    auto elapsed=static_cast<uint32_t>(GetTickCount64()-start);shared->max_step_ms=std::max(shared->max_step_ms,elapsed);
    if(++pulses%10==0)publish(heartbeat);
}
static void initialize(uint32_t token){
    if(shared&&(shared->state==1||shared->state==2||shared->active))return;
    wchar_t name[100]{};std::swprintf(name,100,L"Local\\TacticoreReadonly1_%lu_%u",GetCurrentProcessId(),token);
    auto candidate_mapping=OpenFileMappingW(FILE_MAP_ALL_ACCESS,FALSE,name);if(!candidate_mapping)return;
    auto candidate=static_cast<np::Shared*>(MapViewOfFile(candidate_mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(np::Shared)));
    if(!candidate){CloseHandle(candidate_mapping);return;}
    if(candidate->magic_word!=np::magic||candidate->protocol!=np::version||candidate->structure_size!=sizeof(np::Shared)||candidate->token!=token||candidate->state!=0
        ||candidate->bootstrap.binding.pid!=GetCurrentProcessId()||candidate->bootstrap.binding.thread!=GetCurrentThreadId()){
        UnmapViewOfFile(candidate);CloseHandle(candidate_mapping);return;}
    if(shared){UnmapViewOfFile(shared);CloseHandle(mapping);}shared=candidate;mapping=candidate_mapping;frozen=shared->bootstrap;shared->active=1;shared->state=1;shared->callback_thread=GetCurrentThreadId();
    wchar_t game[32768]{};GetModuleFileNameW(nullptr,game,32768);
    bool paths=frozen.mod_path[1023]==0&&frozen.capability_path[1023]==0&&frozen.safety_path[1023]==0;
    bool valid=paths&&frozen.duration_ms>=1000&&frozen.duration_ms<=90000&&frozen.policy_schema==2&&frozen.binding.player==3
        &&file_hash(game,"ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165")
        &&file_hash(frozen.mod_path,"2d7873e1b2d2c79950ff9da70b5452b1210370a6d6cbec1eaa69201a7d3d0665")
        &&file_hash(frozen.capability_path,"667ee10c6eb9549a33d63a02aff6bd45df9438ca309b563ac89e3cc9273476c8")
        &&file_hash(frozen.safety_path,"1d14e41e10224fb2a8215a2321a7fbbbeae8434b8c006a80fd314f4a11e7719e")&&root();
    if(valid&&!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,reinterpret_cast<LPCWSTR>(&initialize),&pin))valid=false;
    if(valid){try{registry=std::make_unique<nc::TargetRegistry>(frozen.binding);contacts.clear();prior_own.clear();last_frame=0;next_key=1;pulses=0;shared->started_ms=shared->last_ms=GetTickCount64();shared->state=2;}catch(...){shared->error=25;shared->state=4;}}
    else {shared->error=10;shared->state=4;}
    InterlockedDecrement(&shared->active);
}
extern "C" __declspec(dllexport) LRESULT CALLBACK TacticoreReadonlyControl(int code,WPARAM wp,LPARAM lp){
    if(code>=0&&wp==PM_REMOVE&&lp){auto msg=reinterpret_cast<MSG*>(lp);
        if(msg->message==np::bootstrap_message&&msg->wParam==np::magic)initialize(static_cast<uint32_t>(msg->lParam));
        else if(msg->message==np::pulse_message&&shared&&msg->wParam==shared->token){
            InterlockedIncrement(&shared->active);
            if(shared->state==2){
                bool same=np::same(shared->bootstrap,frozen)&&shared->magic_word==np::magic&&shared->protocol==np::version&&GetCurrentThreadId()==frozen.binding.thread;
                if(!same){shared->error=11;shared->state=4;}
                else if(shared->stop||GetTickCount64()-shared->started_ms>=frozen.duration_ms){shared->state=3;}
                else {try{sample();}catch(...){shared->error=24;shared->state=4;}shared->last_ms=GetTickCount64();}
            }
            InterlockedExchange(&shared->pulse_acknowledged,static_cast<LONG>(msg->lParam));InterlockedDecrement(&shared->active);
        }
    }
    return CallNextHookEx(nullptr,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE h,DWORD why,LPVOID){if(why==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(h);return TRUE;}
