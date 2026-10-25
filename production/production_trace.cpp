#include "trace_shared.h"
#include "MinHook.h"
#include <stdio.h>
#include <string.h>
static TraceState* s;static HANDLE mapping;static HMODULE pinned;static DWORD tick_tls=TLS_OUT_OF_INDEXES,pay_tls=TLS_OUT_OF_INDEXES;
static const uint32_t hashes=0x2c358c61;
static bool read(uint32_t p,void* o,SIZE_T n){SIZE_T got=0;return ReadProcessMemory(GetCurrentProcess(),(void*)(uintptr_t)p,o,n,&got)&&got==n;}
static uint32_t word(uint32_t p){uint32_t v=0;read(p,&v,4);return v;}
static uint32_t module(){return s->iface-0x24;}
static uint32_t frame(){return word(word(0xcd8ce4)+0x50);}
static uint32_t resource(){uint32_t a=word(s->owner+0xe4),b=word(s->owner+0xe8);return a&&b>=a+4&&b-a<=64?word(a):0;}
static uint32_t cash(uint32_t r){return word(r+4)+word(r+0x14);}
static bool identity(){return s&&GetCurrentThreadId()==s->thread&&word(s->owner)==0xc5bce0&&word(s->owner+0x20)==3&&word(s->owner+0x90)==s->ai&&word(s->ai)==0xc60f60&&word(s->factory)==0xc4db60&&word(s->factory+0x418)==s->owner&&word(word(s->factory+4)+8)==0x80d4ea1e&&word(module()+8)==s->factory;}
static bool target_node(uint32_t n){return n&&word(n+4)==module()&&word(n+0xc)==1&&word(word(n+0x10)+8)==hashes;}
static TraceEvent* event(uint32_t kind,uint32_t caller,uint32_t node=0){
 if(s->state!=1||!identity())return NULL;
 LONG at=InterlockedIncrement(&s->event_count)-1;if(at>=TRACE_CAP){InterlockedIncrement(&s->dropped);return NULL;}
 TraceEvent* e=&s->events[at];e->v[KIND]=kind;e->v[SEQ]=at;e->v[WALL_MS]=GetTickCount()-s->requested_tick;e->v[FRAME]=frame();e->v[THREAD]=GetCurrentThreadId();e->v[CALLER]=caller;e->v[FACTORY]=s->factory;e->v[OWNER]=s->owner;e->v[MODULE]=module();e->v[NODE]=node;e->v[RESOURCE]=resource();
 if(node){e->v[QUEUE_ID]=word(node+0x18);e->v[TEMPLATE]=word(node+0x10);e->v[TEMPLATE_HASH]=word(e->v[TEMPLATE]+8);e->v[COST]=word(node+0x30);e->v[PAID_BEFORE]=word(node+0x68);e->v[PAID_AFTER]=e->v[PAID_BEFORE];e->v[PROGRESS_BEFORE]=word(node+0x1c);e->v[PROGRESS_AFTER]=e->v[PROGRESS_BEFORE];e->v[NODE_KIND]=word(node+0xc);}
 e->v[CASH_BEFORE]=cash(e->v[RESOURCE]);e->v[CASH_AFTER]=e->v[CASH_BEFORE];return e;
}
static void publish(TraceEvent* e){if(e)InterlockedExchange(&e->ready,1);}
struct TickContext {uint32_t module,node,queue_id,hash;};
struct PayContext {uint32_t node,queue_id;};
struct ObjectLink {uint32_t node,id,object,object_id,hash,created_frame;};
static ObjectLink latest;
static void object_fields(TraceEvent* e,uint32_t o){if(!e)return;e->v[OBJECT]=o;e->v[OBJECT_ID]=word(o+0xdc);e->v[OBJECT_OWNER]=word(o+0x418);e->v[OBJECT_HASH]=word(word(o+4)+8);for(int i=0;i<3;i++){e->v[OBJECT_X+i]=word(o+0x38+i*4);e->v[FACTORY_X+i]=word(s->factory+0x38+i*4);}e->v[OBJECT_HP]=word(word(o+0x33c)+4);}
typedef uint32_t (__attribute__((thiscall))*TickFn)(void*);
typedef uint32_t (__attribute__((thiscall))*PayFn)(void*,void*);
typedef uint32_t (__attribute__((thiscall))*DebitFn)(void*,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t);
typedef uint32_t (__attribute__((thiscall))*CreateFn)(void*,void*,void*,uint32_t,void*);
typedef void (__attribute__((thiscall))*CompleteFn)(void*,void*);
static TickFn original_tick;static PayFn original_pay;static DebitFn original_debit;static CreateFn original_create;static CompleteFn original_complete;
static uint32_t __attribute__((fastcall)) hook_tick(void* self,void*){
 InterlockedIncrement(&s->active);TickContext local={(uint32_t)(uintptr_t)self-0x10,0,0,0};void* previous=TlsGetValue(tick_tls);bool ours=local.module==module()&&identity();if(ours)TlsSetValue(tick_tls,&local);
 uint32_t result=original_tick(self);
 if(ours){TlsSetValue(tick_tls,previous);if(latest.object&&frame()%10==0&&word(latest.object)==0xc4db60&&word(latest.object+0xdc)==latest.object_id&&word(latest.object+0x418)==s->owner&&word(word(latest.object+4)+8)==hashes){TraceEvent* e=event(7,(uintptr_t)__builtin_return_address(0));if(e){e->v[NODE]=latest.node;e->v[QUEUE_ID]=latest.id;e->v[TEMPLATE_HASH]=latest.hash;e->v[CONTEXT_VALID]=1;e->v[HEAD_AFTER]=word(module()+0x34);object_fields(e,latest.object);publish(e);}}}
 InterlockedDecrement(&s->active);return result;
}
static uint32_t __attribute__((fastcall)) hook_pay(void* self,void*,void* player){
 InterlockedIncrement(&s->active);uint32_t node=(uintptr_t)self;bool ours=identity()&&player==(void*)(uintptr_t)s->owner&&target_node(node);PayContext local={node,word(node+0x18)};void* previous=TlsGetValue(pay_tls);TraceEvent* e=NULL;
 if(ours){TlsSetValue(pay_tls,&local);TickContext* t=(TickContext*)TlsGetValue(tick_tls);if(t&&t->module==module()){t->node=node;t->queue_id=local.queue_id;t->hash=hashes;}e=event(2,(uintptr_t)__builtin_return_address(0),node);if(e)e->v[CONTEXT_VALID]=t&&t->module==module();}
 uint32_t result=original_pay(self,player);
 if(ours){TlsSetValue(pay_tls,previous);if(e){e->v[PAID_AFTER]=word(node+0x68);e->v[PROGRESS_AFTER]=word(node+0x1c);e->v[CASH_AFTER]=cash(e->v[RESOURCE]);e->v[RETURNED]=result;publish(e);}}
 InterlockedDecrement(&s->active);return result;
}
static uint32_t __attribute__((fastcall)) hook_debit(void* self,void*,uint32_t a1,uint32_t a2,uint32_t a3,uint32_t a4,uint32_t a5,uint32_t a6,uint32_t a7,uint32_t a8){
 InterlockedIncrement(&s->active);PayContext* p=(PayContext*)TlsGetValue(pay_tls);uint32_t caller=(uintptr_t)__builtin_return_address(0);TraceEvent* e=NULL;
 if(p&&caller==0x70f578&&self==(void*)(uintptr_t)resource()&&target_node(p->node)&&word(p->node+0x18)==p->queue_id){e=event(3,caller,p->node);if(e){e->v[REQUESTED]=a1;e->v[CONTEXT_VALID]=1;}}
 uint32_t result=original_debit(self,a1,a2,a3,a4,a5,a6,a7,a8);
 if(e){e->v[ACTUAL]=result;e->v[RETURNED]=result;e->v[CASH_AFTER]=cash((uintptr_t)self);publish(e);}InterlockedDecrement(&s->active);return result;
}
static uint32_t __attribute__((fastcall)) hook_create(void* self,void*,void* tmpl,void* creation,uint32_t a3,void* a4){
 InterlockedIncrement(&s->active);uint32_t caller=(uintptr_t)__builtin_return_address(0);TickContext* t=(TickContext*)TlsGetValue(tick_tls);TraceEvent* e=NULL;uint32_t node=0,id=0;
 if(self==(void*)(uintptr_t)module()&&caller==0x7baffe&&t&&t->module==module()&&t->hash==hashes&&target_node(t->node)&&word(t->node+0x18)==t->queue_id&&word(t->node+0x10)==(uintptr_t)tmpl){node=t->node;id=t->queue_id;e=event(4,caller,node);if(e)e->v[CONTEXT_VALID]=1;}
 uint32_t object=original_create(self,tmpl,creation,a3,a4);
 if(e){e->v[RETURNED]=object;object_fields(e,object);if(object&&word(object)==0xc4db60&&e->v[OBJECT_OWNER]==s->owner&&e->v[OBJECT_HASH]==hashes)latest={node,id,object,e->v[OBJECT_ID],hashes,frame()};publish(e);}InterlockedDecrement(&s->active);return object;
}
static void __attribute__((fastcall)) hook_complete(void* self,void*,void* nodeptr){
 InterlockedIncrement(&s->active);uint32_t node=(uintptr_t)nodeptr;TraceEvent* e=NULL;if(self==(void*)(uintptr_t)module()&&target_node(node)){e=event(5,(uintptr_t)__builtin_return_address(0),node);if(e){e->v[HEAD_BEFORE]=word(module()+0x34);if(latest.node==node&&latest.id==e->v[QUEUE_ID]){e->v[CONTEXT_VALID]=1;object_fields(e,latest.object);}}}
 original_complete(self,nodeptr);if(e){e->v[HEAD_AFTER]=word(module()+0x34);publish(e);}InterlockedDecrement(&s->active);
}
struct Hook {uint32_t address;void* detour;void** original;const char* signature;uint32_t length;BYTE before[24];bool made,enabled;};
static Hook hooks[]={
 {0x7ba770,(void*)&hook_tick,(void**)&original_tick,"\x81\xec\x3c\x01\x00\x00\xf6\x05\x48\x6b\xce\x00\x01\x53\x56\x57",16,{},false,false},
 {0x70f440,(void*)&hook_pay,(void**)&original_pay,"\x83\xec\x08\x55\x8b\x6c\x24\x10\x85\xed\x56\x8b\xf1",13,{},false,false},
 {0x849220,(void*)&hook_debit,(void**)&original_debit,"\x81\xec\xb4\x00\x00\x00\x56\x8b\xf1\x8b\x46\x14\x8b\x4e\x04",15,{},false,false},
 {0x73e390,(void*)&hook_create,(void**)&original_create,"\x83\xec\x20\x8b\x44\x24\x24\x8b\x54\x24\x2c\x53\x55",13,{},false,false},
 {0x789bf0,(void*)&hook_complete,(void**)&original_complete,"\x51\x56\x8b\xf1\x80\xbe\x38\x01\x00\x00\x00",11,{},false,false}};
static void stop(){if(!s||InterlockedCompareExchange(&s->stop_owner,1,0))return;for(unsigned i=0;i<5;i++){Hook& h=hooks[i];if(h.enabled){MH_STATUS r=MH_DisableHook((void*)(uintptr_t)h.address);if(r!=MH_OK&&r!=MH_ERROR_DISABLED)s->error=300+i;h.enabled=false;}BYTE b[24]={};if(h.made&&read(h.address,b,h.length)&&!memcmp(b,h.before,h.length))s->restore_mask|=1u<<i;}
 DWORD began=GetTickCount();while(s->active&&GetTickCount()-began<2000)Sleep(1);InterlockedExchange(&s->state,s->restore_mask==31&&!s->active&&!s->error?2:3);}
static DWORD WINAPI watchdog(void*){while(s->state==1&&GetTickCount()-s->requested_tick<s->seconds*1000&&s->request!=2)Sleep(25);stop();return 0;}
static void install(){
 s->callback_thread=GetCurrentThreadId();FILETIME a,b,c,d;if(GetCurrentProcessId()!=s->pid||!GetProcessTimes(GetCurrentProcess(),&a,&b,&c,&d)||a.dwLowDateTime!=s->start_low||a.dwHighDateTime!=s->start_high||GetTickCount()-s->requested_tick>10000||!identity()){s->error=10;InterlockedExchange(&s->state,4);return;}
 if((uintptr_t)GetModuleHandleW(NULL)!=0x400000||word(s->iface)!=0xc3f8c8||word(0xc3f8ec)!=0x723f50){s->error=11;InterlockedExchange(&s->state,4);return;}
 for(unsigned i=0;i<5;i++)if(!read(hooks[i].address,hooks[i].before,hooks[i].length)||memcmp(hooks[i].before,hooks[i].signature,hooks[i].length)){s->error=20+i;InterlockedExchange(&s->state,4);return;}
 if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCSTR)(uintptr_t)&install,&pinned)){s->error=30;InterlockedExchange(&s->state,4);return;}
 tick_tls=TlsAlloc();pay_tls=TlsAlloc();if(tick_tls==TLS_OUT_OF_INDEXES||pay_tls==TLS_OUT_OF_INDEXES){s->error=31;InterlockedExchange(&s->state,4);return;}
 MH_STATUS r=MH_Initialize();if(r!=MH_OK&&r!=MH_ERROR_ALREADY_INITIALIZED){s->error=40+r;InterlockedExchange(&s->state,4);return;}
 for(unsigned i=0;i<5;i++){r=MH_CreateHook((void*)(uintptr_t)hooks[i].address,hooks[i].detour,hooks[i].original);if(r!=MH_OK){s->error=100+i;stop();return;}hooks[i].made=true;}
 InterlockedExchange(&s->state,1);for(unsigned i=0;i<5;i++){r=MH_EnableHook((void*)(uintptr_t)hooks[i].address);if(r!=MH_OK){s->error=200+i;stop();return;}hooks[i].enabled=true;}
 HANDLE thread=CreateThread(NULL,0,watchdog,NULL,0,NULL);if(thread)CloseHandle(thread);else{s->error=290;stop();}
}
extern "C" __declspec(dllexport) LRESULT CALLBACK ProductionTraceControl(int code,WPARAM wp,LPARAM lp){
 if(code>=0&&wp==PM_REMOVE&&lp&&((MSG*)lp)->message==TRACE_MESSAGE&&((MSG*)lp)->wParam==TRACE_MAGIC){if(!s){char name[80];snprintf(name,sizeof(name),"Local\\RA3ProductionTrace_%lu",GetCurrentProcessId());mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);if(mapping)s=(TraceState*)MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(TraceState));}if(s&&s->magic==TRACE_MAGIC){if(s->request==1&&s->ack==0)install();else if(s->request==2)stop();InterlockedExchange(&s->ack,s->request);}}
 return CallNextHookEx(NULL,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE h,DWORD reason,LPVOID){if(reason==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(h);return TRUE;}
