"""Pinned read(adapter) target quotes, not a dispatch reservation upper bound.

No process is opened and no native function is invoked. The adapter must bind
the process/session identity. Only current own producers and template facts are
read; unsupported discount/attribute branches remain explicitly unknown.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

import macro_readiness_observation as readiness
import readiness_dependency_contract as dependency

EXE_SHA256 = readiness.EXE_SHA256
PLAYER_MANAGER_GLOBAL = 0xce8c9c
ATTRIBUTE_POOL_VTABLE = 0xc2e174
PRODUCERS = {name: (0xd50c222e if name.startswith('produce') else 0xc16ff13f)
    for name in dependency.ACTIONS}
# Each range is literal reviewed file-backed native code/data, versioned with
# the executable hash. Generated once from the offline executable, never live.
PINS = {
    0xb74a10: '8b4c24048b0185c074118b480485c974208bc18b480485c975f7c38b41083b0875098bc88b40083b0874f7390175028bc1c3',
    0x7df7e0: '8b44240c83f8ff56578bf175090fb7be04030000eb028bf8837c240c0075078bc75f5ec20c008b4c241085c9f30f10050062be00f30f11442414741c6affe89d82f3ff85c074118b108bc88b82a000000056ffd0d95c2414f30f2ac7f30f594424145ff30f2cc05ec20c00',
    0x7ed3c9: '8b86980100003bc374088b50048b4204eb0233c066898504030000',
    0x717a60: '51568bf183be1003000000744183bec0030000007438837c240cff750e8b86b40300008b40145e59c204008d4c240c518d542408528d8eac030000e8900337008b44240481c6b00300003bc675d533c05e59c20400cccccccccccccccccccccce99bffffff',
    0x771cb0: '83ec0cf30f10050062be0053558bd98b6be08b45446bc07c578b7d4803c73bf8f30f1144240c747b568da424000000008b4c24206a006a006a00518d4f0ce85de2d6ff84c0744b8b0f85c974348b510c8b43e48b0a8b51048db0f80300008d442414508d4c241c518bce8954241ce8bd6031008b0083c6043bc60f95c084c07411f30f104704f30f59442410f30f114424108b55446bd27c03554883c77c3bfa758e5e8b43e48b8818040000e8efd20c00d84c240c5f5d5b83c40cc20400',
    0x83efd0: '518b4c240883791400f30f10050062be00f30f11042474568b4108568d71043bc6744a8b48108b159c8cce008b4c8a3080b93c120000007519f30f104014f30f584424040f57c90f2fc8f30f11442404771550e8e859330083c4043bc675c45ed9042459c20400f30f114c24045ed9042459c20400',
    0x83f050: '8d819012000050e874ffffffc3',
    0x723fe0: '8b8ed00000008b43e4897c24148bb818040000c1e91af6c101897c2428751980bc24d400000000750f6aff50578bcee8ccb70b0089442414f30f10050062be008b53e4f30f1144242c8b8a6c03000085c974416a008d442430506a0ee8cf69dbff84c0742ff30f1044242c0f2e05308bbe009ff6c4447a0ac7442414ffffff7feb12f30f2a4c2414f30f5ec8f30f2cc9894c2414',
    0x7241f1: '8b4c24148b9424c40000008b4424248bbc24bc000000894e30',
    0x4daa10: '83ec100f57c08b442418f30f11442404f30f10050062be0057f30f1100a1e48ccd008bf932c985c0884c2407f30f1144240c750932c05f83c410c20c00538b5f2c558b6850568b77283bf30f84980000003b6e0473688b0e8b118b420483f80e77063b6c873c76568b44242c50568bcfe88bc9ffff84c075458b5424248d4c241c51528bcee8b6feffff85c07514f30f1044241cf30f58442414f30f11442414eb1783f8017517f30f1044241cf30f59442418f30f11442418c64424130183c6103bf3758c8a4c241384c9741cf30f10442414f30f58050062be008b442428f30f59442418f30f11005e5d5b8ac15f83c410c20c00',
    0x6fa160: '0f57c053558b6c240c33db568bf157c706cc00c200896e04895e08f30f11460cf30f114614f30f10050062be008d7e308bcf895e10c74618fffffffff30f11461c885e20895e24895e28895e2ce80e0fd4ff',
    0x6fa320: '56578b7c240c8b4704508bf1e82ffeffff897e385fc70674e1c200c7463c00000000c64640018bc65ec20400',
    0x79da9e: '89bd6c030000',
    0x83be10: '8b91e80000002b91e40000008b442404c1fa023bc2720533c0c204008b89e40000008b0481c20400',
    0x70f514: '8b4e683bc80f8da3000000572bc16a008bcd8bf8e8e3c812008b50140350043bd7725a8b461085c074088b48048b5008eb0e8d4c240ce871bbd2ff8b088b50048b85f00100006a01508b460852516a0050576a0f6a008bcde89fc812008bc8e8a89c1300014668',
    0x849220: '81ecb4000000568bf18b46148b4e04578bbc24c400000003c83bf90f47f985ff750d5f33c05e81c4b4000000c220005333db3bf88bcf72028bc885c974102bc12bf98bd98bce894614e812b0ffff8b46043bf872028bf88b9424c40000002bc7894604',
    0xc3f968: 'b01c7700',
    0xbe6200: '0000803f',
    0xbdfeb8: '7870bd009a000000',
}


def verify_pins(read, executable_sha256):
    dependency.verify_pins(read, executable_sha256)
    for at, expected in PINS.items():
        wanted = bytes.fromhex(expected)
        if readiness._read(read, at, len(wanted)) != wanted:
            raise ValueError('cost_signature_changed')
    if readiness._read(read, 0xbd7078, 15) != b'BUILD_FOR_FREE\0':
        raise ValueError('cost_native_enum_name_changed')


def _word(read, at): return readiness._word(read, at)
def _ptr(at, size=4): return readiness._pointer(at, size)


def _float32(value):
    try: result = struct.unpack('<f', struct.pack('<f', value))[0]
    except (OverflowError, struct.error): raise ValueError('cost_float_overflow') from None
    if not math.isfinite(result): raise ValueError('cost_nonfinite_multiplier')
    return result


class NativeCostObserver:
    """Observe a current getter quote and current native payment balance.

    ``sample(action, producer_thing_id=...)`` requires a real owned registered
    construction yard or war factory, according to the requested action. It
    does not qualify command availability, reserve funds, or predict discounts
    at a later dispatch frame. Source evidence is returned even when the final
    quote is unknown. Initialization only freezes reviewed immutable signatures.
    """
    def __init__(self, read, owner, *, executable_sha256, expected_owner_index):
        verify_pins(read, executable_sha256)
        self.dependencies = dependency.DependencyObserver(read, owner,
            executable_sha256=executable_sha256, expected_owner_index=expected_owner_index)
        self.base = self.dependencies.base
        self.read = read; self.owner = self.base.owner
        self.factory = self.dependencies.factory

    def _player_bonus(self, read):
        # Only the proven empty and single own-provider branches are mirrored.
        # Foreign providers are never dereferenced for their eligibility byte.
        tree = self.owner + 0x1290; sentinel = tree + 4
        count = _word(read, tree + 0x14)
        if count == 0:
            return dict(multiplier=1.0, provider_count=0, branch='native_empty_bonus_tree')
        if count != 1:
            return dict(multiplier=None, provider_count=count, reason='multiple_bonus_providers_not_mirrored')
        right, left, root = struct.unpack('<3I', read(tree + 4, 12))
        node = _ptr(root, 24)
        if left != node or right != node or node == sentinel:
            raise ValueError('cost_single_bonus_tree_inconsistent')
        child0, child1, parent = struct.unpack('<3I', read(node, 12))
        color = read(node + 0xc, 1)[0]
        source = _word(read, node + 0x10)
        # b74a10 uses null children, not header sentinels. Header+0 is
        # rightmost, +4 leftmost, +8 root; iterator(singleton) must end.
        if child0 or child1 or parent != sentinel or color not in (0, 1):
            raise ValueError('cost_single_bonus_node_inconsistent')
        if source != self.base.owner_index:
            return dict(multiplier=None, provider_count=1,
                reason='foreign_bonus_provider_eligibility_not_read', provider_index=source)
        manager = _ptr(_word(read, PLAYER_MANAGER_GLOBAL), 0x70)
        if _word(read, manager + 0x30 + 4*source) != self.owner:
            raise ValueError('cost_own_bonus_provider_identity')
        ignored = read(self.owner + 0x123c, 1)[0]
        if ignored not in (0, 1): raise ValueError('cost_provider_ignore_flag')
        bonus = struct.unpack('<f', read(node + 0x14, 4))[0]
        if not math.isfinite(bonus): raise ValueError('cost_nonfinite_bonus')
        factor = 1.0 if ignored else max(0.0, _float32(1.0 + bonus))
        return dict(multiplier=factor, provider_count=1, provider_index=source,
            own_provider_ignored=bool(ignored), native_bonus=bonus,
            branch='native_single_own_bonus_provider')

    def _producer_multiplier(self, read, thing):
        # 717a60(-1) returns null when either guard is null. The getter then
        # uses 1.0, without calling the player bonus getter at all.
        modules = _word(read, thing + 0x310); guard = _word(read, thing + 0x3c0)
        if not modules or not guard:
            return dict(multiplier=1.0, branch='native_no_production_interface_guard')
        wrapper = _ptr(_word(read, thing + 0x3b4), 0x18)
        interface = _word(read, wrapper + 0x14)
        if not interface:
            return dict(multiplier=1.0, branch='native_null_production_interface')
        _ptr(interface - 0x24, 0x138)
        if (_word(read, interface) != readiness.PRODUCTION_INTERFACE_VTABLE
                or _word(read, interface - 0x24) != 0xc3fad0
                or _word(read, interface - 0x1c) != thing):
            raise ValueError('cost_production_interface_identity')
        definition = _ptr(_word(read, interface - 0x20), 0x4c)
        count = _word(read, definition + 0x44)
        if count:
            return dict(multiplier=None, modifier_count=count,
                reason='conditional_production_modifiers_not_mirrored')
        bonus = self._player_bonus(read)
        return dict(bonus, modifier_count=0, interface=hex(interface))

    def _attribute_pool(self, read, thing, producer_template):
        pool = _word(read, thing + 0x36c)
        if not pool:
            return dict(cost_adjustment_absent=True, branch='native_absent_attribute_pool')
        _ptr(pool, 0x3c)
        if (_word(read, pool) != ATTRIBUTE_POOL_VTABLE
                or _word(read, pool + 0x38) != thing
                or _word(read, pool + 4) != producer_template):
            raise ValueError('cost_attribute_pool_identity')
        start, end = struct.unpack('<II', read(pool + 0x28, 8))
        if end < start or (end-start) % 16 or end-start > 16384 or bool(start) != bool(end):
            raise ValueError('cost_attribute_pool_bounds')
        return dict(cost_adjustment_absent=start == end,
            branch='native_empty_attribute_vector' if start == end else 'active_attribute_vector_not_mirrored',
            entry_count=(end-start)//16)

    def _credits(self, read):
        # 83be10(Player, 0), then the exact available-money sum used by
        # production payment 70f528. +14 is spendable too, never "reserved".
        start, end = struct.unpack('<II', read(self.owner + 0xe4, 8))
        if not start and not end:
            return dict(credits=None, credits_verified=False, reason='native_resource_zero_slot_absent')
        if end <= start or (end-start) % 4 or end-start > 256:
            raise ValueError('cost_resource_vector_bounds')
        account = _ptr(_word(read, _ptr(start, end-start)), 0x18)
        if _word(read, account + 0xc) != self.base.owner_index:
            raise ValueError('cost_resource_account_owner_index')
        ordinary = _word(read, account + 4); additional = _word(read, account + 0x14)
        if ordinary + additional > 0x7fffffff:
            raise ValueError('cost_resource_balance_overflow')
        return dict(credits=ordinary+additional, credits_verified=True,
            source='native_player_resource_zero_payment_balance', account=hex(account),
            native_primary_spendable=ordinary, native_additional_spendable=additional,
            native_reserved_credits=None, native_reserved_credits_verified=False)

    def sample(self, action, *, producer_thing_id):
        if type(action) is not str or action not in PRODUCERS:
            raise ValueError('cost_action')
        if type(producer_thing_id) is not int or not 0 < producer_thing_id <= 0xffffffff:
            raise ValueError('cost_producer_id')
        self.base._identity()
        if _word(self.read, dependency.TEMPLATE_FACTORY_GLOBAL) != self.factory:
            raise ValueError('cost_factory_changed')
        frame = _word(self.read, self.base.game + 0x50)
        if not frame: raise ValueError('cost_game_not_running')
        read = dependency.StableRead(self.read)
        thing = readiness.registry_lookup(read, self.base.game, producer_thing_id)
        _ptr(thing, 0x474)
        # Owner validation precedes template, status, discounts and money reads.
        if _word(read, thing) != readiness.THING_VTABLE or _word(read, thing + 0xdc) != producer_thing_id:
            raise ValueError('cost_producer_registry_identity')
        if _word(read, thing + 0x418) != self.owner: raise ValueError('cost_foreign_producer')
        producer_template = _ptr(_word(read, thing + 4), 0x31c)
        if _word(read, producer_template + 8) != PRODUCERS[action]:
            raise ValueError('cost_wrong_producer_type')
        target_hash = dependency.ACTIONS[action][0]
        template = self.dependencies._template(read, target_hash)
        if not template: raise ValueError('cost_target_template_missing')
        base_cost = struct.unpack('<H', read(template + 0x304, 2))[0]
        build_for_free = bool(_word(read, template + 0xd0) & (1 << 26))
        multiplier = self._producer_multiplier(read, thing)
        factor = multiplier['multiplier']; quote = None
        if factor is not None:
            numeric = _float32(_float32(base_cost) * _float32(factor))
            if not 0 <= numeric < 0x80000000: raise ValueError('cost_quote_int32_bounds')
            quote = math.trunc(numeric)  # native cvttss2si after SSE float32.
        attributes = self._attribute_pool(read, thing, producer_template)
        ordinary_unit_cost = None
        if action.startswith('produce') and attributes['cost_adjustment_absent']:
            ordinary_unit_cost = 0 if build_for_free else quote
        balance = self._credits(read)
        read.finish(); self.base._identity()
        frame_after = _word(self.read, self.base.game + 0x50)
        if (_word(self.read, dependency.TEMPLATE_FACTORY_GLOBAL) != self.factory
                or not 0 <= frame_after-frame <= 2):
            raise ValueError('cost_session_or_frame_changed')
        return dict(schema_version=1, kind='native_current_target_cost_observation',
            source='native_read_only_current_target_quote_v1', frame=frame, frame_after=frame_after,
            action=action, target_template_hash=hex(target_hash), target_template=hex(template),
            producer_thing_id=producer_thing_id, producer_thing=hex(thing),
            session_identity=dict(game=hex(self.base.game), owner=hex(self.owner),
                owner_index=self.base.owner_index, template_factory=hex(self.factory)),
            native_runtime_base_cost=base_cost, native_getter_quote=quote,
            native_getter_quote_verified=quote is not None, producer_multiplier=multiplier,
            native_build_for_free=build_for_free, producer_attribute_evidence=attributes,
            ordinary_unit_enqueue_cost=ordinary_unit_cost,
            ordinary_unit_enqueue_cost_verified=ordinary_unit_cost is not None,
            ordinary_unit_enqueue_assumptions=['normal_single_unit_request', 'no_caller_base_override',
                'no_caller_free_override', 'unchanged_observed_native_state'],
            current_payment_balance=balance, upper_cost=None, upper_cost_verified=False,
            native_reserved_credits=None, native_reserved_credits_verified=False,
            actual_construction_cost=None, actual_paid=None, reservation_usable=False,
            future_quote_validity_verified=False, field_verified=False, grants_capability=False,
            native_calls=0, process_writes=0, enemy_details_read=False)


def audit_executable(path):
    result = dependency.audit_executable(path)
    raw = Path(path).read_bytes()
    for at, expected in PINS.items():
        wanted = bytes.fromhex(expected)
        if raw[at-0x400000:at-0x400000+len(wanted)] != wanted:
            raise ValueError('cost_offline_pin_changed')
    if raw[0xbd7078-0x400000:0xbd7078-0x400000+15] != b'BUILD_FOR_FREE\0':
        raise ValueError('cost_offline_enum_changed')
    return dict(result, kind='native_cost_static_audit', field_verified=False,
        cost_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        cost_byte_checks=[dict(address=hex(at), bytes=value) for at, value in PINS.items()],
        positive_scope=['current_runtime_template_u16_base_cost',
            'current_getter_quote_restricted_producer_discount_branches',
            'ordinary_single_unit_enqueue_quote_without_attribute_adjustment',
            'own_native_resource_zero_current_payment_balance'],
        reservation_upper_cost_verified=False, native_reserved_credits_verified=False,
        no_process_opened=True, native_calls=0, process_writes=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-executable', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = audit_executable(args.audit_executable)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf8') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps(dict(output=str(args.output), cost_pins=len(PINS), field_verified=False)))


if __name__ == '__main__': main()
