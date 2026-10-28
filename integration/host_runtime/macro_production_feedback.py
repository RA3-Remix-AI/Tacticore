"""Reduce bound native observations into macro feedback, without execution authority.

Private producer/queue/Thing IDs stay here. A queue count, paid field, and new
own unit are independent observations; none establishes a queue-to-unit callback.
"""
import math

from .contracts import ContractError


TARGETS={
    'produceconscript':('0x19ab11af','0x80d4ea1e'),
    'produceflak':('0x2c358c61','0x80d4ea1e'),
    'producetank':('0x94b3590b','0xd50c222e'),
}


def natural(value, code, *, positive=False):
    if type(value) is not int or not (1 if positive else 0)<=value<=0xffffffff:
        raise ContractError(code)
    return value


def frames(builder,census):
    if (builder.get('source')!='native_macro_builder_read_only'
            or builder.get('process_writes')!=0 or builder.get('native_calls')!=0
            or census.get('enemy_details_read') is not False):
        raise ContractError('macro_production_observation_source')
    first=natural(builder.get('frame'),'macro_production_frame',positive=True)
    second=natural(census.get('frame'),'macro_production_frame',positive=True)
    if abs(first-second)>15:raise ContractError('macro_production_observations_too_far_apart')
    return first,second


def read_sample(builder,census,target,producer_type):
    at=frames(builder,census)
    objects={}
    for row in census['own_objects']:
        ident=natural(row['thing_id'],'macro_production_own_id',positive=True)
        if ident in objects:raise ContractError('macro_production_duplicate_own_id')
        objects[ident]=row['type_hash']
    eligible=set();queues={}
    for row in builder['builders']:
        factory=row['factory'];ident=natural(factory['thing_id'],'macro_production_producer_id',positive=True)
        if factory['type_hash']!=producer_type or row.get('observation_available') is not True:continue
        hp=factory.get('hp')
        if type(hp) not in (float,int) or not math.isfinite(hp) or hp<=0:continue
        if objects.get(ident)!=producer_type:continue
        eligible.add(ident)
        for node in row['queue_candidate']['nodes']:
            if node['kind_raw']!=1 or node['template_hash']!=target:continue
            queue_id=natural(node['production_id_raw'],'macro_production_queue_id',positive=True)
            cost=natural(node['native_cost_plus_30'],'macro_production_queue_cost',positive=True)
            paid=natural(node['paid_accumulator_plus_68'],'macro_production_queue_paid')
            if paid>cost:raise ContractError('macro_production_queue_paid')
            key=(ident,queue_id)
            if key in queues and queues[key]!=(cost,paid):raise ContractError('macro_production_queue_conflict')
            queues[key]=(cost,paid)
    return at,objects,eligible,queues


class ProductionFeedback:
    """One bounded macro production intent; callers own dispatch and gate release."""
    def __init__(self,action,additional_count,builder,census):
        if type(action) is not str or action not in TARGETS or type(additional_count) is not int or not 1<=additional_count<=3:
            raise ContractError('macro_production_quantity')
        self.action=action;self.additional_count=additional_count
        self.target,self.producer_type=TARGETS[action]
        at,objects,eligible,queues=read_sample(builder,census,self.target,self.producer_type)
        if not eligible:raise ContractError('macro_production_no_available_producer')
        self.frames=at;self.baseline_queues=set(queues)
        self.baseline_units={ident for ident,kind in objects.items() if kind==self.target}
        self.eligible=eligible;self.new_queues={};self.new_units=set();self.unavailable=set();self.post_release_queues=set()
        self.policy_released=False;self.reason=None

    def observe(self,builder,census):
        at,objects,eligible,queues=read_sample(builder,census,self.target,self.producer_type)
        if any(new<old for new,old in zip(at,self.frames)):
            raise ContractError('macro_production_observation_regression')
        # Validate before committing any state, including partially parsed input.
        updates={key:value for key,value in queues.items() if key not in self.baseline_queues}
        if any(key in self.new_queues and (value[0]!=self.new_queues[key][0] or value[1]<self.new_queues[key][1])
               for key,value in updates.items()):
            raise ContractError('macro_production_queue_regression')
        if self.policy_released:
            self.post_release_queues.update(key for key in updates if key not in self.new_queues)
            updates={key:value for key,value in updates.items() if key in self.new_queues}
        self.frames=at;self.eligible=eligible;self.new_queues.update(updates)
        self.new_units.update(ident for ident,kind in objects.items() if kind==self.target and ident not in self.baseline_units)
        self.unavailable.update(producer for producer,_ in self.new_queues if producer not in objects)
        return self.public()

    @property
    def release_required(self):
        return not self.policy_released and (len(self.new_queues)>=self.additional_count or not self.eligible or bool(self.unavailable))

    def mark_policy_released(self,reason):
        if reason not in ('queue_target_observed','producer_unavailable','scope_changed','expired','stopped'):
            raise ContractError('macro_production_release_reason')
        self.policy_released=True;self.reason=reason

    def available_actions(self,qualified_actions):
        # This can revoke an existing grant, never create one.
        return tuple(action for action in qualified_actions if action!=self.action or self.eligible)

    def public(self):
        lost_incomplete=sum(producer in self.unavailable and paid<cost
                            for (producer,_),(cost,paid) in self.new_queues.items())
        status=('native_production_partial_producer_unavailable' if lost_incomplete else
                'native_production_producer_unavailable' if not self.eligible else
                'native_production_queue_target_observed' if len(self.new_queues)>=self.additional_count else
                'native_production_pending')
        return dict(module='macro',action=self.action,status=status,
            additional_count_requested=self.additional_count,count_control_basis='new_native_queue_acceptances',
            observed_new_queue_count=len(self.new_queues),queue_target_observed=len(self.new_queues)>=self.additional_count,
            additional_queue_observations_after_release=len(self.post_release_queues),
            queue_target_overshot=len(self.new_queues)>self.additional_count,
            fully_paid_queue_observations=sum(paid==cost for cost,paid in self.new_queues.values()),
            new_own_unit_observations=len(self.new_units),available_producer_count=len(self.eligible),
            producer_unavailable_observed=bool(self.unavailable),incomplete_queues_with_unavailable_producer=lost_incomplete,
            policy_released=self.policy_released,release_reason=self.reason,
            builder_frame=self.frames[0],own_census_frame=self.frames[1],
            completed_units_verified=False,exact_queue_to_unit_link_verified=False,payment_verified=False,
            exclusive_macro_attribution_verified=False,automatic_retry_allowed=False,
            unit_operation_policy='native_ai',product_capability_granted=False)
