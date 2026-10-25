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
static bool role_leased(bool support){return p->issued_frame&&(support?(p->support.detach_calls&&!p->support.returned):(p->detach_calls&&!p->return_verified));}
static bool support_valid(){Support& u=p->support;float hp=0;return word(u.thing)==0xc4db60&&word(u.thing+0xdc)==u.id&&word(u.thing+0x418)==p->owner&&word(word(u.thing+4)+8)==0x2c358c61&&word(u.thing+0x374)==u.update&&word(u.update+8)==u.thing&&read(word(u.thing+0x33c)+4,&hp,4)&&isfinite(hp)&&hp>0;}
static bool unit(){float hp=0;return word(p->unit)==0xc4db60&&word(p->unit+0xdc)==p->object_id&&word(p->unit+0x418)==p->owner&&word(word(p->unit+4)+8)==p->type_hash&&word(p->unit+0x374)==p->update&&word(p->update+8)==p->unit&&read(word(p->unit+0x33c)+4,&hp,4)&&isfinite(hp)&&hp>0;}
static uint32_t current_weapon(uint32_t* entry,uint32_t* ammo){*entry=*ammo=0;uint32_t container=word(p->unit+0x37c);if(word(container+8)!=p->unit)return 0;uint32_t a=word(container+0x24),z=word(container+0x28);if(!a||z<a||z-a>256||(z-a)%4)return 0;for(;a<z;a+=4){uint32_t slot=word(a);if(word(slot)!=0xc3a6e0||word(0xc3a6e0+0x24)!=0x6dbe80||word(0xc3a6e0+0x28)!=0x6f88e0)return 0;uint32_t index=word(slot+0x14);if(index>5)return 0;if(index==5)continue;uint32_t e=word(word(slot+0x94)+4*index);if(!e)continue;if(word(e)!=0xc2e324||word(e+8)!=slot)return 0;uint32_t h=word(word(word(e+4)+4));if(word(h)!=0x94d4d96e)return 0;*entry=e;*ammo=word(e+0x1c);return word(h+4);}return 0;}
static bool button_identity(){uint32_t key=word(p->unit+0x464);if(!key){if(word(word(p->unit+0x78)+0x2c)!=0x6de330)return false;key=word(word(word(p->unit+4)+0x14)+0x94);}if(key!=0xb74cf71a||key!=p->command_set||word(p->button)!=0xbe9170||word(p->button+4)!=p->button_schema||word(p->button_schema+4)!=1)return false;uint32_t h=word(p->button_schema);if(word(h)!=0x7d464170||word(h+4)!=0x5977a798)return false;uint32_t store=word(0xcd8d00),node=word(store+0x4c),found=0;for(unsigned i=0;node&&i<138;i++){uint32_t k=word(node+0x10);if(k==key){found=node;break;}node=word(node+(k>=key?4:0));}if(!found)return false;uint32_t list=word(found+0x14)+8;if(word(list)!=0xbe9178||word(0xbe9178)!=0x524c70||word(0xbe9178+0xc)!=0x4d8fc0)return false;uint32_t inner=word(list+4),count=word(inner+4),items=word(inner+8),matches=0;if(!items||!count||count>64)return false;for(unsigned i=0;i<count;i++)matches+=word(items+i*4)==p->button;return matches==1;}
static bool visible_target();
static void event(uint32_t kind,uint32_t arg=0,uint32_t caller=0,float before=0,float after=0,float reported=0,uint32_t role=0,const float* input=NULL,uint32_t input_path=0,float input_limit=0){
 LONG i=InterlockedIncrement(&p->count)-1;if(i>=T_CAP){p->overflow=1;return;}
 uint32_t thing=role?p->support.thing:p->unit,update=role?p->support.update:p->update,id=role?p->support.id:p->object_id;
 Event e={};e.kind=kind;e.tag=tag;e.frame=frame();e.tick=GetTickCount();e.thread=GetCurrentThreadId();e.caller=caller;e.arg=arg;e.role=role;e.unit_id=id;e.mission_stage=p->mission_stage;e.route_index=p->route_index;e.nav_step=p->nav_step;e.mission_deadline_frame=p->mission_deadline_frame;e.mission_reason=p->retreat_reason;e.native_error=p->error;
 e.team=word(thing+0x414);e.owner=word(thing+0x418);e.source=word(update+0x50);e.lease_stage=p->lease_stage;e.arg_shots=observed_shots;e.arg_source=observed_source;
 if(kind==20||kind==21||kind==22||kind==24||kind==25){e.target_id=p->target_id;e.damage_source=arg;e.damage_before=before;e.damage_after=after;e.damage_reported=reported;}
 if(word(thing)==0xc4db60&&word(thing+0xdc)==id&&word(thing+0x418)==p->owner){read(thing+0x38,&e.x,12);read(word(thing+0x33c)+4,&e.own_hp,4);}
 e.sm=word(update+0x3c);e.sm_flags=word(e.sm+0x78);e.state=word(e.sm+4);e.state_id=word(e.state+4);e.path=word(update+0x150);e.holder=word(thing+0x238);read(e.sm+0x2c,e.requested,12);read(e.sm+0x48,e.effective,12);
 if(kind==20||kind==21||kind==24||kind==25){void* frames[12]={};e.stack_count=CaptureStackBackTrace(0,12,frames,NULL);for(unsigned j=0;j<e.stack_count;j++)e.stack[j]=(uintptr_t)frames[j];e.stack_words_address=(uintptr_t)__builtin_frame_address(0)+4;e.stack_word_count=read(e.stack_words_address,e.stack_words,sizeof(e.stack_words))?128:0;}
 if(!role)e.active_weapon_asset=current_weapon(&e.active_weapon_entry,&e.active_weapon_ammo);
 e.status84=word(thing+0x84);e.target_visible=visible_target();if(e.target_visible)read(p->target_unit+0x38,e.visible_target_xyz,12);memcpy(e.front_goal,p->front_goal,12);memcpy(e.support_goal,p->support_goal,12);if(input)read((uintptr_t)input,e.command_xyz,12);e.argument_path=input_path;e.argument_limit=input_limit;
 p->events[i]=e;MemoryBarrier();InterlockedExchange((LONG*)&p->events[i].seq,i+1);
}

typedef void (__attribute__((thiscall))*Move)(void*,float*,void*,float,uint32_t);typedef void (__attribute__((thiscall))*MoveFacade)(void*,float*,uint32_t);static MoveFacade old_move_facade;typedef void (__attribute__((thiscall))*Attack)(void*,void*,uint32_t,uint32_t);typedef void (__attribute__((thiscall))*Transfer)(void*,void*,uint32_t);typedef void (__attribute__((thiscall))*Member)(void*,void*);
typedef void (__attribute__((thiscall))*Damage)(void*,void*);static Damage old_damage;typedef uint32_t (__attribute__((thiscall))*WeaponGet)(void*,uint32_t);static WeaponGet old_weapon_get;
static Move old_move;static Attack old_attack;static Transfer old_transfer;static Member old_add,old_remove;
static void __attribute__((fastcall)) move_hook(void* self,void*,float* xyz,void* path,float limit,uint32_t source){
 InterlockedIncrement(&p->active);bool front=(uintptr_t)self==p->update,support=(uintptr_t)self==p->support.update;
 if(front||support){if(!tag){if(front&&role_leased(false))p->native_move++;else if(support&&role_leased(true))p->support.native_move++;}event(10,source,(uintptr_t)__builtin_return_address(0),0,0,0,support,xyz,(uintptr_t)path,limit);}
 old_move(self,xyz,path,limit,source);if(front||support)event(11,source,0,0,0,0,support,xyz,(uintptr_t)path,limit);InterlockedDecrement(&p->active);
}
static void __attribute__((fastcall)) move_facade_hook(void* self,void*,float* xyz,uint32_t source){
 InterlockedIncrement(&p->active);bool front=(uintptr_t)self==p->update+0x24,support=(uintptr_t)self==p->support.update+0x24;
 if(front||support)event(50,source,(uintptr_t)__builtin_return_address(0),0,0,0,support,xyz);
 old_move_facade(self,xyz,source);if(front||support)event(51,source,0,0,0,0,support,xyz);InterlockedDecrement(&p->active);
}
static bool weapon_identity(){uint32_t e=p->weapon_entry,slot=p->weapon_slot,cont=word(p->unit+0x37c);if(!e||word(e)!=0xc2e324||word(e+4)!=p->weapon_template||word(e+8)!=slot||word(cont+8)!=p->unit)return false;uint32_t a=word(cont+0x24),z=word(cont+0x28),found=0;if(!a||z<a||z-a>256||(z-a)%4)return false;for(;a<z;a+=4)found|=word(a)==slot;if(!found)return false;uint32_t entries=word(slot+0x94);found=0;for(unsigned i=0;entries&&i<6;i++)found|=word(entries+4*i)==e;return found;}
static uint32_t __attribute__((fastcall)) weapon_get_hook(void* self,void*,uint32_t selector){InterlockedIncrement(&p->active);uint32_t result=old_weapon_get(self,selector);if((tag==2||p->lease_stage==1)&&GetCurrentThreadId()==p->thread&&(uintptr_t)self==word(p->unit+0x37c)&&(uintptr_t)__builtin_return_address(0)==0x76e6c6&&p->mission_stage==2&&word(result)==0xc2e324){p->weapon_entry=result;p->weapon_template=word(result+4);p->weapon_slot=word(result+8);p->weapon_ammo=p->last_ammo=word(result+0x1c);p->limit_before=word(result+0x24);}InterlockedDecrement(&p->active);return result;}
static void sample_weapon(){if(!weapon_identity())return;uint32_t ammo=word(p->weapon_entry+0x1c),limit=word(p->weapon_entry+0x24);if(ammo<p->last_ammo&&p->last_ammo<100000&&limit<=p->last_limit){event(22,p->object_id,0,(float)p->last_ammo,(float)ammo,0);p->shot_samples++;}p->last_ammo=ammo;p->last_limit=limit;}
static void __attribute__((fastcall)) attack_hook(void* self,void*,void* target,uint32_t shots,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update;observed_shots=shots;observed_source=source;if(ours){bool expected=p->lease_stage==1&&p->attack_facade_calls==1&&!p->attack_private_calls&&(uintptr_t)target==p->target_unit&&shots==0x7fffffff&&source==1;if(expected){p->attack_private_calls++;p->attack_issued_frame=frame();}else if(!tag&&role_leased(false))p->native_attack++;event(12,word((uintptr_t)target+0xdc),(uintptr_t)__builtin_return_address(0));}if((uintptr_t)self==p->support.update){if(!tag&&role_leased(true))p->support.native_attack++;event(12,word((uintptr_t)target+0xdc),(uintptr_t)__builtin_return_address(0),0,0,0,1);}old_attack(self,target,shots,source);if((uintptr_t)self==p->support.update)event(13,word((uintptr_t)target+0xdc),0,0,0,0,1);if(ours){if(p->lease_stage==1&&weapon_identity()){p->limit_after=p->last_limit=word(p->weapon_entry+0x24);p->last_ammo=word(p->weapon_entry+0x1c);}event(13,word((uintptr_t)target+0xdc));}InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) transfer_hook(void* self,void*,void* target,uint32_t to_ai){InterlockedIncrement(&p->active);bool ours=(uintptr_t)target==p->unit;if(ours)event(14,to_ai,(uintptr_t)__builtin_return_address(0));if((uintptr_t)target==p->support.thing){event(14,to_ai,(uintptr_t)__builtin_return_address(0),0,0,0,1);}old_transfer(self,target,to_ai);if(ours)event(15,to_ai);if((uintptr_t)target==p->support.thing)event(15,to_ai,0,0,0,0,1);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) add_hook(void* self,void*,void* target){InterlockedIncrement(&p->active);bool ours=(uintptr_t)target==p->unit;if(ours){if(!tag&&role_leased(false))p->native_add++;event(16,(uintptr_t)self,(uintptr_t)__builtin_return_address(0));}if((uintptr_t)target==p->support.thing){if(!tag&&role_leased(true))p->support.native_add++;event(16,(uintptr_t)self,(uintptr_t)__builtin_return_address(0),0,0,0,1);}old_add(self,target);if(ours)event(17,(uintptr_t)self);if((uintptr_t)target==p->support.thing)event(17,(uintptr_t)self,0,0,0,0,1);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) remove_hook(void* self,void*,void* target){InterlockedIncrement(&p->active);bool ours=(uintptr_t)target==p->unit;if(ours){if(!tag&&role_leased(false))p->native_remove++;event(18,(uintptr_t)self,(uintptr_t)__builtin_return_address(0));}if((uintptr_t)target==p->support.thing){if(!tag&&role_leased(true))p->support.native_remove++;event(18,(uintptr_t)self,(uintptr_t)__builtin_return_address(0),0,0,0,1);}old_remove(self,target);if(ours)event(19,(uintptr_t)self);if((uintptr_t)target==p->support.thing)event(19,(uintptr_t)self,0,0,0,0,1);InterlockedDecrement(&p->active);}
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
 InterlockedIncrement(&p->active);InterlockedIncrement((LONG*)&p->damage_hook_calls);uint32_t body=(uintptr_t)self,t=word(body-8),source=word((uintptr_t)info+8);bool observed=p->phase==1&&p->mission_stage==2&&p->lease_stage==1&&GetCurrentThreadId()==p->thread&&t==p->target_unit&&word(t+0x33c)==body&&visible_target();if(observed)p->visible_damage_calls++;bool ours=observed&&source==p->object_id;float before=0;if(observed)read(body+4,&before,4);old_damage(self,info);
 if(observed&&visible_target()){float after=0,reported=0;read(body+4,&after,4);read((uintptr_t)info+0x90,&reported,4);if(!ours)event(21,source,(uintptr_t)__builtin_return_address(0),before,after,reported);if(ours&&isfinite(before)&&isfinite(after)&&isfinite(reported)&&before>after&&reported>0&&fabsf((before-after)-reported)<0.05f){event(20,source,(uintptr_t)__builtin_return_address(0),before,after,reported);p->damage_count++;p->damage_total+=reported;}}
 InterlockedDecrement(&p->active);
}
typedef void (__attribute__((thiscall))*Commit)(void*,float,void*);static Commit old_commit;
static void __attribute__((fastcall)) commit_hook(void* self,void*,float delta,void* info){
 InterlockedIncrement(&p->active);InterlockedIncrement((LONG*)&p->commit_hook_calls);uint32_t body=(uintptr_t)self;bool observed=p->phase==1&&p->mission_stage==2&&p->lease_stage==1&&GetCurrentThreadId()==p->thread&&body==word(p->target_unit+0x33c)&&word(body-8)==p->target_unit&&visible_target();uint32_t source=0;float before=0;if(observed){p->commit_visible_calls++;source=word((uintptr_t)info+8);read(body+4,&before,4);}old_commit(self,delta,info);
 if(observed&&visible_target()){float after=0;read(body+4,&after,4);if(isfinite(before)&&isfinite(after)&&isfinite(delta)){event(source==p->object_id?24:25,source,(uintptr_t)__builtin_return_address(0),before,after,-delta);if(source==p->object_id&&before>after)p->commit_own_calls++;}}
 InterlockedDecrement(&p->active);
}
typedef void (__attribute__((thiscall))*Stop)(void*,uint32_t);static Stop old_stop_facade,old_stop_private;static Attack old_attack_facade;
static void __attribute__((fastcall)) stop_facade_hook(void* self,void*,uint32_t source){
 InterlockedIncrement(&p->active);bool front=(uintptr_t)self==p->update+0x24,support=(uintptr_t)self==p->support.update+0x24;
 if(front||support){if(!tag){if(front&&role_leased(false))p->native_stop++;else if(support&&role_leased(true))p->support.native_stop++;}event(30,source,(uintptr_t)__builtin_return_address(0),0,0,0,support);}
 old_stop_facade(self,source);if(front||support)event(31,source,0,0,0,0,support);InterlockedDecrement(&p->active);
}
static void __attribute__((fastcall)) stop_private_hook(void* self,void*,uint32_t source){
 InterlockedIncrement(&p->active);bool front=(uintptr_t)self==p->update,support=(uintptr_t)self==p->support.update;uint32_t caller=(uintptr_t)__builtin_return_address(0);
 if(front||support){event(32,source,caller,0,0,0,support);}old_stop_private(self,source);
 if(front){p->total_private_stops++;if((p->phase==1||p->phase==7)&&source==1&&caller==0x787791){if(p->lease_stage==3&&p->phase==1)p->prepare_reconstituted_stops++;else if(p->stop_calls){p->private_stop_calls++;p->private_stop_frame=frame();}}event(33,source,caller);}
 if(support){if((p->phase==1||p->phase==7)&&source==1&&caller==0x787791&&p->support.stop_calls){p->support.private_stop_calls++;p->support.private_stop_frame=frame();}event(33,source,caller,0,0,0,1);}
 InterlockedDecrement(&p->active);
}
static void __attribute__((fastcall)) attack_facade_hook(void* self,void*,void* target,uint32_t shots,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update+0x24;observed_shots=shots;observed_source=source;if(ours)event(34,word((uintptr_t)target+0xdc),(uintptr_t)__builtin_return_address(0));old_attack_facade(self,target,shots,source);if(ours)event(35,word((uintptr_t)target+0xdc));InterlockedDecrement(&p->active);}
static void issue_stop(uint32_t stage){p->lease_stage=stage;p->stop_issue_frame=frame();p->stable_samples=p->stop_gate_samples=p->last_sample_frame=0;read(p->unit+0x38,p->stopped_xyz,12);tag=4;p->stop_calls++;((Stop)0x54b0a0)((void*)(uintptr_t)(p->update+0x24),1);event(36);tag=0;}
static bool stop_settled(uint32_t now){if(now==p->last_sample_frame)return false;p->last_sample_frame=now;uint32_t sm=word(p->update+0x3c);float xyz[3];read(p->unit+0x38,xyz,12);bool gate=p->private_stop_calls==p->stop_calls&&now>p->private_stop_frame&&word(p->update+0x50)==1&&!(word(sm+0x78)&0xffff)&&word(p->update+0x150)==0;float dx=xyz[0]-p->stopped_xyz[0],dy=xyz[1]-p->stopped_xyz[1];if(gate){p->stop_gate_samples++;if(dx*dx+dy*dy<=1)p->stable_samples++;else p->stable_samples=0;}else{p->stop_gate_samples=p->stable_samples=0;}memcpy(p->stopped_xyz,xyz,12);return p->stop_gate_samples>=3&&p->stable_samples>=3;}
typedef uint32_t (__attribute__((thiscall))*Button)(void*,void*,uint32_t,uint32_t);static Button old_button;
static uint32_t __attribute__((fastcall)) button_hook(void* self,void*,void* button,uint32_t source,uint32_t third){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->unit;if(ours){if(tag==5&&(uintptr_t)button==p->button&&source==1&&third==0)p->toggle_hook_calls++;event(40,(uintptr_t)button,(uintptr_t)__builtin_return_address(0));}uint32_t result=old_button(self,button,source,third);if(ours)event(41,result);InterlockedDecrement(&p->active);return result;}
struct Hook {uint32_t a;void* fn;void** original;const char* signature;uint32_t n;BYTE before[24];bool made,enabled;};
static Hook hooks[]={
{0x76d9d0,(void*)move_hook,(void**)&old_move,"\x56\x8b\xf1\x57\x8b\x7e\x08\x8b\xcf",9,{},false,false},
{0x76e690,(void*)attack_hook,(void**)&old_attack,"\x83\x7c\x24\x04\x00\x55\x56\x8b\xf1\x8b\x6e\x08",12,{},false,false},
{0x838820,(void*)transfer_hook,(void**)&old_transfer,"\x8b\x81\x8c\x00\x00\x00\x85\xc0\x74\x4f\x56\x8b\xb1\x90\x00\x00\x00",17,{},false,false},
{0x8d8880,(void*)add_hook,(void**)&old_add,"\x83\xec\x24\x56\x8b\x74\x24\x2c\x8b\x46\x04",11,{},false,false},
{0x8cd630,(void*)remove_hook,(void**)&old_remove,"\x83\xec\x34\x53\x57\x8b\x7c\x24\x40\x8b\x47\x04",12,{},false,false},
{0x7d2310,(void*)damage_hook,(void**)&old_damage,"\x81\xec\x20\x01\x00\x00\x53\x55\x56\x8b\xb4\x24\x30\x01\x00\x00",16,{},false,false},
{0x6f7c60,(void*)weapon_get_hook,(void**)&old_weapon_get,"\x53\x8b\x59\x28\x56\x8b\x71\x24\x3b\xf3\x57",11,{},false,false},
{0x765190,(void*)commit_hook,(void**)&old_commit,"\x8b\x44\x24\x08\x85\xc0\xf3\x0f\x10\x4c\x24\x04",12,{},false,false},
{0x54b0a0,(void*)stop_facade_hook,(void**)&old_stop_facade,"\x83\xec\x5c\x8b\x44\x24\x60\x56\x6a\x01\x50\x8b\xf1",13,{},false,false},
{0x721ad0,(void*)stop_private_hook,(void**)&old_stop_private,"\x83\xec\x08\x55\x8b\xe9\x8b\x45\x08\x8b\x48\x04",12,{},false,false},
{0x572280,(void*)attack_facade_hook,(void**)&old_attack_facade,"\x83\xec\x5c\x8b\x44\x24\x68\x56\x6a\x01\x50\x8b\xf1",13,{},false,false},
{0x571d90,(void*)move_facade_hook,(void**)&old_move_facade,"\x83\xec\x5c\x8b\x44\x24\x64\x56\x6a\x01\x50\x8b\xf1",13,{},false,false},
{0x790990,(void*)button_hook,(void**)&old_button,"\x8b\x44\x24\x0c\x8b\x54\x24\x08\x6a\x00\x6a\x00\x6a\x00",14,{},false,false}};
static void finish(){if(timer){KillTimer(window,timer);timer=0;}event(4);for(unsigned i=0;i<13;i++){Hook& h=hooks[i];if(h.enabled){MH_DisableHook((void*)(uintptr_t)h.a);h.enabled=false;}BYTE b[24];if(h.made&&read(h.a,b,h.n)&&!memcmp(b,h.before,h.n))p->restore_mask|=1u<<i;}p->phase=p->error?4:3;}
static float distance(const float a[3],const float b[3]){float x=a[0]-b[0],y=a[1]-b[1];return sqrtf(x*x+y*y);}
static bool finite_point(const float x[3]){return isfinite(x[0])&&isfinite(x[1])&&isfinite(x[2]);}
static bool support_settled(uint32_t now){Support& s=p->support;if(now==s.last_sample_frame)return false;s.last_sample_frame=now;uint32_t sm=word(s.update+0x3c);float xyz[3];read(s.thing+0x38,xyz,12);bool gate=s.private_stop_calls==s.stop_calls&&now>s.private_stop_frame&&word(s.update+0x50)==1&&!(word(sm+0x78)&0xffff)&&word(s.update+0x150)==0;float d=distance(xyz,s.stopped_xyz);if(gate){s.gate_samples++;s.stable_samples=d<=1?s.stable_samples+1:0;}else s.gate_samples=s.stable_samples=0;memcpy(s.stopped_xyz,xyz,12);return s.gate_samples>=3&&s.stable_samples>=3;}
static void stop_support(){Support& s=p->support;s.stable_samples=s.gate_samples=s.last_sample_frame=0;read(s.thing+0x38,s.stopped_xyz,12);tag=4;s.stop_calls++;((Stop)0x54b0a0)((void*)(uintptr_t)(s.update+0x24),1);event(36,0,0,0,0,0,1);tag=0;}
static void stop_both(uint32_t stage){issue_stop(stage);stop_support();}
static void move_role(bool support,const float* goal){tag=6;if(support)p->support.move_calls++;else p->move_calls++;((MoveFacade)0x571d90)((void*)(uintptr_t)((support?p->support.update:p->update)+0x24),(float*)goal,1);event(52,0,0,0,0,0,support);tag=0;}
static void normal_return(){
 if(unit()&&!p->return_calls){tag=3;p->return_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->unit,1);p->return_verified=unit()&&word(p->unit+0x414)==p->default_team;event(5);tag=0;}
 if(support_valid()&&!p->support.return_calls){tag=3;p->support.return_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->support.thing,1);p->support.returned=support_valid()&&word(p->support.thing+0x414)==p->default_team;event(5,0,0,0,0,0,1);tag=0;}
 if(!p->return_verified||!p->support.returned)p->error=p->error?p->error:37;
 p->returned_frame=frame();p->return_pending=0;p->phase=2;
}
static void begin_retreat(uint32_t reason){
 if(p->mission_stage==3||p->mission_stage==4)return;
 p->retreat_reason=reason;p->retreat_started=frame();p->mission_stage=3;p->route_index=p->approach_completed?p->approach_completed-1:0;p->nav_step=0;p->nav_frame=frame();
 // Retrace only completed, actually observed own waypoints; finish at both initial safe positions.
 if(p->approach_completed>1){memcpy(p->front_goal,p->route[p->approach_completed-2],12);if(p->approach_completed>2)memcpy(p->support_goal,p->route[p->approach_completed-3],12);else memcpy(p->support_goal,p->safe_front,12);}
 else{memcpy(p->front_goal,p->safe_front,12);memcpy(p->support_goal,p->safe_support,12);}
 stop_both(5);event(63,reason);
}
static bool paired_geometry(const float front[3],const float support[3]){
 float spacing=distance(front,support),vx=p->front_goal[0]-p->support_goal[0],vy=p->front_goal[1]-p->support_goal[1];
 return distance(front,p->front_goal)<=15&&distance(support,p->support_goal)<=15&&spacing>=25&&spacing<=200&&(front[0]-support[0])*vx+(front[1]-support[1])*vy>0;
}
static void approach_leg(uint32_t index){p->mission_stage=1;p->route_index=index;p->nav_step=0;p->nav_frame=frame();p->nav_arrivals=p->nav_paired=p->nav_last_frame=0;memcpy(p->front_goal,p->route[index],12);memcpy(p->support_goal,index?p->route[index-1]:p->safe_front,12);stop_both(5);event(59,index);}
static void request_cleanup(uint32_t error,uint32_t now){p->error=error;p->mission_stage=5;p->phase=7;p->cleanup_started=now;p->cleanup_front_stopped=p->cleanup_support_stopped=0;}
static void advance_nav(uint32_t now){
 float f[3],s[3];read(p->unit+0x38,f,12);read(p->support.thing+0x38,s,12);
 if(p->nav_step==0){bool a=stop_settled(now),b=support_settled(now);if(a&&b){memcpy(p->front_hold,f,12);memcpy(p->support_hold,s,12);p->nav_step=1;p->nav_arrivals=p->nav_paired=0;p->nav_last_frame=0;event(58);event(58,0,0,0,0,0,1);if(p->mission_stage==1)move_role(false,p->front_goal);else move_role(true,p->support_goal);}else if(now-p->nav_frame>60){request_cleanup(44,now);}return;}
 if(now==p->nav_last_frame)return;
 p->nav_last_frame=now;
 bool approach=p->mission_stage==1;
 if(p->nav_step==1){bool held=distance(approach?s:f,approach?p->support_hold:p->front_hold)<=15;bool arrived=distance(approach?f:s,approach?p->front_goal:p->support_goal)<=15;
  p->nav_arrivals=held&&arrived?p->nav_arrivals+1:0;
  if(p->nav_arrivals>=3){event(61);event(61,0,0,0,0,0,1);p->nav_step=2;p->nav_arrivals=p->nav_paired=0;if(approach)move_role(true,p->support_goal);else move_role(false,p->front_goal);}
 }else if(p->nav_step==2){p->nav_paired=paired_geometry(f,s)?p->nav_paired+1:0;if(p->nav_paired>=3){event(60);event(60,0,0,0,0,0,1);
   if(approach){p->approach_completed++;if(p->approach_completed<p->route_count)approach_leg(p->approach_completed);else{p->mission_stage=2;p->combat_started=now;p->nav_step=0;stop_both(0);event(64);}}
   else{p->retreat_completed++;if(p->route_index>1){p->route_index--;memcpy(p->front_goal,p->route[p->route_index-1],12);memcpy(p->support_goal,p->route_index>1?p->route[p->route_index-2]:p->safe_front,12);p->nav_step=0;p->nav_frame=now;stop_both(5);}
    else if(p->route_index==1){p->route_index=0;memcpy(p->front_goal,p->safe_front,12);memcpy(p->support_goal,p->safe_support,12);p->nav_step=0;p->nav_frame=now;stop_both(5);}
    else{p->mission_stage=4;p->front_retreat_arrivals=p->support_retreat_arrivals=3;stop_both(2);event(65);}}
  }}
}
static bool no_override(){Support& s=p->support;return !p->native_move&&!p->native_attack&&!p->native_add&&!p->native_remove&&!p->native_stop&&!s.native_move&&!s.native_attack&&!s.native_add&&!s.native_remove&&!s.native_stop;}
static bool mobile(uint32_t t,uint32_t u){return !(word(t+0x84)&0x20080000)&&!word(t+0x238)&&word(u)==0xc48670&&word(u+0x24)==0xc48528&&word(u+8)==t;}
static bool absent_id(uint32_t id,uint32_t* count){
 uint32_t now=frame(),first=word(p->logic+0xb4),t=first;*count=0;
 while(t){if(t%4||*count>=20000||word(t)!=0xc4db60||!word(t+0xdc)||word(t+0xdc)==id)return false;uint32_t next=word(t+0x7c);if(next==t)return false;t=next;(*count)++;}
 return *count>0&&identity()&&frame()==now&&word(p->logic+0xb4)==first;
}
static void fatal_cleanup(uint32_t now){
 event(3);event(3,0,0,0,0,0,1);
 if(unit()&&p->detach_calls&&!p->return_calls){if(!p->cleanup_front_stopped){issue_stop(2);p->cleanup_front_stopped=1;}bool settled=stop_settled(now);if(settled||now-p->cleanup_started>=60){event(settled?68:69);tag=3;p->return_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->unit,1);p->return_verified=unit()&&word(p->unit+0x414)==p->default_team;event(5);tag=0;}}
 if(support_valid()&&p->support.detach_calls&&!p->support.return_calls){if(!p->cleanup_support_stopped){stop_support();p->cleanup_support_stopped=1;}bool settled=support_settled(now);if(settled||now-p->cleanup_started>=60){event(settled?68:69,0,0,0,0,0,1);tag=3;p->support.return_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->support.thing,1);p->support.returned=support_valid()&&word(p->support.thing+0x414)==p->default_team;event(5,0,0,0,0,0,1);tag=0;}}
 uint32_t count=0;
 if(!unit()&&!p->return_verified&&now!=p->front_last_absence_frame&&absent_id(p->object_id,&count)){p->front_last_absence_frame=now;p->front_absence_samples++;event(70,count);if(p->front_absence_samples>=2)p->front_disposed_verified=1;}
 if(!support_valid()&&!p->support.returned&&now!=p->support.last_absence_frame&&absent_id(p->support.id,&count)){p->support.last_absence_frame=now;p->support.absence_samples++;event(70,count,0,0,0,0,1);if(p->support.absence_samples>=2)p->support.disposed_verified=1;}
 if((!p->detach_calls||p->return_verified||p->front_disposed_verified)&&(!p->support.detach_calls||p->support.returned||p->support.disposed_verified)){p->returned_frame=now;finish();}
 else if(now-p->cleanup_started>=90){p->error=52;finish();}
}
static void CALLBACK tick(HWND,UINT,UINT_PTR,DWORD){
 if(GetCurrentThreadId()!=p->thread){p->error=30;return;}
 if(p->phase==2){if(!identity()||!unit()||!support_valid()||frame()-p->returned_frame>=p->post_frames){finish();}return;}
 if(!identity()){p->error=31;finish();return;}
 if(p->phase==7){if(paused()){p->paused_samples++;return;}fatal_cleanup(frame());return;}
 if(p->phase==5&&(!unit()||!support_valid())){p->error=34;finish();return;}
 if(!unit()||!support_valid()){p->error=32;p->lifecycle_fail++;p->phase=7;p->cleanup_started=frame();fatal_cleanup(frame());return;}
 if(paused()){p->paused_samples++;if(GetTickCount()-start_tick>330000)p->return_pending=1;return;}
 uint32_t now=frame();
 if(p->phase==5){
  if(p->stop_requested||GetTickCount()-start_tick>60000||p->route_count<2||p->route_count>16||p->mission_deadline_frame<=now+120||p->mission_deadline_frame-now>4500||now<p->target_observed_frame||now-p->target_observed_frame>60||!mobile(p->unit,p->update)||!mobile(p->support.thing,p->support.update)||!button_identity()||!visible_target()||p->support.id==p->object_id||p->support.hash!=0x2c358c61||word(p->owner+0xac)!=p->default_team||word(word(p->owner+0x8c)+0x10)!=p->script_team){p->error=34;finish();return;}
  read(p->unit+0x38,p->safe_front,12);read(p->support.thing+0x38,p->safe_support,12);float gap=distance(p->safe_front,p->safe_support);if(gap<25||gap>200){p->error=34;finish();return;}
  for(unsigned i=0;i<p->route_count;i++){float* prev=i?p->route[i-1]:p->safe_front;float d=distance(prev,p->route[i]);if(!finite_point(p->route[i])||d<25||d>180||fabsf(prev[2]-p->route[i][2])>100){p->error=34;finish();return;}}
  p->native_move=p->native_attack=p->native_add=p->native_remove=p->native_stop=0;p->support.native_move=p->support.native_attack=p->support.native_add=p->support.native_remove=p->support.native_stop=0;p->issued_frame=now;event(71);event(71,0,0,0,0,0,1);p->phase=1;p->original_team=word(p->unit+0x414);p->support.original_team=word(p->support.thing+0x414);
  tag=1;p->detach_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->unit,0);event(1);p->support.detach_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->support.thing,0);event(1,0,0,0,0,0,1);tag=0;
  if(word(p->unit+0x414)!=p->script_team||word(p->support.thing+0x414)!=p->script_team){request_cleanup(35,now);return;}approach_leg(0);return;
 }
 event(3);event(3,0,0,0,0,0,1);
 if(p->phase!=1)return;
 if(!no_override()||!mobile(p->unit,p->update)||!mobile(p->support.thing,p->support.update)){request_cleanup(38,now);return;}
 if(now+p->post_frames+5>=p->mission_deadline_frame||now-p->issued_frame>=p->lease_frames||GetTickCount()-start_tick>320000){request_cleanup(48,now);return;}
 if((p->stop_requested||GetTickCount()-p->heartbeat_tick>5000)&&p->mission_stage!=5){p->error=p->stop_requested?49:50;p->retreat_reason=4;p->mission_stage=5;stop_both(2);}
 if(p->mission_stage==5){bool a=stop_settled(now),b=support_settled(now);if(a&&b){event(67);event(67,0,0,0,0,0,1);normal_return();}else if(now-p->stop_issue_frame>60){request_cleanup(45,now);}return;}
 float front_hp=0,support_hp=0;read(word(p->unit+0x33c)+4,&front_hp,4);read(word(p->support.thing+0x33c)+4,&support_hp,4);
 if((p->retreat_requested||p->return_pending||front_hp<=25||support_hp<=25)&&p->mission_stage<3)begin_retreat(p->retreat_requested?4:3);
 if(p->mission_stage==1||p->mission_stage==3){if(now-p->nav_frame>300){if(p->mission_stage==1)begin_retreat(8);else{request_cleanup(53,now);}return;}advance_nav(now);return;}
 if(p->mission_stage==4){bool a=stop_settled(now),b=support_settled(now);if(a&&b){event(66);event(66,0,0,0,0,0,1);normal_return();}else if(now-p->stop_issue_frame>60){request_cleanup(45,now);}return;}
 if(p->mission_stage!=2)return;
 float f[3],s[3];read(p->unit+0x38,f,12);read(p->support.thing+0x38,s,12);float spacing=distance(f,s);
 if(spacing>=25&&spacing<=350&&distance(s,p->support_goal)<=15)p->combat_geometry_samples++;
 else if(p->lease_stage==1){begin_retreat(6);return;}
 if(!visible_target()){begin_retreat(2);return;}
 if(now-p->combat_started>=p->combat_frames){begin_retreat(5);return;}
 if(p->lease_stage==0){bool a=stop_settled(now),b=support_settled(now);if(a&&b){event(37);uint32_t e=0,ammo=0;uint32_t asset=current_weapon(&e,&ammo);if(asset==0x447ea26e){p->prepare_gate_frame=now;event(42);issue_stop(4);}else if(asset==0x41872ecc&&word(p->unit+0x26c)==0){p->lease_stage=3;tag=5;p->toggle_calls++;p->toggle_frame=now;((Button)0x790990)((void*)(uintptr_t)p->unit,(void*)(uintptr_t)p->button,1,0);event(39);tag=0;}else begin_retreat(7);}else if(now-p->stop_issue_frame>60){request_cleanup(44,now);}return;}
 if(p->lease_stage==3){if(now!=p->last_ak_frame){p->last_ak_frame=now;p->observed_weapon_asset=current_weapon(&p->observed_weapon_entry,&p->observed_ammo);uint32_t sm=word(p->update+0x3c);bool idle=word(word(sm+4)+4)==16&&!(word(sm+0x78)&0xffff)&&!word(p->update+0x150)&&!word(p->unit+0x238)&&word(p->update+0x50)==1;p->ak_samples=p->observed_weapon_asset==0x447ea26e&&now-p->toggle_frame>=15&&idle?p->ak_samples+1:0;if(p->ak_samples>=3){p->prepare_gate_frame=now;event(42);issue_stop(4);}else if(now-p->toggle_frame>60)begin_retreat(7);}return;}
 if(p->lease_stage==4){if(stop_settled(now)){event(43);uint32_t e=0,ammo=0;if(current_weapon(&e,&ammo)!=0x447ea26e||!ammo||ammo>3){begin_retreat(7);return;}p->lease_stage=1;tag=2;p->attack_calls++;p->attack_facade_calls++;((Attack)0x572280)((void*)(uintptr_t)(p->update+0x24),(void*)(uintptr_t)p->target_unit,0x7fffffff,1);event(2);tag=0;}else if(now-p->stop_issue_frame>60){request_cleanup(44,now);}return;}
 if(p->lease_stage==1){sample_weapon();if(p->damage_count&&p->commit_own_calls)begin_retreat(1);}
}
static void install(HWND hwnd){p->callback_thread=GetCurrentThreadId();FILETIME a,b,c,d;
 if(p->magic!=T_MAGIC||p->version!=3||GetCurrentProcessId()!=p->pid||p->thread!=p->callback_thread||!GetProcessTimes(GetCurrentProcess(),&a,&b,&c,&d)||a.dwLowDateTime!=p->start_low||a.dwHighDateTime!=p->start_high||!identity()||!unit()||p->type_hash!=0x19ab11af||p->lease_frames>4500||p->lease_frames<120||p->post_frames<30||p->post_frames>180){p->error=10;p->phase=4;return;}
 if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCSTR)(uintptr_t)&install,&pin)){p->error=11;p->phase=4;return;}
 for(unsigned i=0;i<13;i++)if(!read(hooks[i].a,hooks[i].before,hooks[i].n)||memcmp(hooks[i].before,hooks[i].signature,hooks[i].n)){p->error=12+i;p->phase=4;return;}
 if(used_count>=128||!p->token||p->seq<=last_seq){p->error=40;p->restore_mask=8191;p->phase=4;return;}for(unsigned i=0;i<used_count;i++)if(used_tokens[i]==p->token||!memcmp(used_commands[i],p->command,16)||!memcmp(used_tasks[i],p->task,16)){p->error=41;p->restore_mask=8191;p->phase=4;return;}uint32_t nonzero_command=0,nonzero_task=0;for(unsigned i=0;i<4;i++){nonzero_command|=p->command[i];nonzero_task|=p->task[i];}if(!nonzero_command||!nonzero_task){p->error=42;p->restore_mask=8191;p->phase=4;return;}memcpy(used_commands[used_count],p->command,16);memcpy(used_tasks[used_count],p->task,16);used_tokens[used_count++]=p->token;last_seq=p->seq;
 MH_STATUS s=MH_Initialize();if(s!=MH_OK&&s!=MH_ERROR_ALREADY_INITIALIZED){p->error=20;p->phase=4;return;}
 for(unsigned i=0;i<13;i++){Hook& h=hooks[i];if(!h.made&&MH_CreateHook((void*)(uintptr_t)h.a,h.fn,h.original)!=MH_OK){p->error=21;finish();return;}h.made=true;}
 for(unsigned i=0;i<13;i++){Hook& h=hooks[i];if(MH_EnableHook((void*)(uintptr_t)h.a)!=MH_OK){p->error=22;finish();return;}h.enabled=true;}
 p->phase=5;window=hwnd;start_tick=GetTickCount();timer=SetTimer(window,0x52413374,100,tick);if(!timer){p->error=23;finish();return;}event(0);
}
extern "C" __declspec(dllexport) LRESULT CALLBACK TacticalMissionFormation3Control(int code,WPARAM wp,LPARAM lp){
 if(code>=0&&wp==PM_REMOVE&&lp&&((MSG*)lp)->message==T_MESSAGE&&((MSG*)lp)->wParam==T_MAGIC){
  MSG* msg=(MSG*)lp;uint32_t token=(uint32_t)msg->lParam;
  if(token&&(!p||((p->phase==3||p->phase==4)&&p->restore_mask==8191&&!p->active&&!timer))){
   char name[100];snprintf(name,sizeof(name),"Local\\RA3TacticalMissionFormation3_%lu_%u",GetCurrentProcessId(),token);HANDLE next_mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);Tactical* next=next_mapping?(Tactical*)MapViewOfFile(next_mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Tactical)):NULL;
   if(next&&next->token==token&&next->pid==GetCurrentProcessId()&&next->magic==T_MAGIC){if(p)UnmapViewOfFile(p);if(mapping)CloseHandle(mapping);p=next;mapping=next_mapping;tag=0;install(msg->hwnd);}else{if(next)UnmapViewOfFile(next);if(next_mapping)CloseHandle(next_mapping);}
  }
 }
 return CallNextHookEx(NULL,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE h,DWORD why,LPVOID){if(why==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(h);return TRUE;}
