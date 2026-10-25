"""Read-only mirror of 590020/6fcce0/4df970 command-button lookup. Never calls it."""
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('button_lookup_own',HERE.parent/'ground-normal-terrain-aux/lease.py');b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
sys.path.insert(0,str(HERE.parents[1]/'reference/Ra3-Copilot/unit-codes/tools'))
from sage_hash import sage_hash
COMMAND='Command_ToggleMolotovCocktailSpecialPower'
def inspect(m,unit):
 if m.u32(unit)!=0xc4db60:raise ValueError('thing_vtable')
 oid=m.u32(unit+0xdc);owner=m.u32(unit+0x418)
 if m.u32(owner+0x20)!=3 or m.u32(m.u32(unit+4)+8)!=0x19ab11af:raise ValueError('own_conscript_required')
 key=m.u32(unit+0x464);template=m.u32(unit+4)
 if not key:
  if m.u32(m.u32(unit+0x78)+0x2c)!=0x6de330 or m.read(0x6de330,4)!=bytes.fromhex('8b418cc3'):raise ValueError('template_getter_not_verified')
  key=m.u32(m.u32(template+0x14)+0x94)
 if key!=sage_hash('SovietAntiInfantryInfantryCommandSet'.lower()):raise ValueError('unexpected_command_set')
 store=m.u32(0xcd8d00);end=store+0x44;node=m.u32(store+0x4c);best=end;visited=[]
 while node:
  if node in visited or len(visited)>=128:raise ValueError('command_set_tree_bounds')
  visited.append(node)
  if m.u32(node+0x10)>=key:best=node;node=m.u32(node+4)
  else:node=m.u32(node)
 if best==end or m.u32(best+0x10)!=key:raise ValueError('command_set_not_found')
 value=m.u32(best+0x14);listing=value+8
 if m.u32(listing)!=0xbe9178 or m.u32(0xbe9178)!=0x524c70 or m.u32(0xbe9178+0xc)!=0x4d8fc0:raise ValueError('command_list_getter_changed')
 inner=m.u32(listing+4);count=m.u32(inner+4);items=m.u32(inner+8)
 if not 1<=count<=64 or not items:raise ValueError('command_list_bounds')
 buttons=[]
 for index in range(count):
  entry=m.u32(items+index*4);schema=m.u32(entry+4);header=m.u32(schema)
  if m.u32(entry)!=0xbe9170 or m.u32(header)!=0x7d464170:raise ValueError('logic_command_asset_identity')
  buttons.append(dict(index=index,entry=hex(entry),schema=hex(schema),asset_header=hex(header),asset_type=hex(m.u32(header)),asset_id=hex(m.u32(header+4))))
 wanted=sage_hash(COMMAND.lower());matches=[x for x in buttons if int(x['asset_id'],0)==wanted]
 if len(matches)!=1:raise ValueError('toggle_button_not_unique')
 if m.u32(unit)!=0xc4db60 or m.u32(unit+0xdc)!=oid or m.u32(unit+0x418)!=owner or m.u32(unit+4)!=template:raise ValueError('unit_changed')
 return dict(object_id=oid,unit=hex(unit),owner=hex(owner),command_set_hash=hex(key),store=hex(store),tree_node=hex(best),list=hex(listing),count=count,buttons=buttons,toggle=dict(matches[0],name=COMMAND),ordinary_script_abi=dict(entry='0x790990',this='Thing',stack_arguments=['CommandButtonInfo*','FROM_SCRIPT=1',0],callee_pop_bytes=12,source_caller='0x590080..0x590087'),method='pure_read_mirror_of_native_script_lookup',mutations=False,model_eligible=False)
def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--object-id',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();pre,s,raw,*rest=b.readiness(a.session,a.object_id);m=rest[-1]
 try:
  report=inspect(m,int(pre['selected']['address'],0));report.update(session_id=s['session_id'],pid=s['pid'],frame=pre['frame'],executable_sha256=b.EXPECTED,package_sha256=s['mod_sha256'],source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
  b.durable(a.output,report);print(json.dumps(report,ensure_ascii=False))
 finally:m.close()
if __name__=='__main__':main()
