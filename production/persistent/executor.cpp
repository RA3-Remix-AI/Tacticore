#include "shared.h"
#include "MinHook.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
static Persistent* p;static HANDLE mapping;static HMODULE pin;static DWORD tick_tls=TLS_OUT_OF_INDEXES,pay_tls=TLS_OUT_OF_INDEXES;
static bool read(uint32_t a,void* out,SIZE_T n){SIZE_T got=0;return ReadProcessMemory(GetCurrentProcess(),(void*)(uintptr_t)a,out,n,&got)&&got==n;}
static uint32_t word(uint32_t a){uint32_t v=0;read(a,&v,4);return v;}
static uint32_t frame(){return word(word(0xcd8ce4)+0x50);}
static bool allowed(uint32_t h){return h==0x19ab11af||h==0x2c358c61||h==0x33026fa1;}
static bool old_allowed(uint32_t h){return allowed(h)||h==0xa08aabd3;}
static uint32_t resource(){uint32_t a=word(p->owner+0xe4),b=word(p->owner+0xe8);return a&&b>=a+4&&b-a<=64?word(a):0;}
static uint32_t cash(uint32_t r){return word(r+4)+word(r+0x14);}
static bool basic_identity(){return word(p->owner)==0xc5bce0&&word(p->owner+0x20)==3&&word(p->owner+0x10)==p->player_template&&word(p->owner+0x90)==p->ai&&word(p->ai)==0xc60f60&&word(p->ai+8)==p->owner&&word(p->ai+0x8a8)==p->owner&&word(p->ai+0x8b0)==p->personality&&word(p->personality+0x18)==p->personality_id;}
static bool personality_identity(){
 if(!basic_identity())return false;
 uint32_t store=word(0xce98ec);if(word(store)!=0xc606b8)return false;uint32_t a=word(store+0x24),b=word(store+0x28);if(!a||b<a||b-a>16384||(b-a)%4)return false;uint32_t hits=0,ids=0;for(uint32_t q=a;q<b;q+=4){uint32_t x=word(q);hits+=x==p->personality;ids+=word(x+0x18)==p->personality_id;}if(hits!=1||ids!=1)return false;uint32_t data=word(p->personality),count=word(data+0xec),array=word(data+0xf0);if(count<1||count>32)return false;uint32_t matches=0;for(uint32_t i=0;i<count;i++)matches+=word(array+4*i)==p->player_template;return matches>0;
}
static bool signatures(){
 const BYTE build[]={0x81,0xec,0xa8,0,0,0,0x53,0x8b,0xd9,0x8b,0x43,0xdc,0x8b,0x50,0x58,0x55,0x8d,0x6b,0xdc};const BYTE find[]={0x83,0xec,8,0x56,0x8d,0x71,0x28,0x8d,0x44,0x24,0x10,0x50,0x8d,0x4c,0x24,8,0x51,0x8b,0xce,0xe8};const BYTE price[]={0x8b,0x44,0x24,0x0c,0x83,0xf8,0xff,0x56,0x57,0x8b,0xf1};BYTE b[24];return (uintptr_t)GetModuleHandleW(NULL)==0x400000&&read(0x723f50,b,sizeof(build))&&!memcmp(b,build,sizeof(build))&&read(0x7e4230,b,sizeof(find))&&!memcmp(b,find,sizeof(find))&&read(0x7df7e0,b,sizeof(price))&&!memcmp(b,price,sizeof(price));
}
static void begin(Receipt* r){InterlockedIncrement(&r->updates);}static void end(Receipt* r){InterlockedIncrement(&r->version);InterlockedDecrement(&r->updates);}
static bool receipt_factory(const Receipt* r){uint32_t f=r->command.factory;return word(f)==0xc4db60&&word(f+0xdc)==r->command.factory_id&&word(f+0x418)==p->owner&&word(word(f+4)+8)==0x80d4ea1e&&word(r->command.iface-0x1c)==f;}
static Receipt* find_receipt(uint32_t node){if(!node)return NULL;uint32_t id=word(node+0x18),module=word(node+4);for(uint32_t i=0;i<p->count;i++){Receipt* r=&p->ledger[i];if(r->state>=2&&r->node==node&&r->queue_id==id&&r->command.iface-0x24==module&&word(node+0xc)==1&&word(word(node+0x10)+8)==r->command.hash&&receipt_factory(r))return r;}return NULL;}
struct Tick {uint32_t module;Receipt* receipt;};struct Pay {Receipt* receipt;uint32_t resource,before;};
typedef uint32_t (__attribute__((thiscall))*TickFn)(void*);typedef uint32_t (__attribute__((thiscall))*PayFn)(void*,void*);typedef uint32_t (__attribute__((thiscall))*DebitFn)(void*,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t);typedef uint32_t (__attribute__((thiscall))*CreateFn)(void*,void*,void*,uint32_t,void*);typedef void (__attribute__((thiscall))*CompleteFn)(void*,void*);
static TickFn original_tick;static PayFn original_pay;static DebitFn original_debit;static CreateFn original_create;static CompleteFn original_complete;
static uint32_t __attribute__((fastcall)) hook_tick(void* self,void*){
 InterlockedIncrement(&p->active);Tick local={(uint32_t)(uintptr_t)self-0x10,NULL};void* previous=TlsGetValue(tick_tls);bool ours=GetCurrentThreadId()==p->thread&&basic_identity();if(ours)TlsSetValue(tick_tls,&local);uint32_t result=original_tick(self);
 if(ours){TlsSetValue(tick_tls,previous);for(uint32_t i=0;i<p->count;i++){Receipt* r=&p->ledger[i];if(!r->created||!r->completed||r->command.iface-0x24!=local.module||!receipt_factory(r))continue;uint32_t o=r->object;if(word(o)==0xc4db60&&word(o+0xdc)==r->object_id&&word(o+0x418)==p->owner&&word(word(o+4)+8)==r->command.hash){float hp=0;read(word(o+0x33c)+4,&hp,4);if(isfinite(hp)&&hp>0){begin(r);r->live_samples++;r->object_hp_bits=word(word(o+0x33c)+4);r->object_x_bits=word(o+0x38);r->object_y_bits=word(o+0x3c);r->factory_x_bits=word(r->command.factory+0x38);r->factory_y_bits=word(r->command.factory+0x3c);end(r);}}}}
 InterlockedDecrement(&p->active);return result;
}
static uint32_t __attribute__((fastcall)) hook_pay(void* self,void*,void* player){
 InterlockedIncrement(&p->active);Receipt* r=GetCurrentThreadId()==p->thread&&player==(void*)(uintptr_t)p->owner?find_receipt((uintptr_t)self):NULL;Pay local={r,resource(),r?r->paid:0};void* previous=TlsGetValue(pay_tls);if(r){begin(r);if(word((uintptr_t)self+0x68)!=r->paid)r->payment_error=1;Tick* t=(Tick*)TlsGetValue(tick_tls);if(t&&t->module==r->command.iface-0x24)t->receipt=r;else r->payment_error=2;TlsSetValue(pay_tls,&local);}
 uint32_t result=original_pay(self,player);if(r){TlsSetValue(pay_tls,previous);if(word((uintptr_t)self+0x68)!=r->paid||r->paid>r->cost)r->payment_error=3;end(r);}InterlockedDecrement(&p->active);return result;
}
static uint32_t __attribute__((fastcall)) hook_debit(void* self,void*,uint32_t a,uint32_t b,uint32_t c,uint32_t d,uint32_t e,uint32_t f,uint32_t g,uint32_t h){
 InterlockedIncrement(&p->active);Pay* context=(Pay*)TlsGetValue(pay_tls);Receipt* r=context&&GetCurrentThreadId()==p->thread&&(uintptr_t)__builtin_return_address(0)==0x70f578&&(uintptr_t)self==context->resource?context->receipt:NULL;uint32_t before=r?cash((uintptr_t)self):0;if(r)begin(r);uint32_t actual=original_debit(self,a,b,c,d,e,f,g,h);if(r){if(actual>a||before-cash((uintptr_t)self)!=actual)r->payment_error=4;r->paid+=actual;if(actual)r->debit_count++;end(r);}InterlockedDecrement(&p->active);return actual;
}
static uint32_t __attribute__((fastcall)) hook_create(void* self,void*,void* tmpl,void* creation,uint32_t flag,void* xyz){
 InterlockedIncrement(&p->active);Tick* t=(Tick*)TlsGetValue(tick_tls);Receipt* r=t&&t->module==(uintptr_t)self&&(uintptr_t)__builtin_return_address(0)==0x7baffe?t->receipt:NULL;if(r&&(word(word(r->node+0x10)+8)!=r->command.hash||word((uintptr_t)tmpl+8)!=r->command.hash))r=NULL;if(r)begin(r);uint32_t o=original_create(self,tmpl,creation,flag,xyz);if(r){if(o&&word(o)==0xc4db60&&word(o+0x418)==p->owner&&word(word(o+4)+8)==r->command.hash&&r->paid==r->cost&&!r->payment_error){r->created=1;r->object=o;r->object_id=word(o+0xdc);r->object_owner=word(o+0x418);r->object_hash=word(word(o+4)+8);}end(r);}InterlockedDecrement(&p->active);return o;
}
static void __attribute__((fastcall)) hook_complete(void* self,void*,void* node){
 InterlockedIncrement(&p->active);Receipt* r=GetCurrentThreadId()==p->thread&&(uintptr_t)__builtin_return_address(0)==0x7bb7b6?find_receipt((uintptr_t)node):NULL;if(r&&(uintptr_t)self!=r->command.iface-0x24)r=NULL;if(r){begin(r);if(r->created&&r->paid==r->cost&&!r->payment_error){r->completed=1;r->completion_frame=frame();}end(r);}original_complete(self,node);InterlockedDecrement(&p->active);
}
struct Hook {uint32_t address;void* detour;void** original;const char* bytes;uint32_t length;BYTE before[20];bool made,enabled;};
static Hook hooks[]={
 {0x7ba770,(void*)&hook_tick,(void**)&original_tick,"\x81\xec\x3c\x01\x00\x00\xf6\x05\x48\x6b\xce\x00\x01\x53\x56\x57",16,{},false,false},
 {0x70f440,(void*)&hook_pay,(void**)&original_pay,"\x83\xec\x08\x55\x8b\x6c\x24\x10\x85\xed\x56\x8b\xf1",13,{},false,false},
 {0x849220,(void*)&hook_debit,(void**)&original_debit,"\x81\xec\xb4\x00\x00\x00\x56\x8b\xf1\x8b\x46\x14\x8b\x4e\x04",15,{},false,false},
 {0x73e390,(void*)&hook_create,(void**)&original_create,"\x83\xec\x20\x8b\x44\x24\x24\x8b\x54\x24\x2c\x53\x55",13,{},false,false},
 {0x789bf0,(void*)&hook_complete,(void**)&original_complete,"\x51\x56\x8b\xf1\x80\xbe\x38\x01\x00\x00\x00",11,{},false,false}};
static volatile LONG stop_owner;
static void stop(){if(InterlockedCompareExchange(&stop_owner,1,0))return;InterlockedExchange(&p->stop_requested,1);for(unsigned i=0;i<5;i++){Hook& h=hooks[i];if(h.enabled){MH_DisableHook((void*)(uintptr_t)h.address);h.enabled=false;}BYTE b[20];if(h.made&&read(h.address,b,h.length)&&!memcmp(b,h.before,h.length))p->restore_mask|=1u<<i;}DWORD start=GetTickCount();while(p->active&&GetTickCount()-start<2000)Sleep(1);InterlockedExchange(&p->phase,p->restore_mask==31&&!p->active&&!p->error?2:4);}
static DWORD WINAPI watchdog(void*){while(p->phase==1&&!p->stop_requested&&GetTickCount()-(DWORD)p->heartbeat<5000)Sleep(50);stop();return 0;}
struct Prior {uint32_t address,id,tmpl,cost,paid;};
static bool queue_check(const Command& c,Prior prior[2],uint32_t& count,uint32_t& debt){uint32_t module=c.iface-0x24,head=word(module+0x34),tail=word(module+0x38),prev=0,n=head;count=0;debt=0;if(c.queue_limit>2||!!head!=!!tail)return false;while(n){if(count>=c.queue_limit||n%4||word(n+4)!=module||word(n+0xc)!=1||word(n+0x58)!=prev)return false;uint32_t id=word(n+0x18),tmpl=word(n+0x10),cost=word(n+0x30),paid=word(n+0x68);if(!id||!old_allowed(word(tmpl+8))||!cost||cost>10000||paid>cost||(count&&prior[0].id==id))return false;prior[count++]={n,id,tmpl,cost,paid};debt+=cost-paid;prev=n;n=word(n+0x54);}return prev==tail;}
static bool preserve(const Command& c,const Prior prior[2],uint32_t count,uint32_t n,uint32_t id,uint32_t cost){uint32_t module=c.iface-0x24;if(word(module+0x34)!=(count?prior[0].address:n)||word(module+0x38)!=n||word(n+4)!=module||word(n+0x18)!=id||word(n+0xc)!=1||word(word(n+0x10)+8)!=c.hash||word(n+0x30)!=cost||word(n+0x68)||word(n+0x54)||word(n+0x58)!=(count?prior[count-1].address:0))return false;for(uint32_t i=0;i<count;i++){const Prior& q=prior[i];if(q.address==n||q.id==id||word(q.address+4)!=module||word(q.address+0xc)!=1||word(q.address+0x18)!=q.id||word(q.address+0x10)!=q.tmpl||word(q.address+0x30)!=q.cost||word(q.address+0x68)!=q.paid||word(q.address+0x58)!=(i?prior[i-1].address:0)||word(q.address+0x54)!=(i+1<count?prior[i+1].address:n))return false;}return true;}
static void execute(Receipt* r){const Command& c=r->command;r->frame=frame();
 if(p->stop_requested||p->phase!=1||GetCurrentThreadId()!=p->thread||GetTickCount()-c.requested_tick>5000||!personality_identity()||memcmp(c.session,p->session,16)||memcmp(c.commander,p->commander,16)){r->error=1;return;}
 if(word(word(0xcd8ce4)+0x15c)!=0){r->error=12;return;}
 if(r->frame<p->last_frame||r->frame>c.expires||c.expires-r->frame>900){r->error=2;return;}p->last_frame=r->frame;
 if(!allowed(c.hash)||c.budget<1||c.budget>1000||c.reserve<p->reserve_floor||c.reserve>100000||c.queue_limit>2){r->error=3;return;}
 if(p->last_accepted_frame&&r->frame-p->last_accepted_frame<p->min_interval){r->error=4;return;}
 if(!receipt_factory(r)||word(c.iface)!=0xc3f8c8||word(0xc3f8ec)!=0x723f50||word(word(c.factory+0x3b4)+0x14)!=c.iface||!word(c.factory+0x310)||!word(c.factory+0x3c0)||!signatures()){r->error=5;return;}
 float hp=0;read(word(c.factory+0x33c)+4,&hp,4);if(!isfinite(hp)||hp<=0){r->error=6;return;}
 Prior prior[2]={};uint32_t count=0,debt=0;if(!queue_check(c,prior,count,debt)){r->error=7;return;}r->liability=debt;r->prior_count=count;r->cash=cash(resource());
 typedef void* (__attribute__((thiscall))*Find)(void*,uint32_t);void* tmpl=((Find)0x7e4230)((void*)(uintptr_t)word(0xce6c58),c.hash);if(!tmpl||word((uintptr_t)tmpl+8)!=c.hash||(word((uintptr_t)tmpl+0xd0)&(1u<<26))){r->error=8;return;}
 typedef uint32_t (__attribute__((thiscall))*Price)(void*,void*,void*,uint32_t);uint32_t price=((Price)0x7df7e0)(tmpl,(void*)(uintptr_t)p->owner,(void*)(uintptr_t)c.factory,0xffffffff);r->quoted_cost=price;
 if(!price||price>c.budget||p->spent>p->total_budget||price>p->total_budget-p->spent||price+debt+c.reserve>r->cash){r->error=9;return;}
 typedef uint32_t (__attribute__((thiscall))*Build)(void*,void*,uint32_t,void*,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t);r->attempted=1;r->queue_id=((Build)0x723f50)((void*)(uintptr_t)c.iface,tmpl,0,(void*)0xcd7e84,0,0,0,0,0);
 if(!r->queue_id){r->error=10;return;}uint32_t n=word(c.iface+0x10);for(int i=0;n&&i<128;i++){if(word(n+0x18)==r->queue_id&&word(n+0x10)==(uintptr_t)tmpl){r->node=n;break;}uint32_t next=word(n+0x54);if(next==n)break;n=next;}
 r->cost=word(r->node+0x30);r->preserved=r->node&&preserve(c,prior,count,r->node,r->queue_id,price);if(!r->preserved){r->error=11;InterlockedExchange(&p->stop_requested,1);return;}p->spent+=r->cost;p->last_accepted_frame=r->frame;r->state=2;
}
static void submit(){
 if(InterlockedCompareExchange(&p->request_state,2,1)!=1)return;
 p->reply_index=0xffffffff;p->reply_error=0;Command c=p->request;
 for(uint32_t i=0;i<p->count;i++){Receipt& r=p->ledger[i];if(!memcmp(r.command.id,c.id,16)){Command prior=r.command,now=c;prior.requested_tick=now.requested_tick=0;if(memcmp(&prior,&now,sizeof(Command)))p->reply_error=104;else p->reply_index=i;InterlockedExchange(&p->request_state,3);return;}if(!memcmp(r.command.task,c.task,16)){p->reply_error=102;InterlockedExchange(&p->request_state,3);return;}}
 if(c.seq<=p->last_seq||p->count>=P_CAP){p->reply_error=103;InterlockedExchange(&p->request_state,3);return;}p->last_seq=c.seq;uint32_t index=p->count++;Receipt* r=&p->ledger[index];begin(r);r->command=c;r->state=1;execute(r);if(r->state!=2)r->state=r->attempted&&r->error!=10?4:3;end(r);p->reply_index=index;InterlockedExchange(&p->request_state,3);
}
static void install(){
 p->callback_thread=GetCurrentThreadId();FILETIME a,b,c,d;if(GetCurrentProcessId()!=p->pid||p->callback_thread!=p->thread||!GetProcessTimes(GetCurrentProcess(),&a,&b,&c,&d)||a.dwLowDateTime!=p->start_low||a.dwHighDateTime!=p->start_high||!personality_identity()||!signatures()){p->error=10;p->phase=4;return;}
 if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCSTR)(uintptr_t)&install,&pin)){p->error=11;p->phase=4;return;}tick_tls=TlsAlloc();pay_tls=TlsAlloc();if(tick_tls==TLS_OUT_OF_INDEXES||pay_tls==TLS_OUT_OF_INDEXES){p->error=12;p->phase=4;return;}
 for(unsigned i=0;i<5;i++)if(!read(hooks[i].address,hooks[i].before,hooks[i].length)||memcmp(hooks[i].before,hooks[i].bytes,hooks[i].length)){p->error=20+i;p->phase=4;return;}
 MH_STATUS status=MH_Initialize();if(status!=MH_OK&&status!=MH_ERROR_ALREADY_INITIALIZED){p->error=30;p->phase=4;return;}
 for(unsigned i=0;i<5;i++){status=MH_CreateHook((void*)(uintptr_t)hooks[i].address,hooks[i].detour,hooks[i].original);if(status!=MH_OK){p->error=40+i;stop();return;}hooks[i].made=true;}
 p->last_frame=frame();p->start_frame=p->last_frame;p->phase=1;for(unsigned i=0;i<5;i++){status=MH_EnableHook((void*)(uintptr_t)hooks[i].address);if(status!=MH_OK){p->error=50+i;stop();return;}hooks[i].enabled=true;}
 HANDLE t=CreateThread(NULL,0,watchdog,NULL,0,NULL);if(t)CloseHandle(t);else{p->error=60;stop();}
}
extern "C" __declspec(dllexport) LRESULT CALLBACK PersistentControl(int code,WPARAM wp,LPARAM lp){
 if(code>=0&&wp==PM_REMOVE&&lp&&((MSG*)lp)->message==P_MESSAGE&&((MSG*)lp)->wParam==P_MAGIC){if(!p){char name[80];snprintf(name,sizeof(name),"Local\\RA3ProductionPersistent_%lu",GetCurrentProcessId());mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);if(mapping)p=(Persistent*)MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Persistent));}if(p&&p->magic==P_MAGIC){if(p->phase==0)install();else if(p->phase==1&&!p->stop_requested)submit();}}
 return CallNextHookEx(NULL,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE h,DWORD why,LPVOID){if(why==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(h);return TRUE;}
