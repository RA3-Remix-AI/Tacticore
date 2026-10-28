"""Commit macro dispatch intent before its single native delivery attempt."""
from .contracts import ContractError


class DurableMacroTransport:
    def __init__(self,transport,journal,run_id):
        self.transport=transport;self.session=transport.session;self.journal=journal;self.run_id=run_id

    def apply(self,actions,duration_frames,command_id):
        row=self.journal.reserve_command(self.run_id,command_id,'macro_policy',dict(
            actions=actions,duration_frames=duration_frames,native_command_id=command_id))
        if not row['created']:
            if row['status']=='completed':return row['receipt']
            raise ContractError('macro_durable_dispatch_already_claimed')
        self.journal.mark_dispatching(self.run_id,command_id)
        try:
            native=self.transport.apply(actions,duration_frames,command_id)
        except BaseException:
            self.journal.record_outcome(self.run_id,command_id,'uncertain',dict(reason_code='macro_delivery_unknown'))
            raise
        receipt=dict(seq=native['seq'],native_gate_acknowledged=True,native_effect_verified=False)
        bounds=native.get('native',{})
        begin,deadline=bounds.get('last_frame'),bounds.get('deadline_frame')
        if (actions and type(begin) is int and type(deadline) is int and 0<begin<deadline<=0xffffffff
                and 0<deadline-begin<=duration_frames and deadline-duration_frames>0):
            receipt.update(native_start_frame=deadline-duration_frames,native_deadline_frame=deadline)
        self.journal.record_outcome(self.run_id,command_id,'completed',receipt)
        return receipt

    def close(self):self.transport.close()
