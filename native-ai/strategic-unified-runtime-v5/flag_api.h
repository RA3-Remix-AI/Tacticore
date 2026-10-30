#pragma once
// Fixed strategic flag API, extracted from the frozen Native3 implementation.
// No unit/queue/builder setter exists here. All physical writes use SET_FLAG.
// Included AFTER native's checked read/word helpers and manager input guard.
static bool flag_bytes(uint32_t at,const char* value,SIZE_T n){BYTE buffer[32];return n<=sizeof(buffer)&&read(at,buffer,n)&&!memcmp(buffer,value,n);}
static bool flag_signatures(){
 return flag_bytes(0x58b240,"\x53\x55\x8b\x6c\x24\x0c\x83\x7d\x08\x00\x56\x57\x8b\xf1",14)&&
 flag_bytes(0x58b2a9,"\x8b\x45\x10\x83\x78\x08\x00\x0f\x95\xc0\x88\x07",12)&&
 flag_bytes(0x573b10,"\x83\xec\x10\x56\x57\x8b\xf9\x8d\x87\x60\x7d\x01\x00",13)&&
 flag_bytes(0x574c80,"\x51\x53\x55\x56\x57\x8b\xf9\x33\xed\x39\x6f\x08",12)&&
 flag_bytes(0x574d70,"\x53\x56\x57\x8b\xf9\x33\xdb\x39\x5f\x08",10)&&flag_bytes(0x4cc910,"\x8b\x44\x24\x04",4);
}
typedef void (__attribute__((thiscall))*StringCtor)(void*,const char*);
typedef void* (__attribute__((thiscall))*FlagGet)(void*,uint32_t);
typedef void (__attribute__((thiscall))*ActionInit)(void*,uint32_t);
typedef void (__attribute__((thiscall))*ActionDestroy)(void*);
typedef void (__attribute__((thiscall))*FlagSet)(void*,void*,uint32_t);
static uint32_t flag_deadline;
static uint64_t flag_deadline_ms;
static uint32_t get_flag(unsigned i){
 uint32_t name=0;((StringCtor)0x4cc910)(&name,FLAG_NAMES[i]);
 void* value=((FlagGet)0x573b10)((void*)(uintptr_t)binding.engine,name);
 if(!value)return 2;BYTE out=0;if(!read((uintptr_t)value,&out,1)||out>1)return 3;return out;
}
static bool read_mask(uint32_t& mask){
 mask=0;if(!guard(NULL,binding)||!flag_signatures())return false;
 for(unsigned i=0;i<10;i++){uint32_t value=get_flag(i);if(value==3)return false;if(value==1)mask|=1u<<i;}return true;
}
// Outcome unknown on ANY failed return/read. Caller never retries this write.
static bool set_flag(unsigned i,bool wanted,bool restoring){
 if(i>=10||!guard(NULL,binding)||!flag_signatures())return false;
 uint32_t metadata=binding.engine+0x48+0x80;char name[9]={};
 if(word(metadata+0x48)!=2||word(metadata+0x4c)!=5||word(metadata+0x50)!=8||!read(word(metadata+0xc),name,9)||memcmp(name,"SET_FLAG",9))return false;
 alignas(4) BYTE action[0x48]={};*(uint32_t*)action=0xbef87c;action[0x41]=1;
 ((ActionInit)0x574c80)(action,1);
 uint32_t count=*(uint32_t*)(action+8),first=*(uint32_t*)(action+0xc),second=*(uint32_t*)(action+0x10);
 bool valid=count==2&&first&&second&&word(first)==5&&word(second)==8;
 if(valid){
  ((StringCtor)0x4cc910)((void*)(uintptr_t)(first+0x10),FLAG_NAMES[i]);
  *(uint32_t*)(uintptr_t)(second+8)=wanted?1:0;
  valid=guard(NULL,binding)&&flag_signatures();
  // Sample the clock after the final potentially slow input guard.
  if(valid&&!restoring&&flag_deadline&&(word(binding.game+0x50)>=flag_deadline||GetTickCount64()>=flag_deadline_ms))valid=false;
  if(valid){p->flag_attempted++;((FlagSet)0x58b240)((void*)(uintptr_t)binding.engine,action,0);}
 }
 ((ActionDestroy)0x574d70)(action);return valid&&get_flag(i)==(uint32_t)wanted;
}

