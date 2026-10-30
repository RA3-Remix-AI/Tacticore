"""Explicit trusted file guard and fresh held-handle/native identity checks."""
import copy
import time
import macro_cost_supplier as legacy

class TrustedCostGuard:
    def __init__(self,*,session,file_check,live_check):
        legacy._validate_session(session)
        if not callable(file_check) or not callable(live_check):raise ValueError('cost_guard_trusted_backend_required')
        self.session=session;self.file_check=file_check;self.native_check=live_check
        self.invalidated=False;self.active=None;self.metrics=[];self.counter=0
    def _record(self,kind,operation):
        began=time.perf_counter_ns()
        try:return operation()
        finally:
            self.metrics.append(dict(kind=kind,elapsed_ms=(time.perf_counter_ns()-began)/1000000))
            if len(self.metrics)>128:self.metrics.pop(0)
    def _audit_live(self):
        try:
            observed=self._record('fresh_live_identity',self.native_check)
            legacy._validate_session(observed)
            if observed!=self.session:raise ValueError('cost_guard_process_or_native_identity_changed')
            return observed
        except Exception:self.invalidated=True;raise
    def live_check(self):
        if self.invalidated:raise ValueError('cost_guard_session_epoch_invalidated')
        return self._audit_live()
    def begin(self):
        if self.invalidated:raise ValueError('cost_guard_session_epoch_invalidated')
        if self.active is not None:raise ValueError('cost_guard_nested_window')
        try:
            proof=self._record('complete_files_before',self.file_check)
            if type(proof) is not dict or not proof:raise ValueError('cost_guard_explicit_file_proof_required')
        except Exception:self.invalidated=True;raise
        self.counter+=1;token=(self.counter,copy.deepcopy(proof));self.active=token
        try:self.live_check()
        except Exception:self.active=None;raise
        return token
    def finish(self,token):
        if token is not self.active:raise ValueError('cost_guard_active_token_required')
        error=None;after=None
        try:
            after=self._record('complete_files_after',self.file_check)
            if after!=token[1]:raise ValueError('cost_guard_files_changed')
        except Exception as caught:error=caught;self.invalidated=True
        finally:
            # Always check even a failed financial scan; it must not hide an
            # observed epoch change merely because its outer.finish failed.
            try:self._audit_live()
            except Exception as caught:
                if error is None:error=caught
            self.active=None
        if error is not None:raise error
        return dict(complete_file_guards_equal=True,window_number=token[0],files=after,
            metrics=copy.deepcopy(self.metrics),process_identity_checked_after_files=True)
