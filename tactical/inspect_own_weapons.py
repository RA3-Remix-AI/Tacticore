"""Mirror verified ground-slot getter reads without invoking native code."""
import argparse,hashlib,importlib.util,json,math,struct
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('weapon_own_bind',HERE/'reusable/lease.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
ASSETS={0x447ea26e:'SovietAntiInfantryInfantryAK47',0x41872ecc:'SovietAntiInfantryInfantryMolotovCocktail'}

def active_weapon(m,thing):
 if m.u32(thing)!=0xc4db60:raise ValueError('thing_identity')
 ident=m.u32(thing+0xdc);owner=m.u32(thing+0x418);container=m.u32(thing+0x37c)
 if m.u32(container+8)!=thing:raise ValueError('weapon_container_backpointer')
 start,end=m.u32(container+0x24),m.u32(container+0x28)
 if not start or end<start or end-start>256 or (end-start)%4:raise ValueError('weapon_slot_bounds')
 selected=None;slots=[]
 for cursor in range(start,end,4):
  slot=m.u32(cursor);vt=m.u32(slot)
  if vt!=0xc3a6e0 or m.u32(vt+0x24)!=0x6dbe80 or m.u32(vt+0x28)!=0x6f88e0:raise ValueError('unverified_slot_getter')
  index=m.u32(slot+0x14)
  if index>5:raise ValueError('slot_index')
  entry=0 if index==5 else m.u32(m.u32(slot+0x94)+index*4)
  row=dict(slot=hex(slot),index=index,active_entry=hex(entry))
  if entry:
   if m.u32(entry)!=0xc2e324 or m.u32(entry+8)!=slot:raise ValueError('weapon_entry_identity')
   template=m.u32(entry+4);schema=m.u32(template+4);header=m.u32(schema);typeid=m.u32(header);instance=m.u32(header+4)
   if typeid!=0x94d4d96e:raise ValueError('not_weapon_template')
   row.update(template_pointer=hex(template),template_type=hex(typeid),template_id=hex(instance),template_name=ASSETS.get(instance),ammo=m.u32(entry+0x1c))
   if selected is None:selected=dict(row)
  slots.append(row)
 if m.u32(thing+0xdc)!=ident or m.u32(thing+0x418)!=owner or m.u32(thing+0x37c)!=container:raise ValueError('unit_changed')
 return dict(object_id=ident,slots=slots,selected=selected,method='read_only_mirror_6f7c60_selector_minus1_6dbe80_6f88e0',mutations=False)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--session',type=Path,default=HERE.parent/'acceptance/active-session.json');ap.add_argument('--object-id',type=int);ap.add_argument('--output',type=Path);a=ap.parse_args();pre,session,raw,package,registry,digest,m=b.readiness(a.session,a.object_id)
 try:
  values=[]
  for u in pre['units']:
   if u['eligible'] and (a.object_id is None or a.object_id==u['object_id']):
    try:values.append(active_weapon(m,int(u['address'],0)))
    except Exception as error:values.append(dict(object_id=u['object_id'],error=str(error)))
  if a.session.read_bytes()!=raw:raise ValueError('session_changed')
  report=dict(session_id=session['session_id'],pid=session['pid'],frame=pre['frame'],units=values,mutations=False,note='Current active entry only; Attack may trigger later native selection. No toggle field is written.')
  if a.output:b.durable(a.output,report)
  print(json.dumps(report,ensure_ascii=False))
 finally:m.close()
if __name__=='__main__':main()
