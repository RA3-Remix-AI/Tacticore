"""Version-pinned own-player sampler for a single, persistent battle host."""
from __future__ import annotations
import hashlib,importlib.util,json,math,sys,time
from collections import Counter
from pathlib import Path,PureWindowsPath
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'production'))
sys.path.insert(0,str(ROOT.parent/'native-ai'))
from observe_production import Memory,EXPECTED
from session_package import verify_session_package
from read_selected_personality import inspect_player,resolve_registry
from read_match_state import snapshot as match_snapshot
from sample_state import sample
from own_candidates import own_candidates,load_catalog
from match_participants import verify_two_ai
from formations import FormationRegistry

_mobility_spec=importlib.util.spec_from_file_location('live_mobility_guard',ROOT.parent/'tactical/mobility_guard.py')
_mobility_module=importlib.util.module_from_spec(_mobility_spec);_mobility_spec.loader.exec_module(_mobility_module)
mobility_status=_mobility_module.mobility_status

_admission_spec=importlib.util.spec_from_file_location('live_mission_admission',ROOT.parent/'tactical/mission_actor_admission.py')
_admission_module=importlib.util.module_from_spec(_admission_spec);_admission_spec.loader.exec_module(_admission_module)

def mission_actor_eligible(memory,candidate,owner,admission_module=None):
 module=admission_module or _admission_module
 evidence=module.actor_admission(memory,int(candidate['address'],0))
 return bool(module.verify_evidence(evidence)['verified'] and evidence.get('object_id')==candidate['object_id'] and evidence.get('type_hash')==candidate['type_hash'] and evidence.get('address')==candidate['address'] and int(evidence.get('owner','0'),0)==owner and int(evidence.get('state_snapshot',{}).get('update','0'),0)==int(candidate['ai_address'],0))

def atomic_json(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
 for attempt in range(25):
  try:temp.replace(path);return
  except PermissionError:
   if attempt==24:raise
   time.sleep(.02)

class RetryableSample(ValueError):
 """A discarded non-atomic sample. It never permits dispatch from old lookups."""

def verify_scenario_map(native_path,scenario):
 expected=scenario.get('map_id')
 if expected is None:return
 if not isinstance(expected,str) or not expected or PureWindowsPath(expected).name!=expected:raise ValueError('Invalid scenario map identity')
 actual=PureWindowsPath(native_path)
 if actual.suffix.lower()!='.map' or actual.stem.lower()!=expected.lower() or actual.parent.name.lower()!=expected.lower():raise ValueError('Native map differs from recorded scenario')

class LiveBattleState:
 def __init__(self,session_path,commander_id,player_id=3,*,foci=('native_baseline',),output=None,visibility=False,air_scout=False,mission_history=False,mission_admission_filename='mission_actor_admission.py'):
  if mission_admission_filename not in ('mission_actor_admission.py','mission_actor_admission_v2.py'):raise ValueError('Unknown trusted mission admission reader')
  self.mission_admission_module=None
  if mission_admission_filename!='mission_actor_admission.py':
   spec=importlib.util.spec_from_file_location('live_trusted_mission_admission_v2',ROOT.parent/'tactical'/mission_admission_filename)
   self.mission_admission_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.mission_admission_module)
  self.session_path=Path(session_path);self.session_raw=self.session_path.read_bytes()
  self.session=json.loads(self.session_raw.decode('utf-8-sig'));self.commander_id=commander_id;self.player_id=player_id
  package=verify_session_package(self.session)
  self.package_digest=hashlib.sha256(package.read_bytes()).hexdigest()
  registry_path=Path(self.session['registry']);self.registry_raw=registry_path.read_bytes();self.registry=json.loads(self.registry_raw)
  if self.registry.get('package_sha256')!=self.package_digest:raise ValueError('Registry package mismatch')
  self.foci=tuple(foci);self.output=Path(output or self.session['run_directory'])
  self.owner=None;self.ai=None;self.logic=None;self.map=None;self.last_frame=None;self.sequence=0;self.latest_snapshot_path=None;self.native=None
  self.catalog=load_catalog()
  self.participant_identity=None
  self.visibility_enabled=visibility;self.visibility_reader=None;self.known_regions={'home_base'}
  self.required_regions=set();self.mission_context=None
  self.formations=FormationRegistry(self.session['session_id'],air_scout=air_scout);self.private_formations={};self.private_regions={};self.private_targets={};self.visibility_proof_path=None
  self.mission_history=mission_history;self.route_history_reader=None;self.route_history_samples=0;self.route_history_skips=0

 @staticmethod
 def region_of(point):
  def slug(value):return 'm'+str(-value) if value<0 else str(value)
  return 'region_'+slug(math.floor(point[0]/512))+'_'+slug(math.floor(point[1]/512))

 def collect_battlefield(self,own,raw):
  if not self.visibility_enabled:return None,own['logic_frame_candidate']/15
  sys.path.insert(0,str(ROOT.parent/'visibility'))
  memory=Memory(self.session['pid'],self.session)
  try:
   self.bind_visibility(memory)
   self.visibility_reader.m=memory
   logic=int(own['game_logic'],0);frame=memory.u32(logic+0x50)
   if frame<own['logic_frame_candidate']:raise ValueError('Game clock moved backwards between own and visibility samples')
   if frame-own['logic_frame_candidate']>3 or memory.u32(logic+0x15c)!=own['pause_type_candidate']:raise RetryableSample('own_visibility_sample_skew')
   now=frame/15
   battlefield=self.visibility_reader.collect(now)
   if memory.u32(logic+0x50)<frame:raise ValueError('Game clock moved backwards during visibility sample')
   if memory.u32(logic+0x50)-own['logic_frame_candidate']>3 or memory.u32(logic+0x15c)!=own['pause_type_candidate']:raise RetryableSample('own_visibility_sample_skew')
   eligible=set();owner=int(own['resources']['address'],0) if 'address' in own['resources'] else self.owner
   if owner is None:
    owners={int(candidate['owner_address'],0) for candidate in raw['candidates']}
    if len(owners)!=1:raise ValueError('Own-player identity unavailable')
    owner=next(iter(owners))
   script_team=memory.u32(memory.u32(owner+0x8c)+0x10)
   for candidate in raw['candidates']:
    if candidate['type_hash'] not in self.formations.allowed_hashes:continue
    thing=int(candidate['address'],0);update=int(candidate['ai_address'],0);team=memory.u32(thing+0x414)
    # These troops remain in own totals, not independently mobile cohorts.
    if not mobility_status(memory,thing)['independently_movable'] or memory.u32(thing+0x238):continue
    if getattr(self,'mission_history',False) and candidate['type_hash'] in ('0x19ab11af','0x2c358c61'):
     admission_module=getattr(self,'mission_admission_module',None)
     admitted=mission_actor_eligible(memory,candidate,owner,admission_module) if admission_module is not None else mission_actor_eligible(memory,candidate,owner)
     if not admitted:continue
    if team!=script_team and memory.u32(memory.u32(team+4)+8)==owner and memory.u32(update+8)==thing:eligible.add(candidate['object_id'])
   admission_frame=memory.u32(logic+0x50)
   if admission_frame<frame:raise ValueError('Game clock moved backwards during admission sample')
   if admission_frame-own['logic_frame_candidate']>3 or memory.u32(logic+0x15c)!=own['pause_type_candidate']:raise RetryableSample('own_admission_visibility_sample_skew')
   battlefield['formations']=self.formations.refresh(own['own_objects'],eligible,self.region_of)
   self.private_formations=dict(self.formations.private)
   self.private_targets=dict(self.visibility_reader.private_targets)
   points=dict(self.visibility_reader.region_points)
   private_points={rid:dict(xyz=list(point),observed_frame=int(now*15)) for rid,point in points.items()}
   for rid,point in self.visibility_reader.frontier_points.items():private_points[rid]=dict(xyz=list(point),observed_frame=int(now*15))
   home=next((obj for obj in own['own_objects'] if obj.get('template_annotation')=='SovietConstructionYard'),None)
   if home is not None:private_points['home_base']=dict(xyz=list(home['xyz']),observed_frame=int(now*15))
   self.private_regions=private_points
   from continuous_contract import retreat_context
   self.mission_context=retreat_context(private_points,frame,home_object_id=home.get('object_id') if home else None,own_positions=[obj['xyz'] for obj in own['own_objects'] if obj.get('object_id') in eligible])
   if getattr(self,'mission_history',False):
    history_dir=Path(self.session['run_directory'])/'formation-own-history'
    self.mission_context=dict(self.mission_context or {'schema_version':1},formation_history_dir=str(history_dir.resolve()))
   descriptors={r['region_id']:r for r in battlefield['regions']}
   if home is not None:descriptors['home_base']=dict(region_id='home_base',relation='self',observed_at_game_seconds=now,currently_visible=battlefield['visibility_verified'],role_counts={})
   for region in self.visibility_reader.frontier_regions:descriptors.setdefault(region['region_id'],region)
   for formation in battlefield['formations']:
    rid=formation['region_id'];descriptors.setdefault(rid,dict(region_id=rid,relation='self',observed_at_game_seconds=now,currently_visible=battlefield['visibility_verified'],role_counts={}))
   battlefield['regions']=list(descriptors.values())
   self.known_regions.update(descriptors)
   self.known_regions.update(contact['region_id'] for contact in battlefield['contacts'])
   self.known_regions.update(formation['region_id'] for formation in battlefield['formations'])
   required={'home_base'}|set(descriptors)|{c['region_id'] for c in battlefield['contacts']}|{f['region_id'] for f in battlefield['formations']}|self.required_regions
   if len(required)>256:raise ValueError('Required region capacity exceeded')
   historical=sorted(self.known_regions-required)
   self.known_regions=required|set(historical[-(256-len(required)):]) if len(required)<256 else required
   atomic_json(self.output/'visibility-status.json',dict(viewer_player_id=self.player_id,visibility_verified=battlefield['visibility_verified'],currently_visible=sum(c['currently_visible'] for c in battlefield['contacts']),last_seen=sum(not c['currently_visible'] for c in battlefield['contacts']),vision_metrics=self.visibility_reader.vision_metrics))
   return battlefield,now
  finally:memory.close()

 def bind_visibility(self,memory):
  if not self.visibility_enabled or self.visibility_reader is not None:return
  from capability import bind_session
  from projection import VisibilityProjection
  from collector import VisibilityCollector
  proof,safety=bind_session(memory,self.session,self.player_id)
  if proof['commander_id']!=self.commander_id:raise ValueError('Visibility commander mismatch')
  projection=VisibilityProjection(self.session['session_id'],self.player_id,self.session['mod_sha256'],proof,safety)
  self.visibility_reader=VisibilityCollector(memory,self.session,self.player_id,projection)
  self.visibility_proof_path=self.output/'visibility-proof.json';atomic_json(self.visibility_proof_path,proof)

 def collect(self):
  self.private_targets={}
  try:return self._collect()
  except RetryableSample:raise
  except (ValueError,RuntimeError) as error:
   transient=('Non-atomic visibility snapshot changed','Snapshot clock differs from native frame/15','Footprint changed during sample','Live object list changed/corrupt','Read failed ','ReadProcessMemory failed','Read unavailable','mobility_thing_identity','mobility_identity_or_status_changed')
   if str(error).startswith(transient):raise RetryableSample('non_atomic_sample_discarded') from error
   raise

 def _collect(self):
  if self.session_path.read_bytes()!=self.session_raw:raise ValueError('Active session changed')
  if Path(self.session['registry']).read_bytes()!=self.registry_raw:raise ValueError('Registry changed')
  memory=Memory(self.session['pid'],self.session)
  try:raw=dict(pid=self.session['pid'],sha256=EXPECTED,**own_candidates(memory,self.player_id,self.catalog))
  finally:memory.close()
  path=self.output/'own-candidates.json'
  atomic_json(path,raw)
  self.latest_snapshot_path=path
  owners={int(x['owner_address'],0) for x in raw['candidates']}
  if len(owners)!=1:raise ValueError('No unique owned player in match')
  owner=next(iter(owners));memory=Memory(self.session['pid'],self.session)
  try:
   identity=inspect_player(memory.read,owner);binding=resolve_registry(identity,self.registry,self.session)
   if not binding['personality_binding_verified'] or binding['commander_id']!=self.commander_id or identity['player_index']!=self.player_id:raise ValueError('Effective commander differs from requested binding')
   native_state=match_snapshot(memory.read)
   opponent=self.session.get('scenario',{}).get('opponent_player_index')
   if opponent is not None:
    participants=verify_two_ai(memory,native_state,self.registry,self.player_id,opponent,self.session.get('scenario',{}).get('observer_player_index',2))
    if self.participant_identity is not None and participants!=self.participant_identity:raise ValueError('Combatant identity changed')
    self.participant_identity=participants
    atomic_json(self.output/'participants.json',participants)
   if self.visibility_enabled:
    sys.path.insert(0,str(ROOT.parent/'visibility'))
    self.bind_visibility(memory)
  finally:memory.close()
  own=sample(self.session,raw,self.player_id)
  verify_scenario_map(own['map_path'],self.session.get('scenario',{}))
  if self.owner is not None and (owner!=self.owner or identity['ai_player']!=self.ai or own['game_logic']!=self.logic or own['map_path']!=self.map):raise ValueError('Match lifecycle changed')
  if self.last_frame is not None and own['logic_frame_candidate']<self.last_frame:raise ValueError('Game clock moved backwards')
  self.owner=owner;self.ai=identity['ai_player'];self.logic=own['game_logic'];self.map=own['map_path'];self.last_frame=own['logic_frame_candidate'];self.native=native_state
  battlefield,game_seconds=self.collect_battlefield(own,raw)
  self.sequence+=1
  roles=Counter()
  for obj in own['own_objects']:
   if obj['type_hash']=='0x2c358c61':roles['anti_air']+=1
   elif obj['type_hash'] in ('0x19ab11af','0x33026fa1'):roles['infantry']+=1
  # Unknown or unverified categories are omitted; known counts are lower bounds.
  queues=[x['queue_candidate']['nodes'] for x in own['factories'] if x.get('template')=='SovietBarracks' and isinstance(x.get('queue_candidate',{}).get('nodes'),list) and not x.get('queue_candidate_error')]
  paused=own['pause_type_candidate']!=0
  snapshot=dict(schema_version=1,session_id=self.session['session_id'],player_id=self.player_id,snapshot_id=self.sequence,game_time_seconds=game_seconds,source='game_bridge',paused=paused,
   resources=dict(credits=own['resources']['display_sum'],power_balance=None),
   capabilities=dict(production_focus=list(self.foci),regions=sorted(self.known_regions)),
   production=dict(queued_count=sum(len(x) for x in queues),idle_producers=sum(not x for x in queues),own_roles=dict(roles)),enemy_observations=[],events=[])
  if battlefield is not None:snapshot['battlefield']=battlefield
  atomic_json(self.output/'own-state.json',own);atomic_json(self.output/'identity.json',dict(session_id=self.session['session_id'],pid=self.session['pid'],sampled_wall_time=time.time(),mod_sha256=self.session['mod_sha256'],native=identity,binding=binding));atomic_json(self.output/'match-state.json',native_state);atomic_json(self.output/'snapshot.json',snapshot)
  return snapshot
