"""Conservative source audit, tied to an exact compiled experiment package.
Only templates present in compiled stream with an auditable source/inheritance
chain can enter allowlist. Detection support does not enable stealth contacts.
"""
import argparse,hashlib,json,re,sys,xml.etree.ElementTree as E
from pathlib import Path
SDK=Path('E:/RA3Modding/SDK');ROOT=Path(__file__).resolve().parent
sys.path.insert(0,'E:/RA3Modding/Analysis/Remix037')
from manifest import parse
NS='{uri:ea.com:eala:asset}'
RISK_TAG=re.compile(r'invisib|camouflage|disguise|(?:^|[^a-z])stealth',re.I)
RISK_STATUS={'STEALTH_GARRISON','STEALTHED','HIDDEN','CAN_STEALTH','CAN_STEALTH_FROM_PRODUCER','GARRISON_CAN_STEALTH','BROADCASTING_INVISIBILITY','INVISIBLE_DETECTED_BY_FRIEND','INVISIBLE_DETECTED'}
def audit_node(node):
 reasons=[]
 for item in node.iter():
  tag=item.tag.split('}')[-1]
  if RISK_TAG.search(tag) and tag!='StealthDetectorUpdate':reasons.append('capability_module:'+tag)
  for key,value in item.attrib.items():
   if key in ('ObjectStatus','Status','StatusBitFlags','StatusBitFlagsExclude','KindOf') and {x.lstrip('+-') for x in value.split()}&RISK_STATUS:reasons.append('capability_status:'+value)
   if key.lower() in ('invisibilitytemplate','invisibilitytype','invertstealthopacity'):reasons.append('capability_attribute:'+key)
 return sorted(set(reasons))

def classify_role(name,kinds):
 physical='air' if 'AIRCRAFT' in kinds else 'naval' if 'SHIP' in kinds else 'infantry' if 'INFANTRY' in kinds else 'armor' if 'VEHICLE' in kinds else 'structure' if 'STRUCTURE' in kinds else None
 if name=='SovietRefinery' and physical=='structure' and {'REFINERY','SUPPLY_GATHERING_CENTER'}<=kinds:
  return 'economy',physical,{'classification_revision':'exact_soviet_refinery_v1','required_effective_kind_of':['REFINERY','SUPPLY_GATHERING_CENTER'],'effective_kind_of':sorted(kinds),'scope':'Source functional role only; no live harassment capability granted.'}
 return ('economy' if 'HARVESTER' in kinds else physical),physical,None
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--package',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 index={};duplicates=set()
 for directory in [SDK/'SAGEXML',SDK/'Mods/TriadFront/data']:
  layer={};layer_duplicates=set()
  for p in directory.rglob('*.xml'):
   try:root=E.parse(p).getroot()
   except (E.ParseError,OSError):continue
   for ob in root:
    if ob.tag!=NS+'GameObject' or 'id' not in ob.attrib:continue
    key=ob.attrib['id'].lower()
    if key in layer:layer_duplicates.add(key)
    layer[key]=(p,ob)
  duplicates.difference_update(layer);duplicates.update(layer_duplicates);index.update(layer)
 def chain(key,seen=None):
  seen=set() if seen is None else seen
  if key in seen:raise ValueError('Inheritance cycle')
  if key in duplicates:raise ValueError('Duplicate source definition')
  if key not in index:raise ValueError('Unresolved inheritance')
  seen.add(key);p,node=index[key];result=[(p,node)]
  parent=node.attrib.get('inheritFrom') or node.attrib.get('inheritsFrom')
  if parent:result+=chain(parent.lower(),seen)
  return result
 entries={};rejected={}
 for row in parse(a.manifest):
  if not row['name'].startswith('GameObject:'):continue
  name=row['name'].split(':',1)[1]
  try:
   sources=chain(name.lower());risk=[r for _,n in sources for r in audit_node(n)]
   if risk:raise ValueError(';'.join(sorted(set(risk))))
   # Exclude weapon/prop/effect objects and unknown capability role classes.
   kinds=set()
   for _,n in reversed(sources):
    tokens=n.attrib.get('KindOf','').split()
    if tokens and not any(x.startswith(('+','-')) for x in tokens):kinds=set(tokens)
    else:
     for token in tokens:
      if token.startswith('-'):kinds.discard(token[1:])
      else:kinds.add(token.lstrip('+'))
   role,physical,role_evidence=classify_role(name,kinds)
   if role is None or 'SELECTABLE' not in kinds:raise ValueError('Not an audited selectable combat/structure class')
   entries[hex(row['instance_id'])]={'template':name,'role':role,'physical_role':physical,'source_chain':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p,_ in sources],'compiled_asset_instance_hash':hex(row['instance_hash']),'source_audited_no_intrinsic_stealth':True}
   if role_evidence:entries[hex(row['instance_id'])]['functional_role_evidence']=role_evidence
  except ValueError as e:rejected[name]=str(e)
 report={'schema_version':1,'package_sha256':hashlib.sha256(a.package.read_bytes()).hexdigest(),'compiled_manifest_sha256':hashlib.sha256(a.manifest.read_bytes()).hexdigest(),'source_audit_only':True,'detection_verified':False,'runtime_invisibility_must_still_be_excluded':True,'templates':entries,'rejected':rejected,'note':'Source audit is not a decompiler proof of binary capability absence. Requires explicit live-review acceptance for exact package. Unknown/unaudited templates are excluded.'}
 a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'allowed':len(entries),'rejected':len(rejected),'output':str(a.output)}))
if __name__=='__main__':main()
