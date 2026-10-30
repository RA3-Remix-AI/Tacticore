"""Experimental complete GameLogic-live own queue scan; no product qualification.

The live list is broader than Player+1260. Completeness for owners already
removed from the live list is still unproven and never silently granted here.
"""
import hashlib
from pathlib import Path
import struct

import macro_payment_observation as baseline
import macro_readiness_observation as readiness
import readiness_dependency_contract as dependency

EXE_SHA256=baseline.EXE_SHA256
PINS={
    0x4e9c0b:'8b5424108baab400000085ed',
    0x4e9c9e:'8b6d7c85ed0f8577ffffff',
}


def verify_pins(read,executable_sha256):
    baseline.verify_pins(read,executable_sha256)
    for address,value in PINS.items():
        if readiness._read(read,address,len(bytes.fromhex(value)))!=bytes.fromhex(value):
            raise ValueError('payment_v2_live_list_signature_changed')


def word(read,address):return readiness._word(read,address)
def ptr(value,size=4):return readiness._pointer(value,size)


class PaymentCommitmentObserverV2:
    def __init__(self,read,owner,*,executable_sha256,expected_owner_index):
        verify_pins(read,executable_sha256)
        self.dependencies=dependency.DependencyObserver(read,owner,
            executable_sha256=executable_sha256,expected_owner_index=expected_owner_index)
        self.read=read;self.base=self.dependencies.base;self.owner=self.base.owner;self.factory=self.dependencies.factory

    def _live_owned(self,read):
        at=word(read,self.base.game+0xb4);visited=set();owned=[];foreign_count=0
        while at:
            ptr(at,0x41c)
            if at in visited or len(visited)>=10000:raise ValueError('payment_v2_live_list_cycle_or_bound')
            visited.add(at)
            # Shared topology and ownership only. Foreign details are never read.
            if word(read,at)!=readiness.THING_VTABLE:raise ValueError('payment_v2_live_thing_signature')
            following=word(read,at+0x7c);owner=word(read,at+0x418)
            if owner!=self.owner:
                foreign_count+=1;at=following;continue
            ident=word(read,at+0xdc)
            if readiness.registry_lookup(read,self.base.game,ident)!=at:
                raise ValueError('payment_v2_owned_registry_link')
            template=ptr(word(read,at+4),12)
            owned.append((at,ident,template))
            at=following
        if len({row[1] for row in owned})!=len(owned):raise ValueError('payment_v2_duplicate_owned_id')
        return owned,len(visited),foreign_count

    def _queue(self,read,module,thing,ident,seen):
        if (word(read,module)!=baseline.PRODUCTION_MODULE_VTABLE or word(read,module+8)!=thing
                or word(read,module+0x24)!=readiness.PRODUCTION_INTERFACE_VTABLE):
            raise ValueError('payment_v2_module_owner_binding')
        head,tail=struct.unpack('<II',read(module+0x34,8))
        if bool(head)!=bool(tail):raise ValueError('payment_v2_queue_endpoints')
        node=head;previous=0;nodes=[]
        while node:
            ptr(node,0x6c)
            if node in seen or len(seen)>=2048:raise ValueError('payment_v2_queue_cycle_or_duplicate')
            seen.add(node)
            # Deliberately omit progress/ticks/opaque padding. Every field below
            # is rechecked exactly by StableRead, including paid (no min policy).
            vtable=word(read,node);back_module=word(read,node+4);owner_id=word(read,node+8)
            kind=word(read,node+0xc);number=word(read,node+0x18)
            if (vtable!=baseline.QUEUE_NODE_VTABLE or back_module!=module or owner_id!=ident
                    or not number or kind not in (1,2)):
                raise ValueError('payment_v2_queue_identity_or_kind')
            target=ptr(word(read,node+(0x10 if kind==1 else 0x14)),12)
            target_hash=word(read,target+8)
            cost=word(read,node+0x30);paid=word(read,node+0x68)
            following=word(read,node+0x54);back=word(read,node+0x58)
            if back!=previous:raise ValueError('payment_v2_queue_previous_link')
            remaining=baseline.remaining_queue_commitment(cost,paid)
            nodes.append(dict(node=hex(node),producer_thing_id=ident,producer_thing=hex(thing),module=hex(module),
                kind=kind,native_queue_id=number,target=hex(target),target_hash=hex(target_hash),
                native_total_cost=cost,native_paid_accumulator=paid,outstanding_payment_upper_bound=remaining,
                next=hex(following),previous=hex(back),paid_stability_policy='strict_equal_double_read'))
            previous=node;node=following
        if previous!=tail:raise ValueError('payment_v2_queue_tail_mismatch')
        return dict(module=hex(module),producer_thing_id=ident,head=hex(head),tail=hex(tail),nodes=nodes)

    def sample(self):
        self.base._identity()
        if word(self.read,dependency.TEMPLATE_FACTORY_GLOBAL)!=self.factory:raise ValueError('payment_v2_factory_changed')
        frame=word(self.read,self.base.game+0x50)
        if not frame:raise ValueError('payment_v2_game_not_running')
        read=dependency.StableRead(self.read)
        owned,visited,foreign=self._live_owned(read);queues=[];module_census=[];seen_modules=set();seen_nodes=set()
        for thing,ident,template in owned:
            vector=ptr(word(read,thing+0x310),4);modules=[]
            for index in range(256):
                module=word(read,vector+index*4)
                if not module:break
                ptr(module,4)
                if module in seen_modules:raise ValueError('payment_v2_duplicate_module')
                seen_modules.add(module);vtable=word(read,module)
                modules.append(dict(module=hex(module),vtable=hex(vtable)))
                if vtable==baseline.PRODUCTION_MODULE_VTABLE:
                    queues.append(self._queue(read,module,thing,ident,seen_nodes))
            else:raise ValueError('payment_v2_module_vector_unterminated')
            module_census.append(dict(thing_id=ident,thing=hex(thing),template_hash=hex(word(read,template+8)),
                modules=modules,module_vector_terminated=True))
        total=sum(node['outstanding_payment_upper_bound'] for queue in queues for node in queue['nodes'])
        if total>0xffffffff:raise ValueError('payment_v2_sum_overflow')
        try:read.finish()
        except ValueError as error:
            if str(error)=='dependency_sample_changed':raise ValueError('payment_v2_necessary_bytes_changed') from None
            raise
        self.base._identity();after=word(self.read,self.base.game+0x50)
        if word(self.read,dependency.TEMPLATE_FACTORY_GLOBAL)!=self.factory or not 0<=after-frame<=2:
            raise ValueError('payment_v2_session_or_frame_changed')
        return dict(schema_version=2,kind='native_own_production_queue_commitment_observation',
            source='native_gamelogic_live_owned_production_upgrade_queue_observation_v2',
            frame=frame,frame_after=after,session_identity=dict(game=hex(self.base.game),owner=hex(self.owner),
                owner_index=self.base.owner_index,template_factory=hex(self.factory)),
            roster_scope='all_GameLogic_live_Thing_owner_matches_without_health_filter',
            shared_topology_visited_count=visited,foreign_owner_skipped_count=foreign,own_object_count=len(owned),
            module_census=module_census,queues=queues,production_queue_payment_commitment_upper_bound=total,
            roster_scan_complete=True,queue_scan_complete=True,necessary_fields_stable=True,
            paid_stability_policy='strict_equal_double_read',progress_or_tick_read=False,
            all_current_own_production_queues_enumerated=False,field_qualified_complete_queue_coverage=False,
            removed_live_list_owners_payment_obligations_covered=False,
            existing_native_payment_commitment_upper_bound=None,existing_native_payment_commitment_upper_bound_verified=False,
            queue_external_payment_obligations_covered=False,future_autonomous_spending_controlled=False,
            native_calls=0,process_writes=0,enemy_details_read=False,field_verified=False,grants_capability=False)


def audit_executable(path):
    result=baseline.audit_executable(path);raw=Path(path).read_bytes()
    for at,wanted in PINS.items():
        if raw[at-0x400000:at-0x400000+len(bytes.fromhex(wanted))]!=bytes.fromhex(wanted):
            raise ValueError('payment_v2_offline_live_list_pin_changed')
    return dict(result,kind='native_queue_payment_static_audit_v2',
        payment_v2_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        live_list_byte_checks=[dict(address=hex(at),bytes=value) for at,value in PINS.items()],
        complete_owned_production_coverage_proven=False,removed_live_list_payment_coverage_proven=False)
