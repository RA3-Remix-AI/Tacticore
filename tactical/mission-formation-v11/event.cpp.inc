static bool visible_target();
static uint32_t event(uint32_t kind,uint32_t arg=0,uint32_t caller=0,float before=0,float after=0,float reported=0,uint32_t role=0,const float* input=NULL,uint32_t input_path=0,float input_limit=0,const uint32_t* diagnostic=NULL){
 LONG i=InterlockedIncrement(&p->count)-1;if(i>=T_CAP){p->overflow=1;return 0;}
 uint32_t thing=role?p->support.thing:p->unit,update=role?p->support.update:p->update,id=role?p->support.id:p->object_id;
 Event e={};e.kind=kind;e.tag=tag;e.frame=frame();e.tick=GetTickCount();e.thread=GetCurrentThreadId();e.caller=caller;e.arg=arg;e.role=role;e.unit_id=id;e.mission_stage=p->mission_stage;e.route_index=p->route_index;e.nav_step=p->nav_step;e.mission_deadline_frame=p->mission_deadline_frame;e.mission_reason=p->retreat_reason;e.native_error=p->error;
 e.team=word(thing+0x414);e.owner=word(thing+0x418);e.source=word(update+0x50);e.lease_stage=p->lease_stage;e.arg_shots=observed_shots;e.arg_source=observed_source;
 if(kind==20||kind==21||kind==22||kind==24||kind==25){e.target_id=p->target_id;e.damage_source=arg;e.damage_before=before;e.damage_after=after;e.damage_reported=reported;}
 if(word(thing)==0xc4db60&&word(thing+0xdc)==id&&word(thing+0x418)==p->owner){read(thing+0x38,&e.x,12);read(word(thing+0x33c)+4,&e.own_hp,4);}
 e.sm=word(update+0x3c);e.sm_flags=word(e.sm+0x78);e.state=word(e.sm+4);e.state_id=word(e.state+4);e.path=word(update+0x150);e.holder=word(thing+0x238);read(e.sm+0x2c,e.requested,12);read(e.sm+0x48,e.effective,12);
 if(kind==20||kind==21||kind==24||kind==25){void* frames[12]={};e.stack_count=CaptureStackBackTrace(0,12,frames,NULL);for(unsigned j=0;j<e.stack_count;j++)e.stack[j]=(uintptr_t)frames[j];e.stack_words_address=(uintptr_t)__builtin_frame_address(0)+4;e.stack_word_count=read(e.stack_words_address,e.stack_words,sizeof(e.stack_words))?128:0;}
 if(!role)e.active_weapon_asset=current_weapon(&e.active_weapon_entry,&e.active_weapon_ammo);
 e.status84=word(thing+0x84);e.target_visible=visible_target();if(e.target_visible)read(p->target_unit+0x38,e.visible_target_xyz,12);memcpy(e.front_goal,p->front_goal,12);memcpy(e.support_goal,p->support_goal,12);if(input)read((uintptr_t)input,e.command_xyz,12);e.argument_path=input_path;e.argument_limit=input_limit;
 e.planning_ready=p->planning_ready;e.route_ready=p->route_ready;e.route_generation=p->route_committed_generation;e.route_commit_frame=p->route_commit_frame;e.planning_ready_frame=p->planning_ready_frame;e.committed_route_count=frozen_route_count;memcpy(e.planning_front,p->planning_front,12);memcpy(e.planning_support,p->planning_support,12);if(kind==74&&arg<frozen_route_count)memcpy(e.committed_route_xyz,frozen_route[arg],12);
 e.leader_role=p->leader_role;e.follower_role=p->follower_role;e.follow_active=p->follow_active;e.follow_crumb_role=p->follow_crumb_role;e.follow_crumb_index=p->follow_crumb_index;e.motion_state=p->motion_state;e.regroup_count=p->regroup_count;e.target_last_seen_frame=p->target_last_seen_frame;e.memory_wait_started=p->memory_wait_started;e.actual_gap=p->actual_gap;memcpy(e.last_seen_target,p->last_seen_target,12);memcpy(e.leader_hold_xyz,p->leader_hold_xyz,12);
 if(kind==98||kind==99)e.breadcrumb=retreat_departure_origin;
 else if(kind==97)e.breadcrumb=reanchor_surface;
 else if(kind==80&&role<2&&arg<frozen_crumb_counts[role]){frozen_crumbs[role][arg].published_seq=i+1;p->crumbs[role][arg]=frozen_crumbs[role][arg];e.breadcrumb=frozen_crumbs[role][arg];}
 else if(frozen_follow_role<2&&frozen_follow_index<frozen_crumb_counts[frozen_follow_role])e.breadcrumb=frozen_crumbs[frozen_follow_role][frozen_follow_index];
 if(kind>=110&&kind<=120)e.lineage=lineage_record;
 if(kind>=121&&kind<=123){e.stack_count=0;e.stack_word_count=24;memcpy(e.stack_words,schedule_proof,sizeof(schedule_proof));}
 if((kind==124||kind==125)&&diagnostic){e.stack_count=0;e.stack_word_count=80;memcpy(e.stack_words,diagnostic,80*4);}
 p->events[i]=e;MemoryBarrier();InterlockedExchange((LONG*)&p->events[i].seq,i+1);
 return i+1;
}
