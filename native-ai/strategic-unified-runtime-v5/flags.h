#pragma once
// Lifecycle uses supplied checked flag read/set operations and a durable journal.
// Internal authority lives in DLL memory; shared fields are projections only.
enum class FlagPhase:uint32_t { Empty=0,Held=1,ApplyUnknown=2,RestoreUnknown=3,BaselineObserved=4,Blocked=5 };
static FlagPhase flag_phase=FlagPhase::Empty;
static uint32_t flag_mask,flag_reconcile_mask,flag_reconcile_frame,flag_last_audit_callback;
static uint64_t flag_reconcile_ms;
static bool flag_reconcile_pending;
static bool flag_audit(uint32_t request,uint32_t phase,uint32_t before,uint32_t desired,uint32_t observed,uint32_t trigger){
 if(!journal||audit_sequence>=4096)return false;
 JournalRecord row={};row.magic=MAGIC;row.version=5;row.sequence=++audit_sequence;row.size=sizeof(row);row.kind=2;row.callback_serial=callback_serial;row.intent_not_after_frame=flag_not_after;row.binding=sealed;row.end=0x454e4435;
 row.flags={request,phase,before,desired,observed,word(binding.game+0x50),flag_deadline,p->flag_attempted,trigger,GetTickCount64(),flag_deadline_ms};
 DWORD written=0;if(!WriteFile(journal,&row,sizeof(row),&written,NULL)||written!=sizeof(row)||!FlushFileBuffers(journal))return false;
 p->journal_records=audit_sequence;flag_last_audit_callback=callback_serial;return true;
}
static void project_flags(){p->flag_phase=(uint32_t)flag_phase;p->applied_mask=flag_mask;p->flag_deadline=flag_deadline;}
static bool replace_flags(uint32_t request,uint32_t desired,uint32_t duration,uint32_t wall_ms,bool restoring,uint32_t trigger){
 if(!restoring&&(!valid_mask(desired)||duration<1||duration>1800||wall_ms<1||wall_ms>120000||word(binding.game+0x15c)))return false;
 uint32_t observed=0;if(!read_mask(observed)||observed!=flag_mask){flag_phase=FlagPhase::Blocked;project_flags();return false;}
 // Read the current frame after the potentially slow read_mask/guard.
 // Expired new requests cannot refresh a relative duration. Restoration is
 // still permitted after the original intent's absolute expiry.
 uint32_t now_frame=word(binding.game+0x50);
 if(!restoring&&(!flag_not_after||now_frame>=flag_not_after))return false;
 uint32_t before=observed;flag_phase=restoring?FlagPhase::RestoreUnknown:FlagPhase::ApplyUnknown;flag_reconcile_pending=false;project_flags();
 if(!restoring){
  uint32_t bounded_duration=duration;
  if(bounded_duration>flag_not_after-now_frame)bounded_duration=flag_not_after-now_frame;
  flag_deadline=desired?now_frame+bounded_duration:0;
  flag_deadline_ms=desired?GetTickCount64()+wall_ms:0;
 }
 if(!flag_audit(request,(uint32_t)flag_phase,before,desired,observed,trigger))return false;
 // Journal may block. Recheck identity, actual pause/deadline and old flags.
 uint32_t after_log=0;
 if(!read_mask(after_log)||after_log!=before||(!restoring&&(word(binding.game+0x15c)||(desired&&(word(binding.game+0x50)>=flag_deadline||GetTickCount64()>=flag_deadline_ms)))))return false;
 for(unsigned pass=0;pass<2;pass++)for(unsigned i=0;i<10;i++){
  bool previous=bool(before&(1u<<i)),wanted=bool(desired&(1u<<i));
  if(previous!=wanted&&wanted==(pass==1)&&!set_flag(i,wanted,restoring))return false;
 }
 if(!read_mask(observed)||observed!=desired)return false;
 flag_mask=observed;flag_phase=desired?FlagPhase::Held:FlagPhase::BaselineObserved;
 if(!desired){flag_deadline=0;flag_deadline_ms=0;}
 project_flags();
 if(!flag_audit(request,(uint32_t)flag_phase,before,desired,observed,trigger)){
  flag_phase=restoring?FlagPhase::RestoreUnknown:FlagPhase::ApplyUnknown;project_flags();return false;
 }return true;
}
static bool flags_baseline(){
 if(flag_phase!=FlagPhase::Empty&&flag_phase!=FlagPhase::BaselineObserved)return false;
 uint32_t mask=0;if(!read_mask(mask)||mask)return false;
 return flag_phase==FlagPhase::Empty||callback_serial>flag_last_audit_callback;
}
static void service_flags(bool stop,uint32_t trigger){
 if(flag_phase==FlagPhase::Blocked)return;
 if(flag_phase==FlagPhase::ApplyUnknown||flag_phase==FlagPhase::RestoreUnknown){
  uint32_t now=0,frame=word(binding.game+0x50);uint64_t ms=GetTickCount64();
  if(!read_mask(now))return;
  if(!flag_reconcile_pending){
   if(!flag_audit(0,(uint32_t)flag_phase,flag_mask,0,now,trigger))return;
   flag_reconcile_pending=true;flag_reconcile_mask=now;flag_reconcile_frame=frame;flag_reconcile_ms=ms;return;
  }
  if(frame<=flag_reconcile_frame||ms<=flag_reconcile_ms||now!=flag_reconcile_mask)return;
  if(!flag_audit(0,(uint32_t)flag_phase,flag_mask,0,now,trigger))return;
  if(!now){flag_mask=0;flag_phase=FlagPhase::BaselineObserved;flag_deadline=0;project_flags();return;}
  // An uncertain restore is NEVER retried. An uncertain APPLY, independently
  // read twice, may be followed by the separate purpose of restoring baseline.
  if(flag_phase==FlagPhase::RestoreUnknown){flag_phase=FlagPhase::Blocked;project_flags();return;}
  flag_mask=now;flag_phase=FlagPhase::Held;project_flags();
 }
 // Preserve the original absolute intent bound across later callbacks,
 // independently of relative duration and the wall-clock expiry.
 if(flag_phase==FlagPhase::Held&&(stop||(flag_not_after&&word(binding.game+0x50)>=flag_not_after)||word(binding.game+0x50)>=flag_deadline||GetTickCount64()>=flag_deadline_ms))replace_flags(0,0,1,1,true,trigger);
}
