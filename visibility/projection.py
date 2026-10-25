"""Model-safe visibility projection and last-seen memory.
Raw observations must remain internal; only explicit output fields cross boundary.
"""
import hashlib,math
class VisibilityProjection:
 def __init__(self,session_id,player_id,package_sha256,proof,safety,ttl_seconds=60):
  if not 1<=ttl_seconds<=300:raise ValueError('Bounded memory TTL required')
  self.session=session_id;self.player=player_id;self.sha=package_sha256;self.proof=proof;self.safety=safety;self.ttl=ttl_seconds;self.seen={};self.last_time=None
 def contact_id(self,owner,oid):
  return 'contact_'+hashlib.sha256((self.session+':'+str(owner)+':'+str(oid)).encode()).hexdigest()[:20]
 def verified(self):
  p=self.proof
  return (p.get('schema_version')==2 and p.get('object_visibility_method')=='native_footprint_reconstruction' and p.get('footprint_live_verified') is True and p.get('session_id')==self.session and p.get('target_player_id')==self.player and p.get('package_sha256')==self.sha and p.get('terrain_view_live_verified') is True and p.get('object_view_live_verified') is True and p.get('conservative_stealth_exclusion_reviewed') is True and p.get('no_observer_fallback') is True and self.safety.get('package_sha256')==self.sha)
 def project(self,observations,game_seconds):
  if not math.isfinite(game_seconds) or game_seconds<0:raise ValueError('Invalid game clock')
  if self.last_time is not None and game_seconds<self.last_time:
   self.seen.clear();raise ValueError('Simulation clock rolled back; new session required')
  self.last_time=game_seconds
  if not self.verified():self.seen.clear();return self.empty()
  visible={}
  for ob in observations:
   if ob.get('relation')!='enemy' or ob.get('terrain_shroud')!=1 or not (ob.get('object_shroud_reconstructed')==1 and ob.get('object_visibility_method')=='native_footprint_reconstruction') or not ob.get('runtime_stealth_safe',False):continue
   safe=self.safety.get('templates',{}).get(ob.get('type_hash'))
   if not safe or safe.get('source_audited_no_intrinsic_stealth') is not True:continue
   if not ob.get('identity_stable') or ob.get('observer_fallback') or not ob.get('alive'):continue
   oid=ob.get('object_id');owner=ob.get('owner_player_id');region=ob.get('region_id')
   if type(oid)!=int or oid<=0 or type(owner)!=int or owner==self.player or not isinstance(region,str) or not region:continue
   cid=self.contact_id(owner,oid)
   # No raw position, HP, template hash, pointer or native object ID leaves here.
   contact={'contact_id':cid,'owner_player_id':owner,'relation':'enemy','role':safe['role'],'region_id':region,'observed_at_game_seconds':game_seconds,'currently_visible':True,'stealth_state':'visible'}
   visible[cid]=contact;self.seen[cid]=dict(contact)
  contacts=[]
  for cid,old in list(self.seen.items()):
   if game_seconds-old['observed_at_game_seconds']>self.ttl:del self.seen[cid];continue
   contacts.append(visible.get(cid,{**old,'currently_visible':False}))
  contacts=sorted(contacts,key=lambda c:(not c['currently_visible'],-c['observed_at_game_seconds'],c['contact_id']))[:64]
  retained={c['contact_id'] for c in contacts};self.seen={k:v for k,v in self.seen.items() if k in retained}
  # Regions are based solely on presently visible contacts. Never infer hidden
  # enemy counts or promote a stale contact to a current regional count.
  regions={}
  for ob in visible.values():
   rid=ob['region_id'];r=regions.setdefault(rid,{'region_id':rid,'relation':'enemy','observed_at_game_seconds':game_seconds,'currently_visible':True,'role_counts':{}})
   r['role_counts'][ob['role']]=r['role_counts'].get(ob['role'],0)+1
  for old in contacts:
   if not old['currently_visible'] and old['region_id'] not in regions:
    regions[old['region_id']]={'region_id':old['region_id'],'relation':'enemy','observed_at_game_seconds':old['observed_at_game_seconds'],'currently_visible':False,'role_counts':{}}
  return {'schema_version':1,'viewer_player_id':self.player,'visibility_verified':True,'regions':list(regions.values()),'contacts':contacts,'formations':[]}
 def empty(self):return {'schema_version':1,'viewer_player_id':self.player,'visibility_verified':False,'regions':[],'contacts':[],'formations':[]}
