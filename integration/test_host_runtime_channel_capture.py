"""Capture correctness only; local byte buffers cannot supply field evidence."""
import ctypes as c
import unittest
from host_runtime.runtime_channel_capture import capture_bytes
from host_runtime.runtime_evidence import _layout


class ChannelCapture(unittest.TestCase):
    def setUp(self):
        self.l=_layout();self.shared=self.l.SharedChannel()
        self.shared.magic_word=self.l.MAGIC;self.shared.protocol=self.l.VERSION
        self.shared.structure_size=c.sizeof(self.shared);self.shared.token=123
        self.shared.state=5;self.shared.receipt.held=1
        self.shared.events_written=1;self.shared.events[0].ticket=1
        self.shared.traces_written=1;self.shared.traces[0].ticket=1
        self.shared.traces[0].trace.kind=24
        self.bootstrap=bytes(self.shared.bootstrap);self.actor=bytes(self.shared.admitted_actor)
    def read(self,offset,size):return c.string_at(c.addressof(self.shared)+offset,size)
    def capture(self,read=None):return capture_bytes(self.l,read or self.read,self.bootstrap,self.actor,123)
    def test_keeps_original_ticket_bytes_and_unknown_without_grants(self):
        value=self.capture()
        self.assertEqual(bytes(self.shared.events[0]).hex(),value['events'][0]['raw_hex'])
        self.assertEqual(bytes(self.shared.traces[0]).hex(),value['hook_traces'][0]['raw_hex'])
        self.assertEqual(5,value['state']);self.assertEqual(1,value['held'])
        self.assertEqual(0,value['sdk_game_calls']);self.assertFalse(value['ordinary_execution_granted'])
    def test_changed_bootstrap_and_token_are_rejected(self):
        self.shared.bootstrap.experimental_flags=1
        with self.assertRaisesRegex(ValueError,'binding_changed'):self.capture()
        self.shared.bootstrap.experimental_flags=0;self.shared.token=999
        with self.assertRaisesRegex(ValueError,'binding_changed'):self.capture()
    def test_lost_and_missing_tickets_are_not_renumbered(self):
        self.shared.traces_overwritten=1
        with self.assertRaisesRegex(ValueError,'stream_lost'):self.capture()
        self.shared.traces_overwritten=0;self.shared.traces[0].ticket=2
        with self.assertRaisesRegex(ValueError,'slot_unstable'):self.capture()
    def test_torn_slot_is_rejected(self):
        count=0
        def read(offset,size):
            nonlocal count
            raw=self.read(offset,size)
            if offset==self.l.SharedChannel.traces.offset:
                count+=1
                if count==2:return raw[:-1]+bytes([raw[-1]^1])
            return raw
        with self.assertRaisesRegex(ValueError,'slot_unstable'):self.capture(read)
    def test_counter_or_header_changes_are_rejected(self):
        for offset in (self.l.SharedChannel.traces_written.offset,0):
            count=0
            def read(address,size):
                nonlocal count
                raw=self.read(address,size)
                if address==offset:
                    count+=1
                    if count==2:return bytes([raw[0]^1])+raw[1:]
                return raw
            with self.assertRaisesRegex(ValueError,'stream_changed'):self.capture(read)

if __name__=='__main__':unittest.main()
