// Single controller owns the production-to-reserve-to-mission lifecycle.
static ControllerInput13 controller_frozen;
static BYTE controller_binding13[offsetof(Tactical,unit)];
static uint32_t reserve_clock_start13,reserve_clock_deadline13,lease_clock_deadline13;
static MissionCommitBody13 accepted_commit;
static bool commit_seen;static uint32_t controller_install_tick,first_borrow_role=2,controller_core_tick;
static HANDLE producer_mapping;static const BYTE* producer_view;
static uint32_t reserve_proof_words[128];
struct ReservePrivate13 {
 ReserveSample13 baseline,previous;uint32_t last_observed,cohort_team,cohort_count;
 uint32_t last_stop_sample,stop_count,last_candidate_frame,candidate_count,initial_ready;
 uint32_t factory_words[10],team_words[10];float stopped_xyz[3],last_candidate_xyz[3];
 uint32_t observed_path,stage;float private_initial[3],private_proposal[3],private_brake[3],private_anchor[3],private_initial_gap;bool receipt_bound,baseline_set;ProductionReceipt13 payment;
};
static ReservePrivate13 reserve_private[2];
static void controller_close(){if(producer_view){UnmapViewOfFile(producer_view);producer_view=NULL;}if(producer_mapping){CloseHandle(producer_mapping);producer_mapping=NULL;}}
static bool nonzero_uuid13(const uint32_t* a){return a[0]||a[1]||a[2]||a[3];}
static bool controller_bound(){return p->initial_weapon_asset==captured_initial_asset13&&p->initial_weapon_entry==captured_initial_entry13&&!memcmp(p,controller_binding13,sizeof(controller_binding13))&&(!reserve_clock_start13||(p->controller.clock_frozen&&p->controller.reserve_start_frame==reserve_clock_start13&&p->controller.reserve_deadline_frame==reserve_clock_deadline13&&p->controller.hard_deadline_frame==lease_clock_deadline13&&p->issued_frame==reserve_clock_start13))&&!memcmp(&p->controller_input,&controller_frozen,sizeof(controller_frozen))&&!memcmp(p->command,controller_frozen.controller,16)&&!memcmp(p->task,controller_frozen.lease,16);}
static bool slot_runtime_bound13(){
 for(uint32_t r=0;r<2;r++){const ReservePrivate13& v=reserve_private[r];const PaidSlotOutput13& out=p->slots[r];if(out.stage!=v.stage)return false;if(!v.receipt_bound)continue;
  if(out.thing!=v.payment.object||out.id!=v.payment.object_id)return false;
  if(v.stage&&(role_thing(r)!=v.payment.object||role_id(r)!=v.payment.object_id))return false;
  if(v.baseline_set&&(role_update(r)!=v.baseline.update||out.template_ptr!=v.baseline.template_ptr||out.update!=v.baseline.update))return false;
  if(memcmp(out.initial_xyz,v.private_initial,12)||memcmp(out.proposal,v.private_proposal,12)||memcmp(out.brake_xyz,v.private_brake,12)||memcmp(out.anchor,v.private_anchor,12)||out.initial_factory_gap!=v.private_initial_gap)return false;
 }
 if(commit_seen&&(p->target_unit!=accepted_commit.target_unit||p->target_id!=accepted_commit.target_id||p->target_hash!=accepted_commit.target_hash||p->target_owner!=accepted_commit.target_owner||p->target_template!=accepted_commit.target_template||p->button!=accepted_commit.button||p->button_schema!=accepted_commit.button_schema||p->command_set!=accepted_commit.command_set))return false;
 return true;
}
static void slot_stage13(uint32_t r,uint32_t stage){p->slots[r].stage=reserve_private[r].stage=stage;}
static bool live_member13(uint32_t ptr,uint32_t id){
 uint32_t now=frame(),first=word(p->logic+0xb4),t=first,found=0,count=0;
 while(t){if(t%4||++count>20000||word(t)!=0xc4db60)return false;if(word(t+0xdc)==id){if(t!=ptr||found)return false;found=t;}uint32_t next=word(t+0x7c);if(next==t)return false;t=next;}
 return found&&frame()==now&&word(p->logic+0xb4)==first&&identity();
}
static bool reserve_sample_once13(uint32_t role,ReserveSample13& s){
 memset(&s,0,sizeof(s));uint32_t t=role_thing(role),u=role_update(role);if(!(role?support_valid():unit())||!live_member13(t,role_id(role)))return false;
 s.frame=frame();s.thing=t;s.id=word(t+0xdc);s.owner=word(t+0x418);s.template_ptr=word(t+4);s.type_hash=word(s.template_ptr+8);s.update=word(t+0x374);s.update_vtable=word(u);s.update_backref=word(u+8);s.team=word(t+0x414);
 uint32_t m=word(t+0x380);s.stance_module=m;s.stance_vtable=word(m);s.stance_backref=word(m+8);s.stance_data=word(m+4);s.stance=word(m+0x38);s.stance_enum_list=word(word(s.stance_data+8));s.stance_enum_count=word(s.stance_enum_list+4);if(!s.stance_enum_count||s.stance_enum_count>4||!read(word(s.stance_enum_list+8),s.stance_enum_entries,s.stance_enum_count*8))return false;
 s.sm=word(u+0x3c);s.sm_owner=word(s.sm+0x24);s.sm_flags=word(s.sm+0x78);s.state=word(s.sm+4);s.state_id=word(s.state+4);s.state_vtable=word(s.state);s.state_owner_sm=word(s.state+0x18);s.path=word(u+0x150);s.source=word(u+0x50);
 if(s.state_id==16||s.state_id==94){s.child_sm=word(s.state+0x20);s.child_sm_vtable=word(s.child_sm);s.child_state=word(s.child_sm+4);s.child_state_id=word(s.child_state+4);s.child_state_vtable=word(s.child_state);s.child_state_owner_sm=word(s.child_state+0x18);}
 s.holder=word(t+0x238);if(!read(t+0x80,s.status_words,28)||!read(t+0x5c,&s.height,4)||!read(word(t+0x33c)+4,&s.hp,4)||!read(t+0x38,s.xyz,12))return false;s.height_flags=word(t+0x48);
 s.auto_acquire=word(u+0x484);if(s.auto_acquire){uint16_t flags=0;read(s.auto_acquire+0x9e,&flags,2);s.auto_acquire_flags_9e=flags;s.auto_acquire_24=word(s.auto_acquire+0x24);s.auto_acquire_28=word(s.auto_acquire+0x28);s.auto_acquire_2c=word(s.auto_acquire+0x2c);s.auto_acquire_70=word(s.auto_acquire+0x70);}
 return frame()==s.frame&&finite_point(s.xyz)&&s.stance_vtable==0xc37f90&&s.stance_backref==t&&s.stance_data&&s.stance_enum_list&&(role?support_valid():unit());
}
static bool reserve_sample13(uint32_t r,ReserveSample13& s){ReserveSample13 a={},b={};if(!reserve_sample_once13(r,a)||!reserve_sample_once13(r,b)||memcmp(&a,&b,sizeof(a)))return false;s=a;return true;}
// Own-only admission-baseline risk. It requests the existing retreat exactly
// once through the caller; this proof itself issues no SDK command.
static bool mission_risk16(uint32_t now,const float hp[2],uint32_t hp_read_mask){
 if((p->mission_stage!=1&&p->mission_stage!=2)||p->controller.stage!=3||hp_read_mask!=3)return false;
 float baseline[2]={reserve_private[0].baseline.hp,reserve_private[1].baseline.hp};
 if(!reserve_private[0].baseline_set||!reserve_private[1].baseline_set||!isfinite(baseline[0])||!isfinite(baseline[1])||baseline[0]<=0||baseline[1]<=0||!isfinite(hp[0])||!isfinite(hp[1]))return false;
 float threshold[2]={baseline[0]*.70f,baseline[1]*.80f};uint32_t mask=(hp[0]<=threshold[0]?1u:0u)|(hp[1]<=threshold[1]?2u:0u);if(!mask)return false;
 ReserveSample13 sampled[2]={};uint32_t sample_mask=0;for(uint32_t r=0;r<2;r++)if(reserve_sample13(r,sampled[r])&&sampled[r].frame==now&&sampled[r].hp==hp[r])sample_mask|=1u<<r;
 for(uint32_t r=0;r<2;r++){
  uint32_t* w=reserve_proof_words;memset(w,0,512);w[0]=0x524b3136;w[1]=1;w[2]=r;w[3]=now;w[4]=p->mission_stage;w[5]=mask;w[6]=hp_read_mask;w[7]=sample_mask;
  memcpy(w+8,baseline,8);memcpy(w+10,hp,8);memcpy(w+12,threshold,8);w[14]=r?80:70;w[15]=100;w[16]=p->controller.reserve_start_frame;w[17]=p->controller.reserve_deadline_frame;w[18]=p->controller.hard_deadline_frame;w[19]=p->controller.mission_commit_frame;w[20]=p->controller.approach_frame;w[21]=3;w[22]=reserve_private[0].baseline.frame;w[23]=reserve_private[1].baseline.frame;memcpy(w+24,&sampled[r],240);event(167,mask,0,0,0,0,r,NULL,0,0,w);
 }
 return true;
}
static bool reserve_surface13(const ReserveSample13& s){return s.owner==p->owner&&s.update_vtable==0xc48670&&s.update_backref==s.thing&&word(s.update+0x24)==0xc48528&&s.sm_owner==s.thing&&s.state_owner_sm==s.sm&&!s.holder&&!(s.status_words[0]&0x181)&&!(s.status_words[1]&0x20080000)&&!(s.status_words[5]&2)&&!(s.status_words[6]&0x88000)&&(s.height_flags&4)&&isfinite(s.height)&&fabsf(s.height)<=.5f&&isfinite(s.hp)&&s.hp>0&&finite_point(s.xyz);}
static bool reserve_baseline13(const ReserveSample13& a,const ReserveSample13& b){return a.thing==b.thing&&a.id==b.id&&a.type_hash==b.type_hash&&a.owner==b.owner&&a.template_ptr==b.template_ptr&&a.update==b.update&&a.update_vtable==b.update_vtable&&a.update_backref==b.update_backref&&a.stance_module==b.stance_module&&a.stance_vtable==b.stance_vtable&&a.stance_backref==b.stance_backref&&a.stance_data==b.stance_data&&a.stance==b.stance&&a.stance_enum_list==b.stance_enum_list&&a.stance_enum_count==b.stance_enum_count&&!memcmp(a.stance_enum_entries,b.stance_enum_entries,32)&&a.hp==b.hp;}
static uint32_t reserve_team13(uint32_t r,const ReserveSample13& s){
 ReservePrivate13& v=reserve_private[r];uint32_t* w=v.team_words;memset(w,0,40);w[0]=0x544d5034;w[7]=s.frame;w[8]=v.cohort_team;w[9]=v.cohort_count;w[1]=word(s.thing+0x414);w[2]=word(w[1]+4);w[3]=word(w[2]+8);w[4]=word(s.thing+0x414);w[5]=word(w[4]+4);w[6]=word(w[5]+8);
 if(!s.team||!w[1]||!w[4]||s.team==p->script_team||w[1]==p->script_team||w[4]==p->script_team||(s.team&3)||(w[1]&3)||(w[2]&3)||(w[4]&3)||(w[5]&3)||!w[2]||!w[5]||w[3]!=p->owner||w[6]!=p->owner||frame()!=s.frame)return 3;
 return s.team!=w[1]||w[1]!=w[4]||w[2]!=w[5]?2:0;
}
static bool reserve_factory13(uint32_t r){
 const PaidSlotInput13& in=controller_frozen.slots[r];uint32_t t=in.factory;uint32_t a[10]={t,word(t+0xdc),word(t+0x418),word(t+4),0,frame(),word(t+0x38),word(t+0x3c),word(word(t+0x33c)+4),word(t)};a[4]=word(a[3]+8);float hp,xyz[3]={};memcpy(&hp,a+8,4);memcpy(xyz,a+6,8);
 if(!live_member13(t,in.factory_id)||a[9]!=0xc4db60||a[1]!=in.factory_id||a[2]!=p->owner||a[3]!=in.factory_template||a[4]!=in.factory_hash||a[4]!=0x80d4ea1e||!isfinite(hp)||hp<=0||!finite_point(xyz))return false;
 uint32_t b[10]={t,word(t+0xdc),word(t+0x418),word(t+4),0,frame(),word(t+0x38),word(t+0x3c),word(word(t+0x33c)+4),word(t)};b[4]=word(b[3]+8);if(memcmp(a,b,40))return false;memcpy(reserve_private[r].factory_words,a,40);return true;
}
static uint32_t reserve_event13(uint32_t kind,uint32_t r,const ReserveSample13& s,uint32_t arg=0){
 uint32_t* w=reserve_proof_words;memset(w,0,512);PaidSlotOutput13& out=p->slots[r];ReservePrivate13& v=reserve_private[r];w[0]=0x52533133;w[1]=1;w[2]=r;w[3]=kind;w[4]=s.frame;w[5]=out.stage;w[6]=arg;w[7]=v.cohort_count;memcpy(w+8,&s,240);memcpy(w+68,v.team_words,40);memcpy(w+78,v.factory_words,40);memcpy(w+88,v.previous.xyz,12);w[91]=v.previous.frame;memcpy(w+92,&v.baseline.hp,4);w[93]=p->controller.reserve_start_frame;w[94]=p->controller.reserve_deadline_frame;w[95]=p->controller.hard_deadline_frame;w[96]=v.observed_path;w[97]=out.receipt_observed_frame;w[98]=out.completion_observed_frame;w[99]=out.borrow_frame;w[100]=out.ready_frame;w[101]=first_borrow_role;w[102]=v.candidate_count;w[103]=out.stop_issued_frame;w[104]=out.proposal_reference_role;w[105]=out.proposal_reference_frame;w[106]=out.proposal_policy;w[107]=out.proposal_reference_thing;memcpy(w+108,out.factory_radial_basis,12);memcpy(w+111,out.first_role_actual_anchor,12);memcpy(w+114,out.proposal,12);memcpy(w+117,out.brake_xyz,12);memcpy(w+120,out.anchor,12);w[123]=p->controller.held_mask;w[124]=p->controller.ready_mask;w[125]=out.cohort_reset_count;
 return event(kind,arg,0,0,0,0,r,NULL,0,0,w);
}
static bool producer_header13(const ProductionHeader13& h){const ControllerInput13& in=controller_frozen;return h.magic==0x50434d44&&h.version==1&&h.pid==in.producer_pid&&h.thread==in.producer_thread&&h.callback_thread==in.producer_thread&&h.start_low==in.producer_start_low&&h.start_high==in.producer_start_high&&h.owner==in.producer_owner&&h.ai==in.producer_ai&&h.personality==in.producer_personality&&h.personality_id==in.producer_personality_id&&h.player_template==in.producer_player_template&&!memcmp(h.session,in.producer_session,16)&&!memcmp(h.commander,in.producer_commander,16)&&h.phase==1&&!h.stop_requested&&!h.error&&h.active<=100000&&h.count<=1024&&h.reserve_floor>=50&&h.reserve_floor<=10000&&h.total_budget>=305&&h.total_budget<=20000&&GetTickCount()-h.heartbeat<=2000;}
static bool payment_match13(uint32_t r,const ProductionReceipt13& x,uint32_t service_reserve=0){const PaidSlotInput13& in=controller_frozen.slots[r];const ProductionCommand13& c=x.command;return c.seq==in.seq&&!memcmp(c.id,in.command,16)&&!memcmp(c.task,in.task,16)&&!memcmp(c.session,p->session,16)&&!memcmp(c.commander,p->commander,16)&&c.hash==in.unit_hash&&c.factory==in.factory&&c.factory_id==in.factory_id&&c.iface==in.iface&&c.reserve>=1000&&c.reserve>=service_reserve&&c.budget>=in.expected_cost&&c.budget<=1000&&!x.updates&&x.version>0&&x.state==2&&!x.error&&x.attempted==1&&x.preserved==1&&(uint64_t)x.cash>=(uint64_t)x.cost+x.liability+c.reserve&&x.queue_id&&x.node&&x.created==1&&x.object&&x.object_id&&x.object_owner==p->owner&&x.object_hash==in.unit_hash&&x.completed==1&&x.completion_frame&&x.live_samples&&x.paid==in.expected_cost&&x.cost==in.expected_cost&&x.quoted_cost==in.expected_cost&&x.debit_count>=1&&x.debit_count<=x.paid&&!x.payment_error;}
static bool payment_equal13(ProductionReceipt13 a,ProductionReceipt13 b){a.updates=b.updates=0;a.version=b.version=0;a.live_samples=b.live_samples=0;a.object_hp_bits=b.object_hp_bits=0;a.object_x_bits=b.object_x_bits=0;a.object_y_bits=b.object_y_bits=0;a.factory_x_bits=b.factory_x_bits=0;a.factory_y_bits=b.factory_y_bits=0;return !memcmp(&a,&b,sizeof(a));}
// Read-only waiting observations. The existing retry output is a failure count,
// never an admission/SDK/paid/source credit. Sparse pairs retain original bytes.
static uint32_t producer_wait_reason14[2],producer_wait_attempt14[2];
static bool producer_wait14(uint32_t r,uint32_t reason,uint32_t captured_frame,uint32_t index,uint32_t flags,const ProductionHeader13& a,const ProductionHeader13& b,const ProductionReceipt13& first,const ProductionReceipt13& second){
 uint32_t counter=++p->controller.producer_retry_count,attempt=++producer_wait_attempt14[r];
 bool publish=producer_wait_reason14[r]!=reason||attempt==1||attempt%32==0;producer_wait_reason14[r]=reason;
 if(publish)for(uint32_t copy=0;copy<2;copy++){
  uint32_t* w=reserve_proof_words;memset(w,0,512);w[0]=0x50575431;w[1]=1;w[2]=r;w[3]=captured_frame;w[4]=reason;w[5]=counter;w[6]=flags;w[7]=index;
  memcpy(w+8,copy?&b:&a,256);memcpy(w+72,copy?&second:&first,224);event(copy?165:164,reason,0,0,0,0,r,NULL,0,0,w);
 }
 return false;
}
static bool producer_snapshot13(uint32_t r){
 uint32_t captured_frame=frame(),index=0xffffffffu,flags=0,found=0;ProductionHeader13 a={},b={};ProductionReceipt13 first={},second={};
 #define WAIT14(reason) producer_wait14(r,reason,captured_frame,index,flags,a,b,first,second)
 if(!producer_view)return WAIT14(1);
 if(!read((uintptr_t)producer_view,&a,256))return WAIT14(2);flags|=1;
 if(!producer_header13(a))return WAIT14(3);
 for(uint32_t i=0;i<a.count;i++){
  ProductionReceipt13 x={};if(!read((uintptr_t)(producer_view+256+i*224),&x,224))return WAIT14(4);
  if(x.command.seq==controller_frozen.slots[r].seq&&!memcmp(x.command.id,controller_frozen.slots[r].command,16)&&!memcmp(x.command.task,controller_frozen.slots[r].task,16)){
   if(++found!=1)return WAIT14(5);first=x;index=i;flags|=4;
  }
 }
 if(found!=1)return WAIT14(6);
 if(!read((uintptr_t)(producer_view+256+index*224),&second,224))return WAIT14(7);flags|=8;
 if(memcmp(&first,&second,224))return WAIT14(8);
 if(!payment_match13(r,first,a.reserve_floor))return WAIT14(9);
 if(!read((uintptr_t)producer_view,&b,256))return WAIT14(10);flags|=2;
 if(!producer_header13(b))return WAIT14(11);
 if(a.count!=b.count)return WAIT14(12);
 if(frame()!=captured_frame)return WAIT14(13);
 ReservePrivate13& v=reserve_private[r];PaidSlotOutput13& out=p->slots[r];if(v.receipt_bound&&!payment_equal13(first,v.payment)){p->error=71;return WAIT14(14);}if(!v.receipt_bound){v.payment=first;v.receipt_bound=true;out.receipt_observed_frame=out.completion_observed_frame=frame();out.thing=first.object;out.id=first.object_id;out.receipt_index=index;p->controller.bound_mask|=1u<<r;}
 out.receipt=first;out.receipt_version=first.version;uint32_t generation=++p->controller.producer_snapshots;producer_wait_reason14[r]=0;
 for(uint32_t copy=0;copy<2;copy++){memset(reserve_proof_words,0,512);reserve_proof_words[0]=0x52504331;reserve_proof_words[1]=1;reserve_proof_words[2]=r;reserve_proof_words[3]=frame();reserve_proof_words[4]=index;reserve_proof_words[5]=reserve_proof_words[6]=frame();reserve_proof_words[7]=generation;memcpy(reserve_proof_words+8,copy?&b:&a,256);memcpy(reserve_proof_words+72,copy?&second:&first,224);event(140,copy+1,0,0,0,0,r,NULL,0,0,reserve_proof_words);}
 #undef WAIT14
 return true;
}

static void slot_bind_mirror13(uint32_t r){PaidSlotOutput13& out=p->slots[r];if(!r){p->unit=out.thing;p->object_id=out.id;p->type_hash=0x19ab11af;p->update=out.update;}else{p->support.thing=out.thing;p->support.id=out.id;p->support.hash=0x2c358c61;p->support.update=out.update;}}
static void controller_fail13(uint32_t error,uint32_t now){p->controller.error=error;p->controller.untasked_cleanup=!commit_seen;p->controller.stage=4;if(p->controller.held_mask)request_cleanup(error,now);else{p->error=error;finish();}}
static bool slot_strict_hold13(uint32_t r,const ReserveSample13& s,const float anchor[3]){ReservePrivate13& v=reserve_private[r];return reserve_surface13(s)&&s.team==p->script_team&&s.stance==2&&s.state_id==94&&s.state_vtable==0xc551a0&&!s.path&&s.source==1&&!(s.sm_flags&0xffff)&&(!v.previous.frame||distance(s.xyz,v.previous.xyz)<=1)&&distance(s.xyz,anchor)<=15&&stance_current(r,true);}
static void slot_stop13(uint32_t r){PaidSlotOutput13& out=p->slots[r];ReservePrivate13& v=reserve_private[r];out.stop_issued_frame=frame();v.last_stop_sample=v.stop_count=0;read(role_thing(r)+0x38,v.stopped_xyz,12);stop_role(r);}
static bool slot_stopped13(uint32_t r,const ReserveSample13& s){PaidSlotOutput13& out=p->slots[r];ReservePrivate13& v=reserve_private[r];if(s.frame==v.last_stop_sample)return false;bool expected=r?(p->support.private_stop_calls==p->support.stop_calls&&s.frame>p->support.private_stop_frame):(p->private_stop_calls==p->stop_calls&&s.frame>p->private_stop_frame);bool gate=expected&&s.frame>out.stop_issued_frame&&reserve_surface13(s)&&holding_stance(s.thing,s.update)&&s.team==p->script_team&&s.source==1&&!s.path&&!(s.sm_flags&0xffff)&&distance(s.xyz,v.stopped_xyz)<=1;v.stop_count=gate&&(!v.last_stop_sample||s.frame==v.last_stop_sample+1)?v.stop_count+1:gate?1:0;v.last_stop_sample=s.frame;memcpy(v.stopped_xyz,s.xyz,12);return v.stop_count>=3;}
static float factory_gap_xy13(const float* xyz,const float* factory){float dx=xyz[0]-factory[0],dy=xyz[1]-factory[1];return sqrtf(dx*dx+dy*dy);}
static bool slot_outer13(uint32_t r,const ReserveSample13& s){PaidSlotOutput13& out=p->slots[r];float factory[3]={};memcpy(factory,reserve_private[r].factory_words+6,8);float gap=factory_gap_xy13(s.xyz,factory);return distance(s.xyz,out.initial_xyz)>=60&&gap>=120&&gap>=out.initial_factory_gap;}
static bool slot_pair_geometry13(uint32_t r,const ReserveSample13& s){if(r==first_borrow_role)return true;uint32_t a=first_borrow_role;if(a>1||p->slots[a].stage!=5)return false;ReserveSample13 other={};if(!reserve_sample13(a,other)||other.frame!=s.frame||!slot_strict_hold13(a,other,p->slots[a].anchor))return false;float gap=distance(s.xyz,other.xyz);return gap>=25&&gap<=180;}
static bool slot_propose13(uint32_t r,const ReserveSample13& s){
 PaidSlotOutput13& out=p->slots[r];float f[3]={};memcpy(f,reserve_private[r].factory_words+6,8);float dx,dy,n;
 if(r==first_borrow_role){dx=s.xyz[0]-f[0];dy=s.xyz[1]-f[1];n=sqrtf(dx*dx+dy*dy);if(!isfinite(n)||n<5)return false;out.proposal[0]=s.xyz[0]-200*dy/n;out.proposal[1]=s.xyz[1]+200*dx/n;out.proposal[2]=s.xyz[2];out.proposal_policy=1;out.proposal_reference_role=r;out.proposal_reference_frame=s.frame;out.proposal_reference_thing=s.thing;out.factory_radial_basis[0]=dx/n;out.factory_radial_basis[1]=dy/n;}
 else{const PaidSlotOutput13& first=p->slots[first_borrow_role];if(first.stage!=5)return false;dx=first.anchor[0]-f[0];dy=first.anchor[1]-f[1];n=sqrtf(dx*dx+dy*dy);if(!isfinite(n)||n<5)return false;memcpy(out.first_role_actual_anchor,first.anchor,12);out.factory_radial_basis[0]=dx/n;out.factory_radial_basis[1]=dy/n;out.proposal[0]=first.anchor[0]-80*dy/n;out.proposal[1]=first.anchor[1]+80*dx/n;out.proposal[2]=first.anchor[2];out.proposal_policy=2;out.proposal_reference_role=first_borrow_role;out.proposal_reference_frame=first.anchor_frame;out.proposal_reference_thing=first.thing;}
 if(!finite_point(out.proposal))return false;memcpy(frozen_goals[r],out.proposal,12);uint32_t seq=reserve_event13(146,r,s);if(!arm_move_ticket(r,146,seq,out.proposal))return false;memcpy(reserve_private[r].private_proposal,out.proposal,12);out.move_issued_frame=s.frame;slot_stage13(r,3);move_role(r!=0,out.proposal);return move_tickets[r].proof.delivered&&!move_tickets[r].pending&&!foreign_count(r);
}
#include "origin_scan.cpp.inc"
#ifndef NORMAL_CONTROLLER_TRANSFER
#define NORMAL_CONTROLLER_TRANSFER(owner,thing,to_ai) ((Transfer)0x838820)((void*)(uintptr_t)(owner),(void*)(uintptr_t)(thing),(to_ai))
#endif
enum AdmissionDecision15 { ADMISSION_REJECT15=0,ADMISSION_WAIT15=1,ADMISSION_ELIGIBLE15=2 };
// Same immutable owned actor evidence as the surface gate, without claiming
// ground from a factory-exit sample. Only the exact observed exit state may wait.
static bool reserve_identity_without_ground15(const ReserveSample13& s){
 return s.owner==p->owner&&s.update_vtable==0xc48670&&s.update_backref==s.thing&&word(s.update+0x24)==0xc48528&&s.sm_owner==s.thing&&s.state_owner_sm==s.sm&&!s.holder&&!(s.status_words[0]&0x181)&&!(s.status_words[1]&0x20080000)&&!(s.status_words[5]&2)&&!(s.status_words[6]&0x88000)&&isfinite(s.height)&&fabsf(s.height)<=.5f&&isfinite(s.hp)&&finite_point(s.xyz);
}
static AdmissionDecision15 reserve_admission15(uint32_t r,const ReserveSample13& s,uint32_t& wait_reason){
 wait_reason=0;const ReservePrivate13& v=reserve_private[r];
 bool original_base=reserve_surface13(s)&&s.source<=3&&s.hp>=(r?96:80)&&s.stance==0&&s.team&&s.team!=p->script_team;
 bool eligible=original_base&&!(s.sm_flags&0xffff)&&(s.state_id==1||(s.state_id==16&&!s.path)||(s.state_id==10&&s.state_vtable==0xc548c0));
 if(eligible)return ADMISSION_ELIGIBLE15;
 if(v.baseline_set)return ADMISSION_REJECT15;
 bool spawn_wait=reserve_identity_without_ground15(s)&&s.hp>=(r?96:80)&&s.stance==0&&s.team&&s.team!=p->script_team&&!(s.sm_flags&0xffff)&&s.state_id==7&&s.state_vtable==0xc57a68&&s.source==2&&s.height_flags==1;
 if(spawn_wait){wait_reason=1;return ADMISSION_WAIT15;}
 if(original_base&&(s.state_id==7||s.state_id==96||s.state_id==26)){wait_reason=2;return ADMISSION_WAIT15;}
 return ADMISSION_REJECT15;
}
static bool slot_cohort13(uint32_t r,const ReserveSample13& s){
 PaidSlotOutput13& out=p->slots[r];ReservePrivate13& v=reserve_private[r];uint32_t now=s.frame;
 if(now<out.receipt.completion_frame||now-out.receipt.completion_frame>300||now<out.completion_observed_frame||now-out.completion_observed_frame>300)return false;
 float f[3]={};memcpy(f,v.factory_words+6,8);float initialgap=factory_gap_xy13(s.xyz,f);if(!isfinite(initialgap)||initialgap>200)return false;
 uint32_t wait_reason=0;AdmissionDecision15 decision=reserve_admission15(r,s,wait_reason);
 if(decision==ADMISSION_REJECT15){reserve_event13(141,r,s,0);return false;}
 if(decision==ADMISSION_WAIT15){uint32_t team=reserve_team13(r,s);if(team>=3){reserve_event13(143,r,s,team);return false;}reserve_event13(166,r,s,team==2?3:wait_reason);return true;}
 if(!origin_scan13(r,s)){reserve_event13(141,r,s,0);return !v.baseline_set;}
 if(!v.baseline_set){v.baseline=s;v.baseline_set=true;}else if(!reserve_baseline13(v.baseline,s))return false;
 uint32_t team=reserve_team13(r,s);if(team>=3){reserve_event13(143,r,s,team);return false;}
 if(team==2||(v.cohort_count&&v.cohort_team!=s.team)){reserve_event13(142,r,s,team==2?2:1);out.cohort_reset_count++;v.cohort_count=v.cohort_team=0;out.cohort_count=out.cohort_first_frame=out.cohort_last_frame=0;if(team==2)return true;}
 if(!v.cohort_count){v.cohort_team=s.team;out.admission_first=s;out.cohort_first_frame=now;}
 v.cohort_count++;out.cohort_count=v.cohort_count;out.cohort_last_frame=now;out.admission_last=s;reserve_event13(141,r,s,v.cohort_count);if(v.cohort_count<3)return true;
 if(reserve_team13(r,s)||word(s.thing+0x414)!=s.team)return false;out.admitted_team=s.team;reserve_event13(144,r,s,3);
 if(word(p->owner+0xac)!=p->default_team||word(word(p->owner+0x8c)+0x10)!=p->script_team)return false;
 if(!p->controller.clock_frozen){p->controller.clock_frozen=1;p->controller.reserve_start_frame=now;p->controller.reserve_deadline_frame=now+450;p->controller.hard_deadline_frame=now+4500;p->controller.lease_issued_frame=now;reserve_clock_start13=now;reserve_clock_deadline13=now+450;lease_clock_deadline13=now+4500;frozen_deadline=p->mission_deadline_frame=now+4500;p->issued_frame=now;start_tick=GetTickCount();first_borrow_role=r;reserve_event13(145,r,s);}
 if(now>=p->controller.reserve_deadline_frame)return false;
 if(!capture_stance(r))return false;event(71,0,0,0,0,0,r);
 if(!r)p->original_team=s.team;else p->support.original_team=s.team;
 tag=1;if(r)p->support.detach_calls++;else p->detach_calls++;out.borrow_frame=now;p->controller.held_mask|=1u<<r;NORMAL_CONTROLLER_TRANSFER(p->owner,s.thing,0);event(1,0,0,0,0,0,r);tag=0;
 if(word(s.thing+0x414)!=p->script_team||!change_stance(r,false))return false;
 out.initial_factory_gap=v.private_initial_gap=initialgap;memcpy(out.initial_xyz,s.xyz,12);memcpy(v.private_initial,s.xyz,12);slot_stage13(r,2);slot_stop13(r);return true;
}
static bool reserve_slot_tick13(uint32_t r,uint32_t now){
 PaidSlotOutput13& out=p->slots[r];ReservePrivate13& v=reserve_private[r];
 if(out.stage<=1){if(!producer_snapshot13(r)){if(p->error)return false;return true;}if(!live_member13(out.thing,out.id))return true;out.template_ptr=word(out.thing+4);out.update=word(out.thing+0x374);slot_bind_mirror13(r);slot_stage13(r,1);}
 if(out.stage>=6)return true;
 ReserveSample13 s={};if(!reserve_sample13(r,s))return false;out.last_sample=s;
 if(v.last_observed&&now==v.last_observed)return true;if(v.last_observed&&now!=v.last_observed+1)return false;v.last_observed=now;
 if(!reserve_factory13(r))return false;
 if(out.stage>1)reserve_team13(r,s);reserve_event13(163,r,s);
 bool okay=true;if(out.stage==1)okay=slot_cohort13(r,s);
 else{
  if(!reserve_surface13(s)||s.team!=p->script_team||s.stance!=2||(s.sm_flags&0xffff)||s.state_id==26||!stance_current(r,true)||!reserve_factory13(r))return false;
  if(out.stage==2){if(slot_stopped13(r,s)){if(!v.initial_ready){v.initial_ready=1;memcpy(out.initial_xyz,s.xyz,12);memcpy(v.private_initial,s.xyz,12);}if(first_borrow_role==r||p->slots[first_borrow_role].stage==5)okay=slot_propose13(r,s);}else if(now-out.stop_issued_frame>60)return false;}
  else if(out.stage==3){
   if(now-out.move_issued_frame>90)return false;
   if(s.path&3)return false;if(v.observed_path&&s.path&&v.observed_path!=s.path)return false;
   if(!v.observed_path&&s.state_id==1&&s.state_vtable==0xc55598&&s.source==1&&s.path){v.observed_path=out.observed_path=s.path;out.observed_path_frame=now;reserve_event13(147,r,s,s.path);}
   bool mode=(s.state_id==1&&s.state_vtable==0xc55598&&v.observed_path&&s.path==v.observed_path)||(s.state_id==94&&s.state_vtable==0xc551a0&&!s.path);
   bool eligible=mode&&s.source==1&&slot_outer13(r,s)&&slot_pair_geometry13(r,s);
   bool consecutive=v.candidate_count&&now==v.last_candidate_frame+1&&distance(s.xyz,v.last_candidate_xyz)<=5;
   v.candidate_count=eligible?(consecutive?v.candidate_count+1:1):0;v.last_candidate_frame=now;memcpy(v.last_candidate_xyz,s.xyz,12);out.brake_count=v.candidate_count;
   if(v.candidate_count){reserve_event13(148,r,s,v.candidate_count);if(v.candidate_count>=3){memcpy(out.brake_xyz,s.xyz,12);memcpy(v.private_brake,s.xyz,12);out.brake_frame=now;reserve_event13(149,r,s,3);slot_stage13(r,4);slot_stop13(r);}}
  }
  else if(out.stage==4){if(slot_stopped13(r,s)){if(!slot_outer13(r,s)||distance(s.xyz,out.brake_xyz)>15||!slot_pair_geometry13(r,s))return false;memcpy(out.anchor,s.xyz,12);memcpy(v.private_anchor,s.xyz,12);out.anchor_frame=out.ready_frame=now;slot_stage13(r,5);out.hold_first_frame=out.hold_last_frame=now;out.hold_samples=1;p->controller.ready_mask|=1u<<r;reserve_event13(150,r,s,3);reserve_event13(151,r,s,3);}else if(now-out.stop_issued_frame>60)return false;}
  else if(out.stage==5){uint32_t gap=now-out.hold_last_frame;if(gap>out.hold_max_gap)out.hold_max_gap=gap;out.hold_last_frame=now;out.hold_samples++;float drift=distance(s.xyz,out.anchor);if(drift>out.max_hold_drift)out.max_hold_drift=drift;okay=gap==1&&slot_strict_hold13(r,s,out.anchor);if(!okay)out.hold_failed=1;reserve_event13(155,r,s,okay?1:0);}
 }
 v.previous=s;return okay;
}

static bool controller_pair_ready13(uint32_t now){
 if(p->controller.held_mask!=3||p->controller.ready_mask!=3)return false;ReserveSample13 a={},b={};if(!reserve_sample13(0,a)||!reserve_sample13(1,b)||a.frame!=now||b.frame!=now||!slot_strict_hold13(0,a,p->slots[0].anchor)||!slot_strict_hold13(1,b,p->slots[1].anchor))return false;float gap=distance(a.xyz,b.xyz),homegap=distance(p->slots[0].anchor,p->slots[1].anchor);return gap>=25&&gap<=180&&homegap>=25&&homegap<=180;
}
static bool mission_body_identity13(const MissionCommitBody13& b){return !memcmp(b.controller,controller_frozen.controller,16)&&!memcmp(b.lease,controller_frozen.lease,16)&&!memcmp(b.formation,controller_frozen.formation,16)&&b.formation_version==controller_frozen.formation_version&&nonzero_uuid13(b.parent_command)&&nonzero_uuid13(b.parent_task)&&nonzero_uuid13(b.command)&&nonzero_uuid13(b.task)&&b.seq&&b.front_id==p->slots[0].id&&b.support_id==p->slots[1].id&&b.front_id!=b.support_id&&b.module==1&&b.purpose==1&&b.allocation_scope==1&&b.force_numerator==1&&b.force_denominator==1&&b.reserve_start_frame==p->controller.reserve_start_frame&&b.reserve_deadline_frame==p->controller.reserve_deadline_frame&&b.hard_deadline_frame==p->controller.hard_deadline_frame&&b.combat_frames>=30&&b.combat_frames<=300;}
static bool accept_commit13(uint32_t now){
 uint32_t generation=p->mission_commit.generation;if(!generation)return true;if(generation!=2)return false;MissionCommitBody13 body={};MemoryBarrier();memcpy(&body,&p->mission_commit.body,sizeof(body));MemoryBarrier();if(p->mission_commit.generation!=generation)return false;
 if(commit_seen)return !memcmp(&body,&accepted_commit,sizeof(body));
 if(!controller_pair_ready13(now)||now>=p->controller.reserve_deadline_frame||!mission_body_identity13(body)||body.target_observed_frame>now||now-body.target_observed_frame>60||!body.threat_clear||body.threat_frame>now||now-body.threat_frame>60||!finite_point(body.visible_target)||!nonzero_uuid13(body.visibility_proof_sha256)||!nonzero_uuid13(body.digest_sha256))return false;
 p->target_unit=body.target_unit;p->target_id=body.target_id;p->target_hash=body.target_hash;p->target_owner=body.target_owner;p->target_template=body.target_template;p->target_observed_frame=body.target_observed_frame;p->button=body.button;p->button_schema=body.button_schema;p->command_set=body.command_set;
 if(!positive_native_surface(p->unit)||!positive_native_surface(p->support.thing)||!visible_target()||!button_identity())return false;
 accepted_commit=body;commit_seen=true;p->mission_commit.status=1;p->mission_commit.reason=0;p->mission_commit.ack_frame=now;p->controller.mission_commit_frame=now;reserve_event13(153,0,p->slots[0].last_sample,body.seq);
 // Continue the actual same lease. No capture/set/Transfer occurs here.
 frozen_route_count=0;memset(frozen_route,0,sizeof(frozen_route));frozen_deadline=p->controller.hard_deadline_frame;frozen_lease_frames=4500;p->lease_frames=4500;p->mission_deadline_frame=frozen_deadline;p->combat_frames=body.combat_frames;p->planning_threat_clear=body.threat_clear;p->planning_threat_frame=body.threat_frame;
 memset(frozen_crumbs,0,sizeof(frozen_crumbs));memset(frozen_crumb_counts,0,sizeof(frozen_crumb_counts));memset(last_progress,0,sizeof(last_progress));memset(last_pose_frame,0,sizeof(last_pose_frame));memset(role_arrivals,0,sizeof(role_arrivals));memset(last_arrival_frame,0,sizeof(last_arrival_frame));frozen_follow_role=0;frozen_follow_index=0xffffffffu;regroup_phase=phase_regroups=wait_reanchor_count=0;memset(&reanchor_surface,0,sizeof(reanchor_surface));retreat_departure_used=retreat_departure_active=false;retreat_departure_frame=0;retreat_departure_gap=0;memset(&retreat_departure_origin,0,sizeof(retreat_departure_origin));invalidate_move_tickets(5);memset(move_tickets,0,sizeof(move_tickets));clear_move_context();
 for(uint32_t r=0;r<2;r++){memcpy(frozen_origins[r],p->slots[r].anchor,12);slot_stage13(r,6);}memcpy(p->safe_front,frozen_origins[0],12);memcpy(p->safe_support,frozen_origins[1],12);
 read(p->target_unit+0x38,memory_target,12);memcpy(p->target,memory_target,12);memory_seen_frame=now;memcpy(p->last_seen_target,memory_target,12);p->target_last_seen_frame=now;memory_hidden=false;p->initial_target_distance=distance(frozen_origins[0],memory_target);p->approach_distance=p->initial_target_distance;
 p->mission_stage=1;p->trail_phase=1;p->leader_role=0;p->follower_role=1;p->motion_state=0;p->nav_frame=now;p->motion_last_tick=0;p->controller.stage=3;p->controller.approach_frame=now;stop_both(5);event(76);event(76,0,0,0,0,0,1);return true;
}
static bool controller_input_valid13(){
 const ControllerInput13& in=p->controller_input;if(!p->default_team||!p->script_team||p->default_team==p->script_team||word(p->owner+0xac)!=p->default_team||word(word(p->owner+0x8c)+0x10)!=p->script_team)return false;
 if(in.schema!=1||!nonzero_uuid13(in.controller)||!nonzero_uuid13(in.lease)||!nonzero_uuid13(in.formation)||!in.formation_version||memcmp(in.controller,p->command,16)||memcmp(in.lease,p->task,16)||in.reserve_duration_frames!=450||in.lease_duration_frames!=4500||in.reserve_floor!=1000||in.total_paid_max!=305||in.slot_count!=2||in.allocation_scope!=1||in.force_numerator!=1||in.force_denominator!=1||in.startup_deadline_frame<=frame()||in.startup_deadline_frame-frame()>900||!in.startup_wall_ms||in.startup_wall_ms>60000)return false;
 if(in.producer_pid!=p->pid||in.producer_thread!=p->thread||in.producer_start_low!=p->start_low||in.producer_start_high!=p->start_high||in.producer_owner!=p->owner||in.producer_ai!=p->ai||in.producer_personality!=p->personality||in.producer_personality_id!=p->personality_id||in.producer_player_template!=p->player_template||memcmp(in.producer_session,p->session,16)||memcmp(in.producer_commander,p->commander,16))return false;
 for(uint32_t r=0;r<2;r++){const PaidSlotInput13& s=in.slots[r];if(s.role!=r||!nonzero_uuid13(s.command)||!nonzero_uuid13(s.task)||!s.seq||s.unit_hash!=(r?0x2c358c61u:0x19ab11afu)||s.expected_cost!=(r?220u:85u)||!s.factory||!s.factory_id||!s.factory_template||s.factory_hash!=0x80d4ea1e||!s.iface||(s.factory&3)||(s.iface&3))return false;}
 return in.slots[0].seq!=in.slots[1].seq&&memcmp(in.slots[0].command,in.slots[1].command,16)&&memcmp(in.slots[0].task,in.slots[1].task,16);
}
static bool controller_start13(){
 if(!controller_input_valid13())return false;captured_initial_asset13=captured_initial_entry13=0;if(p->initial_weapon_asset||p->initial_weapon_entry)return false;controller_frozen=p->controller_input;memcpy(controller_binding13,p,sizeof(controller_binding13));reserve_clock_start13=reserve_clock_deadline13=lease_clock_deadline13=0;memset(reserve_private,0,sizeof(reserve_private));memset(&accepted_commit,0,sizeof(accepted_commit));commit_seen=false;first_borrow_role=2;controller_core_tick=0;memset(producer_wait_reason14,0,sizeof(producer_wait_reason14));memset(producer_wait_attempt14,0,sizeof(producer_wait_attempt14));origin_generation=0;memset(origin_last_generation,0,sizeof(origin_last_generation));
 memset(move_tickets,0,sizeof(move_tickets));memset(move_generations,0,sizeof(move_generations));memset(&lineage_record,0,sizeof(lineage_record));clear_move_context();
 memset(frozen_stances,0,sizeof(frozen_stances));memset(stance_operation,0,sizeof(stance_operation));memset(stance_entered,0,sizeof(stance_entered));
 memset(frozen_crumbs,0,sizeof(frozen_crumbs));memset(frozen_crumb_counts,0,sizeof(frozen_crumb_counts));frozen_follow_role=0;frozen_follow_index=0xffffffffu;memset(frozen_goals,0,sizeof(frozen_goals));memset(frozen_origins,0,sizeof(frozen_origins));
 controller_install_tick=GetTickCount();p->controller.stage=1;p->controller.channel_claimed=1;p->controller.scope_verified=1;
 if(p->unit||p->object_id||p->update||p->support.thing||p->support.id||p->support.update||p->target_unit||p->target_id||p->mission_commit.generation)return false;
 char name[100];snprintf(name,sizeof(name),"Local\\RA3ProductionPersistent_%lu",p->pid);producer_mapping=OpenFileMappingA(FILE_MAP_READ,FALSE,name);if(!producer_mapping)return false;producer_view=(const BYTE*)MapViewOfFile(producer_mapping,FILE_MAP_READ,0,0,256+224*1024);if(!producer_view){controller_close();return false;}return true;
}
static void mission_tick_body(){
 if(!identity()){p->error=31;finish();return;}uint32_t now=frame();
 if(p->controller.stage==4||p->phase==7){legacy_mission_tick_body();return;}
 if(!controller_bound()||!slot_runtime_bound13()){controller_fail13(72,now);return;}
 if(commit_seen&&(p->mission_commit.generation!=2||memcmp(&p->mission_commit.body,&accepted_commit,sizeof(accepted_commit)))){controller_fail13(73,now);return;}
 if(p->controller.stage==3){if(GetTickCount()-controller_core_tick<100)return;controller_core_tick=GetTickCount();legacy_mission_tick_body();return;}
 if(p->stop_requested||GetTickCount()-p->heartbeat_tick>5000){controller_fail13(49,now);return;}
 if(p->controller.clock_frozen){if(now>=p->controller.reserve_deadline_frame||now>=p->controller.hard_deadline_frame||GetTickCount()-start_tick>30000){controller_fail13(74,now);return;}}
 else if(now>=controller_frozen.startup_deadline_frame||GetTickCount()-controller_install_tick>controller_frozen.startup_wall_ms){controller_fail13(75,now);return;}
 if(!no_override()){controller_fail13(38,now);return;}
 for(uint32_t r=0;r<2;r++){if(!reserve_slot_tick13(r,now)){p->slots[r].error=p->error?p->error:76;controller_fail13(p->slots[r].error,now);return;}}
 if(p->controller.ready_mask==3){if(!controller_pair_ready13(now)){controller_fail13(77,now);return;}if(!p->controller.pair_ready_frame){p->controller.pair_ready_frame=now;p->controller.stage=2;reserve_event13(152,0,p->slots[0].last_sample);}}
 if(p->mission_commit.generation&&!accept_commit13(now)){p->mission_commit.status=2;p->mission_commit.reason=78;p->mission_commit.ack_frame=now;reserve_event13(154,0,p->slots[0].last_sample,78);controller_fail13(78,now);}
}
