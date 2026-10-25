"""Host-side envelope checks for continuous native missions.

Progress is telemetry from the bound native executor, not completion evidence.
Only independently requalified terminal raw reports can establish an effect.
"""
import math
import uuid

PROTOCOL='continuous_tactical_v1'
MAX_DURATION_FRAMES=4500
STAGES=frozenset({'reserved','approach','prepare','engage','disengage','retreat','restore','restored','completed','failed'})
FIELDS=frozenset({'mission_id','stage','revision','observed_frame','deadline_frame','approach_distance','own_hp','damage','reason'})
REASONS=frozenset({'active','source_damage','fov_lost','approach_stalled','approach_limit','low_hp','engage_limit','retreat_failed','deadline','cancelled','native_override','prepare_failed','heartbeat_lost','target_invalid','initial_binding'})


def mission_limits(grant):
    """A primitive grant cannot silently authorize a continuous mission."""
    schema=grant.get('stop_schema',{})
    if schema.get('mission_protocol')!=PROTOCOL:return None
    duration=schema.get('mission_duration_frames')
    if type(duration) is not int or not 300<=duration<=MAX_DURATION_FRAMES:
        raise ValueError('Invalid continuous mission duration')
    return dict(protocol=PROTOCOL,duration_frames=duration)


def progress_from_receipt(receipt,entry):
    value=receipt.get('mission')
    if entry.get('mission_protocol')!=PROTOCOL:
        if value is not None:raise ValueError('Unapproved continuous mission telemetry')
        return None
    if value is None:return None  # Queued work has no native phase yet.
    if not isinstance(value,dict) or set(value)!=FIELDS:raise ValueError('Invalid mission progress fields')
    if value['mission_id']!=str(uuid.UUID(entry['task_id'])) or str(uuid.UUID(value['mission_id']))!=value['mission_id']:
        raise ValueError('Mission progress task identity changed')
    if value['stage'] not in STAGES:raise ValueError('Unknown mission stage')
    for key in ('revision','observed_frame','deadline_frame'):
        if type(value[key]) is not int or value[key]<=0:raise ValueError('Invalid mission progress clock')
    if value['deadline_frame']!=entry['expires_frame']:raise ValueError('Mission deadline changed')
    observed_limit=entry['expires_frame']+(90 if value['stage']=='restored' else 0)
    if not entry['dispatch_frame']<=value['observed_frame']<=observed_limit:
        raise ValueError('Mission observation outside committed window')
    if entry['expires_frame']-entry['dispatch_frame']>MAX_DURATION_FRAMES:
        raise ValueError('Mission exceeds bounded deadline')
    for key in ('approach_distance','own_hp','damage'):
        number=value[key]
        if key=='approach_distance' and number is None:continue
        if type(number) not in (int,float) or not math.isfinite(number) or not 0<=number<=1e9:
            raise ValueError('Invalid mission progress measurement')
    reason=value['reason']
    if not isinstance(reason,str) or reason not in REASONS:
        raise ValueError('Invalid mission progress reason')
    old=entry.get('last_mission_progress')
    if old:
        if value['revision']<old['revision'] or value['observed_frame']<old['observed_frame'] or value['damage']<old['damage']:
            raise ValueError('Mission progress regressed')
        if value['revision']==old['revision'] and value!=old:raise ValueError('Mission progress revision conflict')
        if old['stage'] in ('retreat','restore','restored','completed','failed') and value['stage'] in ('approach','prepare','engage'):
            raise ValueError('Mission reengaged after retreat')
    return dict(value)


def retreat_context(private_regions,frame,*,home_object_id=None,own_positions=()):
    """Use an actual sampled own position near home, outside its footprint.

    This establishes known provenance, not a promise that combat cannot occur
    there. No enemy lookup, model coordinate or fabricated terrain height enters.
    """
    if type(home_object_id) is not int or home_object_id<=0:return None
    point=private_regions.get('home_base')
    if not isinstance(point,dict) or set(point)!={'xyz','observed_frame'}:return None
    xyz=point['xyz'];observed=point['observed_frame']
    if type(frame) is not int or type(observed) is not int or not 0<=frame-observed<=60:return None
    if not isinstance(xyz,(list,tuple)) or len(xyz)!=3 or any(type(n) not in (int,float) or not math.isfinite(n) or abs(n)>1e6 for n in xyz):return None
    candidates=[]
    for position in own_positions:
        if not isinstance(position,(list,tuple)) or len(position)!=3 or any(type(n) not in (int,float) or not math.isfinite(n) or abs(n)>1e6 for n in position):continue
        distance=math.hypot(position[0]-xyz[0],position[1]-xyz[1])
        if 80<=distance<=300:candidates.append((distance,tuple(position)))
    if not candidates:return None  # The building centre is not a walkable destination.
    _,destination=min(candidates)
    return dict(schema_version=1,retreat_point=dict(xyz=list(destination),observed_frame=observed,source='own_home_base',anchor_object_id=home_object_id),retreat_region='home_base')
