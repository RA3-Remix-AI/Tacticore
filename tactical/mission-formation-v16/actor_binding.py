"""Role identity derived from original Native paid-slot admission outputs.

These descriptors are labeled views, not a replacement preflight snapshot or
current-liveness certificate. Callers must independently audit the raw slot.
"""
def number(value):return int(value,0) if isinstance(value,str) else value

def actor(report,role):
 if type(role) is not int or role not in (0,1):raise ValueError('mf16_role')
 n=report['native'];slot=n['slots'][role];s=slot['admission_last']
 names=('thing','id','type_hash','owner','template_ptr','update')
 if type(s.get('frame')) is not int or s['frame']<=0 or any(type(s.get(k)) is not int or s[k]<=0 for k in names):raise ValueError('mf16_actor_not_admitted')
 expected=0x19ab11af if role==0 else 0x2c358c61
 if s['type_hash']!=expected or s['team']!=slot['admitted_team'] or s['stance']!=0:raise ValueError('mf16_actor_admission_binding')
 if any(slot[k]!=s[v] for k,v in (('thing','thing'),('id','id'),('template_ptr','template_ptr'),('update','update'))):raise ValueError('mf16_slot_identity')
 mirror=n['support'] if role else n
 for key,value in (('thing' if role else 'unit',s['thing']),('id' if role else 'object_id',s['id']),('hash' if role else 'type_hash',s['type_hash']),('update',s['update'])):
  if mirror[key]!=value:raise ValueError('mf16_runtime_actor_mirror')
 return dict(address=hex(s['thing']),object_id=s['id'],type_hash=hex(s['type_hash']),owner_address=hex(s['owner']),ai_address=hex(s['update']),team=hex(s['team']),hp=s['hp'],xyz=list(s['xyz']),source='native_paid_slot_actual_admission',role=role,observed_frame=s['frame'],admission_sample=s,stance=dict(module=hex(s['stance_module']),vtable=hex(s['stance_vtable']),backref=hex(s['stance_backref']),data=hex(s['stance_data']),enum=s['stance'],definition_list=hex(s['stance_enum_list']),definition_count=s['stance_enum_count'],definitions=[dict(enum=s['stance_enum_entries'][2*i],modifier=hex(s['stance_enum_entries'][2*i+1])) for i in range(s['stance_enum_count'])]))

def stance_admission(report,role):
 a=actor(report,role);s=a['admission_sample'];count=s['stance_enum_count']
 if type(count) is not int or not 1<=count<=4 or len(s['stance_enum_entries'])!=8:raise ValueError('mf16_actual_stance_definitions')
 return dict(source=a['source'],role=role,observed_frame=s['frame'],module=s['stance_module'],vtable=s['stance_vtable'],backref=s['stance_backref'],data=s['stance_data'],definition_list=s['stance_enum_list'],definition_count=count,definition_entries=list(s['stance_enum_entries'][:2*count]),original_enum=s['stance'],mutations=False)
