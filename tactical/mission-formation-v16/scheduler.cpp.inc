// One game-window-thread state advance per actual logical frame. This file
// only schedules the unchanged mission_tick_body; it never issues an SDK order.
static uint32_t schedule_token,schedule_seq,schedule_pid,schedule_thread;
static uint32_t schedule_command[4],schedule_task[4],schedule_last_frame;
static uint32_t schedule_last_pulse_tick,schedule_last_origin,schedule_advances,schedule_pulse_count,schedule_start_tick;
static bool schedule_busy,schedule_has_pulse;
static bool schedule_bound(){
 return p&&p->magic==T_MAGIC&&p->version==16&&p->pid==schedule_pid&&p->thread==schedule_thread&&p->token==schedule_token&&p->seq==schedule_seq&&!memcmp(p->command,schedule_command,16)&&!memcmp(p->task,schedule_task,16);
}
static bool schedule_terminal(){return !p||p->phase==3||p->phase==4;}
static void schedule_reset(){
 schedule_token=p->token;schedule_seq=p->seq;schedule_pid=p->pid;schedule_thread=p->thread;
 memcpy(schedule_command,p->command,16);memcpy(schedule_task,p->task,16);
 schedule_last_frame=0xffffffffu;schedule_last_pulse_tick=0;schedule_last_origin=0;schedule_advances=schedule_pulse_count=0;schedule_busy=schedule_has_pulse=false;
 schedule_start_tick=GetTickCount();
 p->pulse_requested=p->pulse_acknowledged=0;
}
static void schedule_emit(uint32_t kind,uint32_t origin,uint32_t previous_frame){
 memset(schedule_proof,0,sizeof(schedule_proof));
 schedule_proof[0]=0x53434839u;schedule_proof[1]=origin;schedule_proof[2]=schedule_token;schedule_proof[3]=schedule_seq;
 memcpy(schedule_proof+4,schedule_command,16);memcpy(schedule_proof+8,schedule_task,16);
 schedule_proof[12]=p->pulse_requested;schedule_proof[13]=p->pulse_acknowledged;
 schedule_proof[14]=frame();schedule_proof[15]=previous_frame;schedule_proof[16]=GetCurrentThreadId();
 schedule_proof[17]=T_PULSE_PERIOD_MS;schedule_proof[18]=T_PULSE_FALLBACK_MS;schedule_proof[19]=schedule_last_pulse_tick;
 schedule_proof[20]=schedule_advances;schedule_proof[21]=frozen_deadline;
 schedule_proof[22]=schedule_pulse_count;schedule_proof[23]=T_PULSE_ACK_TIMEOUT_MS;
 event(kind,origin);
}
static void schedule_advance(uint32_t origin){
 if(schedule_terminal()||GetCurrentThreadId()!=schedule_thread||schedule_busy)return;
 if(!schedule_bound())p->stop_requested=1; // existing stop/cleanup path only
 if(paused()){p->paused_samples++;return;}
 uint32_t now=frame();if(now==schedule_last_frame)return;
 uint32_t previous=schedule_last_frame;schedule_last_frame=now;schedule_busy=true;schedule_advances++;InterlockedIncrement(&p->active);
 bool proof=origin!=schedule_last_origin||(origin==2&&schedule_pulse_count%64==0);
 if(proof)schedule_emit(origin==1?121:origin==2?122:123,origin,previous);
 schedule_last_origin=origin;mission_tick_body();InterlockedDecrement(&p->active);schedule_busy=false;
}
static void schedule_pulse(uint32_t token,uint32_t request){
 if(schedule_terminal()||GetCurrentThreadId()!=schedule_thread||!schedule_bound()||token!=schedule_token||!request)return;
 uint32_t ack=p->pulse_acknowledged;
 uint32_t tick_now=GetTickCount();
 if(request!=p->pulse_requested||(schedule_has_pulse&&(int32_t)(request-ack)<=0)||tick_now-request>T_PULSE_ACK_TIMEOUT_MS)return;
 if(tick_now-(schedule_has_pulse?schedule_last_pulse_tick:schedule_start_tick)>T_PULSE_ACK_TIMEOUT_MS){p->stop_requested=1;return;}
 // Acknowledge duplicate-frame/paused delivery too, without manufacturing a
 // frame, Stop sample, arrival, deadline extension, or SDK action.
 schedule_last_pulse_tick=tick_now;schedule_has_pulse=true;schedule_pulse_count++;MemoryBarrier();InterlockedExchange((LONG*)&p->pulse_acknowledged,(LONG)request);
 schedule_advance(2);
}
static void CALLBACK tick(HWND,UINT,UINT_PTR,DWORD){
 if(schedule_terminal()||GetCurrentThreadId()!=schedule_thread)return;
 uint32_t elapsed=GetTickCount()-(schedule_has_pulse?schedule_last_pulse_tick:schedule_start_tick);
 if(elapsed>T_PULSE_ACK_TIMEOUT_MS)p->stop_requested=1;
 if(schedule_has_pulse&&elapsed<=T_PULSE_FALLBACK_MS)return;
 schedule_advance(3);
}
