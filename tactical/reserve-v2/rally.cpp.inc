// One synchronous normal Move. No delayed-command lineage is imported.
typedef void (__attribute__((thiscall))*Move)(void*,float*,void*,float,uint32_t);
typedef void (__attribute__((thiscall))*MoveFacade)(void*,float*,uint32_t);
static Move old_move;static MoveFacade old_move_facade;
static bool rally_intent_open,rally_facade_open,rally_invalid,rally_proposed;
static uint32_t rally_generation,rally_intent_seq,rally_facade_seq,rally_delivered;
static float rally_private_goal[3];static uint32_t factory_observed[10];
static void rally_reset(){rally_intent_open=rally_facade_open=rally_invalid=rally_proposed=false;rally_generation=rally_intent_seq=rally_facade_seq=rally_delivered=0;memset(rally_private_goal,0,12);memset(factory_observed,0,sizeof(factory_observed));}
static bool factory(){
 uint32_t a=p->rally.factory_address,before=frame(),v[10]={a,word(a+0xdc),word(a+0x418),word(a+4),0,before,word(a+0x38),word(a+0x3c),0,word(a)};
 v[4]=word(v[3]+8);v[8]=word(word(a+0x33c)+4);float hp=0,xy[2];memcpy(&hp,v+8,4);memcpy(xy,v+6,8);
 if(!a||v[9]!=0xc4db60||v[1]!=p->rally.factory_id||v[2]!=p->owner||v[2]!=p->rally.factory_owner||v[3]!=p->rally.factory_template||v[4]!=p->rally.factory_type_hash||v[4]!=0x80d4ea1e||!isfinite(hp)||hp<=0||!isfinite(xy[0])||!isfinite(xy[1])||v[6]!=p->rally.factory_x_bits||v[7]!=p->rally.factory_y_bits)return false;
 uint32_t after[10]={a,word(a+0xdc),word(a+0x418),word(a+4),0,frame(),word(a+0x38),word(a+0x3c),word(word(a+0x33c)+4),word(a)};after[4]=word(after[3]+8);
 if(memcmp(v,after,sizeof(v)))return false;
 memcpy(factory_observed,v,sizeof(v));return true;
}
static bool rally_leased(){return p->detach_calls&&!p->return_calls;}
static void rally_bad_move(){rally_invalid=true;p->rally.foreign_move_entries++;}
static MoveProof move_proof(float* goal,uint32_t path,float limit,bool valid,bool delivered){
 MoveProof out={};out.goal_pointer=(uintptr_t)goal;out.path=path;memcpy(&out.limit_bits,&limit,4);out.intent_seq=rally_intent_seq;out.facade_seq=rally_facade_seq;out.generation=rally_generation;
 if(goal&&read((uintptr_t)goal,out.goal_bits,12)){float xyz[3];memcpy(xyz,out.goal_bits,12);if(finite_xyz(xyz))out.flags|=1;}
 if(valid)out.flags|=2;
 if(delivered)out.flags|=4;
 return out;
}
static void __attribute__((fastcall)) move_hook(void* self,void*,float* goal,void* path,float limit,uint32_t source){
 InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update;uint32_t caller=(uintptr_t)__builtin_return_address(0);bool valid=false;
 MoveProof proof=move_proof(goal,(uintptr_t)path,limit,false,false);
 if(ours){p->rally.move_private_entries++;valid=rally_leased()&&GetCurrentThreadId()==p->thread&&tag==7&&rally_intent_open&&rally_facade_open&&!rally_delivered&&!rally_invalid&&(proof.flags&1)&&!memcmp(proof.goal_bits,rally_private_goal,12)&&!path&&proof.limit_bits==0x7f7fffff&&source==1&&word((uintptr_t)self+8)==p->thing&&actor()&&word(p->thing+0x414)==p->script_team;if(rally_leased()&&!valid)rally_bad_move();if(valid)proof.flags|=2;emit(66,(uintptr_t)path,caller,(uintptr_t)self,source,0,&proof);}
 old_move(self,goal,path,limit,source);
 if(ours){if(valid)rally_delivered++;proof=move_proof(goal,(uintptr_t)path,limit,valid,valid);emit(67,(uintptr_t)path,caller,(uintptr_t)self,source,0,&proof);}InterlockedDecrement(&p->active);
}
static void __attribute__((fastcall)) move_facade_hook(void* self,void*,float* goal,uint32_t source){
 InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update+0x24;uint32_t caller=(uintptr_t)__builtin_return_address(0);bool before_open=rally_facade_open;uint32_t before_seq=rally_facade_seq;
 MoveProof proof=move_proof(goal,0,0,false,false);bool valid=false;
 if(ours){p->rally.move_facade_entries++;valid=rally_leased()&&GetCurrentThreadId()==p->thread&&tag==7&&rally_intent_open&&!rally_facade_open&&!rally_delivered&&!rally_invalid&&(proof.flags&1)&&!memcmp(proof.goal_bits,rally_private_goal,12)&&source==1&&word((uintptr_t)self-0x24+8)==p->thing&&actor()&&word(p->thing+0x414)==p->script_team;if(rally_leased()&&!valid)rally_bad_move();if(valid){rally_facade_open=true;p->rally.move_scope_open=1;proof.flags|=2;}uint32_t seq=emit(64,0,caller,(uintptr_t)self,source,0,&proof);if(valid)rally_facade_seq=seq;}
 old_move_facade(self,goal,source);
 if(ours){proof=move_proof(goal,0,0,valid,valid&&rally_delivered==1);emit(65,0,caller,(uintptr_t)self,source,0,&proof);if(valid){rally_facade_open=before_open;rally_facade_seq=before_seq;p->rally.move_scope_open=before_open?1:0;}}
 InterlockedDecrement(&p->active);
}
#ifdef RESERVE2_PURE
static void test_call_move_facade(float*);
#endif
static bool move_rally(){
 if(!rally_proposed||rally_generation||rally_invalid||!actor()||!module()||!factory())return false;
 rally_generation=1;p->rally.move_generation=1;p->rally.move_intents++;tag=7;rally_intent_seq=sdk(7,0);p->rally.move_intent_seq=rally_intent_seq;if(!rally_intent_seq){tag=0;return false;}rally_intent_open=true;
#ifdef RESERVE2_PURE
 test_call_move_facade(rally_private_goal);
#else
 ((MoveFacade)0x571d90)((void*)(uintptr_t)(p->update+0x24),rally_private_goal,1);
#endif
 rally_intent_open=false;rally_facade_open=false;p->rally.move_scope_open=0;tag=0;
 return !rally_invalid&&rally_delivered==1&&p->rally.move_facade_entries==1&&p->rally.move_private_entries==1;
}
static bool propose_rally(const Sample& s){
 if(rally_proposed||!factory())return false;
 float f[2];memcpy(f,&p->rally.factory_x_bits,8);float dx=p->initial_sample.xyz[0]-f[0],dy=p->initial_sample.xyz[1]-f[1],n=sqrtf(dx*dx+dy*dy);
 if(!isfinite(n)||n<5||!finite_xyz(s.xyz))return false;
 p->rally.proposal_direction[0]=-dy/n;p->rally.proposal_direction[1]=dx/n;memcpy(p->rally.proposal_origin,s.xyz,12);
 p->rally.goal[0]=s.xyz[0]+100*p->rally.proposal_direction[0];p->rally.goal[1]=s.xyz[1]+100*p->rally.proposal_direction[1];p->rally.goal[2]=s.xyz[2];if(!finite_xyz(p->rally.goal))return false;
 memcpy(rally_private_goal,p->rally.goal,12);p->rally.proposal_frame=s.frame;rally_proposed=true;
 MoveProof raw={};memcpy(&raw,factory_observed,40);emit(69,p->rally.factory_id,0,p->rally.factory_address,0,0,&raw);emit(62);return true;
}
static bool rally_goal_bound(){return rally_proposed&&finite_xyz(p->rally.goal)&&!memcmp(p->rally.goal,rally_private_goal,12);}
static bool rally_failed(){return rally_invalid;}
