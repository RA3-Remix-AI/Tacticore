"""Model-visible local maneuver intent; observations confer no execution grant."""
from dataclasses import asdict, dataclass
import uuid
from battlefield import keys, integer, number, fail

PREPARATION_STATES=frozenset({'waiting_paid_unit','waiting_native_readiness','available','active','retired_waiting_paid_unit','waiting_production_barrier'})
PREPARATION_REASONS=frozenset({'completed_paid_unit_required','native_readiness_required','safe_opportunity_available',
    'local_task_in_progress','readiness_wait_elapsed','native_channel_budget','production_or_control_barrier'})

@dataclass(frozen=True)
class RuntimePreparation:
    state: str
    reason_code: str
    paid_units_available: int

    @classmethod
    def from_dict(cls,raw):
        d=keys(raw,{'state','reason_code','paid_units_available'},'runtime_preparation_fields')
        if (not isinstance(d['state'],str) or not isinstance(d['reason_code'],str)
                or d['state'] not in PREPARATION_STATES or d['reason_code'] not in PREPARATION_REASONS):fail('runtime_preparation_state')
        return cls(d['state'],d['reason_code'],integer(d['paid_units_available'],0,1024,'runtime_preparation_paid_count'))

    def public(self):return asdict(self)


def opaque(value):
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:raise ValueError()
    except (ValueError, AttributeError):fail('runtime_task_id')
    return value


@dataclass(frozen=True)
class RuntimeOpportunity:
    opportunity_id: str
    targets: tuple
    max_hold_frames: int

    @classmethod
    def from_dict(cls, raw):
        d=keys(raw, {'opportunity_id','targets','max_hold_frames'}, 'runtime_opportunity_fields')
        targets=d['targets']
        if not isinstance(targets,list) or not 1<=len(targets)<=8:fail('runtime_opportunity_targets')
        rows=[]
        for target in targets:
            t=keys(target,{'target_point_id','bearing_degrees','distance_units'},'runtime_target_fields')
            rows.append((opaque(t['target_point_id']),number(t['bearing_degrees'],0,360,'runtime_target_bearing'),number(t['distance_units'],30,120,'runtime_target_distance')))
        if len({t[0]for t in rows})!=len(rows):fail('runtime_opportunity_targets')
        return cls(opaque(d['opportunity_id']),tuple(rows),integer(d['max_hold_frames'],0,450,'runtime_hold_frames'))

    def public(self):
        return dict(opportunity_id=self.opportunity_id,max_hold_frames=self.max_hold_frames,
            targets=[dict(target_point_id=p,bearing_degrees=b,distance_units=d)for p,b,d in self.targets])


@dataclass(frozen=True)
class RuntimeIntent:
    opportunity_id: str
    purpose: str
    target_point_id: str
    hold_frames: int

    def public(self):return asdict(self)


def validate_runtime_intent(raw, request, latest):
    if raw is None:return None
    d=keys(raw,{'opportunity_id','purpose','target_point_id','hold_frames'},'runtime_task_fields')
    if d['purpose']!='move_hold_return':fail('runtime_task_purpose')
    opportunity=opaque(d['opportunity_id']);point=opaque(d['target_point_id'])
    hold=integer(d['hold_frames'],0,450,'runtime_hold_frames')
    for snapshot in (request,latest):
        observed=snapshot.runtime_opportunity
        if (snapshot.paused or observed is None or observed.opportunity_id!=opportunity
                or point not in {t[0]for t in observed.targets} or hold>observed.max_hold_frames):
            fail('runtime_task_opportunity_stale')
    return RuntimeIntent(opportunity,d['purpose'],point,hold)
