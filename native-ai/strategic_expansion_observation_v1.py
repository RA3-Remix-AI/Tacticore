"""Read-only bound stock SimpleExpansion state/runtime and own groups.

Never follows expansion target pointers or reads hidden enemy objects. Scores
are eligibility observations, not adoption; runtime/own movement are separate.
"""
import struct

from macro_group_role_observation import (cache_scores, word, pointer, own_group_members, verify_pins)
from read_selected_personality import inspect_player
from strategic_expansion_runtime_reader_v2 import sample as sample_rooted, verify_pins as verify_root_pins

VTABLE = 0xc60c34
PINS = {0x8d3a64:'82388d00', 0x8d38b1:'e81abdffff',
        0x8cf5fa:'e8e1effdff', 0x8cf616:'c706340cc600',
        0x8d3558:'8b503c',0x8d3562:'8b448a04'}


def sample_runtime(read, address, owner, group, definition):
    # Structural compatibility helper only. Membership is proved separately by
    # sample_rooted; +60 is this runtime's component-local list, not that proof.
    if word(read,address) != VTABLE or word(read,address+0x2c) != owner:
        raise ValueError('expansion_runtime_owner_or_type')
    raw = read(pointer(address,0xa4),0xa4)
    u = lambda offset:struct.unpack_from('<I',raw,offset)[0]
    if u(0x50) != group or u(0x94) != address or u(0x54) != 0:
        raise ValueError('expansion_runtime_state_binding')
    if word(read,group+0x10) != definition or word(read,definition+0x38) != 1:
        raise ValueError('expansion_definition_binding')
    tactic = pointer(word(read,definition+0x3c),68)
    if word(read,tactic+4) != 8:
        raise ValueError('expansion_exact_native_tactic')
    if u(0x58)!=0xc5fe94 or u(0x5c)!=0xc5fe5c or raw[0x14] not in (0,1) or raw[0x30] not in (0,1):
        raise ValueError('expansion_native_runtime_shape')
    link=address+0x60
    if word(read,pointer(u(0x60),8)+4)!=link or word(read,pointer(u(0x64),8))!=link:
        raise ValueError('expansion_runtime_unlinked')
    start,end=u(4),u(8)
    if end<start or end-start>128 or (end-start)%4 or bool(start)!=bool(end):
        raise ValueError('expansion_owned_group_bounds')
    ids=list(struct.unpack('<'+'I'*((end-start)//4),read(pointer(start,end-start),end-start))) if end>start else []
    if len(set(ids))!=len(ids) or 0 in ids:
        raise ValueError('expansion_owned_group_ids')
    owned=[own_group_members(read,ident,owner) for ident in ids]
    if read(address,0xa4)!=raw or word(read,group+0x10)!=definition:
        raise ValueError('expansion_runtime_changed')
    return dict(address=hex(address),state_group=hex(group),native_execution_active=bool(raw[0x14]),
        cleanup_requested=bool(raw[0x30]),owned_groups=owned,targets_read=False,
        native_tactic='SimpleExpansion',native_task_binding_raw=hex(u(0x28)),
        details_owner='native_ai',expansion_completed_verified=False)


class ExpansionObserver:
    def __init__(self,memory,owner,flags):
        self.memory=memory;self.owner=owner;self.native=inspect_player(memory.read,owner)
        self.ai=int(self.native['ai_player'],0);self.flag=next(flag for flag in flags if flag.endswith('_expand'))
        verify_pins(memory.read)
        if any(memory.read(address,len(bytes.fromhex(value)))!=bytes.fromhex(value) for address,value in PINS.items()):
            raise ValueError('expansion_native_abi_signature')
        verify_root_pins(memory.read)

    def sample(self):
        try:
            return sample_rooted(self.memory.read,self.owner,self.ai,self.flag,self.native,
                                 inspect_player,cache_scores,sample_runtime)
        except (ValueError,RuntimeError) as error:
            # Invalid/unproven roots and incoherent reads are unknown, not a
            # negative scan or a reason to resend the intent.
            return dict(frame=None,frame_after=None,observation_complete=False,
                observation_error=str(error),adoption_status='unknown',runtimes=[],state_score=None,
                native_runtime_object_observed=False,native_runtime_observed=False,
                native_execution_active=False,native_adoption_verified=False,
                strategic_success_verified=False,waiting=None,waiting_reason='observation_unknown',
                native_calls=0,process_writes=0,targets_read=False,enemy_details_read=False,
                expansion_completed_verified=False,sample_atomic=False)
