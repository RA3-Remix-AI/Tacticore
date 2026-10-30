"""Read-only static lifecycle contract; field qualification remains separate.

Validate complete reviewed byte ranges, never call engine functions. These
facts support the registry/live UNION algorithm for native scheduled
ProductionUpdate queues. They do not grant a product fact on their own.
"""
import hashlib
import macro_readiness_observation as readiness

EXE_SHA256=readiness.EXE_SHA256
BLOCKS=(
    ('normal_gc_unschedule_unlink_erase',0x4e2f60,492,'0ff1fcb33bac0ea05e9b627f8da388e9e363b1411928f4b1b0bfaa773701898b'),
    ('thing_initialization_registration_before_modules',0x7c1c90,2200,'a3590ff4be84c61750e1252d37eb00b5f8cdbfb6e9498558fe1af0ae54380692'),
    ('link_register_then_schedule',0x4ee040,268,'8c7bbdb30943bc624c90289908eb132586ea2112dfa055c05c74cde96734066e'),
    ('reschedule_live_membership_gate',0x4edec0,263,'28a161e42393391c53bb0d52972dce97c54df0e982df34cfa10755ed552db04a'),
    ('production_destructor_clears_queue',0x73dfa0,178,'f6e6d42753479af1ca6fbf5538b269b5ad364b2cf800161b6b89d578e0e9dc29'),
    ('queue_payment_update',0x70f440,381,'0b80e02fd620ebaaa48450c53923ab9b1ea505c5cf2a3b2cd52dacab9928d445'),
    ('production_update_interface',0x6e87a0,14,'b7246fa12e0da5809d756c4f78f94b4fcfc2c66fa533e272913c1294c83d6303'),
    ('live_unlink',0x6dd8c0,110,'7134dad5da742d7b76e1b441ffa42897db107238126a4238e52e656bbaf05f6e'),
    ('unregister_id',0x4deaf0,80,'06afd08ee605ba8eb2cfb6bcd4701243bdd1f6fcb694a378962b170b3b4ce2a7'),
    ('xfer_id_reassignment_no_live_unlink',0x78f4d3,85,'61ed595a28420b2620041981a9a86d83aaf06d5f40c45549ce0e84037a5d7b60'),
    ('destroy_all_live_via_normal_gc',0x4f1a00,112,'ad1f60f98cf2e5b8063aecba7c27aaa86993b9f50ea72386d39cb898c6206d23'),
    ('logic_destructor_gc_before_registry_clear',0x4f1a70,778,'c9ade442cf07da7420e1d51a1c86120bc36a3223e198174637b8e225f695d92b'),
    ('logic_reset_registry_clear_then_live_gc',0x4f7b20,720,'53efab80796d855d6a97bdedf90939f932774ec6dcce052db813d269ac97ce95'),
)


def verify_owner_lifecycle_contract(read,*,executable_sha256):
    if executable_sha256!=EXE_SHA256:raise ValueError('queue_coverage_exact_executable_required')
    observed=[]
    for label,address,size,digest in BLOCKS:
        raw=readiness._read(read,address,size)
        if hashlib.sha256(raw).hexdigest()!=digest:
            raise ValueError('queue_coverage_lifecycle_bytes_changed:'+label)
        observed.append(dict(label=label,address=hex(address),size=size,sha256=digest))
    return dict(kind='native_ProductionUpdate_owner_lifecycle_static_contract',schema_version=1,
        executable_sha256=EXE_SHA256,reviewed_blocks=observed,
        supported_owner_algorithm='full_Thing_registry_union_full_GameLogic_live_owner_filter',
        static_normal_lifecycle_support=True,
        initialization_registers_before_module_creation=True,
        live_link_and_registration_precede_update_scheduling=True,
        normal_gc_unschedules_before_live_unlink_and_registry_erase=True,
        id_reassignment_requires_live_union_coverage=True,
        reset_and_destructor_paths_require_union_and_gc_guard=True,
        requires_same_session_native_identity=True,requires_complete_steady_roster_and_queue_bytes=True,
        requires_paid_equal_double_read=True,maximum_internal_frame_span=2,
        product_fact_generated=False,field_qualification_granted=False,
        all_current_own_production_queues_enumerated=False,
        future_autonomous_spending_covered=False,repair_and_ability_spending_covered=False,
        native_calls=0,process_writes=0)
