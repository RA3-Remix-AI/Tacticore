"""Offline size estimate using public historical context and public traits only."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'strategy')]
from http_adapter import system_prompt
from macro_policy import public_descriptions
from integration.host_runtime.macro_group_role_contract import group_role_catalog_overrides

rows=[json.loads(l) for l in (ROOT/'acceptance/runs/20261028-133800-macro-probe/battle-host/host-events.jsonl').read_text().splitlines()]
context=copy.deepcopy([r['context'] for r in rows if r['kind']=='model_macro_request_context'][-1])
profile=json.loads((ROOT/'reports/macro-group-role-directed-profile-20261028.json').read_text())
scope=json.loads((ROOT/'reports/macro-group-role-desktop-bootstrap-20261028-v1/qualification.json').read_text())['scope']
context['allowed_macro_actions']=scope['available_actions']
context['macro_policy_catalog']=public_descriptions(scope['available_actions'],scope['production_counts'].items(),scope['regional_action_regions'].items())
context['macro_policy_catalog'].update(group_role_catalog_overrides())
public_profile=SimpleNamespace(personality=profile['personality'],traits=profile['effective']['traits'])
def size(value):
    prompt=system_prompt(public_profile,value)
    encoded=json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))
    return len(json.dumps(dict(messages=[dict(role='system',content=prompt),dict(role='user',content=encoded)]),ensure_ascii=False).encode('utf8'))+1024
full=size(context)
context['conversation_tail']=[]
for key in ('recent_execution_feedback','local_maneuver_feedback','active_goals','verified_enemy_facts','failure_memory'):
    if key in context['working_memory']:context['working_memory'][key]=[]
for key in ('contacts','regions','formations'):context['working_memory']['battlefield'][key]=[]
context['allowed_regions']=['region_1_3','region_8_3'];context['delta']['verified_events']=context['delta']['verified_events'][-1:]
result=dict(kind='offline_public_group_role_wire_size_estimate',historical_context_with_full_catalog_bytes=full,
    compacted_estimate_bytes=size(context),wire_limit=16384,model_calls=0,credential_access=False,
    live_current_request_claimed=False)
out=ROOT/'reports/macro-group-role-wire-size-20261028-v1.json'
with out.open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
print(json.dumps(result))
