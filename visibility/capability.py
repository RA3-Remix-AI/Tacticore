"""Build-evidence verification and per-match native visibility handshake.
Session flags are outputs of verified evidence/signatures/live reads, never UI
inputs. No game calls, memory writes, hooks or visibility changes.
"""
import argparse,hashlib,json,sys,time,xml.etree.ElementTree as E
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT.parent),str(ROOT.parent/'native-ai'),str(ROOT.parent/'production'),str(ROOT.parent/'reference/Ra3-Copilot/ra3-copilot/tools')]
from probe import EXPECTED
from precheck_aob import parse_pe,rva_to_off
from read_selected_personality import inspect_player,resolve_registry
from native_read import ShroudReader,walk_live_things,object_footprint_status
from audit_templates import audit_node,NS
CODE_FILES=('native_read.py','collector.py','projection.py','audit_templates.py','capability.py')
DEFAULT_SAFETY=ROOT/'template-safety-2d7873e1.json'
DEFAULT_CAPABILITY=ROOT/'build-capability-2d7873e1.json'
SIGNATURE_ADDRESSES=(0x992130,0x9912f0,0x98fef0,0x9903b0,0x990493,0x993264,0x844680,0x504e10,0x6fda40)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def verified_sources(safety):
 seen={};hazards=0
 for entry in safety['templates'].values():
  if entry.get('source_audited_no_intrinsic_stealth') is not True or not entry.get('source_chain'):raise ValueError('Template source not audited')
  for source in entry['source_chain']:
   p=source['path']
   if p in seen:
    if seen[p]!=source['sha256']:raise ValueError('Conflicting source hash')
    continue
   if sha(p)!=source['sha256']:raise ValueError('Template source changed: '+p)
   seen[p]=source['sha256']
  for source in entry['source_chain']:
   nodes=[n for n in E.parse(source['path']).getroot() if n.tag==NS+'GameObject']
   if not nodes or any(audit_node(n) for n in nodes):raise ValueError('Intrinsic hidden capability in allowlist source')
 for reason in safety['rejected'].values():hazards+=('capability_' in reason)
 if not hazards:raise ValueError('Audit lacks any intrinsic-invisibility negative controls')
 return seen

def build_capability(session,census_path,transition_path,safety_path,output):
 census,transitions,safety=load(census_path),load(transition_path),load(safety_path)
 if census['session_id']!=session['session_id'] or transitions['session_id']!=session['session_id'] or transitions.get('viewer_player_id')!=3 or not census.get('grid_stable') or census['read_errors'] or transitions['error']:raise ValueError('Live evidence session/consistency mismatch')
 counts=census['counts']
 def count(*parts):return sum(v for k,v in counts.items() if all(part in k for part in parts))
 checks={'own_view_differs_from_observer':count('viewer2:','cache0:foot1')>0 and count('viewer4:owner3:terrain0:')>0,'native_cached_clear_agrees_with_full_footprint':count('viewer3:owner4:terrain1:cache1:foot1')>0,'lazy_cache_zero_requires_reconstruction':count('viewer3:owner4:terrain1:cache0:foot1')>0,'center_clear_does_not_imply_footprint_clear':count('viewer3:owner4:terrain1:cache0:foot2')>0,'observed_first_sighting':any(e['kind']=='first_full_sighting' for e in transitions['events']),'observed_loss':any(e['kind']=='lost_visibility' and e.get('terrain_shroud')==0 for e in transitions['events'])}
 if not all(checks.values()):raise ValueError('Missing required build capability evidence: '+str(checks))
 if safety['package_sha256']!=session['mod_sha256'] or sha(session['mod_big'])!=session['mod_sha256']:raise ValueError('Exact package mismatch')
 game=Path(session['game']);raw=game.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=EXPECTED:raise ValueError('Unsupported game version')
 base,_,sections=parse_pe(raw);signatures={hex(va):raw[rva_to_off(va-base,sections):rva_to_off(va-base,sections)+24].hex() for va in SIGNATURE_ADDRESSES}
 sources=verified_sources(safety)
 report={'schema_version':2,'object_visibility_method':'native_footprint_reconstruction','kind':'visibility_build_capability','executable_sha256':EXPECTED,'package_sha256':session['mod_sha256'],'safety_sha256':sha(safety_path),'compiled_manifest_sha256':safety['compiled_manifest_sha256'],'implementation_sha256':{n:sha(ROOT/n) for n in CODE_FILES},'source_sha256':sources,'expected_signatures':signatures,'checks':checks,'evidence':{str(Path(p).resolve()):sha(p) for p in (census_path,transition_path)},'evidence_session_id':session['session_id'],'scope':'Full native footprint clear branch; intrinsic/active stealth excluded, no detected mode. Source audit is conservative; unknown templates excluded.','source_audit_only':True,'mutations':False}
 report['build_id']=hashlib.sha256(json.dumps(report,sort_keys=True).encode()).hexdigest();Path(output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');return report

def verify_build(session,capability_path=DEFAULT_CAPABILITY,safety_path=DEFAULT_SAFETY):
 cap,safety=load(capability_path),load(safety_path)
 expected_id=cap.get('build_id');unsigned={k:v for k,v in cap.items() if k!='build_id'}
 if hashlib.sha256(json.dumps(unsigned,sort_keys=True).encode()).hexdigest()!=expected_id:raise ValueError('Build capability checksum mismatch')
 if cap.get('schema_version')!=2 or cap.get('object_visibility_method')!='native_footprint_reconstruction' or cap.get('kind')!='visibility_build_capability' or not all(v is True for v in cap.get('checks',{}).values()) or len(cap.get('checks',{}))!=6:raise ValueError('Incomplete build capability')
 if cap['executable_sha256']!=EXPECTED or cap['package_sha256']!=session['mod_sha256'] or safety['package_sha256']!=session['mod_sha256'] or sha(session['mod_big'])!=session['mod_sha256'] or sha(safety_path)!=cap['safety_sha256']:raise ValueError('Visibility build/package identity mismatch')
 for name,digest in cap['implementation_sha256'].items():
  if name not in CODE_FILES or sha(ROOT/name)!=digest:raise ValueError('Visibility implementation changed: '+name)
 if set(cap['implementation_sha256'])!=set(CODE_FILES):raise ValueError('Incomplete implementation identity')
 for path,digest in cap['evidence'].items():
  if sha(path)!=digest:raise ValueError('Prior live evidence changed')
 if verified_sources(safety)!=cap['source_sha256']:raise ValueError('Capability source identity mismatch')
 return cap,safety

def bind_session(memory,session,player_id,capability_path=DEFAULT_CAPABILITY,safety_path=DEFAULT_SAFETY):
 if not 0<=player_id<16:raise ValueError('Computer player index range')
 cap,safety=verify_build(session,capability_path,safety_path)
 if memory.pid!=session['pid']:raise ValueError('Visibility PID mismatch')
 for va,expected in cap['expected_signatures'].items():
  if memory.read(int(va,0),len(bytes.fromhex(expected))).hex()!=expected:raise ValueError('Visibility native signature changed: '+va)
 logic=memory.u32(0xcd8ce4);frame=memory.u32(logic+0x50)
 if not frame or memory.u32(logic)!=0xbeb630:raise ValueError('Live match not ready')
 plist=memory.u32(0xce8c9c);player=memory.u32(plist+0x30+4*player_id)
 native=inspect_player(memory.read,player);registry=load(session['registry']);binding=resolve_registry(native,registry,session)
 if native['player_index']!=player_id or not binding['personality_binding_verified']:raise ValueError('Selected computer commander binding failed')
 ai=int(native['ai_player'],0);grid=ShroudReader(memory);own_full=0
 for thing in walk_live_things(memory,logic):
  if memory.u32(thing+0x418)!=player:continue
  if object_footprint_status(memory,thing,player_id,grid)==1:own_full+=1
 if not own_full or not grid.stable() or memory.u32(0xcd8ce4)!=logic or memory.u32(logic+0x50)<frame or memory.u32(player+0x90)!=ai:raise ValueError('Per-session own footprint/view handshake not ready')
 proof={'schema_version':2,'object_visibility_method':'native_footprint_reconstruction','footprint_live_verified':True,'session_id':session['session_id'],'target_player_id':player_id,'package_sha256':session['mod_sha256'],'build_id':cap['build_id'],'terrain_view_live_verified':True,'object_view_live_verified':True,'conservative_stealth_exclusion_reviewed':True,'no_observer_fallback':True,'detection_verified':False,'commander_id':binding['commander_id'],'handshake':{'game_logic':logic,'player':player,'ai_player':ai,'shroud_manager':grid.manager,'shroud_impl':grid.impl,'frame_min':frame,'own_fully_clear_footprints':own_full},'evidence':'Prior exact-build cross-view/footprint transition evidence plus this session native signatures, computer UUID chain and own-footprint query. No UI flag inputs.','mutations':False}
 return proof,safety

def main():
 ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='mode',required=True)
 b=sub.add_parser('build');b.add_argument('--session',type=Path,required=True);b.add_argument('--census',type=Path,required=True);b.add_argument('--transitions',type=Path,required=True);b.add_argument('--safety',type=Path,default=DEFAULT_SAFETY);b.add_argument('--output',type=Path,default=DEFAULT_CAPABILITY)
 c=sub.add_parser('bind');c.add_argument('--session',type=Path,required=True);c.add_argument('--player',type=int,required=True);c.add_argument('--output',type=Path,required=True)
 a=ap.parse_args();session=load(a.session)
 if a.mode=='build':r=build_capability(session,a.census,a.transitions,a.safety,a.output);print(json.dumps({'output':str(a.output),'build_id':r['build_id'],'checks':r['checks']}))
 else:
  from observe_production import Memory
  m=Memory(session['pid'],session)
  try:proof,_=bind_session(m,session,a.player);a.output.write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'output':str(a.output),'session_id':proof['session_id'],'viewer':a.player,'handshake':proof['handshake']}))
  finally:m.close()
if __name__=='__main__':main()
