"""Real SDK/factory message encoding with an in-memory HTTP transport only.

Archived requests are public context; no credential stores or response raws are
read. All completions below are synthetic, never historical model responses.
"""
import copy
import ast
from dataclasses import replace
import hashlib
import json
import re
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'strategy'),str(ROOT/'integration'),str(ROOT/'agent_runtime/src')]
import httpx2
import http_adapter
from http_adapter import Endpoint,Profile,structure_diagnostics,system_prompt
from tacticore_agent_runtime.factory import NetworkBackend,create_backend
from tacticore_agent_runtime.protocol import RuntimeAdapterError
from macro_policy import project_strategy_defaults,restore_public_defaults
from macro_strategy import DECLARATION_FIELDS,MacroStrategyMemory,validate_strategy_declaration
import macro_policy
import macro_strategy
from integration.host_runtime.macro_policy_runtime import MacroRequestAudit
from test_macro_strategy_wire import pressure_context

ARCHIVE=ROOT/'acceptance/runs/desktop-46b33a8b-da4e-4e9b-abe3-f18dc821ce24/battle-host'


def archived_requests():
    if not (ARCHIVE/'host-events.jsonl').is_file():
        raise unittest.SkipTest('requires the local historical SDK request archive')
    rows=[json.loads(line) for line in (ARCHIVE/'host-events.jsonl').read_text(encoding='utf8').splitlines()]
    return rows,[r['context'] for r in rows if r.get('kind')=='model_macro_request_context']


def frozen_prompt_functions():
    rows=json.loads((ARCHIVE/'sources.json').read_text(encoding='utf8'))['sources']
    def extract(name,names,namespace,assignments=False):
        row=next(r for r in rows if Path(r['path']).name == name)
        path=ARCHIVE/'source'/row['copy']; raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row['sha256']: raise ValueError('frozen_source_hash')
        tree=ast.parse(raw); selected=[]
        for node in tree.body:
            if isinstance(node,ast.FunctionDef) and node.name in names: selected.append(node)
            elif assignments and isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in node.targets): selected.append(node)
        result=dict(namespace); exec(compile(ast.Module(body=selected,type_ignores=[]),str(path),'exec'),result)
        return result
    old_http=extract('http_adapter.py',{'system_prompt','macro_system_prompt'},vars(http_adapter))
    old_defaults=extract('macro_policy.py',{'strategic_default_prompt'},vars(macro_policy))
    old_schema=extract('macro_strategy.py',{'OBJECTIVES','PHASES','EXPECTED_OBSERVATIONS','CONDITIONS',
        'RESOURCE_KEYS','DECLARATION_FIELDS','STRATEGY_DECLARATION_SCHEMA'},{},True)
    return old_http['system_prompt'],old_defaults['strategic_default_prompt'],old_schema['STRATEGY_DECLARATION_SCHEMA']


def profile(context,provider='DeepSeek',traits=''):
    return Profile(context['commander_id'],'Synthetic shape check','23968c8e-25d3-47bd-8c84-5f0d5bbfd43b',
        provider,'deepseek-flash' if provider=='DeepSeek' else 'gpt-example',1,traits,
        Endpoint.parse('https://fixture.invalid/v1'),'SYNTHETIC-NOT-A-CREDENTIAL')


def example(prompt):
    line=next(line for line in prompt.splitlines() if line.startswith('Example: '))
    return json.loads(line[len('Example: '):])


def completion(answer):
    return httpx2.Response(200,json={'id':'offline-synthetic','object':'chat.completion','created':1,'model':'fixture',
        'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(answer)}}]})


async def latest_resource_pressure():
    # Reuse B's canonical full-resource fixture instead of silently omitting the
    # latest cost/ledger fields from a separate smaller pressure construction.
    from test_macro_expansion_host import ExpansionAuditTests
    captured={}; original=http_adapter.macro_system_prompt
    def capture(p,c):
        captured.update(context=copy.deepcopy(c),traits=p.traits)
        return original(p,c)
    with patch.object(http_adapter,'macro_system_prompt',capture):
        await ExpansionAuditTests().test_twenty_action_context_and_resource_facts_fit_sixteen_kib_wire()
    return captured['context'],captured['traits']


@unittest.skipUnless((ARCHIVE/'host-events.jsonl').is_file() and (ARCHIVE/'sources.json').is_file(),
                     'requires the local historical SDK request archive; use test_native_prompt_budget for portable regression')
class StrategyPydanticTests(unittest.IsolatedAsyncioTestCase):
    async def test_deepseek_json_mode_word_requirement_is_present_in_actual_sdk_messages(self):
        # DeepSeek's documented JSON mode requires the word json in a system or
        # user message, not only response_format. Emulate that provider gate on
        # the real SDK wire, including the prior broken prompt as a negative.
        _,requests=archived_requests(); context=requests[0]
        original=http_adapter.macro_system_prompt
        for missing in (True,False):
            seen=[]
            async def transport(request):
                body=json.loads(request.content);seen.append(body)
                self.assertEqual(body['response_format'],{'type':'json_object'})
                prompts=' '.join(m['content'] for m in body['messages'] if m['role'] in ('system','user'))
                if re.search(r'\bjson\b',prompts,re.IGNORECASE) is None:
                    return httpx2.Response(400,text='synthetic JSON mode word requirement')
                return completion(example(next(m['content'] for m in body['messages'] if m['role']=='system')))
            def prompt(p,c):
                value=original(p,c)
                return re.sub(r'\bJSON\b','',value,count=1,flags=re.IGNORECASE) if missing else value
            backend=create_backend(profile(context),transport=httpx2.MockTransport(transport),max_tokens=1536)
            with patch.object(http_adapter,'macro_system_prompt',prompt):
                if missing:
                    with self.assertRaises(RuntimeAdapterError) as caught: await backend(context)
                    self.assertEqual(caught.exception.args,('http_status_400',))
                else:
                    result=await backend(context)
                    self.assertIn('macro_strategy',result)
            self.assertEqual(len(seen),1)

    async def test_five_frozen_request_hashes_rebuild_exactly_without_credentials_or_network(self):
        rows,requests=archived_requests(); old_prompt,old_defaults,old_schema=frozen_prompt_functions()
        # ProfileStore._record writes only normalized public style/profile data
        # here. Do not load any user library, key store, endpoint or credentials.
        public=json.loads((ARCHIVE/'profile.json').read_text(encoding='utf8'))['effective']
        for sequence,context in enumerate(requests,1):
            seen=[]
            async def transport(request): seen.append(request.content); return completion({})
            p=replace(profile(context,traits=public['traits']),model=public['model'],personality=public['personality'])
            backend=create_backend(p,transport=httpx2.MockTransport(transport),max_tokens=1536)
            backend._prompt=lambda c:old_prompt(p,c)
            with patch.object(macro_policy,'strategic_default_prompt',old_defaults), \
                    patch.object(macro_strategy,'STRATEGY_DECLARATION_SCHEMA',old_schema):
                await backend(context)
            receipt=next(r['transport_receipt'] for r in rows if r.get('kind')=='commander_model_response_returned' and r['call_sequence']==sequence)
            self.assertEqual(len(seen[0]),receipt['request_bytes'])
            self.assertEqual(hashlib.sha256(seen[0]).hexdigest(),receipt['request_sha256'])
            body=json.loads(seen[0]); sent=json.loads(next(m['content'] for m in body['messages'] if m['role']=='user'))
            prompt=next(m['content'] for m in body['messages'] if m['role']=='system')
            self.assertIn('macro_strategy',sent); self.assertIn('Include Allowed+Empty keys+macro_strategy',prompt)

    async def test_all_five_archived_requests_preserve_strategy_through_real_factory_sdk_messages(self):
        rows,requests=archived_requests(); self.assertEqual(len(requests),5)
        self.assertEqual(sum(r.get('kind')=='macro_strategy_response_rejected' for r in rows),4)
        self.assertEqual(sum(r.get('kind')=='commander_model_response_returned' for r in rows),5)
        decisions=[r for r in rows if r.get('kind')=='decision']
        self.assertEqual(sum(r.get('reason_code')=='policy_fields' for r in decisions),1)
        for context in requests:
            original=copy.deepcopy(context); seen=[]
            async def transport(request):
                body=json.loads(request.content); seen.append(body)
                user=next(m['content'] for m in body['messages'] if m['role']=='user')
                prompt=next(m['content'] for m in body['messages'] if m['role']=='system')
                self.assertEqual(json.loads(user),original)
                answer=example(prompt)
                self.assertIn('macro_strategy REQUIRED',prompt); self.assertIn('Example=shape',prompt)
                self.assertEqual(set(answer['macro_strategy']),set(DECLARATION_FIELDS))
                self.assertNotIn('condition_values',answer['macro_strategy'])
                validate_strategy_declaration(answer['macro_strategy'])
                self.assertTrue(set(answer['macro_strategy']['public_fact_refs']) <= set(context['macro_strategy']['fact_catalog']))
                # Explicitly model-supplied synthetic choice, not copied from the
                # example and not overwritten by the host/runtime after parsing.
                answer['macro_strategy'].update(objective='scout',phase='assess',expected_observation='new_lawful_contact')
                return completion(answer)
            backend=create_backend(profile(context),transport=httpx2.MockTransport(transport),max_tokens=1536,max_input_bytes=16384)
            self.assertIsInstance(backend,NetworkBackend)
            result=await backend(context)
            self.assertEqual(result['macro_strategy']['objective'],'scout')
            self.assertEqual(len(seen),1); self.assertEqual(backend.metrics['attempts'],1)
            self.assertEqual(backend.metrics['responses'],1)
            self.assertTrue(backend.last_diagnostics['macro_strategy']['fields_match'])
            self.assertTrue(backend.last_diagnostics['macro_policy_shape']['fields_match'])
            self.assertEqual(context,original)
            self.assertEqual(backend.last_transport_receipt['injected_transport'],True)
            self.assertFalse(backend.last_transport_receipt['real_network_verified'])
            self.assertNotIn('tools',seen[0]); self.assertEqual(seen[0]['response_format'],{'type':'json_object'})

    async def test_synthetic_missing_declaration_still_fails_host_audit_without_invention(self):
        context=archived_requests()[1][0]; seen=[]
        async def transport(request):
            body=json.loads(request.content); seen.append(body)
            answer=example(next(m['content'] for m in body['messages'] if m['role']=='system'))
            answer.pop('macro_strategy')
            return completion(answer)
        backend=create_backend(profile(context),transport=httpx2.MockTransport(transport),max_tokens=1536)
        memory=MacroStrategyMemory(session_id=context['session_id'],commander_id=context['commander_id'],player_id=3,
            profile_revision=21,effective_hash='a'*64)
        audit=MacroRequestAudit(backend,lambda *a,**k:None,strategy_supplier=memory.context)
        with self.assertRaisesRegex(ValueError,'macro_strategy_declaration_missing'): await audit(context)
        self.assertEqual(len(seen),1)
        self.assertEqual(backend.last_diagnostics['macro_strategy']['present'],False)
        self.assertEqual(backend.last_diagnostics['macro_policy_shape']['missing_fields'],['macro_strategy'])

    async def test_synthetic_extra_field_remains_policy_fields_and_diagnostics_never_log_values(self):
        from engine import validate_policy,ContractError
        from fixtures import binding
        from test_macro_strategy_integration import macro_snapshot,memory_for
        snap=macro_snapshot(); context=snap.model_context(binding()); context['macro_strategy']=memory_for(context).context(context)
        async def transport(request):
            body=json.loads(request.content); answer=example(next(m['content'] for m in body['messages'] if m['role']=='system'))
            answer['NEVER-LOG-THIS-KEY']='NEVER-LOG-THIS-RESPONSE-VALUE'
            return completion(answer)
        backend=create_backend(profile(context),transport=httpx2.MockTransport(transport))
        answer=await backend(context)
        with self.assertRaisesRegex(ContractError,'policy_fields'): validate_policy(answer,snap,snap,binding(),30)
        diagnostic=json.dumps(backend.last_diagnostics)
        self.assertNotIn('NEVER-LOG',diagnostic)
        self.assertEqual(backend.last_diagnostics['macro_policy_shape']['extra_field_count'],1)

    async def test_actual_sdk_bytes_fit_twenty_candidates_max_strategy_traits_and_resource_v3(self):
        old,_,_=pressure_context(); old=project_strategy_defaults(old)
        latest,traits=await latest_resource_pressure()
        self.assertEqual(len(latest['allowed_macro_actions']),20)
        self.assertEqual(len(json.dumps(latest['macro_strategy'],ensure_ascii=False,separators=(',',':')).encode()),1536)
        for name,context,style in (('full_feedback',old,'风格偏好'*100),('full_resource_v3',latest,traits)):
            for provider in ('DeepSeek','OpenAI'):
                with self.subTest(name=name,provider=provider):
                    seen=[]; before=restore_public_defaults(context)
                    async def transport(request):
                        seen.append(len(request.content)); body=json.loads(request.content)
                        sent=json.loads(next(m['content'] for m in body['messages'] if m['role']=='user'))
                        self.assertEqual(restore_public_defaults(sent),before)
                        self.assertLessEqual(len(request.content),16384-256)
                        return completion(example(next(m['content'] for m in body['messages'] if m['role']=='system')))
                    backend=create_backend(profile(context,provider,style),transport=httpx2.MockTransport(transport))
                    self.assertLessEqual(backend.input_size(context),16384)
                    await backend(context); self.assertEqual(len(seen),1)
                    self.assertEqual(backend.metrics['max_request_bytes'],seen[0])

    async def test_escaped_style_overflow_is_rejected_before_mock_provider(self):
        context,traits=await latest_resource_pressure(); calls=[]
        async def transport(request): calls.append(1); return completion({})
        escaped='正常风格'*32+'"'*800
        self.assertLessEqual(len(escaped.encode()),1200)
        backend=create_backend(profile(context,traits=escaped),transport=httpx2.MockTransport(transport))
        self.assertGreater(backend.input_size(context),16384)
        with self.assertRaisesRegex(RuntimeAdapterError,'input_budget_exceeded'): await backend(context)
        self.assertEqual(calls,[]); self.assertEqual(backend.metrics['attempts'],0)


if __name__=='__main__': unittest.main()
