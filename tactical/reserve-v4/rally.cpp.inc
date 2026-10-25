// One synchronous normal Move. No delayed-command lineage is imported.
typedef void (__attribute__((thiscall))*Move)(void*,float*,void*,float,uint32_t);
typedef void (__attribute__((thiscall))*MoveFacade)(void*,float*,uint32_t);
static Move old_move;static MoveFacade old_move_facade;
static bool rally_intent_open,rally_facade_open,rally_invalid,rally_proposed;
static uint32_t rally_generation,rally_intent_seq,rally_facade_seq,rally_delivered;
static Sample admission4_baseline;static bool admission4_baseline_set;
static uint32_t admission4_count,admission4_team,admission4_last_observed,admitted_team;
static bool admission_equal(const Sample&,const Sample&);
static float anchor_initial_xyz[3],rally_private_origin[3];
static float anchor_initial_gap,anchor_candidate_xyz[3],anchor_actual_xyz[3],anchor_previous_xyz[3];
static uint32_t anchor_candidate_count,anchor_last_frame;static bool anchor_frozen,anchor_committed;
static float rally_private_goal[3];static uint32_t factory_observed[10];
static void rally_reset(){memset(&admission4_baseline,0,sizeof(admission4_baseline));admission4_baseline_set=false;admission4_count=admission4_team=admission4_last_observed=admitted_team=0;memset(anchor_initial_xyz,0,12);memset(rally_private_origin,0,12);anchor_initial_gap=0;anchor_candidate_count=anchor_last_frame=0;anchor_frozen=anchor_committed=false;memset(anchor_candidate_xyz,0,12);memset(anchor_actual_xyz,0,12);memset(anchor_previous_xyz,0,12);rally_intent_open=rally_facade_open=rally_invalid=rally_proposed=false;rally_generation=rally_intent_seq=rally_facade_seq=rally_delivered=0;memset(rally_private_goal,0,12);memset(factory_observed,0,sizeof(factory_observed));}
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
 if(ours){if(rally_leased())p->rally.move_private_entries++;valid=rally_leased()&&GetCurrentThreadId()==p->thread&&tag==7&&rally_intent_open&&rally_facade_open&&!rally_delivered&&!rally_invalid&&(proof.flags&1)&&!memcmp(proof.goal_bits,rally_private_goal,12)&&!path&&proof.limit_bits==0x7f7fffff&&source==1&&word((uintptr_t)self+8)==p->thing&&actor()&&word(p->thing+0x414)==p->script_team;if(rally_leased()&&!valid)rally_bad_move();if(valid)proof.flags|=2;emit(66,(uintptr_t)path,caller,(uintptr_t)self,source,0,&proof);}
 old_move(self,goal,path,limit,source);
 if(ours){if(valid)rally_delivered++;proof=move_proof(goal,(uintptr_t)path,limit,valid,valid);emit(67,(uintptr_t)path,caller,(uintptr_t)self,source,0,&proof);}InterlockedDecrement(&p->active);
}
static void __attribute__((fastcall)) move_facade_hook(void* self,void*,float* goal,uint32_t source){
 InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update+0x24;uint32_t caller=(uintptr_t)__builtin_return_address(0);bool before_open=rally_facade_open;uint32_t before_seq=rally_facade_seq;
 MoveProof proof=move_proof(goal,0,0,false,false);bool valid=false;
 if(ours){if(rally_leased())p->rally.move_facade_entries++;valid=rally_leased()&&GetCurrentThreadId()==p->thread&&tag==7&&rally_intent_open&&!rally_facade_open&&!rally_delivered&&!rally_invalid&&(proof.flags&1)&&!memcmp(proof.goal_bits,rally_private_goal,12)&&source==1&&word((uintptr_t)self-0x24+8)==p->thing&&actor()&&word(p->thing+0x414)==p->script_team;if(rally_leased()&&!valid)rally_bad_move();if(valid){rally_facade_open=true;p->rally.move_scope_open=1;proof.flags|=2;}uint32_t seq=emit(64,0,caller,(uintptr_t)self,source,0,&proof);if(valid)rally_facade_seq=seq;}
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
 float f[2];memcpy(f,&p->rally.factory_x_bits,8);float dx=anchor_initial_xyz[0]-f[0],dy=anchor_initial_xyz[1]-f[1],n=sqrtf(dx*dx+dy*dy);
 if(!isfinite(n)||n<5||!finite_xyz(s.xyz))return false;
 p->rally.proposal_direction[0]=-dy/n;p->rally.proposal_direction[1]=dx/n;memcpy(p->rally.proposal_origin,s.xyz,12);memcpy(rally_private_origin,s.xyz,12);
 p->rally.goal[0]=s.xyz[0]+100*p->rally.proposal_direction[0];p->rally.goal[1]=s.xyz[1]+100*p->rally.proposal_direction[1];p->rally.goal[2]=s.xyz[2];if(!finite_xyz(p->rally.goal))return false;
 memcpy(rally_private_goal,p->rally.goal,12);p->rally.proposal_frame=s.frame;rally_proposed=true;
 MoveProof raw={};memcpy(&raw,factory_observed,40);emit(69,p->rally.factory_id,0,p->rally.factory_address,0,0,&raw);emit(62);return true;
}
static bool rally_goal_bound(){return rally_proposed&&finite_xyz(p->rally.goal)&&!memcmp(p->rally.goal,rally_private_goal,12)&&!memcmp(p->rally.proposal_origin,rally_private_origin,12);}
static bool rally_failed(){return rally_invalid;}

static bool reserve3_admission(const Sample& s){
 if(s.frame<p->production_birth_frame||s.frame-p->production_birth_frame>300)return false;
 float f[2];memcpy(f,&p->rally.factory_x_bits,8);float dx=s.xyz[0]-f[0],dy=s.xyz[1]-f[1],gap=sqrtf(dx*dx+dy*dy);
 if(!isfinite(gap)||gap>200)return false;
 if(!p->admission_samples)p->anchor.admission_age_first=s.frame-p->production_birth_frame;
 p->anchor.admission_age_last=s.frame-p->production_birth_frame;p->anchor.initial_factory_gap=gap;
 anchor_initial_gap=gap;memcpy(anchor_initial_xyz,s.xyz,12);p->anchor.initial_outside_inner_zone=gap>=120;return true;
}
static bool anchor_point_eligible(const Sample& s){
 float f[2];memcpy(f,&p->rally.factory_x_bits,8);float dx=s.xyz[0]-f[0],dy=s.xyz[1]-f[1],gap=sqrtf(dx*dx+dy*dy);
 return s.state_id==94&&s.state_vtable==0xc551a0&&!s.path&&s.source==1&&s.stance==2&&!(s.sm_flags&0xffff)&&s.team==p->script_team&&isfinite(gap)&&gap>=120&&gap>=anchor_initial_gap&&distance(s.xyz,rally_private_origin)>=60;
}
static bool anchor_candidate_tick(const Sample& s){
 if(anchor_frozen)return false;
 bool okay=anchor_point_eligible(s);bool consecutive=anchor_candidate_count&&s.frame==anchor_last_frame+1&&distance(s.xyz,anchor_previous_xyz)<=1;
 if(!okay){anchor_candidate_count=anchor_last_frame=0;p->anchor.candidate_samples=p->anchor.last_candidate_frame=0;return false;}
 anchor_candidate_count=consecutive?anchor_candidate_count+1:1;anchor_last_frame=s.frame;memcpy(anchor_previous_xyz,s.xyz,12);
 p->anchor.candidate_samples=anchor_candidate_count;p->anchor.last_candidate_frame=s.frame;memcpy(p->anchor.last_candidate_xyz,s.xyz,12);emit(70,anchor_candidate_count);
 if(anchor_candidate_count<3)return false;
 memcpy(anchor_candidate_xyz,s.xyz,12);memcpy(p->anchor.candidate_xyz,s.xyz,12);p->anchor.candidate_frame=s.frame;anchor_frozen=true;emit(71,3);return true;
}
static bool anchor_commit(const Sample& s){
 if(!anchor_frozen||anchor_committed||memcmp(p->anchor.candidate_xyz,anchor_candidate_xyz,12)||!anchor_point_eligible(s)||distance(s.xyz,anchor_candidate_xyz)>15)return false;
 memcpy(anchor_actual_xyz,s.xyz,12);memcpy(p->anchor.actual_anchor,s.xyz,12);p->anchor.commit_frame=s.frame;anchor_committed=true;
 p->anchor.boundary_crossed=!p->anchor.initial_outside_inner_zone;
 p->anchor.proposal_distance=distance(s.xyz,rally_private_goal);p->anchor.proposal_reached=p->rally.rally_reached_frame!=0;
 return true;
}
static bool actual_anchor_bound(){return anchor_committed&&!memcmp(p->anchor.actual_anchor,anchor_actual_xyz,12)&&!memcmp(p->hold_anchor,anchor_actual_xyz,12);}

static void admission4_clear_cohort(){
 admission4_count=admission4_team=0;p->admission_samples=p->admission_first_frame=p->admission_last_frame=p->admission_max_gap=p->admission_verified=0;memset(&p->admission_first_sample,0,sizeof(Sample));
}
static uint32_t admission4_team_proof(const Sample& s,TeamProof& proof){
 memset(&proof,0,sizeof(proof));proof.magic=0x544d5034;proof.sample_frame=s.frame;proof.previous_team=admission4_team;proof.previous_count=admission4_count;
 proof.team_before=word(p->thing+0x414);proof.definition_before=word(proof.team_before+4);proof.owner_before=word(proof.definition_before+8);
 proof.team_after=word(p->thing+0x414);proof.definition_after=word(proof.team_after+4);proof.owner_after=word(proof.definition_after+8);
 if(!s.team||!proof.team_before||!proof.team_after)return 3;
 if(s.team==p->script_team||proof.team_before==p->script_team||proof.team_after==p->script_team)return 4;
 if((s.team&3)||(proof.team_before&3)||(proof.team_after&3)||(proof.definition_before&3)||(proof.definition_after&3)||!proof.definition_before||!proof.definition_after||proof.owner_before!=p->owner||proof.owner_after!=p->owner)return 5;
 if(frame()!=s.frame)return 6;
 return proof.team_before!=proof.team_after||proof.definition_before!=proof.definition_after||s.team!=proof.team_before?2:0;
}
static void admission4_emit(uint32_t kind,uint32_t arg,uint32_t result,const Sample& s,const TeamProof& proof){MoveProof raw={};memcpy(&raw,&proof,40);emit(kind,arg,0,p->thing,0,result,&raw,&s);}
static int admission4_collect(const Sample& s){
 if(admission4_last_observed==s.frame)return 0;
 if(admission4_last_observed&&s.frame!=admission4_last_observed+1){p->error=49;return -1;}admission4_last_observed=s.frame;
 if(!admission4_baseline_set){admission4_baseline=s;admission4_baseline_set=true;}
 else if(!admission_equal(admission4_baseline,s)){p->error=49;return -1;}
 TeamProof proof={};uint32_t status=admission4_team_proof(s,proof);
 if(status>=3){admission4_emit(75,status,admission4_count,s,proof);p->error=status==6?49:60;return -1;}
 if(status==2){admission4_emit(74,2,admission4_count,s,proof);admission4_clear_cohort();return 0;}
 if(admission4_count&&admission4_team!=s.team){admission4_emit(74,1,admission4_count,s,proof);admission4_clear_cohort();proof.previous_team=proof.previous_count=0;}
 if(!admission4_count){p->admission_first_sample=s;p->admission_first_frame=s.frame;p->anchor.admission_age_first=s.frame-p->production_birth_frame;admission4_team=s.team;}
 admission4_emit(73,s.team,admission4_count,s,proof);
 admission4_count++;p->admission_samples=admission4_count;p->admission_last_frame=s.frame;p->admission_max_gap=admission4_count>1?1:0;
 emit(60,admission4_count,0,0,0,0,NULL,&s);
 if(admission4_count<3)return 0;
 TeamProof after={};status=admission4_team_proof(s,after);
 if(status>=3){admission4_emit(75,status,admission4_count,s,after);p->error=status==6?49:60;return -1;}
 if(status==2){admission4_emit(74,2,admission4_count,s,after);admission4_clear_cohort();return 0;}
 admitted_team=s.team;return 1;
}
