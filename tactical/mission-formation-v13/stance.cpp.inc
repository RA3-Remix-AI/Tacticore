// Normal StancesBehavior API only. Never write the enum, locks, target or path.
static StanceRole frozen_stances[2];static uint32_t stance_operation[2],stance_requested[2],stance_observed_this[2],stance_observed_caller[2],stance_observed_return[2];static bool stance_entered[2];
typedef bool (__attribute__((thiscall))*StanceSetter)(void*,uint32_t);static StanceSetter old_stance_setter;
static uint32_t stance_thing(uint32_t r){return r?p->support.thing:p->unit;}
static uint32_t stance_update(uint32_t r){return r?p->support.update:p->update;}
static bool stance_actor(uint32_t r){return r?support_valid():unit();}
static bool stance_definition(uint32_t role,StanceRole& out){
 memset(&out,0,sizeof(out));if(!stance_actor(role))return false;uint32_t t=stance_thing(role),m=word(t+0x380),data=word(m+4),list=word(word(data+8));
 out.module=m;out.vtable=word(m);out.backref=word(m+8);out.data=data;out.definition_list=list;out.definition_count=word(list+4);out.original_enum=word(m+0x38);out.capture_frame=frame();
 if(!m||out.vtable!=0xc37f90||out.backref!=t||word(0xc37f98)!=0x71d3f0||!data||!list||!out.definition_count||out.definition_count>4||!read(word(list+8),out.definition_entries,out.definition_count*8))return false;
 uint32_t seen=0;for(uint32_t i=0;i<out.definition_count;i++){uint32_t e=out.definition_entries[2*i];if(e>3||seen&(1u<<e))return false;seen|=1u<<e;}return (seen&5)==5&&out.original_enum<=3;
}
static bool stance_current(uint32_t role,bool require_hold){
 StanceRole current={};if(!frozen_stances[role].module||!stance_definition(role,current))return false;const StanceRole& saved=frozen_stances[role];
 return current.module==saved.module&&current.vtable==saved.vtable&&current.backref==saved.backref&&current.data==saved.data&&current.definition_list==saved.definition_list&&current.definition_count==saved.definition_count&&!memcmp(current.definition_entries,saved.definition_entries,32)&&(!require_hold||current.original_enum==2);
}
static bool expected_stance_stop(uint32_t role,uint32_t source){return role<2&&source==2&&(tag==7||tag==8)&&GetCurrentThreadId()==p->thread&&stance_operation[role]&&stance_entered[role]&&stance_current(role,false);}
static bool holding_stance(uint32_t thing,uint32_t update){uint32_t r=thing==p->unit?0:thing==p->support.thing?1:2;if(r>1||stance_update(r)!=update||!stance_current(r,true))return false;uint32_t sm=word(update+0x3c),state=word(sm+4);return word(sm+0x24)==thing&&word(state+0x18)==sm&&word(state+4)==94&&word(state)==0xc551a0;}
static void stance_proof(uint32_t role,Event& e){
 uint32_t* w=e.stack_words;memset(w,0,68*4);e.stack_count=0;e.stack_word_count=68;
 w[0]=0x53544e31;w[1]=1;w[2]=e.kind==132?5:(e.kind==130||e.kind==131)?(stance_operation[role]?stance_operation[role]+(e.kind==131):6):0;w[3]=role;w[4]=frame();
 uint32_t t=stance_thing(role),u=stance_update(role),m=word(t+0x380),data=word(m+4),list=word(word(data+8)),sm=word(u+0x3c),state=word(sm+4);
 w[6]=t;w[7]=word(t+0xdc);w[8]=word(word(t+4)+8);w[9]=word(t+0x418);w[10]=word(t+0x374);w[11]=word(u);w[12]=word(u+8);w[13]=m;w[14]=word(m);w[15]=word(m+8);w[16]=data;w[17]=list;w[18]=word(list+4);if(w[18]<=4)read(word(list+8),w+19,w[18]*8);
 w[27]=word(m+0x38);w[28]=frozen_stances[role].original_enum;w[29]=sm;w[30]=word(sm+0x24);w[31]=state;w[32]=word(state+4);w[33]=word(state);w[34]=word(state+0x18);w[35]=word(sm+0x78);w[36]=word(u+0x150);w[37]=word(u+0x50);
 if(w[32]==16||w[32]==94){w[38]=word(state+0x20);w[39]=word(w[38]);w[40]=word(w[38]+4);w[41]=word(w[40]+4);w[42]=word(w[40]);w[43]=word(w[40]+0x18);}
 w[44]=p->stances[role].set_calls;w[45]=p->stances[role].restore_calls;if(e.kind==130||e.kind==131){w[46]=stance_observed_this[role];w[47]=stance_requested[role];w[48]=stance_observed_return[role];w[49]=stance_observed_caller[role];}
 w[50]=p->stances[role].automatic_stop2;w[51]=p->stances[role].private_automatic_stop2;w[52]=frozen_stances[role].module;w[53]=frozen_stances[role].data;w[54]=frozen_stances[role].definition_list;w[55]=frozen_stances[role].definition_count;memcpy(w+56,frozen_stances[role].definition_entries,32);w[64]=frozen_stances[role].capture_frame;w[65]=stance_current(role,false);w[66]=p->stances[role].foreign_calls;w[67]=p->stances[role].restored;w[5]=frame();
}
static bool capture_stance(uint32_t role){StanceRole a={},b={};if(!stance_definition(role,a)||!stance_definition(role,b)||memcmp(&a,&b,sizeof(a))||a.original_enum!=0)return false;frozen_stances[role]=a;p->stances[role]=a;event(132,0,0,0,0,0,role);return true;}
#ifndef NORMAL_STANCE_CALL
#define NORMAL_STANCE_CALL(module,value) ((StanceSetter)0x7640f0)((void*)(uintptr_t)(module),(value))
#endif
static bool change_stance(uint32_t role,bool restore){
 StanceRole& result=p->stances[role];if(!stance_actor(role)||!stance_current(role,false)){if(restore){result.restored=0;event(133,1,0,0,0,0,role);}return false;}
 uint32_t desired=restore?frozen_stances[role].original_enum:2;stance_operation[role]=restore?3:1;stance_requested[role]=desired;stance_entered[role]=false;tag=restore?8:7;
 if(restore){result.restore_calls++;result.restore_before=word(frozen_stances[role].module+0x38);}else{result.set_calls++;result.set_before=word(frozen_stances[role].module+0x38);}
 bool returned=NORMAL_STANCE_CALL(frozen_stances[role].module,desired);bool valid=stance_current(role,false);uint32_t after=valid?word(frozen_stances[role].module+0x38):0xffffffffu;
 if(restore){result.restore_return=returned;result.restore_after=after;result.restored=valid&&after==desired&&(returned||result.restore_before==desired);}else{result.set_return=returned;result.set_after=after;}
 tag=0;stance_operation[role]=0;return valid&&after==desired&&(returned||(restore&&result.restore_before==desired));
}
static bool restore_stance(uint32_t role){bool okay=change_stance(role,true);if(!okay&&!p->error)p->error=61;return okay;}
static bool __attribute__((fastcall)) stance_setter_hook(void* self,void*,uint32_t value){
 InterlockedIncrement(&p->active);uint32_t r=(uintptr_t)self==word(p->unit+0x380)?0:(uintptr_t)self==word(p->support.thing+0x380)?1:2;
 if(r<2){bool expected=GetCurrentThreadId()==p->thread&&stance_operation[r]&&!stance_entered[r]&&value==stance_requested[r]&&tag==(stance_operation[r]==1?7u:8u)&&stance_current(r,false);if(expected)stance_entered[r]=true;else if(role_leased(r)){p->stances[r].foreign_calls++;p->error=62;}stance_observed_this[r]=(uintptr_t)self;stance_observed_caller[r]=(uintptr_t)__builtin_return_address(0);stance_requested[r]=value;stance_observed_return[r]=0;event(130,value,stance_observed_caller[r],0,0,0,r);}
 bool result=old_stance_setter(self,value);if(r<2){stance_observed_return[r]=result;event(131,result,0,0,0,0,r);}InterlockedDecrement(&p->active);return result;
}
