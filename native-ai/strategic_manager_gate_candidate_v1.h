#pragma once
// SOURCE-ONLY next candidate. No transport entry point, DLL, hooks or authority.
// Pause only these normal native manager APIs; opening and native committed
// work remain native. Never write enabled bytes, queues, templates or units.
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#if defined(_WIN32) && defined(__i386__) && defined(RA3_MANAGER_GATE_REVIEWED_NATIVE_THUNK)
#if !defined(_WIN32_WINNT) || _WIN32_WINNT < 0x0601
#error Reviewed manager gate native adapter requires explicit _WIN32_WINNT >= 0x0601 (Windows 7).
#endif
#include <windows.h>
#endif

namespace ra3_strategic_manager_candidate_v1 {
static const char EXPECTED_EXE_SHA256[]="ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165";
enum class Gate : uint32_t { BaseBuilder=0, UnitAndPrerequisiteFamily=1 };
enum class Trigger : uint32_t { Release, Expiry, Stop, Watchdog, Fault };
enum class Phase : uint32_t { Empty, Held, ApplyUnknown, RestoreUnknown, BaselineObserved, Blocked };
enum class Outcome : uint32_t { Completed, Unknown };
enum class Result : uint32_t { Rejected, NoOwnedGate, PausedObserved, BaselineObserved, Unknown, NeedsReconciliation };
struct Binding {
 uint32_t pid, callback_thread, owner, ai, personality, personality_data, player_template, game, engine;
 uint64_t creation_filetime;
 uint8_t session_id[16], lease_id[16], package_sha256[32], source_closure_sha256[32];
};
struct OsIdentity {uint32_t pid,thread,module_base;uint64_t creation_filetime,monotonic_ms;};
struct Snapshot {uint32_t frame;uint64_t ms;uint8_t enabled[3],opening_enabled,opening_terminal;};
struct Audit {
 uint64_t request_id;Gate gate;Phase phase;Trigger trigger;
 uint32_t frame,deadline_frame;uint64_t ms,deadline_ms;
 uint8_t baseline[3],observed[3];uint32_t api_attempts;
 bool read_only_reconciliation;uint32_t first_reconcile_frame;uint64_t first_reconcile_ms;uint8_t first_reconcile_values[3];
 // A receipt reports component bytes only, never independent release/effect.
};
struct Environment {
 struct CallBounds {Binding binding;uint32_t native_enum,deadline_frame,not_before_frame;uint64_t deadline_ms,not_before_ms;bool desired,restoring,armed;};
protected:
 CallBounds call_bounds;
public:
 Environment(){memset(&call_bounds,0,sizeof(call_bounds));}
 virtual ~Environment() {}
 // One-use absolute bounds, retained through the concrete adapter's LAST
 // potentially slow guard. This never extends/reset the original deadline.
 void arm_call_bounds(const Binding& binding,uint32_t native_enum,bool desired,uint32_t frame,uint64_t ms,bool restoring,const Snapshot& before){
  call_bounds.binding=binding;call_bounds.native_enum=native_enum;call_bounds.desired=desired;
  call_bounds.deadline_frame=frame;call_bounds.deadline_ms=ms;call_bounds.restoring=restoring;
  call_bounds.not_before_frame=before.frame;call_bounds.not_before_ms=before.ms;call_bounds.armed=true;
 }
 void clear_call_bounds(){call_bounds.armed=false;}
 virtual bool read(uint32_t address,void* target,size_t size)=0;
 virtual bool os_identity(OsIdentity& actual)=0;
 // Mandatory integration guard: actual held common lease + exact immutable
 // session/source/package/EXE evidence. No caller-supplied boolean is a grant.
 virtual bool verify_bound_inputs_and_common_lease(const Binding&)=0;
 // Must persist a pre-call Unknown record before the native call. Failure
 // prevents the call. Post-call persistence failure remains Unknown.
 virtual bool journal(const Audit&)=0;
 virtual Outcome normal_component_call(uint32_t bound_ai,uint32_t native_enum,bool enabled)=0;
};
struct Pin {uint32_t address;const char* hex;};
static const Pin CODE_PINS[]={
 {0x880e40,"8b44240483f808751e83b9f806000000"},
 {0x880e67,"8944240481c104010000e94ae9ffff"},
 {0x87f7c0,"8b44240483f807568bf10f87b3000000ff248588f88700"},
 {0x87f7d7,"8b54240c8b86540300008b40048d8e5403000052ffd0"},
 {0x87f7f1,"8b96d00300008b4204578b7c24108d8ed003000057ffd0"},
 {0x87f808,"8b96600400008b42048d8e6004000057ffd0"},
 {0x893020,"8a44240488411cc20400"},{0xb663c0,"8a411cc3"},
 {0x885ae0,"8a442404884110c20400"},{0x544f10,"8a4110c3"},
 {0xc5f8fc,"20308900"},{0xc5f904,"c063b600"},
 {0xc5f488,"e05a8800"},{0xc5f490,"104f5400"},
 {0xc5f444,"e05a8800"},{0xc5f44c,"104f5400"},
 {0x8d7a90,"8b97500300008b420c8db7500300008bceffd084c07420"},
 {0x8d7a5d,"8bb7e00400008b168b420c8bceffd084c07420"},
 {0x8d5727,"89beb0080000"},{0x844a3f,"898690000000"}
};
struct Component {uint32_t offset,vtable,owner_offset,enabled_offset;};
static const Component COMPONENTS[]={{0x458,0xc5f8f8,0x14,0x1c},{0x4d4,0xc5f484,8,0x10},{0x564,0xc5f440,8,0x10}};
struct Channel {
 Phase phase;uint8_t baseline[3];uint32_t deadline_frame;uint64_t deadline_ms;
 uint32_t api_attempts,reconcile_frame;uint64_t reconcile_ms;uint8_t reconcile_values[3];
 bool reconcile_pending;
 Channel():phase(Phase::Empty),deadline_frame(0),deadline_ms(0),api_attempts(0),reconcile_frame(0),reconcile_ms(0),reconcile_pending(false){memset(baseline,0,3);memset(reconcile_values,0,3);}
};
struct Request {uint64_t id;Gate gate;uint32_t frames,wall_ms;Result result;};

class Candidate {
 Environment& env;const Binding binding;Channel channels[2];Request receipts[128];uint32_t used,last_frame;uint64_t last_ms;
 bool stop_latched;
 static bool pointer(uint32_t p,uint32_t n=4){return !(p&3)&&p>=0x10000&&p<=0x7ffe0000-n;}
 bool word(uint32_t p,uint32_t& out){return pointer(p)&&env.read(p,&out,4);}
 bool eq(uint32_t p,uint32_t expected){uint32_t value=0;return word(p,value)&&value==expected;}
 bool byte(uint32_t p,uint8_t& out){return p>=0x10000&&p<0x7ffe0000&&env.read(p,&out,1)&&out<=1;}
 static unsigned nibble(char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:255;}
 bool pins(){
  for(size_t i=0;i<sizeof(CODE_PINS)/sizeof(Pin);i++){
   const char* hex=CODE_PINS[i].hex;size_t n=strlen(hex);uint8_t wanted[64],actual[64];
   if(n%2||n/2>64)return false;
   for(size_t j=0;j<n/2;j++){unsigned a=nibble(hex[2*j]),b=nibble(hex[2*j+1]);if(a>15||b>15)return false;wanted[j]=(uint8_t)(a*16+b);}
   if(!env.read(CODE_PINS[i].address,actual,n/2)||memcmp(actual,wanted,n/2))return false;
  }return true;
 }
 bool identity(){
  const Binding& b=binding;uint32_t manager=0,store=0,start=0,end=0;
  if(!pointer(b.owner)||!pointer(b.ai,0x8b4)||!pointer(b.personality)||!pointer(b.personality_data,0xf4)||
   !eq(0xcd8ce4,b.game)||!eq(b.game,0xbeb630)||!eq(0xcdd190,b.engine)||
   !eq(b.owner,0xc5bce0)||!eq(b.owner+0x20,3)||!eq(b.owner+0x10,b.player_template)||!eq(b.owner+0x90,b.ai)||
   !eq(b.ai,0xc60f60)||!eq(b.ai+8,b.owner)||!eq(b.ai+0x8a8,b.owner)||!eq(b.ai+0x8b0,b.personality)||
   !eq(b.personality,b.personality_data)||!eq(b.personality+0x18,0x799613e0)||
   !word(0xcdd1a0,manager)||!eq(manager,0xc07ab8)||!word(0xce98ec,store)||!eq(store,0xc606b8)||
   !word(store+0x24,start)||!word(store+0x28,end)||end<=start||end-start>16384||(end-start)%4)return false;
  unsigned matching=0,registered=0,instances=0;
  for(unsigned i=0;i<20;i++){
   uint32_t player=0,ai=0,profile=0;
   if(!word(manager+0x48+4*i,player))return false;
   if(!player)continue;
   if(!eq(player,0xc5bce0)||!word(player+0x90,ai))return false;
   if(!ai)continue;
   if(!eq(ai,0xc60f60)||!word(ai+0x8b0,profile))return false;
   if(!profile)continue;
   uint32_t id=0;if(!pointer(profile)||!word(profile+0x18,id))return false;
   if(id==0x799613e0){if(player!=b.owner)return false;matching++;}
  }
  for(uint32_t at=start;at<end;at+=4){uint32_t profile=0,id=0;if(!word(at,profile)||!pointer(profile)||!word(profile+0x18,id))return false;registered+=profile==b.personality;instances+=id==0x799613e0;}
  uint32_t count=0,array=0;bool side=false;
  if(!word(b.personality_data+0xec,count)||!word(b.personality_data+0xf0,array)||!count||count>32||!pointer(array,4*count))return false;
  for(uint32_t i=0;i<count;i++){uint32_t value=0;if(!word(array+4*i,value)||!value)return false;side|=value==b.player_template;}
  return matching==1&&registered==1&&instances==1&&side;
 }
 bool snapshot(Snapshot& s){
  OsIdentity os={};
  if(!env.os_identity(os)||os.pid!=binding.pid||os.thread!=binding.callback_thread||
   os.creation_filetime!=binding.creation_filetime||os.module_base!=0x400000||
   !env.verify_bound_inputs_and_common_lease(binding)||!pins()||!identity()||!word(binding.game+0x50,s.frame)||
   !s.frame||s.frame<last_frame||os.monotonic_ms<last_ms)return false;
  s.ms=os.monotonic_ms;
  for(unsigned i=0;i<3;i++){uint32_t p=binding.ai+COMPONENTS[i].offset;
   if(!eq(p,COMPONENTS[i].vtable)||!eq(p+COMPONENTS[i].owner_offset,binding.owner)||!byte(p+COMPONENTS[i].enabled_offset,s.enabled[i]))return false;}
  uint32_t opening=0;if(!word(binding.ai+0x5e8,opening)||!eq(opening,0xc5f378)||!eq(opening+0x18,binding.owner)||
   !byte(opening+0xc,s.opening_enabled)||!byte(opening+0x20,s.opening_terminal))return false;
  for(unsigned i=0;i<3;i++){uint8_t value=0;if(!byte(binding.ai+COMPONENTS[i].offset+COMPONENTS[i].enabled_offset,value)||value!=s.enabled[i])return false;}
  uint32_t after=0;OsIdentity end={};
  // The final guard may perform real I/O. Clock/OS identity and real game
  // frame must be sampled AFTER it, and cover the full original sample span.
  if(!identity()||!pins()||!env.verify_bound_inputs_and_common_lease(binding)||
   !word(binding.game+0x50,after)||!env.os_identity(end)||end.pid!=os.pid||end.thread!=os.thread||end.creation_filetime!=os.creation_filetime||
   end.module_base!=os.module_base||end.monotonic_ms<os.monotonic_ms||end.monotonic_ms-os.monotonic_ms>250||
   after<s.frame||after-s.frame>2)return false;
  last_frame=after;last_ms=end.monotonic_ms;s.frame=after;s.ms=end.monotonic_ms;return true;
 }
 static unsigned index(Gate gate){return (unsigned)gate;}
 static bool selected_equal(Gate gate,const uint8_t a[3],const uint8_t b[3]){return gate==Gate::BaseBuilder?a[0]==b[0]:a[1]==b[1]&&a[2]==b[2];}
 static bool paused(Gate gate,const uint8_t a[3]){const uint8_t zero[3]={};return selected_equal(gate,a,zero);}
 bool record(Gate gate,Trigger trigger,uint64_t id,const Snapshot& s){
  Channel& c=channels[index(gate)];Audit a={};a.request_id=id;a.gate=gate;a.phase=c.phase;a.trigger=trigger;
  a.frame=s.frame;a.ms=s.ms;a.deadline_frame=c.deadline_frame;a.deadline_ms=c.deadline_ms;a.api_attempts=c.api_attempts;
  memcpy(a.baseline,c.baseline,3);memcpy(a.observed,s.enabled,3);
  a.read_only_reconciliation=c.reconcile_pending;
  if(c.reconcile_pending){a.first_reconcile_frame=c.reconcile_frame;a.first_reconcile_ms=c.reconcile_ms;memcpy(a.first_reconcile_values,c.reconcile_values,3);}
  return env.journal(a);
 }
 Result invoke(Gate gate,bool desired,bool restoring,const Snapshot& before,uint64_t id,Trigger trigger){
  Channel& c=channels[index(gate)];c.phase=restoring?Phase::RestoreUnknown:Phase::ApplyUnknown;
  c.reconcile_pending=false;
  if(!record(gate,trigger,id,before))return Result::Unknown;
  // Durable logging itself can take time. Recheck the actual callback identity,
  // lease, code and exact component state immediately before the physical call.
  env.arm_call_bounds(binding,index(gate),desired,c.deadline_frame,c.deadline_ms,restoring,before);
  Snapshot pre_call={};if(!snapshot(pre_call)||!selected_equal(gate,before.enabled,pre_call.enabled)||
   (!restoring&&(pre_call.frame>=c.deadline_frame||pre_call.ms>=c.deadline_ms))){env.clear_call_bounds();return Result::Unknown;}
  c.api_attempts++; // Unknown is latched before the only normal native call.
  Outcome outcome=env.normal_component_call(binding.ai,index(gate),desired);env.clear_call_bounds();Snapshot after={};
  if(outcome!=Outcome::Completed||!snapshot(after))return Result::Unknown;
  bool expected=restoring?selected_equal(gate,c.baseline,after.enabled):paused(gate,after.enabled);
  if(!expected)return Result::Unknown;
  c.phase=restoring?Phase::BaselineObserved:Phase::Held;
  if(!record(gate,trigger,id,after)){c.phase=restoring?Phase::RestoreUnknown:Phase::ApplyUnknown;return Result::Unknown;}
  return restoring?Result::BaselineObserved:Result::PausedObserved;
 }
public:
 static const bool field_verified=false,dispatch_granted=false,product_capability_granted=false;
 Candidate(Environment& e,const Binding& b):env(e),binding(b),used(0),last_frame(0),last_ms(0),stop_latched(false){memset(receipts,0,sizeof(receipts));}
 Result pause(Gate gate,uint64_t id,uint32_t frames,uint32_t wall_ms){
  if(index(gate)>1||!id||!frames||frames>1800||!wall_ms||wall_ms>120000)return Result::Rejected;
  for(unsigned i=0;i<used;i++)if(receipts[i].id==id){Request& r=receipts[i];return r.gate==gate&&r.frames==frames&&r.wall_ms==wall_ms?r.result:Result::Rejected;}
  if(stop_latched||used==128||(used&&id<=receipts[used-1].id))return Result::Rejected;
  for(unsigned i=0;i<used;i++)if(receipts[i].result==Result::Unknown)return Result::Rejected;
  for(unsigned i=0;i<2;i++)if(channels[i].phase==Phase::ApplyUnknown||channels[i].phase==Phase::RestoreUnknown||channels[i].phase==Phase::Blocked)return Result::Rejected;
  Channel& c=channels[index(gate)];if(c.phase!=Phase::Empty&&c.phase!=Phase::BaselineObserved)return Result::Rejected;
  Snapshot s={};if(!snapshot(s)||s.frame>0xffffffffu-frames||s.ms>UINT64_MAX-wall_ms)return Result::Rejected;
  // enum1 sets TWO components; capture both and reject mixed before mutation.
  if(gate==Gate::UnitAndPrerequisiteFamily&&s.enabled[1]!=s.enabled[2])return Result::Rejected;
  memcpy(c.baseline,s.enabled,3);c.reconcile_pending=false;c.deadline_frame=s.frame+frames;c.deadline_ms=s.ms+wall_ms;
  receipts[used++]={id,gate,frames,wall_ms,Result::Unknown};
  if(paused(gate,s.enabled)){c.phase=Phase::Held;receipts[used-1].result=record(gate,Trigger::Release,id,s)?Result::PausedObserved:Result::Unknown;return receipts[used-1].result;}
  receipts[used-1].result=invoke(gate,false,false,s,id,Trigger::Release);return receipts[used-1].result;
 }
 Result release(Gate gate,Trigger trigger=Trigger::Release){
  if(index(gate)>1)return Result::Rejected;
  Channel& c=channels[index(gate)];
  if(c.phase==Phase::Empty)return Result::NoOwnedGate;
  if(c.phase==Phase::ApplyUnknown||c.phase==Phase::RestoreUnknown||c.phase==Phase::Blocked)return Result::NeedsReconciliation;
  Snapshot s={};if(!snapshot(s)){c.phase=Phase::Blocked;return Result::Unknown;}
  if(selected_equal(gate,c.baseline,s.enabled)){c.phase=Phase::BaselineObserved;
   if(record(gate,trigger,0,s))return Result::BaselineObserved;
   c.phase=Phase::RestoreUnknown;return Result::Unknown;}
  if(c.phase!=Phase::Held||!paused(gate,s.enabled)){c.phase=Phase::Blocked;return Result::NeedsReconciliation;}
  bool prior=gate==Gate::BaseBuilder?c.baseline[0]:c.baseline[1];
  return invoke(gate,prior,true,s,0,trigger);
 }
 // Only called on the SAME game callback thread. An external watchdog may
 // request this callback; it must never invoke the component API on its worker.
 void service(Trigger trigger){
  bool stopping=trigger==Trigger::Stop||trigger==Trigger::Watchdog||trigger==Trigger::Fault;
  if(stopping)stop_latched=true;
  for(unsigned i=0;i<2;i++){Channel& c=channels[i];if(c.phase==Phase::Empty||c.phase==Phase::BaselineObserved)continue;
   Snapshot s={};if(!snapshot(s)){c.phase=Phase::Blocked;continue;}
   if(stopping||s.frame>=c.deadline_frame||s.ms>=c.deadline_ms)release((Gate)i,stopping?trigger:Trigger::Expiry);
  }
 }
 Result reconcile(Gate gate){
  if(index(gate)>1)return Result::Rejected;
  Channel& c=channels[index(gate)];
  if(c.phase!=Phase::ApplyUnknown&&c.phase!=Phase::RestoreUnknown)return Result::Rejected;
  Snapshot s={};if(!snapshot(s))return Result::Unknown;
  bool baseline=selected_equal(gate,c.baseline,s.enabled),off=paused(gate,s.enabled);
  if(!baseline&&!off){c.phase=Phase::Blocked;return Result::NeedsReconciliation;}
  if(!c.reconcile_pending){c.reconcile_pending=true;c.reconcile_frame=s.frame;c.reconcile_ms=s.ms;memcpy(c.reconcile_values,s.enabled,3);
   if(record(gate,Trigger::Release,0,s))return Result::NeedsReconciliation;
   c.reconcile_pending=false;return Result::Unknown;}
  if(s.frame<=c.reconcile_frame||s.ms<=c.reconcile_ms||!selected_equal(gate,c.reconcile_values,s.enabled))return Result::NeedsReconciliation;
  if(baseline){c.phase=Phase::BaselineObserved;
   if(record(gate,Trigger::Release,0,s))return Result::BaselineObserved;
   c.phase=Phase::RestoreUnknown;c.reconcile_pending=false;return Result::Unknown;}
  if(c.phase==Phase::RestoreUnknown){ // NEVER retry uncertain restore.
   if(record(gate,Trigger::Release,0,s))return Result::NeedsReconciliation;
   c.reconcile_pending=false;return Result::Unknown;}
  c.phase=Phase::Held;
  if(record(gate,Trigger::Release,0,s))return Result::PausedObserved;
  c.phase=Phase::ApplyUnknown;c.reconcile_pending=false;return Result::Unknown;
 }
 Phase phase(Gate gate)const{return index(gate)<2?channels[index(gate)].phase:Phase::Blocked;}
 // No semaphore release/detach/clear_flags call exists here. Caller must retain
 // common lease while any gate is unresolved, and obtain independent readback.
};

// The exact normal API is AIPlayer::component(enum,bool), not a raw setter.
// A future reviewed Windows i386 adapter may implement Environment with this
// thunk. Not enabled, compiled, installed or called by this source-only change.
#if defined(_WIN32) && defined(__i386__) && defined(RA3_MANAGER_GATE_REVIEWED_NATIVE_THUNK)
typedef void (__attribute__((thiscall))*NormalComponentApi)(void*,uint32_t,bool);
inline Outcome reviewed_native_thunk(uint32_t ai,uint32_t native_enum,bool enabled){
 if(native_enum>1)return Outcome::Unknown;
 ((NormalComponentApi)0x880e40)((void*)(uintptr_t)ai,native_enum,enabled);
 return Outcome::Completed; // only means returned; Candidate requires readback.
}
// Concrete OS/read/ABI adapter for future reviewed integration. Guard/journal
// callbacks are still mandatory integration dependencies and default to deny.
// Neither this class nor the thunk is emitted without the explicit opt-in.
class ReviewedWin32Environment : public Environment {
public:
 typedef bool (*Guard)(void*,const Binding&);
 typedef bool (*Journal)(void*,const Audit&);
private:
 void* context;Guard guard_fn;Journal journal_fn;Binding held;bool checked;
public:
 ReviewedWin32Environment(void* context_,Guard guard_,Journal journal_):context(context_),guard_fn(guard_),journal_fn(journal_),checked(false){memset(&held,0,sizeof(held));}
 bool read(uint32_t address,void* target,size_t size)override{SIZE_T got=0;return ReadProcessMemory(GetCurrentProcess(),(const void*)(uintptr_t)address,target,size,&got)&&got==size;}
 bool os_identity(OsIdentity& actual)override{
  FILETIME created,ended,kernel,user;if(!GetProcessTimes(GetCurrentProcess(),&created,&ended,&kernel,&user))return false;
  actual.pid=GetCurrentProcessId();actual.thread=GetCurrentThreadId();actual.module_base=(uint32_t)(uintptr_t)GetModuleHandleW(NULL);
  actual.creation_filetime=(uint64_t)created.dwLowDateTime|((uint64_t)created.dwHighDateTime<<32);actual.monotonic_ms=GetTickCount64();return true;
 }
 bool verify_bound_inputs_and_common_lease(const Binding& binding_)override{
  checked=guard_fn&&journal_fn&&guard_fn(context,binding_);if(checked)held=binding_;return checked;
 }
 bool journal(const Audit& audit)override{return journal_fn&&journal_fn(context,audit);}
 Outcome normal_component_call(uint32_t ai,uint32_t native_enum,bool enabled)override{
  CallBounds bounds=call_bounds;clear_call_bounds();bool was_checked=checked;checked=false;
  if(!was_checked||!bounds.armed||memcmp(&bounds.binding,&held,sizeof(Binding))||ai!=held.ai||native_enum>1||
   native_enum!=bounds.native_enum||enabled!=bounds.desired)return Outcome::Unknown;
  OsIdentity before={},actual={};uint32_t game=0,frame=0;
  // Guard FIRST; its real I/O time is inside both full-span and absolute
  // original-deadline checks. No further guard or journal occurs after the
  // final OS clock before the normal call.
  if(!os_identity(before)||!guard_fn(context,held)||
   !read(0xcd8ce4,&game,4)||game!=held.game||!read(game+0x50,&frame,4)||!os_identity(actual)||
   actual.pid!=held.pid||actual.thread!=held.callback_thread||actual.creation_filetime!=held.creation_filetime||actual.module_base!=0x400000||
   actual.pid!=before.pid||actual.thread!=before.thread||actual.creation_filetime!=before.creation_filetime||actual.module_base!=before.module_base||
   actual.monotonic_ms<before.monotonic_ms||actual.monotonic_ms-before.monotonic_ms>250||
   actual.monotonic_ms<bounds.not_before_ms||actual.monotonic_ms-bounds.not_before_ms>250||
   frame<bounds.not_before_frame||frame-bounds.not_before_frame>2||
   (!bounds.restoring&&(frame>=bounds.deadline_frame||actual.monotonic_ms>=bounds.deadline_ms)))return Outcome::Unknown;
  return reviewed_native_thunk(ai,native_enum,enabled);
 }
};
#endif
} // namespace
