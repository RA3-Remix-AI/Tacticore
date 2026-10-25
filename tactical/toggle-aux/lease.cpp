#include "shared.h"
#include "MinHook.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
static Tactical* p;static HANDLE mapping;static HMODULE pin;static HWND window;static UINT_PTR timer;static uint32_t tag,start_tick,last_seq,used_count;static uint32_t used_commands[128][4],used_tasks[128][4],used_tokens[128];
static bool read(uint32_t a,void* b,SIZE_T n){SIZE_T got=0;return ReadProcessMemory(GetCurrentProcess(),(void*)(uintptr_t)a,b,n,&got)&&got==n;}
static uint32_t word(uint32_t a){uint32_t v=0;read(a,&v,4);return v;}
static uint32_t frame(){return word(p->logic+0x50);}static bool paused(){return word(p->logic+0x15c)!=0;}
static bool identity(){return word(0xcd8ce4)==p->logic&&word(p->logic)==0xbeb630&&word(p->owner)==0xc5bce0&&word(p->owner+0x20)==3&&word(p->owner+0x10)==p->player_template&&word(p->owner+0x90)==p->ai&&word(p->ai)==0xc60f60&&word(p->ai+8)==p->owner&&word(p->ai+0x8b0)==p->personality&&word(p->personality+0x18)==p->personality_id;}
static bool unit(){float hp=0;return word(p->unit)==0xc4db60&&word(p->unit+0xdc)==p->object_id&&word(p->unit+0x418)==p->owner&&word(word(p->unit+4)+8)==p->type_hash&&word(p->unit+0x374)==p->update&&word(p->update+8)==p->unit&&read(word(p->unit+0x33c)+4,&hp,4)&&isfinite(hp)&&hp>0;}

static uint32_t cash(){uint32_t first=word(p->owner+0xe4),end=word(p->owner+0xe8);if(!first||end<first+4||end-first>64)return 0;uint32_t r=word(first);return word(r+4)+word(r+0x14);}
static uint32_t current_weapon(uint32_t* entry,uint32_t* ammo){*entry=*ammo=0;uint32_t container=word(p->unit+0x37c);if(word(container+8)!=p->unit)return 0;uint32_t a=word(container+0x24),z=word(container+0x28);if(!a||z<a||z-a>256||(z-a)%4)return 0;for(;a<z;a+=4){uint32_t slot=word(a);if(word(slot)!=0xc3a6e0||word(0xc3a6e0+0x24)!=0x6dbe80||word(0xc3a6e0+0x28)!=0x6f88e0)return 0;uint32_t index=word(slot+0x14);if(index>5)return 0;if(index==5)continue;uint32_t e=word(word(slot+0x94)+4*index);if(!e)continue;if(word(e)!=0xc2e324||word(e+8)!=slot)return 0;uint32_t h=word(word(word(e+4)+4));if(word(h)!=0x94d4d96e)return 0;*entry=e;*ammo=word(e+0x1c);return word(h+4);}return 0;}
static bool button_identity(){uint32_t key=word(p->unit+0x464);if(!key){if(word(word(p->unit+0x78)+0x2c)!=0x6de330)return false;key=word(word(word(p->unit+4)+0x14)+0x94);}if(key!=0xb74cf71a||key!=p->command_set||word(p->button)!=0xbe9170||word(p->button+4)!=p->button_schema||word(p->button_schema+4)!=1)return false;uint32_t h=word(p->button_schema);if(word(h)!=0x7d464170||word(h+4)!=0x5977a798)return false;uint32_t store=word(0xcd8d00),node=word(store+0x4c),found=0;for(unsigned i=0;node&&i<128;i++){uint32_t k=word(node+0x10);if(k==key){found=node;break;}node=word(node+(k>=key?4:0));}if(!found)return false;uint32_t list=word(found+0x14)+8;if(word(list)!=0xbe9178||word(0xbe9178)!=0x524c70||word(0xbe9178+0xc)!=0x4d8fc0)return false;uint32_t inner=word(list+4),count=word(inner+4),items=word(inner+8),matches=0;if(!items||!count||count>64)return false;for(unsigned i=0;i<count;i++)matches+=word(items+i*4)==p->button;return matches==1;}
static void event(uint32_t kind,uint32_t arg=0,uint32_t caller=0){LONG i=InterlockedIncrement(&p->count)-1;if(i>=T_CAP){p->overflow=1;return;}Event e={};e.seq=i+1;e.kind=kind;e.tag=tag;e.frame=frame();e.tick=GetTickCount();e.thread=GetCurrentThreadId();e.caller=caller;e.team=word(p->unit+0x414);e.owner=word(p->unit+0x418);e.source=word(p->update+0x50);e.arg=arg;read(p->unit+0x38,&e.x,12);e.sm=word(p->update+0x3c);e.sm_flags=word(e.sm+0x78);e.state=word(e.sm+4);e.state_id=word(e.state+4);e.path=word(p->update+0x150);e.path_node=word(e.path+0x10);read(e.sm+0x2c,e.requested,12);read(e.sm+0x48,e.effective,12);read(e.path_node+0xc,e.path_xy,8);e.weapon_asset=current_weapon(&e.weapon_entry,&e.weapon_ammo);e.status84=word(p->unit+0x84);e.cash=(int32_t)cash();e.seq=0;p->events[i]=e;MemoryBarrier();InterlockedExchange((LONG*)&p->events[i].seq,i+1);}
typedef void (__attribute__((thiscall))*Move)(void*,float*,uint32_t);typedef void (__attribute__((thiscall))*Attack)(void*,void*,uint32_t,uint32_t);typedef void (__attribute__((thiscall))*Transfer)(void*,void*,uint32_t);typedef void (__attribute__((thiscall))*Member)(void*,void*);
typedef void (__attribute__((thiscall))*Stop)(void*,uint32_t);static Stop old_stop_facade,old_stop_private;
static Move old_move;static Attack old_attack;static Transfer old_transfer;static Member old_add,old_remove;
static void __attribute__((fastcall)) move_hook(void* self,void*,float* xyz,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update;if(ours){if(!tag)p->native_move++;event(10,source,(uintptr_t)__builtin_return_address(0));}old_move(self,xyz,source);if(ours)event(11,source);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) attack_hook(void* self,void*,void* target,uint32_t shots,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update;if(ours){if(!tag)p->native_attack++;event(12,source,(uintptr_t)__builtin_return_address(0));}old_attack(self,target,shots,source);if(ours)event(13,source);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) transfer_hook(void* self,void*,void* target,uint32_t to_ai){InterlockedIncrement(&p->active);bool ours=(uintptr_t)target==p->unit;if(ours)event(14,to_ai,(uintptr_t)__builtin_return_address(0));old_transfer(self,target,to_ai);if(ours)event(15,to_ai);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) add_hook(void* self,void*,void* target){InterlockedIncrement(&p->active);bool ours=(uintptr_t)target==p->unit;if(ours){if(!tag)p->native_add++;event(16,(uintptr_t)self,(uintptr_t)__builtin_return_address(0));}old_add(self,target);if(ours)event(17,(uintptr_t)self);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) remove_hook(void* self,void*,void* target){InterlockedIncrement(&p->active);bool ours=(uintptr_t)target==p->unit;if(ours){if(!tag)p->native_remove++;event(18,(uintptr_t)self,(uintptr_t)__builtin_return_address(0));}old_remove(self,target);if(ours)event(19,(uintptr_t)self);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) stop_facade_hook(void* self,void*,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update+0x24;if(ours)event(20,source,(uintptr_t)__builtin_return_address(0));old_stop_facade(self,source);if(ours)event(21,source);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) stop_private_hook(void* self,void*,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update;uint32_t caller=(uintptr_t)__builtin_return_address(0);if(ours)event(22,source,caller);old_stop_private(self,source);if(ours){if((p->phase==1||p->phase==6)&&!p->move_calls&&p->stop_calls&&source==1&&caller==0x787791){p->private_stop_calls++;p->private_stop_frame=frame();}event(23,source,caller);}InterlockedDecrement(&p->active);}

typedef uint32_t (__attribute__((thiscall))*Button)(void*,void*,uint32_t,uint32_t);static Button old_button;
static uint32_t __attribute__((fastcall)) button_hook(void* self,void*,void* button,uint32_t source,uint32_t third){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->unit;if(ours){if(tag==5&&(uintptr_t)button==p->button&&source==1&&third==0)p->toggle_hook_calls++;event(32,(uintptr_t)button,(uintptr_t)__builtin_return_address(0));}uint32_t result=old_button(self,button,source,third);if(ours)event(33,result);InterlockedDecrement(&p->active);return result;}
struct Hook {uint32_t a;void* fn;void** original;const char* signature;uint32_t n;BYTE before[24];bool made,enabled;};
static Hook hooks[]={
{0x6eff70,(void*)move_hook,(void**)&old_move,"\x56\x8b\xf1\x8b\x4e\x3c\x8b\x01\x8b\x50\x38\xff\xd2",13,{},false,false},
{0x76e690,(void*)attack_hook,(void**)&old_attack,"\x83\x7c\x24\x04\x00\x55\x56\x8b\xf1\x8b\x6e\x08",12,{},false,false},
{0x838820,(void*)transfer_hook,(void**)&old_transfer,"\x8b\x81\x8c\x00\x00\x00\x85\xc0\x74\x4f\x56\x8b\xb1\x90\x00\x00\x00",17,{},false,false},
{0x8d8880,(void*)add_hook,(void**)&old_add,"\x83\xec\x24\x56\x8b\x74\x24\x2c\x8b\x46\x04",11,{},false,false},
{0x8cd630,(void*)remove_hook,(void**)&old_remove,"\x83\xec\x34\x53\x57\x8b\x7c\x24\x40\x8b\x47\x04",12,{},false,false},
{0x54b0a0,(void*)stop_facade_hook,(void**)&old_stop_facade,"\x83\xec\x5c\x8b\x44\x24\x60\x56\x6a\x01\x50\x8b\xf1",13,{},false,false},
{0x721ad0,(void*)stop_private_hook,(void**)&old_stop_private,"\x83\xec\x08\x55\x8b\xe9\x8b\x45\x08\x8b\x48\x04",12,{},false,false},
{0x790990,(void*)button_hook,(void**)&old_button,"\x8b\x44\x24\x0c\x8b\x54\x24\x08\x6a\x00\x6a\x00\x6a\x00",14,{},false,false}};
static void finish(){if(timer){KillTimer(window,timer);timer=0;}event(4);for(unsigned i=0;i<8;i++){Hook& h=hooks[i];if(h.enabled){MH_DisableHook((void*)(uintptr_t)h.a);h.enabled=false;}BYTE b[24];if(h.made&&read(h.a,b,h.n)&&!memcmp(b,h.before,h.n))p->restore_mask|=1u<<i;}p->phase=p->error?4:3;}
static void CALLBACK tick(HWND,UINT,UINT_PTR,DWORD){
 if(GetCurrentThreadId()!=p->thread){p->error=30;return;}if(!identity()&&p->phase==2&&p->return_verified){p->post_actor_disposed=1;finish();return;}if(!identity()){p->error=31;p->lifecycle_fail++;finish();return;}
 if(p->phase==2&&p->return_verified&&(!unit()||!identity())){p->post_actor_disposed=1;finish();return;}if(!unit()){p->error=32;p->lifecycle_fail++;finish();return;}
 if(paused()){p->paused_samples++;if(p->phase==1&&(p->stop_requested||GetTickCount()-start_tick>60000))p->return_pending=1;return;}
 uint32_t now=frame();
 if(p->phase==5){
  if(p->stop_requested||GetTickCount()-start_tick>60000){p->error=33;finish();return;}
  uint32_t entry=0,ammo=0;uint32_t asset=current_weapon(&entry,&ammo);if((word(p->unit+0x84)&0x20080000)||!button_identity()||asset!=0x41872ecc||word(p->unit+0x26c)||word(p->owner+0xac)!=p->default_team||word(word(p->owner+0x8c)+0x10)!=p->script_team){p->error=34;finish();return;}p->initial_weapon_asset=asset;p->initial_weapon_entry=entry;p->cash_before=cash();
  p->phase=6;p->original_team=word(p->unit+0x414);p->issued_frame=now;tag=1;p->detach_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->unit,0);event(1);tag=0;
  if(!unit()||word(p->unit+0x414)!=p->script_team){p->error=35;p->phase=1;p->return_pending=1;return;}
  if(paused()){p->phase=1;p->return_pending=1;return;}
  if(word(p->update)!=0xc48670||word(p->update+0x24)!=0xc48528||word(0xc48528)!=0x787500||word(0xc48670+0x8c)!=0x721ad0){p->error=43;p->phase=1;p->return_pending=1;return;}
  read(p->unit+0x38,p->stopped_xyz,12);tag=4;p->stop_calls++;((Stop)0x54b0a0)((void*)(uintptr_t)(p->update+0x24),1);event(6);tag=0;p->phase=1;return;
 }
 event(3);if(p->phase==1){float xyz[3];read(p->unit+0x38,xyz,12);
  if(!p->toggle_calls&&!p->return_pending&&!p->stop_requested&&now!=p->last_sample_frame){p->last_sample_frame=now;uint32_t sm=word(p->update+0x3c);bool gate=p->private_stop_calls==1&&now>p->private_stop_frame&&word(p->update+0x50)==1&&!(word(sm+0x78)&0xffff)&&word(p->update+0x150)==0;
   float sx=xyz[0]-p->stopped_xyz[0],sy=xyz[1]-p->stopped_xyz[1];if(gate){p->stop_gate_samples++;if(sx*sx+sy*sy<=1)p->stable_samples++;else p->stable_samples=0;}else{p->stop_gate_samples=0;p->stable_samples=0;}memcpy(p->stopped_xyz,xyz,12);
   if(p->stable_samples>=3&&p->stop_gate_samples>=3){event(24);uint32_t e=0,a=0;if(!button_identity()||word(p->unit+0x26c)||current_weapon(&e,&a)!=0x41872ecc){p->error=45;p->return_pending=1;}else{tag=5;p->toggle_calls++;p->toggle_frame=now;p->button_result=((Button)0x790990)((void*)(uintptr_t)p->unit,(void*)(uintptr_t)p->button,1,0);event(30);tag=0;}}
   else if(now-p->issued_frame>=30){p->error=44;p->return_pending=1;}
  }
  if(p->toggle_calls&&now!=p->last_ak_frame){p->last_ak_frame=now;p->observed_weapon_asset=current_weapon(&p->observed_weapon_entry,&p->observed_ammo);if(p->observed_weapon_asset==0x447ea26e&&now-p->toggle_frame>=15)p->ak_samples++;else p->ak_samples=0;if(p->ak_samples==3)event(31);}

  if(p->stop_requested||p->return_pending||p->ak_samples>=3||now-p->issued_frame>=p->lease_frames||GetTickCount()-start_tick>60000){
   if(p->native_add){p->error=36;finish();return;}
   tag=3;p->return_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->unit,1);event(5);tag=0;p->returned_frame=now;p->cash_after=cash();p->return_pending=0;p->return_verified=unit()&&word(p->unit+0x414)==p->default_team;p->phase=2;if(!p->return_verified){p->error=37;finish();}
  }
 }else if(p->phase==2&&now-p->returned_frame>=p->post_frames)finish();
}
static void install(HWND hwnd){p->callback_thread=GetCurrentThreadId();FILETIME a,b,c,d;
 if(p->magic!=T_MAGIC||p->version!=1||GetCurrentProcessId()!=p->pid||p->thread!=p->callback_thread||!GetProcessTimes(GetCurrentProcess(),&a,&b,&c,&d)||a.dwLowDateTime!=p->start_low||a.dwHighDateTime!=p->start_high||!identity()||!unit()||p->type_hash!=0x19ab11af||p->lease_frames>180||p->lease_frames<30||p->post_frames<30||p->post_frames>180){p->error=10;p->phase=4;return;}
 if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCSTR)(uintptr_t)&install,&pin)){p->error=11;p->phase=4;return;}
 for(unsigned i=0;i<8;i++)if(!read(hooks[i].a,hooks[i].before,hooks[i].n)||memcmp(hooks[i].before,hooks[i].signature,hooks[i].n)){p->error=12+i;p->phase=4;return;}
 if(used_count>=128||!p->token||p->seq<=last_seq){p->error=40;p->restore_mask=255;p->phase=4;return;}for(unsigned i=0;i<used_count;i++)if(used_tokens[i]==p->token||!memcmp(used_commands[i],p->command,16)||!memcmp(used_tasks[i],p->task,16)){p->error=41;p->restore_mask=255;p->phase=4;return;}uint32_t nonzero_command=0,nonzero_task=0;for(unsigned i=0;i<4;i++){nonzero_command|=p->command[i];nonzero_task|=p->task[i];}if(!nonzero_command||!nonzero_task){p->error=42;p->restore_mask=255;p->phase=4;return;}memcpy(used_commands[used_count],p->command,16);memcpy(used_tasks[used_count],p->task,16);used_tokens[used_count++]=p->token;last_seq=p->seq;
 MH_STATUS s=MH_Initialize();if(s!=MH_OK&&s!=MH_ERROR_ALREADY_INITIALIZED){p->error=20;p->phase=4;return;}
 for(unsigned i=0;i<8;i++){Hook& h=hooks[i];if(!h.made&&MH_CreateHook((void*)(uintptr_t)h.a,h.fn,h.original)!=MH_OK){p->error=21;finish();return;}h.made=true;}
 for(unsigned i=0;i<8;i++){Hook& h=hooks[i];if(MH_EnableHook((void*)(uintptr_t)h.a)!=MH_OK){p->error=22;finish();return;}h.enabled=true;}
 p->phase=5;window=hwnd;start_tick=GetTickCount();timer=SetTimer(window,0x52413374,100,tick);if(!timer){p->error=23;finish();return;}event(0);
}
extern "C" __declspec(dllexport) LRESULT CALLBACK TacticalWeaponToggleControl(int code,WPARAM wp,LPARAM lp){
 if(code>=0&&wp==PM_REMOVE&&lp&&((MSG*)lp)->message==T_MESSAGE&&((MSG*)lp)->wParam==T_MAGIC){
  MSG* msg=(MSG*)lp;uint32_t token=(uint32_t)msg->lParam;
  if(token&&(!p||((p->phase==3||p->phase==4)&&p->restore_mask==255&&!p->active&&!timer))){
   char name[100];snprintf(name,sizeof(name),"Local\\RA3TacticalWeaponToggle_%lu_%u",GetCurrentProcessId(),token);HANDLE next_mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);Tactical* next=next_mapping?(Tactical*)MapViewOfFile(next_mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Tactical)):NULL;
   if(next&&next->token==token&&next->pid==GetCurrentProcessId()&&next->magic==T_MAGIC){if(p)UnmapViewOfFile(p);if(mapping)CloseHandle(mapping);p=next;mapping=next_mapping;tag=0;install(msg->hwnd);}else{if(next)UnmapViewOfFile(next);if(next_mapping)CloseHandle(next_mapping);}
  }
 }
 return CallNextHookEx(NULL,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE h,DWORD why,LPVOID){if(why==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(h);return TRUE;}
