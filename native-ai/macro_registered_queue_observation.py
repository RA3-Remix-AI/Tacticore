"""Research-only enumeration of every Thing-ID hash bucket and own queue.

Broader than GameLogic's live list. No process opening or native calls. The
unregister/last-payment ordering still requires proof before product grants.
"""
import hashlib
from pathlib import Path
import struct

import macro_payment_observation_v2 as payment
import macro_readiness_observation as readiness
import readiness_dependency_contract as dependency

EXE_SHA256=payment.EXE_SHA256
PINS={
    0x504e10:'8b44240883ec08568b3033d2578b79088bc6f7f78b49048b049185c08d1491740b3b30742e8b400885c075f5',
    0x4e611a:'8b86dc00000083c4048d4c2414518d8bbc00000089442418e869684100578930',
    0x73dfe0:'8b4634508bcee8e563feff837e340075ef',
    0x4e2f77:'c6864401000001',
    0x4e313e:'c6864401000000',
}


def verify_pins(read,executable_sha256):
    payment.verify_pins(read,executable_sha256)
    for at,wanted in PINS.items():
        if readiness._read(read,at,len(bytes.fromhex(wanted)))!=bytes.fromhex(wanted):
            raise ValueError('registered_queue_signature_changed')


def registered_owned(read,game,owner):
    """Full bucket scan, not a heuristic ID upper bound or live-list walk.

    ``read`` should be StableRead so all table topology/necessary identities
    participate in the caller's final stability check.
    """
    buckets,count=struct.unpack('<II',read(game+0xc0,8))
    if not 1<=count<=65536:raise ValueError('registered_queue_bucket_count_bound')
    payment.ptr(buckets,(count+1)*4)
    raw=b''.join(read(buckets+offset,min(0x2000,(count+1)*4-offset))
        for offset in range(0,(count+1)*4,0x2000))
    heads=struct.unpack('<'+'I'*(count+1),raw);sentinel=heads[-1]
    seen_nodes=set();seen_ids=set();seen_things=set();owned=[];foreign=0;max_chain=0
    for bucket,first in enumerate(heads[:-1]):
        at=first;chain=0
        while at and at!=sentinel:
            payment.ptr(at,12);chain+=1
            if at in seen_nodes or len(seen_nodes)>=10000 or chain>128:
                raise ValueError('registered_queue_node_cycle_duplicate_or_bound')
            seen_nodes.add(at)
            ident,thing,following=struct.unpack('<III',read(at,12))
            if not ident or ident%count!=bucket or ident in seen_ids:
                raise ValueError('registered_queue_id_bucket_or_duplicate')
            seen_ids.add(ident);payment.ptr(thing,0x41c)
            if thing in seen_things:raise ValueError('registered_queue_duplicate_thing')
            seen_things.add(thing)
            if payment.word(read,thing)!=readiness.THING_VTABLE:
                raise ValueError('registered_queue_thing_signature')
            # No enemy ID/template/HP/position/module/status reads.
            if payment.word(read,thing+0x418)==owner:
                if payment.word(read,thing+0xdc)!=ident:raise ValueError('registered_queue_owned_id_mismatch')
                template=payment.ptr(payment.word(read,thing+4),12)
                owned.append((thing,ident,template))
            else:foreign+=1
            at=following
        max_chain=max(max_chain,chain)
    return owned,dict(registry_table=hex(game+0xbc),bucket_array=hex(buckets),bucket_count=count,
        registry_node_count=len(seen_nodes),foreign_owner_skipped_count=foreign,
        maximum_chain_length=max_chain,complete_bucket_scan=True,
        arbitrary_id_upper_bound_used=False,live_list_membership_required=False)


class RegisteredQueueCommitmentObserver(payment.PaymentCommitmentObserverV2):
    def __init__(self,read,owner,*,executable_sha256,expected_owner_index):
        verify_pins(read,executable_sha256)
        super().__init__(read,owner,executable_sha256=executable_sha256,expected_owner_index=expected_owner_index)
        self.registry_metadata=None

    def _live_owned(self,read):
        # Frozen v2 delegates only this roster hook; its exact queue-field and
        # strict paid policy are reused, without writing the frozen module.
        gc=read(self.base.game+0x144,1)[0]
        if gc!=0:raise ValueError('registered_queue_deletion_batch_active_or_unknown')
        owned,metadata=registered_owned(read,self.base.game,self.owner)
        by_address={row[0]:row for row in owned}
        # ID reassignment erases/reinserts registry membership without live
        # unlink. Include that independently complete live list as a union.
        at=payment.word(read,self.base.game+0xb4);visited=set();live_own=0;live_only=[]
        while at:
            payment.ptr(at,0x41c)
            if at in visited or len(visited)>=10000:raise ValueError('registered_queue_live_cycle_or_bound')
            visited.add(at)
            if payment.word(read,at)!=readiness.THING_VTABLE:raise ValueError('registered_queue_live_signature')
            following=payment.word(read,at+0x7c)
            if payment.word(read,at+0x418)==self.owner:
                ident=payment.word(read,at+0xdc)
                if not ident:raise ValueError('registered_queue_live_owned_id')
                template=payment.ptr(payment.word(read,at+4),12);row=(at,ident,template);live_own+=1
                if at in by_address and by_address[at]!=row:raise ValueError('registered_queue_union_identity_changed')
                if at not in by_address:live_only.append(ident);owned.append(row);by_address[at]=row
            at=following
        if len({row[1] for row in owned})!=len(owned):raise ValueError('registered_queue_union_duplicate_id')
        metadata.update(live_list_complete=True,live_topology_count=len(visited),live_owned_count=live_own,
            live_only_owned_ids=live_only,union_owned_count=len(owned),deletion_batch_active=False)
        self.registry_metadata=metadata
        return owned,metadata['registry_node_count'],metadata['foreign_owner_skipped_count']

    def sample(self):
        result=super().sample()
        result.update(schema_version=1,source='native_registry_and_live_union_owned_queue_research_observation_v1',
            roster_scope='all_Thing_ID_registry_buckets_union_full_live_list_owner_matches_without_health_filter',
            registry_scan=dict(self.registry_metadata),registered_roster_scan_complete=True,
            live_roster_scan_complete=True,roster_union_scan_complete=True,
            registry_unregistration_before_last_payment_excluded=False,
            unregistered_owners_payment_obligations_covered=False,
            product_fact_eligible=False,field_qualified_complete_queue_coverage=False)
        return result


def audit_executable(path):
    result=payment.audit_executable(path);raw=Path(path).read_bytes()
    for at,wanted in PINS.items():
        if raw[at-0x400000:at-0x400000+len(bytes.fromhex(wanted))]!=bytes.fromhex(wanted):
            raise ValueError('registered_queue_offline_pin_changed')
    return dict(result,kind='registered_queue_static_research_audit',
        registered_queue_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        registered_queue_byte_checks=[dict(address=hex(at),bytes=value) for at,value in PINS.items()],
        registry_unregistration_before_last_payment_excluded=False,product_fact_eligible=False)
