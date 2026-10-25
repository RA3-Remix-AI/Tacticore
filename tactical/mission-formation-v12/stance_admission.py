"""Read-only normal StancesBehavior admission for scoped HOLD_POSITION control."""
import struct

def inspect_stance(memory,thing):
 def read():
  module=memory.u32(thing+0x380);data=memory.u32(module+4);definitions=memory.u32(memory.u32(data+8));count=memory.u32(definitions+4);items=memory.u32(definitions+8)
  if not module or not data or not definitions or not items or not 1<=count<=4:raise ValueError('stance_definition_bounds')
  entries=list(struct.unpack('<'+'I'*(count*2),memory.read(items,count*8)))
  return dict(module=module,vtable=memory.u32(module),backref=memory.u32(module+8),data=data,definition_list=definitions,definition_count=count,definition_items=items,definition_entries=entries,original_enum=memory.u32(module+0x38))
 a=read();b=read()
 if a!=b:raise ValueError('stance_changed_during_admission')
 if a['vtable']!=0xc37f90 or a['backref']!=thing or memory.u32(a['vtable']+8)!=0x71d3f0 or memory.read(0x71d3f0,6)!=bytes.fromhex('b84c7ec000c3'):raise ValueError('stance_module_binding')
 enums=a['definition_entries'][::2]
 if a['original_enum']!=0 or not {0,2}<=set(enums) or len(enums)!=len(set(enums)) or any(v not in (0,1,2,3) for v in enums):raise ValueError('stance_original_or_allowed_enum')
 return dict(a,mutations=False)
