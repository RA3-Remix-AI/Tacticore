"""Native active attribute nonincreasing cost bound; never an exact quote.

Mirrors only the sign proof for native property 14. All possible native
eligibility subsets are safe if every selected contribution is nonnegative.
It does not invoke getters or dereference an enemy/source game object.
"""
import math
import struct
import macro_cost_observation_v2 as baseline

PINS={5089616: '5153568b318b168b4234578b7a308bd88d3cfb3bc774178b7a308bd38d14fa8b7c24143938741383c0083bc275f55f5eb8020000005b59c20800f30f1040048b7c24188b06f30f11078b4024ba010000003bc2f30f1144240c89542414761583c10c3b01894424147d048d4c24148b1189542414f30f100d0062be000f2fc1721bf30f5cc1f30f2aca33f6f30f59c1f30f11075f8bc65e5b59c20800be010000003bd67e0fd944240cdb442414e8b0f46b00d91f5f8bc65e5b59c20800', 5089808: '83ec100f57c08b442418f30f11442404f30f10050062be0057f30f1100a1e48ccd008bf932c985c0884c2407f30f1144240c750932c05f83c410c20c00538b5f2c558b6850568b77283bf30f84980000003b6e0473688b0e8b118b420483f80e77063b6c873c76568b44242c50568bcfe88bc9ffff84c075458b5424248d4c241c51528bcee8b6feffff85c07514f30f1044241cf30f58442414f30f11442414eb1783f8017517f30f1044241cf30f59442418f30f11442418c64424130183c6103bf3758c8a4c241384c9741cf30f10442414f30f58050062be008b442428f30f59442418f30f11005e5d5b8ac15f83c410c20c00', 7487456: '8b8ed00000008b43e4897c24148bb818040000c1e91af6c101897c2428751980bc24d400000000750f6aff50578bcee8ccb70b0089442414f30f10050062be008b53e4f30f1144242c8b8a6c03000085c974416a008d442430506a0ee8cf69dbff84c0742ff30f1044242c0f2e05308bbe009ff6c4447a0ac7442414ffffff7feb12f30f2a4c2414f30f5ec8f30f2cc9894c2414', 12487472: '00000000'}

def verify_pins(read):
    for at,expected in PINS.items():
        if baseline.baseline.readiness._read(read,at,len(bytes.fromhex(expected)))!=bytes.fromhex(expected):
            raise ValueError('attribute_cost_bound_native_signature_changed')

def inspect_active_cost_bound(read,start,end):
    if end<start or (end-start)%16 or end-start>16384 or bool(start)!=bool(end):
        raise ValueError('attribute_cost_bound_vector_bounds')
    entries=[]
    for entry in range(start,end,16):
        wrapper=baseline.baseline._ptr(baseline.baseline._word(read,entry),4)
        definition=baseline.baseline._ptr(baseline.baseline._word(read,wrapper),0x38)
        # 4da950 follows entry->wrapper->definition, then count+30/array+34.
        count,array=struct.unpack('<II',read(definition+0x30,8))
        if count>128 or count and not array:raise ValueError('attribute_cost_bound_property_array')
        if count:baseline.baseline._ptr(array,count*8)
        matching=[]
        for index in range(count):
            at=array+8*index;kind=baseline.baseline._word(read,at)
            if kind==14:
                value=struct.unpack('<f',read(at+4,4))[0];matching.append(value)
        if len(matching)>1:raise ValueError('attribute_cost_bound_duplicate_property14')
        stack_limit=None
        if matching:
            stack_limit=baseline.baseline._word(read,definition+0x24)
            if stack_limit not in (0,1):raise ValueError('attribute_cost_bound_stacking_context_unknown')
            if not math.isfinite(matching[0]) or matching[0]<1:
                raise ValueError('attribute_cost_bound_can_increase_or_invalid')
        entries.append(dict(entry=hex(entry),wrapper=hex(wrapper),definition=hex(definition),
            native_property_count=count,native_property14_values=matching,stacking_limit=stack_limit,
            branch='property14_absent_native_return2' if not matching else 'nonnegative_additive_divisor_contribution',
            expiry_and_blacklist_not_mirrored=True,eligibility_subset_cannot_violate_lower_bound=True))
    return dict(source='native_current_attribute14_nonincreasing_upper_context_v1',
        entries=entries,entry_count=len(entries),all_active_entries_examined=True,
        native_attribute_divisor_lower_bound=1,native_attribute_upper_context_verified=True,
        native_exact_divisor=None,native_exact_post_attribute_enqueue_quote=None,
        exact_enqueue_quote_verified=False,definition_creation_closure_verified=False,
        observed_active_definition_signs_verified=True,enemy_source_objects_dereferenced=False,
        future_modifier_state_verified=False,field_qualification_granted=False)

class AttributeBoundCostObserver(baseline.NativeCostObserverV2):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);verify_pins(self.read)
    def _attribute_pool(self,read,thing,producer_template):
        evidence=super()._attribute_pool(read,thing,producer_template)
        if evidence['cost_adjustment_absent']:
            return dict(evidence,attribute_upper_context=dict(
                source='native_absent_or_empty_attribute_upper_context_v1',
                native_attribute_divisor_lower_bound=1,native_attribute_upper_context_verified=True,
                all_active_entries_examined=True,entries=[],exact_enqueue_quote_verified=True))
        module=int(evidence['module'],0)
        start,end=struct.unpack('<II',read(module+0x28,8))
        return dict(evidence,attribute_upper_context=inspect_active_cost_bound(read,start,end))
    def sample(self,*args,**kwargs):
        value=super().sample(*args,**kwargs)
        # Keep ordinary_unit_enqueue_cost unknown for any active vector. This
        # adds an upper-bound proof, never relabels the pre-attribute getter.
        return dict(value,schema_version=3,source='native_target_pre_attribute_quote_and_active_cost_upper_context_v3',
            native_getter_quote_is_pre_attribute=True,
            native_attribute_upper_context_verified=value['producer_attribute_evidence']['attribute_upper_context']['native_attribute_upper_context_verified'])
