"""Bounded read-only planning wait before any Reserve/lease/native action.

An observed clear window only stops the planner from requesting a known-bad
home. The native game-thread admission still decides whether to Borrow. No
rejection, unknown action, or expired lease is retried here.
"""
from __future__ import annotations

import math
import time

from live_state import own_candidates


class PlanningUnavailable(ValueError):
    """The bounded planning window ended before any Reserve was requested."""


class HomeWindow:
    def __init__(self, memory, player_id, actor):
        self.memory, self.player_id, self.actor = memory, player_id, actor
        self.last_frame = None
        self.clear_frames = 0

    def begin(self, record, *, require_stationary=False):
        self.last_frame, self.clear_frames = None, 0
        self.previous_xyz, self.require_stationary = None, require_stationary
        self.record = record['preborrow_home_wait'] = dict(
            source='independent_own_live_list_planning_filter',
            required_distinct_clear_frames=3, center_clearance=20,
            require_stationary_position=require_stationary,
            native_authority_granted=False, route_verified=False, observations=[])

    def observe(self, native):
        census = own_candidates(self.memory, self.player_id, {})
        frame, end = census['frame_start'], census['frame_end']
        actor = self.actor
        own = next((row for row in census['candidates'] if row['object_id'] == actor.object_id), None)
        if (own is None or int(own['address'], 0) != actor.thing
                or int(own['owner_address'], 0) != actor.owner
                or int(own['ai_address'], 0) != actor.update
                or int(own['type_hash'], 0) != actor.type_hash
                or native['object_id'] != actor.object_id or native['generation'] != actor.generation
                or native['team'] == native['script_team']):
            self.record['refused_identity_observation'] = dict(
                frame_start=frame, frame_end=end, own_actor=own, native_actor=native,
                expected_actor={name:getattr(actor,name) for name in
                    ('object_id','thing','owner','update','type_hash','generation')})
            raise ValueError('preborrow_actor_identity_or_owner_changed')
        if self.last_frame is not None and frame < self.last_frame:
            raise ValueError('preborrow_frame_regressed')
        # The channel and the independent process read have distinct clocks.
        # A moving actor can legitimately travel between their frames. Use the
        # complete same-frame own inventory for this *planning* vacancy check;
        # the native game-thread gate rechecks its actual home before Borrow.
        aligned = frame == end and native['frame'] <= frame <= native['frame'] + 2
        blockers = [dict(object_id=row['object_id'], type_hash=row['type_hash'], xyz=row['xyz'],
                         distance_xy=math.dist(own['xyz'][:2], row['xyz'][:2]))
                    for row in census['candidates'] if row['object_id'] != actor.object_id
                    and math.dist(own['xyz'][:2], row['xyz'][:2]) < 20
                    and abs(own['xyz'][2] - row['xyz'][2]) <= 2]
        position_lag=math.dist(own['xyz'][:2],native['xyz'][:2])
        stationary=(not self.require_stationary or (native.get('path')==0
            and type(native.get('state_flags')) is int and not native['state_flags']&0xffff
            and native.get('grounded') is True and position_lag<=1
            and (self.previous_xyz is None or tuple(own['xyz'])==self.previous_xyz)))
        lender_idle=(not self.require_stationary or (native.get('command_source')==2
            and native.get('state_id')==16 and native.get('state_vtable')==0xc55130
            and native.get('stance')==0 and native.get('foreign_epoch')==0))
        if not aligned or blockers or not stationary or not lender_idle:
            self.clear_frames = 0
        elif frame != self.last_frame:
            continuous = self.last_frame is not None and frame - self.last_frame <= 10
            self.clear_frames = min(3, self.clear_frames + 1) if continuous else 1
        ready = aligned and not blockers and stationary and lender_idle and self.clear_frames >= 3
        reason = ('home_read_cross_frame_wait' if not aligned else 'home_occupied_wait' if blockers
                  else 'home_not_stationary_wait' if not stationary
                  else 'home_lender_state_unverified_wait' if not lender_idle
                  else 'home_window_observed_native_check_still_required' if ready else 'home_clear_window_wait')
        observation = dict(frame_start=frame, frame_end=end, native_frame=native['frame'],
                           actor_xyz=own['xyz'], native_actor_xyz=native['xyz'],
                           position_lag_xy=position_lag, stationary_position=stationary,
                           native_lender_idle_candidate=lender_idle,
                           native_command_source=native.get('command_source'),
                           native_state_id=native.get('state_id'),native_foreign_epoch=native.get('foreign_epoch'),
                           native_state_vtable=native.get('state_vtable'),native_state_flags=native.get('state_flags'),
                           native_stance=native.get('stance'),native_path=native.get('path'),
                           native_grounded=native.get('grounded'),native_team=native.get('team'),
                           blockers=blockers, distinct_clear_frames=self.clear_frames,
                           ready_for_native_check=ready, reason=reason)
        rows = self.record['observations']
        if not rows or (rows[-1]['frame_start'], rows[-1]['reason']) != (frame, reason):
            if len(rows) >= 1024:
                raise ValueError('preborrow_observation_capacity_exceeded')
            rows.append(observation)
        self.last_frame = frame
        self.previous_xyz=tuple(own['xyz']) if aligned and not blockers and stationary else None
        return ready


def choose_target(runtime, binding, record, home_window, observe_environment=None, *, home_first=False):
    if type(home_first) is not bool:
        raise ValueError('preparation_mode_must_be_explicit_bool')
    record['endpoint_wait_budget_seconds'] = 30
    record['preparation_mode'] = 'home_first_bounded_ready_wait' if home_first else 'joint_home_and_endpoint'
    observations = record.setdefault('endpoint_observations', [])
    home_window.begin(record,require_stationary=True)
    deadline = time.monotonic() + record['endpoint_wait_budget_seconds']
    while time.monotonic() < deadline:
        snapshot = runtime.admit(binding)
        state = runtime.poll()
        native = runtime.observe_actor(binding)
        points = runtime.targets()
        if observe_environment is not None:
            observe_environment('selecting_before_borrow')
        # The DLL publishes current_observation before controller.tick(). A
        # released event can therefore precede the next ambient sample, whose
        # same-frame team still reflects the old script owner. Require a newer
        # game-thread observation before the strict identity/home check; never
        # reinterpret the receipt sample as fresh planning state.
        if state.get('phase') == 'released':
            released_frame = state.get('game_frame')
            if type(released_frame) is not int:
                raise ValueError('preborrow_released_frame_unverified_no_commands')
            if native['frame'] <= released_frame:
                rows = record.setdefault('released_observation_wait', [])
                row = dict(native_frame=native['frame'], released_frame=released_frame,
                           native_team=native['team'], script_team=native['script_team'],
                           native_authority_granted=False)
                if not rows or rows[-1] != row:
                    if len(rows) >= 1024:
                        raise ValueError('preborrow_release_wait_capacity_exceeded')
                    rows.append(row)
                time.sleep(.05)
                continue
        home_ready = home_window.observe(native)
        current = native['xyz']
        eligible = [(math.dist(point[:2], current[:2]), key) for key, point in points.items()
                    if 30 <= math.dist(point[:2], current[:2]) <= 120 and abs(point[2] - current[2]) <= 2]
        if not observations or observations[-1]['frame'] != snapshot.game_frame:
            observations.append(dict(frame=snapshot.game_frame, monotonic_ms=snapshot.monotonic_ms,
                actor_xyz=current, native_points=len(points), eligible_points=len(eligible),
                home_ready_for_native_check=home_ready,
                candidates=[dict(point_id=key, xyz=points[key], distance_xy=distance) for distance, key in eligible]))
        if home_ready and (eligible or home_first):
            # Reserve remains a bounded preparation, never a Move. The native
            # home gate decides Borrow, and Ready selection still needs an
            # actually vacant native point within the unchanged return margin.
            return min(eligible)[1] if eligible else None
        time.sleep(.05)
    record['planning_outcome']=dict(status='not_dispatched',
        reason_code='preborrow_no_home_and_endpoint_window_no_commands',
        observations=len(observations),home_ready_frames=sum(row['home_ready_for_native_check'] for row in observations),
        endpoint_ready_frames=sum(row['eligible_points']>0 for row in observations),
        tactical_commands_dispatched=0,control_acquired=False,mission_effect_verified=False)
    raise PlanningUnavailable('preborrow_no_home_and_endpoint_window_no_commands')


def choose_commit_target(runtime, binding, record, task_id, lease_id, preliminary, observe_environment=None, *, wait_seconds=8):
    # Borrow/Hold/Stop can move an initially walking actor. The preliminary
    # candidate is not a committed intent and must not survive as stale input.
    home = runtime.reserved_home(task_id, lease_id)
    lease_deadline = getattr(runtime, 'lease_deadline_frame', None)
    if type(lease_deadline) is not int or not 0 < wait_seconds <= 8:
        raise ValueError('post_ready_wait_lease_or_budget_invalid')
    selection = record['post_ready_target_selection'] = dict(reserve_home=home,
        preliminary_point_id=preliminary, selected_point_id=None, changed=False,
        lease_deadline_frame=lease_deadline, wait_budget_seconds=wait_seconds,
        wait_budget_frames=120, return_reserve_frames=120, observations=[])
    deadline, frame_deadline = time.monotonic() + wait_seconds, None
    while True:
        state = runtime.poll()
        native = runtime.observe_actor(binding)
        if (state['phase'] != 'ready' or not native['settled'] or native['stance'] != 2
                or native['team'] != native['script_team']):
            raise ValueError('post_ready_target_requires_current_native_ready')
        if frame_deadline is None:
            frame_deadline = min(native['frame'] + 120, lease_deadline - 120)
            selection['wait_deadline_frame'] = frame_deadline
        if native['frame'] >= frame_deadline or time.monotonic() >= deadline:
            raise ValueError('post_ready_no_native_endpoint_no_commit')
        points = runtime.targets()
        eligible = [(math.dist(native['xyz'][:2], point[:2]), key) for key, point in points.items()
                    if 20 <= math.dist(home['xyz'][:2], point[:2]) <= 120
                    and 30 <= math.dist(native['xyz'][:2], point[:2]) <= 120
                    and abs(point[2] - home['xyz'][2]) <= 2 and abs(point[2] - native['xyz'][2]) <= 2]
        selected = preliminary if any(key == preliminary for _, key in eligible) else min(eligible)[1] if eligible else None
        observation = dict(frame=native['frame'], ready_xyz=native['xyz'], selected_point_id=selected,
            native_points=[dict(point_id=key, xyz=point) for key, point in points.items()],
            candidates=[dict(point_id=key, xyz=points[key], distance_from_ready=distance,
                             distance_from_home=math.dist(home['xyz'][:2], points[key][:2])) for distance, key in eligible])
        rows = selection['observations']
        if not rows or rows[-1] != observation:
            if len(rows) >= 256:
                raise ValueError('post_ready_wait_observation_capacity_exceeded')
            rows.append(observation)
        selection.update(frame=native['frame'], selected_point_id=selected, changed=selected != preliminary,
                         candidates=observation['candidates'])
        if observe_environment is not None:
            observe_environment('waiting_commit_endpoint', points[selected] if selected else None)
        if selected is not None:
            return selected
        time.sleep(.05)
