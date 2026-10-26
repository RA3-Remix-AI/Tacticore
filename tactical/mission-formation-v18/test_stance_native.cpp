// Actual stance.cpp.inc with only the normal setter replaced by a fake engine.
#include "shared.h"
#include <map>
#include <vector>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
static std::map<uint32_t,BYTE> memory;static Tactical storage,*p=&storage;static uint32_t tag,now=10;static unsigned checks,api_calls;static bool fail_set,fail_restore;
static bool read(uint32_t a,void* out,SIZE_T n){for(SIZE_T i=0;i<n;i++){auto q=memory.find(a+i);if(q==memory.end())return false;((BYTE*)out)[i]=q->second;}return true;}
template<class T>static void put(uint32_t a,T v){for(unsigned i=0;i<sizeof(v);i++)memory[a+i]=((BYTE*)&v)[i];}
static uint32_t word(uint32_t a){uint32_t w=0;read(a,&w,4);return w;}
static uint32_t frame(){return now;}
static bool unit(){return word(p->unit+0xdc)==p->object_id&&word(p->unit+0x418)==p->owner;}
static bool support_valid(){return word(p->support.thing+0xdc)==p->support.id&&word(p->support.thing+0x418)==p->owner;}
static bool role_leased(bool r){return r?p->support.detach_calls&&!p->support.returned:p->detach_calls&&!p->return_verified;}
static void stance_proof(uint32_t,Event&);
static uint32_t event(uint32_t kind,uint32_t arg=0,uint32_t caller=0,float=0,float=0,float=0,uint32_t role=0,const float* =NULL,uint32_t=0,float=0,const uint32_t* =NULL);
static bool fake_call(uint32_t,uint32_t);
#define NORMAL_STANCE_CALL(module,value) fake_call(module,value)
#include "stance.cpp.inc"
static uint32_t event(uint32_t kind,uint32_t arg,uint32_t caller,float,float,float,uint32_t role,const float*,uint32_t,float,const uint32_t*){if(p->count>=T_CAP)abort();Event& e=p->events[p->count];memset(&e,0,sizeof(e));e.kind=kind;e.arg=arg;e.caller=caller;e.frame=now;e.thread=GetCurrentThreadId();e.role=role;e.tag=tag;e.unit_id=role?p->support.id:p->object_id;e.owner=p->owner;uint32_t u=role?p->support.update:p->update,t=role?p->support.thing:p->unit;e.sm=word(u+0x3c);e.sm_flags=word(e.sm+0x78);e.state=word(e.sm+4);e.state_id=word(e.state+4);e.path=word(u+0x150);e.source=word(u+0x50);e.holder=word(t+0x238);read(t+0x38,&e.x,12);stance_proof(role,e);e.seq=++p->count;return e.seq;}
static bool __attribute__((thiscall)) fake_original(void* module,uint32_t value){uint32_t m=(uintptr_t)module;api_calls++;if((value==2&&fail_set)||(value==0&&fail_restore))return false;uint32_t old=word(m+0x38);if(old==value)return false;put(m+0x38,value);return true;}
static bool fake_call(uint32_t module,uint32_t value){return stance_setter_hook((void*)(uintptr_t)module,NULL,value);}
static void need(bool b,const char* why){checks++;if(!b){fprintf(stderr,"FAIL %s\n",why);exit(1);}}
static void reset(){memory.clear();memset(p,0,sizeof(*p));memset(frozen_stances,0,sizeof(frozen_stances));memset(stance_operation,0,sizeof(stance_operation));memset(stance_entered,0,sizeof(stance_entered));tag=0;now=10;api_calls=0;fail_set=fail_restore=false;p->unit=0x2000;p->object_id=11;p->update=0x6000;p->support.thing=0x3000;p->support.id=12;p->support.update=0x7000;p->owner=0x9000;p->thread=GetCurrentThreadId();old_stance_setter=fake_original;
 for(uint32_t r=0;r<2;r++){uint32_t t=r?p->support.thing:p->unit,u=r?p->support.update:p->update,m=0x10000+r*0x1000,data=0x20000+r*0x1000,list=0x30000+r*0x1000,inner=0x40000+r*0x1000,items=0x50000+r*0x1000,sm=0x60000+r*0x1000,state=0x70000+r*0x1000;for(uint32_t i=0;i<0x500;i++){memory[t+i]=0;memory[u+i]=0;memory[m+i]=0;}put(t+0xdc,r?12u:11u);put(t+0x418,p->owner);put(t+0x374,u);put(t+4,0x80000+r*0x1000);put(0x80008+r*0x1000,r?0x2c358c61u:0x19ab11afu);put(u,0xc48670u);put(u+8,t);put(u+0x3c,sm);put(u+0x50,1u);put(sm+4,state);put(sm+0x24,t);put(sm+0x78,0x10000u);put(state,0xc551a0u);put(state+4,94u);put(state+0x18,sm);put(t+0x380,m);put(m,0xc37f90u);put(m+4,data);put(m+8,t);put(m+0x38,0u);put(data+8,inner);put(inner,list);put(list+4,4u);put(list+8,items);for(uint32_t i=0;i<4;i++){put(items+8*i,i);put(items+8*i+4,0u);}}
 put(0xc37f98,0x71d3f0u);
}
int main(int argc,char** argv){
 reset();need(capture_stance(0)&&capture_stance(1),"both original captures");need(frozen_stances[0].original_enum==0&&p->stances[1].definition_count==4,"actual original definitions");p->detach_calls=p->support.detach_calls=1;
 need(change_stance(0,false)&&change_stance(1,false),"normal Set2 per role");need(api_calls==2&&p->stances[0].set_calls==1&&p->stances[1].set_after==2,"exact set counters and readback");need(holding_stance(p->unit,p->update)&&holding_stance(p->support.thing,p->support.update),"both actual94 held stance");event(3);event(3,0,0,0,0,0,1);need(restore_stance(0)&&restore_stance(1),"both original normal restores");need(api_calls==4&&p->stances[0].restored&&p->stances[1].restore_after==0,"restored actual0 and four setters");need(!p->stances[0].foreign_calls&&!p->stances[1].foreign_calls,"own setter never foreign");if(argc>1){FILE* f=fopen(argv[1],"wb");if(!f)return 2;fwrite(p,1,sizeof(*p),f);fclose(f);}
 reset();put(0x10008,999u);need(!capture_stance(0),"module backref rejection");reset();put(0x10000,0x1234u);need(!capture_stance(0),"module VT rejection");reset();put(0x10038,2u);need(!capture_stance(0),"original must real GUARD0");reset();put(0x30004,5u);need(!capture_stance(0),"enum definition bounds");reset();put(0x50010,0u);need(!capture_stance(0),"duplicate definition rejection");
 reset();capture_stance(0);p->detach_calls=1;fail_set=true;need(!change_stance(0,false)&&p->stances[0].set_return==0&&word(0x10038)==0,"failed setter cannot certify HOLD");need(restore_stance(0)&&p->stances[0].restored&&p->stances[0].restore_return==0,"normal unchanged0 setter false still preserved original");
 reset();capture_stance(0);p->detach_calls=1;change_stance(0,false);fail_restore=true;need(!restore_stance(0)&&!p->stances[0].restored&&word(0x10038)==2,"restore failure truthful");
 reset();capture_stance(0);p->detach_calls=1;change_stance(0,false);put(p->unit+0x380,999u);unsigned before=api_calls;need(!restore_stance(0)&&api_calls==before&&!p->stances[0].restored,"module loss never old setter");
 reset();capture_stance(0);p->detach_calls=1;change_stance(0,false);put(p->unit+0xdc,99u);before=api_calls;need(!restore_stance(0)&&api_calls==before,"actor loss never stale setter");
 reset();capture_stance(0);p->detach_calls=1;change_stance(0,false);tag=0;fake_call(0x10000,1);need(p->stances[0].foreign_calls==1&&p->error==62,"external setter is interference");
 reset();capture_stance(0);p->detach_calls=1;change_stance(0,false);put(word(p->update+0x3c)+4,0x70000u);put(0x70004,16u);need(!holding_stance(p->unit,p->update),"Guard16 cannot pretend HOLD94");
 reset();capture_stance(0);p->detach_calls=1;change_stance(0,false);put(0x10038,0u);need(!holding_stance(p->unit,p->update),"state94 without actualenum2 rejected");
 reset();capture_stance(0);p->detach_calls=1;change_stance(0,false);stance_operation[0]=1;stance_entered[0]=true;tag=7;need(expected_stance_stop(0,2)&&!expected_stance_stop(0,1)&&!expected_stance_stop(1,2),"only same role source2 in real private op");tag=0;need(!expected_stance_stop(0,2),"source2 tag0 not exempt");
 printf("{\"scope\":\"actual_stance_cpp_fake_setter\",\"tests\":%u,\"passed\":true,\"field_verified\":false}\n",checks);return 0;
}
