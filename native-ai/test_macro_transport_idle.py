import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

path=Path(__file__).resolve().parent/'macro-policy-runtime/client.py'
spec=importlib.util.spec_from_file_location('macro_transport_idle_test_client',path)
client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)

class NativeIdleTests(unittest.TestCase):
    def state(self,**changes):
        value=dict(phase=1,error=0,request=3,ack=3,active=0);value.update(changes)
        return SimpleNamespace(**value)

    def test_transient_callback_busy_waits_before_any_new_request(self):
        state=self.state(active=1)
        def callback_returns(_):state.active=0
        with patch.object(client.time,'sleep',side_effect=callback_returns) as sleep:
            client.wait_native_idle(state)
        self.assertEqual(sleep.call_count,1);self.assertEqual(state.request,3);self.assertEqual(state.ack,3)

    def test_pending_unknown_request_is_never_retried_or_waited_out(self):
        state=self.state(request=4,ack=3,active=1)
        with patch.object(client.time,'sleep') as sleep,self.assertRaisesRegex(ValueError,'not_ready'):
            client.wait_native_idle(state)
        sleep.assert_not_called();self.assertEqual(state.request,4)

    def test_busy_deadline_is_bounded_and_does_not_change_command_fields(self):
        state=self.state(active=1)
        with patch.object(client.time,'monotonic',side_effect=[0,.6]),self.assertRaisesRegex(ValueError,'not_ready'):
            client.wait_native_idle(state)
        self.assertEqual(state.request,3);self.assertEqual(state.ack,3)

    def test_stopped_and_faulted_native_instances_are_rejected(self):
        for changes in (dict(phase=2),dict(error=1)):
            with self.subTest(changes=changes),self.assertRaisesRegex(ValueError,'not_ready'):
                client.wait_native_idle(self.state(**changes))

if __name__=='__main__':unittest.main()
