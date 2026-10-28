"""Rank already admitted endpoints using this actor's observed native egress.

The trajectory is a diagnostic preparation hint, never endpoint/route authority.
All commands still use the current native registry and game-thread admission.
"""
import math
import struct


def native_cell(point):
    f32=lambda value:struct.unpack('<f',struct.pack('<f',value))[0]
    return tuple(math.trunc(f32(value*f32(.05))) for value in point[:2])


def segment_distance(point,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    size=dx*dx+dy*dy
    amount=max(0.,min(1.,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/size)) if size else 0.
    return math.hypot(point[0]-a[0]-amount*dx,point[1]-a[1]-amount*dy)


def select_egress_target(runtime,binding,record,actor,initial):
    state=runtime.poll();native=runtime.observe_actor(binding)
    if state['phase']!='ready' or not native['settled'] or native['team']!=native['script_team']:
        raise ValueError('egress_intercept_requires_current_native_ready')
    home=record['post_ready_target_selection']['reserve_home']['xyz']
    points=runtime.targets();history=[];factory=None
    for sample in record.get('own_environment',{}).get('samples',[]):
        if sample['stage']!='selecting_before_borrow':continue
        census=sample['census'];frame=census['frame_start']
        if frame!=census['frame_end']:continue
        for row in census['candidates']:
            if row['type_hash']=='0x80d4ea1e':factory=row['xyz']
            if row['object_id']!=actor.object_id:continue
            if (int(row['address'],0)!=actor.thing or int(row['ai_address'],0)!=actor.update
                    or int(row['owner_address'],0)!=actor.owner or int(row['type_hash'],0)!=actor.type_hash):
                raise ValueError('egress_intercept_history_identity_changed')
            xyz=row['xyz']
            if not all(math.isfinite(v) for v in xyz) or abs(xyz[2]-home[2])>2:continue
            if not history or frame!=history[-1]['frame']:history.append(dict(frame=frame,xyz=xyz))
    history_source='own_environment_same_actor_census'
    # HomeWindow retains independent same-actor observations every planning
    # frame; the wider census recorder intentionally samples only every5.
    # Use actual observed cells, rather than a10-unit circle around a sparse
    # trajectory: a20-unit native cell also includes its diagonal corners.
    home_history=[]
    for row in record.get('preborrow_home_wait',{}).get('observations',[]):
        xyz=row['actor_xyz']
        if (row['frame_start']==row['frame_end'] and all(math.isfinite(v) for v in xyz)
                and abs(xyz[2]-home[2])<=2):
            home_history.append(dict(frame=row['frame_start'],xyz=xyz))
    if home_history:
        history=home_history;history_source='strict_same_actor_home_window_independent_observations'
    if (not history or factory is None or max(math.dist(x['xyz'][:2],home[:2]) for x in history)<30):
        raise ValueError('egress_intercept_observed_ingress_missing_no_commit')
    segments=[(a['xyz'],b['xyz']) for a,b in zip(history,history[1:])
              if 0<b['frame']-a['frame']<=10 and math.dist(a['xyz'][:2],b['xyz'][:2])<=30]
    observed_cells={native_cell(x['xyz']) for x in history}
    candidates=[];considered=[]
    for row in record['post_ready_target_selection']['candidates']:
        key=row['point_id'];point=points.get(key)
        if point is None or tuple(point)!=tuple(row['xyz']):continue
        if (not 30<=math.dist(point[:2],native['xyz'][:2])<=120
                or not 20<=math.dist(point[:2],home[:2])<=120
                or abs(point[2]-native['xyz'][2])>2 or abs(point[2]-home[2])>2):continue
        cross=min([math.dist(point[:2],x['xyz'][:2]) for x in history]
                  +[segment_distance(point,a,b) for a,b in segments])
        cell=native_cell(point);matched=cell in observed_cells
        candidate=dict(point_id=key,xyz=list(point),cross_track_distance=cross,center_cell=list(cell),
            observed_cell_match=matched,distance_to_factory=math.dist(point[:2],factory[:2]),
            distance_to_home=math.dist(point[:2],home[:2]))
        considered.append(candidate)
        if matched:candidates.append(candidate)
    record['egress_intercept_selection']=dict(initial_point_id=initial,native_frame=native['frame'],
        source_actor_id=actor.object_id,history_source=history_source,history=history,
        maximum_frame_gap=10,maximum_segment_length=30,required_observed_native_cell=True,
        native_xy_scale_bits='0x3d4ccccd',observed_center_cells=[list(c) for c in sorted(observed_cells)],
        considered=considered,candidates=candidates,planning_status='refused_no_observed_cell_match',
        history_is_route_authority=False,ordinary_execution_granted=False)
    if not candidates:raise ValueError('egress_intercept_no_supported_native_point_no_commit')
    selected=min(candidates,key=lambda x:(x['cross_track_distance'],x['distance_to_factory'],x['distance_to_home'],x['point_id']))
    record['egress_intercept_selection'].update(selected_point_id=selected['point_id'],
        selected_xyz=selected['xyz'],planning_status='selected_current_native_endpoint_in_observed_cell')
    record['post_ready_target_selection'].update(initial_selected_point_id=initial,
        selected_point_id=selected['point_id'],selection_reason='observed_native_egress_preparation_hint')
    return selected['point_id']
