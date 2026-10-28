"""Pointer-free x86 native channel layout. Importing never attaches to a game."""
import ctypes as c
import struct
import uuid

U = c.c_uint32
I = c.c_int32
Q = c.c_uint64
F = c.c_float
ID = U * 4
DIGEST = U * 8
MAGIC = 0x54524331
VERSION = 1
CAPACITY = 2048
TRACE_CAPACITY = 4096


class Point(c.Structure):
    _fields_ = [(name, F) for name in ('x', 'y', 'z')]


class Binding(c.Structure):
    _fields_ = [('session', ID), ('commander', ID), ('host', ID), ('binding_hash', DIGEST),
                ('player', U), ('pid', U), ('thread', U), ('process_start', Q)]


class NativeBinding(c.Structure):
    _fields_ = [(name, U) for name in ('logic', 'owner', 'ai', 'personality', 'personality_id', 'player_template', 'default_team', 'script_team')]


class Actor(c.Structure):
    _fields_ = [(name, U) for name in ('object_id', 'thing', 'template_ptr', 'update', 'owner', 'type_hash', 'born_frame')] + [('generation', Q)]


class Command(c.Structure):
    _fields_ = [('command', ID), ('task', ID), ('lease', ID), ('sequence', Q), ('operation', U),
                ('actor', Actor), ('target', Point), ('expires_frame', U), ('lease_deadline_frame', U),
                ('hold_frames', U), ('expires_monotonic_ms', Q)]


class Sample(c.Structure):
    _fields_ = [('binding', Binding), ('actor', Actor)] + [(name, U) for name in
                ('frame', 'current_thread', 'team', 'default_team', 'script_team', 'stance', 'foreign_epoch',
                 'state_id', 'state_vtable', 'path', 'command_source', 'state_flags')] + [
                ('monotonic_ms', Q), ('xyz', Point)] + [(name, c.c_bool) for name in
                ('identity', 'actor_birth_verified', 'live_list_member', 'grounded', 'paused', 'settled',
                 'normal_move_owned', 'interference_guard_ready')]


class ProducerReference(c.Structure):
    _fields_ = [('command', ID), ('task', ID), ('sequence', U), ('receipt_index', U)]


class Bootstrap(c.Structure):
    _fields_ = [('binding', Binding), ('native', NativeBinding), ('actor', Actor),
                ('producer', ProducerReference), ('persisted_sequence', Q), ('experimental_flags', U)]


class WireReceipt(c.Structure):
    _fields_ = [('command', ID), ('task', ID), ('lease', ID), ('sequence', Q), ('monotonic_ms', Q)] + [
                (name, U) for name in ('phase', 'frame', 'accepted', 'physical_home', 'control_released', 'stance_restored', 'held')] + [
                ('sdk_calls', U * 6), ('reason', c.c_char * 96)]


class WireEvent(c.Structure):
    _fields_ = [('ticket', I), ('kind', U), ('event_type', c.c_char * 48),
                ('receipt', WireReceipt), ('observation', Sample)]


class HookTrace(c.Structure):
    _fields_ = [(name, U) for name in ('frame', 'thread', 'kind', 'self', 'target', 'caller', 'operation', 'scope', 'source',
                                      'epoch_before', 'epoch_after', 'word_count')] + [('words', U * 24)]


class WireHookTrace(c.Structure):
    _fields_ = [('ticket', I), ('trace', HookTrace)]


class SharedChannel(c.Structure):
    _fields_ = [(name, U) for name in ('magic_word', 'protocol', 'structure_size', 'token')] + [
                ('bootstrap', Bootstrap)] + [(name, I) for name in
                ('state', 'stop_requested', 'active_callbacks', 'callback_thread', 'pulse_requested', 'pulse_acknowledged',
                 'command_generation', 'command_acknowledged')] + [('command', Command), ('command_receipt_generation', I),
                ('command_receipt', WireReceipt), ('receipt_generation', I), ('receipt', WireReceipt),
                ('events_written', I), ('events_overwritten', I), ('hooks_restored', U), ('reason', c.c_char * 96),
                ('admitted_actor', Actor), ('native_last_sequence', Q), ('observation_generation', I),
                ('current_observation', Sample), ('targets_generation', I), ('targets_count', U),
                ('approved_targets', Point * 64), ('events', WireEvent * CAPACITY),
                ('traces_written', I), ('traces_overwritten', I), ('traces', WireHookTrace * TRACE_CAPACITY)]


def inventory():
    return dict(schema_version=1, protocol=VERSION, shared=c.sizeof(SharedChannel), bootstrap=c.sizeof(Bootstrap),
                command=c.sizeof(Command), wire_receipt=c.sizeof(WireReceipt), event=c.sizeof(WireEvent),
                command_offset=SharedChannel.command.offset, receipt_offset=SharedChannel.receipt.offset,
                events_offset=SharedChannel.events.offset, hook_trace=c.sizeof(WireHookTrace),
                trace_capacity=TRACE_CAPACITY, traces_offset=SharedChannel.traces.offset)


def uuid_words(value):
    parsed = uuid.UUID(value)
    if str(parsed) != value or not parsed.int:
        raise ValueError('runtime_uuid_invalid')
    return struct.unpack('<4I', parsed.bytes)


def uuid_text(words):
    return str(uuid.UUID(bytes=struct.pack('<4I', *words)))


def digest_words(value):
    if not isinstance(value, str) or len(value) != 64 or value.lower() != value:
        raise ValueError('runtime_digest_invalid')
    try:
        return struct.unpack('<8I', bytes.fromhex(value))
    except (ValueError, struct.error):
        raise ValueError('runtime_digest_invalid') from None
