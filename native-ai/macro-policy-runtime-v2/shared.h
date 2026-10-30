#pragma once
#include <windows.h>
#include <stdint.h>
#include "profile.h"
static const uint32_t MAGIC=0x4d503032, MESSAGE=WM_APP+0x344;
struct Shared {
 uint32_t magic,version,pid,thread,start_low,start_high,owner,ai,personality,personality_id,player_template,engine;
 volatile LONG request,ack,phase,active;
 uint32_t error,attempted,callback_thread,start_frame,last_frame,applied_mask,deadline_frame,cleanup_verified,
  watchdog_reason,self_hook_installed,client_heartbeat,kind,mask,duration_frames,emergency_stop,lease_held;
};
static bool valid_mask(uint32_t mask){
 if(mask&~KNOWN_MASK)return false;
 for(unsigned i=0;i<sizeof(EXCLUSIVE_MASKS)/sizeof(EXCLUSIVE_MASKS[0]);i++){
  uint32_t value=mask&EXCLUSIVE_MASKS[i];if(value&&(value&(value-1)))return false;
 }
 return true;
}
