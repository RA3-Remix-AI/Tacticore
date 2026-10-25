from pathlib import Path
import shutil
root=Path('bridge-probe/tactical');out=root/'stop-move';out.mkdir(exist_ok=True)
for name in ['shared.h','host.cpp','lease.cpp','lease.py','build.ps1']:
 text=(root/'reusable'/name).read_text()
 text=text.replace('TacticalLeaseReusable','TacticalStopMove').replace('TacticalReusableControl','TacticalStopMoveControl').replace('RA3TacticalReusable','RA3TacticalStopMove').replace('tactical-reusable-','tactical-stop-move-')
 if name=='shared.h':
  text=text.replace('0x54414331u','0x54534d31u').replace('0x362','0x36a')
  text=text.replace('float x,y,z;','float x,y,z;uint32_t sm,sm_flags,state,state_id,path,path_node;float requested[3],effective[3],path_xy[2];')
  text=text.replace('Event events[T_CAP];','uint32_t stop_calls,private_stop_calls,private_stop_frame,move_issued_frame,stable_samples,stop_gate_samples,last_sample_frame;float stopped_xyz[3];Event events[T_CAP];')
 if name=='lease.cpp':
  text=text.replace('p->version!=2','p->version!=1').replace('i<5','i<7').replace('restore_mask=31','restore_mask=127').replace('restore_mask==31','restore_mask==127')
  text=text.replace('read(p->unit+0x38,&e.x,12);e.seq=0;', 'read(p->unit+0x38,&e.x,12);e.sm=word(p->update+0x3c);e.sm_flags=word(e.sm+0x78);e.state=word(e.sm+4);e.state_id=word(e.state+4);e.path=word(p->update+0x150);e.path_node=word(e.path+0x10);read(e.sm+0x2c,e.requested,12);read(e.sm+0x48,e.effective,12);read(e.path_node+0xc,e.path_xy,8);e.seq=0;')
  text=text.replace('static Move old_move;', 'typedef void (__attribute__((thiscall))*Stop)(void*,uint32_t);static Stop old_stop_facade,old_stop_private;\nstatic Move old_move;')
  hook='''static void __attribute__((fastcall)) stop_facade_hook(void* self,void*,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update+0x24;if(ours)event(20,source,(uintptr_t)__builtin_return_address(0));old_stop_facade(self,source);if(ours)event(21,source);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) stop_private_hook(void* self,void*,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update;uint32_t caller=(uintptr_t)__builtin_return_address(0);if(ours)event(22,source,caller);old_stop_private(self,source);if(ours){if(p->stop_calls&&source==1&&caller==0x787791){p->private_stop_calls++;p->private_stop_frame=frame();}event(23,source,caller);}InterlockedDecrement(&p->active);}
'''
  text=text.replace('struct Hook {',hook+'struct Hook {')
  text=text.replace('12,{},false,false}};','12,{},false,false},\n{0x54b0a0,(void*)stop_facade_hook,(void**)&old_stop_facade,"\\x83\\xec\\x5c\\x8b\\x44\\x24\\x60\\x56\\x6a\\x01\\x50\\x8b\\xf1",13,{},false,false},\n{0x721ad0,(void*)stop_private_hook,(void**)&old_stop_private,"\\x83\\xec\\x08\\x55\\x8b\\xe9\\x8b\\x45\\x08\\x8b\\x48\\x04",12,{},false,false}};')
  old='if(paused()){p->phase=1;p->return_pending=1;return;}tag=2;p->move_calls++;((Move)0x6eff70)((void*)(uintptr_t)p->update,p->target,0);event(2);tag=0;p->phase=1;return;'
  new='''if(paused()){p->phase=1;p->return_pending=1;return;}
  if(word(p->update)!=0xc48670||word(p->update+0x24)!=0xc48528||word(0xc48528)!=0x787500||word(0xc48670+0x8c)!=0x721ad0){p->error=43;p->phase=1;p->return_pending=1;return;}
  read(p->unit+0x38,p->stopped_xyz,12);tag=4;p->stop_calls++;((Stop)0x54b0a0)((void*)(uintptr_t)(p->update+0x24),1);event(6);tag=0;p->phase=1;return;'''
  assert old in text;text=text.replace(old,new)
  old='event(3);if(p->phase==1){float xyz[3];read(p->unit+0x38,xyz,12);float dx=xyz[0]-p->target[0],dy=xyz[1]-p->target[1];if(dx*dx+dy*dy<=225)p->arrival_samples++;'
  new='''event(3);if(p->phase==1){float xyz[3];read(p->unit+0x38,xyz,12);float dx=xyz[0]-p->target[0],dy=xyz[1]-p->target[1];
  if(!p->move_calls&&!p->return_pending&&!p->stop_requested&&now!=p->last_sample_frame){p->last_sample_frame=now;uint32_t sm=word(p->update+0x3c);bool gate=p->private_stop_calls==1&&now>p->private_stop_frame&&word(p->update+0x50)==1&&!(word(sm+0x78)&0xffff)&&word(p->update+0x150)==0;
   float sx=xyz[0]-p->stopped_xyz[0],sy=xyz[1]-p->stopped_xyz[1];if(gate){p->stop_gate_samples++;if(sx*sx+sy*sy<=1)p->stable_samples++;else p->stable_samples=0;}else{p->stop_gate_samples=0;p->stable_samples=0;}memcpy(p->stopped_xyz,xyz,12);
   if(p->stable_samples>=3&&p->stop_gate_samples>=3){event(24);tag=2;p->move_calls++;p->move_issued_frame=now;((Move)0x6eff70)((void*)(uintptr_t)p->update,p->target,0);event(2);tag=0;}
   else if(now-p->issued_frame>=30){p->error=44;p->return_pending=1;}
  }
  if(p->move_calls&&dx*dx+dy*dy<=225)p->arrival_samples++;'''
  assert old in text;text=text.replace(old,new)
 if name=='host.cpp':text=text.replace('restore_mask==31','restore_mask==127')
 if name=='lease.py':
  text=text.replace(']+[(x,c.c_float) for x in \'x y z\'.split()]',']+[(x,c.c_float) for x in \'x y z\'.split()]+[(x,U) for x in \'sm sm_flags state state_id path path_node\'.split()]+[(\'requested\',c.c_float*3),(\'effective\',c.c_float*3),(\'path_xy\',c.c_float*2)]')
  text=text.replace("[('events',Event*4096)]","[(x,U) for x in 'stop_calls private_stop_calls private_stop_frame move_issued_frame stable_samples stop_gate_samples last_sample_frame'.split()]+[('stopped_xyz',c.c_float*3)]+[('events',Event*4096)]")
  text=text.replace('s.magic=0x54414331;s.version=2','s.magic=0x54534d31;s.version=1')
  text=text.replace("{name:getattr(event,name) for name,_ in Event._fields_}","{name:list(getattr(event,name)) if isinstance(getattr(event,name),c.Array) else getattr(event,name) for name,_ in Event._fields_}")
  text=text.replace("RESULT+['phase','active','count']","RESULT+'stop_calls private_stop_calls private_stop_frame move_issued_frame stable_samples stop_gate_samples last_sample_frame'.split()+['phase','active','count']")
  text=text.replace("native.get('restore_mask')==31","native.get('restore_mask')==127")
  text=text.replace("x['tag'] in [1,2,3]","x['tag'] in [1,2,3,4]")
  text=text.replace("status='move_and_return_primitive_verified' if all(checks.values())", "status='stop_move_and_return_primitive_verified' if all(checks.values())")
  needle=" return dict(status='stop_move_and_return_primitive_verified'"
  addition=''' stops=[x for x in events if x['kind']==23 and x['arg']==1 and x['caller']==0x787791 and issued<=x['frame']<=returned]
 gates=[x for x in events if x['kind']==24 and x['frame']==native.get('move_issued_frame') and not x['path'] and not (x['sm_flags']&0xffff) and x['source']==1]
 checks['one_normal_stop']=native.get('stop_calls')==1 and native.get('private_stop_calls')==1 and len(stops)==1 and sum(x['kind']==20 and x['tag']==4 and x['arg']==1 for x in events)==1 and sum(x['kind']==21 and x['tag']==4 for x in events)==1
 checks['deferred_stop_before_move']=len(gates)==1 and len(stops)==1 and gates[0]['frame']>stops[0]['frame'] and gates[0]['seq']>stops[0]['seq'] and native.get('stable_samples',0)>=3 and native.get('stop_gate_samples',0)>=3
 clean=[x for x in events if x['kind']==3 and len(stops)==1 and stops[0]['frame']<x['frame']<native.get('move_issued_frame',0) and not x['path'] and not(x['sm_flags']&0xffff) and x['source']==1]
 checks['clean_stop_samples']=len({x['frame'] for x in clean})>=2
'''
  assert needle in text;text=text.replace(needle,addition+needle)
  text=text.replace("durable(target,report);handle=None", "report.update(native_binary_sha256=hashlib.sha256((HERE/'bin/TacticalStopMove.dll').read_bytes()).hexdigest(),native_host_sha256=hashlib.sha256((HERE/'bin/tactical_host.exe').read_bytes()).hexdigest(),wrapper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest());durable(target,report);handle=None")
 (out/name).write_text(text)
print(out)
