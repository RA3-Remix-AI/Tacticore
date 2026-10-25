from pathlib import Path
root=Path('bridge-probe/tactical');out=root/'combat-commit';out.mkdir(exist_ok=True)
for name in ['shared.h','host.cpp','lease.cpp','lease.py','build.ps1']:
 s=(root/'combat-stack'/name).read_text().replace('TacticalCombatStack','TacticalCombatCommit').replace('RA3TacticalCombatStack','RA3TacticalCombatCommit').replace('tactical-combat-stack-','tactical-combat-commit-')
 if name=='shared.h':
  s=s.replace('0x54414331u','0x434f4d31u').replace('WM_APP+0x36b','WM_APP+0x36e')
  s=s.replace('float damage_total;', 'uint32_t commit_hook_calls,commit_visible_calls,commit_own_calls;float damage_total;')
 if name=='lease.cpp':
  s=s.replace('p->version!=5','p->version!=6').replace('i<7','i<8').replace('restore_mask=127','restore_mask=255').replace('restore_mask==127','restore_mask==255')
  s=s.replace('if(kind==20||kind==21||kind==22)','if(kind==20||kind==21||kind==22||kind==24||kind==25)').replace('if(kind==20||kind==21){','if(kind==20||kind==21||kind==24||kind==25){')
  needle='struct Hook {'
  extra='''typedef void (__attribute__((thiscall))*Commit)(void*,float,void*);static Commit old_commit;
static void __attribute__((fastcall)) commit_hook(void* self,void*,float delta,void* info){
 InterlockedIncrement(&p->active);InterlockedIncrement((LONG*)&p->commit_hook_calls);uint32_t body=(uintptr_t)self;bool observed=p->phase==1&&GetCurrentThreadId()==p->thread&&body==word(p->target_unit+0x33c)&&word(body-8)==p->target_unit&&visible_target();uint32_t source=0;float before=0;if(observed){p->commit_visible_calls++;source=word((uintptr_t)info+8);read(body+4,&before,4);}old_commit(self,delta,info);
 if(observed&&visible_target()){float after=0;read(body+4,&after,4);if(isfinite(before)&&isfinite(after)&&isfinite(delta)){event(source==p->object_id?24:25,source,(uintptr_t)__builtin_return_address(0),before,after,-delta);if(source==p->object_id&&before>after)p->commit_own_calls++;}}
 InterlockedDecrement(&p->active);
}
'''
  assert needle in s;s=s.replace(needle,extra+needle)
  s=s.replace('11,{},false,false}};', '11,{},false,false},\n{0x765190,(void*)commit_hook,(void**)&old_commit,"\\x8b\\x44\\x24\\x08\\x85\\xc0\\xf3\\x0f\\x10\\x4c\\x24\\x04",12,{},false,false}};')
  s=s.replace('p->damage_count>0||!visible_target()', 'p->damage_count>0||p->commit_own_calls>0||!visible_target()')
 if name=='host.cpp':s=s.replace('restore_mask==127','restore_mask==255')
 if name=='lease.py':
  s=s.replace("[('damage_total',c.c_float)]", "[(x,U) for x in ['commit_hook_calls','commit_visible_calls','commit_own_calls']]+[('damage_total',c.c_float)]")
  s=s.replace('s.magic=0x54414331;s.version=5','s.magic=0x434f4d31;s.version=6')
  s=s.replace("RESULT+['phase','active','count']", "RESULT+['phase','active','count','commit_hook_calls','commit_visible_calls','commit_own_calls']")
  s=s.replace("n.get('restore_mask')==127", "n.get('restore_mask')==255")
  s=s.replace("durable(target,report);handle=None", "\n if target.exists():raise ValueError('existing_report_requires_recovery')\n durable(target,report);handle=None")
  s=s.replace("return dict(status=", "checks['diagnostic_only_no_capability']=False\n return dict(status=",1)
 (out/name).write_text(s)
print(out)
