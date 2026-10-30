"""Failure telemetry/probe tests; no protected profile loads or networking."""
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'strategy'),str(ROOT/'agent_runtime/src')]
from host_runtime.application import safe_backend_diagnostics,observe_applied_backend,apply_commander_draft,create_applied_backend
from test_host_runtime_application import profile,draft,context
import probe_archived_macro_backend as cli

SECRET='PRIVATE-ENDPOINT-RAW-RESPONSE-KEY'


class Diagnostics(unittest.IsolatedAsyncioTestCase):
    async def test_success_recomputes_safe_shapes_instead_of_backend_raw_diagnostics(self):
        from test_macro_strategy_pydantic import archived_requests
        _,contexts=archived_requests();ctx=contexts[0]
        class Backend:
            last_diagnostics={'untrusted':SECRET}
            async def __call__(self,_):
                return {'macro_actions':[{'action':'budgeteconomy',SECRET:SECRET}],'macro_production':None}
        events=[]
        b=observe_applied_backend(Backend(),apply_commander_draft(profile(),draft()),
            event_sink=lambda k,p:events.append((k,p)))
        await b(ctx)
        diag=events[-1][1]['response_diagnostics']
        self.assertEqual(diag['macro_actions']['validation_code'],'macro_policy_actions')
        self.assertEqual(diag['macro_actions']['item_type_counts'],{'object':1})
        self.assertNotIn(SECRET,json.dumps(events));self.assertNotIn('untrusted',diag)

    async def test_failure_projects_only_fixed_codes_and_numeric_counters(self):
        class Failing:
            last_error_code='input_budget_exceeded'
            metrics={'attempts':1,'timeouts':0,'responses':False,'max_request_bytes':16385,'key':SECRET,'retries':-1}
            async def __call__(self,_): raise ValueError(SECRET)
        events=[]
        b=observe_applied_backend(Failing(),apply_commander_draft(profile(),draft()),
            event_sink=lambda k,p:events.append((k,p)))
        with self.assertRaises(ValueError): await b(context())
        expected={'error_code':'input_budget_exceeded','transport_metrics':{'attempts':1,'timeouts':0,'max_request_bytes':16385}}
        self.assertEqual(events[-1][1]['backend_diagnostics'],expected)
        self.assertEqual(b.observation()['failure_diagnostics'],expected)
        self.assertNotIn(SECRET,json.dumps(events))
        self.assertFalse(b.observation()['model_response_received'])

    async def test_unknown_and_malicious_codes_and_metric_values_are_not_exported(self):
        for code in [SECRET,'http_status_999','http_status_200\n'+SECRET,[],None]:
            d=safe_backend_diagnostics(SimpleNamespace(last_error_code=code,metrics={'attempts':True,'responses':2**60,'max_request_bytes':SECRET}))
            self.assertEqual(d,{'error_code':None,'transport_metrics':{}})
        for code in ['http_status_401','http_status_503','framework_request_failed']:
            self.assertEqual(safe_backend_diagnostics(SimpleNamespace(last_error_code=code))['error_code'],code)

    async def test_cancel_keeps_cancellation_semantics_and_no_failure_claim(self):
        class Cancel:
            async def __call__(self,_): raise asyncio.CancelledError()
        b=observe_applied_backend(Cancel(),apply_commander_draft(profile(),draft()))
        with self.assertRaises(asyncio.CancelledError): await b(context())
        self.assertIsNone(b.observation()['failure_diagnostics'])
        self.assertEqual(b.observation()['stage'],'call_cancelled')


class Probe(unittest.IsolatedAsyncioTestCase):
    def fixture(self,folder):
        import fixtures
        archived=ROOT/'acceptance/runs/desktop-4222c48d-0de5-4bdd-aea9-956845365854/battle-host/host-events.jsonl'
        if not archived.is_file():
            raise unittest.SkipTest('requires the local historical provider-context archive')
        # A public context fixture only; no provider or credential metadata.
        with archived.open(encoding='utf8') as stream:
            c=next(json.loads(line)['context'] for line in stream if json.loads(line).get('kind')=='model_macro_request_context')
        c['commander_id']=fixtures.COMMANDER
        encoded=json.dumps(c,ensure_ascii=False,separators=(',',':')).encode()
        events=Path(folder)/'host-events.jsonl'
        events.write_text(json.dumps({'kind':'model_macro_request_context','sequence':1,'context':c,
            'context_bytes':len(encoded),'context_sha256':hashlib.sha256(encoded).hexdigest()},ensure_ascii=False)+'\n',encoding='utf8')
        applied=apply_commander_draft(profile(),draft())
        (Path(folder)/'profile.json').write_text(json.dumps({'effective':{'effective_hash':applied.effective.effective_hash}}),encoding='utf8')
        return events,applied

    async def test_real_factory_sdk_one_call_exports_only_shape_and_safe_diagnostics(self):
        import httpx2
        calls=[]
        async def handle(req):
            calls.append(len(req.content))
            return httpx2.Response(200,json={'id':'fixture','object':'chat.completion','created':1,'model':'fixture',
                'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':json.dumps({SECRET:SECRET})}}]})
        original=create_applied_backend
        def factory(applied,**kwargs): return original(applied,transport=httpx2.MockTransport(handle),**kwargs)
        with tempfile.TemporaryDirectory() as folder:
            events,applied=self.fixture(folder)
            record={'draft':draft(),'effective':{'effective_hash':applied.effective.effective_hash}}
            store=SimpleNamespace(get_profile=lambda _: {'profile':record},close=lambda:None)
            args=SimpleNamespace(real_model=True,events=events,sequence=1,output=Path(folder)/'out.json')
            with patch.object(cli,'load_registration',return_value={'library_path':str(Path(folder)/'unused')}), \
                patch.object(cli,'ProfileStore',return_value=store),patch.object(cli,'load_profile',return_value=profile()), \
                patch.object(cli,'create_applied_backend',factory):
                report=await cli.probe(args)
            self.assertEqual(len(calls),1);self.assertEqual(report['calls_invoked'],1)
            self.assertTrue(report['response_returned']);self.assertFalse(report['real_network_response_verified'])
            self.assertTrue(report['response_shape']['json_object'])
            self.assertFalse(report['response_shape']['macro_strategy_object'])
            self.assertNotIn(SECRET,args.output.read_text())
            self.assertEqual(report['backend_diagnostics']['transport_metrics']['attempts'],1)

    async def test_explicit_opt_in_and_context_hash_reject_before_profile_or_call(self):
        with tempfile.TemporaryDirectory() as folder:
            events,_=self.fixture(folder)
            args=SimpleNamespace(real_model=False,events=events,sequence=1,output=Path(folder)/'out.json')
            with patch.object(cli,'load_profile') as load,patch.object(cli,'create_applied_backend') as create:
                with self.assertRaises(ValueError): await cli.probe(args)
                args.real_model=True
                row=json.loads(events.read_text());row['context']['player_id']=7
                events.write_text(json.dumps(row)+'\n')
                with self.assertRaises(ValueError): await cli.probe(args)
                load.assert_not_called();create.assert_not_called()
            self.assertFalse(args.output.exists())

    async def test_actual_sdk_http_failure_has_attempt_without_receipt_and_no_raw(self):
        import httpx2
        calls=[]
        async def handle(req):
            calls.append(1)
            return httpx2.Response(503,text=SECRET)
        original=create_applied_backend
        def factory(applied,**kwargs): return original(applied,transport=httpx2.MockTransport(handle),**kwargs)
        with tempfile.TemporaryDirectory() as folder:
            events,applied=self.fixture(folder)
            record={'draft':draft(),'effective':{'effective_hash':applied.effective.effective_hash}}
            store=SimpleNamespace(get_profile=lambda _: {'profile':record},close=lambda:None)
            args=SimpleNamespace(real_model=True,events=events,sequence=1,output=Path(folder)/'out.json')
            with patch.object(cli,'load_registration',return_value={'library_path':str(Path(folder)/'unused')}), \
                patch.object(cli,'ProfileStore',return_value=store),patch.object(cli,'load_profile',return_value=profile()), \
                patch.object(cli,'create_applied_backend',factory):
                report=await cli.probe(args)
            self.assertEqual(calls,[1]);self.assertTrue(report['failed'])
            self.assertFalse(report['complete_200_receipt']);self.assertFalse(report['response_returned'])
            self.assertEqual(report['backend_diagnostics']['error_code'],'http_status_503')
            self.assertEqual(report['backend_diagnostics']['transport_metrics']['attempts'],1)
            self.assertGreater(report['backend_diagnostics']['transport_metrics']['max_request_bytes'],0)
            self.assertNotIn(SECRET,args.output.read_text())


if __name__=='__main__': unittest.main()
