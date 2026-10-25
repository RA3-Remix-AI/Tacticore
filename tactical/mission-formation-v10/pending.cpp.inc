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
static void ticket_foreign(uint32_t r){if(r)p->support.native_move++;else p->native_move++;}
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
 if(valid){memcpy(t.proof.stored_after,after,sizeof(after));t.pending=true;lineage_emit(112,r);}else{invalidate_move_ticket(r,6);ticket_foreign(r);}InterlockedDecrement(&p->active);
}
static bool __attribute__((fastcall)) stored_unpack_hook(void* self,void*,void* thing,void* output){
 InterlockedIncrement(&p->active);uint32_t r=2;for(uint32_t i=0;i<2;i++)if((uintptr_t)self==ticket_update(i)+0x310&&ticket_leased(i))r=i;
 if(r==2||(!move_tickets[r].armed&&!move_tickets[r].pending)){bool passthrough=old_stored_unpack(self,thing,output);InterlockedDecrement(&p->active);return passthrough;}MoveTicket& t=move_tickets[r];uint32_t caller=LINEAGE_OBSERVED_CALLER,current[24]={};
 bool valid=ticket_current(r)&&tag==0&&t.pending&&!t.unpack_ready&&!t.facade_open&&!t.consumer_open&&!t.proof.delivered&&(uintptr_t)thing==ticket_thing(r)&&caller==0x7da0b3&&read((uintptr_t)self,current,sizeof(current))&&!memcmp(current,t.proof.stored_after,sizeof(current));
 t.proof.observed_this=(uintptr_t)self;t.proof.observed_thing=(uintptr_t)thing;t.proof.observed_command=(uintptr_t)output;
 if(valid){t.proof.unpack_caller=caller;t.proof.output_command=(uintptr_t)output;lineage_emit(113,r);}
 bool result=old_stored_unpack(self,thing,output);uint32_t decoded[23]={};valid=valid&&result&&read((uintptr_t)output,decoded,sizeof(decoded))&&pure_move_command(decoded,t.proof.goal)&&stored_move_payload(current,decoded);
 if(valid){memcpy(t.proof.unpacked,decoded,sizeof(decoded));t.unpack_ready=true;lineage_emit(114,r);}else{invalidate_move_ticket(r,8);ticket_foreign(r);}InterlockedDecrement(&p->active);return result;
}
static void __attribute__((fastcall)) command_dispatch_hook(void* self,void*,void* command){
 InterlockedIncrement(&p->active);uint32_t r=2;for(uint32_t i=0;i<2;i++)if((uintptr_t)self==ticket_update(i)+0x24&&ticket_leased(i))r=i;
 if(r==2){old_command_dispatch(self,command);InterlockedDecrement(&p->active);return;}MoveTicket& t=move_tickets[r];uint32_t caller=LINEAGE_OBSERVED_CALLER,input[23]={};bool got=read((uintptr_t)command,input,sizeof(input));MoveDispatchContext prior=load_move_context();
 bool own=got&&tag==6&&ticket_current(r)&&t.facade_open&&!t.dispatch_seen&&!t.proof.delivered&&pure_move_command(input,t.proof.goal);
 bool continuation=got&&tag==0&&ticket_current(r)&&t.pending&&t.unpack_ready&&!t.proof.delivered&&!t.facade_open&&caller==0x7da0d9&&(uintptr_t)command==t.proof.output_command&&!memcmp(input,t.proof.unpacked,sizeof(input))&&pure_move_command(input,t.proof.goal);
 t.proof.observed_this=(uintptr_t)self;t.proof.observed_thing=0;t.proof.observed_command=(uintptr_t)command;
 if(own){t.dispatch_seen=true;t.proof.input_command=(uintptr_t)command;memcpy(t.proof.command,input,sizeof(input));set_move_context(r,t.proof.generation,(uint32_t)(uintptr_t)command,1);lineage_emit(120,r);}
 else if(continuation){t.unpack_ready=false;t.consumer_open=true;t.proof.dispatch_caller=caller;set_move_context(r,t.proof.generation,(uint32_t)(uintptr_t)command,2);lineage_emit(115,r);}
 else if(tag==0||tag==6){invalidate_move_ticket(r,9);ticket_foreign(r);clear_move_context();}
 old_command_dispatch(self,command);
 if(continuation){t.proof.observed_this=(uintptr_t)self;t.proof.observed_thing=0;t.proof.observed_command=(uintptr_t)command;if(!t.proof.delivered){invalidate_move_ticket(r,10);ticket_foreign(r);}else lineage_emit(117,r);t.consumer_open=false;t.armed=false;}
 restore_move_context(prior);InterlockedDecrement(&p->active);
}
