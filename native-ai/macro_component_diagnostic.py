"""Private component/read tracing around a caller-supplied read-only adapter.

No process handles, native calls or game imports. Diagnostics never turn a
failed observation into a fact and must never enter a model-facing context.
"""
import time
import re


def _error(error):
    reason=str(error)[:160]
    static=reason if re.fullmatch(r'(?:readiness|dependency|cost_supplier|payment|macro)_[a-z0-9_]{1,100}',reason) else 'unclassified_component_exception'
    return dict(error_type=type(error).__name__[:80],reason=reason,static_reason_code=static)


class ComponentReadTrace:
    def __init__(self,read,*,maximum_records=256,maximum_raw_bytes=65536):
        if not callable(read):raise TypeError('component_diagnostic_read_required')
        if type(maximum_records) is not int or not 1<=maximum_records<=16000:
            raise ValueError('component_diagnostic_record_bound')
        if type(maximum_raw_bytes) is not int or not 1<=maximum_raw_bytes<=1048576:
            raise ValueError('component_diagnostic_byte_bound')
        self.read=read;self.active=None;self.domains={}
        self.maximum_records=maximum_records;self.maximum_raw_bytes=maximum_raw_bytes

    def _retain(self,state,record,raw=b''):
        # Keep the last N observed reads with their actual returned bytes.
        # Eviction is explicit; a partial trace never claims replay completeness.
        if len(raw)>self.maximum_raw_bytes:
            record.update(raw_omitted=True,returned_bytes=len(raw));raw=b''
            state['trace_complete']=False
        record['raw_hex']=raw.hex();record['captured_bytes']=len(raw)
        while state['reads'] and (len(state['reads'])>=self.maximum_records
                or state['retained_raw_bytes']+len(raw)>self.maximum_raw_bytes):
            dropped=state['reads'].pop(0);state['retained_raw_bytes']-=dropped['captured_bytes']
            state['evicted_records']+=1;state['trace_complete']=False
        state['reads'].append(record);state['retained_raw_bytes']+=len(raw)

    def __call__(self,address,size):
        state=self.domains.get(self.active)
        if state is not None:
            state['read_count']+=1;state['requested_bytes']+=size
            state['last_read']={'address':hex(address),'size':size}
        try:
            raw=self.read(address,size)
            if state is not None:
                record=dict(state['last_read'],sequence=state['read_count'],status='returned')
                if type(raw) is bytes:self._retain(state,record,raw)
                else:
                    record['returned_type']=type(raw).__name__;state['trace_complete']=False
                    self._retain(state,record)
            return raw
        except Exception as error:
            if state is not None:
                state['failed_read']=dict(state['last_read'],**_error(error))
                self._retain(state,dict(state['failed_read'],sequence=state['read_count'],status='failed'))
            raise

    def run(self,domain,operation):
        if self.active is not None:raise ValueError('component_diagnostic_nested_domain')
        if type(domain) is not str or re.fullmatch(r'[a-z][a-z0-9_]{0,63}',domain) is None:
            raise ValueError('component_diagnostic_domain')
        if domain not in self.domains and len(self.domains)>=16:raise ValueError('component_diagnostic_domain_bound')
        state=dict(read_count=0,requested_bytes=0,last_read=None,failed_read=None,reads=[],
            retained_raw_bytes=0,evicted_records=0,trace_complete=True,
            started_monotonic_ns=time.monotonic_ns(),status='running')
        self.domains[domain]=state;self.active=domain
        try:
            value=operation();state.update(status='observed',original_frame=value.get('frame') if type(value) is dict else None)
            return value
        except Exception as error:
            state.update(status='failed',**_error(error))
            raise
        finally:
            state['ended_monotonic_ns']=time.monotonic_ns();self.active=None

    def private_report(self):
        import copy
        return dict(kind='private_read_only_component_diagnostic',schema_version=1,
            domains=copy.deepcopy(self.domains),processes_opened=0,native_calls=0,process_writes=0,
            maximum_records_per_domain=self.maximum_records,maximum_raw_bytes_per_domain=self.maximum_raw_bytes,
            trace_covers_only_explicit_domains=True,
            observation_qualification_granted=False,model_projection_allowed=False)
