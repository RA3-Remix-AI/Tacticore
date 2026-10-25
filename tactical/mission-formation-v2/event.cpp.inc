static bool visible_target();
static void event(uint32_t kind,uint32_t arg=0,uint32_t caller=0,float before=0,float after=0,float reported=0,uint32_t role=0,const float* input=NULL,uint32_t input_path=0,float input_limit=0){
 LONG i=InterlockedIncrement(&p->count)-1;if(i>=T_CAP){p->overflow=1;return;}
 uint32_t thing=role?p->support.thing:p->unit,update=role?p->support.update:p->update,id=role?p->support.id:p->object_id;
 Event e={};e.kind=kind;e.tag=tag;e.frame=frame();e.tick=GetTickCount();e.thread=GetCurrentThreadId();e.caller=caller;e.arg=arg;e.role=role;e.unit_id=id;e.mission_stage=p->mission_stage;e.route_index=p->route_index;e.nav_step=p->nav_step;e.mission_deadline_frame=p->mission_deadline_frame;e.mission_reason=p->retreat_reason;e.native_error=p->error;
 e.team=word(thing+0x414);e.owner=word(thing+0x418);e.source=word(update+0x50);e.lease_stage=p->lease_stage;e.arg_shots=observed_shots;e.arg_source=observed_source;
 if(kind==20||kind==21||kind==22||kind==24||kind==25){e.target_id=p->target_id;e.damage_source=arg;e.damage_before=before;e.damage_after=after;e.damage_reported=reported;}
 if(word(thing)==0xc4db60&&word(thing+0xdc)==id&&word(thing+0x418)==p->owner){read(thing+0x38,&e.x,12);read(word(thing+0x33c)+4,&e.own_hp,4);}
 e.sm=word(update+0x3c);e.sm_flags=word(e.sm+0x78);e.state=word(e.sm+4);e.state_id=word(e.state+4);e.path=word(update+0x150);e.holder=word(thing+0x238);read(e.sm+0x2c,e.requested,12);read(e.sm+0x48,e.effective,12);
 if(kind==20||kind==21||kind==24||kind==25){void* frames[12]={};e.stack_count=CaptureStackBackTrace(0,12,frames,NULL);for(unsigned j=0;j<e.stack_count;j++)e.stack[j]=(uintptr_t)frames[j];e.stack_words_address=(uintptr_t)__builtin_frame_address(0)+4;e.stack_word_count=read(e.stack_words_address,e.stack_words,sizeof(e.stack_words))?128:0;}
 if(!role)e.active_weapon_asset=current_weapon(&e.active_weapon_entry,&e.active_weapon_ammo);
 e.status84=word(thing+0x84);e.target_visible=visible_target();if(e.target_visible)read(p->target_unit+0x38,e.visible_target_xyz,12);memcpy(e.front_goal,p->front_goal,12);memcpy(e.support_goal,p->support_goal,12);if(input)read((uintptr_t)input,e.command_xyz,12);e.argument_path=input_path;e.argument_limit=input_limit;
 p->events[i]=e;MemoryBarrier();InterlockedExchange((LONG*)&p->events[i].seq,i+1);
}
