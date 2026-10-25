"""Isolated one-lease normal weapon preparation plus the verified attack path."""
from pathlib import Path
HERE=Path(__file__).resolve().parent;DEST=HERE/'ordered-combo';DEST.mkdir(exist_ok=True)
EXTRA='button button_schema command_set initial_weapon_asset initial_weapon_entry toggle_calls toggle_hook_calls toggle_frame ak_samples last_ak_frame prepare_reconstituted_stops observed_weapon_asset observed_weapon_entry observed_ammo total_private_stops prepare_gate_frame'.split()
for name in ['shared.h','lease.cpp','host.cpp','build.ps1','lease.py']:
 text=(HERE/'ordered-attack'/name).read_text(encoding='utf-8').replace('TacticalOrderedAttack','TacticalOrderedCombo').replace('RA3TacticalOrderedAttack_','RA3TacticalOrderedCombo_').replace('0x4f415431','0x4f434231')
 if name=='shared.h':
  text=text.replace('(WM_APP+0x374)','(WM_APP+0x378)')
  text=text.replace('stack_words[128];','stack_words[128];uint32_t active_weapon_entry,active_weapon_asset,active_weapon_ammo,status84;')
  text=text.replace('Event events[T_CAP];','uint32_t '+','.join(EXTRA)+';Event events[T_CAP];')
 if name=='host.cpp':text=text.replace('restore_mask==2047','restore_mask==4095')
 if name=='lease.cpp':
  toggle=(HERE/'toggle-aux/lease.cpp').read_text(encoding='utf-8');a=toggle.index('static uint32_t current_weapon(');z=toggle.index('static void event(',a);helpers=toggle[a:z]
  pos=text.index('static void event(');text=text[:pos]+helpers+text[pos:]
  text=text.replace('e.seq=0;p->events[i]=e;','e.active_weapon_asset=current_weapon(&e.active_weapon_entry,&e.active_weapon_ammo);e.status84=word(p->unit+0x84);e.seq=0;p->events[i]=e;')
  old='if(p->phase==1&&p->stop_calls&&source==1&&caller==0x787791&&(p->lease_stage==0||p->lease_stage==2)){p->private_stop_calls++;p->private_stop_frame=frame();}'
  new='p->total_private_stops++;if(p->phase==1&&source==1&&caller==0x787791){if(p->lease_stage==3){p->prepare_reconstituted_stops++;}else if(p->stop_calls&&(p->lease_stage==0||p->lease_stage==4||p->lease_stage==2)){p->private_stop_calls++;p->private_stop_frame=frame();}}'
  assert old in text;text=text.replace(old,new)
  pos=text.index('struct Hook {');a=toggle.index('typedef uint32_t (__attribute__((thiscall))*Button)');z=toggle.index('struct Hook {',a);hook=toggle[a:z].replace('event(32,','event(40,').replace('event(33,','event(41,');text=text[:pos]+hook+text[pos:]
  end='13,{},false,false}};';assert end in text
  text=text.replace(end,'13,{},false,false},\n{0x790990,(void*)button_hook,(void**)&old_button,"\\x8b\\x44\\x24\\x0c\\x8b\\x54\\x24\\x08\\x6a\\x00\\x6a\\x00\\x6a\\x00",14,{},false,false}};')
  text=text.replace('i<11','i<12').replace('restore_mask=2047','restore_mask=4095').replace('restore_mask==2047','restore_mask==4095').replace('p->version!=7','p->version!=8')
  text=text.replace('(p->type_hash!=0x19ab11af&&p->type_hash!=0x2c358c61)','p->type_hash!=0x19ab11af')
  text=text.replace('if(word(p->unit+0x238)||word(p->update)!=0xc48670', 'if((word(p->unit+0x84)&0x20080000)||!button_identity()||word(p->unit+0x238)||word(p->update)!=0xc48670')
  mark='  p->phase=6;p->original_team=word(p->unit+0x414);'
  text=text.replace(mark,'  uint32_t initial_ammo=0;p->initial_weapon_asset=current_weapon(&p->initial_weapon_entry,&initial_ammo);if(p->initial_weapon_asset!=0x447ea26e&&p->initial_weapon_asset!=0x41872ecc){p->error=46;finish();return;}\n'+mark)
  old='  if(p->lease_stage==0&&!end){if(!visible_target()){end=true;}else if(stop_settled(now)){event(37);if(word(p->unit+0x238)){p->error=43;end=true;}else{p->lease_stage=1;tag=2;p->attack_calls++;p->attack_facade_calls++;((Attack)0x572280)((void*)(uintptr_t)(p->update+0x24),(void*)(uintptr_t)p->target_unit,0x7fffffff,1);event(2);tag=0;}}else if(now-p->issued_frame>=30){p->error=44;end=true;}}'
  assert old in text
  new=r'''  if(p->lease_stage==0&&!end){if(!visible_target()){end=true;}else if(stop_settled(now)){event(37);uint32_t entry=0,ammo=0;uint32_t asset=current_weapon(&entry,&ammo);if(word(p->unit+0x238)||!button_identity()){p->error=43;end=true;}else if(asset==0x447ea26e){p->prepare_gate_frame=now;event(42);issue_stop(4);}else if(asset==0x41872ecc&&word(p->unit+0x26c)==0){p->lease_stage=3;tag=5;p->toggle_calls++;p->toggle_frame=now;((Button)0x790990)((void*)(uintptr_t)p->unit,(void*)(uintptr_t)p->button,1,0);event(39);tag=0;}else{p->error=46;end=true;}}else if(now-p->issued_frame>=30){p->error=44;end=true;}}
  if(p->lease_stage==3&&!end){if(!visible_target()){end=true;}else if(now!=p->last_ak_frame){p->last_ak_frame=now;p->observed_weapon_asset=current_weapon(&p->observed_weapon_entry,&p->observed_ammo);uint32_t sm=word(p->update+0x3c);bool idle=word(word(sm+4)+4)==16&&!(word(sm+0x78)&0xffff)&&word(p->update+0x150)==0&&word(p->unit+0x238)==0&&word(p->update+0x50)==1;if(p->observed_weapon_asset==0x447ea26e&&now-p->toggle_frame>=15&&idle)p->ak_samples++;else p->ak_samples=0;if(p->ak_samples>=3){p->prepare_gate_frame=now;event(42);issue_stop(4);}else if(now-p->toggle_frame>=60){p->error=47;end=true;}}}
  if(p->lease_stage==4&&!end){if(!visible_target()){end=true;}else if(stop_settled(now)){event(43);uint32_t e=0,a=0;if(current_weapon(&e,&a)!=0x447ea26e||!a||a>3||word(p->unit+0x238)){p->error=46;end=true;}else{p->lease_stage=1;tag=2;p->attack_calls++;p->attack_facade_calls++;((Attack)0x572280)((void*)(uintptr_t)(p->update+0x24),(void*)(uintptr_t)p->target_unit,0x7fffffff,1);event(2);tag=0;}}else if(now-p->stop_issue_frame>=30){p->error=44;end=true;}}
'''
  text=text.replace(old,new)
 if name=='lease.py':
  text=text.replace("('stack_words',U*128)]","('stack_words',U*128)]+[(x,U) for x in 'active_weapon_entry active_weapon_asset active_weapon_ammo status84'.split()]")
  text=text.replace("[('events',Event*4096)]","[(x,U) for x in "+repr(' '.join(EXTRA))+".split()]+[('events',Event*4096)]")
  text=text.replace("from ordered_qualification import qualify","from combo_qualification import qualify")
  text=text.replace("report['native']['target']=list(shared.target);", "report['native'].update({x:getattr(shared,x) for x in "+repr(' '.join(EXTRA))+".split()});report['native']['target']=list(shared.target);")
  text=text.replace("obs=json.loads(args.natural.read_text", "sys.path.insert(0,str(HERE.parent));from mobility_guard import mobility_status\n if not mobility_status(memory,int(pre['selected']['address'],0))['independently_movable']:raise ValueError('actor_garrisoned_or_immobile')\n import importlib.util\n sp=importlib.util.spec_from_file_location('combo_button_resolver',HERE.parent/'recon/read_own_command_buttons.py');resolver=importlib.util.module_from_spec(sp);sp.loader.exec_module(resolver);button_info=resolver.inspect(memory,int(pre['selected']['address'],0))\n obs=json.loads(args.natural.read_text")
  text=text.replace("if target.exists():raise ValueError('existing_report_requires_recovery')", "report['request']['button']=button_info\n if target.exists():raise ValueError('existing_report_requires_recovery')")
  text=text.replace('s.version=7;','s.version=8;')
  text=text.replace("s.type_hash=int(pre['selected']['type_hash'],0);", "s.type_hash=int(pre['selected']['type_hash'],0);s.button=int(button_info['toggle']['entry'],0);s.button_schema=int(button_info['toggle']['schema'],0);s.command_set=int(button_info['command_set_hash'],0);")
 (DEST/name).write_text(text,encoding='utf-8')
print('Created independent ordered-combo sources; no SDK interaction')
