// Actual native and host scheduling helpers. Engine body/time/message delivery
// are controlled fakes; no process is opened and no SDK function is called.
#include "shared.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
static Tactical* p=new Tactical;static uint32_t wall=1000,logical=100,thread_id=7,checks,body_calls,body_active;
static bool is_paused,post_ok=true,nested;static unsigned posts;static uint32_t posted_token,posted_nonce;
static uint32_t frozen_deadline=4500,schedule_proof[24];static std::vector<Event> events;
static DWORD fake_tick(){return wall;}static DWORD fake_thread(){return thread_id;}
static BOOL fake_post(HWND,UINT message,WPARAM token,LPARAM nonce){posts++;posted_token=token;posted_nonce=nonce;return post_ok&&message==T_PULSE_MESSAGE;}
#define GetTickCount fake_tick
#define GetCurrentThreadId fake_thread
#define PostMessageA fake_post
static uint32_t frame(){return logical;}static bool paused(){return is_paused;}
static void schedule_pulse(uint32_t,uint32_t);static void CALLBACK tick(HWND,UINT,UINT_PTR,DWORD);
static void event(uint32_t kind,uint32_t arg){Event e={};e.seq=events.size()+1;e.kind=kind;e.arg=arg;e.frame=logical;e.tick=wall;e.thread=thread_id;if(kind>=121&&kind<=123){e.stack_word_count=24;memcpy(e.stack_words,schedule_proof,sizeof(schedule_proof));}events.push_back(e);}
static void mission_tick_body(){body_calls++;body_active=p->active;p->stable_samples++;if(nested){nested=false;schedule_pulse(p->token,p->pulse_requested);tick(NULL,0,0,0);}if(p->stop_requested)p->phase=7;}
#include "scheduler.cpp.inc"
#include "host_pulse.cpp.inc"
static void need(bool yes,const char* text){checks++;if(!yes){fprintf(stderr,"case%u: %s\n",checks,text);exit(1);}}
static void reset(uint32_t time=1000){memset(p,0,sizeof(*p));wall=time;logical=100;thread_id=7;is_paused=false;post_ok=true;nested=false;posts=0;body_calls=body_active=0;events.clear();p->magic=T_MAGIC;p->version=17;p->pid=12;p->thread=p->callback_thread=7;p->token=88;p->seq=99;p->command[0]=11;p->task[0]=22;p->mission_deadline_frame=4500;p->phase=5;schedule_reset();}
static void pulse(uint32_t nonce){p->pulse_requested=nonce;schedule_pulse(p->token,nonce);}
static HostPulse host(){HostPulse h={};h.last_post_tick=wall-100;return h;}
static void host_step(HostPulse& h){uint32_t c[4]={11},t[4]={22};host_pulse_step(p,NULL,88,99,c,t,h);}
static void uuid_text(FILE* f,const uint32_t words[4]){const BYTE* bytes=(const BYTE*)words;for(unsigned i=0;i<16;i++){if(i==4||i==6||i==8||i==10)fputc('-',f);fprintf(f,"%02x",bytes[i]);}}
int main(int argc,char** argv){
 need(sizeof(Event)==1616&&sizeof(MoveLineage)==568&&offsetof(Tactical,events)==31148&&sizeof(Tactical)==13269420,"actual new ABI and unchanged Event");
 need(offsetof(Tactical,phase)==260&&offsetof(Tactical,pulse_requested)==27900&&offsetof(Tactical,pulse_acknowledged)==27904,"prefix and two exact trailing words");
 reset();schedule_advance(1);need(body_calls==1&&body_active==1&&p->active==0&&events.size()==1&&events[0].kind==121,"immediate old body once with callback lifetime");
 need(events[0].stack_words[15]==0xffffffffu&&events[0].stack_words[20]==1&&events[0].stack_words[21]==4500,"actual first proof before frozen original deadline");
 pulse(1000);need(p->pulse_acknowledged==1000&&body_calls==1,"same-frame pulse consumed without second progression");
 wall=1100;logical=101;pulse(1100);need(body_calls==2&&events.back().kind==122&&events.back().stack_words[22]==2,"normal fresh pulse drives next actual frame");
 wall=1200;logical=102;tick(NULL,0,0,0);need(body_calls==2,"timer suppressed through100ms");
 wall=1201;tick(NULL,0,0,0);need(body_calls==3&&events.back().kind==123&&!p->stop_requested,"host gap101ms original timer fallback");
 tick(NULL,0,0,0);need(body_calls==3,"fallback no double same frame");
 wall=1500;logical=103;pulse(1500);need(body_calls==4&&events.back().kind==122,"fresh host resumes within1000ms");
 reset();p->pulse_requested=wall;schedule_pulse(89,wall);need(!p->pulse_acknowledged&&!body_calls,"wrong token no acknowledgement or SDK body");
 schedule_pulse(88,wall+1);need(!p->pulse_acknowledged&&!body_calls,"header/message nonce mismatch rejected");
 pulse(1000);logical++;schedule_pulse(88,1000);need(body_calls==1&&p->pulse_acknowledged==1000,"duplicate delivery rejected");
 p->pulse_requested=999;schedule_pulse(88,999);need(body_calls==1&&p->pulse_acknowledged==1000,"old nonce rejected independently of source1");
 reset();pulse(0);need(!body_calls&&!p->pulse_acknowledged,"zero reserved");
 wall=2001;pulse(1000);need(!body_calls&&!p->pulse_acknowledged,"expired message rejected after1000ms");
 reset();pulse(1001);need(!body_calls&&!p->pulse_acknowledged,"future timestamp rejected");
 reset(0xfffffff0u);pulse(0xfffffff0u);wall=0x54;logical++;pulse(0x54);need(body_calls==2&&p->pulse_acknowledged==0x54,"wall clock nonce wraps signed modular forward");
 p->pulse_requested=0xfffffff0u;schedule_pulse(88,0xfffffff0u);need(body_calls==2&&p->pulse_acknowledged==0x54,"prewrap replay rejected");
 reset();p->seq++;pulse(wall);need(!body_calls&&!p->pulse_acknowledged,"command seq mutation cannot consume pulse");
 tick(NULL,0,0,0);need(p->stop_requested&&p->phase==7,"binding mutation only invokes original cleanup through fallback");
 reset();p->command[0]++;pulse(wall);need(!body_calls,"command UUID mutation rejects");
 reset();p->task[0]++;pulse(wall);need(!body_calls,"task UUID mutation rejects");
 reset();is_paused=true;schedule_advance(1);pulse(wall);need(!body_calls&&events.empty()&&p->pulse_acknowledged==wall,"paused messages consumed without fake samples");
 is_paused=false;wall+=100;pulse(wall);need(body_calls==1&&events[0].kind==122&&events[0].stack_words[15]==0xffffffffu,"first unpaused frame real progression");
 wall+=100;pulse(wall);wall+=100;pulse(wall);need(p->stable_samples==1,"three pulses same logical frame cannot forge Stop3");
 reset();p->pulse_requested=wall;nested=true;schedule_advance(1);need(body_calls==1&&p->active==0&&p->pulse_acknowledged==wall,"nested message may consume but cannot reenter body");
 reset();p->phase=3;pulse(wall);tick(NULL,0,0,0);schedule_advance(1);need(!body_calls&&!p->pulse_acknowledged,"success terminal no new SDK or ack");
 p->phase=4;pulse(wall);need(!body_calls&&!p->pulse_acknowledged,"failure terminal inert");
 reset();thread_id=8;pulse(wall);tick(NULL,0,0,0);need(!body_calls&&!p->pulse_acknowledged,"wrong thread inert");
 reset();pulse(wall);logical++;wall=2001;tick(NULL,0,0,0);need(p->stop_requested&&p->phase==7,"lost host1001ms requests original cleanup despite fresh Python heartbeat");
 wall=2100;logical++;pulse(wall);need(p->stop_requested&&p->phase==7,"late recovery never clears latched stop");
 reset();wall=2001;logical++;tick(NULL,0,0,0);need(p->stop_requested&&p->phase==7,"host never posts after install still stops at1001ms");
 reset();is_paused=true;wall=2001;tick(NULL,0,0,0);need(p->stop_requested&&!body_calls,"paused host loss records stop without SDK");
 reset();HostPulse h=host();host_step(h);need(posts==1&&h.pending&&p->pulse_requested==1000&&posted_token==88,"host first pulse exact window message/token/clocknonce");
 wall=1100;host_step(h);need(posts==1,"maximum one outstanding");
 p->pulse_acknowledged=1000;host_step(h);need(posts==2&&h.pending&&p->pulse_requested==1100,"ack consumed then next period sends once");
 reset();h=host();post_ok=false;host_step(h);wall+=200;host_step(h);need(posts==1&&h.stopped&&p->stop_requested,"PostMessage failure immediately stops and never reposts");
 reset();h=host();host_step(h);wall+=1001;host_step(h);wall+=100;host_step(h);need(posts==1&&h.stopped&&p->stop_requested,"unacknowledged timeout permanently stops sender");
 reset();h=host();p->seq++;host_step(h);need(!posts&&h.stopped&&p->stop_requested,"host binds command seq");
 reset();h=host();p->command[0]++;host_step(h);need(!posts&&h.stopped,"host binds UUID");
 reset();h=host();p->phase=3;host_step(h);p->phase=4;host_step(h);need(!posts&&!p->stop_requested,"host does not emit after either terminal");
 reset(0);h=host();host_step(h);need(!posts,"host skips clock nonce zero");
 reset(0xfffffff0u);pulse(wall);h=host();h.last_post_tick=wall;h.count=1;wall=0x54;logical++;host_step(h);schedule_pulse(88,posted_nonce);need(posts==1&&p->pulse_acknowledged==0x54&&body_calls==2,"actual host and native helpers both cross clock wrap");
 reset();p->pulse_requested=wall;schedule_advance(1);need(events[0].kind==121&&events[0].stack_words[12]==1000&&!events[0].stack_words[13]&&!events[0].stack_words[22],"first inline may observe one posted but unconsumed nonce");
 reset();h=host();h.count=T_PULSE_MAX_POSTS;host_step(h);need(!posts&&h.stopped&&p->stop_requested,"transport total bounded below20001");
 // Exact software trace for independent qualifier protocol review, not field.
 reset();event(0,0);schedule_advance(1);wall=1100;logical=101;pulse(wall);wall=1500;logical=102;tick(NULL,0,0,0);
 if(argc>1){FILE* f=fopen(argv[1],"wb");if(!f)return 2;fprintf(f,"{\"provenance\":\"actual_cpp_scheduler_with_fake_engine_clock_transport\",\"field_verified\":false,\"sdk_calls\":0,\"request\":{\"command_id\":\"");uuid_text(f,p->command);fputs("\",\"task_id\":\"",f);uuid_text(f,p->task);fprintf(f,"\",\"seq\":%u,\"token\":%u,\"expires_frame\":%u},\"preflight\":{\"window_thread\":%u},\"native\":{\"callback_thread\":%u,\"mission_deadline_frame\":%u,\"pulse_requested\":%u,\"pulse_acknowledged\":%u,\"paused_samples\":%u},\"events\":[",p->seq,p->token,p->mission_deadline_frame,p->thread,p->callback_thread,p->mission_deadline_frame,p->pulse_requested,p->pulse_acknowledged,p->paused_samples);for(unsigned i=0;i<events.size();i++){auto&e=events[i];if(i)fputc(',',f);fprintf(f,"{\"seq\":%u,\"kind\":%u,\"arg\":%u,\"frame\":%u,\"tick\":%u,\"thread\":%u,\"stack_word_count\":%u,\"stack_words\":[",e.seq,e.kind,e.arg,e.frame,e.tick,e.thread,e.stack_word_count);for(unsigned j=0;j<e.stack_word_count;j++)fprintf(f,"%s%u",j?",":"",e.stack_words[j]);fputs("]}",f);}fputs("]}",f);fclose(f);}
 printf("{\"actual_scheduler_cases\":%u,\"game_access\":false,\"sdk_calls\":0}\n",checks);return 0;
}
