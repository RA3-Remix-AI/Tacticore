"""Bind rooted own telemetry to the exact live product transport and lawful view."""
import math
import time
from .contracts import ContractError

IDENTITY=('magic','version','size','pid','start_low','start_high','owner','ai','personality','player_template','engine')
def fail():raise ContractError('strategic_unified_observation_binding_changed')

# Read-only witness from the admitted Native5 producer, never a new command.
CALLBACK_CONTROL_FIELDS=('raw_binding','magic','version','size','pid','start_low','start_high','owner','ai',
    'personality','player_template','engine','phase','error','stop','lease_held','hook_held','cleanup_verified',
    'request','ack','kind','gate','frames','wall_ms','result','gates','journal_records','requested_mask',
    'applied_mask','flag_phase','flag_deadline','flag_attempted','not_after_frame')


def _post_tail_callback_witness(transport,initial,telemetry_after,started):
    # The product's completed_native_status brackets its SDK copy with aligned
    # active/serial loads. Cached/model dictionaries cannot supply this witness.
    baseline={key:initial[key] for key in CALLBACK_CONTROL_FIELDS}
    highwater=initial['callback_serial'];last_completed_frame=initial['last_frame'];anchor=None
    if (type(highwater) is not int or not 0<=highwater<0xffffffff
            or type(last_completed_frame) is not int or not 0<=last_completed_frame<=0xffffffff):fail()
    expected_binding=initial['raw_binding']
    def in_time():
        elapsed=time.monotonic_ns()-started
        if not 0<=elapsed<=250_000_000:raise ValueError('unified_control_callback_witness_timeout')
    def one():
        nonlocal highwater
        in_time();s=transport.completed_native_status();in_time()
        if s is None:return None
        serial=s['callback_serial']
        if type(serial) is not int or not highwater<=serial<0xffffffff:fail()
        highwater=serial
        if (s['raw_binding']!=expected_binding or s['magic']!=0x53434735 or s['version']!=5 or s['size']!=1440
                or s['phase']!=1 or s['error']!=0 or s['stop']!=0 or s['lease_held']!=1 or s['hook_held']!=1
                or s['cleanup_verified']!=0 or s['request']!=s['ack']
                or any(s[key]!=value for key,value in baseline.items())):fail()
        if type(s['active']) is not int or s['active'] not in (0,1):fail()
        if any(g['phase'] not in (0,1,4) for g in s['gates']) or s['flag_phase'] not in (0,1,4):fail()
        if type(s['last_frame']) is not int or not 0<=s['last_frame']<=0xffffffff:fail()
        return s
    for _ in range(128):
        # Three separate SDK copies: no mixed active/header/frame generation
        # may become an anchor or a completed-callback witness.
        copies=[one(),one(),one()]
        key=lambda s:(s['callback_serial'],s['last_frame'],s['active'])
        if (all(s is not None and s['active']==0 and s['callback_serial']>0 and s['last_frame']>0 for s in copies)
                and key(copies[0])==key(copies[1])==key(copies[2])):
            current=copies[-1]
            if current['last_frame']<last_completed_frame:fail()
            last_completed_frame=current['last_frame']
            if anchor is None:
                # This anchor is acquired only after the caller's final raw
                # identity tail/revalidation. An old callback is not enough.
                anchor=current
            elif current['callback_serial']>anchor['callback_serial']:
                if current['last_frame']<telemetry_after:fail()
                in_time()
                return dict(anchor_serial=anchor['callback_serial'],anchor_last_frame=anchor['last_frame'],
                    later_serial=current['callback_serial'],later_last_frame=current['last_frame'],
                    stable_status_copies=3,source='strictly_later_completed_admitted_native5_callback',
                    native_guard_side_store_rechecked=False)
        in_time();time.sleep(0.001)
    raise ValueError('unified_control_later_completed_callback_not_observed')


def sample_controls(transport):
    from strategic_expansion_runtime_reader_v2 import SequentialRead,word,pointer
    from read_selected_personality import inspect_player
    from read_script_flags import inspect_flags
    seq=SequentialRead(transport.memory.read,time.monotonic_ns);initial=transport.native_status();b=initial['raw_binding']
    game=pointer(word(seq,0xcd8ce4),0x54);frame=word(seq,game+0x50)
    if game!=b['game'] or not frame or word(seq,0xcdd190)!=b['engine']:fail()
    manager=pointer(word(seq,0xcdd1a0),0x98);people=[]
    if word(seq,manager)!=0xc07ab8:fail()
    for index in range(20):
        player=word(seq,manager+0x48+4*index)
        if player and word(seq,pointer(player)+0x20)==3:people.append(player)
    if people!=[b['owner']] or inspect_player(seq,b['owner'])!=transport.native:fail()
    rows=[]
    for index,(offset,vt,own,enabled) in enumerate(((0x458,0xc5f8f8,0x14,0x1c),(0x4d4,0xc5f484,8,0x10),(0x564,0xc5f440,8,0x10))):
        at=b['ai']+offset;value=seq(at+enabled,1)[0]
        if word(seq,at)!=vt or word(seq,at+own)!=b['owner'] or value not in (0,1):fail()
        rows.append(dict(index=index,enabled=value))
    flags=inspect_flags(seq,transport.manifest['flags']);seq.revalidate()
    after=word(transport.memory.read,game+0x50)
    # The final frame read can yield after the earlier raw revalidation.
    # Recheck only current own metadata; flags/components above stay independent.
    tail_start=len(seq.trace)
    if word(seq,0xcd8ce4)!=game or word(seq,game)!=0xbeb630 or word(seq,0xcdd190)!=b['engine']:fail()
    manager=pointer(word(seq,0xcdd1a0),0x98);people=[]
    if word(seq,manager)!=0xc07ab8:fail()
    for index in range(20):
        player=word(seq,manager+0x48+4*index)
        if player:
            if word(seq,pointer(player))!=0xc5bce0:fail()
            if word(seq,player+0x20)==3:people.append(player)
    identity=inspect_player(seq,b['owner'])
    if people!=[b['owner']] or identity!=transport.native:fail()
    fields=dict(player='owner',ai_player='ai',personality_wrapper='personality',
                personality_data='personality_data',player_template='player_template')
    if any(int(identity[key],0)!=b[field] for key,field in fields.items()):fail()
    # Revalidate the tail without re-reading the earlier changing frame counter.
    for address,size,raw in tuple(seq.trace[tail_start:]):
        if seq(address,size)!=raw:fail()
    # No world/raw read occurs after the final identity tail. A later completed
    # Native callback supplies a frame bound ordered after all those raw reads.
    witness=_post_tail_callback_witness(transport,initial,after,seq.started)
    after=witness['later_last_frame'];elapsed=time.monotonic_ns()-seq.started
    if not 0<=after-frame<=2 or not 0<=elapsed<=250_000_000:raise ValueError('unified_control_sample_incoherent')
    return dict(frame=frame,frame_after=after,components=rows,flags=flags,sequential_reads_revalidated=True,sample_atomic=False,
        post_tail_callback_witness=witness,complete_sample_elapsed_ns=elapsed)

def bind_transport(transport,session):
    state=transport.native_status();own=transport.native
    ticks=session['process_creation_filetime']
    expected=dict(magic=0x53434735,version=5,size=1440,pid=session['pid'],start_low=ticks&0xffffffff,
        start_high=ticks>>32,owner=transport.owner,engine=transport.memory.u32(0xcdd190))
    for key,field in (('ai','ai_player'),('personality','personality_wrapper'),('player_template','player_template')):
        expected[key]=int(own[field],0)
    if (transport.creation!=ticks or transport.manifest['protocol_version']!=5 or len(transport.manifest['flags'])!=10
            or any(type(state.get(k)) is not int or state[k]!=v for k,v in expected.items())):fail()
    return dict(identity=tuple((key,expected[key]) for key in IDENTITY),raw_binding=state['raw_binding'],
        flags=tuple(transport.manifest['flags']))

def validate_sample(sample,view,transport,binding):
    if type(sample) is not dict or 'build_observation' in sample or 'observation' not in sample:fail()
    native=sample['unified_native'];obs=sample['observation'];current=transport.native_status()
    if (native['raw_binding']!=binding['raw_binding'] or current['raw_binding']!=binding['raw_binding']
            or any(type(native.get(k)) is not int or native[k]!=v for k,v in binding['identity'])):fail()
    if any(native.get(k)!=v for k,v in dict(phase=1,error=0,hook_held=1,lease_held=1).items()):fail()
    if native['request']!=native['ack'] or native['applied_mask']&~1023:fail()
    if any(g['phase'] not in (0,1,4) for g in native['gates']):return None
    if native['active'] or current['active'] or any(native[k]!=current[k] for k in ('request','ack','phase','applied_mask','flag_phase','flag_deadline','gates')):return None
    if obs.get('observation_complete') is not True:return None
    controls=sample.get('independent_controls')
    if type(controls) is not dict or controls.get('sequential_reads_revalidated') is not True:fail()
    witness=controls.get('post_tail_callback_witness',{})
    if (witness.get('source')!='strictly_later_completed_admitted_native5_callback'
            or type(witness.get('anchor_serial')) is not int or type(witness.get('later_serial')) is not int
            or not 0<witness['anchor_serial']<witness['later_serial']<0xffffffff
            or witness.get('later_last_frame')!=controls.get('frame_after')
            or type(controls.get('complete_sample_elapsed_ns')) is not int
            or not 0<=controls['complete_sample_elapsed_ns']<=250_000_000
            or not 0<=controls['frame_after']-controls['frame']<=2):fail()
    sealed=obs.get('native5_read_only_binding',{})
    context=dict(pid=transport.session['pid'],process_creation_filetime=transport.creation)
    if (sealed.get('OS_before')!=context or sealed.get('OS_after')!=context
            or sealed.get('session_id')!=transport.session['session_id']):fail()
    flags=controls['flags']['flags']
    if [r['name'] for r in flags]!=list(binding['flags']):fail()
    if any(type(r['present']) is not bool or r['present'] and type(r['value']) is not bool
            or bool(r['present'] and r['value'])!=bool(native['applied_mask']&(1<<i)) for i,r in enumerate(flags)):fail()
    if (obs.get('source')!='native_macro_read_only' or obs.get('native_calls')!=0 or obs.get('process_writes')!=0
            or obs.get('sequential_reads_revalidated') is not True or obs.get('targets_read') is not False
            or obs.get('enemy_details_read') is not False or obs.get('native')!=transport.native
            or obs.get('caller_session_binding')!=dict(pid=transport.session['pid'],process_creation_filetime=transport.creation,
                session_id=transport.session['session_id'])):fail()
    field=view.get('battlefield',{})
    if field.get('visibility_verified') is not True or type(field.get('viewer_player_id')) is not int or field['viewer_player_id']!=3:fail()
    frame=obs.get('frame');after=obs.get('frame_after');seconds=view.get('game_time_seconds')
    if (type(frame) is not int or type(after) is not int or not 0<frame<=after<=frame+2
            or type(seconds) not in (int,float) or not math.isfinite(seconds)):fail()
    frames=(frame,after,controls['frame'],controls['frame_after'])
    if any(type(f) is not int or f<=0 for f in frames):fail()
    if any(abs(seconds*15-f)>15 for f in (*frames,native['last_frame'])):return None
    return frames
