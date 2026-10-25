"""Offline independent air scout using normal script Move opcode0, not opcode83."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent;SOURCE=ROOT.parent/'recon-air';OUT=ROOT.parent/'recon-air-normal'
OUT.mkdir(exist_ok=False)
for name in ['shared.h','lease.cpp','host.cpp','lease.py','build.ps1','logic.py','probe.py']:
 text=(SOURCE/name).read_text(encoding='utf-8')
 for old,new in [('TacticalAirScout','TacticalAirScoutNormal'),('RA3TacticalAirScout','RA3TacticalAirScoutNormal'),('0x41535231','0x41534e31'),('WM_APP+0x370','WM_APP+0x371')]:text=text.replace(old,new)
 if name=='shared.h':
  text=text.replace('float requested[3],effective[3],path_xy[2];','float requested[3],effective[3],path_xy[2],command_xyz[3];uint32_t argument_path;float argument_limit;')
  text=text.replace('last_sample_frame;','last_sample_frame,last_arrival_frame;')
 if name=='lease.cpp':
  text=text.replace('uint32_t caller=0){LONG i=', 'uint32_t caller=0,const float* input=NULL,uint32_t input_path=0,float input_limit=0){LONG i=')
  text=text.replace('e.source=word(p->update+0x50);', 'e.source=word(p->update+0x50);if(input)read((uintptr_t)input,e.command_xyz,12);e.argument_path=input_path;e.argument_limit=input_limit;')
  start=text.index('typedef void (__attribute__((thiscall))*Move)');end=text.index('static bool weapon_identity()',start) if 'static bool weapon_identity()' in text else -1
  text=text.replace('typedef void (__attribute__((thiscall))*Move)(void*,float*,uint32_t);','typedef void (__attribute__((thiscall))*Move)(void*,float*,void*,float,uint32_t);typedef void (__attribute__((thiscall))*MoveFacade)(void*,float*,uint32_t);')
  text=text.replace('static Move old_move;','static Move old_move;static MoveFacade old_move_facade;')
  old='static void __attribute__((fastcall)) move_hook'
  a=text.index(old);z=text.index('static void __attribute__((fastcall))',a+len(old))
  text=text[:a]+'''static void __attribute__((fastcall)) move_hook(void* self,void*,float* xyz,void* path,float limit,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update;if(ours){if(!tag)p->native_move++;event(10,source,(uintptr_t)__builtin_return_address(0),xyz,(uintptr_t)path,limit);}old_move(self,xyz,path,limit,source);if(ours)event(11,source,0,xyz,(uintptr_t)path,limit);InterlockedDecrement(&p->active);}
static void __attribute__((fastcall)) move_facade_hook(void* self,void*,float* xyz,uint32_t source){InterlockedIncrement(&p->active);bool ours=(uintptr_t)self==p->update+0x24;if(ours)event(30,source,(uintptr_t)__builtin_return_address(0),xyz);old_move_facade(self,xyz,source);if(ours)event(31,source,0,xyz);InterlockedDecrement(&p->active);}
'''+text[z:]
  old_hook='{0x6eff70,(void*)move_hook,(void**)&old_move,"\\x56\\x8b\\xf1\\x8b\\x4e\\x3c\\x8b\\x01\\x8b\\x50\\x38\\xff\\xd2",13,{},false,false}'
  new_hook='{0x76d9d0,(void*)move_hook,(void**)&old_move,"\\x56\\x8b\\xf1\\x57\\x8b\\x7e\\x08\\x8b\\xcf",9,{},false,false}'
  if old_hook not in text:raise ValueError('original_move_hook_site_changed')
  text=text.replace(old_hook,new_hook)
  text=text.replace('12,{},false,false}};','12,{},false,false},\n{0x571d90,(void*)move_facade_hook,(void**)&old_move_facade,"\\x83\\xec\\x5c\\x8b\\x44\\x24\\x64\\x56\\x6a\\x01\\x50\\x8b\\xf1",13,{},false,false}};')
  text=text.replace('i<7;i++','i<8;i++').replace('restore_mask==127','restore_mask==255').replace('restore_mask=127','restore_mask=255')
  text=text.replace('((Move)0x6eff70)((void*)(uintptr_t)p->update,p->target,0);','((MoveFacade)0x571d90)((void*)(uintptr_t)(p->update+0x24),p->target,1);')
  text=text.replace('if(p->move_calls&&dx*dx+dy*dy<=225)p->arrival_samples++;','if(p->move_calls&&now!=p->last_arrival_frame){p->last_arrival_frame=now;if(dx*dx+dy*dy<=225)p->arrival_samples++;else p->arrival_samples=0;}')
 if name=='lease.py':
  text=text.replace("('path_xy',c.c_float*2)]", "('path_xy',c.c_float*2),('command_xyz',c.c_float*3),('argument_path',U),('argument_limit',c.c_float)]")
  text=text.replace("+[(x,c.c_float*3) for x in ['requested','effective']]+[('path_xy',c.c_float*2)]", "+[(x,c.c_float*3) for x in ['requested','effective']]+[('path_xy',c.c_float*2),('command_xyz',c.c_float*3),('argument_path',U),('argument_limit',c.c_float)]")
  text=text.replace("last_sample_frame'.split()","last_sample_frame last_arrival_frame'.split()")
  text=text.replace("native.get('restore_mask')==127","native.get('restore_mask')==255")
 if name=='logic.py':text=text.replace("n.get('restore_mask')==127","n.get('restore_mask')==255")
 if name=='probe.py':text=text.replace("get('restore_mask')==127","get('restore_mask')==255")
 (OUT/name).write_text(text,encoding='utf-8')
print(OUT)
