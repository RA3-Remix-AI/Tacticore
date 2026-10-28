"""One paid Flak left to native AI during an explicit yield diagnostic.

The existing producer's305 total/1000 floor/150 interval remain authoritative.
No lease, Move, attack, native query or replay is issued for the neighbor.
"""
import hashlib
from pathlib import Path
import shutil
import sys
import uuid

from live_state import atomic_json, own_candidates

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tactical/terrain'))
from native_path import NativePathReader


class PaidNativeNeighbor:
    def __init__(self,producer,memory,binding,record,output,*,eligible_phase='ready'):
        if eligible_phase not in ('ready','holding'):
            raise ValueError('native_neighbor_preparation_phase_unverified')
        if (producer.total_budget,producer.reserve_floor,producer.min_interval)!=(305,1000,150):
            raise ValueError('native_neighbor_original_production_limits_required')
        self.producer,self.memory,self.binding,self.record,self.output=producer,memory,binding,record,output
        self.request=None;self.last_path_frame=None
        self.eligible_phase=eligible_phase
        folder=Path(output).parent/'neighbor-path-code';folder.mkdir()
        source=ROOT/'tactical/terrain/native_path.py';target=folder/source.name;shutil.copyfile(source,target)
        self.facts=record['paid_native_neighbor']=dict(unit='flak',budget=220,total_budget=305,
            reserve_floor=1000,min_interval_frames=150,commands=[],path_samples=[],path_rejections={},
            path_reader_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
            eligible_phase=eligible_phase,neighbor_control_commands=0,neighbor_borrowed=False,native_yield_source_verified=False)
        self.reader=NativePathReader(memory)

    def __call__(self,state,sample):
        if state['phase']!=self.eligible_phase or not state.get('held') or sample['team']!=sample['script_team']:
            return
        if self.eligible_phase=='holding' and not (sample.get('settled') is True and sample.get('stance')==2
                and sample.get('state_id')==94 and sample.get('state_vtable')==0xc551a0
                and sample.get('path')==0 and sample.get('command_source')==1
                and type(sample.get('state_flags')) is int and not sample['state_flags']&0xffff):
            return
        status=self.producer.status()
        if self.request is None:
            if status['native_phase']!=1 or status['last_seq']!=1 or status['spent_committed']!=85:
                raise ValueError('native_neighbor_producer_prior_sequence_or_budget_changed')
            first=status['ledger'][0]
            if not (first['completed'] and first['paid_verified'] and first['paid']==85):
                raise ValueError('native_neighbor_original_actor_unpaid')
            earliest=first['enqueue_frame']+150
            self.facts['earliest_production_frame']=earliest
            if sample['frame']<earliest:return
            self.request=dict(session_id=self.binding.session_id,player_id=3,commander_id=self.binding.commander_id,
                command_id=str(uuid.uuid4()),task_id=str(uuid.uuid4()),seq=2,unit='flak',budget=220,reserve=1000,
                expires_frame=sample['frame']+300)
            # Durable intent precedes the one producer submission. Unknown
            # delivery is preserved; no subsequent tick can resend it.
            self.facts['commands'].append(dict(command=self.request,delivery='pending'))
            atomic_json(self.output,self.record)
            receipt=self.producer.submit(self.request)
            self.facts['commands'][0].update(delivery='responded',receipt=receipt)
            atomic_json(self.output,self.record)
            if not receipt.get('accepted'):
                raise ValueError('native_neighbor_production_refused_no_replay')
            return
        row=next((r for r in status['ledger'] if r['command_id']==self.request['command_id']),None)
        if row is None:return
        self.facts['last_production_receipt']=row
        if row.get('status') in ('rejected','failed','unknown'):
            raise ValueError('native_neighbor_production_failed_or_unknown_no_replay')
        if not row.get('completed'):return
        if not (row.get('paid_verified') and row.get('paid')==220 and row.get('created') and row.get('object_id')):
            raise ValueError('native_neighbor_paid_birth_unverified')
        if len(self.facts['path_samples'])>=12:return
        try:
            census=own_candidates(self.memory,3,{})
            frame=census['frame_start']
            if frame!=census['frame_end'] or (self.last_path_frame is not None and frame<self.last_path_frame+5):return
            self.last_path_frame=frame
            actor=next((x for x in census['candidates'] if x['object_id']==row['object_id']),None)
            if actor is None or int(actor['type_hash'],0)!=0x2c358c61:
                raise ValueError('native_neighbor_not_in_current_own_list')
            path=self.reader.sample(actor,frame)
            self.facts['path_samples'].append(path)
        except (ValueError,RuntimeError,OSError,KeyError) as error:
            code=str(error) if isinstance(error,ValueError) else type(error).__name__
            reasons=self.facts['path_rejections'];reasons[code]=reasons.get(code,0)+1
        atomic_json(self.output,self.record)
