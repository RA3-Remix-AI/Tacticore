"""Session-local own-unit roster. Public descriptions never include native IDs."""
from collections import Counter
import math
import uuid

ROLES={'0x19ab11af':'infantry','0x2c358c61':'anti_air'}
AIR_SCOUT_HASH='0x40acad6d'

class FormationRegistry:
    def __init__(self,session_id,*,air_scout=False):
        self.session=str(uuid.UUID(session_id));self.records={};self.private={};self.reserved=set()
        self.roles=dict(ROLES)
        if air_scout:self.roles[AIR_SCOUT_HASH]='air'

    @property
    def allowed_hashes(self):return tuple(self.roles)

    def reserve(self,formation_ids):
        if any(ident not in self.private or ident in self.reserved for ident in formation_ids):raise ValueError('Formation unavailable')
        self.reserved.update(formation_ids)

    def release(self,formation_ids):self.reserved.difference_update(formation_ids)

    def refresh(self,own_objects,eligible_ids,region_for_point,*,claimed_ids=()):
        external_held=set(claimed_ids)
        if any(type(ident) is not int or ident<1 for ident in external_held):raise ValueError('Invalid external unit claim')
        live={}
        for obj in own_objects:
            ident=obj.get('object_id');hp=obj.get('hp',0);kind=obj.get('type_hash','').lower()
            if type(ident) is not int or kind not in self.roles:continue
            if not isinstance(hp,(int,float)) or not math.isfinite(hp) or hp<=0:continue
            if ident in live:raise ValueError('Own object identity duplicated')
            live[ident]=dict(obj,role=self.roles[kind])
        held={oid for fid in self.reserved for oid in self.private[fid]['object_ids']}
        if held & external_held:raise ValueError('Native unit control already allocated')
        held.update(external_held)
        infantry=sorted(oid for oid,obj in live.items() if obj['role']=='infantry' and oid in eligible_ids and oid not in held)
        support=sorted(oid for oid,obj in live.items() if obj['role']=='anti_air' and oid in eligible_ids and oid not in held)
        main_id='formation_'+uuid.uuid5(uuid.UUID(self.session),'main_force').hex[:16]
        raid=infantry[-2:] if len(infantry)>=4 or main_id in self.reserved else []
        main=[oid for oid in infantry if oid not in raid][:4]+support[:3]
        assignments={'main_force':main,'raid_force':raid}
        if AIR_SCOUT_HASH in self.roles:
            assignments['scout_air']=sorted(oid for oid,obj in live.items() if obj['role']=='air' and oid in eligible_ids and oid not in held)[:1]
        public=[];private={}
        for name,members in assignments.items():
            fid='formation_'+uuid.uuid5(uuid.UUID(self.session),name).hex[:16]
            old=self.records.get(fid)
            if fid in self.reserved:
                previous=self.private[fid]
                surviving=[oid for oid in previous['object_ids'] if oid in live]
                # Keep the in-flight version for exact feedback correlation.
                # Death is reflected in roles/availability; it never recruits a replacement.
                descriptor=dict(old['public'],roles=dict(Counter(live[oid]['role'] for oid in surviving)),available=False)
                if descriptor['roles']:public.append(descriptor)
                private[fid]=previous
                continue
            if not members:continue
            fingerprint=tuple((oid,live[oid]['type_hash']) for oid in members)
            version=old['version'] if old and old['fingerprint']==fingerprint else (old['version']+1 if old else 1)
            point=live[members[0]]['xyz'];region=region_for_point(point)
            descriptor=dict(formation_id=fid,version=version,roles=dict(Counter(live[oid]['role'] for oid in members)),region_id=region,available=True)
            public.append(descriptor)
            private[fid]=dict(version=version,object_ids=list(members),role='mixed' if len(descriptor['roles'])>1 else next(iter(descriptor['roles'])))
            self.records[fid]=dict(version=version,fingerprint=fingerprint,public=descriptor)
        self.private=private
        return public
