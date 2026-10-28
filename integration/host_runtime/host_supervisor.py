"""Exclude only this independently identified live control-plane supervisor.

A desktop host_start stays started throughout its process lifetime. That is not
an outstanding game command. Its exact PID/start/binding is checked on every
epoch barrier; no other command or unknown launch is hidden or rewritten.
"""
from dataclasses import dataclass,field
import os

from .contracts import ContractError,SessionBinding

_SEAL=object()


def _identity():
    from battle_host import own_process_identity
    return os.getpid(),own_process_identity()[1]


@dataclass(frozen=True)
class LiveHostSupervisor:
    binding: SessionBinding
    run_id: str
    command_id: str
    pid: int
    start: str
    _seal: object=field(repr=False,compare=False)

    def public(self):
        return dict(run_id=self.run_id,command_id=self.command_id,host_pid=self.pid,host_start_time=self.start)


def verify_supervisor(journal,binding,supervisor):
    if not isinstance(supervisor,LiveHostSupervisor) or supervisor._seal is not _SEAL:
        raise ContractError('native_epoch_live_supervisor_required')
    fields=('session_id','player_id','commander_id','game_process_id','game_process_start','game_sha256','mod_sha256')
    if any(getattr(binding,k)!=getattr(supervisor.binding,k) for k in fields):
        raise ContractError('native_epoch_supervisor_binding_changed')
    pid,start=_identity()
    row=journal.get_command_by_id(supervisor.run_id,supervisor.command_id)
    receipt=row.get('receipt') or {}
    if (row['operation']!='host_start' or row['status']!='started'
            or pid!=supervisor.pid or start!=supervisor.start
            or receipt.get('host_pid')!=pid or receipt.get('host_start_time')!=start):
        raise ContractError('native_epoch_supervisor_process_unverified')


def supervisor_for_host(host):
    runtime=host.runtime_production
    rows=runtime.journal.commands_for_run(runtime.run_id,operation='host_start')
    if not rows:return None
    if len(rows)!=1:raise ContractError('native_epoch_supervisor_ambiguous')
    pid,start=_identity()
    result=LiveHostSupervisor(runtime.binding,runtime.run_id,rows[0]['command_id'],pid,start,_SEAL)
    verify_supervisor(runtime.journal,runtime.binding,result)
    return result


def pending_native_commands(journal,binding,supervisor=None,*,exclude_run_id=None):
    rows=journal.unresolved_for_session(binding.public(),exclude_run_id=exclude_run_id)
    if supervisor is None:return rows
    verify_supervisor(journal,binding,supervisor)
    return [r for r in rows if r['command_id']!=supervisor.command_id]
