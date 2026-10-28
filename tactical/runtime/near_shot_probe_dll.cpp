// New passive diagnostic: all three original functions are forwarded once.
// No SDK invocation, argument mutation, task attribution or control acquisition.
#include "near_shot_probe.h"
#include "near_shot_target_policy.h"
#include "MinHook.h"
#include <cstdio>
#include <cwchar>
#include <memory>
#include <set>
namespace rt=tacticore::runtime;namespace np=rt::shot_probe;namespace nc=rt::near_combat;
static np::Shared* shared=nullptr;static HANDLE mapping=nullptr;static HMODULE pinned=nullptr;
static np::Bootstrap frozen{};static bool closing=false;static uint64_t next_call=0;static uint32_t next_key=1;
static std::unique_ptr<nc::NearBuildPolicy> policy;static std::unique_ptr<nc::TargetRegistry> registry;
static std::unique_ptr<np::DiagnosticTargetPolicy> target_policy;
static std::map<uint32_t,nc::Target> contacts;
static std::array<uint32_t,20> capture_stages{};
static std::array<uint32_t,25> weapon_refusals{};
static std::map<std::pair<uint32_t,uint32_t>,uint32_t> refusal_rows;
static bool read(uint32_t p,void*out,uint32_t n){SIZE_T got=0;return p>=0x10000&&n&&uint64_t(p)+n<=0xffffffffull&&ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(p),out,n,&got)&&got==n;}
static uint32_t word(uint32_t p){uint32_t v=0;read(p,&v,4);return v;}
static uint32_t bits(float f){uint32_t v=0;std::memcpy(&v,&f,4);return v;}
class LiveMemory:public rt::Memory {
public:
    bool read(uint32_t p,void*out,uint32_t n)override{return ::read(p,out,n);}
    rt::Binding current_binding()override{auto b=frozen.binding;b.pid=GetCurrentProcessId();b.thread=GetCurrentThreadId();FILETIME c{},e{},k{},u{};b.process_start=GetProcessTimes(GetCurrentProcess(),&c,&e,&k,&u)?uint64_t(c.dwHighDateTime)<<32|c.dwLowDateTime:0;return b;}
    uint32_t thread()override{return GetCurrentThreadId();}uint64_t monotonic_ms()override{return GetTickCount64();}
};
static LiveMemory memory;
static bool root(){auto&b=frozen.binding;auto&n=frozen.native;return shared&&np::same(shared->bootstrap,frozen)&&memory.current_binding()==b&&b.player==3
    &&word(0xcd8ce4)==n.logic&&word(n.logic)==0xbeb630&&!word(n.logic+0x15c)&&word(n.owner)==0xc5bce0&&word(n.owner+0x20)==3
    &&word(n.owner+0x10)==n.player_template&&word(n.owner+0x90)==n.ai&&word(n.ai)==0xc60f60&&word(n.ai+8)==n.owner
    &&word(n.ai+0x8b0)==n.personality&&word(n.personality+0x18)==n.personality_id;}
static bool live(uint32_t thing){std::set<uint32_t> seen;auto cursor=word(frozen.native.logic+0xb4);while(cursor){if(seen.size()>=20000||cursor%4||!seen.insert(cursor).second||word(cursor)!=0xc4db60)return false;if(cursor==thing)return true;cursor=word(cursor+0x7c);}return false;}
static bool actor(uint32_t thing,rt::Actor& a){
    a={};a.thing=thing;a.object_id=word(thing+0xdc);a.template_ptr=word(thing+4);a.update=word(thing+0x374);a.owner=word(thing+0x418);a.type_hash=word(a.template_ptr+8);
    auto body=word(thing+0x33c);float hp=0;
    return root()&&thing&&a.object_id&&a.owner==frozen.native.owner&&a.type_hash==0x19ab11af&&word(thing)==0xc4db60
        &&word(a.update)==0xc48670&&word(a.update+8)==thing&&word(a.update+0x24)==0xc48528
        &&read(body+4,&hp,4)&&std::isfinite(hp)&&hp>0&&live(thing);
}
static void publish(np::Row r){if(!shared)return;auto i=InterlockedIncrement(&shared->count)-1;if(i>=LONG(np::capacity)){shared->overflow=1;closing=true;return;}r.ticket=0;shared->rows[i]=r;MemoryBarrier();InterlockedExchange(&shared->rows[i].ticket,i+1);}
static np::Row row(np::Kind kind,uint64_t id,uint64_t parent=0){np::Row r;r.kind=uint32_t(kind);r.frame=word(frozen.native.logic+0x50);r.thread=GetCurrentThreadId();r.monotonic_ms=GetTickCount64();r.call_id=id;r.parent_id=parent;return r;}
static void elapsed(uint64_t start){auto ms=GetTickCount64()-start;if(shared&&ms>shared->max_callback_ms)shared->max_callback_ms=ms>UINT32_MAX?UINT32_MAX:uint32_t(ms);}
static bool observing(){return shared&&shared->state==2&&!closing&&!shared->stop&&!shared->overflow&&policy&&registry&&root();}
struct Context {uint64_t id=0;uint32_t actor=0,target=0,entry=0,weapon_template=0,weapon_slot=0,body=0,body_vtable=0,source=0;nc::Target registered{};float hp=0;bool visible=false;};
static thread_local Context private_context{},fire_context{};
using Attack=void(__attribute__((thiscall))*)(void*,void*,uint32_t,uint32_t);
using Fire=void(__attribute__((thiscall))*)(void*,void*);
using Damage=void(__attribute__((thiscall))*)(void*,void*);
static Attack original_attack=nullptr;static Fire original_fire=nullptr;static Damage original_damage=nullptr;
static void weapon_refusal(const rt::Actor&a,const nc::WeaponReadDiagnostic&d,uint32_t origin,uint32_t caller){
    auto reason=uint32_t(d.failure);if(!reason||reason>=weapon_refusals.size())return;
    weapon_refusals[reason]++;
    // Bounded examples plus exact aggregate counts; no target reads/fields.
    if(refusal_rows[{reason,origin}]++>=4)return;
    auto r=row(np::Kind::WeaponRefusal,0);const auto&w=d.observed;auto&x=r.words;
    x[0]=a.thing;x[1]=a.object_id;x[2]=a.owner;x[3]=a.type_hash;x[4]=a.update;
    x[12]=w.entry;x[13]=w.ammo;x[14]=w.request_limit;x[15]=w.state_id;x[16]=w.asset;x[17]=w.template_ptr;x[18]=w.schema;
    x[19]=w.range_words[0];x[23]=w.state_vtable;x[26]=w.state_machine;x[27]=w.state;x[41]=caller;
    std::copy(w.range_words.begin(),w.range_words.end(),x.begin()+64);x[69]=w.slot;x[70]=w.index;x[71]=w.container;x[72]=w.header;
    x[73]=w.requested;x[74]=w.flags;x[88]=d.pass;x[89]=d.last_address;x[90]=reason;x[91]=d.last_value;
    x[92]=d.unreadable_address;x[93]=bits(d.expected_range);x[94]=origin;x[95]=0x57524631;publish(r);
}
static bool capture(uint32_t thing,uint32_t target,nc::WeaponSnapshot& w,Context& ctx,np::Row& r){
    capture_stages[0]++;rt::Actor a{};if(!actor(thing,a)){capture_stages[1]++;return false;}capture_stages[2]++;
    nc::WeaponReader reader(frozen.binding,frozen.native,memory,*policy);nc::WeaponReadDiagnostic diagnostic;
    w=reader.sample(a,&diagnostic);if(!w.facts.identity_verified){capture_stages[3]++;weapon_refusal(a,diagnostic,r.kind,r.words[41]);return false;}
    // Own firing facts are independent of whether a target can be admitted.
    // With no admitted target, publish no target identity/HP/position/context.
    ctx.actor=thing;ctx.target=target;ctx.entry=w.entry;ctx.weapon_template=w.template_ptr;ctx.weapon_slot=w.slot;auto&x=r.words;
    x[0]=thing;x[1]=a.object_id;x[2]=a.owner;x[3]=a.type_hash;x[4]=a.update;
    x[12]=w.entry;x[13]=w.ammo;x[14]=w.request_limit;x[15]=w.state_id;x[16]=w.asset;x[17]=w.template_ptr;x[18]=w.schema;x[19]=w.range_words[0];
    x[23]=w.state_vtable;x[24]=word(a.update+0x50);x[25]=word(thing+0x414);x[26]=w.state_machine;x[27]=w.state;
    x[86]=word(thing+0x48);x[87]=word(thing+0x238);x[93]=w.slot;x[94]=w.index;x[95]=0x53504f31;
    if(!target||next_key==UINT32_MAX){capture_stages[4]++;x[90]=1;return true;}
    auto target_type=word(word(target+4)+8);
    capture_stages[target_type==0x19ab11af?11:target_type==0x2c358c61?12:target_type==0x33026fa1?13:14]++;
    nc::TargetReader targets(frozen.binding,frozen.native,memory,*target_policy,*registry);
    auto id=word(target+0xdc);auto found=contacts.find(id);
    if(found!=contacts.end()){
        const auto&t=found->second;
        if(t.thing!=target||t.template_ptr!=word(target+4)||t.update!=word(target+0x374)||t.owner!=word(target+0x418)||t.type_hash!=word(word(target+4)+8)){x[90]=6;return true;}
        ctx.registered=t;
    }else{
        nc::ContactCandidate c{{frozen.binding.host[0],frozen.binding.host[1],0x5350,next_key++},id,target,word(target+4),word(target+0x374),word(target+0x418),word(word(target+4)+8)};
        auto pair=targets.observe_candidate(c);if(!pair.valid()){capture_stages[5]++;x[90]=2;return true;}
        try{ctx.registered=registry->admit(pair);contacts.emplace(id,ctx.registered);}catch(...){capture_stages[6]++;x[90]=3;return true;}
    }
    auto t=targets.sample(ctx.registered);if(!t.identity_verified||!t.visible||!t.visibility_complete||!t.live||!t.enemy){registry->retire(ctx.registered);contacts.erase(id);ctx.registered={};capture_stages[7]++;x[90]=4;return true;}capture_stages[8]++;
    ctx.body=word(target+0x33c);ctx.body_vtable=word(ctx.body);ctx.hp=t.hp;ctx.visible=true;
    x[5]=target;x[6]=t.identity.object_id;x[7]=t.identity.owner;x[8]=t.identity.template_ptr;x[9]=t.identity.type_hash;x[20]=1;x[21]=ctx.body;x[22]=bits(t.hp);
    x[28]=t.visibility_frame;x[29]=word(ctx.body);x[30]=word(ctx.body-8);x[31]=word(ctx.body-0x10);return true;
}
static bool after(Context&ctx,np::Row&r){
    auto&x=r.words;rt::Actor a{};if(!actor(ctx.actor,a))return false;
    nc::WeaponReader reader(frozen.binding,frozen.native,memory,*policy);auto w=reader.sample(a);
    if(!w.facts.identity_verified||w.entry!=ctx.entry||w.template_ptr!=x[17]||w.slot!=x[93])return false;
    x[33]=w.ammo;x[34]=w.request_limit;x[35]=w.template_ptr;x[36]=w.state_machine;x[37]=w.state;x[38]=w.state_vtable;x[39]=w.state_id;x[92]=1;
    if(!ctx.visible)return true;
    if(word(ctx.target)!=0xc4db60||word(ctx.target+0xdc)!=x[6]||word(ctx.target+4)!=x[8]||word(ctx.target+0x418)!=x[7]||word(ctx.target+0x33c)!=ctx.body
        ||word(ctx.body)!=ctx.body_vtable||word(ctx.body-8)!=ctx.target||word(ctx.target+0x374)!=ctx.registered.update)return false;
    float hp=0;if(!read(ctx.body+4,&hp,4)||!std::isfinite(hp))return false;
    x[32]=bits(hp);x[40]=1;x[44]=word(ctx.body);x[45]=word(ctx.body-8);x[46]=word(ctx.target+0x33c);x[47]=word(ctx.target+0x374);return true;
}
static void __attribute__((fastcall)) attack_hook(void*self,void*,void*target,uint32_t shots,uint32_t source){
    if(shared){InterlockedIncrement(&shared->active);}auto began=GetTickCount64();Context saved=private_context,ctx{};private_context={};np::Row r{};bool valid=false;
    try{if(observing()){ctx.id=++next_call;r=row(np::Kind::PrivateEnter,ctx.id);r.words[41]=uintptr_t(__builtin_return_address(0));nc::WeaponSnapshot w;valid=capture(word(uintptr_t(self)+8),uintptr_t(target),w,ctx,r);
        if(valid){r.words[10]=source;r.words[11]=shots;r.words[41]=uintptr_t(__builtin_return_address(0));private_context=ctx;publish(r);}else shared->rejected++;}}
    catch(...){if(shared)shared->rejected++;}
    original_attack(self,target,shots,source);
    try{if(valid){r.kind=uint32_t(np::Kind::PrivateExit);r.frame=word(frozen.native.logic+0x50);r.monotonic_ms=GetTickCount64();after(ctx,r);publish(r);}}
    catch(...){if(shared)shared->rejected++;}
    private_context=saved;elapsed(began);if(shared)InterlockedDecrement(&shared->active);
}
static void __attribute__((fastcall)) fire_hook(void*self,void*,void*argument){
    if(shared){InterlockedIncrement(&shared->active);}auto began=GetTickCount64();Context saved=fire_context,ctx{};fire_context={};np::Row r{};bool valid=false;
    try{if(observing()){uint32_t words[16]{};ctx.id=++next_call;r=row(np::Kind::FireEnter,ctx.id,private_context.id);r.words[41]=uintptr_t(__builtin_return_address(0));nc::WeaponSnapshot w;
        valid=read(uintptr_t(argument),words,sizeof(words))&&capture(words[1],words[7],w,ctx,r)&&w.entry==uintptr_t(self);
        if(valid){r.words[41]=uintptr_t(__builtin_return_address(0));r.words[42]=uintptr_t(argument);if(ctx.visible){std::copy(words,words+16,r.words.begin()+48);}else {r.words[49]=ctx.actor;}fire_context=ctx;publish(r);}else {shared->rejected++;}}}
    catch(...){if(shared)shared->rejected++;}
    original_fire(self,argument);
    try{if(valid){r.kind=uint32_t(np::Kind::FireExit);r.frame=word(frozen.native.logic+0x50);r.monotonic_ms=GetTickCount64();after(ctx,r);publish(r);}}
    catch(...){if(shared)shared->rejected++;}
    fire_context=saved;elapsed(began);if(shared)InterlockedDecrement(&shared->active);
}
static void __attribute__((fastcall)) damage_hook(void*self,void*,void*argument){
    if(shared){InterlockedIncrement(&shared->active);}auto began=GetTickCount64();np::Row r{};Context ctx=fire_context;bool valid=false;
    try{if(observing()&&ctx.id&&ctx.visible&&uintptr_t(self)==ctx.body&&word(ctx.target+0x33c)==ctx.body&&word(ctx.body-8)==ctx.target){
        r=row(np::Kind::DamageEnter,++next_call,ctx.id);r.words[0]=ctx.actor;r.words[1]=word(ctx.actor+0xdc);r.words[5]=ctx.target;r.words[6]=ctx.registered.object_id;r.words[7]=ctx.registered.owner;r.words[8]=ctx.registered.template_ptr;r.words[9]=ctx.registered.type_hash;
        r.words[12]=ctx.entry;r.words[17]=ctx.weapon_template;r.words[26]=word(ctx.entry+0x64);r.words[93]=ctx.weapon_slot;r.words[21]=ctx.body;r.words[22]=word(ctx.body+4);r.words[29]=word(ctx.body);r.words[30]=word(ctx.body-8);r.words[31]=word(ctx.body-0x10);r.words[41]=uintptr_t(__builtin_return_address(0));r.words[42]=uintptr_t(argument);
        valid=read(uintptr_t(argument),r.words.data()+48,0x94);if(valid){r.words[10]=r.words[50];publish(r);}else shared->skipped_damage++;
    }else if(shared)shared->skipped_damage++;}catch(...){if(shared)shared->skipped_damage++;}
    original_damage(self,argument);
    try{if(valid){r.kind=uint32_t(np::Kind::DamageExit);r.frame=word(frozen.native.logic+0x50);r.monotonic_ms=GetTickCount64();after(ctx,r);
        if(read(uintptr_t(argument),r.words.data()+48,0x94)){r.words[43]=1;}publish(r);}}
    catch(...){if(shared)shared->skipped_damage++;}
    elapsed(began);if(shared)InterlockedDecrement(&shared->active);
}
struct Hook{uint32_t address;void*detour;void**original;const char*signature;uint32_t size;bool made=false,enabled=false;};
static Hook hooks[]={
    {0x76e690,reinterpret_cast<void*>(attack_hook),reinterpret_cast<void**>(&original_attack),"\x83\x7c\x24\x04\0\x55\x56\x8b\xf1\x8b\x6e\x08",12},
    {0x790d80,reinterpret_cast<void*>(fire_hook),reinterpret_cast<void**>(&original_fire),"\x83\xec\x08\x56\x57\x8b\x7c\x24\x14",9},
    {0x764e20,reinterpret_cast<void*>(damage_hook),reinterpret_cast<void**>(&original_damage),"\x83\xec\x14\x55\x57\x8b\xf9\x8b\x47\xf0",10}};
static bool original_entries(){for(auto&h:hooks){uint8_t bytes[20]{};if(!read(h.address,bytes,h.size)||std::memcmp(bytes,h.signature,h.size))return false;}return true;}
static void close(){
    closing=true;if(!shared||shared->active)return;
    bool okay=true;for(auto&h:hooks)if(h.enabled){auto code=MH_DisableHook(reinterpret_cast<void*>(h.address));if(code==MH_OK||code==MH_ERROR_DISABLED)h.enabled=false;else okay=false;}
    uint32_t mask=0;for(unsigned i=0;i<3;i++){uint8_t bytes[20]{};auto&h=hooks[i];if(!h.enabled&&read(h.address,bytes,h.size)&&!std::memcmp(bytes,h.signature,h.size))mask|=1u<<i;}
    shared->hooks_restored=mask;
    if(!okay||mask!=np::restore_mask||shared->active){shared->state=5;return;}
    // Keep pinned code and trampolines allocated; no stale callback can unload.
    shared->state=3;
}
static void bootstrap(uint32_t token){
    if(shared){return;}wchar_t name[100]{};std::swprintf(name,100,L"Local\\TacticoreShot1_%lu_%u",GetCurrentProcessId(),token);
    mapping=OpenFileMappingW(FILE_MAP_ALL_ACCESS,FALSE,name);if(!mapping)return;shared=static_cast<np::Shared*>(MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(np::Shared)));if(!shared)return;
    frozen=shared->bootstrap;shared->callback_thread=GetCurrentThreadId();shared->state=1;
    if(shared->magic_word!=np::magic||shared->protocol!=np::version||shared->structure_size!=sizeof(np::Shared)||shared->token!=token
        ||frozen.policy_schema!=2||frozen.duration_ms<1000||frozen.duration_ms>90000||!root()||!original_entries()){shared->error=10;shared->hooks_restored=1;shared->state=4;return;}
    policy=nc::NearBuildPolicy::verify_current_game(frozen.binding,frozen.mod_path,frozen.capability_path,frozen.safety_path);
    if(!policy||!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,reinterpret_cast<LPCWSTR>(&bootstrap),&pinned)){shared->error=11;shared->hooks_restored=1;shared->state=4;return;}
    target_policy=np::DiagnosticTargetPolicy::verify(frozen.binding,*policy);if(!target_policy){shared->error=15;shared->hooks_restored=1;shared->state=4;return;}
    registry=std::make_unique<nc::TargetRegistry>(frozen.binding);auto init=MH_Initialize();
    if(init!=MH_OK&&init!=MH_ERROR_ALREADY_INITIALIZED){shared->error=12;shared->hooks_restored=1;shared->state=4;return;}
    for(auto&h:hooks){if(MH_CreateHook(reinterpret_cast<void*>(h.address),h.detour,h.original)!=MH_OK){shared->error=13;close();return;}h.made=true;}
    shared->started_ms=shared->last_ms=GetTickCount64();shared->state=2;
    for(auto&h:hooks){if(MH_EnableHook(reinterpret_cast<void*>(h.address))!=MH_OK){shared->error=14;close();return;}h.enabled=true;shared->installed_count++;}
}
extern "C" __declspec(dllexport) LRESULT CALLBACK TacticoreShotControl(int code,WPARAM wp,LPARAM lp){
    if(code>=0&&wp==PM_REMOVE&&lp){auto msg=reinterpret_cast<MSG*>(lp);
        if(msg->message==np::bootstrap_message&&msg->wParam==np::magic&&!shared)bootstrap(msg->lParam);
        else if(shared&&msg->message==np::pulse_message&&msg->wParam==shared->token){
            auto now=GetTickCount64();if(shared->state==2){if(!root()){shared->error=20;closing=true;}
                if(shared->stop||shared->overflow||now<shared->started_ms||now-shared->started_ms>=frozen.duration_ms||now<shared->last_ms||now-shared->last_ms>3000)closing=true;
                if(!closing){auto r=row(np::Kind::Heartbeat,0);std::copy(capture_stages.begin(),capture_stages.end(),r.words.begin());std::copy(weapon_refusals.begin(),weapon_refusals.end(),r.words.begin()+32);publish(r);}}
            if(closing){close();}shared->last_ms=now;InterlockedExchange(&shared->pulse_acknowledged,msg->lParam);
        }
    }
    return CallNextHookEx(nullptr,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID){if(reason==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(instance);return TRUE;}
