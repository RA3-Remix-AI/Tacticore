// Passive, single-delivery lineage of the native stored normal-Move command.
#ifndef LINEAGE_OBSERVED_CALLER
#define LINEAGE_OBSERVED_CALLER ((uint32_t)(uintptr_t)__builtin_return_address(0))
#endif
struct MoveTicket {MoveLineage proof;bool armed,pending,unpack_ready,facade_open,consumer_open,dispatch_seen;};
static MoveTicket move_tickets[2];static uint32_t move_generations[2];
struct MoveDispatchContext {uint32_t role,generation,command,kind;};
// Windows may allocate an injected MinGW TLS block at an eight-byte address.
// Keep true thread-local/reentrant state, but never give the compiler an
// aggregate TLS load/store that it can turn into aligned MOVAPS/MOVDQA.
static __thread volatile uint32_t move_context_words[4]={};
static __attribute__((noinline)) MoveDispatchContext load_dispatch_words(const volatile uint32_t* words){MoveDispatchContext c;c.role=words[0];c.generation=words[1];c.command=words[2];c.kind=words[3];return c;}
static __attribute__((noinline)) void store_dispatch_words(volatile uint32_t* words,const MoveDispatchContext& c){words[0]=c.role;words[1]=c.generation;words[2]=c.command;words[3]=c.kind;}
static __attribute__((noinline)) void set_dispatch_words(volatile uint32_t* words,uint32_t role,uint32_t generation,uint32_t command,uint32_t kind){words[0]=role;words[1]=generation;words[2]=command;words[3]=kind;}
static __attribute__((noinline)) void clear_dispatch_words(volatile uint32_t* words){words[0]=0;words[1]=0;words[2]=0;words[3]=0;}
static __attribute__((noinline)) MoveDispatchContext load_move_context(){return load_dispatch_words(move_context_words);}
static __attribute__((noinline)) void set_move_context(uint32_t role,uint32_t generation,uint32_t command,uint32_t kind){set_dispatch_words(move_context_words,role,generation,command,kind);}
static __attribute__((noinline)) void clear_move_context(){clear_dispatch_words(move_context_words);}
static __attribute__((noinline)) void restore_move_context(const MoveDispatchContext& context){store_dispatch_words(move_context_words,context);}
typedef void (__attribute__((thiscall))*StoredCopy)(void*,void*);static StoredCopy old_stored_copy;
typedef bool (__attribute__((thiscall))*StoredUnpack)(void*,void*,void*);static StoredUnpack old_stored_unpack;
typedef void (__attribute__((thiscall))*CommandDispatch)(void*,void*);static CommandDispatch old_command_dispatch;
static uint32_t ticket_thing(uint32_t r){return r?p->support.thing:p->unit;}
static uint32_t ticket_update(uint32_t r){return r?p->support.update:p->update;}
static bool ticket_leased(uint32_t r){return role_leased(r!=0)&&p->phase==1&&GetCurrentThreadId()==p->thread;}
static uint32_t diagnostic_record(uint32_t kind,uint32_t cause,uint32_t previous,uint32_t r,uint32_t self,uint32_t thing,uint32_t command,uint32_t caller,uint32_t before,uint32_t after,uint32_t reason){
 uint32_t words[80]={};words[0]=0x44473131u;words[1]=kind==124?1:2;words[2]=cause;words[3]=previous;words[4]=r;words[5]=self;words[6]=thing;words[7]=command;words[8]=caller;words[9]=tag;words[10]=before;words[11]=after;words[12]=reason;
 MoveTicket& ticket=move_tickets[r];words[13]=ticket.armed;words[14]=ticket.pending;words[15]=ticket.unpack_ready;words[16]=ticket.facade_open;words[17]=ticket.consumer_open;words[18]=ticket.dispatch_seen;words[19]=ticket.proof.delivered;words[20]=ticket.proof.generation;words[21]=role_leased(r!=0);
 MoveDispatchContext current=load_move_context();words[24]=current.role;words[25]=current.generation;words[26]=current.command;words[27]=current.kind;
 words[76]=frame();words[22]=command&&read(command,words+28,23*4);words[75]=ticket_update(r)+0x310;words[23]=read(words[75],words+51,24*4);words[77]=frame();words[78]=word(thing+0xdc);words[79]=word(thing+0x418);
 return event(kind,cause,caller,0,0,0,r,NULL,0,0,words);
}
static uint32_t foreign_count(uint32_t r){return r?p->support.native_move:p->native_move;}
// YL18 denies a proven, external local-yield request. It grants no Move credit.
// The dispatcher and its facade both return void; the caller only destroys the
// stack Command afterward. All other inputs retain the original fatal policy.
static uint32_t denied_yield_count18[2];
static void reset_denied_yield18(){denied_yield_count18[0]=denied_yield_count18[1]=0;}
static bool deny_sample18(uint32_t r,uint32_t* w){
 uint32_t t=ticket_thing(r),u=ticket_update(r),mask=0;w[14]=t;w[39]=p->script_team;
 auto get=[&](uint32_t index,uint32_t address){w[index]=0;bool ok=read(address,w+index,4);if(ok)mask|=1u<<(index-15);return ok;};
 get(15,t+0xdc);get(16,t+4);get(17,w[16]+8);get(18,t+0x418);get(19,t+0x414);get(20,t+0x374);get(21,u);get(22,u+8);get(23,u+0x50);get(24,u+0x3c);get(25,w[24]+0x24);get(26,w[24]+0x78);get(27,w[24]+4);get(28,w[27]+4);get(29,w[27]);get(30,w[27]+0x18);get(31,u+0x150);get(32,t);
 w[94]=word(t+0x33c);get(33,w[94]+4);get(34,t+0x238);get(35,t+0x84);get(36,t+0x38);get(37,t+0x3c);get(38,t+0x40);w[77]=mask;
 float hp=0;memcpy(&hp,w+33,4);uint32_t id=r?p->support.id:p->object_id,hash=r?p->support.hash:p->type_hash;
 return mask==0xffffffu&&t&&u&&id&&p->owner&&p->script_team&&w[15]==id&&w[16]&&w[16]==p->slots[r].template_ptr&&w[17]==hash&&w[18]==p->owner&&w[19]==p->script_team&&w[20]==u&&w[21]==0xc48670&&w[22]==t&&w[23]==1&&w[25]==t&&w[30]==w[24]&&w[32]==0xc4db60&&isfinite(hp)&&hp>0;
}
#ifndef DENY_CAPTURE_STACK18
#define DENY_CAPTURE_STACK18(out) CaptureStackBackTrace(0,12,(void**)(out),NULL)
#endif
static bool deny_local_yield18(uint32_t r,uint32_t command,uint32_t caller,const uint32_t input[23],bool got,const MoveDispatchContext& prior,uint32_t dg_pre){
 MoveTicket& t=move_tickets[r];uint32_t before[128]={};
 if(p->phase!=1||p->error||GetCurrentThreadId()!=p->thread||!got||tag||caller!=0x6939aa||input[0]!=48||input[1]!=2||!ticket_leased(r)||(t.armed&&!t.proof.delivered)||t.pending||t.unpack_ready||t.facade_open||t.consumer_open||prior.role||prior.generation||prior.command||prior.kind||!deny_sample18(r,before))return false;
 uint32_t now=frame();if(!p->controller.clock_frozen||now>=p->controller.hard_deadline_frame)return false;
 uint32_t ordinal=denied_yield_count18[r]+1,foreign=foreign_count(r),moves=r?p->support.move_calls:p->move_calls;
 before[0]=0x594c3138;before[1]=1;before[2]=1;before[3]=r;before[4]=now;before[5]=GetCurrentThreadId();before[7]=ordinal;before[8]=32;before[9]=1;before[12]=p->phase;before[13]=p->mission_stage;before[40]=before[41]=foreign;before[42]=before[43]=moves;
 before[44]=(t.armed?1:0)|(t.pending?2:0)|(t.unpack_ready?4:0)|(t.facade_open?8:0)|(t.consumer_open?16:0)|(t.dispatch_seen?32:0)|(t.proof.delivered?64:0);
 before[46]=prior.role;before[47]=prior.generation;before[48]=prior.command;before[49]=prior.kind;before[50]=command;before[51]=caller;before[52]=1;memcpy(before+53,input,92);before[76]=frame();before[78]=before[79]=denied_yield_count18[r];before[92]=DENY_CAPTURE_STACK18(before+80);if(before[92]>12)before[92]=12;
 uint32_t pre=event(172,ordinal,caller,0,0,0,r,NULL,0,0,before);uint32_t after[128];memcpy(after,before,sizeof(after));after[2]=2;after[6]=pre;after[4]=frame();after[11]=ordinal>32?2:1;
 if(ordinal<=32)denied_yield_count18[r]++;after[79]=denied_yield_count18[r];bool same=deny_sample18(r,after);after[52]=read(command,after+53,92);after[76]=frame();after[41]=foreign_count(r);after[43]=r?p->support.move_calls:p->move_calls;
 after[12]=p->phase;after[13]=p->mission_stage;after[44]=(t.armed?1:0)|(t.pending?2:0)|(t.unpack_ready?4:0)|(t.facade_open?8:0)|(t.consumer_open?16:0)|(t.dispatch_seen?32:0)|(t.proof.delivered?64:0);
 MoveDispatchContext actual=load_move_context();after[46]=actual.role;after[47]=actual.generation;after[48]=actual.command;after[49]=actual.kind;
 same=same&&after[52]&&before[12]==after[12]&&before[13]==after[13]&&before[44]==after[44]&&before[4]==after[4]&&before[4]==after[76]&&!memcmp(before+14,after+14,26*4)&&!memcmp(before+53,after+53,92)&&!memcmp(before+46,after+46,16)&&after[41]==foreign&&after[43]==moves;
 if(!same)after[11]=3;event(173,ordinal,caller,0,0,0,r,NULL,0,0,after);diagnostic_record(125,0,dg_pre,r,ticket_update(r)+0x24,ticket_thing(r),command,caller,foreign,foreign_count(r),same?(ordinal>32?6:5):7);
 // No trampoline, private call, ticket mutation, or TLS write on this branch.
 if(ordinal>32||!same)request_cleanup(38,frame());return true;
}
static void ticket_foreign(uint32_t r,uint32_t cause,uint32_t previous=0,uint32_t self=0,uint32_t thing=0,uint32_t command=0,uint32_t caller=0,uint32_t reason=0){uint32_t before=foreign_count(r);if(r)p->support.native_move++;else p->native_move++;diagnostic_record(125,cause,previous,r,self,thing,command,caller,before,foreign_count(r),reason);}
static bool zero_words(const uint32_t* x,unsigned a,unsigned b){for(unsigned i=a;i<=b;i++)if(x[i])return false;return true;}
static bool pure_move_command(const uint32_t* c,const float goal[3]){
 return c[0]==0&&c[1]==1&&!memcmp(c+2,goal,12)&&zero_words(c,5,9)&&zero_words(c,11,13)&&zero_words(c,15,18)&&c[20]==0&&c[21]==0&&((const BYTE*)c)[0x58]==1;
}
static bool stored_move_payload(const uint32_t* s,const uint32_t* c){
 return !memcmp(s,c,24)&&zero_words(s,6,10)&&zero_words(s,12,14)&&!memcmp(s+16,c+15,16)&&s[21]==0&&s[22]==c[21]&&((const BYTE*)s)[0x5c]==((const BYTE*)c)[0x58];
}
static bool ticket_current(uint32_t r){
 MoveTicket& t=move_tickets[r];uint32_t u=ticket_update(r),thing=ticket_thing(r);
 return t.armed&&ticket_leased(r)&&t.proof.role==r&&t.proof.mission_stage==p->mission_stage&&frame()>=t.proof.issued_frame&&frame()-t.proof.issued_frame<=250&&frame()<frozen_deadline&&word(thing+0x418)==p->owner&&word(thing+0x374)==u&&word(u+8)==thing&&!memcmp(t.proof.goal,frozen_goals[r],12);
}
static void lineage_emit(uint32_t kind,uint32_t r,uint32_t reason=0){
 MoveTicket& t=move_tickets[r];t.proof.step=kind;lineage_record=t.proof;memset(lineage_record.observed_slot,0,sizeof(lineage_record.observed_slot));read(t.proof.slot,lineage_record.observed_slot,sizeof(lineage_record.observed_slot));event(kind,reason,0,0,0,0,r);
}
static void invalidate_move_ticket(uint32_t r,uint32_t reason){
 MoveTicket& t=move_tickets[r];if(t.armed||t.pending||t.unpack_ready||t.consumer_open){t.proof.invalid_reason=reason;lineage_emit(118,r,reason);}t.armed=t.pending=t.unpack_ready=t.facade_open=t.consumer_open=false;
}
static void invalidate_move_tickets(uint32_t reason){invalidate_move_ticket(0,reason);invalidate_move_ticket(1,reason);}
static bool arm_move_ticket(uint32_t r,uint32_t kind,uint32_t source_seq,const float* goal){
 invalidate_move_ticket(r,3);MoveTicket& t=move_tickets[r];memset(&t,0,sizeof(t));
 if(kind==168&&(r>1||!goal||p->mission_stage!=3||memcmp(goal,frozen_origins[r],12)))return false;
 if(!ticket_leased(r)||!source_seq||!isfinite(goal[0])||!isfinite(goal[1])||!isfinite(goal[2])||move_generations[r]>=160)return false;
 t.armed=true;t.proof.generation=++move_generations[r];t.proof.role=r;t.proof.mission_stage=p->mission_stage;t.proof.goal_kind=kind;t.proof.goal_event_seq=source_seq;t.proof.issued_frame=frame();t.proof.slot=ticket_update(r)+0x310;memcpy(t.proof.goal,goal,12);return true;
}
static bool authorize_private_move(uint32_t r,const float* goal,uint32_t path,float limit,uint32_t source,uint32_t caller){
 MoveDispatchContext context=load_move_context();MoveTicket& t=move_tickets[r];uint32_t bits=0;memcpy(&bits,&limit,4);
 if(!ticket_current(r)||t.proof.delivered||source!=1||path||bits!=0x7f7fffff||!goal||memcmp(goal,t.proof.goal,12)||caller!=0x6d3b7d||context.role!=r||context.generation!=t.proof.generation)return false;
 bool direct=tag==6&&context.kind==1&&t.facade_open;
 bool deferred=tag==0&&context.kind==2&&t.consumer_open&&t.pending&&context.command==t.proof.output_command;
 if((!direct&&!deferred)||(uintptr_t)goal!=context.command+8)return false;
 t.proof.delivered=1;t.proof.private_caller=caller;if(deferred)t.pending=false;return true;
}
static void __attribute__((fastcall)) stored_copy_hook(void* self,void*,void* command){
 InterlockedIncrement(&p->active);uint32_t r=2;for(uint32_t i=0;i<2;i++)if((uintptr_t)self==ticket_update(i)+0x310&&ticket_leased(i))r=i;
 if(r==2||(tag!=0&&tag!=6)){old_stored_copy(self,command);InterlockedDecrement(&p->active);return;}MoveTicket& t=move_tickets[r];uint32_t caller=LINEAGE_OBSERVED_CALLER;uint32_t before[24]={},input[23]={};bool got=read((uintptr_t)self,before,sizeof(before))&&read((uintptr_t)command,input,sizeof(input));
 MoveDispatchContext context=load_move_context();bool valid=got&&ticket_current(r)&&tag==6&&t.facade_open&&context.kind==1&&context.role==r&&context.generation==t.proof.generation&&context.command==(uintptr_t)command&&t.proof.input_command==(uintptr_t)command&&caller==0x787d42&&!t.pending&&!t.proof.delivered&&before[0]==0xffffffffu&&pure_move_command(input,t.proof.goal)&&!memcmp(input,t.proof.command,sizeof(input));
 t.proof.observed_this=(uintptr_t)self;t.proof.observed_thing=0;t.proof.observed_command=(uintptr_t)command;
 if(valid){t.proof.copy_caller=caller;memcpy(t.proof.stored_before,before,sizeof(before));lineage_emit(111,r);}
 old_stored_copy(self,command);uint32_t after[24]={};valid=valid&&read((uintptr_t)self,after,sizeof(after))&&memcmp(before,after,sizeof(after))&&stored_move_payload(after,input);
 if(valid){memcpy(t.proof.stored_after,after,sizeof(after));t.pending=true;lineage_emit(112,r);}else{invalidate_move_ticket(r,6);ticket_foreign(r,3,0,(uintptr_t)self,word((uintptr_t)self-0x310+8),(uintptr_t)command,caller,6);}InterlockedDecrement(&p->active);
}
static bool __attribute__((fastcall)) stored_unpack_hook(void* self,void*,void* thing,void* output){
 InterlockedIncrement(&p->active);uint32_t r=2;for(uint32_t i=0;i<2;i++)if((uintptr_t)self==ticket_update(i)+0x310&&ticket_leased(i))r=i;
 if(r==2||(!move_tickets[r].armed&&!move_tickets[r].pending)){bool passthrough=old_stored_unpack(self,thing,output);InterlockedDecrement(&p->active);return passthrough;}MoveTicket& t=move_tickets[r];uint32_t caller=LINEAGE_OBSERVED_CALLER,current[24]={};
 bool valid=ticket_current(r)&&tag==0&&t.pending&&!t.unpack_ready&&!t.facade_open&&!t.consumer_open&&!t.proof.delivered&&(uintptr_t)thing==ticket_thing(r)&&caller==0x7da0b3&&read((uintptr_t)self,current,sizeof(current))&&!memcmp(current,t.proof.stored_after,sizeof(current));
 t.proof.observed_this=(uintptr_t)self;t.proof.observed_thing=(uintptr_t)thing;t.proof.observed_command=(uintptr_t)output;
 if(valid){t.proof.unpack_caller=caller;t.proof.output_command=(uintptr_t)output;lineage_emit(113,r);}
 bool result=old_stored_unpack(self,thing,output);uint32_t decoded[23]={};valid=valid&&result&&read((uintptr_t)output,decoded,sizeof(decoded))&&pure_move_command(decoded,t.proof.goal)&&stored_move_payload(current,decoded);
 if(valid){memcpy(t.proof.unpacked,decoded,sizeof(decoded));t.unpack_ready=true;lineage_emit(114,r);}else{invalidate_move_ticket(r,8);ticket_foreign(r,4,0,(uintptr_t)self,(uintptr_t)thing,(uintptr_t)output,caller,8);}InterlockedDecrement(&p->active);return result;
}
static void __attribute__((fastcall)) command_dispatch_hook(void* self,void*,void* command){
 InterlockedIncrement(&p->active);uint32_t r=2;for(uint32_t i=0;i<2;i++)if((uintptr_t)self==ticket_update(i)+0x24&&ticket_leased(i))r=i;
 if(r==2){old_command_dispatch(self,command);InterlockedDecrement(&p->active);return;}MoveTicket& t=move_tickets[r];uint32_t caller=LINEAGE_OBSERVED_CALLER,input[23]={};bool got=read((uintptr_t)command,input,sizeof(input));MoveDispatchContext prior=load_move_context();
 uint32_t observed_this=(uintptr_t)self,observed_thing=word(observed_this-0x24+8),counter_before=foreign_count(r);uint32_t diagnostic_pre=diagnostic_record(124,0,0,r,observed_this,observed_thing,(uintptr_t)command,caller,counter_before,counter_before,0);
 if(deny_local_yield18(r,(uintptr_t)command,caller,input,got,prior,diagnostic_pre)){InterlockedDecrement(&p->active);return;}
 bool own=got&&tag==6&&ticket_current(r)&&t.facade_open&&!t.dispatch_seen&&!t.proof.delivered&&pure_move_command(input,t.proof.goal);
 bool continuation=got&&tag==0&&ticket_current(r)&&t.pending&&t.unpack_ready&&!t.proof.delivered&&!t.facade_open&&caller==0x7da0d9&&(uintptr_t)command==t.proof.output_command&&!memcmp(input,t.proof.unpacked,sizeof(input))&&pure_move_command(input,t.proof.goal);
 t.proof.observed_this=(uintptr_t)self;t.proof.observed_thing=0;t.proof.observed_command=(uintptr_t)command;
 if(own){t.dispatch_seen=true;t.proof.input_command=(uintptr_t)command;memcpy(t.proof.command,input,sizeof(input));set_move_context(r,t.proof.generation,(uint32_t)(uintptr_t)command,1);lineage_emit(120,r);diagnostic_record(125,0,diagnostic_pre,r,observed_this,observed_thing,(uintptr_t)command,caller,counter_before,foreign_count(r),1);}
 else if(continuation){t.unpack_ready=false;t.consumer_open=true;t.proof.dispatch_caller=caller;set_move_context(r,t.proof.generation,(uint32_t)(uintptr_t)command,2);lineage_emit(115,r);diagnostic_record(125,0,diagnostic_pre,r,observed_this,observed_thing,(uintptr_t)command,caller,counter_before,foreign_count(r),2);}
 else if(tag==0||tag==6||((tag==7||tag==8)&&(!got||input[0]!=5||!expected_stance_stop(r,input[1])))){invalidate_move_ticket(r,9);ticket_foreign(r,5,diagnostic_pre,observed_this,observed_thing,(uintptr_t)command,caller,3);clear_move_context();}
 else diagnostic_record(125,0,diagnostic_pre,r,observed_this,observed_thing,(uintptr_t)command,caller,counter_before,foreign_count(r),4);
 old_command_dispatch(self,command);
 if(continuation){t.proof.observed_this=(uintptr_t)self;t.proof.observed_thing=0;t.proof.observed_command=(uintptr_t)command;if(!t.proof.delivered){invalidate_move_ticket(r,10);ticket_foreign(r,7,diagnostic_pre,observed_this,observed_thing,(uintptr_t)command,caller,10);}else lineage_emit(117,r);t.consumer_open=false;t.armed=false;}
 restore_move_context(prior);InterlockedDecrement(&p->active);
}
