from pathlib import Path
root=Path('bridge-probe/tactical');out=root/'ordered-attack';out.mkdir(exist_ok=True)
stop_fields='stop_calls private_stop_calls private_stop_frame attack_facade_calls attack_private_calls attack_issued_frame stable_samples stop_gate_samples last_sample_frame lease_stage stop_failed'.split()
for name in ['shared.h','lease.cpp','lease.py','host.cpp','build.ps1']:
 s=(root/'combat-commit'/name).read_text().replace('TacticalCombatCommit','TacticalOrderedAttack').replace('RA3TacticalCombatCommit','RA3TacticalOrderedAttack').replace('tactical-combat-commit-','tactical-ordered-attack-')
 if name=='shared.h':
  s=s.replace('0x434f4d31u','0x4f415431u').replace('WM_APP+0x36e','WM_APP+0x371')
  s=s.replace('Event events[T_CAP];','uint32_t '+','.join(stop_fields)+';float stopped_xyz[3];Event events[T_CAP];')
  s=s.replace('uint32_t stack_count,', 'uint32_t lease_stage,sm,sm_flags,state,state_id,path,holder,arg_shots,arg_source;float requested[3],effective[3];uint32_t stack_count,')
 if name=='lease.cpp':
  s=s.replace('p->version!=6','p->version!=7').replace('i<8','i<11').replace('restore_mask=255','restore_mask=2047').replace('restore_mask==255','restore_mask==2047')
  s=s.replace('read(p->unit+0x38,&e.x,12);', 'if(word(p->unit)==0xc4db60&&word(p->unit+0xdc)==p->object_id&&word(p->unit+0x418)==p->owner)read(p->unit+0x38,&e.x,12);e.lease_stage=p->lease_stage;e.sm=word(p->update+0x3c);e.sm_flags=word(e.sm+0x78);e.state=word(e.sm+4);e.state_id=word(e.state+4);e.path=word(p->update+0x150);e.holder=word(p->unit+0x238);read(e.sm+0x2c,e.requested,12);read(e.sm+0x48,e.effective,12);')
  s=s.replace('if(tag==2&&GetCurrentThreadId()', 'if((tag==2||p->lease_stage==1)&&GetCurrentThreadId()')
  old='if(ours){if(!tag)p->native_attack++;event(12,word((uintptr_t)target+0xdc),(uintptr_t)__builtin_return_address(0));}'
  new='if(ours){bool expected=p->lease_stage==1&&p->attack_facade_calls==1&&!p->attack_private_calls&&(uintptr_t)target==p->target_unit&&shots==0x7fffffff&&source==1;if(expected){p->attack_private_calls++;p->attack_issued_frame=frame();}else if(!tag)p->native_attack++;event(12,word((uintptr_t)target+0xdc),(uintptr_t)__builtin_return_address(0));}'
  assert old in s;s=s.replace(old,new)
  s=s.replace('if(tag==2&&weapon_identity())','if(p->lease_stage==1&&weapon_identity())')
  # The real ordinary Body damage virtual is slot+0x10, not the separate+0x14 path.
  s=s.replace('{0x764e20,','{0x7d2310,').replace('"\\x83\\xec\\x14\\x55\\x57\\x8b\\xf9\\x8b\\x47\\xf0\\x8b\\x50\\x64\\x8d\\x4f\\xf0",16', '"\\x81\\xec\\x20\\x01\\x00\\x00\\x53\\x55\\x56\\x8b\\xb4\\x24\\x30\\x01\\x00\\x00",16')
  extra='''typedef void (__attribute__((thiscall))*Stop)(void*,uint32_t);static Stop old_stop_facade,old_stop_private;static Attack old_attack_facade;
static void __attribute__((fastcall)) stop_facade_hook(void* self,void*,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update+0x24;if(ours)event(30,source,(uintptr_t)__builtin_return_address(0));old_stop_facade(self,source);if(ours)event(31,source);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) stop_private_hook(void* self,void*,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update;uint32_t caller=(uintptr_t)__builtin_return_address(0);if(ours)event(32,source,caller);old_stop_private(self,source);if(ours){if(p->phase==1&&p->stop_calls&&source==1&&caller==0x787791&&(p->lease_stage==0||p->lease_stage==2)){p->private_stop_calls++;p->private_stop_frame=frame();}event(33,source,caller);}InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) attack_facade_hook(void* self,void*,void* target,uint32_t shots,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update+0x24;if(ours)event(34,word((uintptr_t)target+0xdc),(uintptr_t)__builtin_return_address(0));old_attack_facade(self,target,shots,source);if(ours)event(35,word((uintptr_t)target+0xdc));InterlockedDecrement(&p->active);}
static void issue_stop(uint32_t stage){p->lease_stage=stage;p->stable_samples=p->stop_gate_samples=p->last_sample_frame=0;read(p->unit+0x38,p->stopped_xyz,12);tag=4;p->stop_calls++;((Stop)0x54b0a0)((void*)(uintptr_t)(p->update+0x24),1);event(36);tag=0;}
static bool stop_settled(uint32_t now){if(now==p->last_sample_frame)return false;p->last_sample_frame=now;uint32_t sm=word(p->update+0x3c);float xyz[3];read(p->unit+0x38,xyz,12);bool gate=p->private_stop_calls==p->stop_calls&&now>p->private_stop_frame&&word(p->update+0x50)==1&&!(word(sm+0x78)&0xffff)&&word(p->update+0x150)==0;float dx=xyz[0]-p->stopped_xyz[0],dy=xyz[1]-p->stopped_xyz[1];if(gate){p->stop_gate_samples++;if(dx*dx+dy*dy<=1)p->stable_samples++;else p->stable_samples=0;}else{p->stop_gate_samples=p->stable_samples=0;}memcpy(p->stopped_xyz,xyz,12);return p->stop_gate_samples>=3&&p->stable_samples>=3;}
'''
  s=s.replace('struct Hook {',extra+'struct Hook {')
  s=s.replace('12,{},false,false}};', '12,{},false,false},\n{0x54b0a0,(void*)stop_facade_hook,(void**)&old_stop_facade,"\\x83\\xec\\x5c\\x8b\\x44\\x24\\x60\\x56\\x6a\\x01\\x50\\x8b\\xf1",13,{},false,false},\n{0x721ad0,(void*)stop_private_hook,(void**)&old_stop_private,"\\x83\\xec\\x08\\x55\\x8b\\xe9\\x8b\\x45\\x08\\x8b\\x48\\x04",12,{},false,false},\n{0x572280,(void*)attack_facade_hook,(void**)&old_attack_facade,"\\x83\\xec\\x5c\\x8b\\x44\\x24\\x68\\x56\\x6a\\x01\\x50\\x8b\\xf1",13,{},false,false}};')
  s=s.replace('if(!unit()){p->error=32;', 'if(!unit()&&p->phase==2){finish();return;}\n if(!unit()){p->error=32;')
  old='if(paused()||!visible_target()){p->phase=1;p->return_pending=1;return;}tag=2;p->attack_calls++;((Attack)0x76e690)((void*)(uintptr_t)p->update,(void*)(uintptr_t)p->target_unit,1,0);event(2);tag=0;p->phase=1;return;'
  new='''p->phase=1;if(paused()||!visible_target()){p->return_pending=1;return;}if(word(p->unit+0x238)||word(p->update)!=0xc48670||word(p->update+0x24)!=0xc48528||word(0xc48528)!=0x787500||word(0xc48670+0x8c)!=0x721ad0){p->error=43;p->return_pending=1;return;}issue_stop(0);return;'''
  assert old in s;s=s.replace(old,new)
  a=s.index(' event(3);if(p->phase==1){');z=s.index(' }else if(p->phase==2&&',a)
  s=s[:a]+''' event(3);if(p->phase==1){
  bool end=p->stop_requested||p->return_pending||now-p->issued_frame>=p->lease_frames||GetTickCount()-start_tick>60000||p->native_move||p->native_attack||p->native_add||p->native_remove;
  if(p->lease_stage==0&&!end){if(!visible_target()){end=true;}else if(stop_settled(now)){event(37);if(word(p->unit+0x238)){p->error=43;end=true;}else{p->lease_stage=1;tag=2;p->attack_calls++;p->attack_facade_calls++;((Attack)0x572280)((void*)(uintptr_t)(p->update+0x24),(void*)(uintptr_t)p->target_unit,0x7fffffff,1);event(2);tag=0;}}else if(now-p->issued_frame>=30){p->error=44;end=true;}}
  if(p->lease_stage==1){sample_weapon();if(!visible_target()||p->damage_count||p->commit_own_calls)end=true;}
  if(end&&p->lease_stage!=2){issue_stop(2);p->return_pending=1;}
  if(p->lease_stage==2&&(stop_settled(now)||now-p->private_stop_frame>=30)){
   if(p->stable_samples<3){p->stop_failed=1;p->error=45;}
   if(p->native_add){p->error=36;finish();return;}
   tag=3;p->return_calls++;((Transfer)0x838820)((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->unit,1);event(5);tag=0;p->returned_frame=now;p->return_pending=0;p->return_verified=unit()&&word(p->unit+0x414)==p->default_team;p->phase=2;if(!p->return_verified){p->error=37;finish();}
  }
''' +s[z:]
 if name=='host.cpp':s=s.replace('restore_mask==255','restore_mask==2047')
 if name=='lease.py':
  s=s.replace("[('stack_count',U)", "[(x,U) for x in 'lease_stage sm sm_flags state state_id path holder arg_shots arg_source'.split()]+[('requested',c.c_float*3),('effective',c.c_float*3)]+[('stack_count',U)")
  s=s.replace("[('events',Event*4096)]", "[(x,U) for x in "+repr(' '.join(stop_fields))+".split()]+[('stopped_xyz',c.c_float*3)]+[('events',Event*4096)]")
  s=s.replace('s.magic=0x434f4d31;s.version=6','s.magic=0x4f415431;s.version=7')
  s=s.replace("'commit_own_calls']}", "'commit_own_calls']+"+repr(stop_fields)+"}")
  s=s.replace("n.get('restore_mask')==255", "n.get('restore_mask')==2047")
  s=s.replace("native_limit_written_as_one=n.get('limit_after')==1", "native_script_burst_limit=n.get('limit_after')==0x7fffffff")
  s=s.replace("shot_observed=len(shots)==1 and n.get('shot_samples')==1 and abs(sum(e['damage_before']-e['damage_after'] for e in shots)-1)<.001", "ammo_activity_observed=bool(shots) and n.get('shot_samples')==len(shots)")
  s=s.replace("contact['body_vtable']+0x14", "contact['body_vtable']+0x10")
 (out/name).write_text(s)
print(out)
