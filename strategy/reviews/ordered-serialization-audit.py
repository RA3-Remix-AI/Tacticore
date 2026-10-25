"""Offline immutable failure forensics; no production imports/process access."""
import ctypes
import hashlib
import io
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'acceptance/runs/20261025-004819-commander'


def diagnostic_vectors(event):
    """Reference only: diagnostic nulls retain explicit validity, never geometry."""
    result={};invalid=[]
    for key,value in event.items():
        if isinstance(value,ctypes.Array):value=list(value)
        if key in ('requested','effective'):
            bad=[index for index,item in enumerate(value) if type(item) not in (int,float) or not math.isfinite(item)]
            if bad:
                invalid.extend(f'{key}[{index}]' for index in bad)
                value=[None if index in bad else item for index,item in enumerate(value)]
        result[key]=value
    result['diagnostic_invalid_fields']=invalid
    return result


def valid_xyz(vector):
    return isinstance(vector,list) and len(vector)==3 and all(type(value) in (int,float) and math.isfinite(value) for value in vector)


def main():
    raw_path=RUN/'ordered-ak01.json';temporary=RUN/'ordered-ak01.json.tmp';recovery=RUN/'ordered-ak01-recovery-readonly.json'
    raw=json.loads(raw_path.read_text(encoding='utf-8-sig'));recovered=json.loads(recovery.read_text(encoding='utf-8-sig'))['native'];temp=temporary.read_bytes()
    example={'seq':1,'requested':(ctypes.c_float*3)(0,0,0),'effective':(ctypes.c_float*3)(0,0,0)}
    out=io.StringIO();error=None
    try:json.dump(example,out,indent=2,allow_nan=False)
    except TypeError as exc:error=str(exc)
    assert error=='Object of type c_float_Array_3 is not JSON serializable'
    assert out.getvalue().endswith('"requested": ')
    assert temp.endswith(b'"requested": ')
    events=recovered['events'];assert all(valid_xyz(event['requested']) and valid_xyz(event['effective']) for event in events)
    corrected=diagnostic_vectors(example);json.dumps(corrected,allow_nan=False);assert corrected['diagnostic_invalid_fields']==[]
    for special in (float('nan'),float('inf'),float('-inf')):
        synthetic=dict(example,requested=(ctypes.c_float*3)(1,special,3));value=diagnostic_vectors(synthetic)
        json.dumps(value,allow_nan=False);assert value['requested']==[1,None,3] and value['diagnostic_invalid_fields']==['requested[1]']
        assert not valid_xyz(value['requested'])  # A nullable diagnostic vector is never valid geometry.
        try:json.dumps(dict(target=[1,special,3]),allow_nan=False)
        except ValueError:pass
        else:raise AssertionError('Nonfinite actual target accepted')
    for invalid in ([1,None,3],[1,True,3],[1,float('nan'),3],[1,2]):assert not valid_xyz(invalid)
    assert valid_xyz([1,2,3])
    result=dict(source='offline_immutable_reports_and_stdlib_reproduction',game_or_api_access=False,
        original_report=dict(sha256=hashlib.sha256(raw_path.read_bytes()).hexdigest(),status=raw['status'],phase=raw['native']['phase'],event_count=len(raw['events'])),
        truncated_temporary=dict(sha256=hashlib.sha256(temp).hexdigest(),byte_length=len(temp),trailing_key='events[0].requested',value_start_byte=len(temp),tail=temp[-45:].decode('utf-8')),
        failure_reproduction=dict(type='TypeError',message=error,finite_zero_ctypes_array_fails=True,second_dump_same_record_also_fails=True),
        recovered_diagnostics=[dict(seq=e['seq'],kind=e['kind'],requested=e['requested'],effective=e['effective']) for e in events],
        recovered_terminal={key:recovered[key] for key in ('phase','error','restore_mask','active','issued_frame','returned_frame','detach_calls','attack_calls','return_calls','stop_requested','timer')},
        conclusion='ctypes float arrays, not nonfinite values, explain this exact first requested-field failure; native never issued/detached. Diagnostic normalization still needs explicit invalid metadata; nullable vectors cannot satisfy geometry.',
        capabilities_granted=[])
    destination=Path(__file__).with_name('ordered-ak01-serialization-independent.json');destination.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
