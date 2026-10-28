import concurrent.futures
from pathlib import Path
import tempfile
import unittest
import uuid

from host_runtime.contracts import SessionBinding
from host_runtime.journal import CommandJournal, IdentityConflict, JournalError


def uid():
    return str(uuid.uuid4())


class SequenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/'ledger.sqlite'
        self.journal=CommandJournal(self.path)
        self.binding=SessionBinding(1,uid(),3,uid(),1234,'2026-10-26T00:00:00+00:00',uid(),'a'*64,'b'*64)
        self.run=uid(); self.journal.register_run(self.run,self.binding.public())

    def tearDown(self):
        self.journal.close(); self.tmp.cleanup()

    def reserve(self, journal=None, run=None):
        return (journal or self.journal).reserve_command(run or self.run,uid(),'produce',{'unit':'conscript'})

    def test_reopen_reuses_number_and_observed_native_can_advance_high_water(self):
        one=self.reserve(); self.assertEqual(self.journal.reserve_native_sequence(self.run,one['command_id'],4),5)
        self.journal.close(); self.journal=CommandJournal(self.path)
        self.assertEqual(self.journal.get_native_sequence(self.run,one['command_id']),5)
        self.assertEqual(self.journal.reserve_native_sequence(self.run,one['command_id'],99),5)
        two=self.reserve(); self.assertEqual(self.journal.reserve_native_sequence(self.run,two['command_id'],99),100)

    def test_concurrent_connections_allocate_distinct_numbers(self):
        other=CommandJournal(self.path)
        try:
            one=self.reserve(); two=self.reserve(other)
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                futures=[pool.submit(j.reserve_native_sequence,self.run,c['command_id'],0)
                         for j,c in [(self.journal,one),(other,two)]]
                values=[f.result() for f in futures]
            self.assertEqual(set(values),{1,2})
        finally:other.close()

    def test_new_host_run_does_not_reset_same_game_channel(self):
        one=self.reserve(); self.journal.reserve_native_sequence(self.run,one['command_id'],0)
        newrun=uid(); self.journal.register_run(newrun,{**self.binding.public(),'host_id':uid()})
        two=self.reserve(run=newrun)
        self.assertEqual(self.journal.reserve_native_sequence(newrun,two['command_id'],0),2)
        with self.assertRaises(IdentityConflict):
            self.journal.reserve_native_sequence(newrun,one['command_id'],0)

    def test_invalid_high_water_and_exhaustion_are_rejected(self):
        one=self.reserve()
        for value in (-1,True,2**32):
            with self.assertRaises(JournalError):
                self.journal.reserve_native_sequence(self.run,one['command_id'],value)
        with self.assertRaisesRegex(JournalError,'exhausted'):
            self.journal.reserve_native_sequence(self.run,one['command_id'],0xffffffff)

    def test_new_host_identity_cannot_bypass_prior_uncertain_work(self):
        one=self.reserve()
        self.journal.mark_dispatching(self.run,one['request_id'])
        self.journal.record_outcome(self.run,one['request_id'],'uncertain',{'reason_code':'native_timeout'})
        newbinding={**self.binding.public(),'host_id':uid()}
        rows=self.journal.unresolved_for_session(newbinding)
        self.assertEqual([row['command_id'] for row in rows],[one['command_id']])
        changed_game={**newbinding,'game_process_start':'2026-10-26T01:00:00+00:00'}
        self.assertEqual(self.journal.unresolved_for_session(changed_game),[])

    def test_ready_reserve_remains_owned_across_reopen_and_host_identity(self):
        payload = dict(task_id=uid(), lease_id=uid(), generation=1)
        one = self.journal.reserve_command(self.run, uid(), 'reserve', payload)
        self.journal.mark_dispatching(self.run, one['request_id'])
        self.journal.record_outcome(self.run, one['request_id'], 'completed', {'reason_code':'ready_still_held'})
        self.journal.close(); self.journal = CommandJournal(self.path)
        self.assertEqual([r['command_id'] for r in self.journal.unresolved(self.run)], [one['command_id']])
        self.assertEqual(len(self.journal.unresolved_for_session({**self.binding.public(), 'host_id':uid()})), 1)
        release = self.journal.reserve_command(self.run, uid(), 'stop', payload)
        self.journal.mark_dispatching(self.run, release['request_id'])
        self.journal.record_outcome(self.run, release['request_id'], 'released', {'reason_code':'trusted_native_release'})
        self.assertEqual(self.journal.unresolved(self.run), [])
        self.assertEqual(self.journal.unresolved_for_session(self.binding.public()), [])

    def test_other_lease_task_or_generation_release_cannot_clear_owned_reserve(self):
        payload = dict(task_id=uid(), lease_id=uid(), generation=1)
        one = self.journal.reserve_command(self.run, uid(), 'reserve', payload)
        self.journal.mark_dispatching(self.run, one['request_id'])
        self.journal.record_outcome(self.run, one['request_id'], 'completed', {'reason_code':'ready_still_held'})
        for change in (dict(lease_id=uid()), dict(task_id=uid()), dict(generation=2)):
            release = self.journal.reserve_command(self.run, uid(), 'stop', {**payload, **change})
            self.journal.mark_dispatching(self.run, release['request_id'])
            self.journal.record_outcome(self.run, release['request_id'], 'released', {'reason_code':'other_release'})
            self.assertEqual([r['command_id'] for r in self.journal.unresolved(self.run)], [one['command_id']])


if __name__=='__main__':unittest.main()
