"""Create an isolated normal CommandButton toggle diagnostic, preserving all baselines."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
DEST=HERE/'toggle-aux';DEST.mkdir(exist_ok=True)
extra='button button_schema command_set initial_weapon_asset initial_weapon_entry toggle_calls toggle_hook_calls toggle_frame ak_samples last_ak_frame observed_weapon_asset observed_weapon_entry observed_ammo cash_before cash_after button_result post_actor_disposed'.split()
for name in ['shared.h','lease.cpp','host.cpp','build.ps1']:
 text=(HERE/'stop-move'/name).read_text(encoding='utf-8')
 text=text.replace('TacticalStopMove','TacticalWeaponToggle').replace('RA3TacticalStopMove_','RA3TacticalWeaponToggle_').replace('0x54534d31u','0x57544731u').replace('0x36a','0x377')
 if name=='shared.h':
  text=text.replace('float requested[3],effective[3],path_xy[2];','float requested[3],effective[3],path_xy[2];uint32_t weapon_entry,weapon_asset,weapon_ammo,status84;int32_t cash;')
  text=text.replace('Event events[T_CAP];','uint32_t '+','.join(extra)+';Event events[T_CAP];')
 if name=='host.cpp':text=text.replace('restore_mask==127','restore_mask==255')
 if name=='lease.cpp':
  pos=text.index('static void event(')
  helpers=r'''
static uint32_t cash(){uint32_t first=word(p->owner+0xe4),end=word(p->owner+0xe8);if(!first||end<first+4||end-first>64)return 0;uint32_t r=word(first);return word(r+4)+word(r+0x14);}
static uint32_t current_weapon(uint32_t* entry,uint32_t* ammo){*entry=*ammo=0;uint32_t container=word(p->unit+0x37c);if(word(container+8)!=p->unit)return 0;uint32_t a=word(container+0x24),z=word(container+0x28);if(!a||z<a||z-a>256||(z-a)%4)return 0;for(;a<z;a+=4){uint32_t slot=word(a);if(word(slot)!=0xc3a6e0||word(0xc3a6e0+0x24)!=0x6dbe80||word(0xc3a6e0+0x28)!=0x6f88e0)return 0;uint32_t index=word(slot+0x14);if(index>5)return 0;if(index==5)continue;uint32_t e=word(word(slot+0x94)+4*index);if(!e)continue;if(word(e)!=0xc2e324||word(e+8)!=slot)return 0;uint32_t h=word(word(word(e+4)+4));if(word(h)!=0x94d4d96e)return 0;*entry=e;*ammo=word(e+0x1c);return word(h+4);}return 0;}
static bool button_identity(){uint32_t key=word(p->unit+0x464);if(!key){if(word(word(p->unit+0x78)+0x2c)!=0x6de330)return false;key=word(word(word(p->unit+4)+0x14)+0x94);}if(key!=0xb74cf71a||key!=p->command_set||word(p->button)!=0xbe9170||word(p->button+4)!=p->button_schema||word(p->button_schema+4)!=1)return false;uint32_t h=word(p->button_schema);if(word(h)!=0x7d464170||word(h+4)!=0x5977a798)return false;uint32_t store=word(0xcd8d00),node=word(store+0x4c),found=0;for(unsigned i=0;node&&i<128;i++){uint32_t k=word(node+0x10);if(k==key){found=node;break;}node=word(node+(k>=key?4:0));}if(!found)return false;uint32_t list=word(found+0x14)+8;if(word(list)!=0xbe9178||word(0xbe9178)!=0x524c70||word(0xbe9178+0xc)!=0x4d8fc0)return false;uint32_t inner=word(list+4),count=word(inner+4),items=word(inner+8),matches=0;if(!items||!count||count>64)return false;for(unsigned i=0;i<count;i++)matches+=word(items+i*4)==p->button;return matches==1;}
'''
  text=text[:pos]+helpers+text[pos:]
  text=text.replace('e.seq=0;p->events[i]=e;', 'e.weapon_asset=current_weapon(&e.weapon_entry,&e.weapon_ammo);e.status84=word(p->unit+0x84);e.cash=(int32_t)cash();e.seq=0;p->events[i]=e;')
  pos=text.index('struct Hook {')
  hook=r'''
typedef uint32_t (__attribute__((thiscall))*Button)(void*,void*,uint32_t,uint32_t);static Button old_button;
static uint32_t __attribute__((fastcall)) button_hook(void* self,void*,void* button,uint32_t source,uint32_t third){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->unit;if(ours){if(tag==5&&(uintptr_t)button==p->button&&source==1&&third==0)p->toggle_hook_calls++;event(32,(uintptr_t)button,(uintptr_t)__builtin_return_address(0));}uint32_t result=old_button(self,button,source,third);if(ours)event(33,result);InterlockedDecrement(&p->active);return result;}
'''
  text=text[:pos]+hook+text[pos:]
  old='12,{},false,false}};'
  assert old in text
  text=text.replace(old,'12,{},false,false},\n{0x790990,(void*)button_hook,(void**)&old_button,"\\x8b\\x44\\x24\\x0c\\x8b\\x54\\x24\\x08\\x6a\\x00\\x6a\\x00\\x6a\\x00",14,{},false,false}};')
  text=text.replace('i<7','i<8').replace('restore_mask=127','restore_mask=255').replace('restore_mask==127','restore_mask==255')
  text=text.replace('if(!unit()){p->error=32;', 'if(p->phase==2&&p->return_verified&&(!unit()||!identity())){p->post_actor_disposed=1;finish();return;}if(!unit()){p->error=32;')
  begin=text.index('  float xyz[3];read(p->unit+0x38,xyz,12);float dx=xyz[0]-p->target[0]')
  end=text.index('  p->phase=6;',begin)
  text=text[:begin]+'''  uint32_t entry=0,ammo=0;uint32_t asset=current_weapon(&entry,&ammo);if((word(p->unit+0x84)&0x20080000)||!button_identity()||asset!=0x41872ecc||word(p->unit+0x26c)||word(p->owner+0xac)!=p->default_team||word(word(p->owner+0x8c)+0x10)!=p->script_team){p->error=34;finish();return;}p->initial_weapon_asset=asset;p->initial_weapon_entry=entry;p->cash_before=cash();
'''+text[end:]
  old='if(p->stable_samples>=3&&p->stop_gate_samples>=3){event(24);tag=2;p->move_calls++;p->move_issued_frame=now;((Move)0x6eff70)((void*)(uintptr_t)p->update,p->target,0);event(2);tag=0;}'
  new='if(p->stable_samples>=3&&p->stop_gate_samples>=3){event(24);uint32_t e=0,a=0;if(!button_identity()||word(p->unit+0x26c)||current_weapon(&e,&a)!=0x41872ecc){p->error=45;p->return_pending=1;}else{tag=5;p->toggle_calls++;p->toggle_frame=now;p->button_result=((Button)0x790990)((void*)(uintptr_t)p->unit,(void*)(uintptr_t)p->button,1,0);event(30);tag=0;}}'
  assert old in text;text=text.replace(old,new).replace('if(!p->move_calls&&!p->return_pending','if(!p->toggle_calls&&!p->return_pending')
  text=text.replace('  if(p->move_calls&&dx*dx+dy*dy<=225)p->arrival_samples++;','''  if(p->toggle_calls&&now!=p->last_ak_frame){p->last_ak_frame=now;p->observed_weapon_asset=current_weapon(&p->observed_weapon_entry,&p->observed_ammo);if(p->observed_weapon_asset==0x447ea26e&&now-p->toggle_frame>=15)p->ak_samples++;else p->ak_samples=0;if(p->ak_samples==3)event(31);}
''')
  text=text.replace('p->arrival_samples>=3','p->ak_samples>=3')
  text=text.replace('p->returned_frame=now;p->return_pending=0;','p->returned_frame=now;p->cash_after=cash();p->return_pending=0;')
  text=text.replace('(p->type_hash!=0x19ab11af&&p->type_hash!=0x2c358c61)','p->type_hash!=0x19ab11af')
  text=text.replace('float dx=xyz[0]-p->target[0],dy=xyz[1]-p->target[1];','')
  text=text.replace('if(!identity()){p->error=31;p->lifecycle_fail++;finish();return;}','if(!identity()&&p->phase==2&&p->return_verified){p->post_actor_disposed=1;finish();return;}if(!identity()){p->error=31;p->lifecycle_fail++;finish();return;}')
 (DEST/name).write_text(text,encoding='utf-8')
print('Created isolated toggle-aux; no game interaction')
