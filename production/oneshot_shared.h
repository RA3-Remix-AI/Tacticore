#pragma once
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <stdint.h>
#define ONE_MESSAGE (WM_APP+0x32e)
#define ONE_MAGIC 0x464c414bu
struct OneState { uint32_t magic,pid,thread,factory,owner,ai,iface,start_low,start_high,requested_tick,queue_limit;volatile LONG claimed,state;uint32_t error,callback_thread,template_pointer,queue_id,node,cost;int32_t cash_before,cash_after;uint32_t head_before,tail_before,head_after,tail_after;float hp;uint32_t prior_count,prior_nodes[2],prior_ids[2],prior_templates[2],prior_costs[2],prior_paid[2],queue_preserved,initial_paid;};
