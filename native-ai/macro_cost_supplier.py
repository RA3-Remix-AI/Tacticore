"""Strict session/frame/template binding for current queue-budget research.

The v2 product supplier remains closed without complete native obligation
coverage. A narrower current-queue observation is available explicitly; it is
never silently converted into the older global NativeCostFact contract.
"""
from dataclasses import dataclass
import copy
import hashlib
import math
from pathlib import Path
import struct

import macro_cost_asset_audit as assets
import macro_cost_observation as cost
import macro_cost_upper_contract as envelope
import macro_payment_observation as payment
import readiness_dependency_contract as dependency


@dataclass(frozen=True)
class CostSessionBinding:
    session_id: str
    pid: int
    process_creation_filetime: int
    executable_sha256: str
    package_sha256: str
    player_index: int
    game_identity: tuple


class CompiledCostUniverse:
    """Created from an actual offline archive audit, not a model/RPC payload."""
    def __init__(self, inventory):
        self.inventory = copy.deepcopy(inventory)
        self.envelope = envelope.derive_cost_envelope(self.inventory)
        self._archives_verified = False
        if not self.envelope['discount_envelope_supported']:
            raise ValueError('cost_supplier_definition_envelope_unproven')
        self.ceilings = {}
        for row in self.envelope['target_conditional_ceilings']:
            key=row['action']; value=row['conditional_base_ceiling']
            if key in self.ceilings and self.ceilings[key]!=value:
                raise ValueError('cost_supplier_quality_cost_disagreement')
            self.ceilings[key]=value
    @classmethod
    def recompute(cls, *, package, game_root, output):
        result=cls(assets.audit(package,game_root,output))
        result._archives_verified=True
        return result


def _validate_session(session):
    if (type(session) is not CostSessionBinding or type(session.session_id) is not str
            or not 0<len(session.session_id)<=128 or type(session.pid) is not int or session.pid<=0
            or type(session.process_creation_filetime) is not int or session.process_creation_filetime<=0
            or session.executable_sha256!=cost.EXE_SHA256 or session.package_sha256!=assets.PACKAGE_SHA256
            or type(session.player_index) is not int or session.player_index!=3
            or type(session.game_identity) is not tuple or len(session.game_identity)!=3):
        raise ValueError('cost_supplier_exact_session_required')
    for value in session.game_identity:
        if type(value) is not str or value!=hex(int(value,0)):
            raise ValueError('cost_supplier_game_identity')
        cost._ptr(int(value,0))


class StrictNativeCostSupplier:
    """Trusted backend-only reader; ``sample`` never supplies price evidence.

    identity_reader must revalidate PID+creation against the open read adapter
    and return CostSessionBinding on every invocation. This module opens no
    handle itself. The identity callback is a backend dependency, not an RPC.
    """
    def __init__(self, read, *, session, identity_reader, universe,
            product_scope='all_accepted_native_payment_obligations_v2'):
        _validate_session(session)
        if type(universe) is not CompiledCostUniverse or not callable(identity_reader):
            raise ValueError('cost_supplier_trusted_dependencies_required')
        if product_scope not in ('all_accepted_native_payment_obligations_v2',
                'current_owned_production_upgrade_queues_v3'):
            raise ValueError('cost_supplier_explicit_scope_required')
        self.read=read; self.session=session; self.identity_reader=identity_reader;self.universe=universe
        self.product_scope=product_scope
        game,owner,factory=(int(value,0) for value in session.game_identity)
        self.costs=cost.NativeCostObserver(read,owner,executable_sha256=session.executable_sha256,expected_owner_index=3)
        self.payments=payment.PaymentCommitmentObserver(read,owner,
            executable_sha256=session.executable_sha256,expected_owner_index=3)
        if (self.costs.base.game,self.costs.owner,self.costs.factory)!=(game,owner,factory):
            raise ValueError('cost_supplier_native_session_identity')
        self._identity()
    def _identity(self):
        observed=self.identity_reader();_validate_session(observed)
        if observed!=self.session:raise ValueError('cost_supplier_process_or_session_changed')

    def _target_binding(self, action):
        read=dependency.StableRead(self.read); template=self.costs.dependencies._template(read,dependency.ACTIONS[action][0])
        if not template:raise ValueError('cost_supplier_target_missing')
        definition=cost._ptr(cost._word(read,template+0x14),0x19c)
        transaction=cost._ptr(cost._word(read,definition+0x198),8)
        count,array=struct.unpack('<II',read(transaction,8))
        if count!=1:raise ValueError('cost_supplier_single_resource_transaction_required')
        account,amount=struct.unpack('<II',read(cost._ptr(array,8),8))
        base=struct.unpack('<H',read(template+0x304,2))[0]
        expected=self.universe.ceilings[action]
        if account!=0 or amount!=base or base!=expected:
            raise ValueError('cost_supplier_loaded_native_cost_drift')
        build_time=struct.unpack('<f',read(definition+0x88,4))[0]
        if not math.isfinite(build_time) or build_time<0:
            raise ValueError('cost_supplier_native_build_time')
        if action.startswith('build') and build_time!=0:
            raise ValueError('cost_supplier_soviet_unpack_payment_context_changed')
        read.finish()
        return dict(template=hex(template),definition=hex(definition),transaction=hex(transaction),
            transaction_count=count,resource_account=account,native_amount=amount,native_base_u16=base,
            audited_conditional_ceiling=expected,native_build_time=build_time,
            loaded_target_cost_fields_match_audited_asset=True)

    def _producer_definitions(self,queues,producer_id,binding):
        read=dependency.StableRead(self.read)
        target_category=cost._word(read,int(binding['definition'],0)+0x130)
        definitions=[]
        for queue in queues['queues']:
            if queue['producer_thing_id']!=producer_id:continue
            module=int(queue['module'],0)
            definition=cost._ptr(cost._word(read,module+4),0x4c)
            category=cost._word(read,definition+0x30)
            quantity_count=cost._word(read,definition+0x3c)
            modifier_count=cost._word(read,definition+0x44)
            if quantity_count or modifier_count:
                raise ValueError('cost_supplier_producer_definition_context_changed')
            definitions.append(dict(module=hex(module),definition=hex(definition),
                category=category,quantity_modifier_count=quantity_count,cost_modifier_count=modifier_count))
        if sum(row['category']==target_category for row in definitions)!=1:
            raise ValueError('cost_supplier_unique_matching_production_category_required')
        read.finish()
        return dict(target_category=target_category,definitions=definitions,
            producer_definition_verified=True)

    def observe(self,action,*,game_seconds,component_frames=()):
        if action not in self.universe.ceilings:raise ValueError('cost_supplier_action')
        if (type(game_seconds) not in (int,float) or not math.isfinite(game_seconds)
                or any(type(f) is not int or f<=0 for f in component_frames)):
            raise ValueError('cost_supplier_frame_input')
        self._identity();start=cost._word(self.read,self.costs.base.game+0x50)
        queues=self.payments.sample()
        candidates=[row['thing_id'] for row in queues['module_census']
            if int(row['template_hash'],0)==cost.PRODUCERS[action]]
        if len(candidates)!=1:raise ValueError('cost_supplier_unique_current_producer_required')
        quote=self.costs.sample(action,producer_thing_id=candidates[0])
        binding=self._target_binding(action)
        producer_binding=self._producer_definitions(queues,candidates[0],binding)
        if quote['native_runtime_base_cost']!=binding['native_base_u16']:
            raise ValueError('cost_supplier_quote_binding_changed')
        self._identity();after=cost._word(self.read,self.costs.base.game+0x50)
        frames=(start,after,queues['frame'],queues['frame_after'],quote['frame'],quote['frame_after'],*component_frames)
        if (not start or not 0<=after-start<=15 or max(frames)-min(frames)>15
                or not -15<=game_seconds*15-after<=15):
            raise ValueError('cost_supplier_components_stale_or_incoherent')
        balance=quote['current_payment_balance']; credits=balance.get('credits')
        queued=queues['production_queue_payment_commitment_upper_bound']
        per_node=binding['audited_conditional_ceiling']
        return dict(schema_version=1,kind='native_current_queue_budget_observation',
            source='native_current_queue_payment_budget_and_target_bound_v1',
            scope='current_payment_balance_and_all_current_own_production_queues',
            session_id=self.session.session_id,pid=self.session.pid,
            process_creation_filetime=self.session.process_creation_filetime,
            player_index=3,game_identity=self.session.game_identity,frame=start,frame_after=after,
            action=action,template_hash=hex(dependency.ACTIONS[action][0]),
            loaded_target_binding=binding,quote=quote,queue_commitments=queues,
            producer_definition_binding=producer_binding,
            credits=credits,credits_verified=balance.get('credits_verified') is True,
            production_queue_payment_commitment_upper_bound=queued,
            current_balance_after_accepted_production_queues=None if credits is None else credits-queued,
            single_native_queue_conditional_upper_cost=per_node,
            current_balance_covers_one_conditional_queue=credits is not None and credits>=queued+per_node,
            loaded_definition_universe_closure_verified=False,
            native_requests_per_flag_window_hard_limit_verified=False,
            host_influence_total_spend_hard_cap_verified=False,
            existing_native_payment_commitment_upper_bound=None,
            existing_native_payment_commitment_upper_bound_verified=False,
            upper_cost=None,upper_cost_verified=False,
            future_autonomous_spending_controlled=False,reservation_usable=False,
            native_calls=0,process_writes=0,enemy_details_read=False,
            field_verified=False,grants_capability=False)

    def _current_queue_fact(self,observation):
        from host_runtime.contracts import ContractError
        from host_runtime.resource_reservations import CurrentQueueBudgetFact,CURRENT_QUEUE_BUDGET_SOURCE
        if observation is not getattr(self,'last_observation',None):
            raise ContractError('blocked_native_cost_reservation_unverified')
        quote=observation['quote'];multiplier=quote['producer_multiplier']
        native_context=(quote['native_getter_quote_verified'] is True
            and multiplier.get('modifier_count')==0
            and quote['producer_attribute_evidence']['cost_adjustment_absent'] is True
            and quote['native_getter_quote']<=observation['single_native_queue_conditional_upper_cost'])
        if (self.product_scope!='current_owned_production_upgrade_queues_v3'
                or self.universe._archives_verified is not True
                or observation['credits_verified'] is not True or not native_context
                or observation['producer_definition_binding']['producer_definition_verified'] is not True):
            raise ContractError('blocked_native_cost_reservation_unverified')
        queues=observation['queue_commitments']
        fact=CurrentQueueBudgetFact(session_id=self.session.session_id,player_id=3,
            action=observation['action'],template_hash=observation['template_hash'],
            source=CURRENT_QUEUE_BUDGET_SOURCE,frame=observation['frame_after'],
            upper_cost=observation['single_native_queue_conditional_upper_cost'],
            credits=observation['credits'],
            production_upgrade_queue_payment_commitment_upper_bound=
                observation['production_queue_payment_commitment_upper_bound'],
            game_identity=self.session.game_identity,producer_thing_id=quote['producer_thing_id'],
            producer_type_hash=hex(cost.PRODUCERS[observation['action']]),
            upper_cost_verified=True,credits_verified=True,
            production_upgrade_queue_payment_commitment_upper_bound_verified=
                queues['all_current_own_production_queues_enumerated'],
            all_owned_production_updates_observed=True,all_production_and_upgrade_nodes_observed=True,
            loaded_target_schema_verified=True,native_quote_context_verified=True,
            producer_definition_verified=True,single_new_request_hard_limit_verified=False,
            native_ai_autonomous_spending_covered=False,repair_and_ability_spending_covered=False,
            additional_count=1)
        return fact

    def __call__(self,action,sample,game_seconds):
        from host_runtime.contracts import ContractError
        frames=[]
        if type(sample) is not dict:raise ContractError('blocked_native_cost_reservation_unverified')
        for key in ('observation','build_observation','dependency','readiness','macro','builder'):
            row=sample.get(key)
            if type(row) is dict and 'frame' in row:frames.append(row['frame'])
        census=sample.get('observation',{}).get('construction_feedback') if type(sample.get('observation')) is dict else None
        if type(census) is dict and 'frame' in census:frames.append(census['frame'])
        self.last_observation=self.observe(action,game_seconds=game_seconds,component_frames=tuple(frames))
        if self.product_scope=='current_owned_production_upgrade_queues_v3':
            return self._current_queue_fact(self.last_observation)
        # The existing v2 fact requires *all* already accepted deferred cash
        # obligations. A complete production-queue scan alone is insufficient.
        raise ContractError('blocked_native_cost_reservation_unverified')
