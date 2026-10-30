"""Parameterised queue/readiness facts; no guessed completion or permissions."""
import math

from .contracts import ContractError
from .macro_expansion_scope import EXTRA_ACTIONS, TARGETS
from .macro_production_feedback import read_sample
from .resource_reservations import compact_reservation


def pair(sample):
    try:return sample['build_observation'],sample['observation']['construction_feedback']
    except (KeyError,TypeError):raise ContractError('macro_expansion_sample_missing') from None


def live_gate(action,sample,game_seconds):
    """A known enqueue subpredicate never becomes an overall permission claim."""
    if action not in TARGETS:raise ContractError('macro_expansion_action_unknown')
    builder,census=pair(sample);target,producer,domain=TARGETS[action]
    at,objects,eligible,queues=read_sample(builder,census,target,producer)
    readiness=sample.get('readiness',{});dependency=sample.get('dependency',{})
    fs=(*at,sample.get('observation',{}).get('frame'),readiness.get('frame'),dependency.get('frame'))
    if (any(type(frame) is not int or frame<=0 or not -15<=game_seconds*15-frame<=15 for frame in fs)
            or max(fs)-min(fs)>15 or readiness.get('kind')!='native_own_readiness_observation'
            or readiness.get('own_perspective') is not True or readiness.get('enemy_details_read') is not False
            or readiness.get('native_calls')!=0 or readiness.get('process_writes')!=0
            or dependency.get('kind')!='native_required_object_dependency_observation'
            or dependency.get('enemy_details_read') is not False or dependency.get('owner_index')!=3
            or dependency.get('native_calls')!=0 or dependency.get('process_writes')!=0):
        raise ContractError('macro_expansion_readiness_missing_or_stale')
    identity=dependency.get('session_identity')
    if (type(identity) is not dict or identity.get('owner_index')!=3
            or any(not isinstance(identity.get(key),str) or not identity[key].startswith('0x')
                   for key in ('game','owner','template_factory'))):
        raise ContractError('macro_expansion_dependency_identity_missing')
    rows=[row for row in dependency.get('actions',[]) if row.get('action')==action]
    if (len(rows)!=1 or rows[0].get('target_type_hash')!=target
            or rows[0].get('target_template_loaded') is not True
            or rows[0].get('prerequisite_met') is not True
            or rows[0].get('sdk_required_objects_match') is not True
            or rows[0].get('native_required_objects_met') is not True):
        raise ContractError('macro_expansion_native_prerequisite_unknown_or_missing')
    row=rows[0]
    admissions={entry.get('producer_thing_id') for entry in row.get('enqueue_admission_candidates',[])
        if entry.get('producer_type_hash')==producer and entry.get('native_factory_category_match') is True
        and entry.get('native_enqueue_admission_met') is True and entry.get('unresolved_admission_conditions')==[]
        and entry.get('native_stop') is False and entry.get('native_unpacking') is False}
    ready={entry.get('thing_id') for entry in readiness.get('own_objects',[])
        if entry.get('currently_registered') is True and entry.get('named_template_supported') is True
        and entry.get('type_hash')==producer and type(entry.get('hp')) in (int,float) and entry['hp']>0
        and not any(entry.get('object_status',{}).get(key) is not False for key in
            ('destroyed','under_construction','sold','reconstructing','not_in_world','pending_construction','unpacking'))}
    allowed=eligible&admissions&ready
    if len(allowed)!=1 or allowed!=eligible:raise ContractError('macro_expansion_unique_ready_producer_required')
    power=readiness.get('power',{})
    if action=='buildpower':
        if (type(power.get('native_supply')) is not int or type(power.get('native_demand')) is not int
                or power['native_supply']>=power['native_demand'] or power.get('native_energy_sufficient') is not False):
            raise ContractError('macro_expansion_native_power_need_missing')
    elif power.get('native_energy_sufficient') is not True:
        raise ContractError('macro_expansion_power_unknown_or_unavailable')
    if any(witness.get('underpowered') is True for required in row.get('required_object_evidence',[])
           for witness in required.get('witnesses',[])):
        raise ContractError('macro_expansion_dependency_underpowered')
    if action=='buildrefinery' and row.get('native_open_resource_node_available') is not True:
        raise ContractError('macro_expansion_open_resource_node_unknown')
    own_targets={ident for ident,kind in objects.items() if kind==target}
    if action in ('buildbarracks','buildfactory','buildbattlelab') and own_targets:
        raise ContractError('macro_expansion_single_structure_already_present')
    if queues:raise ContractError('macro_expansion_target_queue_already_present')
    if domain=='construction' and any(entry.get('factory',{}).get('thing_id') in allowed
        and entry.get('observation_available') is True and entry.get('queue_candidate',{}).get('nodes')
        for entry in builder.get('builders',[])):
        raise ContractError('macro_expansion_native_builder_occupied')
    return dict(frames=fs,producer_ids=allowed,gate=row)


class ExpansionFeedback:
    def __init__(self,action,sample,game_seconds):
        self.action=action;self.target,self.producer,self.domain=TARGETS[action]
        gate=live_gate(action,sample,game_seconds);builder,census=pair(sample)
        at,objects,eligible,queues=read_sample(builder,census,self.target,self.producer)
        self.frames=at;self.baseline_producers=set(gate['producer_ids']);self.eligible=eligible
        self.baseline_queues=set(queues);self.baseline_objects={ident for ident,kind in objects.items() if kind==self.target}
        self.new_queues={};self.new_objects=set();self.late_queues=set();self.positive=False
        self.completed=set();self.previous={};self.last_dependency_frame=None
        self.session_identity=sample.get('dependency',{}).get('session_identity')
        self.policy_released=False;self.release_reason=None;self.native_start_frame=None;self.deadline_frame=None

    def bind_native_window(self,begin,deadline):
        if type(begin) is not int or type(deadline) is not int or not 0<begin<deadline<=0xffffffff:
            raise ContractError('macro_expansion_native_window_required')
        self.native_start_frame=begin;self.deadline_frame=deadline

    def observe(self,sample,flag):
        builder,census=pair(sample);at,objects,eligible,queues=read_sample(builder,census,self.target,self.producer)
        if any(new<old for new,old in zip(at,self.frames)):raise ContractError('macro_expansion_feedback_regression')
        dependency=sample.get('dependency',{});extra=dependency.get('frame')
        component_frames=(*at,extra,sample.get('observation',{}).get('frame'),sample.get('readiness',{}).get('frame'))
        if dependency.get('session_identity')!=self.session_identity:
            raise ContractError('macro_expansion_feedback_session_changed')
        if (dependency.get('kind')!='native_required_object_dependency_observation'
                or dependency.get('native_calls')!=0 or dependency.get('process_writes')!=0
                or dependency.get('enemy_details_read') is not False or dependency.get('owner_index')!=3
                or any(type(frame) is not int or frame<=0 for frame in component_frames)
                or max(component_frames)-min(component_frames)>15
                or self.last_dependency_frame is not None and extra<self.last_dependency_frame):
            raise ContractError('macro_expansion_feedback_dependency_stale')
        within=(not self.policy_released and self.native_start_frame is not None
                and min(component_frames)>=self.native_start_frame and max(component_frames)<self.deadline_frame)
        updates={key:value for key,value in queues.items() if key not in self.baseline_queues and key[0] in self.baseline_producers}
        if any(key in self.new_queues and (value[0]!=self.new_queues[key][0] or value[1]<self.new_queues[key][1])
               for key,value in updates.items()):raise ContractError('macro_expansion_feedback_queue_regression')
        if not within:
            self.late_queues.update(key for key in updates if key not in self.new_queues)
            updates={key:value for key,value in updates.items() if key in self.new_queues}
        self.new_queues.update(updates);self.eligible=eligible;self.frames=at
        if within:
            self.new_objects.update(ident for ident,kind in objects.items() if kind==self.target and ident not in self.baseline_objects)
            self.positive|=any(entry.get('flag')==flag and entry.get('dirty') is False
                and type(entry.get('state_score')) in (float,int) and math.isfinite(entry['state_score']) and entry['state_score']>0
                and any(item.get('build_type_hash_raw')==self.target for item in entry.get('entries',[]))
                for entry in builder.get('macro_entries',[]))
        self._completion_edges(dependency,within)
        return self.public()

    def _completion_edges(self,dependency,within):
        frame=dependency['frame']
        if self.last_dependency_frame is None or not 0<frame-self.last_dependency_frame<=30:self.previous={}
        current={}
        for row in dependency.get('own_lifecycles',[]):
            if row.get('type_hash')!=self.target:continue
            key=tuple(row.get(name) for name in ('thing_id','thing_address','template_address','type_hash'))
            if any(value is None for value in key):continue
            status=row.get('object_status',{});unpack=row.get('unpack',{})
            active=unpack.get('native_unpack_in_progress');notified=row.get('native_unpack_completion_notified')
            negative=any(status.get(name) is True for name in ('under_construction','pending_construction','unpacking','reconstructing'))
            valid=(row.get('currently_registered') is True and row.get('named_template_supported') is True
                and type(row.get('hp')) in (float,int) and row['hp']>0
                and all(status.get(name) is False for name in ('destroyed','sold','not_in_world')))
            before=self.previous.get(key)
            if (within and valid and not negative
                    and all(status.get(name) is False for name in ('under_construction','pending_construction','unpacking','reconstructing'))
                    and active is False and notified is True and before
                    and before['within']
                    and before['active'] is True and before['notified'] is False and before['negative']
                    and type(before['duration']) is int and before['duration']>0
                    and type(before['started']) is int and before['started']>0
                    and before['duration']==unpack.get('native_unpack_duration_frames')
                    and before['started']==unpack.get('native_unpack_started_frame')
                    and row['thing_id'] in self.new_objects):
                self.completed.add(key)
            current[key]=dict(active=active,notified=notified,negative=negative,within=within,
                duration=unpack.get('native_unpack_duration_frames',0),started=unpack.get('native_unpack_started_frame',0))
        self.previous=current;self.last_dependency_frame=frame

    @property
    def release_required(self):
        return not self.policy_released and (bool(self.new_queues) or self.eligible!=self.baseline_producers)

    def mark_policy_released(self,reason):
        if reason not in ('queue_target_observed','producer_unavailable','prerequisite_changed','expired','stopped'):
            raise ContractError('macro_expansion_release_reason')
        self.policy_released=True;self.release_reason=reason

    def public(self):
        return dict(source='native_macro_expansion_observation',action=self.action,domain=self.domain,
            status='native_queue_observed' if self.new_queues else 'native_producer_unavailable'
                if self.eligible!=self.baseline_producers else 'native_expansion_pending',
            additional_count_requested=1,observed_new_queue_count=len(self.new_queues),
            observed_queue_cost_sum=sum(cost for cost,paid in self.new_queues.values()),
            observed_paid_field_sum=sum(paid for cost,paid in self.new_queues.values()),
            new_own_target_observations=len(self.new_objects),native_completion_edges_observed=len(self.completed),
            fully_paid_queue_observations=sum(cost==paid for cost,paid in self.new_queues.values()),
            additional_queue_observations_after_window=len(self.late_queues),
            available_producer_count=len(self.eligible),positive_native_build_state_observed=self.positive,
            policy_released=self.policy_released,release_reason=self.release_reason,
            builder_frame=self.frames[0],own_census_frame=self.frames[1],
            count_control_basis='new_native_queue_acceptances',overall_production_permitted=None,
            cost_observation_semantics='last_observed_fields_per_queue_not_total_cash_outflow',
            resource_reservation_verified=False,budget_hard_cap_verified=False,
            exact_queue_to_object_link_verified=False,payment_verified=False,unit_exit_verified=False,
            technology_unlock_verified=False,exclusive_macro_attribution_verified=False,
            automatic_retry_allowed=False,unit_operation_policy='native_ai')


def compact_expansion_feedback(value,game_seconds):
    counts=('additional_count_requested','observed_new_queue_count','new_own_target_observations',
        'native_completion_edges_observed','fully_paid_queue_observations','additional_queue_observations_after_window',
        'available_producer_count')
    flags=('positive_native_build_state_observed','policy_released')
    frames=('builder_frame','own_census_frame')
    amounts=('observed_queue_cost_sum','observed_paid_field_sum')
    if (type(value) is not dict or value.get('source')!='native_macro_expansion_observation'
            or value.get('action') not in EXTRA_ACTIONS or value.get('domain')!=TARGETS[value['action']][2]
            or value.get('status') not in ('native_queue_observed','native_producer_unavailable','native_expansion_pending')
            or value.get('release_reason') not in (None,'queue_target_observed','producer_unavailable','prerequisite_changed','expired','stopped')
            or value.get('additional_count_requested')!=1 or type(value.get('additional_count_requested')) is not int
            or any(type(value.get(key)) is not int or not 0<=value[key]<=100000 for key in counts)
            or any(type(value.get(key)) is not bool for key in flags)
            or any(type(value.get(key)) is not int or not 0<=value[key]<=0xffffffffffffffff for key in amounts)
            or value['observed_paid_field_sum']>value['observed_queue_cost_sum']
            or any(type(value.get(key)) is not int or not 0<value[key]<=0xffffffff
                   or not -15<=game_seconds*15-value[key]<=30 for key in frames)):
        raise ContractError('macro_expansion_feedback_invalid_or_stale')
    result={**{key:value[key] for key in ('source','action','domain','status','release_reason',*counts,*flags,*frames,*amounts)},
        'count_control_basis':'new_native_queue_acceptances','overall_production_permitted':None,
        'cost_observation_semantics':'last_observed_fields_per_queue_not_total_cash_outflow',
        'resource_reservation_verified':False,'budget_hard_cap_verified':False,
        'exact_queue_to_object_link_verified':False,'payment_verified':False,'unit_exit_verified':False,
        'technology_unlock_verified':False,'exclusive_macro_attribution_verified':False,
        'automatic_retry_allowed':False,'unit_operation_policy':'native_ai'}
    if 'resource_reservation' in value:
        result['resource_reservation']=compact_reservation(value['resource_reservation'])
        result['resource_reservation_verified']=True
    return result
