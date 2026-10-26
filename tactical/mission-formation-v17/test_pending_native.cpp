// Actual pending.cpp.inc functions; only engine memory/callees/caller sampling
// are fakes. No process access, hooks, SDK, or game functions are invoked.
#include "shared.h"
#include <map>
#include <vector>
#include <cstring>
#include <cmath>
#include <cstdio>
#include <cstdlib>
using std::isfinite;
static float frozen_origins[2][3];
static Tactical* p=new Tactical;static uint32_t now=100,tag,frozen_deadline=4500,caller,checks,private_calls;
static float frozen_goals[2][3];static MoveLineage lineage_record;
static uint32_t live_command[23],decoded_command[23];static std::map<uint32_t,BYTE> mem;static std::vector<Event> events;
static uint32_t frame(){return now;}
static bool role_leased(bool r){return p->issued_frame&&(r?p->support.detach_calls&&!p->support.returned:p->detach_calls&&!p->return_verified);}
static bool read(uint32_t a,void* out,SIZE_T n){for(auto buffer:{live_command,decoded_command}){uint32_t start=(uintptr_t)buffer;if(a>=start&&a+n<=start+sizeof(live_command)){memcpy(out,(void*)(uintptr_t)a,n);return true;}}for(unsigned i=0;i<n;i++){if(!mem.count(a+i))return false;((BYTE*)out)[i]=mem[a+i];}return true;}
template<class T>static void put(uint32_t a,const T& v){for(unsigned i=0;i<sizeof(v);i++)mem[a+i]=((const BYTE*)&v)[i];}
static uint32_t word(uint32_t a){uint32_t x=0;read(a,&x,4);return x;}
static uint32_t event(uint32_t kind,uint32_t arg=0,uint32_t ec=0,float=0,float=0,float=0,uint32_t role=0,const float* input=NULL,uint32_t path=0,float limit=0,const uint32_t* diagnostic=NULL){Event e={};e.seq=++p->count;e.kind=kind;e.arg=arg;e.caller=ec;e.role=role;e.tag=tag;e.frame=now;e.lineage=lineage_record;e.thread=p->thread;e.owner=p->owner;e.unit_id=role?p->support.id:p->object_id;e.source=1;e.mission_stage=p->mission_stage;e.mission_deadline_frame=frozen_deadline;memcpy(e.command_xyz,frozen_goals[role],12);if(kind==10||kind==11){uint32_t maximum=0x7f7fffff;memcpy(&e.argument_limit,&maximum,4);}if(diagnostic){e.stack_word_count=80;memcpy(e.stack_words,diagnostic,80*4);}events.push_back(e);return e.seq;}
#define LINEAGE_OBSERVED_CALLER ::caller
static bool fake_stance_scope;static uint32_t fake_stance_role;
static bool expected_stance_stop(uint32_t r,uint32_t source){return fake_stance_scope&&r==fake_stance_role&&source==2;}
#include "pending.cpp.inc"
static bool replay_private=true,repeat_defer=false;static uint32_t active_observation;
static void __attribute__((thiscall)) fake_copy(void* self,void* input){active_observation=p->active;uint32_t c[23]={},s[24]={};read((uintptr_t)input,c,sizeof(c));memcpy(s,c,24);memcpy(s+16,c+15,16);s[22]=c[21];((BYTE*)s)[0x5c]=((BYTE*)c)[0x58];for(unsigned i=0;i<24;i++)put((uintptr_t)self+4*i,s[i]);}
static bool __attribute__((thiscall)) fake_unpack(void* self,void*,void* output){active_observation=p->active;uint32_t s[24]={},c[23]={};read((uintptr_t)self,s,sizeof(s));memcpy(c,s,24);memcpy(c+15,s+16,16);c[21]=s[22];((BYTE*)c)[0x58]=((BYTE*)s)[0x5c];memcpy(output,c,sizeof(c));return true;}
static void __attribute__((thiscall)) fake_dispatch(void*,void* command){
 active_observation=p->active;
 if(tag==6||repeat_defer){uint32_t prior=caller;caller=0x787d42;stored_copy_hook((void*)(uintptr_t)(p->support.update+0x310),NULL,command);caller=prior;return;}
 if(!replay_private)return;float maximum;uint32_t bits=0x7f7fffff;memcpy(&maximum,&bits,4);
 if(authorize_private_move(1,(float*)((BYTE*)command+8),0,maximum,1,0x6d3b7d)){private_calls++;event(10,1,0x6d3b7d,0,0,0,1);move_tickets[1].proof.private_seq=p->count;move_tickets[1].proof.observed_this=p->support.update;move_tickets[1].proof.observed_thing=p->support.thing;move_tickets[1].proof.observed_command=(uintptr_t)command+8;lineage_emit(116,1);event(11,1,0,0,0,0,1);put(p->support.update+0x310,0xffffffffu);}
}
static void need(bool b,const char* label){checks++;if(!b){fprintf(stderr,"case%u %s native%u/%u\n",checks,label,p->native_move,p->support.native_move);exit(1);}}
static unsigned count(uint32_t kind){unsigned n=0;for(auto& e:events)n+=e.kind==kind;return n;}
static void reset(){mem.clear();events.clear();memset(p,0,sizeof(*p));memset(move_tickets,0,sizeof(move_tickets));memset(move_generations,0,sizeof(move_generations));clear_move_context();memset(&lineage_record,0,sizeof(lineage_record));memset(live_command,0,sizeof(live_command));memset(decoded_command,0,sizeof(decoded_command));now=100;tag=0;caller=0;fake_stance_scope=false;fake_stance_role=0;private_calls=0;repeat_defer=false;replay_private=true;p->phase=1;p->thread=GetCurrentThreadId();p->owner=0x9000;p->unit=0x2000;p->update=0x6000;p->support.thing=0x3000;p->support.update=0x7000;p->issued_frame=1;p->detach_calls=p->support.detach_calls=1;p->mission_stage=1;frozen_goals[1][0]=300;frozen_goals[1][1]=400;frozen_goals[1][2]=210;
 for(unsigned r=0;r<2;r++){uint32_t t=r?p->support.thing:p->unit,u=r?p->support.update:p->update;put(t+0x418,p->owner);put(t+0x374,u);put(u+8,t);for(unsigned i=0;i<96;i++)mem[u+0x310+i]=0;put(u+0x310,0xffffffffu);}
 live_command[1]=1;memcpy(live_command+2,frozen_goals[1],12);((BYTE*)live_command)[0x58]=1;old_stored_copy=fake_copy;old_stored_unpack=fake_unpack;old_command_dispatch=fake_dispatch;
}
static void own_issue(){event(81,0,0,0,0,0,1);need(arm_move_ticket(1,81,p->count,frozen_goals[1]),"arm own immutable normal Move");tag=6;event(50,1,0,0,0,0,1);auto& t=move_tickets[1];t.facade_open=true;t.proof.own_facade_seq=p->count;t.proof.observed_this=p->support.update+0x24;t.proof.observed_command=(uintptr_t)(live_command+2);lineage_emit(110,1);command_dispatch_hook((void*)(uintptr_t)(p->support.update+0x24),NULL,live_command);event(51,1,0,0,0,0,1);t.facade_open=false;t.proof.observed_this=p->support.update+0x24;t.proof.observed_thing=0;t.proof.observed_command=(uintptr_t)(live_command+2);lineage_emit(119,1);tag=0;}
static void unpack(){caller=0x7da0b3;stored_unpack_hook((void*)(uintptr_t)(p->support.update+0x310),NULL,(void*)(uintptr_t)p->support.thing,decoded_command);}
static void dispatch(){caller=0x7da0d9;command_dispatch_hook((void*)(uintptr_t)(p->support.update+0x24),NULL,decoded_command);}
static void dump_positive(const char* path){
 FILE* f=fopen(path,"wb");if(!f)return;
 fprintf(f,"{\"provenance\":\"actual_pending_cpp_hooks_engine_and_caller_stub\",\"sdk_calls\":0,\"game_access\":false,\"native\":{\"mission_deadline_frame\":4500,\"native_move\":%u,\"support\":{\"native_move\":%u}},\"preflight\":{\"owner\":\"0x9000\",\"window_thread\":%u,\"selected\":{\"object_id\":0,\"address\":\"0x2000\",\"ai_address\":\"0x6000\"},\"support\":{\"object_id\":0,\"address\":\"0x3000\",\"ai_address\":\"0x7000\"}},\"events\":[",p->native_move,p->support.native_move,p->thread);
 for(unsigned i=0;i<events.size();i++){auto& e=events[i];auto& q=e.lineage;if(i)fputc(',',f);fprintf(f,"{\"seq\":%u,\"kind\":%u,\"arg\":%u,\"role\":%u,\"tag\":%u,\"frame\":%u,\"thread\":%u,\"owner\":%u,\"unit_id\":%u,\"source\":%u,\"caller\":%u,\"mission_stage\":%u,\"mission_deadline_frame\":%u,\"command_xyz\":[%.9g,%.9g,%.9g],\"argument_path\":0,\"argument_limit\":%.9g,\"lineage\":{",e.seq,e.kind,e.arg,e.role,e.tag,e.frame,e.thread,e.owner,e.unit_id,e.source,e.caller,e.mission_stage,e.mission_deadline_frame,e.command_xyz[0],e.command_xyz[1],e.command_xyz[2],e.argument_limit);
 #define U(name) fprintf(f,"\"" #name "\":%u,",q.name)
 U(generation);U(step);U(issued_frame);U(mission_stage);U(goal_kind);U(goal_event_seq);U(slot);U(input_command);U(output_command);U(copy_caller);U(unpack_caller);U(dispatch_caller);U(private_caller);U(delivered);U(role);U(invalid_reason);U(own_facade_seq);U(private_seq);U(observed_this);U(observed_thing);U(observed_command);
 #undef U
 fprintf(f,"\"goal\":[%.9g,%.9g,%.9g]",q.goal[0],q.goal[1],q.goal[2]);
 #define A(name) fputs(",\"" #name "\":[",f);for(unsigned j=0;j<sizeof(q.name)/4;j++){if(j)fputc(',',f);fprintf(f,"%u",q.name[j]);}fputc(']',f)
 A(command);A(stored_before);A(stored_after);A(unpacked);A(observed_slot);
 #undef A
 fprintf(f,"},\"stack_word_count\":%u,\"stack_words\":[",e.stack_word_count);for(unsigned j=0;j<e.stack_word_count;j++)fprintf(f,"%s%u",j?",":"",e.stack_words[j]);fputs("]}",f);
 }fputs("]}",f);fclose(f);
}
int main(int argc,char** argv){
 reset();own_issue();need(count(111)==1&&count(112)==1&&move_tickets[1].pending&&!p->support.native_move,"actual copy establishes one pending generation");now+=148;unpack();need(count(113)==1&&count(114)==1&&move_tickets[1].unpack_ready,"actual stored command decodes same owned Thing");dispatch();need(private_calls==1&&count(115)==1&&count(116)==1&&count(117)==1&&!p->support.native_move,"148frame consumer dispatch privately delivered once");need(move_tickets[1].proof.delivered==1&&!move_tickets[1].armed,"credit consumed and closed");if(argc>=2)dump_positive(argv[1]);dispatch();need(private_calls==1&&p->support.native_move>0,"duplicate consumer rejected");
 reset();own_issue();now+=251;unpack();need(!move_tickets[1].unpack_ready&&p->support.native_move>0,"older than existing250 watchdog rejected");
 reset();own_issue();put(p->support.update+0x318,999.f);unpack();need(!move_tickets[1].unpack_ready&&p->support.native_move>0,"external pending slot overwrite rejected");
 reset();own_issue();caller=0x7da0b3;stored_unpack_hook((void*)(uintptr_t)(p->support.update+0x310),NULL,(void*)(uintptr_t)p->unit,decoded_command);need(p->support.native_move>0&&!move_tickets[1].unpack_ready,"wrong consumer Thing rejected");
 reset();own_issue();caller=0x7da0b4;stored_unpack_hook((void*)(uintptr_t)(p->support.update+0x310),NULL,(void*)(uintptr_t)p->support.thing,decoded_command);need(p->support.native_move>0,"wrong unpack callsite rejected");
 reset();own_issue();unpack();decoded_command[1]=0;dispatch();need(private_calls==0&&p->support.native_move>0,"source0 rejected despite same goal/caller");
 reset();own_issue();unpack();((float*)(decoded_command+2))[0]+=1;dispatch();need(private_calls==0&&p->support.native_move>0,"changed goal rejected");
 reset();own_issue();unpack();caller=0x7da0d8;command_dispatch_hook((void*)(uintptr_t)(p->support.update+0x24),NULL,decoded_command);need(private_calls==0&&p->support.native_move>0,"wrong dispatcher caller rejected");
 reset();own_issue();unpack();replay_private=false;dispatch();need(p->support.native_move>0&&!move_tickets[1].armed,"consumer with no private cannot leave reusable credit");
 reset();own_issue();unpack();repeat_defer=true;dispatch();need(private_calls==0&&p->support.native_move>0&&!move_tickets[1].pending,"re-defer is not automatically authorized");
 reset();own_issue();invalidate_move_ticket(0,1);need(move_tickets[1].pending,"another role Stop does not cancel rear pending Move");now+=148;unpack();dispatch();need(private_calls==1&&!p->support.native_move,"rear continuation remains valid across leader-only Stop");
 reset();own_issue();invalidate_move_ticket(1,1);tag=4;live_command[0]=5;caller=0x787d42;stored_copy_hook((void*)(uintptr_t)(p->support.update+0x310),NULL,live_command);tag=0;need(!p->support.native_move&&!move_tickets[1].pending,"own Stop may replace stored opcode without being a foreign Move");
 for(uint32_t reason=1;reason<=5;reason++){reset();own_issue();invalidate_move_ticket(1,reason);unpack();dispatch();need(private_calls==0&&p->support.native_move>0,"Stop Attack newFacade Return owner invalidation prevents late private");}
 reset();put(p->support.update+0x310,0u);own_issue();need(p->support.native_move>0&&!move_tickets[1].pending,"old occupied pending slot gives no credit");
 reset();own_issue();unpack();set_move_context(1,move_tickets[1].proof.generation,(uint32_t)(uintptr_t)decoded_command,2);move_tickets[1].consumer_open=true;move_tickets[1].unpack_ready=false;float maximum;uint32_t maximum_bits=0x7f7fffff;memcpy(&maximum,&maximum_bits,4);float same_xyz[3];memcpy(same_xyz,frozen_goals[1],12);need(!authorize_private_move(1,same_xyz,0,maximum,1,0x6d3b7d),"same XYZ from a different pointer cannot replace decoded command+8");
 need(!authorize_private_move(1,(float*)(decoded_command+2),1,maximum,1,0x6d3b7d),"nonzero native path rejected");need(!authorize_private_move(1,(float*)(decoded_command+2),0,1.f,1,0x6d3b7d),"non-FLTMAX move rejected");
 reset();stored_copy_hook((void*)0x8000,NULL,live_command);need(active_observation>0&&p->active==0,"untracked copy callback participates in active lifetime");stored_unpack_hook((void*)0x8000,NULL,(void*)0x3000,decoded_command);need(active_observation>0&&p->active==0,"untracked unpack callback participates in active lifetime");replay_private=false;command_dispatch_hook((void*)0x8000,NULL,live_command);need(active_observation>0&&p->active==0,"untracked dispatcher callback participates in active lifetime");
 reset();tag=0;replay_private=false;live_command[0]=42;live_command[1]=1;move_tickets[0].proof.delivered=1;move_tickets[0].proof.generation=1;caller=0x12345678;command_dispatch_hook((void*)(uintptr_t)(p->update+0x24),NULL,live_command);
 need(p->native_move==1&&private_calls==0,"diagnostics preserve original closed-ticket classification and SDK count");
 need(count(124)==1&&count(125)==1&&count(118)==0,"closed ticket still publishes actual dispatcher and counter record");
 Event pre={},post={};for(auto&e:events){if(e.kind==124)pre=e;if(e.kind==125)post=e;}
 need(pre.stack_words[28]==42&&pre.stack_words[29]==1&&pre.stack_words[7]==(uintptr_t)live_command&&pre.stack_words[8]==0x12345678,"actual raw command and input caller not inferred from goal");
 need(post.stack_words[2]==5&&post.stack_words[3]==pre.seq&&post.stack_words[10]==0&&post.stack_words[11]==1,"counter delta and exact pre publication link");if(argc>=3)dump_positive(argv[2]);
 for(uint32_t cause=1;cause<=7;cause++){reset();ticket_foreign(0,cause);need(p->native_move==1&&count(125)==1&&events.back().stack_words[2]==cause&&events.back().stack_words[10]==0&&events.back().stack_words[11]==1,"every counter source logs its distinct cause without an open ticket");}
 for(uint32_t r=0;r<2;r++)for(uint32_t st:{7u,8u}){for(uint32_t failure=0;failure<3;failure++){reset();tag=st;replay_private=false;fake_stance_role=r;fake_stance_scope=failure!=2;live_command[0]=failure==0?42:5;live_command[1]=failure==1?0:2;command_dispatch_hook((void*)(uintptr_t)((r?p->support.update:p->update)+0x24),NULL,live_command);need((r?p->support.native_move:p->native_move)==1&&events.back().stack_words[2]==5,"new setter tags never exempt unknown opcode Source0 or absent private scope");}reset();tag=st;replay_private=false;fake_stance_role=r;fake_stance_scope=true;live_command[0]=5;live_command[1]=2;command_dispatch_hook((void*)(uintptr_t)((r?p->support.update:p->update)+0x24),NULL,live_command);need(!p->native_move&&!p->support.native_move&&events.back().stack_words[12]==4,"only bound own setter opcode5 Source2 Stop is legal passthrough");}

 reset();p->mission_stage=3;memcpy(frozen_origins[1],frozen_goals[1],12);need(arm_move_ticket(1,168,1,frozen_origins[1]),"new parallel home kind168 has exact private origin in stage3");float wrongHome[3];memcpy(wrongHome,frozen_origins[1],12);wrongHome[0]+=1;need(!arm_move_ticket(1,168,1,wrongHome),"same role cannot substitute different home for168");need(!arm_move_ticket(1,168,1,NULL),"parallel home nullgoal rejects before raw comparison");need(!arm_move_ticket(2,168,1,frozen_origins[1]),"parallel home role outside bound pair rejects");p->mission_stage=1;need(!arm_move_ticket(1,168,1,frozen_origins[1]),"approach cannot borrow parallel-home allowance");
 printf("{\"passed\":true,\"cases\":%u,\"scope\":\"actual_pending_hooks_engine_memory_callers_and_callees_stubbed\",\"sdk_calls\":0,\"game_access\":false}\n",checks);
}
