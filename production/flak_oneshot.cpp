#include "oneshot_shared.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
static OneState* s;static HANDLE mapping;static HMODULE pin;
static bool read(uint32_t p,void* out,SIZE_T n){SIZE_T got=0;return ReadProcessMemory(GetCurrentProcess(),(void*)(uintptr_t)p,out,n,&got)&&got==n;}
static uint32_t word(uint32_t p){uint32_t v=0;read(p,&v,4);return v;}
static bool sig(uint32_t p,const BYTE* expected,SIZE_T n){BYTE b[32];return n<=sizeof(b)&&read(p,b,n)&&!memcmp(b,expected,n);}
static int cash(){uint32_t begin=word(s->owner+0xe4),end=word(s->owner+0xe8);if(!begin||end-begin<4||end-begin>64)return -1;uint32_t r=word(begin);return (int)word(r+4)+(int)word(r+0x14);}
static bool allowed(uint32_t h){return h==0x19ab11af||h==0x2c358c61||h==0x33026fa1||h==0xa08aabd3;}
static bool validate_prior_queue(){
 if(s->queue_limit>2||!!s->head_before!=!!s->tail_before)return false;
 uint32_t n=s->head_before,previous=0;
 while(n){uint32_t i=s->prior_count;if(i>=s->queue_limit||n%4||word(n+4)!=s->iface-0x24||word(n+0xc)!=1||word(n+0x58)!=previous)return false;
  uint32_t id=word(n+0x18),tmpl=word(n+0x10);if(!id||!allowed(word(tmpl+8))||(i&&s->prior_ids[0]==id))return false;
  s->prior_nodes[i]=n;s->prior_ids[i]=id;s->prior_templates[i]=tmpl;s->prior_costs[i]=word(n+0x30);s->prior_paid[i]=word(n+0x68);if(!s->prior_costs[i]||s->prior_paid[i]>s->prior_costs[i])return false;s->prior_count++;previous=n;n=word(n+0x54);
 }
 return previous==s->tail_before;
}
static bool prior_queue_preserved(){
 if(s->tail_after!=s->node||s->head_after!=(s->prior_count?s->head_before:s->node)||word(s->node+0x54)||word(s->node+0x58)!=s->tail_before||word(s->node+4)!=s->iface-0x24||word(s->node+0x68))return false;
 for(uint32_t i=0;i<s->prior_count;i++){uint32_t n=s->prior_nodes[i],previous=i?s->prior_nodes[i-1]:0,next=i+1<s->prior_count?s->prior_nodes[i+1]:s->node;
  if(n==s->node||s->prior_ids[i]==s->queue_id||word(n+4)!=s->iface-0x24||word(n+0xc)!=1||word(n+0x18)!=s->prior_ids[i]||word(n+0x10)!=s->prior_templates[i]||word(n+0x30)!=s->prior_costs[i]||word(n+0x68)!=s->prior_paid[i]||word(n+0x54)!=next||word(n+0x58)!=previous)return false;
 }
 return true;
}
static void execute(){
 s->callback_thread=GetCurrentThreadId();
 if(GetCurrentProcessId()!=s->pid||s->callback_thread!=s->thread||GetTickCount()-s->requested_tick>10000){s->error=1;return;}
 FILETIME a,b,c,d;if(!GetProcessTimes(GetCurrentProcess(),&a,&b,&c,&d)||a.dwLowDateTime!=s->start_low||a.dwHighDateTime!=s->start_high){s->error=2;return;}
 if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCSTR)(uintptr_t)&execute,&pin)){s->error=3;return;}
 const BYTE build[]={0x81,0xec,0xa8,0,0,0,0x53,0x8b,0xd9,0x8b,0x43,0xdc,0x8b,0x50,0x58,0x55,0x8d,0x6b,0xdc};
 const BYTE find[]={0x83,0xec,8,0x56,0x8d,0x71,0x28,0x8d,0x44,0x24,0x10,0x50,0x8d,0x4c,0x24,8,0x51,0x8b,0xce,0xe8};
 if((uintptr_t)GetModuleHandleW(NULL)!=0x400000||!sig(0x723f50,build,sizeof(build))||!sig(0x7e4230,find,sizeof(find))){s->error=4;return;}
 if(word(s->owner)!=0xc5bce0||word(s->owner+0x20)!=3||word(s->owner+0x90)!=s->ai||word(s->ai)!=0xc60f60){s->error=5;return;}
 if(word(s->factory)!=0xc4db60||word(s->factory+0x418)!=s->owner||word(word(s->factory+4)+8)!=0x80d4ea1e){s->error=6;return;}
 if(!read(word(s->factory+0x33c)+4,&s->hp,4)||!isfinite(s->hp)||s->hp<=0||!word(s->factory+0x310)||!word(s->factory+0x3c0)){s->error=7;return;}
 if(word(word(s->factory+0x3b4)+0x14)!=s->iface||word(s->iface)!=0xc3f8c8||word(0xc3f8c8+0x24)!=0x723f50||word(s->iface-0x1c)!=s->factory){s->error=8;return;}
 s->head_before=word(s->iface+0x10);s->tail_before=word(s->iface+0x14);s->cash_before=cash();if(!validate_prior_queue()||s->cash_before<220){s->error=9;return;}
 uint32_t store=word(0xce6c58);if(store<0x10000){s->error=10;return;}
 typedef void* (__attribute__((thiscall))*FindFn)(void*,uint32_t);
 s->template_pointer=(uintptr_t)((FindFn)0x7e4230)((void*)(uintptr_t)store,0x2c358c61);
 if(!s->template_pointer||word(s->template_pointer+8)!=0x2c358c61){s->error=11;return;}
 typedef uint32_t (__attribute__((thiscall))*BuildFn)(void*,void*,uint32_t,void*,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t);
 // Exactly the natural UNIT_BUILD sample: one unit, native sentinel, five zeros.
 s->queue_id=((BuildFn)0x723f50)((void*)(uintptr_t)s->iface,(void*)(uintptr_t)s->template_pointer,0,(void*)0xcd7e84,0,0,0,0,0);
 s->head_after=word(s->iface+0x10);s->tail_after=word(s->iface+0x14);s->cash_after=cash();
 uint32_t node=s->head_after;for(int i=0;node&&i<64;i++){if(word(node+0xc)==1&&word(node+0x10)==s->template_pointer&&word(node+0x18)==s->queue_id){s->node=node;s->cost=word(node+0x30);break;}uint32_t next=word(node+0x54);if(next==node)break;node=next;}
 if(!s->queue_id||!s->node){s->error=12;return;}
 s->initial_paid=word(s->node+0x68);s->queue_preserved=prior_queue_preserved();if(!s->queue_preserved){s->error=13;return;}
}
extern "C" __declspec(dllexport) LRESULT CALLBACK FlakOneShotControl(int code,WPARAM wp,LPARAM lp){
 if(code>=0&&wp==PM_REMOVE&&lp&&((MSG*)lp)->message==ONE_MESSAGE&&((MSG*)lp)->wParam==ONE_MAGIC){
  if(!s){char name[80];snprintf(name,sizeof(name),"Local\\RA3FlakOneShot_%lu",GetCurrentProcessId());mapping=OpenFileMappingA(FILE_MAP_ALL_ACCESS,FALSE,name);if(mapping)s=(OneState*)MapViewOfFile(mapping,FILE_MAP_ALL_ACCESS,0,0,sizeof(OneState));}
  if(s&&s->magic==ONE_MAGIC&&InterlockedCompareExchange(&s->claimed,1,0)==0){execute();InterlockedExchange(&s->state,s->error?3:2);}
 }
 return CallNextHookEx(NULL,code,wp,lp);
}
BOOL WINAPI DllMain(HINSTANCE h,DWORD reason,LPVOID){if(reason==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(h);return TRUE;}
