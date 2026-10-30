#pragma once
#include <windows.h>
#include <stdint.h>
#include "profile.h"
#include "strategic_manager_gate_enable_candidate_v2.h"
// This research protocol owns managers only. It never publishes flag intents.
// It shares the SAME process lease with all flag transports.
static const uint32_t MAGIC=0x534d4734, MESSAGE=WM_APP+0x345;
struct BindingWire {
 uint32_t pid,thread,start_low,start_high,owner,ai,personality,personality_data,player_template,game,engine;
 uint8_t session[16],lease[16],package[32],sources[32];
 wchar_t deployment[520];
};
struct GateStatus {
 uint32_t phase,baseline_captured,baseline[3],observed[3],frame,deadline_frame;
 uint64_t ms,deadline_ms;
 uint32_t attempted,requested_enabled,operation_enabled,already_satisfied;
};
struct Shared {
 uint32_t magic,version,size;BindingWire binding;
 volatile LONG request,ack,phase,active;
 uint32_t error,heartbeat,kind,gate,frames,wall_ms,result,stop,lease_held,hook_held,last_frame,cleanup_verified;
 uint32_t journal_records;
 GateStatus gates[2];
};
// kind: 1 pause, 2 enable, 3 release, 4 read-only reconcile, 5 STOP.
// phase: 0 preparing, 1 active, 2 independently eligible for release,
// 4 admission rejected (no manager call), 5 unresolved; lease retained.
static_assert(sizeof(BindingWire)==1180,"explicit wire binding");
struct JournalRecord {
 uint32_t magic,version,sequence,size;BindingWire binding;
 ra3_strategic_manager_enable_candidate_v2::Audit audit;uint32_t end;
};
