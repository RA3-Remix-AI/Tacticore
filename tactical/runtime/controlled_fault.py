"""Owned diagnostic helpers; no game call, state write or permission grant."""
import hashlib,json,math,os
from pathlib import Path

NAMES=frozenset(('controlled-fault-intent.json','recovery-return-intent.json','failed-return-release-intent.json'))

def seal_owned_intent(output,name,wire,context):
    if name not in NAMES:raise ValueError('owned_diagnostic_intent_name_unreviewed')
    path=Path(output).resolve().parent/name
    body=dict(schema_version=1,kind='owned_diagnostic_pre_effect_intent',wire=wire,context=context,
        ordinary_authority_granted=False,model_requests=0)
    payload=(json.dumps(body,sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False)+'\n').encode('utf-8')
    with path.open('xb')as stream:
        stream.write(payload);stream.flush();os.fsync(stream.fileno())
    return dict(file=str(path),sha256=hashlib.sha256(payload).hexdigest())

def choose_fault_point(runtime,binding,state):
    sample=runtime.observe_actor(binding)
    if sample.get('settled') is not True or sample.get('stance')!=2 or sample.get('team')!=sample.get('script_team'):
        raise ValueError('controlled_fault_actor_not_stopped_no_injection')
    home=runtime.reserved_home(state['task_id'],state['lease_id'])['xyz']
    points=runtime.targets()
    eligible=[(math.dist(p[:2],sample['xyz'][:2]),key,p)for key,p in points.items()
        if 30<=math.dist(p[:2],sample['xyz'][:2])<=120 and 30<=math.dist(p[:2],home[:2])<=300
        and abs(p[2]-sample['xyz'][2])<=2 and abs(p[2]-home[2])<=2]
    if not eligible:return None,None
    distance,key,point=min(eligible)
    return key,dict(source='current_native_endpoint_registry',sample=sample,private_home=home,
        selected_point_id=key,target_xyz=list(point),distance_xy=distance,ordinary_authority_granted=False)
