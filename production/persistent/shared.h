#pragma once
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <stdint.h>
#define P_MAGIC 0x50434d44u
#define P_MESSAGE (WM_APP+0x330)
#define P_CAP 1024
struct Command {uint32_t seq,id[4],task[4],session[4],commander[4],hash,budget,reserve,expires,queue_limit,requested_tick,factory,factory_id,iface;};
struct Receipt {volatile LONG updates,version;Command command;uint32_t state,error,attempted,frame,queue_id,node,cost,quoted_cost,cash,liability,prior_count,preserved,paid,debit_count,payment_error,created,object,object_id,object_owner,object_hash,completed,completion_frame,live_samples,object_hp_bits,object_x_bits,object_y_bits,factory_x_bits,factory_y_bits;};
struct Persistent {uint32_t magic,version,pid,thread,owner,ai,personality,personality_id,player_template,start_low,start_high,session[4],commander[4],total_budget,reserve_floor,min_interval,start_frame;volatile LONG phase,stop_requested,active,heartbeat,request_state;Command request;uint32_t reply_index,reply_error,last_seq,last_frame,last_accepted_frame,spent,count,restore_mask,error,callback_thread;Receipt ledger[P_CAP];};
