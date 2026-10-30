"""Bind one immutable model request to one real lawful observation.

The normal Audit and backend still validate, log and send it. This only freezes
their public suppliers before asynchronous scheduling; no native authority or
future memory is imported into the older request.
"""
from copy import deepcopy
import json

from .contracts import ContractError
from .macro_policy_runtime import MacroRequestAudit
from .macro_admission_feedback_v4 import MacroRequestAuditV4
from .strategic_unified_feedback_v5 import UnifiedRequestAuditV5
from battle_agent import BattleAgent
from engine import Snapshot,Decision
from macro_strategy import MacroStrategyMemory

_SEAL=object()
SUPPLIERS=('feedback_supplier','production_supplier','construction_supplier','infrastructure_supplier',
    'scouting_supplier','regional_supplier','forces_supplier','catalog_supplier','expansion_supplier','resource_supplier')


def fail(code):raise ContractError('macro_prepared_request_'+code)
def encoded(value):return json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf8')


class PreparedMacroRequestV1:
    def __init__(self,snapshot,measure,sender,parent,sequence,seal):
        if seal is not _SEAL:fail('trusted_capture_required')
        self.snapshot=snapshot;self.measure=measure;self.sender=sender;self.parent=parent
        self.sequence=sequence;self.called=False
    def __getattr__(self,name):return getattr(self.measure,name)
    def input_size(self,context):return self.measure.input_size(context)
    async def __call__(self,context):
        if self.called or self.parent.sequence!=self.sequence:fail('already_consumed_or_superseded')
        self.called=True
        return await self.sender(context)


def prepare_macro_request_v1(agent,audit,snapshot):
    """Synchronous capture before create_task; providers are read exactly once."""
    if (type(agent) is not BattleAgent or type(audit) not in (MacroRequestAudit,MacroRequestAuditV4,UnifiedRequestAuditV5)
            or type(snapshot) is not Snapshot or snapshot!=agent.latest or snapshot.macro_control is None):fail('current_snapshot_required')
    supplier=audit.strategy_supplier
    if supplier is not None:
        memory=getattr(supplier,'__self__',None)
        if type(memory) is not MacroStrategyMemory or getattr(supplier,'__func__',None) is not MacroStrategyMemory.context:
            fail('canonical_strategy_required')
        strategy=deepcopy(memory).context
    else:strategy=None
    providers={}
    for name in (*SUPPLIERS,*(('unified_supplier',) if type(audit) is UnifiedRequestAuditV5 else ())):
        supplier=getattr(audit,name)
        if supplier is None:providers[name]=None;continue
        value=deepcopy(supplier())
        providers[name]=lambda value=value:deepcopy(value)
    measure=type(audit)(audit.backend,audit.event,strategy_supplier=strategy,
                       strategic_only=audit.strategic_only,**providers)
    limit=getattr(audit,'max_input_bytes',16384)
    if type(limit) is not int or not 1<=limit<=16384:fail('wire_limit')
    base=agent.context(snapshot.model_context(agent.engine.binding),commit=False,
        wire_size=measure.input_size,wire_limit=limit)
    prepared=measure.prepare(base);base_bytes=encoded(base);prepared_bytes=encoded(prepared)
    if len(prepared_bytes)>16384 or audit.backend.input_size(prepared)>limit:fail('wire_limit')
    for key in ('session_id','commander_id','player_id','snapshot_id','game_time_seconds'):
        if prepared.get(key)!=base.get(key):fail('snapshot_binding')
    sequence=audit.sequence;sender=None
    def event(kind,**facts):
        if kind=='model_macro_request_context':
            if audit.sequence!=sequence or facts.get('sequence')!=sequence+1:fail('sequence_changed')
            # Keep the live audit's exact sent-request lookup for subsequent
            # dispatch review. Its prepare() continues using current providers.
            audit._last_request_context=deepcopy(facts['context']);audit.sequence=facts['sequence']
        audit.event(kind,**facts)
    sender=type(audit)(audit.backend,event,strategy_supplier=strategy,
                      strategic_only=audit.strategic_only,**providers);sender.sequence=sequence
    def exact_prepared(context):
        if encoded(context)!=base_bytes:fail('captured_context_changed')
        return json.loads(prepared_bytes)
    sender.prepare=exact_prepared
    return PreparedMacroRequestV1(snapshot,measure,sender,audit,sequence,_SEAL)


async def decide_prepared_macro_request_v1(agent,snapshot,prepared):
    """A task delayed before starting cannot regress the agent's observation."""
    if type(prepared) is not PreparedMacroRequestV1 or prepared.snapshot!=snapshot:fail('snapshot_binding')
    if agent.latest!=snapshot:return Decision('deferred','macro_prepared_request_snapshot_superseded',None)
    return await agent.decide(snapshot,prepared)
