"""Bounded shape/enum diagnostics only. Never repairs or exports unknown text."""
import hashlib
import json
import re
import unicodedata
from macro_policy import ACTIONS,restore_public_defaults,validate_actions,validate_production

SAFE_ACTION_ERRORS=frozenset(('macro_policy_actions','unsupported_macro_action','conflicting_macro_actions','conflicting_macro_work_actions'))
SAFE_PRODUCTION_ERRORS=frozenset(('macro_production_without_action','macro_production_quantity','macro_production_quantity_not_qualified'))
SELECTOR_FIELDS=('action','name','macro_action','type','flag')


def kind(value):
    return {type(None):'null',bool:'boolean',int:'integer',float:'number',str:'string',list:'array',dict:'object'}.get(type(value),'other')


def fingerprint(value):
    try:
        raw=json.dumps(value,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode('ascii')
        return dict(canonical_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    except (ValueError,TypeError,UnicodeError,RecursionError):return dict(fingerprint_unavailable=True)


def normalized_match(value):
    if type(value) is not str:return None
    normalized=re.sub(r'[\s_-]+','',unicodedata.normalize('NFKC',value).casefold())
    return normalized if normalized in ACTIONS else None


def action_shape(policy,context):
    raw=policy.get('macro_actions') if type(policy) is dict else None
    try:public=restore_public_defaults(context)
    except (ValueError,TypeError):public={}
    allowed=public.get('allowed_macro_actions')
    allowed_valid=type(allowed) is list and all(type(a) is str and a in ACTIONS for a in allowed)
    allowed=set(allowed) if allowed_valid else set()
    result=dict(present=type(policy) is dict and 'macro_actions' in policy,type=kind(raw),
        request_allowed_available=allowed_valid,list_length=len(raw) if type(raw)is list else None,
        maximum_items=5,items=[],validation_code=None)
    if type(raw) is list:
        exact=[a for a in raw if type(a)is str and a in ACTIONS]
        tokens=[fingerprint(a).get('sha256') for a in raw]
        result.update(unique_count=len(set(tokens)) if None not in tokens else None,
            item_type_counts={t:sum(kind(a)==t for a in raw) for t in sorted({kind(a) for a in raw})},
            known_string_count=len(exact),request_allowed_string_count=sum(a in allowed for a in exact),
            known_action_names=sorted(set(exact)),request_allowed_action_names=sorted(set(exact)&allowed),
            inspected_items=min(8,len(raw)),items_truncated=len(raw)>8)
        for value in raw[:8]:
            row={'type':kind(value)}
            if type(value)is str and value in ACTIONS:
                row.update(known_action=value,request_allowed=value in allowed)
            else:
                row.update(fingerprint(value))
                match=normalized_match(value)
                if match is not None:row['normalized_known_action']=match
                if type(value)is dict:
                    row['key_count']=len(value);selectors=[]
                    for key in SELECTOR_FIELDS:
                        if key not in value:continue
                        selected=value[key];entry={'field':key,'type':kind(selected)}
                        if type(selected)is str and selected in ACTIONS:
                            entry.update(known_action=selected,request_allowed=selected in allowed)
                        else:
                            entry.update(fingerprint(selected));match=normalized_match(selected)
                            if match is not None:entry['normalized_known_action']=match
                        selectors.append(entry)
                    row['known_selector_fields']=selectors
            result['items'].append(row)
    elif raw is not None:result.update(fingerprint(raw))
    try:validate_actions(raw,allowed,allowed)
    except ValueError as error:
        result['validation_code']=error.args[0] if len(error.args)==1 and error.args[0] in SAFE_ACTION_ERRORS else 'macro_action_validation_unknown'
    return result


def production_shape(policy,context):
    if type(policy) is not dict:return {'type':'null','validation_code':'macro_policy_not_object'}
    value=policy.get('macro_production');actions=policy.get('macro_actions')
    result={'present':'macro_production' in policy,'type':kind(value),'validation_code':None}
    production=[a for a in actions if type(a)is str and ACTIONS.get(a)=='production'] if type(actions)is list else []
    result['known_production_actions']=sorted(set(production))
    if type(value)is dict:
        result.update(fields_match=set(value)=={'action','additional_count'},extra_field_count=len(set(value)-{'action','additional_count'}),
            action_type=kind(value.get('action')),additional_count_type=kind(value.get('additional_count')))
        if type(value.get('action'))is str and value['action'] in ACTIONS:result['known_action']=value['action']
        else:result['action_fingerprint']=fingerprint(value.get('action'))
        count=value.get('additional_count')
        if type(count)is int and 1<=count<=3:result['bounded_additional_count']=count
        else:result['count_fingerprint']=fingerprint(count)
    if any(type(a)is not str or a not in ACTIONS for a in actions) if type(actions)is list else True:
        result['validation_code']='macro_actions_invalid_before_production';return result
    try:
        public=restore_public_defaults(context);catalog=public.get('macro_policy_catalog',{})
        counts={a:v['quantity']['allowed_additional_counts'] for a,v in catalog.items()
            if type(v)is dict and type(v.get('quantity'))is dict and 'allowed_additional_counts' in v['quantity']}
        validate_production(value,actions,macro_mode=True,request_counts=counts,latest_counts=counts)
    except ValueError as error:
        result['validation_code']=error.args[0] if len(error.args)==1 and error.args[0] in SAFE_PRODUCTION_ERRORS else 'macro_production_validation_unknown'
    return result
