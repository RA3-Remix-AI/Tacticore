"""Explicit strategic diagnostics, bounded by frozen model/native time windows.

Private native command identities are used only to correlate evidence. They and
their payloads are never returned. This is an export-time projection, not a new
authority for commands, game outcomes, or full native lease release.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import uuid

from .contracts import ContractError
from .macro_strategy_public import project_macro_strategy_state,_public_ref

STRATEGY_EVENTS=frozenset(('macro_strategy_review','macro_strategy_declared',
    'macro_strategy_outcome','macro_strategy_budget_observed'))
PREPARED=frozenset(('model_macro_dispatch_prepared','model_macro_production_prepared',
    'model_macro_construction_prepared','model_macro_scout_prepared','model_macro_region_prepared'))
_OUTCOMES=frozenset(('pending','effect_observed','no_effect','failed','cancelled','expired','replaced','unknown'))


def _invalid():raise ContractError('macro_strategy_diagnostics_invalid')


def _uuid(value):
    if type(value) is not str:_invalid()
    try:
        if str(uuid.UUID(value))!=value:_invalid()
    except (ValueError,AttributeError):_invalid()
    return value


def _time(value):
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=86400:_invalid()
    return value


def _code(value):
    if type(value) is not str or re.fullmatch(r'[a-z][a-z0-9_]{0,63}',value) is None:_invalid()
    return value


def project_declaration(value):
    from .desktop_backend import _module
    module=_module('macro_strategy',directory=Path(__file__).resolve().parents[2]/'strategy')
    try:result=module.validate_strategy_declaration(value)
    except module.StrategyError:_invalid()
    result['public_fact_refs']=[_public_ref(ref) for ref in result['public_fact_refs']]
    return result


def _parts(event):
    if 'event_type' in event:return event['event_type'],event.get('payload',{})
    return event.get('kind'),event


def event_seconds(event):
    frame=event.get('game_frame')
    if type(frame) is int and 0<=frame<=0xffffffff:return frame/15
    _,payload=_parts(event)
    at=payload.get('game_time_seconds')
    return at if type(at) in (int,float) and math.isfinite(at) and 0<=at<=86400 else None


class StrategyEvidence:
    """Immutable plan and native-receipt bounds; later frames cannot enlarge it."""
    def __init__(self,events,receipts=None,binding=None):
        self.plans={};self.prepared={};self.declared={};self.attempts=[];self.receipts=receipts or {}
        self.binding=binding;invalid_plans=set()
        for index,event in enumerate(events):
            kind,payload=_parts(event)
            if kind!='plan_applied' or type(payload) is not dict:continue
            plan=payload.get('plan')
            try:
                if type(plan) is not dict or plan.get('origin')!='model':continue
                ident=_uuid(plan.get('plan_id'))
                if ident in invalid_plans:continue
                if ident!=payload.get('plan_id') or plan.get('snapshot_id')!=payload.get('snapshot_id'):continue
                if binding is not None and (plan.get('session_id'),plan.get('commander_id'),plan.get('player_id'))!=(binding.session_id,binding.commander_id,binding.player_id):continue
                begin=_time(plan.get('based_on_game_time_seconds'));end=_time(plan.get('expires_at_game_seconds'))
                if not 5<=end-begin<=60:continue
                declared=project_declaration(plan['macro_strategy']) if plan.get('macro_strategy') is not None else None
                if ident in self.plans and self.plans[ident]['plan']!=plan:
                    invalid_plans.add(ident);del self.plans[ident];continue
                self.plans[ident]=dict(plan=copy.deepcopy(plan),start=begin,end=end,declaration=declared,index=index)
            except ContractError:continue
        latest_request=None
        for index,event in enumerate(events):
            kind,payload=_parts(event)
            if type(payload) is not dict:continue
            if kind=='model_macro_request_context':
                context=payload.get('context')
                value=context.get('game_time_seconds') if type(context) is dict else None
                if type(value) in (int,float) and math.isfinite(value) and 0<=value<=86400:latest_request=value
            if kind in PREPARED:
                if binding is not None and (payload.get('session_id'),payload.get('commander_id'),payload.get('player_id'))!=(binding.session_id,binding.commander_id,binding.player_id):continue
                try:ident=_uuid(payload.get('plan_id'));command=_uuid(payload.get('command_id'))
                except ContractError:continue
                when=event_seconds(event);known=self.plans.get(ident);duration=payload.get('duration_frames')
                if known and payload.get('actions')!=known['plan'].get('macro_actions'):continue
                if when is None and known and type(duration) is int and 0<duration<=900:
                    when=max(known['start'],known['end']-duration/15-1/15)
                if when is None:when=latest_request
                self.prepared[ident]=dict(command=command,index=index,time=when)
                self.attempts.append((index,when,command))
            if kind=='macro_strategy_declared':
                if binding is not None and (payload.get('session_id'),payload.get('commander_id'),payload.get('player_id'))!=(binding.session_id,binding.commander_id,binding.player_id):continue
                try:
                    ident=_uuid(payload.get('plan_id'));strategy=_uuid(payload.get('strategy_id'))
                    command=payload.get('command_id')
                    if command is not None:_uuid(command)
                    if type(payload.get('delivery_unknown')) is not bool:_invalid()
                except ContractError:continue
                self.declared[ident]=dict(strategy_id=strategy,command=command,index=index,unknown=payload['delivery_unknown'])

    def bounds(self,plan_id,command_id):
        if type(plan_id) is not str or type(command_id) is not str:return None
        plan=self.plans.get(plan_id);prepared=self.prepared.get(plan_id);declared=self.declared.get(plan_id)
        if (not plan or plan['declaration'] is None or not prepared or prepared['command']!=command_id
                or not declared or declared['unknown'] or declared['command']!=command_id or declared['index']<prepared['index']):return None
        receipt=self.receipts.get(command_id)
        if type(receipt) is not dict or receipt.get('native_gate_acknowledged') is not True:return None
        begin=receipt.get('native_start_frame');end=receipt.get('native_deadline_frame');seq=receipt.get('seq')
        if (type(begin) is not int or type(end) is not int or not 0<begin<end<=0xffffffff or end-begin>900
                or type(seq) is not int or seq<1):return None
        lower=max(plan['start'],begin/15);upper=min(plan['end'],end/15)
        for index,when,command in self.attempts:
            if index>prepared['index'] and command!=command_id:
                # An unanchored later attempt prevents assuming a longer old
                # effect window. No later observed frame repairs that gap.
                upper=min(upper,lower if when is None else when)
        return (lower,upper) if lower<upper else None

    def effect_valid(self,plan_id,command_id,seen,at=None):
        interval=self.bounds(plan_id,command_id)
        return bool(interval is not None and interval[0]<=seen<interval[1] and (at is None or seen<=at))

    def declaration(self,plan_id,strategy_id):
        known=self.plans.get(plan_id)
        if not known or known['declaration'] is None:return None
        result=copy.deepcopy(known['declaration']);result['strategy_id']=strategy_id
        return result


def journal_receipts(commands):
    result={}
    for command in commands:
        if type(command) is not dict:continue
        if command.get('operation')!='macro_policy' or command.get('status')!='completed':continue
        payload=command.get('payload') or {};ident=command.get('request_id')
        if payload.get('native_command_id')!=ident:continue
        try:_uuid(ident)
        except ContractError:continue
        result[ident]=copy.deepcopy(command.get('receipt') or {})
    return result


def native_receipts(acknowledgements):
    """The accepted trial supplies raw ACKs; expose only fixed scalar bounds."""
    result={}
    for ident,ack in acknowledgements.items():
        if type(ack) is not dict or type(ack.get('native')) is not dict:continue
        native=ack.get('native',{});duration=native.get('duration_frames');end=native.get('deadline_frame')
        seq=ack.get('seq')
        if (ack.get('native_gate_acknowledged') is not True or type(seq) is not int or seq<1
                or any(type(native.get(k)) is not int for k in ('error','request','ack','phase'))
                or native['error']!=0 or native['request']!=native['ack'] or native['ack']!=seq or native['phase'] not in (1,2)
                or type(duration) is not int or not 0<duration<=900 or type(end) is not int
                or not 0<end-duration<end<=0xffffffff):continue
        result[ident]=dict(native_gate_acknowledged=True,seq=seq,native_start_frame=end-duration,native_deadline_frame=end)
    return result


def project_strategy_event(kind,payload,*,binding=None,evidence=None,at=None,command_presence=None):
    if kind not in STRATEGY_EVENTS or type(payload) is not dict:_invalid()
    if payload.get('command_id') is not None:_uuid(payload['command_id'])
    if binding is not None and (payload.get('session_id'),payload.get('commander_id'),payload.get('player_id'))!=(binding.session_id,binding.commander_id,binding.player_id):_invalid()
    plan_id=_uuid(payload.get('plan_id'))
    result=dict(plan_id=plan_id,global_native_release_verified=False,verification_scope='macro_intent_only')
    if kind in ('macro_strategy_review','macro_strategy_declared'):
        result['strategy_id']=_uuid(payload.get('strategy_id'))
    if kind=='macro_strategy_review':
        if type(payload.get('allowed')) is not bool:_invalid()
        result.update(allowed=payload['allowed'],reason_code=_code(payload.get('reason_code')))
    elif kind=='macro_strategy_declared':
        if type(payload.get('delivery_unknown')) is not bool:_invalid()
        result['delivery_unknown']=payload['delivery_unknown']
        if command_presence is None:
            present=payload.get('command_id') is not None
            if present:_uuid(payload['command_id'])
        else:
            if type(command_presence) is not bool:_invalid()
            present=command_presence
        if result['delivery_unknown'] and not present:_invalid()
        result['intent_command_present']=present
        if evidence:
            declared=evidence.declaration(plan_id,result['strategy_id'])
            if declared is not None:result['declaration']=declared
    elif kind=='macro_strategy_budget_observed':
        if payload.get('work_effect_verified') is not False:_invalid()
        seen=_time(payload.get('observed_game_seconds'))
        result.update(observed_game_seconds=seen,work_effect_verified=False,
            budget_observation_window_verified=bool(evidence and evidence.effect_valid(plan_id,payload.get('command_id'),seen,at)))
        interval=evidence.bounds(plan_id,payload.get('command_id')) if evidence else None
        if interval is not None:result.update(effect_window_start_seconds=interval[0],effect_window_end_seconds=interval[1])
    else:
        outcome=payload.get('outcome');reported=payload.get('effect_observed');released=payload.get('native_release_verified')
        if type(outcome) is not str or outcome not in _OUTCOMES or type(reported) is not bool or type(released) is not bool:_invalid()
        result.update(outcome=outcome,reason_code=_code(payload.get('reason_code')),intent_end_verified=released,
            effect_observed=False,effect_reported=reported,effect_window_verified=False)
        seen=payload.get('observed_game_seconds')
        if seen is not None:seen=_time(seen);result['observed_game_seconds']=seen
        if outcome=='effect_observed':
            interval=evidence.bounds(plan_id,payload.get('command_id')) if evidence else None
            if interval is not None:result.update(effect_window_start_seconds=interval[0],effect_window_end_seconds=interval[1])
            valid=bool(reported and seen is not None and evidence and evidence.effect_valid(plan_id,payload.get('command_id'),seen,at))
            result['effect_observed']=valid;result['effect_window_verified']=valid
            if not valid:
                result.update(outcome='unknown',reported_outcome='effect_observed',effect_rejection_reason='strategy_effect_window_unverified')
    return result


def read_strategy_state(path,allowed):
    """One byte snapshot yields both the public state and actual-source hash."""
    index=dict(label='macro_strategy_state',available=False,content_included=False)
    try:
        path=Path(path);allowed=Path(allowed).resolve(strict=True)
        if path.is_symlink() or getattr(path.lstat(),'st_file_attributes',0)&0x400:raise OSError()
        path=path.resolve(strict=True)
        if not path.is_relative_to(allowed) or not path.is_file():raise OSError()
        before=path.stat()
        with path.open('rb') as stream:raw=stream.read(16385)
        after=path.stat()
        if len(raw)>16384:raise OSError()
        stable=(before.st_size==after.st_size==len(raw) and before.st_mtime_ns==after.st_mtime_ns
            and before.st_ino==after.st_ino and before.st_dev==after.st_dev)
        index=dict(label='macro_strategy_state',sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
            content_included=False,stable_during_read=stable)
        if not stable:return None,index,'strategy_state_changed'
        def pairs(items):
            value={}
            for key,item in items:
                if key in value:_invalid()
                value[key]=item
            return value
        value=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=lambda _: _invalid())
        return project_macro_strategy_state(value),index,None
    except (OSError,ValueError,UnicodeError,ContractError):return None,index,'strategy_state_unavailable'


def prepare_strategy_extension(status,raw_files,events):
    """Optional schema1 extension; the legacy diagnostic envelope stays schema1."""
    from .contracts import content_hash
    safe=dict(status)
    projected=None
    if safe.get('macro_strategy') is not None:
        try:projected=project_macro_strategy_state(safe['macro_strategy']);safe['macro_strategy']=projected
        except ContractError:
            safe.pop('macro_strategy',None);safe['macro_strategy_unavailable']=True
    sources=[(Path(path),Path(allowed)) for label,path,allowed in raw_files if label=='host_status']
    strategy_events=sum(_parts(event)[0] in STRATEGY_EVENTS for event in events)
    candidate=sources[0][0].with_name('macro-strategy-state.json') if len(sources)==1 else None
    exists=candidate is not None and candidate.exists()
    if projected is None and not safe.get('macro_strategy_unavailable') and not strategy_events and not exists:
        return safe,None,None
    if candidate is None:
        state,index,reason=None,dict(label='macro_strategy_state',available=False,content_included=False),'strategy_state_source_ambiguous'
    else:state,index,reason=read_strategy_state(candidate,sources[0][1])
    matches=state is not None and projected is not None and state==projected
    if state is not None and not matches:reason='strategy_state_snapshot_changed'
    extension=dict(schema_version=1,kind='macro_strategy_diagnostics_extension',
        state_available=matches,state=state if matches else None,state_source=index,
        state_matches_status=matches,event_count=strategy_events,
        global_native_release_verified=False,verification_scope='macro_intent_only')
    if matches:extension['state_projection_sha256']=content_hash(state)
    if reason:extension['state_reason_code']=reason
    return safe,extension,index
