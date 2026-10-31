// Portable Native6 offline candidate. No exact production/build/unit API.
#define RA3_MANAGER_GATE_REVIEWED_NATIVE_THUNK 1
#include "shared.h"
#include "strategic_manager_gate_enable_candidate_v2.h"
#include <wincrypt.h>
#include <stdio.h>
#include <new>
namespace g=ra3_strategic_manager_enable_candidate_v2;
static Shared* p;static HANDLE mapping,lease,journal;
static HHOOK owned_hook;static HMODULE pin;static BindingWire sealed;
static HANDLE inputs[4096];static unsigned input_count;static bool actual_lease;
static g::Binding binding;static g::Candidate* candidate;
static g::ReviewedWin32Environment* environment;
static DWORD started;static uint32_t audit_sequence,callback_serial,last_audit_callback[2];
static uint32_t current_not_after,manager_not_after[2],flag_not_after;
static bool stopping;static g::Audit last_audit[2];static bool has_audit[2];
static bool admission_cleanup_pending;
// One outstanding self wake, including its callback. A ticket prevents the
// temporary bootstrap hook from clearing a newer wake when it sees the same
// message a second time. This is scheduling state, never action authority.
static volatile LONG wake_pending,wake_serial,wake_bootstrap=1;
using WakePoster=BOOL (WINAPI*)(DWORD,UINT,WPARAM,LPARAM);
static bool queue_wake(WakePoster post=PostThreadMessageW){
 if(InterlockedCompareExchange(&wake_pending,-1,0))return true;
 LONG serial=InterlockedIncrement(&wake_serial);
 if(serial<=0||serial>0x3fffffff){InterlockedExchange(&wake_pending,0);return false;}
 LONG ticket=serial|0x40000000;InterlockedExchange(&wake_pending,ticket);
 if(post(sealed.thread,MESSAGE,MAGIC,(LPARAM)ticket))return true;
 InterlockedCompareExchange(&wake_pending,0,ticket);return false;
}
static bool claim_wake(LPARAM ticket){
 return ticket>=0x40000001&&ticket<=0x7fffffff&&
  InterlockedCompareExchange(&wake_pending,-(LONG)ticket,(LONG)ticket)==(LONG)ticket;
}
static void finish_wake(LPARAM ticket){
 if(ticket>=0x40000001&&ticket<=0x7fffffff)InterlockedCompareExchange(&wake_pending,0,-(LONG)ticket);
}
extern "C" __declspec(dllexport) LRESULT CALLBACK StrategicCommanderControl(int,WPARAM,LPARAM);

static bool plain_path(const wchar_t* path){
 if(!path||!path[0]||!path[1]||path[1]!=L':'||path[2]!=L'\\')return false;
 wchar_t work[1024];if(wcslen(path)>=1024)return false;wcscpy(work,path);
 for(unsigned i=3;;i++)if(work[i]==L'\\'||!work[i]){
  wchar_t saved=work[i];work[i]=0;DWORD attributes=GetFileAttributesW(work);work[i]=saved;
  if(attributes==INVALID_FILE_ATTRIBUTES||(attributes&FILE_ATTRIBUTE_REPARSE_POINT))return false;
  if(!saved)break;
 }return true;
}
static bool lock_hash(const wchar_t* path,const uint8_t expected[32]){
 if(input_count>=4096||!plain_path(path))return false;
 HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 if(file==INVALID_HANDLE_VALUE)return false;
 HCRYPTPROV provider=0;HCRYPTHASH hash=0;bool okay=false;
 if(CryptAcquireContextW(&provider,NULL,NULL,PROV_RSA_AES,CRYPT_VERIFYCONTEXT)&&CryptCreateHash(provider,CALG_SHA_256,0,0,&hash)){
  BYTE buffer[16384],digest[32];DWORD got=0,n=32;bool valid=true;
  for(;;){if(!ReadFile(file,buffer,sizeof(buffer),&got,NULL)){valid=false;break;}if(!got)break;if(!CryptHashData(hash,buffer,got,0)){valid=false;break;}}
  okay=valid&&CryptGetHashParam(hash,HP_HASHVAL,digest,&n,0)&&n==32&&!memcmp(digest,expected,32);
 }
 if(hash)CryptDestroyHash(hash);if(provider)CryptReleaseContext(provider,0);
 if(okay)inputs[input_count++]=file;else CloseHandle(file);return okay;
}
#include "portable_paths.h"
static bool read(uint32_t at,void* out,size_t n){SIZE_T got=0;return ReadProcessMemory(GetCurrentProcess(),(void*)(uintptr_t)at,out,n,&got)&&got==n;}
static uint32_t word(uint32_t at){uint32_t v=0;read(at,&v,4);return v;}
static bool live_identity(){
 FILETIME a,b,c,d;
 if(GetCurrentProcessId()!=binding.pid||GetCurrentThreadId()!=binding.callback_thread||
    !GetProcessTimes(GetCurrentProcess(),&a,&b,&c,&d)||a.dwLowDateTime!=sealed.start_low||a.dwHighDateTime!=sealed.start_high||
    (uintptr_t)GetModuleHandleW(NULL)!=0x400000||word(0xcd8ce4)!=binding.game||word(binding.game)!=0xbeb630||
    word(0xcdd190)!=binding.engine||word(binding.owner)!=0xc5bce0||word(binding.owner+0x20)!=3||
    word(binding.owner+0x10)!=binding.player_template||word(binding.owner+0x90)!=binding.ai||
    word(binding.ai)!=0xc60f60||word(binding.ai+8)!=binding.owner||word(binding.ai+0x8a8)!=binding.owner||
    word(binding.ai+0x8b0)!=binding.personality||word(binding.personality)!=binding.personality_data||
    word(binding.personality+0x18)!=0x799613e0)return false;
 uint32_t manager=word(0xcdd1a0);if(word(manager)!=0xc07ab8)return false;unsigned owners=0;
 for(unsigned i=0;i<20;i++){
  uint32_t player=word(manager+0x48+4*i),ai=player?word(player+0x90):0,profile=ai?word(ai+0x8b0):0;
  if(profile&&word(profile+0x18)==0x799613e0){owners++;if(player!=binding.owner)return false;}
 }
 return owners==1;
}
static bool guard(void*,const g::Binding& b){
 if(!p||!actual_lease||!lease||!journal||!candidate||!environment||
    memcmp(&b,&binding,sizeof(b))||memcmp(&p->binding,&sealed,sizeof(sealed))||
    p->magic!=MAGIC||p->version!=6||p->size!=sizeof(Shared)||!p->lease_held||
    input_count!=SOURCE_PIN_COUNT+3||!live_identity())return false;
 for(unsigned i=0;i<input_count;i++){
  BY_HANDLE_FILE_INFORMATION info={};if(!GetFileInformationByHandle(inputs[i],&info)||(info.dwFileAttributes&FILE_ATTRIBUTE_REPARSE_POINT))return false;
 }
 return !current_not_after||word(binding.game+0x50)<current_not_after;
}
static bool audit(void*,const g::Audit& value){
 if(!journal||!p||audit_sequence>=4096||(unsigned)value.gate>1)return false;
 JournalRecord record={};record.magic=MAGIC;record.sequence=++audit_sequence;
 record.version=6;record.size=sizeof(record);record.kind=1;record.callback_serial=callback_serial;record.intent_not_after_frame=current_not_after?current_not_after:manager_not_after[(unsigned)value.gate];record.binding=sealed;record.audit=value;record.end=0x454e4436;
 DWORD written=0;
 if(!WriteFile(journal,&record,sizeof(record),&written,NULL)||written!=sizeof(record)||!FlushFileBuffers(journal))return false;
 unsigned i=(unsigned)value.gate;last_audit[i]=value;has_audit[i]=true;last_audit_callback[i]=callback_serial;
 GateStatus& s=p->gates[i];s.phase=(uint32_t)value.phase;s.baseline_captured=value.baseline_captured;
 for(unsigned j=0;j<3;j++){s.baseline[j]=value.baseline[j];s.observed[j]=value.observed[j];}
 s.frame=value.frame;s.ms=value.ms;s.deadline_frame=value.deadline_frame;s.deadline_ms=value.deadline_ms;
 s.attempted=value.api_attempts;s.requested_enabled=value.requested_enabled;s.operation_enabled=value.operation_enabled;
 s.already_satisfied=value.state_already_satisfied;p->journal_records=audit_sequence;return true;
}
#include "flag_api.h"
#include "flags.h"
static bool components_at_baseline(){
 for(unsigned i=0;i<2;i++){
  g::Phase phase=candidate->phase((g::Gate)i);
  p->gates[i].phase=(uint32_t)phase;
  if(phase==g::Phase::Empty)continue;
  if(phase!=g::Phase::BaselineObserved||!has_audit[i])return false;
  const g::Audit& a=last_audit[i];uint32_t frame=word(binding.game+0x50);
  // Require a distinct later callback observation before returning the lease.
  if(callback_serial<=last_audit_callback[i]||frame<a.frame||GetTickCount64()<=a.ms||!guard(NULL,binding))return false;
  unsigned begin=i?1:0,end=i?3:1;
  for(unsigned j=begin;j<end;j++){
   const g::Component& c=g::COMPONENTS[j];BYTE actual=2;
   if(word(binding.ai+c.offset)!=c.vtable||word(binding.ai+c.offset+c.owner_offset)!=binding.owner||
      !read(binding.ai+c.offset+c.enabled_offset,&actual,1)||actual!=a.baseline[j])return false;
  }
 }return true;
}
static void return_lease(){
 if(!components_at_baseline()||!flags_baseline())return;
 if(owned_hook&&!UnhookWindowsHookEx(owned_hook)){p->error=32;return;}
 owned_hook=NULL;p->hook_held=0;
 if(!ReleaseSemaphore(lease,1,NULL)){p->error=33;return;}
 actual_lease=false;p->lease_held=0;p->cleanup_verified=1;p->phase=2;
 // Input locks deliberately remain held until this game process exits.
}
static void admission_failure_cleanup(){
 if(admission_cleanup_pending)return;
 p->error=40;p->cleanup_verified=0;
 if(owned_hook){
  if(!UnhookWindowsHookEx(owned_hook)){
   admission_cleanup_pending=true;p->error=32;p->phase=5;return;
  }
  owned_hook=NULL;p->hook_held=0;
 }
 if(actual_lease){
  if(!ReleaseSemaphore(lease,1,NULL)){
   admission_cleanup_pending=true;p->error=33;p->phase=5;return;
  }
  actual_lease=false;p->lease_held=0;
 }
 p->phase=4;
}
static void tick(){
 if(admission_cleanup_pending||!p||p->phase==2||p->phase==4||!candidate)return;
 if(InterlockedCompareExchange(&p->active,1,0))return;
 if(callback_serial==0xffffffffu){p->error=36;p->phase=5;p->active=0;return;}
 p->callback_serial=++callback_serial;
 uint32_t frame=word(binding.game+0x50);
 if(!frame||frame<p->last_frame||!guard(NULL,binding)){p->error=34;stopping=true;p->phase=5;}
 else p->last_frame=frame;
 bool watchdog=GetTickCount()-p->heartbeat>5000||GetTickCount()-started>HARD_WALL_MS;
 if(p->stop||watchdog||p->phase==5)stopping=true;
 if(stopping){
  service_flags(true,watchdog?3:2);
  candidate->service(watchdog?g::Trigger::Watchdog:g::Trigger::Stop);
  // Reconciliation performs only reads; no uncertain API call is retried.
  for(unsigned i=0;i<2;i++){
   g::Phase phase=candidate->phase((g::Gate)i);
   if(phase==g::Phase::ApplyUnknown||phase==g::Phase::RestoreUnknown)candidate->reconcile((g::Gate)i);
  }
  return_lease();p->active=0;return;
 }
 candidate->service(g::Trigger::Expiry);
 for(unsigned i=0;i<2;i++)if(manager_not_after[i]&&frame>=manager_not_after[i]&&candidate->phase((g::Gate)i)==g::Phase::Held)candidate->release((g::Gate)i,g::Trigger::Expiry);
 service_flags(false,1);
 if(flag_phase==FlagPhase::ApplyUnknown||flag_phase==FlagPhase::RestoreUnknown||flag_phase==FlagPhase::Blocked){stopping=true;p->phase=5;p->active=0;return;}
 for(unsigned i=0;i<2;i++){
  g::Phase phase=candidate->phase((g::Gate)i);
  if(phase==g::Phase::ApplyUnknown||phase==g::Phase::RestoreUnknown||phase==g::Phase::Blocked){stopping=true;p->phase=5;p->active=0;return;}
 }
 LONG request=p->request;
 if(request>p->ack){
  uint32_t kind=p->kind,gate=p->gate,frames=p->frames,wall=p->wall_ms;
  if(request!=p->ack+1||request<1||request>2048||p->request!=request||gate>1||kind<1||kind>6){p->error=35;stopping=true;p->phase=5;}
  else {
   g::Result result=g::Result::Rejected;
   bool paused=word(binding.game+0x15c)!=0;
   uint32_t absolute=p->not_after_frame,prior_absolute=manager_not_after[gate];
   bool timely=absolute>frame&&absolute-frame<=1800;
   if(timely&&frames>absolute-frame)frames=absolute-frame;
   current_not_after=(kind==1||kind==2||kind==6)?absolute:0;
   if((kind==1||kind==2)&&timely&&!paused){
    manager_not_after[gate]=absolute;
    result=kind==1?candidate->request_pause((g::Gate)gate,request,frames,wall):candidate->request_enable((g::Gate)gate,request,frames,wall);
    if(result==g::Result::Rejected)manager_not_after[gate]=prior_absolute;
   }
   if(kind==3)result=candidate->release((g::Gate)gate);
   if(kind==4)result=candidate->reconcile((g::Gate)gate);
   if(kind==5){stopping=true;candidate->service(g::Trigger::Stop);result=g::Result::NeedsReconciliation;}
   if(kind==6){
    uint32_t mask=p->requested_mask;
    if(!paused&&timely&&valid_mask(mask)&&frames>=1&&frames<=1800&&wall>=1&&wall<=120000){
     flag_not_after=absolute;
     bool okay=replace_flags(request,mask,frames,wall,false,0);
     result=okay?(g::Result)8:g::Result::Unknown; // flag readback, no task/effect claim
    }
   }
   current_not_after=0;
   p->result=(uint32_t)result;p->ack=request;
   if(result==g::Result::Unknown||result==g::Result::NeedsReconciliation){stopping=true;p->phase=5;}
  }
 }
 for(unsigned i=0;i<2;i++)p->gates[i].phase=(uint32_t)candidate->phase((g::Gate)i);
 p->active=0;
}
static DWORD WINAPI watchdog(void*){
 while(p&&p->phase!=2&&p->phase!=4){if(!InterlockedCompareExchange(&wake_bootstrap,0,0))queue_wake();Sleep(100);}return 0;
}
static bool prepare(){
 if(!FIELD_CANDIDATE)return false;
 if(p->magic!=MAGIC||p->version!=6||p->size!=sizeof(Shared)||p->binding.pid!=GetCurrentProcessId()||
    p->binding.thread!=GetCurrentThreadId()||memcmp(p->binding.package,PACKAGE_SHA,32)||memcmp(p->binding.sources,SOURCE_SHA,32))return false;
 sealed=p->binding;memset(&binding,0,sizeof(binding));
 binding.pid=sealed.pid;binding.callback_thread=sealed.thread;binding.creation_filetime=(uint64_t)sealed.start_low|((uint64_t)sealed.start_high<<32);
 binding.owner=sealed.owner;binding.ai=sealed.ai;binding.personality=sealed.personality;binding.personality_data=sealed.personality_data;
 binding.player_template=sealed.player_template;binding.game=sealed.game;binding.engine=sealed.engine;
 memcpy(binding.session_id,sealed.session,16);memcpy(binding.lease_id,sealed.lease,16);
 memcpy(binding.package_sha256,sealed.package,32);memcpy(binding.source_closure_sha256,sealed.sources,32);
 FILETIME created,a,b,c;
 if(!GetProcessTimes(GetCurrentProcess(),&created,&a,&b,&c)||created.dwLowDateTime!=sealed.start_low||created.dwHighDateTime!=sealed.start_high)return false;
 bool session_nonzero=false,lease_nonzero=false;
 for(unsigned i=0;i<16;i++){session_nonzero|=sealed.session[i]!=0;lease_nonzero|=sealed.lease[i]!=0;}
 if(!session_nonzero||!lease_nonzero||!portable_bind_paths(sealed))return false;
 for(unsigned i=0;i<SOURCE_PIN_COUNT;i++){
  wchar_t input[1024];if(!runtime_input(sealed.runtime_root,SOURCE_PINS[i].path,input,1024)||!lock_hash(input,SOURCE_PINS[i].sha))return false;
 }
 wchar_t inventory[1024];if(!runtime_input(sealed.runtime_root,L"manifest.json",inventory,1024)||!lock_hash(inventory,sealed.runtime_manifest))return false;
 if(!lock_hash(sealed.game_image,GAME_SHA)||!lock_hash(sealed.deployment,PACKAGE_SHA))return false;
 wchar_t file[1024],id[33];for(unsigned i=0;i<16;i++)swprintf(id+2*i,3,L"%02x",sealed.session[i]);
 if(wcslen(sealed.journal_root)+40>=1024)return false;swprintf(file,1024,L"%ls\\%ls.bin",sealed.journal_root,id);
 journal=CreateFileW(file,GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL|FILE_FLAG_WRITE_THROUGH,NULL);
 if(journal==INVALID_HANDLE_VALUE){journal=NULL;return false;}
 char name[96];snprintf(name,sizeof(name),"Local\\RA3MacroPolicyLease_%lu",GetCurrentProcessId());
 lease=CreateSemaphoreA(NULL,1,1,name);if(!lease||WaitForSingleObject(lease,0)!=WAIT_OBJECT_0)return false;
 actual_lease=true;p->lease_held=1;
 environment=new(std::nothrow) g::ReviewedWin32Environment(NULL,guard,audit);
 if(!environment)return false;candidate=new(std::nothrow) g::Candidate(*environment,binding);if(!candidate)return false;
 if(!guard(NULL,binding))return false;
 uint32_t initial_flags=0;if(!read_mask(initial_flags)||initial_flags)return false;
 if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCWSTR)(uintptr_t)&tick,&pin))return false;
 owned_hook=SetWindowsHookExW(WH_GETMESSAGE,StrategicCommanderControl,pin,sealed.thread);if(!owned_hook)return false;
 p->hook_held=1;started=GetTickCount();
 HANDLE worker=CreateThread(NULL,0,watchdog,NULL,0,NULL);if(!worker)return false;CloseHandle(worker);
 p->phase=1;return true;
}
extern "C" __declspec(dllexport) LRESULT CALLBACK StrategicCommanderControl(int code,WPARAM wp,LPARAM lp){
 if(!FIELD_CANDIDATE)return CallNextHookEx(NULL,code,wp,lp);
 if(code>=0&&wp==PM_REMOVE&&lp&&((MSG*)lp)->message==MESSAGE&&((MSG*)lp)->wParam==MAGIC){
  LPARAM ticket=((MSG*)lp)->lParam;
  bool bootstrap=!p&&ticket==0;
  if(!bootstrap&&!claim_wake(ticket))return CallNextHookEx(NULL,code,wp,lp);
  if(bootstrap){
   wchar_t name[96];swprintf(name,96,L"Local\\RA3StrategicCommanderV6_%lu",GetCurrentProcessId());
   mapping=OpenFileMappingW(FILE_MAP_ALL_ACCESS,FALSE,name);
   if(mapping)p=(Shared*)MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Shared));
   if(p&&!prepare())admission_failure_cleanup();
  }
  tick();if(bootstrap)InterlockedExchange(&wake_bootstrap,0);else finish_wake(ticket);
 }
 return CallNextHookEx(NULL,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID){if(reason==DLL_PROCESS_ATTACH){portable_module=module;DisableThreadLibraryCalls(module);}return TRUE;}
