"""Pure functional check: being hidden does not establish remembered movement."""
import math


def point(value):
    return (isinstance(value, (list, tuple)) and len(value) == 3 and
            all(type(x) in (int, float) and math.isfinite(x) for x in value))


def qualify(report):
    intervals = []
    block = None
    def finish(value,reacquired=None):
        displacement=math.dist(value['first'][:2],value['last'][:2])
        moved=value['samples']>=3 and displacement>=120
        intervals.append(dict(first_hidden_frame=value['first_frame'],
            last_hidden_frame=value['last_frame'],reacquired_frame=reacquired,
            last_seen_frame=value['key'][0],distinct_hidden_frames=value['samples'],
            displacement=displacement,movement_observed=moved,
            verified=moved and reacquired is not None))
    for event in report.get('events', []):
        if event.get('kind') != 3:
            continue
        frame = event.get('frame')
        seen = event.get('target_last_seen_frame')
        target = event.get('remembered_target_xyz')
        xyz = [event.get(key) for key in ('x', 'y', 'z')]
        valid = (event.get('mission_stage') == 2 and
                 type(frame) is int and type(seen) is int and
                 type(event.get('current_visible')) is int and
                 0 < seen <= frame <= seen + 900 and point(target) and point(xyz))
        if valid and event.get('current_visible') == 0:
            key = (seen, tuple(target))
            if block is None or block['key'] != key:
                if block is not None:finish(block)
                block = dict(key=key, first_frame=frame, last_frame=frame,
                             first=xyz, last=xyz, samples=1)
            elif frame > block['last_frame']:
                block.update(last_frame=frame, last=xyz, samples=block['samples']+1)
            continue
        if (block is not None and valid and event.get('current_visible') == 1
                and frame >= block['last_frame'] and seen == frame):
            finish(block,frame)
        elif block is not None:finish(block)
        block = None
    if block is not None:finish(block)
    return dict(hidden_approach_verified=any(x['verified'] for x in intervals),
                hidden_movement_observed=any(x['movement_observed'] for x in intervals),
                maximum_hidden_displacement=max((x['displacement'] for x in intervals), default=0),
                hidden_intervals=intervals,
                reacquired_intervals=[x for x in intervals if x['reacquired_frame'] is not None], required_displacement=120,
                scope='Own displacement during frozen remembered navigation; '
                      'effect and retreat require separate raw qualification')
