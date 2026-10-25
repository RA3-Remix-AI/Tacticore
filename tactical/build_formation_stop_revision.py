from pathlib import Path
root=Path('bridge-probe/tactical');out=root/'formation-stop';out.mkdir(exist_ok=True)
for name in ['shared.h','host.cpp','lease.cpp','lease.py','build.ps1']:
 s=(root/'formation-disposal'/name).read_text()
 s=s.replace('TacticalFormationSafe','TacticalFormationStop').replace('TacticalFormationSafeControl','TacticalFormationStopControl').replace('RA3TacticalFormationSafe','RA3TacticalFormationStop').replace('tactical-formation-safe-','tactical-formation-stop-')
 if name=='shared.h':
  s=s.replace('0x464f5231u','0x46535431u').replace('0x36c','0x36d')
  s=s.replace('float disposed_hp;','float disposed_hp;uint32_t stop_calls,private_stop_calls,private_stop_frame,stable_samples,gate_samples,last_sample_frame,native_stop;float stopped_xyz[3];')
  s=s.replace('float x,y,z;','float x,y,z;uint32_t sm,sm_flags,state,state_id,path,path_node;float requested[3],effective[3],path_xy[2];')
 if name=='lease.cpp':
  s=s.replace('p->version!=2','p->version!=3').replace('i<5','i<7').replace('restore_mask=31','restore_mask=127').replace('restore_mask==31','restore_mask==127')
  s=s.replace('read(u->thing+0x38,&e.x,12);','read(u->thing+0x38,&e.x,12);e.sm=word(u->update+0x3c);e.sm_flags=word(e.sm+0x78);e.state=word(e.sm+4);e.state_id=word(e.state+4);e.path=word(u->update+0x150);e.path_node=word(e.path+0x10);read(e.sm+0x2c,e.requested,12);read(e.sm+0x48,e.effective,12);read(e.path_node+0xc,e.path_xy,8);')
  s=s.replace('static Move old_move;', 'typedef void (__attribute__((thiscall))*Stop)(void*,uint32_t);static Stop old_stop_facade,old_stop_private;\nstatic Move old_move;')
  hooks='''static void __attribute__((fastcall)) stop_facade_hook(void* self,void*,uint32_t source){InterlockedIncrement(&p->active);Unit* u=by_update((uintptr_t)self-0x24);if(u){if(!tag)u->native_stop++;event(u,20,source,(uintptr_t)__builtin_return_address(0));}old_stop_facade(self,source);if(u)event(u,21,source);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) stop_private_hook(void* self,void*,uint32_t source){InterlockedIncrement(&p->active);Unit* u=by_update((uintptr_t)self);uint32_t caller=(uintptr_t)__builtin_return_address(0);bool expected=u&&(p->phase==1||p->phase==6)&&p->stage==0&&u->stop_calls&&source==1&&caller==0x787791;if(u){if(!tag&&!expected)u->native_stop++;event(u,22,source,caller);}old_stop_private(self,source);if(u){if(expected){u->private_stop_calls++;u->private_stop_frame=frame();}event(u,23,source,caller);}InterlockedDecrement(&p->active);}
'''
  s=s.replace('struct Hook {',hooks+'struct Hook {')
  s=s.replace('12,{},false,false}};','12,{},false,false},\n{0x54b0a0,(void*)stop_facade_hook,(void**)&old_stop_facade,"\\x83\\xec\\x5c\\x8b\\x44\\x24\\x60\\x56\\x6a\\x01\\x50\\x8b\\xf1",13,{},false,false},\n{0x721ad0,(void*)stop_private_hook,(void**)&old_stop_private,"\\x83\\xec\\x08\\x55\\x8b\\xe9\\x8b\\x45\\x08\\x8b\\x48\\x04",12,{},false,false}};')
  s=s.replace('p->stage=1;p->stage_frame=now;', 'p->stage=0;p->stage_frame=now;',1)
  old='issue_move(p->units[1],p->units[1].hold);issue_move(p->units[0],p->units[0].goal);p->phase=1;return;'
  new='''for(unsigned i=0;i<2;i++){Unit& u=p->units[i];if(word(u.update)!=0xc48670||word(u.update+0x24)!=0xc48528||word(0xc48528)!=0x787500||word(0xc48670+0x8c)!=0x721ad0){p->error=43;p->phase=1;p->return_pending=1;return;}read(u.thing+0x38,u.stopped_xyz,12);tag=4;u.stop_calls++;((Stop)0x54b0a0)((void*)(uintptr_t)(u.update+0x24),1);event(&u,6);tag=0;}p->phase=1;return;'''
  assert old in s;s=s.replace(old,new)
  s=s.replace('!u.native_add&&!u.native_remove;', '!u.native_add&&!u.native_remove&&!u.native_stop;')
  old='if(p->stage==1){bool held='
  new='''if(p->stage==0){bool ready=true;for(unsigned i=0;i<2;i++){Unit& u=p->units[i];float xyz[3];read(u.thing+0x38,xyz,12);if(now!=u.last_sample_frame){u.last_sample_frame=now;uint32_t sm=word(u.update+0x3c);bool gate=u.private_stop_calls==1&&now>u.private_stop_frame&&word(u.update+0x50)==1&&!(word(sm+0x78)&0xffff)&&word(u.update+0x150)==0;float dx=xyz[0]-u.stopped_xyz[0],dy=xyz[1]-u.stopped_xyz[1];if(gate){u.gate_samples++;if(dx*dx+dy*dy<=1)u.stable_samples++;else u.stable_samples=0;}else{u.gate_samples=0;u.stable_samples=0;}memcpy(u.stopped_xyz,xyz,12);}ready&=u.stable_samples>=3&&u.gate_samples>=3;}
   if(ready){for(unsigned i=0;i<2;i++){Unit& u=p->units[i];memcpy(u.hold,u.stopped_xyz,12);event(&u,24);}p->stage=1;p->stage_frame=now;issue_move(p->units[0],p->units[0].goal);}
   else if(now-p->issued_frame>=30){p->error=44;return_all();}return;
  }
  if(p->stage==1){bool held='''
  assert old in s;s=s.replace(old,new)
 if name=='host.cpp':s=s.replace('restore_mask==31','restore_mask==127')
 if name=='lease.py':
  s=s.replace("[('disposed_hp',c.c_float)]","[('disposed_hp',c.c_float)]+[(x,U) for x in 'stop_calls private_stop_calls private_stop_frame stable_samples gate_samples last_sample_frame native_stop'.split()]+[('stopped_xyz',c.c_float*3)]")
  s=s.replace("[(x,c.c_float) for x in 'x y z'.split()]", "[(x,c.c_float) for x in 'x y z'.split()]+[(x,U) for x in 'sm sm_flags state state_id path path_node'.split()]+[('requested',c.c_float*3),('effective',c.c_float*3),('path_xy',c.c_float*2)]")
  s=s.replace("x in ['initial','goal','hold']", "isinstance(getattr(u,x),c.Array)")
  s=s.replace("{name:getattr(e,name) for name,_ in Event._fields_}","{name:list(getattr(e,name)) if isinstance(getattr(e,name),c.Array) else getattr(e,name) for name,_ in Event._fields_}")
  s=s.replace('s.magic=0x464f5231;s.version=2','s.magic=0x46535431;s.version=3')
  s=s.replace("n.get('restore_mask')==31", "n.get('restore_mask')==127").replace("units[1]['move_calls']==2","units[1]['move_calls']==1")
  s=s.replace("report);b.durable(path,report)","report);b.durable(path,report)")
  s=s.replace("status='preflight');b.durable(path,report)","status='preflight')\n if path.exists():raise ValueError('existing_report_requires_recovery')\n b.durable(path,report)")
  needle="  # Pair consecutive same-tick timer samples;"
  extra='''  for i,u in enumerate(units):
   ev=[e for e in events if e['unit_id']==u['id']];stops=[e for e in ev if e['kind']==23 and e['arg']==1 and e['caller']==0x787791 and n['issued_frame']<=e['frame']<n['returned_frame']];gates=[e for e in ev if e['kind']==24 and e['stage']==0 and not e['path'] and not(e['sm_flags']&0xffff) and e['source']==1];moves=[e for e in ev if e['kind']==10 and e['tag']==2]
   checks['unit_'+str(i)+'_normal_stop']=u.get('stop_calls')==u.get('private_stop_calls')==1 and len(stops)==len(gates)==1 and sum(e['kind']==20 and e['tag']==4 and e['arg']==1 for e in ev)==1 and sum(e['kind']==21 and e['tag']==4 for e in ev)==1
   checks['unit_'+str(i)+'_stop_then_move']=len(stops)==len(gates)==1 and bool(moves) and stops[0]['frame']<gates[0]['frame']<=min(e['frame'] for e in moves) and stops[0]['seq']<gates[0]['seq']<min(e['seq'] for e in moves) and u.get('stable_samples',0)>=3 and u.get('gate_samples',0)>=3
   checks['unit_'+str(i)+'_settled_hold_bound']=len(gates)==1 and all(math.isfinite(gates[0][axis]) and abs(gates[0][axis]-u['hold'][j])<.001 for j,axis in enumerate(['x','y','z']))
   clean=[e for e in ev if e['kind']==3 and len(stops)==1 and len(gates)==1 and stops[0]['frame']<e['frame']<gates[0]['frame'] and not e['path'] and not(e['sm_flags']&0xffff) and e['source']==1]
   checks['unit_'+str(i)+'_clean_samples']=len({e['frame'] for e in clean})>=2 and u.get('native_stop')==0
'''
  assert needle in s;s=s.replace(needle,extra+needle)
 (out/name).write_text(s)
print(out)
