"""Ground-only infantry positive surface evidence; read-only, no SDK calls.

Unlike revision 1, flag160 is diagnostic, not a universal prerequisite. This
proves a sampled own point rests at the native cached surface, not a route edge.
Bear's amphibious locomotor remains outside this ground-only source scope.
"""
import hashlib,importlib.util,math,struct
from pathlib import Path
HERE=Path(__file__).resolve().parent
_spec=importlib.util.spec_from_file_location('ground_v2_native_status_mapping',HERE/'grounded_status.py');native_status=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(native_status)
FOOT={0x19ab11af:'SovietAntiInfantryInfantry',0x2c358c61:'SovietAntiVehicleInfantry'}
MAX_HEIGHT=.5
SOURCE='ground_only_template_plus_valid_native_surface_cache_and_air_exclusions_v2'

def fingerprints():return dict(helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),native_status_helper_sha256=hashlib.sha256((HERE/'grounded_status.py').read_bytes()).hexdigest())

def unknown(reason):return dict(schema_version=2,status='unknown_or_ineligible',ground_positive=False,grounded_verified=False,walkable_route_verified=False,reason_code=reason,mutations=False)

def grounded_status(memory,thing):
 try:
  logic=memory.u32(0xcd8ce4)
  if memory.u32(logic)!=0xbeb630:return unknown('not_live_logic')
  frame=memory.u32(logic+0x50);oid=memory.u32(thing+0xdc);owner=memory.u32(thing+0x418);template=memory.u32(thing+4);kind=memory.u32(template+8)
  if memory.u32(thing)!=0xc4db60 or not oid or memory.u32(owner)!=0xc5bce0 or memory.u32(owner+0x20)!=3:return unknown('not_live_owned_thing')
  if kind not in FOOT:return unknown('outside_proven_ground_only_infantry_scope')
  body=memory.u32(thing+0x33c)
  def sample():
   return dict(words=memory.read(thing+0x80,28),xyz=memory.read(thing+0x38,12),cache_flags=memory.u32(thing+0x48),height=memory.read(thing+0x5c,4),holder=memory.u32(thing+0x238),hp=memory.read(body+4,4))
  first=sample();second=sample();end=memory.u32(logic+0x50)
  if first!=second or frame!=end or memory.u32(0xcd8ce4)!=logic or memory.u32(thing)!=0xc4db60 or memory.u32(thing+0xdc)!=oid or memory.u32(thing+0x418)!=owner or memory.u32(owner+0x20)!=3 or memory.u32(thing+4)!=template or memory.u32(template+8)!=kind or memory.u32(thing+0x33c)!=body:return unknown('identity_frame_or_sample_changed')
  words=list(struct.unpack('<7I',first['words']));xyz=list(struct.unpack('<3f',first['xyz']));height=struct.unpack('<f',first['height'])[0];hp=struct.unpack('<f',first['hp'])[0];flags=native_status.decode(words)
  cache_valid=bool(first['cache_flags']&4);height_valid=cache_valid and math.isfinite(height) and abs(height)<=MAX_HEIGHT;position_valid=all(math.isfinite(x) for x in xyz);eligible=height_valid and position_valid and math.isfinite(hp) and hp>0 and not flags['known_air_state'] and flags['independently_movable'] and first['holder']==0 and not words[0]&1
  return dict(schema_version=2,status='verified_native_surface_sample',object_id=oid,address=hex(thing),owner=hex(owner),type_hash=hex(kind),template=FOOT[kind],frame=frame,end_frame=end,status_words=[hex(w) for w in words],flags=flags['flags'],ground160_diagnostic=flags['ground_positive'],known_air_state=flags['known_air_state'],height_cache_flags=hex(first['cache_flags']),height_cache_valid=cache_valid,cached_height_distance=height if math.isfinite(height) else None,height_tolerance=MAX_HEIGHT,xyz=xyz if position_valid else None,hp=hp if math.isfinite(hp) else None,holder=hex(first['holder']),ground_positive=height_valid,grounded_verified=eligible,walkable_route_verified=False,atomic_sample_verified=True,source=SOURCE,mutations=False,**fingerprints())
 except Exception as error:return unknown(type(error).__name__)

def verify_evidence(record):
 """Pure record check; caller additionally binds session/file/collector provenance."""
 checks={}
 try:
  number=lambda value:int(value,0) if isinstance(value,str) else value
  words=[number(v) for v in record.get('status_words',[])];kind=number(record.get('type_hash'));cache=number(record.get('height_cache_flags'));height=record.get('cached_height_distance');hp=record.get('hp');xyz=record.get('xyz');flags=native_status.decode(words) if len(words)==7 and all(type(v) is int and 0<=v<=0xffffffff for v in words) else None
  finite=lambda v:type(v) in [int,float] and math.isfinite(v)
  checks['exact_method_source']=record.get('schema_version')==2 and record.get('status')=='verified_native_surface_sample' and record.get('source')==SOURCE and all(record.get(k)==v for k,v in fingerprints().items())
  checks['atomic_identity_frame']=record.get('atomic_sample_verified') is True and type(record.get('frame')) is int and record['frame']>0 and record['frame']==record.get('end_frame') and type(record.get('object_id')) is int and record['object_id']>0 and number(record.get('owner'))>0 and number(record.get('address'))>0
  checks['ground_only_template']=kind in FOOT and record.get('template')==FOOT.get(kind)
  checks['positive_native_surface_cache']=type(cache) is int and bool(cache&4) and record.get('height_cache_valid') is True and finite(height) and abs(height)<=MAX_HEIGHT and record.get('height_tolerance')==MAX_HEIGHT
  checks['air_and_mobility_exclusions']=bool(flags) and not flags['known_air_state'] and flags['independently_movable'] and not words[0]&1 and record.get('flags')==flags['flags'] and record.get('known_air_state') is False and record.get('ground160_diagnostic')==flags['ground_positive']
  checks['own_position_alive_unheld']=isinstance(xyz,(list,tuple)) and len(xyz)==3 and all(finite(x) for x in xyz) and finite(hp) and hp>0 and number(record.get('holder'))==0
  checks['claim_scope']=record.get('ground_positive') is True and record.get('grounded_verified') is True and record.get('walkable_route_verified') is False and record.get('mutations') is False
 except (TypeError,ValueError,KeyError):checks['well_formed']=False
 return dict(verified=bool(checks) and all(checks.values()),checks=checks,walkable_route_verified=False,schema_version=2)

def static_proof(path):
 proof=native_status.static_proof(path)
 data=Path(path).read_bytes();pe=struct.unpack_from('<I',data,0x3c)[0];count=struct.unpack_from('<H',data,pe+6)[0];size=struct.unpack_from('<H',data,pe+20)[0];base=struct.unpack_from('<I',data,pe+52)[0];sections=[struct.unpack_from('<8sIIII',data,pe+24+size+40*i) for i in range(count)]
 def read(address,length):
  for name,vs,va,n,raw in sections:
   if base+va<=address and address+length<=base+va+n:return data[raw+address-base-va:raw+address-base-va+length]
  raise ValueError('not_file_backed')
 expected={0x7e2a94:'f6464804',0x7e2ac0:'f30f104640f30f5c442404834e4804f30f11465c',0x7e2ae8:'d9465c',0x7e3de6:'8956388b4804894e3c8b50088b068b4014836648f9'}
 for address,expected_bytes in expected.items():
  if read(address,len(bytes.fromhex(expected_bytes))).hex()!=expected_bytes:raise ValueError('native_surface_cache_proof_changed')
 proof.update(ground_method_version=2,surface_cache_proof=[dict(address=hex(a),bytes=b) for a,b in expected.items()],surface_cache=dict(flags_offset='0x48',valid_bit='0x4',value_offset='0x5c',meaning='native Z minus selected surface height',position_writer_invalidation='0x7e3df7 clears bits2/4'),ground160_required=False,ground_templates=FOOT,amphibious_bear_eligible=False,height_tolerance=MAX_HEIGHT,walkable_route_verified=False)
 return proof
