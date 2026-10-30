"""Own accepted production-queue payment commitments, via read(adapter) only.

All owned objects and all their ProductionUpdate modules are enumerated. The
sum is a complete production-queue sum, not a claim about queue-external repair,
abilities, scripts or later autonomous spending. No native function is called.
"""
import hashlib
from pathlib import Path
import struct

import macro_cost_observation as cost
import macro_readiness_observation as readiness
import readiness_dependency_contract as dependency

EXE_SHA256 = cost.EXE_SHA256
PRODUCTION_MODULE_VTABLE = 0xc3fad0
QUEUE_NODE_VTABLE = 0xc34000
PINS = {
    0x70f2c0: '8bc18b4c24080f57c08b54240489480433c9c7000040c30089500889480c894810894814c7401801000000f30f11401cf30f11402089482489482889482c8948308948348b15285ace0089503889483c88484089484489484888484c88484d88484e88484f884850894854894858c7405cfffffffff30f114060884864884865894868f30f11406cc20800',
    0x70f440: '83ec08558b6c241085ed568bf1750a5e32c05d83c408c204008b461085c0f30f104620f30f58461c53f30f11442418b30174568b40140f57c90f2f888800000072478b46048b50248d48248b82bc000000ffd085c0742a8d4c2418518bc8e84de0fefff30f10442418f30f59053c66be000f57c90f2fc1f30f11442418770aeb15f30f1044241832dbf30f100d3c66be000f2fc87706f30f114c2418db463083ec08d84c2420d80db063be00dd1c24ff15c074bc008b4630d95c2414f30f2c4c241483c4083bc87d028bc184db5b0f84ae0000008b4e683bc80f8da3000000572bc16a008bcd8bf8e8e3c812008b50140350043bd7725a8b461085c074088b48048b5008eb0e8d4c240ce871bbd2ff8b088b50048b85f00100006a01508b460852516a0050576a0f6a008bcde89fc812008bc8e8a89c1300014668f30f104424185ff30f11461c5eb0015d83c408c204008bcde858c3120084c0741b8b0d44b7cd008b91e00000008b422c6a006a006a0050e8a96ae2ff5f5e32c05d83c408c20400f30f10442414f30f11461c5eb0015d83c408c20400cccccccccccccccccc8b411085c0750332c0c38b80c0000000',
    0x724142: '6a70e85728cfff83c40485c074168b53e48b8adc00000055518bc8e85eb1feff8bf0eb0233f6807c241300740b8b442420c644241300eb0e8b55008b42588bcdffd0894424208b4c241c8946188bc1c7462801000000c7462c000000008b503c8b79408b40408d0cd03bf97442908b178b0d586cce0052e872000c0085c074138b8c24bc000000518bc8e81f020c0084c075168b44241c8b503c8b404083c7088d0cd03bf975c7eb068b57048956288b4c24148b9424c40000008b4424248bbc24bc000000894e30528d4e48c746',
    0x73e120: '83ec0c8b89ec000000568b35e48ccd005733ff85c9894c2408744468f4c6c100b9808dcd00e806ce2e008d442408508d4c241081c6bc000000518bcee8af6cdcff8b56088b4e048b44240c3b049174038b78046a01b9808dcd00e881ce2e008bc75f5e83c40cc3',
    0x6fd4f0: 'b8010000008405fc5fce00568bf1751b8b0d3873d0000905fc5fce006898a5be00e89ad72800a3f85fce00a1f85fce00508bcee82804feff85c05e74078bc8e94c99ffff8b5424040f57c0f30f110232c0c20400',
    0x7baaf3: '8b442418508bcde84149f5ff84c0755a85dbc78720010000000000000f84a10c00008b4b048b91d0000000c1ea15f6c2010f848c0c00008bcbe8ef2af4ff84c00f857d0c00008b4c242c8b018b55108b80c00000006a0052ffd05d5f5eb8010000005b81c43c010000c3',
    0x771fcc: '8b453433db3bc3895c241874138da4240000000083442418018b40543bc375f48b068b50748d4c2418518bceffd2f64604010f84610100008d4c2410e8b390ccff8b7d343bfb0f84120300008b068b50146a048d5f0c538bceffd28b1b83eb01740e83eb010f85110100008b4714eb038b47108b4804894c24108b50088d44241050568954241ce8c83321008b168b521483c4086a048d4718508bceffd28b068b50648d4f1c518bceffd28b068b50648d4f20518bceffd28b068b50708d4f24518bceffd28b068b50708d4f',
    0x6f6cb0: '83ec10578bf9807f44000f84a00100008b44241c5333db5633f62bc3895c2410742483e8010f85f90000008b0de48ccd008b47388b71508b5f402b773c89442410e9de0000008b35e48ccd008b573cd986bc01000055d95c2414528bcee81ed0fdffd80d9467be00d97c24128bce0fb7442412d80d5cbccd000d000c0000894424188b4740d84c241450d96c241cdf7c241c8b6c241cd96c2416e8e1cffdffd80d9467be008b4f38d97c24120fb7442412d80d5cbccd000d000c00008944241851d84c24188bced96c241cdf7c241c8b5c241cd96c2416e8a4cffdffd80d9467be008b0d50b7cd00d97c24120fb7442412d80d5cbccd000d000c0000894424188b01d84c2414d96c2418df7c24188b542418895424148b5074d96c2412ffd28bf02bf55d807f45007422837c242401750aa1e48ccd008b4050eb0d8b0d50b7cd008b118b4274ffd02bd803f385f689742424db4424247d06d805748fbe008b4c2410db44241085c97d06d805748fbe00def98b4424200f57c95e5bd954241cd918f30f1044241c0f2fc876030f28c1f30f100d0062be000f2fc8f30f110077030f28c1f30f1100b0015f83c410c208008b5424180f57c0f30f110232c05f83c410c20800cc',
    0xbe663c: '0000c842',
    0xbe63b0: '0ad7233c',
    0xc3f984: '20e17300',
}


def verify_pins(read, executable_sha256):
    cost.verify_pins(read, executable_sha256)
    for at, expected in PINS.items():
        wanted = bytes.fromhex(expected)
        if readiness._read(read, at, len(wanted)) != wanted:
            raise ValueError('payment_signature_changed')


def _word(read, at): return readiness._word(read, at)
def _ptr(at, size=4): return readiness._pointer(at, size)


def remaining_queue_commitment(total_cost, paid):
    # 70f440 clamps desired cumulative payment to total cost and only pays its
    # positive difference from +68. Refund/requeue are separate lifecycle facts.
    if (type(total_cost) is not int or type(paid) is not int
            or not 0 <= paid <= total_cost <= 0x7fffffff):
        raise ValueError('payment_cost_paid_bounds')
    return total_cost-paid


class PaymentCommitmentObserver:
    def __init__(self, read, owner, *, executable_sha256, expected_owner_index):
        verify_pins(read, executable_sha256)
        self.dependencies = dependency.DependencyObserver(read, owner,
            executable_sha256=executable_sha256, expected_owner_index=expected_owner_index)
        self.base = self.dependencies.base; self.owner = self.base.owner
        self.read = read; self.factory = self.dependencies.factory

    def _queue(self, read, module, owner_thing, owner_id, seen_nodes):
        if (_word(read, module) != PRODUCTION_MODULE_VTABLE
                or _word(read, module+8) != owner_thing
                or _word(read, module+0x24) != readiness.PRODUCTION_INTERFACE_VTABLE):
            raise ValueError('payment_production_module_binding')
        head, tail = struct.unpack('<II', read(module+0x34, 8))
        if bool(head) != bool(tail): raise ValueError('payment_queue_endpoints')
        node = head; previous = 0; rows = []
        while node:
            _ptr(node, 0x70)
            if node in seen_nodes or len(seen_nodes) >= 2048:
                raise ValueError('payment_queue_cycle_or_duplicate')
            seen_nodes.add(node); raw = read(node, 0x70)
            words = struct.unpack('<28I', raw)
            if words[0] != QUEUE_NODE_VTABLE or words[1] != module or words[0x58//4] != previous:
                raise ValueError('payment_queue_node_binding')
            kind = words[3]
            if kind not in (1, 2): raise ValueError('payment_queue_kind_unknown')
            total, paid = words[0x30//4], words[0x68//4]
            remainder = remaining_queue_commitment(total, paid)
            rows.append(dict(node=hex(node), producer_thing_id=owner_id,
                producer_thing=hex(owner_thing), module=hex(module), kind=kind,
                native_queue_id=words[0x18//4], native_total_cost=total,
                native_paid_accumulator=paid, outstanding_payment_upper_bound=remainder,
                next=hex(words[0x54//4]), previous=hex(previous), raw=raw.hex()))
            previous = node; node = words[0x54//4]
        if previous != tail: raise ValueError('payment_queue_tail_mismatch')
        return dict(module=hex(module), producer_thing_id=owner_id,
            head=hex(head), tail=hex(tail), nodes=rows)

    def sample(self):
        self.base._identity()
        if _word(self.read, dependency.TEMPLATE_FACTORY_GLOBAL) != self.factory:
            raise ValueError('payment_factory_changed')
        frame = _word(self.read, self.base.game+0x50)
        if not frame: raise ValueError('payment_game_not_running')
        read = dependency.StableRead(self.read)
        owned = self.dependencies._owned(read); queues = []; seen_nodes = set(); seen_modules = set()
        module_census = []
        for thing, ident, template in owned:
            vector = _ptr(_word(read, thing+0x310), 4)
            modules = []; terminated = False
            for index in range(128):
                module = _word(read, vector+4*index)
                if not module: terminated = True; break
                _ptr(module, 4)
                if module in seen_modules: raise ValueError('payment_duplicate_module')
                seen_modules.add(module)
                vtable = _word(read, module); modules.append(dict(module=hex(module),vtable=hex(vtable)))
                if vtable == PRODUCTION_MODULE_VTABLE:
                    queues.append(self._queue(read, module, thing, ident, seen_nodes))
            if not terminated: raise ValueError('payment_module_vector_unterminated')
            module_census.append(dict(thing_id=ident, thing=hex(thing),
                template_hash=hex(_word(read, template+8)), modules=modules,
                module_vector_terminated=True))
        total = sum(node['outstanding_payment_upper_bound'] for queue in queues for node in queue['nodes'])
        if total > 0xffffffff: raise ValueError('payment_commitment_sum_overflow')
        read.finish(); self.base._identity()
        after = _word(self.read, self.base.game+0x50)
        if (_word(self.read, dependency.TEMPLATE_FACTORY_GLOBAL) != self.factory
                or not 0 <= after-frame <= 2): raise ValueError('payment_session_or_frame_changed')
        return dict(schema_version=1,kind='native_own_production_queue_commitment_observation',
            source='native_all_own_production_update_queue_payment_upper_bound_v1',
            frame=frame,frame_after=after,session_identity=dict(game=hex(self.base.game),
                owner=hex(self.owner),owner_index=self.base.owner_index,template_factory=hex(self.factory)),
            own_object_count=len(owned),module_census=module_census,queues=queues,
            production_queue_payment_commitment_upper_bound=total,
            all_current_own_production_queues_enumerated=True,
            existing_native_payment_commitment_upper_bound=None,
            existing_native_payment_commitment_upper_bound_verified=False,
            queue_external_payment_obligations_covered=False,
            future_autonomous_spending_controlled=False,field_verified=False,grants_capability=False,
            native_calls=0,process_writes=0,enemy_details_read=False)


def audit_executable(path):
    result = cost.audit_executable(path); raw = Path(path).read_bytes()
    for at, expected in PINS.items():
        wanted = bytes.fromhex(expected)
        if raw[at-0x400000:at-0x400000+len(wanted)] != wanted:
            raise ValueError('payment_offline_pin_changed')
    return dict(result,kind='native_queue_payment_static_audit',
        payment_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        payment_byte_checks=[dict(address=hex(at),bytes=value) for at,value in PINS.items()],
        full_native_obligation_coverage_verified=False,field_verified=False,grants_capability=False)
