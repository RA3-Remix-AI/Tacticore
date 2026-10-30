"""Composable configuration RPC. Existing active bridge source is untouched."""
import uuid
from .bridge_service import BridgeService
from .connection_config_service_v1 import ConnectionConfigServiceV1
from .connection_config_schema_v1 import OPERATIONS
from .contracts import ContractError


class NativeStoppedRunsV1:
    def __init__(self, backend):
        self.backend = backend

    def __call__(self):
        try:
            state = self.backend.run_resume({}, str(uuid.uuid4()))
            if (state.get('observation_only') is not True or type(state.get('other_unreleased_runs')) is not int
                    or state['other_unreleased_runs'] != 0):
                return False
            run = state.get('run')
            return run is None or (type(run) is dict and run.get('state') in ('stopped', 'completed', 'fault', 'result_candidate')
                                   and run.get('native_release_verified') is True)
        except Exception:
            return False


class ConnectionAwareBridgeV1:
    """Fusion candidate; no command other than the old backend is introduced.

    Mutating configuration and admitting a new run share one SQLite barrier.
    Status/stop/diagnostics deliberately remain available during recovery.
    """
    def __init__(self, store, backend, *, registration_path, credentials=None):
        self.base = BridgeService(store, backend)
        self.configuration = None
        try:
            self.configuration = ConnectionConfigServiceV1(store, stopped_guard=NativeStoppedRunsV1(backend),
                registration_path=registration_path, credentials=credentials)
        except Exception:
            # A damaged configuration key cannot disable an existing Host's
            # status/stop/diagnostics. Never regenerate an unauthenticated key.
            pass

    def close(self):
        if self.configuration is not None:
            self.configuration.close()

    def handle(self, request):
        operation = request.get('operation') if type(request) is dict else None
        if type(operation) is str and operation in OPERATIONS:
            if self.configuration is None:
                return dict(schema_version=1, request_id=request.get('request_id'), ok=False,
                            error=dict(code='connection_config_unavailable'))
            result = self.configuration.handle(request)
            if result.get('ok') is True and operation in ('connections.configure', 'connections.recover'):
                # Revalidation still happens on the next check. No existing
                # token is permitted to survive a changed library identity.
                self.base.backend._db.execute('DELETE FROM readiness')
            return result
        if operation not in ('run.check', 'run.start', 'profiles.save', 'session.prepare'):
            return self.base.handle(request)
        if self.configuration is None:
            return dict(schema_version=1, request_id=request.get('request_id'), ok=False,
                        error=dict(code='connection_config_recovery_required'))
        try:
            with self.configuration.admission_barrier():
                return self.base.handle(request)
        except ContractError:
            return dict(schema_version=1, request_id=request.get('request_id'), ok=False,
                        error=dict(code='connection_config_recovery_required'))
        except Exception:
            return dict(schema_version=1, request_id=request.get('request_id'), ok=False,
                        error=dict(code='connection_config_unavailable'))
