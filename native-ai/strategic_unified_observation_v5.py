"""Own strategy telemetry rooted in the actual native tactic manager.

No heap search, native calls, builder queues, target pointers or enemy objects.
Eligibility, active task, own membership and movement remain separate facts.
"""
import copy
import struct
import time
import uuid

from read_selected_personality import inspect_player
from macro_group_role_observation import (cache_scores,native_budget,sample_runtime,
    own_group_members,verify_pins,RUNTIME_VTABLES,SCOUT_RUNTIME_VTABLE)
from strategic_expansion_observation_v1 import sample_runtime as expansion_runtime
from strategic_expansion_runtime_reader_v2 import (SequentialRead,rooted_addresses,
    verify_pins as verify_root_pins,word,pointer,EXPANSION_VTABLE)


def _caller_context(value):
    # These are caller-authenticated facts, not independent OS proof here.
    if type(value) is not dict or set(value)!={'pid','process_creation_filetime','session_id'}:
        raise ValueError('strategic_explicit_caller_binding_required')
    if (type(value['pid']) is not int or not 0<value['pid']<=0xffffffff or
            type(value['process_creation_filetime']) is not int or not 0<value['process_creation_filetime']<=0xffffffffffffffff or
            type(value['session_id']) is not str or str(uuid.UUID(value['session_id']))!=value['session_id']):
        raise ValueError('strategic_caller_binding_invalid')
    return dict(value)


def _check_current_binding(read,owner,ai,identity,expected,inspect_identity):
    if (type(expected) is not dict or set(expected)!={'kind','caller_context','owner','ai','game','engine','identity'} or
            expected.get('kind')!='strategic_own_observer_binding_v1' or
            type(owner) is not int or type(ai) is not int or
            expected.get('owner')!=owner or expected.get('ai')!=ai or expected.get('identity')!=identity):
        raise ValueError('strategic_expected_binding_mismatch')
    _caller_context(expected['caller_context'])
    game=pointer(expected['game'],0x54);engine=pointer(expected['engine'])
    if word(read,0xcd8ce4)!=game or word(read,game)!=0xbeb630 or word(read,0xcdd190)!=engine:
        raise ValueError('strategic_bound_game_or_engine_changed')
    manager=pointer(word(read,0xcdd1a0),0x98)
    if word(read,manager)!=0xc07ab8:raise ValueError('strategic_player_manager_type')
    people=[]
    for index in range(20):
        player=word(read,manager+0x48+4*index)
        if not player:continue
        if word(read,pointer(player))!=0xc5bce0:raise ValueError('strategic_registered_player_type')
        if word(read,player+0x20)==3:people.append(player)
    if people!=[owner]:raise ValueError('strategic_unique_current_own_player')
    if (identity['player_index']!=3 or int(identity['player'],0)!=owner or
            int(identity['ai_player'],0)!=ai or int(identity['instance_id'],0)!=0x799613e0 or
            inspect_identity(read,owner)!=identity):
        raise ValueError('strategic_current_own_identity_changed')


def _finish_binding_sample(seq,actual_read,expected,frame,clock):
    seq.revalidate()
    game_after=word(actual_read,0xcd8ce4)
    engine_after=word(actual_read,0xcdd190)
    frame_after=word(actual_read,expected['game']+0x50)
    # No potentially blocking memory read is allowed after this final clock.
    elapsed=clock()-seq.started
    if (game_after!=expected['game'] or engine_after!=expected['engine'] or
            not 0<=frame_after-frame<=2 or not 0<=elapsed<=250_000_000):
        raise ValueError('strategic_sequential_sample_incoherent')
    return frame_after,elapsed


def seal_own_binding(actual_read,owner,caller_binding,*,clock=time.monotonic_ns,inspect_identity=inspect_player):
    context=_caller_context(caller_binding)
    seq=SequentialRead(actual_read,clock)
    game=pointer(word(seq,0xcd8ce4),0x54);frame=word(seq,game+0x50)
    if not frame:raise ValueError('strategic_no_simulation')
    seq.trace=[]
    identity=inspect_identity(seq,owner);ai=int(identity['ai_player'],0)
    expected=dict(kind='strategic_own_observer_binding_v1',caller_context=context,owner=owner,ai=ai,
                  game=game,engine=pointer(word(seq,0xcdd190)),identity=identity)
    _check_current_binding(seq,owner,ai,identity,expected,inspect_identity)
    _finish_binding_sample(seq,actual_read,expected,frame,clock)
    return copy.deepcopy(expected)


def rooted_sample(actual_read,owner,ai,flags,identity,*,expected_binding,inspect_identity=inspect_player,
                  score_reader=cache_scores,budget_reader=native_budget,
                  runtime_reader=sample_runtime,group_reader=own_group_members,
                  clock=time.monotonic_ns,include_trace=False):
    seq=SequentialRead(actual_read,clock)
    game=pointer(word(seq,0xcd8ce4),0x54);frame=word(seq,game+0x50)
    if not frame:raise ValueError('strategic_no_simulation')
    seq.trace=[]
    _check_current_binding(seq,owner,ai,identity,expected_binding,inspect_identity)
    addresses,root=rooted_addresses(seq,owner,ai)
    strategic=score_reader(seq,ai,flags)
    budgets=score_reader(seq,ai,flags,0xe8,'budget')
    if set(strategic)&set(budgets):raise ValueError('strategic_cache_domain_alias')
    scores={**strategic,**budgets};budget=budget_reader(seq,ai,scores)
    by_group={int(row['group'],0):name for name,row in strategic.items()}
    if len(by_group)!=len(strategic):raise ValueError('strategic_state_alias')
    runtimes=[]
    for address in addresses:
        vt=word(seq,address)
        if vt not in RUNTIME_VTABLES and vt!=EXPANSION_VTABLE:continue
        if word(seq,address+0x2c)!=owner:raise ValueError('strategic_foreign_runtime')
        group=word(seq,address+0x50)
        if group not in by_group:continue
        if len(runtimes)>=16:raise ValueError('strategic_runtime_match_bound')
        flag=by_group[group]
        if vt==EXPANSION_VTABLE:
            if not flag.endswith('_expand'):raise ValueError('strategic_expansion_state_alias')
            row=expansion_runtime(seq,address,owner,group,pointer(word(seq,group+0x10),0x40))
            row.update(group=hex(group),native_tactic_family='simple_expansion')
        else:
            row=runtime_reader(seq,address,owner,set(by_group))
            row['owned_groups']=[group_reader(seq,ident,owner) for ident in row['native_owned_ids_raw']]
            row['object_ids_resolved']=bool(row['owned_groups']) and all(g.get('found') and g.get('all_members_resolved') for g in row['owned_groups'])
            if vt==SCOUT_RUNTIME_VTABLE:row['native_tactic_family']='scout'
            # Do not publish even raw addresses of native target arrays.
            row.pop('target_vector_begin_raw',None);row.pop('target_vector_end_raw',None)
        row.update(flag=flag,authoritative_runtime_membership_verified=True,
            authoritative_runtime_root=root['tactic_manager'],targets_read=False)
        runtimes.append(row)
    _check_current_binding(seq,owner,ai,identity,expected_binding,inspect_identity)
    original=list(seq.trace)
    after,elapsed=_finish_binding_sample(seq,actual_read,expected_binding,frame,clock)
    result=dict(source='native_macro_read_only',native=identity,frame=frame,frame_after=after,
        root=root,state_scores=scores,budget_feedback=budget,runtimes=runtimes,
        construction_feedback=dict(frame=frame,enemy_details_read=False,own_objects=[],
            queue_observed=False,precise_build_observer_requested=False),
        observation_complete=True,sample_atomic=False,sequential_reads_revalidated=True,
        caller_session_binding=copy.deepcopy(expected_binding['caller_context']),actual_OS_identity_verified_by_module=False,
        sample_elapsed_ns=elapsed,native_calls=0,process_writes=0,
        targets_read=False,enemy_details_read=False,strategic_success_verified=False)
    if include_trace:result['ordered_raw_reads']=[dict(address=a,size=n,raw_hex=b.hex()) for a,n,b in original]
    return result


class RootedStrategicObserverV5:
    def __init__(self,memory,owner,flags,*,caller_binding):
        context=_caller_context(caller_binding)
        if type(getattr(memory,'pid',None)) is not int or memory.pid!=context['pid']:
            raise ValueError('strategic_caller_memory_pid_mismatch')
        self.memory=memory;self.owner=owner;self.flags=tuple(flags)
        verify_pins(memory.read);verify_root_pins(memory.read)
        self._expected_binding=seal_own_binding(memory.read,owner,context)
        self.identity=copy.deepcopy(self._expected_binding['identity']);self.ai=self._expected_binding['ai']
    def sample(self,*,include_trace=False):
        try:return rooted_sample(self.memory.read,self.owner,self.ai,self.flags,self.identity,expected_binding=self._expected_binding,include_trace=include_trace)
        except (ValueError,RuntimeError) as error:
            return dict(source='native_macro_read_only',frame=None,observation_complete=False,
                observation_error=str(error),runtimes=[],state_scores={},budget_feedback=None,
                native_calls=0,process_writes=0,targets_read=False,enemy_details_read=False,
                strategic_success_verified=False,sample_atomic=False)
