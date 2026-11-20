"""Host start context and the STOP / return contract for the native runtime.

STOP asks the DLL to restore the native AI's original settings; the SDK then
reads the actual state once (native_release). Unknown deliveries are never
replayed: they are only settled by that verified return.
"""
from pathlib import Path

from .contracts import ContractError
from .native_paths import NativePaths
from .native_runtime_contract import read, sha

KIND = 'native_host_context_v2'
CONTEXT = 'native-context.json'


def report_directory(session):
    return NativePaths.current().report(session['session_id'])


def freeze(host):
    """Record what this Host runs against; no source copies or later replay."""
    from .desktop_backend import _atomic
    scope = host.native_scope
    _atomic(host.output / 'profile.json', host.profile)
    _atomic(host.output / CONTEXT, dict(kind=KIND, run_id=host.run_id, binding=host.binding.public(),
        runtime_root=str(scope.runtime_root), runtime_manifest_sha256=scope.runtime_manifest_sha256,
        report=str(report_directory(host.session)), session_sha256=sha(host.args.session)))


def unknown_before_stop(journal, run_id, stop):
    """Uncertain strategic deliveries made before STOP; settled only by return."""
    rows = []
    for row in journal.unresolved(run_id):
        if row['request_id'] == 'macro-stop' or row['operation'] == 'host_start':
            continue
        if row['status'] != 'uncertain' or row['created_at'] > stop['created_at']:
            return None
        rows.append(row)
    return rows


def unresolved_ownership(backend, row, status):
    """Outstanding control of a run; deliveries settled by a verified return excluded."""
    if status.get('history_archived') is True:
        return []
    unresolved = backend.journal.unresolved(row['run_id'])
    if not unresolved or status.get('native_release_verified') is not True:
        return unresolved
    stop = backend.journal.get_command(row['run_id'], 'macro-stop')
    return [] if unknown_before_stop(backend.journal, row['run_id'], stop) is not None else unresolved


def finish(host):
    from .desktop_backend import _atomic
    from .native_release import KIND as RELEASE_KIND, verified_final
    stop = host.journal.reserve_command(host.run_id, 'macro-stop', 'macro_policy_stop',
                                        dict(binding_hash=host.binding.binding_hash))
    if not stop['created']:
        raise ContractError('macro_stop_already_claimed')
    host.journal.mark_dispatching(host.run_id, 'macro-stop')
    try:
        if host.transport is None:
            from .native_no_attachment import capture, KIND as contract
            proof = capture(host.sampler.memory if host.sampler else None, host.session, host.binding, host.run_id)
            path = host.output / 'native-no-attachment.json'
            _atomic(path, proof)
            publication = dict(native_release_contract=contract, no_attachment_sha256=sha(path))
            verified = True
        else:
            if host.controller:
                host.controller.stop()
            else:
                host.transport.close()
            path = report_directory(host.session) / 'final-state.json'
            final = read(path)
            verified = verified_final(final, path.with_name('independent-release.json'), host.session, host.binding)
            stop = host.journal.get_command(host.run_id, 'macro-stop')
            verified = verified and unknown_before_stop(host.journal, host.run_id, stop) is not None
            publication = dict(native_release_contract=RELEASE_KIND, final_state_sha256=sha(path),
                               independent_release_sha256=final['independent_release_sha256'])
        proof = dict(kind='macro_policy_native_release', binding=host.binding.public(), run_id=host.run_id,
            host_pid=host.host_pid, host_start_time=host.host_start, native_release_verified=verified, **publication)
        _atomic(host.output / 'macro-release.json', proof)
        host.journal.record_outcome(host.run_id, 'macro-stop', 'released' if verified else 'uncertain', dict(
            binding_hash=host.binding.binding_hash, host_pid=host.host_pid, host_start_time=host.host_start,
            native_release_verified=verified, release_sha256=sha(host.output / 'macro-release.json'), **publication))
        if not verified:
            raise ContractError('macro_stop_unverified')
        if getattr(host, 'strategy_runtime', None) is not None:
            at = host.latest['game_time_seconds']
            if host.transport:
                at = max(at, host.transport.native_status()['last_frame'] / 15)
            host.strategy_runtime.finish(at, release_verified=True)
    except BaseException:
        if host.journal.get_command(host.run_id, 'macro-stop')['status'] == 'dispatching':
            host.journal.record_outcome(host.run_id, 'macro-stop', 'uncertain', dict(native_release_verified=False))
        raise


def verified_return(backend, row, binding, host_receipt):
    """The Host recorded a verified return for exactly this run and process."""
    try:
        output = Path(row['output_path'])
        stop = backend.journal.get_command(row['run_id'], 'macro-stop')
        receipt = stop['receipt'] or {}
        release = read(output / 'macro-release.json')
        same_host = all(release.get(key) == host_receipt.get(key) == receipt.get(key)
                        for key in ('host_pid', 'host_start_time'))
        return (stop['status'] == 'released' and receipt.get('native_release_verified') is True
                and release.get('native_release_verified') is True and release.get('run_id') == row['run_id']
                and release.get('binding') == binding.public() and receipt.get('binding_hash') == binding.binding_hash
                and receipt.get('release_sha256') == sha(output / 'macro-release.json') and same_host
                and unknown_before_stop(backend.journal, row['run_id'], stop) is not None)
    except (OSError, ValueError, KeyError, TypeError, ContractError):
        return False
