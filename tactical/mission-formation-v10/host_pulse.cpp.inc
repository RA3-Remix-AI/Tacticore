// Transport only: one unacknowledged message, no game SDK calls.
struct HostPulse {uint32_t last_sent,sent_at,last_post_tick,count;bool pending,stopped;};
static void host_pulse_step(Tactical* shared,HWND target_window,uint32_t token,uint32_t bound_seq,const uint32_t command[4],const uint32_t task[4],HostPulse& state){
 uint32_t now=GetTickCount();
 if(shared->phase==3||shared->phase==4)return;
 if(!state.stopped&&(shared->token!=token||shared->seq!=bound_seq||memcmp(shared->command,command,16)||memcmp(shared->task,task,16))){InterlockedExchange(&shared->stop_requested,1);state.stopped=true;printf("{\"scheduler\":\"binding_rejected\"}\n");fflush(stdout);}
 if(state.pending&&shared->pulse_acknowledged==state.last_sent){state.pending=false;if(state.count==1||state.count%64==0){printf("{\"scheduler\":\"pulse_ack\",\"nonce\":%u,\"token\":%u,\"seq\":%u,\"tick\":%u}\n",state.last_sent,token,bound_seq,now);fflush(stdout);}}
 if(!state.stopped&&state.pending&&now-state.sent_at>T_PULSE_ACK_TIMEOUT_MS){InterlockedExchange(&shared->stop_requested,1);state.stopped=true;printf("{\"scheduler\":\"ack_timeout_stop\",\"nonce\":%u}\n",state.last_sent);fflush(stdout);}
 if(state.stopped||state.pending||!(shared->phase==5||shared->phase==1||shared->phase==2||shared->phase==7)||now-state.last_post_tick<T_PULSE_PERIOD_MS)return;
 if(shared->pulse_requested!=shared->pulse_acknowledged||state.count>=4096){InterlockedExchange(&shared->stop_requested,1);state.stopped=true;return;}
 if(!now)return; // nonce zero is reserved, including the one-ms clock wrap.
 state.last_sent=now;state.sent_at=now;state.last_post_tick=now;state.pending=true;state.count++;
 InterlockedExchange((LONG*)&shared->pulse_requested,(LONG)state.last_sent);MemoryBarrier();
 if(!PostMessageA(target_window,T_PULSE_MESSAGE,token,state.last_sent)){InterlockedExchange(&shared->stop_requested,1);state.stopped=true;printf("{\"scheduler\":\"post_failed_stop\",\"nonce\":%u}\n",state.last_sent);fflush(stdout);}
 else if(state.count==1||state.count%64==0){printf("{\"scheduler\":\"pulse_post\",\"nonce\":%u,\"token\":%u,\"seq\":%u,\"tick\":%u}\n",state.last_sent,token,bound_seq,now);fflush(stdout);}
}
