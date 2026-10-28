"""Bounded, read-only own-player context for controlled runtime experiments.

This inventory is diagnostic context, never route, clearance, or command authority.
Frame ranges are retained: a process read is not an atomic simulation snapshot.
"""
from __future__ import annotations

import time

from live_state import own_candidates


class OwnEnvironmentRecorder:
    def __init__(self, memory, player_id, catalog, actor_id, record, *, capacity=512, frame_step=5):
        self.memory, self.player_id, self.catalog = memory, player_id, catalog
        self.actor_id, self.record = actor_id, record
        self.capacity, self.frame_step = capacity, frame_step
        self.last_frame = None
        self.last_stage = None
        self.disabled = False
        record['own_environment'] = dict(
            source='independent_read_only_native_live_list_own_only',
            route_or_clearance_verified=False, atomic_snapshot=False,
            sample_capacity=capacity, minimum_frame_step=frame_step,
            samples=[], incomplete=False)

    def capture(self, stage, target=None):
        context = self.record['own_environment']
        if self.disabled:
            return
        if len(context['samples']) >= self.capacity:
            context.update(incomplete=True, reason='sample_capacity_reached')
            self.disabled = True
            return
        try:
            logic = self.memory.u32(0xcd8ce4)
            frame = self.memory.u32(logic + 0x50)
            if self.last_frame is not None:
                if frame < self.last_frame:
                    raise ValueError('own_environment_frame_regressed')
                if stage == self.last_stage and frame - self.last_frame < self.frame_step:
                    return
            census = own_candidates(self.memory, self.player_id, self.catalog)
            # Only decode the already verified Conscript update layout. Other
            # classes remain position/type records, without guessed AI fields.
            for row in census['candidates']:
                if row['type_hash'] != '0x19ab11af':
                    continue
                thing, update = int(row['address'], 0), int(row['ai_address'], 0)
                if (self.memory.u32(thing + 0xdc) != row['object_id']
                        or self.memory.u32(thing + 0x418) != int(row['owner_address'], 0)
                        or self.memory.u32(thing + 0x374) != update
                        or self.memory.u32(update) != 0xc48670
                        or self.memory.u32(update + 8) != thing):
                    raise ValueError('own_environment_actor_changed')
                machine = self.memory.u32(update + 0x3c)
                state = self.memory.u32(machine + 4)
                row['conscript_state_raw'] = dict(
                    state_id=self.memory.u32(state + 4), state_vtable=hex(self.memory.u32(state)),
                    path=hex(self.memory.u32(update + 0x150)),
                    command_source=self.memory.u32(update + 0x50),
                    state_flags=hex(self.memory.u32(machine + 0x78)),
                    team=hex(self.memory.u32(thing + 0x414)))
            end = self.memory.u32(logic + 0x50)
            if self.memory.u32(0xcd8ce4) != logic or end < census['frame_end'] or census['frame_start'] < frame:
                raise ValueError('own_environment_lifecycle_changed')
            context['samples'].append(dict(stage=stage, monotonic_ns=time.monotonic_ns(),
                frame_start=frame, frame_end=end, target_xyz=target,
                actor_found=any(row['object_id'] == self.actor_id for row in census['candidates']),
                census=census))
            self.last_frame, self.last_stage = end, stage
        except Exception as error:
            # A diagnostic read cannot authorize, retry, or suppress a command,
            # and must not prevent the driver's separate native safety cleanup.
            context.update(incomplete=True, reason=type(error).__name__, detail=str(error))
            self.disabled = True
