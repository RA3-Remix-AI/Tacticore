#include "shared.h"
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
static Probe storage,*p=&storage,frozen;static uint32_t now,logical,last_advance,last_pulse,install_tick,calls,thread;static bool has_pulse,busy,paused,reenter;static unsigned passed;
static uint32_t fake_tick(){return now;}
static uint32_t fake_thread(){return thread;}
#define GetTickCount fake_tick
#define GetCurrentThreadId fake_thread
static uint32_t frame(){return logical;}static uint32_t word(uint32_t){return paused;}
static void advance();static void probe_body(){calls++;if(reenter)advance();}
#include "scheduler.cpp.inc"
static void check(bool okay,const char* name){if(!okay){fprintf(stderr,"FAIL %s\n",name);exit(1);}passed++;}
static void reset(){memset(p,0,sizeof(*p));p->magic=T_MAGIC;p->version=4;p->pid=1;p->thread=thread=2;p->token=3;p->seq=4;p->command[0]=5;p->task[0]=6;p->phase=5;p->expires_frame=400;memcpy(&frozen,p,offsetof(Probe,phase));now=install_tick=100;logical=100;last_advance=0xffffffffu;last_pulse=calls=0;has_pulse=busy=paused=reenter=false;}
static void send(uint32_t nonce){p->pulse_requested=nonce;pulse(p->token,nonce);}
int main(){
 reset();advance();check(calls==1&&!p->active,"inline exact one advance");advance();check(calls==1,"same logical frame no duplicate SDK");logical++;advance();check(calls==2,"next actual frame advances");
 reset();paused=true;advance();check(!calls&&p->paused_samples==1,"paused inline no SDK");send(now);check(p->pulse_acknowledged==now&&!calls,"paused ack not progress");paused=false;advance();check(calls==1,"real unpause advances");
 reset();reenter=true;advance();check(calls==1&&!p->active&&!busy,"reentry and callback lifetime");
 reset();p->pulse_requested=100;pulse(999,100);check(!calls&&!p->pulse_acknowledged,"wrong token rejected");pulse(3,0);check(!calls,"zero rejected");now=200;pulse(3,201);check(!calls,"future rejected");now=1201;pulse(3,100);check(!calls,"expired rejected");
 reset();send(100);check(calls==1&&p->pulse_acknowledged==100,"current nonce accepted");logical++;now=110;send(100);check(calls==1,"duplicate nonce rejected");send(99);check(calls==1,"old nonce rejected");send(110);check(calls==2,"strict increasing nonce");
 reset();now=install_tick=0xfffffff0u;send(now);logical++;now=0x54;send(now);check(calls==2&&p->pulse_acknowledged==0x54,"mod32 wrap valid");
 reset();send(100);logical++;now=200;tick(NULL,0,0,now);check(calls==1,"fallback suppressed through100ms");now=201;tick(NULL,0,0,now);check(calls==2,"fallback after100ms actualframe");tick(NULL,0,0,now);check(calls==2,"fallback sameframe no duplicate");
 reset();logical++;now=1101;tick(NULL,0,0,now);check(p->stop_requested&&calls==1,"host lost1000ms latches stop");logical++;send(now);check(p->stop_requested&&calls==1,"late recovered pulse cannot clear stop or progress");
 reset();paused=true;now=1200;tick(NULL,0,0,now);check(p->stop_requested&&!calls,"paused hostloss no SDK");
 reset();p->phase=3;advance();send(100);tick(NULL,0,0,100);check(!calls,"terminal no SDK");
 reset();thread=7;advance();send(100);check(!calls,"wrong thread no advance");
 reset();p->command[0]=999;advance();check(p->command[0]==5&&p->stop_requested&&p->error==48&&calls==1,"binding mismatch restores private original and only cleanup path");
 reset();p->production_command[0]=999;advance();check(p->production_command[0]==0&&p->stop_requested&&p->error==48&&calls==1,"provenance mutation restored then cleanup only");
 printf("{\"scope\":\"pure_actual_scheduler\",\"tests\":%u,\"passed\":true,\"field_verified\":false}\n",passed);return 0;
}
