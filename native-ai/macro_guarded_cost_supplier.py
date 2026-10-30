"""Versioned pure-file guards outside the unchanged financial clock window."""
import struct
import macro_coherent_registered_cost_supplier as baseline
from macro_cost_identity_guard import TrustedCostGuard

RESEARCH_SCOPE='guarded_registry_live_union_financial_window_research_v3'
PAYER_PINS={8103792: '81ec3c010000f605486bce00015356578bf9751c8b0d3873d000830d486bce00016804d9c400e815051d00a3446bce00a1e48ccd008b48508b47f88b5ff48b90cc030000894c240c8d4ff0895c242c8944241089542420894c2424e880d4f9ff8b47148b90840000008d77148bce89742428ffd284c0740f5f5eb8ffffff3f5b81c43c010000c38b068b5078558bceffd2837b0c008be88b4424148b8818040000896c2440894c24187e098b4c2428e8dc4df5ff8b870401000085c0760983c0ff8987040100008b473485c074128b5424102bd03b531c7607c747340000000080bf250100000175358b4c24148db7c4000000568d9f8800000053e8500df4ff6a3c6a0053e8ee91d1ff6a3c6a0056e8e491d1ff83c418c687250100000085ed0f84200f00008b4424148b8880000000c1e915f6c1010f850a0f0000837c2418000f84f50e0000837d0c010f85810100008b4d10e8a74e020085c08b5c2418757938454e8b57f8895c2444895424488844244c75658b45108b881803000085c974588d54244452e81483d2ff85c0744a8b772885f67443807e65007536837e0c0175308b47f8895c246089442464c6442468008b4e108b891803000085c974138d54246052e8d682d2ff85c0740583f80675428b765885f675bd8b45108b88e0000000c1e90af6c10174468b93181300003b93141300007e388b4c242c8b018b502c55ffd25d5f5eb8010000005b81c43c010000c38b4c242c8b018b502c56ffd25d5f5eb8010000005b81c43c010000c383bf00010000000f85940000008b4ff88b51048b8adc000000c1e90af6c10175128b4c241850e824a8080084c0750432dbeb02b3018b45108b7424188b4e306a0150e86820f2ff84db740484c07552807d4000754c84c00f85b80d00008b0d9c8cce00e8d7e907003bf00f85a50d00008b5424148b0d44b7cd008b81e00000006a006a0083c238528b502852e82eb6d7ff5d5f5eb8010000005b81c43c010000c3837d0c02753b8b751485f674348b460c83782401752b8b4ff856e80feafbff84c0751e8b4c242c8b118b42106a0056ffd05d5f5eb8010000005b81c43c010000c38b4c242855e8a3a1f3ff508bcd89442470e8d79df3ff8b87000100008b35e48ccd0033db85c089442434744468f4c6c100b9808dcd00e8920427008d4c2434518d54242081c6bc000000528bcee83ba3d4ff8b4e088b56048b44241c3b048a74038b58046a01b9808dcd00e80d0527008b442418508bcde84149f5ff84c0755a', 12843404: '70a77b00'}

def verify_payer_pins(read):
    for at,expected in PAYER_PINS.items():
        if baseline.readiness._read(read,at,len(bytes.fromhex(expected)))!=bytes.fromhex(expected):
            raise ValueError('cost_guard_payer_context_signature_changed')

class GuardedCostSupplier:
    def __init__(self,read,*,session,guard,universe,product_scope):
        if type(guard) is not TrustedCostGuard or guard.session!=session or product_scope!=RESEARCH_SCOPE:
            raise ValueError('cost_guard_explicit_trusted_object_required')
        self.guard=guard;self.raw=read;self.session=session
        self.core=baseline.CoherentRegisteredCostSupplier(read,session=session,identity_reader=guard.live_check,
            universe=universe,product_scope=baseline.RESEARCH_SCOPE)
        self.last_observation=None;self.last_partial_observation=None;self.frame_floor=self.core.frame_floor
    def _frame(self):return struct.unpack('<I',baseline.readiness._read(self.raw,self.core.game+0x50,4))[0]
    def observe(self,action,*,game_seconds,component_frames=()):
        self.last_observation=None;self.last_partial_observation=None
        token=self.guard.begin();result=None;error=None
        try:
            verify_payer_pins(self.raw)
            result=self.core.observe(action,game_seconds=game_seconds,component_frames=component_frames)
        except Exception as caught:
            self.last_partial_observation=self.core.last_partial_observation;error=caught
        finally:
            # Financial failure never skips epoch auditing or complete files.
            try:
                proof=self.guard.finish(token)
                verify_payer_pins(self.raw)
                self.guard.live_check()
                after=self._frame()
                if after<self.frame_floor:raise ValueError('cost_guard_session_epoch_frame_regressed')
                self.frame_floor=after
                if result is not None:
                    frames=(result['financial_window_frame'],result['financial_window_frame_after'],*component_frames)
                    if any(not 0<=after-frame<=15 for frame in frames):raise ValueError('cost_guard_financial_candidate_expired')
            except Exception as caught:
                if 'epoch' in str(caught) or 'identity' in str(caught) or 'signature' in str(caught):self.guard.invalidated=True
                error=caught
                if result is not None:self.last_partial_observation=dict(result,
                    final_file_and_live_guards_verified=False,product_fact_eligible=False)
        if error is not None:raise error
        result=dict(result,source='native_guarded_registry_live_union_shared_financial_window_observation_v3',
            schema_version=3,file_guard=proof,guard_verified_current_frame=after,
            pure_file_guards_outside_financial_window=True,payer_context_runtime_pins_verified=True,
            product_fact_eligible=False,product_fact_block_reason='blocked_guarded_cost_field_review_pending')
        self.last_observation=result;return result
    def __call__(self,*args,**kwargs):
        from host_runtime.contracts import ContractError
        raise ContractError('blocked_guarded_cost_field_review_pending')
