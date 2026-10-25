"""Read-only current-player selection for the normal-stance primitive."""
import hashlib,importlib.util,math,re,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parent.parent
HEALTH={0x19ab11af:80.,0x2c358c61:96.}

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def external_source_paths():
 return [BRIDGE/p for p in ('tactical/ordered-combo/lease.py','tactical/mission_actor_admission_v2.py','tactical/grounded_status_v2.py','tactical/grounded_status.py','tactical/mobility_guard.py','visibility/capability.py','visibility/collector.py','visibility/projection.py','production/persistent/client.py','production/persistent/shared.h','production/persistent/bin-v2/ProductionPersistent.dll','production/persistent/bin-v2/persistent_host.exe')]

def fingerprints():return {p.relative_to(BRIDGE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in external_source_paths()}

def original_probe_entries(memory):
 text=(HERE/'lease.cpp').read_text().split('static Hook hooks[]={',1)[1].split(';',1)[0]
 rows=re.findall(r'\{(0x[0-9a-f]+),[^\n]*?"((?:\\x[0-9a-f]{2})+)"',text)
 if len(rows)!=6 or len({a for a,_ in rows})!=6:raise ValueError('probe_exact_hook_set')
 for address,escaped in rows:
  expected=bytes.fromhex(escaped.replace('\\x',''))
  if memory.read(int(address,0),len(expected))!=expected:raise ValueError('probe_entry_not_original')

def stance_snapshot(memory,thing):
 def read():
  p=memory.u32(thing+0x380);data=memory.u32(p+4);lst=memory.u32(memory.u32(data+8));count=memory.u32(lst+4);items=memory.u32(lst+8)
  if not p or not data or not lst or not items or not 1<=count<=4:raise ValueError('stance_definition_bounds')
  raw=memory.read(items,count*8);rows=list(struct.unpack('<'+'I'*(count*2),raw));vt=memory.u32(p)
  return dict(module=hex(p),vtable=hex(vt),backref=hex(memory.u32(p+8)),data=hex(data),enum=memory.u32(p+0x38),definition_list=hex(lst),definition_count=count,definition_items=hex(items),definitions=[dict(enum=rows[i],modifier=hex(rows[i+1])) for i in range(0,len(rows),2)],getter=hex(memory.u32(vt+8)))
 first=read();second=read()
 if first!=second:raise ValueError('stance_identity_changed_during_sample')
 if first['vtable']!='0xc37f90' or first['backref']!=hex(thing) or first['getter']!='0x71d3f0' or memory.read(0x71d3f0,6)!=bytes.fromhex('b84c7ec000c3'):raise ValueError('stance_module_identity')
 values=[r['enum'] for r in first['definitions']]
 if len(set(values))!=len(values) or any(type(v) is not int or v not in (0,1,2,3) for v in values) or first['enum'] not in values or 2 not in values:raise ValueError('stance_definition_not_supported')
 if first['enum']!=0:raise ValueError('probe_requires_actual_original_guard0')
 return first

def eligible_actor(unit,admission,stance,owner):
 try:
  h=int(unit['type_hash'],0);g=admission['grounded_status'];s=admission['state_snapshot']
  return unit.get('eligible') is True and h in HEALTH and math.isfinite(g['hp']) and g['hp']>=HEALTH[h] and all(g[k]==unit[k] for k in ('object_id','address','type_hash')) and g['owner']==owner and s['update']==unit['ai_address'] and stance['backref']==unit['address'] and stance['enum']==0
 except (KeyError,ValueError,TypeError):return False

def current_selection(session_path,commander,actor_id=None):
 b=module('rsv1_readonly_ordered_backend',HERE.parent/'ordered-combo/lease.py');pre,session,raw,package,registry,registry_sha,memory=b.readiness(session_path)
 try:
  if pre['commander_id']!=commander:raise ValueError('reserve_commander_binding')
  if pre['paused']:raise ValueError('reserve_requires_running_game')
  original_probe_entries(memory)
  admission=module('rsv1_actor_admission',HERE.parent/'mission_actor_admission_v2.py');mobility=module('rsv1_actor_mobility',HERE.parent/'mobility_guard.py')
  selected=[];rejected=[]
  for unit in pre['units']:
   if actor_id is not None and unit['object_id']!=actor_id:continue
   try:
    current=admission.actor_admission(memory,int(unit['address'],0));stance=stance_snapshot(memory,int(unit['address'],0))
    if not admission.verify_evidence(current)['verified'] or not eligible_actor(unit,current,stance,pre['owner']) or not mobility.mobility_status(memory,int(unit['address'],0))['independently_movable']:raise ValueError('reserve_actor_current_admission')
    selected.append(dict(unit,xyz=current['grounded_status']['xyz'],hp=current['grounded_status']['hp'],admission=current,stance=stance))
   except (ValueError,RuntimeError,KeyError) as error:rejected.append(dict(object_id=unit['object_id'],reason=str(error)))
  if len(selected)!=1:raise ValueError('reserve_requires_one_current_paid_actor')
  actor=selected[0];current=admission.actor_admission(memory,int(actor['address'],0));stance=stance_snapshot(memory,int(actor['address'],0));frame=memory.u32(int(pre['logic'],0)+0x50)
  if not admission.verify_evidence(current)['verified'] or not eligible_actor(actor,current,stance,pre['owner']) or not current['frame']<=frame<=current['frame']+4:raise ValueError('reserve_admission_expired')
  if memory.u32(int(pre['logic'],0)+0x15c) or session_path.read_bytes()!=raw:raise ValueError('reserve_late_paused_or_binding_changed')
  actor.update(xyz=current['grounded_status']['xyz'],hp=current['grounded_status']['hp'],admission=current,stance=stance)
  pre.update(frame=frame,selected=actor,selection_rejections=rejected,external_sources=fingerprints(),enemy_observation_used=False,own_reserve_only=True)
  return b,pre,session,raw,package,registry,registry_sha,memory
 except BaseException:memory.close();raise
