"""Replay the complete Native7 independent return proof, never scalar fallback."""
import hashlib
import json
from pathlib import Path
import uuid
import struct

KIND='native7_unified_release_v1'


def verified_focus_restoration(proof):
    try:
        native=proof['native'];owned=native['focus'];actual=proof['enemy_focus']
        opponents=actual.get('public_opponent_ids')
        if opponents not in ([4],[4,5]):return False
        maximum_alive_mask=1 if opponents==[4] else 3
        scalars=('phase','baseline_captured','selector','baseline_scheme','target_player','request','manual','isolated',
                 'alive_mask','frame','callback','deadline_frame','call_reservations','ms','deadline_ms')
        if (set(owned)!=set(scalars)|{'priority'} or any(type(owned[key]) is not int
                or not 0<=owned[key]<=(0xffffffffffffffff if key in ('ms','deadline_ms') else 0xffffffff) for key in scalars)
                or type(owned['priority']) is not list or len(owned['priority'])!=2
                or any(type(value) is not int for value in owned['priority'])):return False
        actual_words=('selector','automatic_scheme','manual','isolated','enumeration_lock','priority_p4','priority_p5','alive_mask','own_player_id','native_calls','process_writes')
        if (any(type(actual.get(key)) is not int for key in actual_words)
                or actual.get('source')!='bound_native_enemy_selector_v1' or actual['selector']<0x10000
                or actual['selector']%4 or actual['automatic_scheme']!=2 or actual['manual'] or actual['isolated']
                or actual['enumeration_lock'] or actual['own_player_id']!=3
                or not 0<=actual['alive_mask']<=maximum_alive_mask or actual['native_calls']!=0 or actual['process_writes']!=0
                or actual['enemy_details_read'] is not False or actual['mission_success_verified'] is not False
                or actual['priority_p4']!=int(bool(actual['alive_mask']&1))
                or actual['priority_p5']!=int(bool(actual['alive_mask']&2))):return False
        if not owned['baseline_captured']:
            return all(owned[key]==0 for key in scalars) and owned['priority']==[0,0]
        return (owned['baseline_captured']==1 and owned['phase']==4 and owned['selector']==actual['selector']
            and owned['baseline_scheme']==2 and owned['target_player'] in opponents and 1<=owned['request']<=2048
            and not owned['manual'] and not owned['isolated'] and not owned['deadline_frame'] and not owned['deadline_ms']
            and type(native['callback_serial']) is int and 0<owned['frame']<=proof['frame']
            and 0<owned['callback']<native['callback_serial'] and 0<=owned['alive_mask']<=maximum_alive_mask
            and owned['priority']==[int(bool(owned['alive_mask']&1)),int(bool(owned['alive_mask']&2))]
            and owned['ms']>0 and owned['call_reservations']<=4096)
    except (KeyError,TypeError,ValueError):return False

def verified_journal(raw,native):
    from .native7_journal import verified
    return verified(raw,native)


def verified_proof(proof,*,pid,ticks,session_id,package,flags,closure=None,expected_host_returncode=0):
    # The original contract continues to require an observed, exact helper
    # exit status. Orphan recovery uses a separate, explicitly named contract.
    if not isinstance(proof,dict):return False
    if proof.get('enemy_focus',{}).get('public_opponent_ids')==[4,5]:
        from .native7_release_1v2 import verified_proof as original
        return original(proof,pid=pid,ticks=ticks,session_id=session_id,package=package,
            flags=flags,closure=closure,expected_host_returncode=expected_host_returncode)
    return (proof.get('host_process_ended') is True
        and type(proof.get('host_returncode')) is int
        and proof['host_returncode']==expected_host_returncode
        and _verified_current_restoration(proof,pid=pid,ticks=ticks,session_id=session_id,
            package=package,flags=flags,closure=closure))


def _verified_current_restoration(proof,*,pid,ticks,session_id,package,flags,closure=None):
    """Current Native ownership only; this is not a lifecycle certificate."""
    try:
        native=proof['native'];b=native['binding'];rows=proof['flags']['flags'];components=proof['components'];own=proof['current_own_identity']
        from .native7_journal import wire_binding
        wire_binding(b)
        scalar=dict(magic=0x53434737,version=7,size=4672,phase=2,error=0,active=0,
            applied_mask=0,flag_deadline=0,cleanup_verified=1,hook_held=0,lease_held=0)
        if any(type(native.get(k)) is not int or native[k]!=v for k,v in scalar.items()):return False
        if (native['request']!=native['ack'] or b['pid']!=pid or (b['start_low']|b['start_high']<<32)!=ticks
                or bytes(b['session'])!=uuid.UUID(session_id).bytes or bytes(b['package']).hex()!=package
                or closure is not None and bytes(b['sources']).hex()!=closure):return False
        if any(proof.get(key) is not True for key in ('native_release_verified','sequential_reads_revalidated')):return False
        if native['journal_records']:
            if proof.get('native_durable_journal_verified') is not True:return False
        elif (proof.get('native_durable_journal_verified') is not False or native['request']!=0
                or native['ack']!=0 or native['flag_attempted']!=0 or any(g['baseline_captured'] for g in native['gates'])):return False
        if (proof['semaphore_current']!=1 or proof['semaphore_maximum']!=1
                or proof['native_durable_journal_records']!=native['journal_records']):return False
        identity=dict(pid=pid,process_creation_filetime=ticks)
        if proof['actual_OS_before']!=identity or proof['actual_OS_after']!=identity:return False
        if (type(proof['frame']) is not int or not 0<proof['frame']<=proof['frame_after']<=proof['frame']+2
                or not 0<=proof['ended_monotonic_ns']-proof['started_monotonic_ns']<=250_000_000):return False
        if (int(own['player'],0)!=b['owner'] or int(own['ai_player'],0)!=b['ai'] or own['player_index']!=3
                or int(own['instance_id'],0)!=0x799613e0 or own['store_membership_verified'] is not True
                or own['side_matches_player'] is not True or own['mutations'] is not False
                or int(own['personality_wrapper'],0)!=b['personality'] or int(own['player_template'],0)!=b['player_template']):return False
        if (type(rows) is not list or [r['name'] for r in rows]!=list(flags)
                or any(type(r['present']) is not bool or r['present'] and r['value'] is not False for r in rows)):return False
        if len(components)!=3 or [r['index'] for r in components]!=[0,1,2]:return False
        for index,row in enumerate(components):
            gate=native['gates'][0 if index==0 else 1]
            if (type(row['owned']) is not bool or row['owned']!=bool(gate['baseline_captured']) or type(row['enabled']) is not int or row['enabled'] not in (0,1)
                    or gate['phase'] not in (0,4) or gate['baseline_captured'] not in (0,1)
                    or gate['baseline_captured'] and (gate['phase']!=4 or row['enabled']!=gate['baseline'][index]
                        or row['enabled']!=gate['observed'][index])):return False
        return verified_focus_restoration(proof)
    except (KeyError,TypeError,ValueError,OverflowError):return False

def verified_final(final,proof_path,session,binding,manifest,*,runtime_root,runtime_manifest_sha256):
    try:
        scenario=session['scenario']
        opponents=scenario.get('opponent_player_indices',[4])
        if opponents==[4,5] and scenario.get('participant_count')==3:
            from .native7_release_1v2 import verified_final as original
            return original(final,proof_path,session,binding,manifest,
                runtime_root=runtime_root,runtime_manifest_sha256=runtime_manifest_sha256)
        if opponents!=[4] or scenario.get('participant_count')!=2:return False
        raw=Path(proof_path).read_bytes();proof=json.loads(raw)
        if proof['enemy_focus']['public_opponent_ids']!=opponents:return False
        journal=Path(proof_path).with_name('native-journal.bin').read_bytes()
        b=proof['native']['binding']
        from .native7_journal import decode
        focus_rows=[row['focus'] for row in decode(journal,b) if row['kind']==3]
        owned=proof['native']['focus'];flat=dict(owned)
        priorities=flat.pop('priority');flat.update(priority_p4=priorities[0],priority_p5=priorities[1])
        if bool(focus_rows)!=bool(owned['baseline_captured']) or focus_rows and focus_rows[-1]!=flat:return False
        return (final.get('native_release_contract')==KIND and final['cleanup_verified'] is True
            and final['runtime_root']==str(runtime_root) and final['runtime_manifest_sha256']==runtime_manifest_sha256
            and b['runtime_root']==str(runtime_root) and bytes(b['runtime_manifest']).hex()==runtime_manifest_sha256
            and Path(b['game_image'])==Path(session['game']) and Path(b['deployment'])==Path(session['mod_big'])
            and final['session_id']==binding.session_id and final['pid']==binding.game_process_id
            and final['process_creation_filetime']==session['process_creation_filetime']
            and final['mod_sha256']==binding.mod_sha256 and type(final['unknown_command_ids']) is list
            and len(final['unknown_command_ids'])<=2048 and all(str(uuid.UUID(key))==key for key in final['unknown_command_ids'])
            and type(final['host_returncode']) is int and final['host_returncode']==0
            and final['independent_release_sha256']==hashlib.sha256(raw).hexdigest()
            and final['native_journal_sha256']==hashlib.sha256(journal).hexdigest() and verified_journal(journal,proof['native'])
            and final['raw_native']==proof['native'] and final['independent_flags']==proof['flags']
            and final['independent_enemy_focus']==proof['enemy_focus']
            and verified_proof(proof,pid=binding.game_process_id,ticks=session['process_creation_filetime'],
                session_id=binding.session_id,package=binding.mod_sha256,flags=manifest['flags'],closure=manifest['source_closure_sha256']))
    except (OSError,KeyError,TypeError,ValueError):return False
