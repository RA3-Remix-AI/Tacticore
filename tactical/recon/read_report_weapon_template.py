"""Read a reported weapon template's immutable asset header; never call its getter."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('readonly_weapon_backend',HERE.parent/'inspect_own_weapons.py');b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 raw=a.report.read_bytes();source=json.loads(raw.decode('utf-8-sig'));session=json.loads(a.session.read_text(encoding='utf-8-sig'))
 if source['session_id']!=session['session_id'] or source['preflight']['pid']!=session['pid']:raise ValueError('session_mismatch')
 m=b.b.Memory(session['pid'],session)
 try:
  pointer=source['native']['weapon_template'];schema=m.u32(pointer+4);header=m.u32(schema);type_id=m.u32(header);asset_id=m.u32(header+4)
  if type_id!=0x94d4d96e:raise ValueError('not_weapon_template')
  evidence=dict(session_id=session['session_id'],pid=session['pid'],report=str(a.report.resolve()),report_sha256=hashlib.sha256(raw).hexdigest(),reported_entry=hex(source['native']['weapon_entry']),reported_template=hex(pointer),template_schema=hex(schema),asset_header=hex(header),asset_type=hex(type_id),asset_id=hex(asset_id),template_name=b.ASSETS.get(asset_id),method='reported_template_plus4_to_schema_to_asset_header',mutations=False,model_eligible=False,note='Template asset header only; does not dereference a dead actor or weapon entry, and does not prove fire attribution.')
  if m.u32(pointer+4)!=schema or m.u32(schema)!=header or m.u32(header+4)!=asset_id:raise ValueError('template_changed')
  b.b.durable(a.output,evidence);print(json.dumps(evidence))
 finally:m.close()
if __name__=='__main__':main()
