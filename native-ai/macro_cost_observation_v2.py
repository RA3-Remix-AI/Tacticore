"""Versioned quote reader with the actual AttributeModifier module layout.

Legacy source stays frozen. This parser calls no native functions and grants
no execution qualification. Active modifiers remain explicitly unknown.
"""
import struct
import macro_cost_observation as baseline

ATTRIBUTE_POOL_VTABLE=0xbe9748
PINS={5135168: '8b442408535556578bf18b4c241450518bcee8a916ffffc74624408ebe00c7064897be00c7460c1896be00c746100896be00c74624fc95be0033c033db895e28895e2c895e3089463c89464089464489464889464c89465089465489465889465c89466089466489466889466c894670894674889eb40000008b6e288b7e2c555757e8699b1f002bfdc1ff04f7dfc1e70483c40c017e2cc74638ffffff3f8d4678b90f0000008958c4891883c00483e90175f38b560868ffffff3f528d4e10e8fc581f005f8bc65e5d5bc2', 5075456: '8b442408568bf18b4c240850518bcee8ec833000c7460c388bbe008b4608894620c746102093be00c746140000000083c9ff894e18894e1cc7066094be00c7460c3093be00c74610008ebe008bc65ec20800', 8254976: '8b442408568bf18b4c240885c9894604c70658eac40074108b118b4208ffd08946088bc65ec2080033c08946088bc65ec20800', 7985804: '8b178b42108bcfffd03b05286ace00750c5e89bd6c0300005f5dc20400', 5090160: 'b8a097be00c3', 12490568: 'f0dd4d00a0f85f0070ab4d00c08f4e0080ab4d00'}

PINS.update({12901224: 'e0565400', 5527264: '8bc1c3'})

class NativeCostObserverV2(baseline.NativeCostObserver):
    def __init__(self,read,owner,*,executable_sha256,expected_owner_index):
        super().__init__(read,owner,executable_sha256=executable_sha256,expected_owner_index=expected_owner_index)
        for at,expected in PINS.items():
            if baseline.readiness._read(read,at,len(bytes.fromhex(expected)))!=bytes.fromhex(expected):
                raise ValueError('cost_v2_attribute_module_signature_changed')

    def _attribute_pool(self,read,thing,producer_template):
        pool=baseline._word(read,thing+0x36c)
        if not pool:return dict(cost_adjustment_absent=True,branch='native_absent_attribute_pool')
        baseline._ptr(pool,0xb5)
        # 4e5b40 -> 4d7200 -> 7df600: ordinary Module base fields are
        # definition+4 and Thing+8. +38 is a scheduler value, never the owner.
        if baseline._word(read,pool)!=ATTRIBUTE_POOL_VTABLE or baseline._word(read,pool+8)!=thing:
            raise ValueError('cost_v2_attribute_module_identity')
        definition=baseline._ptr(baseline._word(read,pool+4),4)
        vector=baseline._ptr(baseline._word(read,thing+0x310),4);matches=0
        for index in range(256):
            module=baseline._word(read,vector+index*4)
            if not module:break
            if module==pool:matches+=1
        else:raise ValueError('cost_v2_attribute_module_vector_unterminated')
        if matches!=1:raise ValueError('cost_v2_attribute_module_membership')
        start,end=struct.unpack('<II',read(pool+0x28,8))
        if end<start or (end-start)%16 or end-start>16384 or bool(start)!=bool(end):
            raise ValueError('cost_v2_attribute_pool_bounds')
        return dict(cost_adjustment_absent=start==end,
            branch='native_empty_attribute_vector' if start==end else 'active_attribute_vector_not_mirrored',
            entry_count=(end-start)//16,module=hex(pool),module_definition=hex(definition),
            native_module_owner_verified=True,native_module_vector_membership_verified=True,
            layout_source='attribute_modifier_module_4e5b40_v2')

    def sample(self,*args,**kwargs):
        result=super().sample(*args,**kwargs)
        result.update(schema_version=2,source='native_read_only_current_target_quote_v2')
        return result
