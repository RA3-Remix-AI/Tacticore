#include "shared.h"
#include "MinHook.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
static Tactical* p;static HANDLE mapping;static HMODULE pin;static HWND window;static UINT_PTR timer;static uint32_t observed_shots,observed_source;static uint32_t tag,start_tick,last_seq,used_count;static uint32_t used_commands[128][4],used_tasks[128][4],used_tokens[128];
static bool read(uint32_t a,void* b,SIZE_T n){SIZE_T got=0;return ReadProcessMemory(GetCurrentProcess(),(void*)(uintptr_t)a,b,n,&got)&&got==n;}
static uint32_t word(uint32_t a){uint32_t v=0;read(a,&v,4);return v;}
static uint32_t frame(){return word(p->logic+0x50);}static bool paused(){return word(p->logic+0x15c)!=0;}
static bool identity(){return word(0xcd8ce4)==p->logic&&word(p->logic)==0xbeb630&&word(p->owner)==0xc5bce0&&word(p->owner+0x20)==3&&word(p->owner+0x10)==p->player_template&&word(p->owner+0x90)==p->ai&&word(p->ai)==0xc60f60&&word(p->ai+8)==p->owner&&word(p->ai+0x8b0)==p->personality&&word(p->personality+0x18)==p->personality_id;}
static bool unit(){float hp=0;return word(p->unit)==0xc4db60&&word(p->unit+0xdc)==p->object_id&&word(p->unit+0x418)==p->owner&&word(word(p->unit+4)+8)==p->type_hash&&word(p->unit+0x374)==p->update&&word(p->update+8)==p->unit&&read(word(p->unit+0x33c)+4,&hp,4)&&isfinite(hp)&&hp>0;}
static void event(uint32_t kind,uint32_t arg=0,uint32_t caller=0,float before=0,float after=0,float reported=0){LONG i=InterlockedIncrement(&p->count)-1;if(i>=T_CAP){p->overflow=1;return;}Event e={};e.seq=i+1;e.kind=kind;e.tag=tag;e.frame=frame();e.tick=GetTickCount();e.thread=GetCurrentThreadId();e.caller=caller;e.team=word(p->unit+0x414);e.owner=word(p->unit+0x418);e.source=word(p->update+0x50);e.arg=arg;if(kind==20||kind==21||kind==22||kind==24||kind==25){e.target_id=p->target_id;e.damage_source=arg;e.damage_before=before;e.damage_after=after;e.damage_reported=reported;}if(word(p->unit)==0xc4db60&&word(p->unit+0xdc)==p->object_id&&word(p->unit+0x418)==p->owner)read(p->unit+0x38,&e.x,12);e.lease_stage=p->lease_stage;e.arg_shots=observed_shots;e.arg_source=observed_source;e.sm=word(p->update+0x3c);e.sm_flags=word(e.sm+0x78);e.state=word(e.sm+4);e.state_id=word(e.state+4);e.path=word(p->update+0x150);e.holder=word(p->unit+0x238);read(e.sm+0x2c,e.requested,12);read(e.sm+0x48,e.effective,12);if(kind==20||kind==21||kind==24||kind==25){void* frames[12]={};e.stack_count=CaptureStackBackTrace(0,12,frames,NULL);for(unsigned j=0;j<e.stack_count;j++)e.stack[j]=(uintptr_t)frames[j];e.stack_words_address=(uintptr_t)__builtin_frame_address(0)+4;e.stack_word_count=read(e.stack_words_address,e.stack_words,sizeof(e.stack_words))?128:0;}e.seq=0;p->events[i]=e;MemoryBarrier();InterlockedExchange((LONG*)&p->events[i].seq,i+1);}
typedef void (__attribute__((thiscall))*Move)(void*,float*,uint32_t);typedef void (__attribute__((thiscall))*Attack)(void*,void*,uint32_t,uint32_t);typedef void (__attribute__((thiscall))*Transfer)(void*,void*,uint32_t);typedef void (__attribute__((thiscall))*Member)(void*,void*);
typedef void (__attribute__((thiscall))*Damage)(void*,void*);static Damage old_damage;typedef uint32_t (__attribute__((thiscall))*WeaponGet)(void*,uint32_t);static WeaponGet old_weapon_get;
static Move old_move;static Attack old_attack;static Transfer old_transfer;static Member old_add,old_remove;
static void __attribute__((fastcall)) move_hook(void* self,void*,float* xyz,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update;if(ours){if(!tag)p->native_move++;event(10,source,(uintptr_t)__builtin_return_address(0));}old_move(self,xyz,source);if(ours)event(11,source);InterlockedDecrement(&p->active);}
static bool weapon_identity(){uint32_t e=p->weapon_entry,slot=p->weapon_slot,cont=word(p->unit+0x37c);if(!e||word(e)!=0xc2e324||word(e+4)!=p->weapon_template||word(e+8)!=slot||word(cont+8)!=p->unit)return false;uint32_t a=word(cont+0x24),z=word(cont+0x28),found=0;if(!a||z<a||z-a>256||(z-a)%4)return false;for(;a<z;a+=4)found|=word(a)==slot;if(!found)return false;uint32_t entries=word(slot+0x94);found=0;for(unsigned i=0;entries&&i<6;i++)found|=word(entries+4*i)==e;return found;}
static uint32_t __attribute__((fastcall)) weapon_get_hook(void* self,void*,uint32_t selector){InterlockedIncrement(&p->active);uint32_t result=old_weapon_get(self,selector);if((tag==2||p->lease_stage==1)&&GetCurrentThreadId()==p->thread&&(uintptr_t)self==word(p->unit+0x37c)&&(uintptr_t)__builtin_return_address(0)==0x76e6c6&&word(result)==0xc2e324){p->weapon_entry=result;p->weapon_template=word(result+4);p->weapon_slot=word(result+8);p->weapon_ammo=p->last_ammo=word(result+0x1c);p->limit_before=word(result+0x24);}InterlockedDecrement(&p->active);return result;}
static void sample_weapon(){if(!weapon_identity())return;uint32_t ammo=word(p->weapon_entry+0x1c),limit=word(p->weapon_entry+0x24);if(ammo<p->last_ammo&&p->last_ammo<100000&&limit<=p->last_limit){event(22,p->object_id,0,(float)p->last_ammo,(float)ammo,0);p->shot_samples++;}p->last_ammo=ammo;p->last_limit=limit;}
static void __attribute__((fastcall)) attack_hook(void* self,void*,void* target,uint32_t shots,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update;observed_shots=shots;observed_source=source;if(ours){bool expected=p->lease_stage==1&&p->attack_facade_calls==1&&!p->attack_private_calls&&(uintptr_t)target==p->target_unit&&shots==0x7fffffff&&source==1;if(expected){p->attack_private_calls++;p->attack_issued_frame=frame();}else if(!tag)p->native_attack++;event(12,word((uintptr_t)target+0xdc),(uintptr_t)__builtin_return_address(0));}old_attack(self,target,shots,source);if(ours){if(p->lease_stage==1&&weapon_identity()){p->limit_after=p->last_limit=word(p->weapon_entry+0x24);p->last_ammo=word(p->weapon_entry+0x1c);}event(13,word((uintptr_t)target+0xdc));}InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) transfer_hook(void* self,void*,void* target,uint32_t to_ai){InterlockedIncrement(&p->active);bool ours=(uintptr_t)target==p->unit;if(ours)event(14,to_ai,(uintptr_t)__builtin_return_address(0));old_transfer(self,target,to_ai);if(ours)event(15,to_ai);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) add_hook(void* self,void*,void* target){InterlockedIncrement(&p->active);bool ours=(uintptr_t)target==p->unit;if(ours){if(!tag)p->native_add++;event(16,(uintptr_t)self,(uintptr_t)__builtin_return_address(0));}old_add(self,target);if(ours)event(17,(uintptr_t)self);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) remove_hook(void* self,void*,void* target){InterlockedIncrement(&p->active);bool ours=(uintptr_t)target==p->unit;if(ours){if(!tag)p->native_remove++;event(18,(uintptr_t)self,(uintptr_t)__builtin_return_address(0));}old_remove(self,target);if(ours)event(19,(uintptr_t)self);InterlockedDecrement(&p->active);}
static bool visible_target(){
 uint32_t t=p->target_unit;if(word(p->owner+0x20)!=3)return false;if(word(t)!=0xc4db60||word(t+0xdc)!=p->target_id||word(t+4)!=p->target_template||word(p->target_template+8)!=p->target_hash||word(t+0x418)!=p->target_owner||word(p->target_owner)!=0xc5bce0||word(t+0xc8)&((1u<<11)|(1u<<12)))return false;
 uint32_t index=word(p->target_owner+0x20);if(index>=20||index==3)return false;uint32_t rel=word(p->owner+0xfc),buckets=word(rel+8),count=word(rel+0xc);if(!rel||!word(rel+0x10)||!buckets||count<1||count>4096)return false;uint32_t n=word(buckets+(index%count)*4),found=0;for(unsigned i=0;n&&i<100;i++){if(word(n)==index){found=word(n+4)==0?1:2;break;}n=word(n+8);}if(found!=1)return false;
 uint32_t manager=word(0xce2fa0),impl=word(manager+0x28);if(word(manager)!=0xc6aefc)return false;uint32_t cells=word(impl+0x44),width=word(impl+0x3c),height=word(impl+0x40),fallback=word(0xd074a4);float origin[2]={},scale=0,xyz[3]={};if(!read(impl+4,origin,8)||!read(impl+0x38,&scale,4)||!read(t+0x38,xyz,12)||!isfinite(origin[0])||!isfinite(origin[1]))return false;if(!cells||width<1||height<1||width>4096||height>4096||width*height>4000000||!isfinite(scale)||scale<=0||scale>10||!isfinite(xyz[0])||!isfinite(xyz[1]))return false;
 int gx=(int)((xyz[0]-origin[0])*scale),gy=(int)((xyz[1]-origin[1])*scale);if(gx<0||gy<0||(unsigned)gx>=width||(unsigned)gy>=height)return false;
 uint32_t center=cells+((uint32_t)gy*width+gx)*0x34;BYTE flag=1;uint16_t c=0;read(center+0x32,&flag,1);read(center+10,&c,2);if(flag||!c||(c==0xffff&&fallback!=1))return false;
 uint32_t record=word(t+0x9c),first=word(record+0x1c),num=word(record+0x20);BYTE pending=1,masked=1;read(record+0xf8,&pending,1);read(record+0xf9,&masked,1);if(!record||word(record)!=impl||pending||masked||!first||num<1||num>4096)return false;uint32_t total=0;
 for(uint32_t i=0;i<num;i++){uint32_t cell=word(first+16*i);if(!cell)continue;if(cell<cells||(cell-cells)%0x34||(cell-cells)/0x34>=width*height)return false;total++;flag=1;c=0;read(cell+0x32,&flag,1);read(cell+10,&c,2);if(flag||!c||(c==0xffff&&fallback!=1))return false;}
 float hp=0;pending=1;masked=1;read(record+0xf8,&pending,1);read(record+0xf9,&masked,1);if(!total||pending||masked||word(t+0x9c)!=record||word(record+0x1c)!=first||word(record+0x20)!=num||word(t)!=0xc4db60||word(t+0xdc)!=p->target_id||word(t+4)!=p->target_template||word(p->target_template+8)!=p->target_hash||word(t+0x418)!=p->target_owner)return false;return read(word(t+0x33c)+4,&hp,4)&&isfinite(hp)&&hp>0;
}
static void __attribute__((fastcall)) damage_hook(void* self,void*,void* info){
 InterlockedIncrement(&p->active);InterlockedIncrement((LONG*)&p->damage_hook_calls);uint32_t body=(uintptr_t)self,t=word(body-8),source=word((uintptr_t)info+8);bool observed=p->phase==1&&GetCurrentThreadId()==p->thread&&t==p->target_unit&&word(t+0x33c)==body&&visible_target();if(observed)p->visible_damage_calls++;bool ours=observed&&source==p->object_id;float before=0;if(observed)read(body+4,&before,4);old_damage(self,info);
 if(observed&&visible_target()){float after=0,reported=0;read(body+4,&after,4);read((uintptr_t)info+0x90,&reported,4);if(!ours)event(21,source,(uintptr_t)__builtin_return_address(0),before,after,reported);if(ours&&isfinite(before)&&isfinite(after)&&isfinite(reported)&&before>after&&reported>0&&fabsf((before-after)-reported)<0.05f){event(20,source,(uintptr_t)__builtin_return_address(0),before,after,reported);p->damage_count++;p->damage_total+=reported;}}
 InterlockedDecrement(&p->active);
}
typedef void (__attribute__((thiscall))*Commit)(void*,float,void*);static Commit old_commit;
static void __attribute__((fastcall)) commit_hook(void* self,void*,float delta,void* info){
 InterlockedIncrement(&p->active);InterlockedIncrement((LONG*)&p->commit_hook_calls);uint32_t body=(uintptr_t)self;bool observed=p->phase==1&&GetCurrentThreadId()==p->thread&&body==word(p->target_unit+0x33c)&&word(body-8)==p->target_unit&&visible_target();uint32_t source=0;float before=0;if(observed){p->commit_visible_calls++;source=word((uintptr_t)info+8);read(body+4,&before,4);}old_commit(self,delta,info);
 if(observed&&visible_target()){float after=0;read(body+4,&after,4);if(isfinite(before)&&isfinite(after)&&isfinite(delta)){event(source==p->object_id?24:25,source,(uintptr_t)__builtin_return_address(0),before,after,-delta);if(source==p->object_id&&before>after)p->commit_own_calls++;}}
 InterlockedDecrement(&p->active);
}
typedef void (__attribute__((thiscall))*Stop)(void*,uint32_t);static Stop old_stop_facade,old_stop_private;static Attack old_attack_facade;
static void __attribute__((fastcall)) stop_facade_hook(void* self,void*,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update+0x24;if(ours)event(30,source,(uintptr_t)__builtin_return_address(0));old_stop_facade(self,source);if(ours)event(31,source);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) stop_private_hook(void* self,void*,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update;uint32_t caller=(uintptr_t)__builtin_return_address(0);if(ours)event(32,source,caller);old_stop_private(self,source);if(ours){if(p->phase==1&&p->stop_calls&&source==1&&caller==0x787791&&(p->lease_stage==0||p->lease_stage==2)){p->private_stop_calls++;p->private_stop_frame=frame();}event(33,source,caller);}InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) attack_facade_hook(void* self,void*,void* target,uint32_t shots,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update+0x24;observed_shots=shots;observed_source=source;if(ours)event(34,word((uintptr_t)target+0xdc),(uintptr_t)__builtin_return_address(0));old_attack_facade(self,target,shots,source);if(ours)event(35,word((uintptr_t)target+0xdc));InterlockedDecrement(&p->active);}
static void issue_stop(uint32_t stage){p->lease_stage=stage;p->stop_issue_frame=frame();p->stable_samples=p->stop_gate_samples=p->last_sample_frame=0;read(p->unit+0x38,p->stopped_xyz,12);tag=4;p->stop_calls++;((Stop)0x54b0a0)((void*)(uintptr_t)(p->update+0x24),1);event(36);tag=0;}
static bool stop_settled(uint32_t now){if(now==p->last_sample_frame)return false;p->last_sample_frame=now;uint32_t sm=word(p->update+0x3c);float xyz[3];read(p->unit+0x38,xyz,12);bool gate=p->private_stop_calls==p->stop_calls&&now>p->private_stop_frame&&word(p->update+0x50)==1&&!(word(sm+0x78)&0xffff)&&word(p->update+0x150)==0;float dx=xyz[0]-p->stopped_xyz[0],dy=xyz[1]-p->stopped_xyz[1];if(gate){p->stop_gate_samples++;if(dx*dx+dy*dy<=1)p->stable_samples++;else p->stable_samples=0;}else{p->stop_gate_samples=p->stable_samples=0;}memcpy(p->stopped_xyz,xyz,12);return p->stop_gate_samples>=3&&p->stable_samples>=3;}
struct Hook {uint32_t a;void* fn;void** original;const char* signature;uint32_t n;BYTE before[24];bool made,enabled;};
static Hook hooks[]={
{0x6eff70,(void*)move_hook,(void**)&old_move,"\x56\x8b\xf1\x8b\x4e\x3c\x8b\x01\x8b\x50\x38\xff\xd2",13,{},false,false},
{0x76e690,(void*)attack_hook,(void**)&old_attack,"\x83\x7c\x24\x04\x00\x55\x56\x8b\xf1\x8b\x6e\x08",12,{},false,false},
{0x838820,(void*)transfer_hook,(void**)&old_transfer,"\x8b\x81\x8c\x00\x00\x00\x85\xc0\x74\x4f\x56\x8b\xb1\x90\x00\x00\x00",17,{},false,false},
{0x8d8880,(void*)add_hook,(void**)&old_add,"\x83\xec\x24\x56\x8b\x74\x24\x2c\x8b\x46\x04",11,{},false,false},
{0x8cd630,(void*)remove_hook,(void**)&old_remove,"\x83\xec\x34\x53\x57\x8b\x7c\x24\x40\x8b\x47\x04",12,{},false,false},
{0x7d2310,(void*)damage_hook,(void**)&old_damage,"\x81\xec\x20\x01\x00\x00\x53\x55\x56\x8b\xb4\x24\x30\x01\x00\x00",16,{},false,false},
{0x6f7c60,(void*)weapon_get_hook,(void**)&old_weapon_get,"\x53\x8b\x59\x28\x56\x8b\x71\x24\x3b\xf3\x57",11,{},false,false},
{0x765190,(void*)commit_hook,(void**)&old_commit,"\x8b\x44\x24\x08\x85\xc0\xf3\x0f\x10\x4c\x24\x04",12,{},false,false},
{0x54b0a0,(void*)stop_facade_hook,(void**)&old_stop_facade,"\x83\xec\x5c\x8b\x44\x24\x60\x56\x6a\x01\x50\x8b\xf1",13,{},false,false},
{0x721ad0,(void*)stop_private_hook,(void**)&old_stop_private,"\x83\xec\x08\x55\x8b\xe9\x8b\x45\x08\x8b\x48\x04",12,{},false,false},
{0x572280,(void*)attack_facade_hook,(void**)&old_attack_facade,"\x83\xec\x5c\x8b\x44\x24\x68\x56\x6a\x01\x50\x8b\xf1",13,{},false,false}};
static void finish(){if(timer){KillTimer(window,timer);timer=0;}event(4);for(unsigned i=0;i<11;i++){Hook& h=hooks[i];if(h.enabled){MH_DisableHook((void*)(uintptr_t)h.a);h.enabled=false;}BYTE b[24];if(h.made&&read(h.a,b,h.n)&&!memcmp(b,h.before,h.n))p->restore_mask|=1u<<i;}p->phase=p->error?4:3;}
static void CALLBACK tick(HWND,UINT,UINT_PTR,DWORD){
 if(GetCurrentThreadId()!=p->thread){p->error=30;return;}if(!identity()&&p->phase==2&&p->return_verified){p->post_scene_changed=1;finish();return;}if(!identity()){p->error=31;p->lifecycle_fail++;finish();return;}
 if(!unit()&&p->phase==2&&p->return_verified){p->post_actor_disposed=1;finish();return;}
 if(!unit()){p->error=32;p->lifecycle_fail++;finish();return;}
 if(paused()){p->paused_samples++;if(p->phase==1&&(p->stop_requested||GetTickCount()-start_tick>60000))p->return_pending=1;return;}
 uint32_t now=frame();
 if(p->phase==5){
  if(p->stop_requested||GetTickCount()-start_tick>60000){p->error=33;finish();return;}
  if(word(p->unit+0x238)||word(p->update)!=0xc48670||word(p->update+0x24)!=0xc48528||word(0xc48528)!=0x787500||word(0xc48670+0x8c)!=0x721ad0||!visible_target()||frame()<p->target_observed_frame||frame()-p->target_observed_frame>60||word(p->owner+0xac)!=p->default_team||word(word(p->owner+0x8c)+0x10)!=p->script_team||word(word(p->default_team+4)+8)!=p->owner||word(word(p->script_team+4)+8)!=p->owner){p->error=34;finish();return;}
  p->phase=6;p->original_team=word(p->unit+0x414);p->issued_frame=now;tag=1;p->detach_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->unit,0);event(1);tag=0;
  if(!unit()||word(p->unit+0x414)!=p->script_team){p->error=35;p->phase=1;p->return_pending=1;return;}
  p->phase=1;if(paused()||!visible_target()){p->return_pending=1;return;}if(word(p->unit+0x238)||word(p->update)!=0xc48670||word(p->update+0x24)!=0xc48528||word(0xc48528)!=0x787500||word(0xc48670+0x8c)!=0x721ad0){p->error=43;p->return_pending=1;return;}issue_stop(0);return;
 }
 event(3);if(p->phase==1){
  bool end=p->stop_requested||p->return_pending||now-p->issued_frame>=p->lease_frames||GetTickCount()-start_tick>60000||p->native_move||p->native_attack||p->native_add||p->native_remove;
  if(p->lease_stage==0&&!end){if(!visible_target()){end=true;}else if(stop_settled(now)){event(37);if(word(p->unit+0x238)){p->error=43;end=true;}else{p->lease_stage=1;tag=2;p->attack_calls++;p->attack_facade_calls++;((Attack)0x572280)((void*)(uintptr_t)(p->update+0x24),(void*)(uintptr_t)p->target_unit,0x7fffffff,1);event(2);tag=0;}}else if(now-p->issued_frame>=30){p->error=44;end=true;}}
  if(p->lease_stage==1){sample_weapon();if(!visible_target()||p->damage_count||p->commit_own_calls)end=true;}
  if(end&&p->lease_stage!=2){issue_stop(2);p->return_pending=1;}
  if(p->lease_stage==2&&(stop_settled(now)||now-p->stop_issue_frame>=30)){
   if(p->stable_samples<3){p->stop_failed=1;p->error=45;}else event(38);
   if(p->native_add){p->error=36;finish();return;}
   tag=3;p->return_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->unit,1);event(5);tag=0;p->returned_frame=now;p->return_pending=0;p->return_verified=unit()&&word(p->unit+0x414)==p->default_team;p->phase=2;if(!p->return_verified){p->error=37;finish();}
  }
 }else if(p->phase==2&&now-p->returned_frame>=p->post_frames)finish();
}
static void install(HWND hwnd){p->callback_thread=GetCurrentThreadId();FILETIME a,b,c,d;
 if(p->magic!=T_MAGIC||p->version!=7||GetCurrentProcessId()!=p->pid||p->thread!=p->callback_thread||!GetProcessTimes(GetCurrentProcess(),&a,&b,&c,&d)||a.dwLowDateTime!=p->start_low||a.dwHighDateTime!=p->start_high||!identity()||!unit()||(p->type_hash!=0x19ab11af&&p->type_hash!=0x2c358c61)||p->lease_frames>180||p->lease_frames<30||p->post_frames<30||p->post_frames>180){p->error=10;p->phase=4;return;}
 if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCSTR)(uintptr_t)&install,&pin)){p->error=11;p->phase=4;return;}
 for(unsigned i=0;i<11;i++)if(!read(hooks[i].a,hooks[i].before,hooks[i].n)||memcmp(hooks[i].before,hooks[i].signature,hooks[i].n)){p->error=12+i;p->phase=4;return;}
 if(used_count>=128||!p->token||p->seq<=last_seq){p->error=40;p->restore_mask=2047;p->phase=4;return;}for(unsigned i=0;i<used_count;i++)if(used_tokens[i]==p->token||!memcmp(used_commands[i],p->command,16)||!memcmp(used_tasks[i],p->task,16)){p->error=41;p->restore_mask=2047;p->phase=4;return;}uint32_t nonzero_command=0,nonzero_task=0;for(unsigned i=0;i<4;i++){nonzero_command|=p->command[i];nonzero_task|=p->task[i];}if(!nonzero_command||!nonzero_task){p->error=42;p->restore_mask=2047;p->phase=4;return;}memcpy(used_commands[used_count],p->command,16);memcpy(used_tasks[used_count],p->task,16);used_tokens[used_count++]=p->token;last_seq=p->seq;
 MH_STATUS s=MH_Initialize();if(s!=MH_OK&&s!=MH_ERROR_ALREADY_INITIALIZED){p->error=20;p->phase=4;return;}
 for(unsigned i=0;i<11;i++){Hook& h=hooks[i];if(!h.made&&MH_CreateHook((void*)(uintptr_t)h.a,h.fn,h.original)!=MH_OK){p->error=21;finish();return;}h.made=true;}
 for(unsigned i=0;i<11;i++){Hook& h=hooks[i];if(MH_EnableHook((void*)(uintptr_t)h.a)!=MH_OK){p->error=22;finish();return;}h.enabled=true;}
 p->phase=5;window=hwnd;start_tick=GetTickCount();timer=SetTimer(window,0x52413374,100,tick);if(!timer){p->error=23;finish();return;}event(0);
}
extern "C" __declspec(dllexport) LRESULT CALLBACK TacticalOrderedAttackControl(int code,WPARAM wp,LPARAM lp){
 if(code>=0&&wp==PM_REMOVE&&lp&&((MSG*)lp)->message==T_MESSAGE&&((MSG*)lp)->wParam==T_MAGIC){
  MSG* msg=(MSG*)lp;uint32_t token=(uint32_t)msg->lParam;
  if(token&&(!p||((p->phase==3||p->phase==4)&&p->restore_mask==2047&&!p->active&&!timer))){
   char name[100];snprintf(name,sizeof(name),"Local\\RA3TacticalOrderedAttack_%lu_%u",GetCurrentProcessId(),token);HANDLE next_mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);Tactical* next=next_mapping?(Tactical*)MapViewOfFile(next_mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Tactical)):NULL;
   if(next&&next->token==token&&next->pid==GetCurrentProcessId()&&next->magic==T_MAGIC){if(p)UnmapViewOfFile(p);if(mapping)CloseHandle(mapping);p=next;mapping=next_mapping;tag=0;install(msg->hwnd);}else{if(next)UnmapViewOfFile(next);if(next_mapping)CloseHandle(next_mapping);}
  }
 }
 return CallNextHookEx(NULL,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE h,DWORD why,LPVOID){if(why==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(h);return TRUE;}
