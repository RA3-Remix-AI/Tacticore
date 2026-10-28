"""A diagnostic neighbor has one durable producer intent and no control lease."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from native_neighbor import PaidNativeNeighbor


class Producer:
    total_budget=305;reserve_floor=1000;min_interval=150
    def __init__(self):self.calls=[];self.fail=False
    def status(self):return dict(native_phase=1,last_seq=1,spent_committed=85,
        ledger=[dict(completed=True,paid_verified=True,paid=85,enqueue_frame=100,command_id='first')])
    def submit(self,request):
        self.calls.append(request)
        if self.fail:raise TimeoutError('delivery_unknown')
        return dict(accepted=True)


class NativeNeighborTests(unittest.TestCase):
    def make(self,directory,producer,**options):
        record={};binding=SimpleNamespace(session_id='s',commander_id='c')
        return PaidNativeNeighbor(producer,object(),binding,record,Path(directory)/'trial.json',**options),record

    def test_native_interval_then_exactly_one_request_with_original_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Producer();tick,record=self.make(directory,p)
            ready=dict(phase='ready',held=True);sample=dict(frame=249,team=20,script_team=20)
            tick(ready,sample);self.assertEqual([],p.calls)
            sample['frame']=250;tick(ready,sample);tick(ready,sample)
            self.assertEqual(1,len(p.calls));self.assertEqual((2,'flak',220,1000),tuple(p.calls[0][k] for k in ('seq','unit','budget','reserve')))
            self.assertEqual(0,record['paid_native_neighbor']['neighbor_control_commands'])

    def test_unknown_delivery_is_never_submitted_again(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Producer();p.fail=True;tick,record=self.make(directory,p)
            ready=dict(phase='ready',held=True);sample=dict(frame=250,team=20,script_team=20)
            with self.assertRaises(TimeoutError):tick(ready,sample)
            tick(ready,sample)
            self.assertEqual(1,len(p.calls));self.assertEqual('pending',record['paid_native_neighbor']['commands'][0]['delivery'])

    def test_no_production_after_release_or_uncertain_or_wrong_team(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Producer();tick,_=self.make(directory,p)
            for phase,held,team in [('released',False,18),('uncertain',True,20),('ready',True,18)]:
                tick(dict(phase=phase,held=held),dict(frame=250,team=team,script_team=20))
            self.assertEqual([],p.calls)

    def test_intercept_neighbor_waits_for_actual_owned_target_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Producer();tick,_=self.make(directory,p,eligible_phase='holding')
            sample=dict(frame=250,team=20,script_team=20,settled=True,stance=2,state_id=94,
                state_vtable=0xc551a0,path=0,command_source=1,state_flags=0x10000)
            tick(dict(phase='ready',held=True),sample)
            bad=dict(sample,path=0x1234);tick(dict(phase='holding',held=True),bad)
            self.assertEqual([],p.calls)
            tick(dict(phase='holding',held=True),sample)
            self.assertEqual(1,len(p.calls))


if __name__=='__main__':unittest.main()
