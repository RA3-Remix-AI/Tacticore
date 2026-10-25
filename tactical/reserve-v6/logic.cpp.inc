// Shared with the pure fake-engine harness. All actual SDK adapters live in lease.cpp.
static bool surface(const Sample& s){return s.id==p->object_id&&s.owner==p->owner&&s.update==p->update&&s.sm_owner==p->thing&&s.state_owner_sm==s.sm&&!s.holder&&!(s.status_words[0]&0x181)&&!(s.status_words[1]&0x20080000)&&!(s.status_words[5]&2)&&!(s.status_words[6]&0x88000)&&(s.height_flags&4)&&isfinite(s.height)&&fabsf(s.height)<=.5f&&isfinite(s.hp)&&s.hp>0&&finite_xyz(s.xyz);}

static bool admission_equal(const Sample& a,const Sample& b){
 return a.thing==b.thing&&a.id==b.id&&a.type_hash==b.type_hash&&a.owner==b.owner&&a.template_ptr==b.template_ptr&&a.update==b.update&&a.update_vtable==b.update_vtable&&a.update_backref==b.update_backref&&a.stance_module==b.stance_module&&a.stance_vtable==b.stance_vtable&&a.stance_backref==b.stance_backref&&a.stance_data==b.stance_data&&a.stance==b.stance&&a.stance_enum_list==b.stance_enum_list&&a.stance_enum_count==b.stance_enum_count&&!memcmp(a.stance_enum_entries,b.stance_enum_entries,sizeof(a.stance_enum_entries))&&a.hp==b.hp;
}
static bool stopped(const Sample& s){if(s.frame==p->last_sample_frame)return false;p->last_sample_frame=s.frame;bool gate=p->private_explicit_stops==p->explicit_stops&&s.frame>p->private_stop_frame&&s.source==1&&!(s.sm_flags&0xffff)&&!s.path&&s.stance==2&&s.state_id==94&&s.state_vtable==0xc551a0&&surface(s)&&s.team==p->script_team;float d=distance(s.xyz,p->stopped_xyz);p->stable_samples=gate&&d<=1?p->stable_samples+1:0;memcpy(p->stopped_xyz,s.xyz,12);return p->stable_samples>=3;}
static void restore_return(){p->stage=4;if(!actor()){p->error=p->error?p->error:32;finish();return;}p->restore_before_enum=module()?word(p->stance_module+0x38):0xffffffffu;emit(44,p->original_stance);if(module()){if(p->stance_changed){bool okay=set_stance(p->original_stance,5);p->restore_after_enum=module()?word(p->stance_module+0x38):0xffffffffu;p->stance_restored=okay&&p->restore_after_enum==p->original_stance;if(!p->stance_restored&&!p->error)p->error=46;}else{p->restore_after_enum=p->restore_before_enum;p->stance_restored=p->restore_after_enum==p->original_stance;}}else{p->restore_after_enum=0xffffffffu;p->stance_restored=0;if(!p->error)p->error=46;}emit(45,p->original_stance);if(!actor()){p->error=p->error?p->error:32;finish();return;}p->pool_before_enum=module()?word(p->stance_module+0x38):0xffffffffu;emit(46);transfer(1);p->pool_after_enum=module()?word(p->stance_module+0x38):0xffffffffu;p->return_verified=actor()&&word(p->thing+0x414)==p->default_team;p->returned_frame=frame();emit(47);if(!p->return_verified&&!p->error)p->error=47;finish();}
static void probe_body(){
 uint32_t now=frame();if(!world()){p->scene_changed=1;p->error=p->error?p->error:31;finish();return;}if(!actor()){p->disposed=1;p->error=p->error?p->error:32;finish();return;}
 if(!factory()){if(!p->detach_calls){p->error=51;finish();return;}cleanup(51);}
 if(!module()){if(!p->detach_calls){p->error=36;finish();return;}cleanup(36);if(now-p->stop_issue_frame>60||now>=p->expires_frame||GetTickCount()-start_tick>30000)restore_return();return;}
 Sample s={};if(!sample(s)){p->error=p->error?p->error:33;if(p->detach_calls){cleanup(p->error);if(now-p->stop_issue_frame>60||now>=p->expires_frame||GetTickCount()-start_tick>30000)restore_return();}else finish();return;}emit(3);
 if(p->phase==5){
  if(GetTickCount()-start_tick>30000||GetTickCount()-p->heartbeat_tick>2000){p->error=40;finish();return;}
  if(!p->rally.factory_source_frame||p->rally.factory_source_frame>now||now-p->rally.factory_source_frame>60){p->error=51;finish();return;}
  bool known=p->type_hash==0x19ab11af||p->type_hash==0x2c358c61;float hp_floor=p->type_hash==0x19ab11af?80:96;
  bool state=s.state_id==1||(s.state_id==16&&!s.path)||(s.state_id==10&&s.state_vtable==0xc548c0);
  bool enum0=false,enum2=false;for(uint32_t i=0;i<s.stance_enum_count;i++){enum0|=s.stance_enum_entries[2*i]==0;enum2|=s.stance_enum_entries[2*i]==2;}
  if(!known||!surface(s)||s.hp<hp_floor||!state||(s.sm_flags&0xffff)||s.stance!=0||!enum0||!enum2||p->test_stance!=2||p->stop_requested||now<p->observed_frame||now-p->observed_frame>60||p->expires_frame<=now||p->expires_frame-now>300||p->expires_frame-now<210||word(p->owner+0xac)!=p->default_team||word(word(p->owner+0x8c)+0x10)!=p->script_team){p->error=34;finish();return;}
  bool production_command=false,production_task=false,production_hash=false;
  for(unsigned i=0;i<4;i++){production_command|=p->production_command[i]!=0;production_task|=p->production_task[i]!=0;}
  for(unsigned i=0;i<8;i++)production_hash|=p->production_receipt_sha256[i]!=0;
  if(!production_command||!production_task||!production_hash||!p->production_seq||!p->production_queue_id||!p->production_birth_frame||p->production_birth_frame>p->observed_frame||p->production_paid!=(p->type_hash==0x19ab11af?85u:220u)){p->error=50;finish();return;}
  if(!reserve3_admission(s)){p->error=58;finish();return;}
  if(now-p->observed_frame>30){p->error=48;finish();return;}
  int admission=admission4_collect(s);
  if(admission<0){finish();return;}if(!admission)return;
  p->admission_verified=1;emit(61,3,0,0,0,0,NULL,&s);
  if(!admitted_team||admitted_team!=s.team){p->error=60;finish();return;}
  p->initial_sample=s;p->original_stance=s.stance;p->issued_frame=now;p->phase=1;transfer(0);emit(1);
  if(word(p->thing+0x414)!=p->script_team){cleanup(35);return;}
  bool changed=set_stance(2,2);p->stance_changed=module()&&word(p->stance_module+0x38)!=p->original_stance;
  if(!changed){cleanup(36);return;}p->stage=1;stop(3);return;
 }
 bool timeout=now>=p->expires_frame||GetTickCount()-start_tick>30000||GetTickCount()-p->heartbeat_tick>2000||p->stop_requested;
 if(timeout&&p->stage!=3&&p->stage!=4&&p->stage!=5)cleanup(40);
 if(p->stage!=3&&p->stage!=4&&p->stage!=5&&s.state_id==26)cleanup(57);
 if(rally_failed()&&p->stage!=3&&p->stage!=4&&p->stage!=5)cleanup(52);
 if((p->stage==6||p->stage==7||p->stage==2)&&!rally_goal_bound())cleanup(53);
 if(p->stage==2&&!actual_anchor_bound())cleanup(59);
 if(p->stage==1){if(stopped(s)){p->initial_stop_verified=1;if(!propose_rally(s)){cleanup(53);return;}p->stage=6;p->rally.rally_issue_frame=now;if(!move_rally())cleanup(52);}else if(now-p->stop_issue_frame>60)cleanup(41);return;}
 if(p->stage==6){
  if(now-p->rally.rally_issue_frame>90){cleanup(55);return;}
  if(!observe_command_state_path(s)){cleanup(54);return;}
  bool eligible=surface(s)&&s.stance==2&&s.source==1&&!(s.sm_flags&0xffff)&&s.team==p->script_team;
  if(!eligible){cleanup(54);return;}
  bool goal_close=distance(s.xyz,p->rally.goal)<=15;
  if(now!=p->rally.last_arrival_frame){p->rally.arrival_samples=goal_close&&(!p->rally.arrival_samples||now==p->rally.last_arrival_frame+1)?p->rally.arrival_samples+1:goal_close?1:0;p->rally.last_arrival_frame=now;}
  p->anchor.proposal_distance=distance(s.xyz,p->rally.goal);
  if(p->rally.arrival_samples>=3&&!p->rally.rally_reached_frame){p->rally.rally_reached_frame=now;p->anchor.proposal_reached=1;emit(63,3);}
  if(anchor_candidate_tick(s)){p->stage=7;p->rally.rally_stop_frame=now;stop(8);return;}
  return;
 }
 if(p->stage==7){if(stopped(s)&&anchor_commit(s)){p->rally.rally_stop_verified=1;emit(68,3);emit(72,3);p->stage=2;p->hold_started=p->hold_first_frame=p->hold_last_frame=now;p->hold_samples=1;memcpy(p->hold_anchor,s.xyz,12);emit(40);}else if(now-p->stop_issue_frame>60)cleanup(56);return;}
 if(p->stage==2){
  uint32_t gap=now-p->hold_last_frame;p->hold_max_gap=gap>p->hold_max_gap?gap:p->hold_max_gap;if(gap>1)p->hold_missing_frames+=gap-1;p->hold_last_frame=now;p->hold_samples++;
  float drift=distance(s.xyz,p->hold_anchor);if(drift>p->max_hold_drift)p->max_hold_drift=drift;
  bool okay=gap==1&&surface(s)&&s.stance==2&&s.state_id==94&&s.state_vtable==0xc551a0&&!s.path&&s.source==1&&!(s.sm_flags&0xffff)&&distance(s.xyz,p->stopped_xyz)<=1&&drift<=15&&s.team==p->script_team;
  memcpy(p->stopped_xyz,s.xyz,12);if(!okay){cleanup(42);return;}if(now-p->hold_started>=90){p->hold_finished=now;p->hold_verified=1;emit(41);cleanup(0);}return;
 }
 if(p->stage==3){if(stopped(s)){p->cleanup_stop_verified=1;emit(42);restore_return();}else if(now-p->stop_issue_frame>60||now>=p->expires_frame||GetTickCount()-start_tick>30000){if(!p->error)p->error=43;emit(43);restore_return();}return;}
}
