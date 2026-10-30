"""Replay the complete Native5 independent return proof, never scalar fallback."""
import hashlib
import json
from pathlib import Path
import uuid
import struct

KIND='strategic_unified_release_v5'

def verified_journal(raw,native):
    """Fixed actual i386 Native5 layout, independently from ctypes imports."""
    try:
        b=native['binding'];count=native['journal_records']
        if type(count) is not int or not 0<=count<=4096 or len(raw)!=count*1360:return False
        expected=struct.pack('<11I',*(b[k] for k in ('pid','thread','start_low','start_high','owner','ai','personality','personality_data','player_template','game','engine')))
        expected+=b''.join(bytes(b[k]) for k in ('session','lease','package','sources'))
        name=b['deployment'].encode('utf-16-le')+b'\0\0'
        if len(name)>1040:return False
        expected+=name.ljust(1040,b'\0')
        for index in range(count):
            record=raw[index*1360:(index+1)*1360];magic,version,seq,size,kind,_,_=struct.unpack_from('<7I',record)
            if ((magic,version,seq,size)!=(0x53434735,5,index+1,1360) or kind not in (1,2)
                    or record[28:1208]!=expected or struct.unpack_from('<I',record,1352)[0]!=0x454e4435):return False
        return True
    except (KeyError,TypeError,ValueError,struct.error,OverflowError):return False

def verified_proof(proof,*,pid,ticks,session_id,package,flags,closure=None,expected_host_returncode=0):
    # The original contract continues to require an observed, exact helper
    # exit status. Orphan recovery uses a separate, explicitly named contract.
    if not isinstance(proof,dict):return False
    return (proof.get('host_process_ended') is True
        and type(proof.get('host_returncode')) is int
        and proof['host_returncode']==expected_host_returncode
        and _verified_current_restoration(proof,pid=pid,ticks=ticks,session_id=session_id,
            package=package,flags=flags,closure=closure))


def _verified_current_restoration(proof,*,pid,ticks,session_id,package,flags,closure=None):
    """Current Native ownership only; this is not a lifecycle certificate."""
    try:
        native=proof['native'];b=native['binding'];rows=proof['flags']['flags'];components=proof['components'];own=proof['current_own_identity']
        scalar=dict(magic=0x53434735,version=5,size=1440,phase=2,error=0,active=0,
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
        return True
    except (KeyError,TypeError,ValueError,OverflowError):return False

def verified_final(final,proof_path,session,binding,manifest):
    try:
        raw=Path(proof_path).read_bytes();proof=json.loads(raw)
        journal=Path(proof_path).with_name('native-journal.bin').read_bytes()
        return (final.get('native_release_contract')==KIND and final['cleanup_verified'] is True
            and final['session_id']==binding.session_id and final['pid']==binding.game_process_id
            and final['process_creation_filetime']==session['process_creation_filetime']
            and final['mod_sha256']==binding.mod_sha256 and final['unknown_command_ids']==[]
            and type(final['host_returncode']) is int and final['host_returncode']==0
            and final['independent_release_sha256']==hashlib.sha256(raw).hexdigest()
            and final['native_journal_sha256']==hashlib.sha256(journal).hexdigest() and verified_journal(journal,proof['native'])
            and final['raw_native']==proof['native'] and final['independent_flags']==proof['flags']
            and verified_proof(proof,pid=binding.game_process_id,ticks=session['process_creation_filetime'],
                session_id=binding.session_id,package=binding.mod_sha256,flags=manifest['flags'],closure=manifest['source_closure_sha256']))
    except (OSError,KeyError,TypeError,ValueError):return False
