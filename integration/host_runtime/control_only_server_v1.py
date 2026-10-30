"""Native-owned existing-run control pipe, independent of library/credentials.

Only resume/status/stop/diagnostics are admitted. This module cannot initialize
a library, prepare a session, check admission, spawn a Host, or call a model.
The native launcher alone supplies its fixed per-user desktop-runtime path.
"""
import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

from .bridge_service import BridgeService, serve
from .contracts import ContractError
from .desktop_backend import DesktopBackend, NativeHostSpawner

CONTROL_OPERATIONS = frozenset({'run.resume', 'run.status', 'run.stop', 'diagnostics.export'})


@dataclass(frozen=True)
class ExistingRunStateV1:
    # Deliberately no library_path/get_profile/credentials interface.
    state_dir: Path


class NoAdmissionV1:
    def check(self, *_):
        raise ContractError('operation_unsupported')


class HostIdentityOnlyV1:
    identity = staticmethod(NativeHostSpawner.identity)

    def spawn(self, *_):
        raise ContractError('operation_unsupported')


class ExistingRunControlV1:
    def __init__(self, state_dir):
        state = Path(state_dir)
        if not state.is_absolute():
            raise ContractError('local_state_unavailable')
        self.state = state.resolve()
        self.backend = None

    def close(self):
        if self.backend is not None:
            self.backend.close()
            self.backend = None

    def _existing(self):
        if self.backend is None:
            journal = self.state / 'host-runtime.sqlite3'
            launches = self.state / 'desktop-launch-index.sqlite3'
            if not journal.exists() and not launches.exists():
                return None
            if not journal.is_file() or not launches.is_file():
                raise ContractError('run_history_unverifiable')
            # Reuse the real journal/launch/session/STOP binding, release checks,
            # and redacted diagnostics. No synthetic profile is supplied.
            self.backend = DesktopBackend(ExistingRunStateV1(self.state),
                checks=NoAdmissionV1(), spawner=HostIdentityOnlyV1())
        return self.backend

    def run_resume(self, args, request_id):
        backend = self._existing()
        if backend is None:
            # Do not create empty launch ledgers: that would block first use.
            return dict(run=None, observation_only=True, other_unreleased_runs=0)
        return backend.run_resume(args, request_id)

    def _run(self, method, args, request_id):
        backend = self._existing()
        if backend is None:
            raise ContractError('run_not_found')
        return getattr(backend, method)(args, request_id)

    def run_status(self, args, request_id):
        return self._run('run_status', args, request_id)

    def run_stop(self, args, request_id):
        return self._run('run_stop', args, request_id)

    def diagnostics_export(self, args, request_id):
        return self._run('diagnostics_export', args, request_id)


class ControlOnlyServiceV1(BridgeService):
    def __init__(self, state_dir):
        super().__init__(None, ExistingRunControlV1(state_dir))

    def close(self):
        self.backend.close()

    def dispatch(self, operation, args, request_id):
        if operation not in CONTROL_OPERATIONS:
            raise ContractError('operation_unsupported')
        # Existing strict UUID/argument grammar, error projection and response
        # redaction apply unchanged; no WebView path/PID/exec option exists.
        return super().dispatch(operation, args, request_id)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    service = ControlOnlyServiceV1(args.state_dir)
    try:
        serve(service, sys.stdin.buffer, sys.stdout.buffer)
    finally:
        service.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
