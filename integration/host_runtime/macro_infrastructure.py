"""Bounded own-infrastructure facts; presence and queue fields are not completion."""
import math

from .contracts import ContractError
from .macro_production_feedback import read_sample

TEMPLATES={
    'construction_yard':'0xc16ff13f','barracks':'0x80d4ea1e','war_factory':'0xd50c222e',
    'refinery':'0xc45aaeab','super_reactor':'0x524bbd01','battle_lab':'0xb7377639',
}
QUEUE_TARGETS=('refinery','super_reactor','battle_lab')


def observe_infrastructure(builder,census):
    at,objects,eligible,_=read_sample(builder,census,TEMPLATES['super_reactor'],TEMPLATES['construction_yard'])
    if len(objects)>8192:raise ContractError('macro_infrastructure_bounds')
    counts={name:0 for name in TEMPLATES}
    for row in census['own_objects']:
        if row['type_hash'] not in TEMPLATES.values():continue
        hp=row.get('hp')
        if type(hp) not in (float,int) or not math.isfinite(hp) or hp<=0:
            raise ContractError('macro_infrastructure_own_hp')
        name=next(name for name,template in TEMPLATES.items() if template==row['type_hash'])
        counts[name]+=1
    queues={}
    for name in QUEUE_TARGETS:
        _,_,_,current=read_sample(builder,census,TEMPLATES[name],TEMPLATES['construction_yard'])
        queues[name]=dict(observed_queue_count=len(current),observed_cost_sum=sum(v[0] for v in current.values()),
            observed_paid_field_sum=sum(v[1] for v in current.values()),fully_paid_queue_count=sum(v[0]==v[1] for v in current.values()))
    return dict(source='bound_own_infrastructure_observation',builder_frame=at[0],own_census_frame=at[1],
        own_template_presence_counts=counts,available_construction_yards=len(eligible),construction_queues=queues,
        presence_includes_unfinished_foundations=True,completed_technology_verified=False,
        exact_queue_to_object_link_verified=False,payment_verified=False,grants_capability=False,
        own_perspective=True,enemy_details_read=False,coverage='named_soviet_templates_only')


def compact_infrastructure(value,game_seconds):
    """Strict projection also checks age at the provider boundary."""
    def count(number,maximum=8192):
        if type(number) is not int or not 0<=number<=maximum:raise ContractError('macro_infrastructure_count')
        return number
    if (value.get('source')!='bound_own_infrastructure_observation' or value.get('own_perspective') is not True
            or value.get('enemy_details_read') is not False):raise ContractError('macro_infrastructure_source')
    frames=[value.get(key) for key in ('builder_frame','own_census_frame')]
    if (type(game_seconds) not in (int,float) or not math.isfinite(game_seconds)
            or any(type(frame) is not int or not 0<frame<=0xffffffff
                or not -15<=game_seconds*15-frame<=30 for frame in frames)
            or abs(frames[0]-frames[1])>15):raise ContractError('macro_infrastructure_stale')
    counts=value.get('own_template_presence_counts');queues=value.get('construction_queues')
    if type(counts) is not dict or set(counts)!=set(TEMPLATES) or type(queues) is not dict or set(queues)!=set(QUEUE_TARGETS):
        raise ContractError('macro_infrastructure_shape')
    result={key:value[key] for key in ('source','builder_frame','own_census_frame')}
    result.update(own_template_presence_counts={name:count(counts[name]) for name in TEMPLATES},
        available_construction_yards=count(value.get('available_construction_yards')),construction_queues={})
    for name in QUEUE_TARGETS:
        row=queues[name]
        if type(row) is not dict:raise ContractError('macro_infrastructure_shape')
        fields={key:count(row.get(key),0xffffffff if key.endswith('_sum') else 8192)
            for key in ('observed_queue_count','observed_cost_sum','observed_paid_field_sum','fully_paid_queue_count')}
        if fields['observed_paid_field_sum']>fields['observed_cost_sum'] or fields['fully_paid_queue_count']>fields['observed_queue_count']:
            raise ContractError('macro_infrastructure_queue')
        result['construction_queues'][name]=fields
    result.update(presence_includes_unfinished_foundations=True,completed_technology_verified=False,
        exact_queue_to_object_link_verified=False,payment_verified=False,grants_capability=False,
        own_perspective=True,enemy_details_read=False,coverage='named_soviet_templates_only')
    return result
