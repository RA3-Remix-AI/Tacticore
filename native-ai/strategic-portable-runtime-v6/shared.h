#pragma once
#include <windows.h>
#include <stdint.h>
#include "profile.h"
#include "strategic_manager_gate_enable_candidate_v2.h"
// Explicit unified schema. One lease owns managers and lawful strategic flags.
static const uint32_t MAGIC=0x53434736, MESSAGE=WM_APP+0x346;
struct BindingWire {
 uint32_t pid,thread,start_low,start_high,owner,ai,personality,personality_data,player_template,game,engine;
 uint8_t session[16],lease[16],package[32],sources[32],runtime_manifest[32];
 wchar_t deployment[520],game_image[520],runtime_root[520],journal_root[520];
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
 uint32_t requested_mask,applied_mask,flag_deadline,flag_phase,flag_attempted,callback_serial,not_after_frame;
};
// kind: 1 pause, 2 enable, 3 release, 4 read-only reconcile, 5 STOP,
// 6 strategic flag replacement. No exact construction/production command.
// phase: 0 preparing, 1 active, 2 independently eligible for release,
// 4 admission rejected (no manager call), 5 unresolved; lease retained.
static_assert(sizeof(BindingWire)==4332,"explicit wire binding");
struct FlagAudit {
 uint32_t request,phase,previous_mask,desired_mask,observed_mask,frame,deadline_frame,attempted,trigger;
 uint64_t ms,deadline_ms;
};
struct JournalRecord {
 uint32_t magic,version,sequence,size,kind,callback_serial,intent_not_after_frame;BindingWire binding;
 ra3_strategic_manager_enable_candidate_v2::Audit audit;FlagAudit flags;uint32_t end;
};
static bool valid_mask(uint32_t mask){
 if(mask&~1023u)return false;
 const uint32_t groups[]={0x70u,0x38fu};
 for(uint32_t group:groups){uint32_t value=mask&group;if(value&&(value&(value-1)))return false;}
 return true;
}
