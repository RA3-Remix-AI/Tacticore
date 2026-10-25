#include "shared.h"
#include "MinHook.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <stddef.h>
static float frozen_route[16][3];static uint32_t frozen_route_count,frozen_deadline,frozen_lease_frames;
static uint32_t wait_reanchor_count;static Breadcrumb reanchor_surface;
static MoveLineage lineage_record;
static bool retreat_departure_used,retreat_departure_active;static uint32_t retreat_departure_frame;static float retreat_departure_gap;static Breadcrumb retreat_departure_origin;
static Breadcrumb frozen_crumbs[2][CRUMB_CAP];static uint32_t frozen_crumb_counts[2],frozen_follow_role,frozen_follow_index;static float frozen_goals[2][3],frozen_origins[2][3];
static void controller_close();
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
static uint32_t schedule_proof[24];
static void stance_proof(uint32_t,Event&);
static bool holding_stance(uint32_t,uint32_t);
static bool capture_stance(uint32_t);
static bool change_stance(uint32_t,bool);
static bool restore_stance(uint32_t);
static bool stance_current(uint32_t,bool);
static bool expected_stance_stop(uint32_t,uint32_t);
#include "event.cpp.inc"

typedef void (__attribute__((thiscall))*Move)(void*,float*,void*,float,uint32_t);typedef void (__attribute__((thiscall))*MoveFacade)(void*,float*,uint32_t);static MoveFacade old_move_facade;typedef void (__attribute__((thiscall))*Attack)(void*,void*,uint32_t,uint32_t);typedef void (__attribute__((thiscall))*Transfer)(void*,void*,uint32_t);typedef void (__attribute__((thiscall))*Member)(void*,void*);
typedef void (__attribute__((thiscall))*Damage)(void*,void*);static Damage old_damage;typedef uint32_t (__attribute__((thiscall))*WeaponGet)(void*,uint32_t);static WeaponGet old_weapon_get;
static Move old_move;static Attack old_attack;static Transfer old_transfer;static Member old_add,old_remove;
#include "pending.cpp.inc"
static void __attribute__((fastcall)) move_hook(void* self,void*,float* xyz,void* path,float limit,uint32_t source){
 InterlockedIncrement(&p->active);bool front=(uintptr_t)self==p->update,support=(uintptr_t)self==p->support.update;
 bool accepted=false,continuation=false;uint32_t caller=(uintptr_t)__builtin_return_address(0);
 if((front||support)&&role_leased(support)){accepted=authorize_private_move(support,xyz,(uintptr_t)path,limit,source,caller);continuation=accepted&&tag==0;if(!accepted){invalidate_move_ticket(support,3);ticket_foreign(support,1,0,(uintptr_t)self,word((uintptr_t)self+8),0,caller,3);}}
 if(front||support){event(10,source,caller,0,0,0,support,xyz,(uintptr_t)path,limit);if(continuation){move_tickets[support].proof.private_seq=p->count;move_tickets[support].proof.observed_this=(uintptr_t)self;move_tickets[support].proof.observed_thing=word((uintptr_t)self+8);move_tickets[support].proof.observed_command=(uintptr_t)xyz;lineage_emit(116,support);}}
 old_move(self,xyz,path,limit,source);if(front||support)event(11,source,0,0,0,0,support,xyz,(uintptr_t)path,limit);InterlockedDecrement(&p->active);
}
static void __attribute__((fastcall)) move_facade_hook(void* self,void*,float* xyz,uint32_t source){
 InterlockedIncrement(&p->active);bool front=(uintptr_t)self==p->update+0x24,support=(uintptr_t)self==p->support.update+0x24;
 bool owned=(front||support)&&ticket_leased(support)&&tag==6&&ticket_current(support)&&source==1&&xyz&&!memcmp(xyz,move_tickets[support].proof.goal,12);
 if((front||support)&&role_leased(support)&&!owned){invalidate_move_ticket(support,3);ticket_foreign(support,2,0,(uintptr_t)self,word((uintptr_t)self-0x24+8),0,(uintptr_t)__builtin_return_address(0),3);}
 if(front||support)event(50,source,(uintptr_t)__builtin_return_address(0),0,0,0,support,xyz);
 if(owned){move_tickets[support].facade_open=true;move_tickets[support].proof.own_facade_seq=p->count;move_tickets[support].proof.observed_this=(uintptr_t)self;move_tickets[support].proof.observed_thing=0;move_tickets[support].proof.observed_command=(uintptr_t)xyz;lineage_emit(110,support);}
 old_move_facade(self,xyz,source);if(front||support)event(51,source,0,0,0,0,support,xyz);InterlockedDecrement(&p->active);
 if(owned){MoveTicket& t=move_tickets[support];t.facade_open=false;if(!t.pending&&!t.proof.delivered){invalidate_move_ticket(support,10);ticket_foreign(support,6,0,(uintptr_t)self,word((uintptr_t)self-0x24+8),0,(uintptr_t)__builtin_return_address(0),10);}t.proof.observed_this=(uintptr_t)self;t.proof.observed_thing=0;t.proof.observed_command=(uintptr_t)xyz;lineage_emit(119,support);if(t.proof.delivered)t.armed=false;}
}
static bool weapon_identity(){uint32_t e=p->weapon_entry,slot=p->weapon_slot,cont=word(p->unit+0x37c);if(!e||word(e)!=0xc2e324||word(e+4)!=p->weapon_template||word(e+8)!=slot||word(cont+8)!=p->unit)return false;uint32_t a=word(cont+0x24),z=word(cont+0x28),found=0;if(!a||z<a||z-a>256||(z-a)%4)return false;for(;a<z;a+=4)found|=word(a)==slot;if(!found)return false;uint32_t entries=word(slot+0x94);found=0;for(unsigned i=0;entries&&i<6;i++)found|=word(entries+4*i)==e;return found;}
static uint32_t __attribute__((fastcall)) weapon_get_hook(void* self,void*,uint32_t selector){InterlockedIncrement(&p->active);uint32_t result=old_weapon_get(self,selector);if((tag==2||p->lease_stage==1)&&GetCurrentThreadId()==p->thread&&(uintptr_t)self==word(p->unit+0x37c)&&(uintptr_t)__builtin_return_address(0)==0x76e6c6&&p->mission_stage==2&&word(result)==0xc2e324){if(!p->weapon_entry){p->weapon_entry=result;p->weapon_template=word(result+4);p->weapon_slot=word(result+8);p->weapon_ammo=p->last_ammo=word(result+0x1c);p->limit_before=word(result+0x24);}else if(result!=p->weapon_entry||word(result+4)!=p->weapon_template||word(result+8)!=p->weapon_slot){p->error=56;}}InterlockedDecrement(&p->active);return result;}
static void sample_weapon(){if(!weapon_identity())return;uint32_t ammo=word(p->weapon_entry+0x1c),limit=word(p->weapon_entry+0x24);if(ammo<p->last_ammo&&p->last_ammo<100000&&limit<=p->last_limit){event(22,p->object_id,0,(float)p->last_ammo,(float)ammo,0);p->shot_samples++;}p->last_ammo=ammo;p->last_limit=limit;}
static void __attribute__((fastcall)) attack_hook(void* self,void*,void* target,uint32_t shots,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update;if(ours&&role_leased(false))invalidate_move_ticket(0,2);if((uintptr_t)self==p->support.update&&role_leased(true))invalidate_move_ticket(1,2);observed_shots=shots;observed_source=source;if(ours){bool expected=p->lease_stage==1&&p->attack_facade_calls==1&&!p->attack_private_calls&&(uintptr_t)target==p->target_unit&&shots==0x7fffffff&&source==1;if(expected){p->attack_private_calls++;p->attack_issued_frame=frame();}else if((!tag||tag==7||tag==8)&&role_leased(false))p->native_attack++;event(12,word((uintptr_t)target+0xdc),(uintptr_t)__builtin_return_address(0));}if((uintptr_t)self==p->support.update){if((!tag||tag==7||tag==8)&&role_leased(true))p->support.native_attack++;event(12,word((uintptr_t)target+0xdc),(uintptr_t)__builtin_return_address(0),0,0,0,1);}old_attack(self,target,shots,source);if((uintptr_t)self==p->support.update)event(13,word((uintptr_t)target+0xdc),0,0,0,0,1);if(ours){if(p->lease_stage==1&&weapon_identity()){p->limit_after=p->last_limit=word(p->weapon_entry+0x24);p->last_ammo=word(p->weapon_entry+0x1c);}event(13,word((uintptr_t)target+0xdc));}InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) transfer_hook(void* self,void*,void* target,uint32_t to_ai){InterlockedIncrement(&p->active);bool ours=(uintptr_t)target==p->unit;if(ours&&role_leased(false))invalidate_move_ticket(0,4);if((uintptr_t)target==p->support.thing&&role_leased(true))invalidate_move_ticket(1,4);if(ours)event(14,to_ai,(uintptr_t)__builtin_return_address(0));if((uintptr_t)target==p->support.thing){event(14,to_ai,(uintptr_t)__builtin_return_address(0),0,0,0,1);}old_transfer(self,target,to_ai);if(ours)event(15,to_ai);if((uintptr_t)target==p->support.thing)event(15,to_ai,0,0,0,0,1);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) add_hook(void* self,void*,void* target){InterlockedIncrement(&p->active);bool ours=(uintptr_t)target==p->unit;if(ours){if((!tag||tag==7||tag==8)&&role_leased(false))p->native_add++;event(16,(uintptr_t)self,(uintptr_t)__builtin_return_address(0));}if((uintptr_t)target==p->support.thing){if((!tag||tag==7||tag==8)&&role_leased(true))p->support.native_add++;event(16,(uintptr_t)self,(uintptr_t)__builtin_return_address(0),0,0,0,1);}old_add(self,target);if(ours)event(17,(uintptr_t)self);if((uintptr_t)target==p->support.thing)event(17,(uintptr_t)self,0,0,0,0,1);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) remove_hook(void* self,void*,void* target){InterlockedIncrement(&p->active);bool ours=(uintptr_t)target==p->unit;if(ours){if((!tag||tag==7||tag==8)&&role_leased(false))p->native_remove++;event(18,(uintptr_t)self,(uintptr_t)__builtin_return_address(0));}if((uintptr_t)target==p->support.thing){if((!tag||tag==7||tag==8)&&role_leased(true))p->support.native_remove++;event(18,(uintptr_t)self,(uintptr_t)__builtin_return_address(0),0,0,0,1);}old_remove(self,target);if(ours)event(19,(uintptr_t)self);if((uintptr_t)target==p->support.thing)event(19,(uintptr_t)self,0,0,0,0,1);InterlockedDecrement(&p->active);}
static bool visible_target(){
 uint32_t t=p->target_unit;if(word(p->owner+0x20)!=3)return false;if(word(t)!=0xc4db60||word(t+0xdc)!=p->target_id||word(t+4)!=p->target_template||word(p->target_template+8)!=p->target_hash||word(t+0x418)!=p->target_owner||word(p->target_owner)!=0xc5bce0||word(t+0xc8)&((1u<<11)|(1u<<12)))return false;
 uint32_t index=word(p->target_owner+0x20);if(index>=20||index==3)return false;uint32_t rel=word(p->owner+0xfc),buckets=word(rel+8),count=word(rel+0xc);if(!rel||!word(rel+0x10)||!buckets||count<1||count>4096)return false;uint32_t n=word(buckets+(index%count)*4),found=0;for(unsigned i=0;n&&i<100;i++){if(word(n)==index){found=word(n+4)==0?1:2;break;}n=word(n+8);}if(found!=1)return false;
 uint32_t manager=word(0xce2fa0),impl=word(manager+0x28);if(word(manager)!=0xc6aefc)return false;uint32_t cells=word(impl+0x44),width=word(impl+0x3c),height=word(impl+0x40),fallback=word(0xd074a4);float origin[2]={},scale=0,xyz[3]={};if(!read(impl+4,origin,8)||!read(impl+0x38,&scale,4)||!isfinite(origin[0])||!isfinite(origin[1]))return false;if(!cells||width<1||height<1||width>4096||height>4096||width*height>4000000||!isfinite(scale)||scale<=0||scale>10)return false;BYTE flag=1;uint16_t c=0;
 uint32_t record=word(t+0x9c),first=word(record+0x1c),num=word(record+0x20);BYTE pending=1,masked=1;read(record+0xf8,&pending,1);read(record+0xf9,&masked,1);if(!record||word(record)!=impl||pending||masked||!first||num<1||num>4096)return false;uint32_t total=0;
 for(uint32_t i=0;i<num;i++){uint32_t cell=word(first+16*i);if(!cell)continue;if(cell<cells||(cell-cells)%0x34||(cell-cells)/0x34>=width*height)return false;total++;flag=1;c=0;read(cell+0x32,&flag,1);read(cell+10,&c,2);if(flag||!c||(c==0xffff&&fallback!=1))return false;}
 if(!total)return false;
 if(!read(t+0x38,xyz,12)||!isfinite(xyz[0])||!isfinite(xyz[1])||!isfinite(xyz[2]))return false;int gx=(int)((xyz[0]-origin[0])*scale),gy=(int)((xyz[1]-origin[1])*scale);if(gx<0||gy<0||(unsigned)gx>=width||(unsigned)gy>=height)return false;uint32_t center=cells+((uint32_t)gy*width+gx)*0x34;flag=1;c=0;read(center+0x32,&flag,1);read(center+10,&c,2);if(flag||!c||(c==0xffff&&fallback!=1))return false;
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
 if(front||support){if(role_leased(support))invalidate_move_ticket(support,1);if(expected_stance_stop(support,source))p->stances[support].automatic_stop2++;if(!tag||((tag==7||tag==8)&&!expected_stance_stop(support,source))){if(front&&role_leased(false))p->native_stop++;else if(support&&role_leased(true))p->support.native_stop++;}event(30,source,(uintptr_t)__builtin_return_address(0),0,0,0,support);}
 old_stop_facade(self,source);if(front||support)event(31,source,0,0,0,0,support);InterlockedDecrement(&p->active);
}
static void __attribute__((fastcall)) stop_private_hook(void* self,void*,uint32_t source){
 InterlockedIncrement(&p->active);bool front=(uintptr_t)self==p->update,support=(uintptr_t)self==p->support.update;uint32_t caller=(uintptr_t)__builtin_return_address(0);
 if(front||support){event(32,source,caller,0,0,0,support);}old_stop_private(self,source);
 if(front){if(expected_stance_stop(0,source))p->stances[0].private_automatic_stop2++;p->total_private_stops++;if((p->phase==1||p->phase==7)&&source==1&&caller==0x787791){if(p->lease_stage==3&&p->phase==1)p->prepare_reconstituted_stops++;else if(p->stop_calls){p->private_stop_calls++;p->private_stop_frame=frame();}}event(33,source,caller);}
 if(support){if(expected_stance_stop(1,source))p->stances[1].private_automatic_stop2++;if((p->phase==1||p->phase==7)&&source==1&&caller==0x787791&&p->support.stop_calls){p->support.private_stop_calls++;p->support.private_stop_frame=frame();}event(33,source,caller,0,0,0,1);}
 InterlockedDecrement(&p->active);
}
#include "stance.cpp.inc"
static void __attribute__((fastcall)) attack_facade_hook(void* self,void*,void* target,uint32_t shots,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update+0x24;if(ours&&role_leased(false))invalidate_move_ticket(0,2);observed_shots=shots;observed_source=source;if(ours)event(34,word((uintptr_t)target+0xdc),(uintptr_t)__builtin_return_address(0));old_attack_facade(self,target,shots,source);if(ours)event(35,word((uintptr_t)target+0xdc));InterlockedDecrement(&p->active);}
static void issue_stop(uint32_t stage){p->lease_stage=stage;p->stop_issue_frame=frame();p->stable_samples=p->stop_gate_samples=p->last_sample_frame=0;read(p->unit+0x38,p->stopped_xyz,12);tag=4;p->stop_calls++;((Stop)0x54b0a0)((void*)(uintptr_t)(p->update+0x24),1);event(36);tag=0;}
static bool stop_settled(uint32_t now){if(now==p->last_sample_frame)return false;p->last_sample_frame=now;uint32_t sm=word(p->update+0x3c);float xyz[3];read(p->unit+0x38,xyz,12);bool gate=p->private_stop_calls==p->stop_calls&&now>p->private_stop_frame&&word(p->update+0x50)==1&&!(word(sm+0x78)&0xffff)&&word(p->update+0x150)==0&&holding_stance(p->unit,p->update);float dx=xyz[0]-p->stopped_xyz[0],dy=xyz[1]-p->stopped_xyz[1];if(gate){p->stop_gate_samples++;if(dx*dx+dy*dy<=1)p->stable_samples++;else p->stable_samples=0;}else{p->stop_gate_samples=p->stable_samples=0;}memcpy(p->stopped_xyz,xyz,12);return p->stop_gate_samples>=3&&p->stable_samples>=3;}
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
{0x790990,(void*)button_hook,(void**)&old_button,"\x8b\x44\x24\x0c\x8b\x54\x24\x08\x6a\x00\x6a\x00\x6a\x00",14,{},false,false},
{0x830220,(void*)stored_copy_hook,(void**)&old_stored_copy,"\x53\x55\x56\x8b\xf1\x57\x8b\x7c\x24\x14",10,{},false,false},
{0x830320,(void*)stored_unpack_hook,(void**)&old_stored_unpack,"\x83\xec\x0c\x53\x56\x8b\xf1\x8b\x46\x14",10,{},false,false},
{0x787500,(void*)command_dispatch_hook,(void**)&old_command_dispatch,"\x83\xec\x60\x53\x55\x8b\xd9\x8b\x43\xdc",10,{},false,false},
{0x7640f0,(void*)stance_setter_hook,(void**)&old_stance_setter,"\x83\xec\x14\x53\x8b\xd9\x8b\x43\x08",9,{},false,false}};
static void finish(){if(timer){KillTimer(window,timer);timer=0;}event(4);for(unsigned i=0;i<17;i++){Hook& h=hooks[i];if(h.enabled){MH_DisableHook((void*)(uintptr_t)h.a);h.enabled=false;}BYTE b[24];if(h.made&&read(h.a,b,h.n)&&!memcmp(b,h.before,h.n))p->restore_mask|=1u<<i;}p->phase=p->error?4:3;
 if(p->return_verified||p->front_disposed_verified)p->controller.held_mask&=~1u;if(p->support.returned||p->support.disposed_verified)p->controller.held_mask&=~2u;p->controller.channel_claimed=p->controller.held_mask?1:0;p->controller.stage=5;
 for(uint32_t r=0;r<2;r++){p->slots[r].return_verified=r?p->support.returned:p->return_verified;p->slots[r].restore_verified=p->stances[r].restored;p->slots[r].disposed_verified=r?p->support.disposed_verified:p->front_disposed_verified;if(p->slots[r].return_verified||p->slots[r].disposed_verified)p->slots[r].stage=8;}
 controller_close();
}
#include "mission_state.cpp.inc"
#include "controller.cpp.inc"
#include "scheduler.cpp.inc"
static void install(HWND hwnd){p->callback_thread=GetCurrentThreadId();FILETIME a,b,c,d;
 if(p->magic!=T_MAGIC||p->version!=14||GetCurrentProcessId()!=p->pid||p->thread!=p->callback_thread||!GetProcessTimes(GetCurrentProcess(),&a,&b,&c,&d)||a.dwLowDateTime!=p->start_low||a.dwHighDateTime!=p->start_high||!identity()||p->lease_frames!=4500||p->post_frames<30||p->post_frames>180){p->error=10;p->phase=4;return;}
 if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCSTR)(uintptr_t)&install,&pin)){p->error=11;p->phase=4;return;}
 for(unsigned i=0;i<17;i++)if(!read(hooks[i].a,hooks[i].before,hooks[i].n)||memcmp(hooks[i].before,hooks[i].signature,hooks[i].n)){p->error=12+i;p->phase=4;return;}
 if(used_count>=128||!p->token||p->seq<=last_seq){p->error=40;p->restore_mask=131071;p->phase=4;return;}for(unsigned i=0;i<used_count;i++)if(used_tokens[i]==p->token||!memcmp(used_commands[i],p->command,16)||!memcmp(used_tasks[i],p->task,16)){p->error=41;p->restore_mask=131071;p->phase=4;return;}uint32_t nonzero_command=0,nonzero_task=0;for(unsigned i=0;i<4;i++){nonzero_command|=p->command[i];nonzero_task|=p->task[i];}if(!nonzero_command||!nonzero_task){p->error=42;p->restore_mask=131071;p->phase=4;return;}memcpy(used_commands[used_count],p->command,16);memcpy(used_tasks[used_count],p->task,16);used_tokens[used_count++]=p->token;last_seq=p->seq;
 MH_STATUS s=MH_Initialize();if(s!=MH_OK&&s!=MH_ERROR_ALREADY_INITIALIZED){p->error=20;p->phase=4;return;}
 for(unsigned i=0;i<17;i++){Hook& h=hooks[i];if(!h.made&&MH_CreateHook((void*)(uintptr_t)h.a,h.fn,h.original)!=MH_OK){p->error=21;finish();return;}h.made=true;}
 for(unsigned i=0;i<17;i++){Hook& h=hooks[i];if(MH_EnableHook((void*)(uintptr_t)h.a)!=MH_OK){p->error=22;finish();return;}h.enabled=true;}
 if(!controller_start13()){p->error=70;finish();return;}
 frozen_route_count=0;frozen_deadline=0;frozen_lease_frames=4500;memset(frozen_route,0,sizeof(frozen_route));window=hwnd;start_tick=GetTickCount();schedule_reset();p->phase=1;timer=SetTimer(window,0x5241337f,T_PULSE_PERIOD_MS,tick);if(!timer){p->error=23;finish();return;}event(0);schedule_advance(1);
}
extern "C" __declspec(dllexport) LRESULT CALLBACK TacticalMissionFormation14Control(int code,WPARAM wp,LPARAM lp){
 if(code>=0&&wp==PM_REMOVE&&lp&&((MSG*)lp)->message==T_PULSE_MESSAGE){MSG* pulse=(MSG*)lp;if(pulse->hwnd==window)schedule_pulse((uint32_t)pulse->wParam,(uint32_t)pulse->lParam);}
 if(code>=0&&wp==PM_REMOVE&&lp&&((MSG*)lp)->message==T_MESSAGE&&((MSG*)lp)->wParam==T_MAGIC){
  MSG* msg=(MSG*)lp;uint32_t token=(uint32_t)msg->lParam;
  if(token&&(!p||((p->phase==3||p->phase==4)&&p->restore_mask==131071&&!p->active&&!timer&&!p->controller.held_mask&&!p->controller.channel_claimed))){
   char name[100];snprintf(name,sizeof(name),"Local\\RA3TacticalMissionFormation14_%lu_%u",GetCurrentProcessId(),token);HANDLE next_mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);Tactical* next=next_mapping?(Tactical*)MapViewOfFile(next_mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(Tactical)):NULL;
   if(next&&next->token==token&&next->pid==GetCurrentProcessId()&&next->magic==T_MAGIC){if(p)UnmapViewOfFile(p);if(mapping)CloseHandle(mapping);p=next;mapping=next_mapping;tag=0;install(msg->hwnd);}else{if(next)UnmapViewOfFile(next);if(next_mapping)CloseHandle(next_mapping);}
  }
 }
 return CallNextHookEx(NULL,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE h,DWORD why,LPVOID){if(why==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(h);return TRUE;}
