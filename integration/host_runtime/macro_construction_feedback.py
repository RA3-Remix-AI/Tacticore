"""Own construction observations, never a completed-building or unit-control claim."""
from .contracts import ContractError
from .macro_production_feedback import read_sample

TARGET='0x524bbd01'
PRODUCER='0xc16ff13f'
ACTION='buildreactor'


class ConstructionFeedback:
    def __init__(self,builder,census):
        at,objects,eligible,queues=read_sample(builder,census,TARGET,PRODUCER)
        if len(eligible)!=1:raise ContractError('macro_construction_unique_builder_required')
        self.frames=at;self.eligible=eligible;self.baseline_builders=set(eligible);self.baseline_queues=set(queues)
        self.baseline_objects={ident for ident,kind in objects.items() if kind==TARGET}
        self.new_queues={};self.new_objects=set();self.after_release=set()
        self.policy_released=False;self.reason=None;self.positive=False

    def observe(self,builder,census,flag):
        at,objects,eligible,queues=read_sample(builder,census,TARGET,PRODUCER)
        if any(new<old for new,old in zip(at,self.frames)):
            raise ContractError('macro_construction_observation_regression')
        updates={key:value for key,value in queues.items() if key not in self.baseline_queues and key[0] in self.baseline_builders}
        if any(key in self.new_queues and (cost!=self.new_queues[key][0] or paid<self.new_queues[key][1])
               for key,(cost,paid) in updates.items()):
            raise ContractError('macro_construction_queue_regression')
        positive=any(entry['flag']==flag and entry['state_score']>0 and any(
            item['build_type_hash_raw']==TARGET for item in entry['entries']) for entry in builder['macro_entries'])
        if self.policy_released:
            self.after_release.update(key for key in updates if key not in self.new_queues)
            updates={key:value for key,value in updates.items() if key in self.new_queues}
        self.frames=at;self.eligible=eligible;self.new_queues.update(updates)
        self.new_objects.update(ident for ident,kind in objects.items() if kind==TARGET and ident not in self.baseline_objects)
        if not self.policy_released:self.positive|=positive

    @property
    def release_required(self):
        return not self.policy_released and bool(self.new_queues or self.new_objects or self.eligible!=self.baseline_builders)

    def mark_policy_released(self,reason):
        self.policy_released=True;self.reason=reason

    def public(self):
        return dict(module='macro',action=ACTION,status='native_construction_queue_observed' if self.new_queues else
            'native_construction_builder_unavailable' if self.eligible!=self.baseline_builders else 'native_construction_pending',
            observed_new_queue_count=len(self.new_queues),new_own_construction_object_observations=len(self.new_objects),
            fully_paid_queue_observations=sum(paid==cost for cost,paid in self.new_queues.values()),
            available_builder_count=len(self.eligible),positive_native_build_state_observed=self.positive,
            builder_scope_changed=self.eligible!=self.baseline_builders,
            additional_queue_observations_after_release=len(self.after_release),
            policy_released=self.policy_released,release_reason=self.reason,
            builder_frame=self.frames[0],own_census_frame=self.frames[1],
            construction_completed_verified=False,exact_queue_to_object_link_verified=False,
            payment_verified=False,exclusive_macro_attribution_verified=False,automatic_retry_allowed=False,
            unit_operation_policy='native_ai')


def compact_construction_feedback(value,game_seconds):
    counts=('observed_new_queue_count','new_own_construction_object_observations','fully_paid_queue_observations',
            'available_builder_count','additional_queue_observations_after_release')
    bools=('positive_native_build_state_observed','policy_released','builder_scope_changed')
    frames=('builder_frame','own_census_frame')
    if (type(value) is not dict or value.get('action')!=ACTION or value.get('status') not in {
            'native_construction_queue_observed','native_construction_builder_unavailable','native_construction_pending'}
            or value.get('release_reason') not in {None,'queue_observed','target_present','builder_unavailable','expired','stopped'}
            or any(type(value.get(k)) is not int or not 0<=value[k]<=100000 for k in counts)
            or any(type(value.get(k)) is not bool for k in bools)
            or any(type(value.get(k)) is not int or not 0<value[k]<=0xffffffff
                   or not -15<=game_seconds*15-value[k]<=30 for k in frames)):
        raise ContractError('macro_construction_feedback_invalid_or_stale')
    return dict(source='native_construction_observation',action=ACTION,status=value['status'],
        release_reason=value['release_reason'],**{k:value[k] for k in (*counts,*bools,*frames)},
        construction_completed_verified=False,exact_queue_to_object_link_verified=False,payment_verified=False,
        exclusive_macro_attribution_verified=False,automatic_retry_allowed=False,unit_operation_policy='native_ai')
