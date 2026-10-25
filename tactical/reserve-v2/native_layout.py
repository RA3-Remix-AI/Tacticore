"""Exact RSV2 shared.h layout; import does not open a game or controller."""
import ctypes as c

U=c.c_uint32
L=c.c_int32

class Sample(c.Structure):
 _fields_=[(x,U) for x in 'frame thing id type_hash owner template_ptr update update_vtable update_backref team stance_module stance_vtable stance_backref stance_data stance stance_enum_list stance_enum_count'.split()]+[('stance_enum_entries',U*8)]+[(x,U) for x in 'sm sm_owner sm_flags state state_id state_vtable state_owner_sm path source child_sm child_sm_vtable child_state child_state_id child_state_vtable child_state_owner_sm holder'.split()]+[('status_words',U*7),('height_flags',U),('height',c.c_float),('hp',c.c_float),('xyz',c.c_float*3)]+[(x,U) for x in 'auto_acquire auto_acquire_flags_9e auto_acquire_24 auto_acquire_28 auto_acquire_2c auto_acquire_70'.split()]

class MoveProof(c.Structure):
 _fields_=[('goal_pointer',U),('goal_bits',U*3)]+[(x,U) for x in 'path limit_bits intent_seq facade_seq generation flags'.split()]

class RallyState(c.Structure):
 _fields_=[(x,U) for x in 'factory_address factory_id factory_owner factory_template factory_type_hash factory_source_frame factory_x_bits factory_y_bits'.split()]+[('proposal_origin',c.c_float*3),('proposal_direction',c.c_float*2),('goal',c.c_float*3)]+[(x,U) for x in 'proposal_frame arrival_samples last_arrival_frame rally_issue_frame rally_reached_frame rally_stop_verified rally_stop_frame move_intents move_facade_entries move_private_entries foreign_move_entries move_scope_open move_generation move_intent_seq'.split()]

class Event(c.Structure):
 _fields_=[(x,U) for x in 'seq kind tag frame tick thread caller self arg source result stage sdk_calls error explicit_stops private_explicit_stops automatic_stop2 private_automatic_stop2'.split()]+[('sample',Sample),('move',MoveProof)]

class Probe(c.Structure):
 _fields_=[(x,U) for x in 'magic version pid thread start_low start_high'.split()]+[(x,U*4) for x in ('session','commander','command','task')]+[(x,U) for x in 'token seq logic owner ai personality personality_id player_template thing object_id type_hash template_ptr update stance_module original_team script_team default_team observed_frame threat_frame threat_clear expires_frame test_stance'.split()]+[(x,L) for x in 'phase stop_requested active count'.split()]+[(x,U) for x in 'error restore_mask callback_thread stage issued_frame returned_frame sdk_calls detach_calls return_calls return_verified stance_calls explicit_stops private_explicit_stops automatic_stop2 private_automatic_stop2 private_stop_frame original_stance stance_changed stance_restored initial_stop_verified cleanup_stop_verified hold_verified hold_started hold_finished cleanup_started stable_samples last_sample_frame stop_issue_frame paused_samples overflow heartbeat_tick hold_samples hold_max_gap hold_missing_frames hold_first_frame hold_last_frame restore_before_enum restore_after_enum pool_before_enum pool_after_enum disposed scene_changed pulse_requested pulse_acknowledged'.split()]+[('stopped_xyz',c.c_float*3),('hold_anchor',c.c_float*3),('max_hold_drift',c.c_float),('initial_sample',Sample),('production_command',U*4),('production_task',U*4)]+[(x,U) for x in 'production_seq production_queue_id production_birth_frame production_paid'.split()]+[('production_receipt_sha256',U*8)]+[(x,U) for x in 'admission_samples admission_first_frame admission_last_frame admission_verified admission_max_gap'.split()]+[('admission_first_sample',Sample),('rally',RallyState),('events',Event*1024)]

class Header(c.Structure):
 _fields_=Probe._fields_[:-1]

def layout():
 return dict(sample=c.sizeof(Sample),event=c.sizeof(Event),tactical=c.sizeof(Probe),events=Probe.events.offset,period_ms=20,fallback_ms=100,loss_ms=1000)

assert layout()==dict(sample=240,event=352,tactical=361544,events=1096,period_ms=20,fallback_ms=100,loss_ms=1000)
