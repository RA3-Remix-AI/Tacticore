"""Pointer-free Windows x86 near channel2 layout. Importing never attaches."""
import ctypes as c
from tactical.runtime import layout as base

U,I,Q,F,ID=base.U,base.I,base.Q,base.F,base.ID
MAGIC=0x544e5232
VERSION=2
COMBAT_CAPACITY=512
CONTACT_CAPACITY=64


class NativeBootstrap(c.Structure):
    _fields_=[('schema',U),('original',base.Bootstrap),('mod_path',c.c_wchar*1024),
              ('visibility_path',c.c_wchar*1024),('template_audit_path',c.c_wchar*1024)]


class Intent(c.Structure):
    _fields_=[(n,ID)for n in ['command','task','lease','target_key']]+[('sequence',Q),('actor',base.Actor),
              ('expires_frame',U),('lease_deadline_frame',U),('expires_monotonic_ms',Q)]


class Target(c.Structure):
    _fields_=[('key',ID)]+[(n,U)for n in ['object_id','thing','template_ptr','update','owner','type_hash','observed_frame']]+[('incarnation',Q)]


class Weapon(c.Structure):
    _fields_=[(n,c.c_bool)for n in ['identity_verified','ready','ground_target_supported']]+[('ammo',U),('range',F)]


class TargetSample(c.Structure):
    _fields_=[('identity',Target),('xyz',base.Point),('hp',F),('visibility_frame',U),('visibility_monotonic_ms',Q)]+[
        (n,c.c_bool)for n in ['identity_verified','live','grounded','enemy','visible','visibility_complete']]


class Damage(c.Structure):
    _fields_=[('ticket',Q),('binding',base.Binding),('actor',base.Actor),('target',Target)]+[
        (n,ID)for n in ['attack_command','task','lease']]+[('source_object_id',U),('frame',U),('monotonic_ms',Q),
        ('shot_event_id',Q),('shot_monotonic_ms',Q),('weapon_instance',U),('shot_frame',U)]+[
        (n,F)for n in ['hp_before','hp_after','reported_damage']]+[('origin',U)]+[
        (n,c.c_bool)for n in ['identity_before','identity_after','visible_before','visible_after','source_verified','complete',
                             'shot_command_link_verified','shot_target_link_verified','damage_shot_link_verified']]


class Observation(c.Structure):
    _fields_=[('actor',base.Sample),('target',TargetSample),('actor_weapon',Weapon),('damage',Damage),
              ('damage_overwritten',U),('native_preemption',U)]


class Withdrawal(c.Structure):
    _fields_=[('binding',base.Binding),('actor',base.Actor),('task',ID),('lease',ID),('xyz',base.Point)]+[
        (n,U)for n in ['frame','original_deadline_frame','stance']]+[('monotonic_ms',Q)]+[
        (n,c.c_bool)for n in ['complete','released','control_released','stance_restored','held','physical_home']]


class ContactView(c.Structure):
    _fields_=[('key',ID),('type_hash',U),('frame',U),('monotonic_ms',Q),('xyz',base.Point),('hp',F)]


class NearCommand(c.Structure):
    _fields_=[('intent',Intent),('original_return',base.Command)]


class WireResult(c.Structure):
    _fields_=[(n,ID)for n in ['command','task','lease']]+[('sequence',Q),('monotonic_ms',Q)]+[
        (n,U)for n in ['phase','frame','attack_attempts','withdrawal_requests','accepted','attributed_hit','physical_home',
                      'control_released','stance_restored','held','cancelled','task_completed']]+[
        ('attributed_damage',F),('reason',c.c_char*96)]


class WireCombatEvent(c.Structure):
    _fields_=[('ticket',I),('withdrawal_present',U),('event_type',c.c_char*48),('result',WireResult),
              ('observation',Observation),('withdrawal',Withdrawal)]


class Shared(c.Structure):
    _fields_=[('movement',base.SharedChannel),('bootstrap',NativeBootstrap),('near_command_generation',I),
              ('near_command_acknowledged',I),('near_command',NearCommand),('near_command_receipt_generation',I),
              ('near_command_receipt',WireResult),('near_receipt_generation',I),('near_receipt',WireResult),
              ('contacts_generation',I),('contacts_count',U),('contacts',ContactView*CONTACT_CAPACITY),
              ('combat_written',I),('combat_overwritten',I),('combat',WireCombatEvent*COMBAT_CAPACITY)]


def inventory():
    if c.sizeof(c.c_wchar)!=2:
        raise ValueError('Channel2 requires the Windows UTF-16 wchar layout')
    return dict(schema_version=2,protocol=2,shared=c.sizeof(Shared),movement=c.sizeof(base.SharedChannel),
                bootstrap=c.sizeof(NativeBootstrap),near_command=c.sizeof(NearCommand),near_result=c.sizeof(WireResult),
                combat_event=c.sizeof(WireCombatEvent),contact_view=c.sizeof(ContactView),
                bootstrap_offset=Shared.bootstrap.offset,bootstrap_original_offset=NativeBootstrap.original.offset,
                near_command_generation_offset=Shared.near_command_generation.offset,near_command_offset=Shared.near_command.offset,
                near_command_receipt_offset=Shared.near_command_receipt.offset,near_receipt_offset=Shared.near_receipt.offset,
                contacts_offset=Shared.contacts.offset,combat_offset=Shared.combat.offset,
                combat_capacity=COMBAT_CAPACITY,contact_capacity=CONTACT_CAPACITY,
                observation=c.sizeof(Observation),target=c.sizeof(Target),weapon=c.sizeof(Weapon),damage=c.sizeof(Damage),
                withdrawal=c.sizeof(Withdrawal),observation_target_offset=Observation.target.offset,
                observation_weapon_offset=Observation.actor_weapon.offset,observation_damage_offset=Observation.damage.offset,
                damage_shot_id_offset=Damage.shot_event_id.offset,withdrawal_monotonic_offset=Withdrawal.monotonic_ms.offset)


if __name__=='__main__':
    import json
    print(json.dumps(inventory()))
