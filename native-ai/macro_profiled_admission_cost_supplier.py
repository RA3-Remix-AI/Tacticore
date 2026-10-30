"""Price, complete finance and owned profile in one financial double collect."""
from macro_active_attribute_cost_supplier import ActiveAttributeCostSupplier,RESEARCH_SCOPE as ACTIVE_SCOPE
from read_selected_personality import inspect_player
import macro_readiness_observation as readiness
RESEARCH_SCOPE='profiled_same_window_current_admission_cost_research_v6'
SOURCE='native_profiled_same_window_current_admission_cost_observation_v6'

class ProfiledAdmissionCostSupplier(ActiveAttributeCostSupplier):
    def __init__(self,read,*,session,guard,universe,product_scope):
        if product_scope!=RESEARCH_SCOPE:raise ValueError('profiled_admission_explicit_scope_required')
        super().__init__(read,session=session,guard=guard,universe=universe,product_scope=ACTIVE_SCOPE)
        for at,raw in ((0x8d5727,'89beb0080000'),(0x844a3f,'898690000000')):
            if readiness._read(read,at,len(bytes.fromhex(raw)))!=bytes.fromhex(raw):
                raise ValueError('profiled_admission_identity_signature_changed')
        sample=self.core.payments.sample
        def with_profile():
            window=self.core.reader.current
            if window is None or window.phase!='collecting':raise ValueError('profiled_admission_not_in_financial_collect')
            self._same_window=window
            before=readiness._word(self.core.reader,self.core.game+0x50)
            profile=inspect_player(self.core.reader,self.core.owner)
            after=readiness._word(self.core.reader,self.core.game+0x50)
            if profile['player_index']!=3 or profile['instance_id']!='0x799613e0':
                raise ValueError('profiled_admission_wrong_personality')
            self._profile=profile;self._profile_frames=(before,after)
            return sample()
        self.core.payments.sample=with_profile
        self.last_raw_manifest=None
    def observe(self,*args,**kwargs):
        self._same_window=None;self._profile=None;self.last_raw_manifest=None
        value=super().observe(*args,**kwargs)
        if self._same_window is None or self._same_window.phase!='finished' or self._profile is None:
            raise ValueError('profiled_admission_financial_window_not_complete')
        frames=(*self._profile_frames,value['queue_commitments']['frame'],value['queue_commitments']['frame_after'],
            value['quote']['frame'],value['quote']['frame_after'])
        if any(not value['financial_window_frame']<=frame<=value['financial_window_frame_after'] for frame in frames):
            raise ValueError('profiled_admission_internal_components_outside_window')
        self.last_raw_manifest=[dict(address=hex(at),size=size,first_raw_hex=raw.hex(),final_equal=True)
            for (at,size),raw in self._same_window.copies.items()]
        value=dict(value,source=SOURCE,schema_version=6,native_profile=self._profile,
            internal_financial_component_frames=frames)
        self.last_observation=value;return value
