"""Visibility-filtered observations and high-level tactical intent contracts.

Native addresses, coordinates, template IDs and object IDs deliberately have no
place in this protocol. The trusted collector maintains their private mapping.
"""
from dataclasses import asdict,dataclass
import math

ROLES=frozenset({"anti_air","anti_armor","infantry","naval","air","armor","economy","structure"})
PURPOSES={"raid":frozenset({"harass_economy","recon"}),"attack":frozenset({"main_attack"}),"combined_arms":frozenset({"coordinate_force","defend_base"})}
RELATIONS=frozenset({"self","ally","enemy","neutral","unknown"})
STEALTH=frozenset({"visible","detected","unknown"})


def fail(code):
    from engine import ContractError
    raise ContractError(code)


def keys(value,fields,code):
    if type(value) is not dict or set(value)!=set(fields):fail(code)
    return value


def ident(value,code):
    import re
    from engine import _identifier
    result=_identifier(value,code)
    if re.fullmatch(r"(?:0x[0-9a-fA-F]+|[0-9]+)",result):fail(code)
    return result


def number(value,low,high,code):
    if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:fail(code)
    return value


def integer(value,low,high,code):
    if type(value) is not int or not low<=value<=high:fail(code)
    return value


def enum(value,allowed,code):
    if not isinstance(value,str) or value not in allowed:fail(code)
    return value


def boolean(value,code):
    if type(value) is not bool:fail(code)
    return value


def role_counts(value):
    if type(value) is not dict or set(value)-ROLES:fail("battlefield_roles")
    return tuple(sorted((role,integer(count,0,100000,"battlefield_role_count")) for role,count in value.items()))


@dataclass(frozen=True)
class Region:
    region_id:str
    relation:str
    observed_at_game_seconds:float
    currently_visible:bool
    role_counts:tuple

    def public(self):return {**asdict(self),"role_counts":dict(self.role_counts)}


@dataclass(frozen=True)
class Contact:
    contact_id:str
    owner_player_id:int
    relation:str
    role:str
    region_id:str
    observed_at_game_seconds:float
    currently_visible:bool
    stealth_state:str

    def public(self):return asdict(self)


@dataclass(frozen=True)
class Formation:
    formation_id:str
    version:int
    roles:tuple
    region_id:str
    available:bool

    def public(self):return {**asdict(self),"roles":dict(self.roles)}


@dataclass(frozen=True)
class Battlefield:
    visibility_verified:bool
    regions:tuple
    contacts:tuple
    formations:tuple
    viewer_player_id:int

    @classmethod
    def from_dict(cls,raw,game_time,region_ids,player_id):
        value=keys(raw,{"schema_version","viewer_player_id","visibility_verified","regions","contacts","formations"},"battlefield_fields")
        if type(value["schema_version"]) is not int or value["schema_version"]!=1:fail("battlefield_schema")
        verified=boolean(value["visibility_verified"],"battlefield_visibility")
        viewer=integer(value["viewer_player_id"],0,15,"battlefield_viewer")
        if viewer!=player_id:fail("battlefield_viewer_mismatch")
        output=[]
        for field,limit in [("regions",256),("contacts",64),("formations",32)]:
            rows=value[field]
            if not isinstance(rows,list) or len(rows)>limit:fail("battlefield_"+field)
            parsed=[];seen=set()
            for row in rows:
                if field=="regions":
                    row=keys(row,{"region_id","relation","observed_at_game_seconds","currently_visible","role_counts"},"region_fields")
                    region=enum(row["region_id"],region_ids,"battlefield_region")
                    relation=enum(row["relation"],RELATIONS,"battlefield_relation")
                    visible=boolean(row["currently_visible"],"battlefield_visible")
                    at=number(row["observed_at_game_seconds"],0,game_time,"battlefield_time")
                    roles=role_counts(row["role_counts"])
                    if not verified and (visible or relation=="enemy" or roles):fail("unverified_enemy_information")
                    item=Region(region,relation,at,visible,roles);key=region
                elif field=="contacts":
                    row=keys(row,{"contact_id","owner_player_id","relation","role","region_id","observed_at_game_seconds","currently_visible","stealth_state"},"contact_fields")
                    if not verified:fail("unverified_enemy_information")
                    key=ident(row["contact_id"],"contact_id")
                    owner=integer(row["owner_player_id"],0,15,"contact_owner")
                    relation=enum(row["relation"],RELATIONS,"battlefield_relation")
                    if (relation=="self")!=(owner==player_id):fail("contact_relation_owner")
                    role=enum(row["role"],ROLES,"contact_role");region=enum(row["region_id"],region_ids,"battlefield_region")
                    at=number(row["observed_at_game_seconds"],0,game_time,"battlefield_time")
                    visible=boolean(row["currently_visible"],"battlefield_visible")
                    stealth=enum(row["stealth_state"],STEALTH,"contact_stealth")
                    if visible and (stealth=="unknown" or game_time-at>3):fail("contact_not_currently_verified")
                    item=Contact(key,owner,relation,role,region,at,visible,stealth)
                else:
                    row=keys(row,{"formation_id","version","roles","region_id","available"},"formation_fields")
                    key=ident(row["formation_id"],"formation_id");version=integer(row["version"],1,2**31-1,"formation_version")
                    roles=role_counts(row["roles"])
                    if not roles or not any(count for _,count in roles):fail("formation_empty")
                    region=enum(row["region_id"],region_ids,"battlefield_region")
                    item=Formation(key,version,roles,region,boolean(row["available"],"formation_available"))
                if key in seen:fail("battlefield_duplicate_id")
                seen.add(key);parsed.append(item)
            output.append(tuple(parsed))
        return cls(verified,*output,viewer)

    def public(self):return {"schema_version":1,"viewer_player_id":self.viewer_player_id,"visibility_verified":self.visibility_verified,"regions":[r.public() for r in self.regions],"contacts":[c.public() for c in self.contacts],"formations":[f.public() for f in self.formations]}


@dataclass(frozen=True)
class TacticalIntent:
    module:str
    purpose:str
    target_region:str
    target_contact_id:str|None
    formation_ids:tuple
    required_roles:tuple
    force_fraction:float
    formation_versions:tuple=()

    def public(self):
        result={**asdict(self),"formation_ids":list(self.formation_ids),"required_roles":list(self.required_roles)}
        result.pop("formation_versions")
        return result


def validate_intents(raw,request,latest):
    if not isinstance(raw,list) or len(raw)>3:fail("tactical_tasks")
    if raw and (request.battlefield is None or latest.battlefield is None):fail("tactical_context_unavailable")
    result=[];modules=set();claimed=set()
    requested_forms={f.formation_id:f for f in request.battlefield.formations} if raw else {}
    current_forms={f.formation_id:f for f in latest.battlefield.formations} if raw else {}
    requested_contacts={c.contact_id:c for c in request.battlefield.contacts} if raw else {}
    current_contacts={c.contact_id:c for c in latest.battlefield.contacts} if raw else {}
    for task in raw:
        task=keys(task,{"module","purpose","target_region","target_contact_id","formation_ids","required_roles","force_fraction"},"tactical_task_fields")
        module=enum(task["module"],PURPOSES,"tactical_module");purpose=enum(task["purpose"],PURPOSES[module],"tactical_purpose")
        if module in modules:fail("tactical_duplicate_module")
        modules.add(module)
        region=enum(task["target_region"],set(request.regions)&set(latest.regions),"tactical_region")
        if purpose=="defend_base":
            descriptor=next((r for r in latest.battlefield.regions if r.region_id==region),None)
            if descriptor is None or descriptor.relation not in {"self","ally"}:fail("tactical_defend_relation")
        ids=task["formation_ids"]
        if not isinstance(ids,list) or not 1<=len(ids)<=4 or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):fail("tactical_formations")
        roles=task["required_roles"]
        if not isinstance(roles,list) or not 1<=len(roles)<=len(ROLES) or any(not isinstance(i,str) or i not in ROLES for i in roles) or len(set(roles))!=len(roles):fail("tactical_roles")
        actual_roles=set()
        for formation_id in ids:
            old,current=requested_forms.get(formation_id),current_forms.get(formation_id)
            if old is None or current is None or old.version!=current.version or not old.available or not current.available:fail("tactical_formation_stale")
            if formation_id in claimed:fail("tactical_formation_conflict")
            claimed.add(formation_id);actual_roles.update(role for role,count in current.roles if count)
        if set(roles)-actual_roles:fail("tactical_roles_unavailable")
        if module=="combined_arms" and len(set(roles))<2:fail("combined_arms_requires_roles")
        target=task["target_contact_id"]
        if purpose=="recon" and target is not None:fail("recon_uses_region_only")
        if target is not None:
            ident(target,"tactical_contact")
            old,current=requested_contacts.get(target),current_contacts.get(target)
            if old is None or current is None or current.relation!="enemy" or old.relation!="enemy" or current.region_id!=region:fail("tactical_contact")
            if not old.currently_visible or not current.currently_visible or current.stealth_state not in {"visible","detected"} or latest.game_time_seconds-current.observed_at_game_seconds>3:fail("tactical_contact_stale")
        if purpose in {"harass_economy","main_attack"} and target is None:fail("tactical_contact_required")
        if purpose=="harass_economy" and current_contacts[target].role!="economy":fail("raid_economy_target")
        force=number(task["force_fraction"],.01,1,"tactical_force_budget")
        result.append(TacticalIntent(module,purpose,region,target,tuple(ids),tuple(roles),force,tuple((key,requested_forms[key].version) for key in ids)))
    return tuple(result)
