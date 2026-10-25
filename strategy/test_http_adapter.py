import asyncio
from contextlib import contextmanager
import copy
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
import uuid

from engine import Snapshot,validate_policy
from fixtures import COMMANDER, CONNECTION, SESSION, binding, policy, snapshot
from http_adapter import AdapterError, ChatAdapter, Endpoint, Profile, TransportPool, load_profile,structure_diagnostics,system_prompt
from service import player_lease

FAKE_KEY="FAKE-ONLY-LOCALHOST-SECRET"


def protect_fake(value):
    class Blob(ctypes.Structure):_fields_=[("size",wintypes.DWORD),("data",ctypes.POINTER(ctypes.c_ubyte))]
    crypto=ctypes.WinDLL("crypt32",use_last_error=True);kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    crypto.CryptProtectData.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    kernel.LocalFree.argtypes=[ctypes.c_void_p]
    raw=value.encode();buffer=(ctypes.c_ubyte*len(raw)).from_buffer_copy(raw);source,target=Blob(len(raw),buffer),Blob()
    if not crypto.CryptProtectData(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target)):raise RuntimeError("Fake key setup failed")
    try:return ctypes.string_at(target.data,target.size)
    finally:ctypes.memset(target.data,0,target.size);kernel.LocalFree(target.data)


def library(directory,url,*,remember=False,provider="自定义"):
    document={"schema_version":2,"connections":[{"id":CONNECTION,"name":"mock-connection","provider":provider,"base_url":url,"remember_key":remember,"default_model":"mock-default"}],"commanders":[{"id":COMMANDER,"name":"mock-commander","connection_id":CONNECTION,"model":"","personality":2,"traits":"侦察后骚扰，避免正面消耗。"}]}
    path=directory/"library.v2.json";path.write_text(json.dumps(document,ensure_ascii=False),encoding="utf-8")
    if remember:
        (directory/"secrets").mkdir(exist_ok=True);(directory/"secrets"/(CONNECTION+".dpapi")).write_bytes(protect_fake(FAKE_KEY))
    return path,document


def completion(context):
    return json.dumps({"choices":[{"finish_reason":"stop","message":{"content":json.dumps(policy(context))}}]}).encode()


class Profiles(unittest.TestCase):
    def test_endpoint_rejects_credentials_query_remote_http_and_full_path(self):
        for url in ["http://example.com/v1","https://user:key@example.com/v1","https://example.com/v1?key=secret","https://example.com/v1#fragment","https://example.com/v1/chat/completions","https://example.com/\r\n"]:
            with self.subTest(url=url),self.assertRaises(AdapterError):Endpoint.parse(url)
        self.assertEqual(Endpoint.parse("https://api.openai.com/v1").path,"/v1/chat/completions")
        self.assertTrue(Endpoint.parse("http://[::1]:1234").loopback)

    @unittest.skipUnless(os.name=="nt","DPAPI is Windows-specific")
    def test_real_dpapi_fake_key_default_and_override(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path,doc=library(root,"https://api.deepseek.com",remember=True,provider="DeepSeek")
            p=load_profile(path,COMMANDER)
            self.assertEqual(p.key,FAKE_KEY);self.assertEqual(p.model,"mock-default");self.assertNotIn(FAKE_KEY,repr(p))
            doc["commanders"][0]["model"]="mock-override";path.write_text(json.dumps(doc),encoding="utf-8")
            self.assertEqual(load_profile(path,COMMANDER).model,"mock-override")
            cipher=root/"secrets"/(CONNECTION+".dpapi");cipher.write_bytes(b"broken")
            with self.assertRaisesRegex(AdapterError,"credential_unavailable"):load_profile(path,COMMANDER)
            self.assertEqual(cipher.read_bytes(),b"broken")

    def test_unsaved_remote_key_refused_keyless_loopback_allowed_and_id_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path,_=library(Path(temp),"https://api.openai.com/v1")
            with self.assertRaisesRegex(AdapterError,"credential_not_saved"):load_profile(path,COMMANDER)
            path,_=library(Path(temp),"http://127.0.0.1:1234")
            self.assertEqual(load_profile(path,COMMANDER).key,"")
            with self.assertRaisesRegex(AdapterError,"invalid_profile_id"):load_profile(path,"../secret")

    def test_duplicate_id_and_unexpected_secret_field_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path,doc=library(Path(temp),"http://localhost:1234")
            doc["connections"].append(copy.deepcopy(doc["connections"][0]));path.write_text(json.dumps(doc),encoding="utf-8")
            with self.assertRaisesRegex(AdapterError,"duplicate_profile_id"):load_profile(path,COMMANDER)
            doc["connections"].pop();doc["connections"][0]["api_key"]=FAKE_KEY;path.write_text(json.dumps(doc),encoding="utf-8")
            with self.assertRaisesRegex(AdapterError,"invalid_library"):load_profile(path,COMMANDER)

    def test_session_player_lease_blocks_second_commander_then_releases(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);other=binding(commander=str(uuid.uuid4()))
            with player_lease(root,binding()):
                with self.assertRaisesRegex(AdapterError,"player_lease_conflict"):
                    with player_lease(root,other):pass
            with player_lease(root,other):pass


class HttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests=[];self.handlers=set();self.active=0;self.peak=0
        async def normal(request):return 200,completion(json.loads(request["body"]["messages"][1]["content"]))
        self.behavior=normal
        async def handler(reader,writer):
            task=asyncio.current_task();self.handlers.add(task);self.active+=1;self.peak=max(self.peak,self.active)
            try:
                header=await reader.readuntil(b"\r\n\r\n");lines=header[:-4].decode("ascii").split("\r\n");headers={}
                for line in lines[1:]:name,value=line.split(":",1);headers[name.lower()]=value.strip()
                body=await reader.readexactly(int(headers.get("content-length",0)))
                request={"path":lines[0].split(" ")[1],"headers":headers,"body":json.loads(body)};self.requests.append(request)
                result=await self.behavior(request)
                if isinstance(result,bytes):writer.write(result)
                else:
                    status,payload=result
                    writer.write(("HTTP/1.1 "+str(status)+" Mock\r\nContent-Type: application/json\r\nContent-Length: "+str(len(payload))+"\r\nConnection: close\r\n\r\n").encode()+payload)
                await writer.drain()
            except (ConnectionError,asyncio.IncompleteReadError):pass
            finally:
                self.active-=1;self.handlers.discard(task);writer.close()
        self.server=await asyncio.start_server(handler,"127.0.0.1",0)
        self.port=self.server.sockets[0].getsockname()[1];self.url="http://127.0.0.1:"+str(self.port)+"/v1"
        self.context=Snapshot.from_dict(snapshot()).model_context(binding())

    async def asyncTearDown(self):
        self.server.close()
        for task in list(self.handlers):task.cancel()
        await asyncio.gather(*self.handlers,return_exceptions=True)
        await self.server.wait_closed()

    def adapter(self,provider="自定义",**kwargs):
        return ChatAdapter(Profile(COMMANDER,"mock",CONNECTION,provider,"mock-model",2,"侦察后骚扰",Endpoint.parse(self.url),FAKE_KEY),total_timeout=kwargs.pop("total_timeout",.5),**kwargs)

    async def test_auth_context_personality_json_and_provider_token_parameters(self):
        for provider in ["OpenAI","DeepSeek","自定义"]:
            result=await self.adapter(provider)(self.context)
            self.assertEqual(result["commander_id"],COMMANDER)
            request=self.requests[-1];body=request["body"]
            self.assertEqual(request["path"],"/v1/chat/completions")
            self.assertEqual(request["headers"]["authorization"],"Bearer "+FAKE_KEY)
            self.assertEqual(body["response_format"],{"type":"json_object"});self.assertFalse(body["stream"])
            self.assertIn("raider",body["messages"][0]["content"]);self.assertIn("侦察后骚扰",body["messages"][0]["content"])
            self.assertNotIn(FAKE_KEY,json.dumps(body));self.assertNotIn("connection_id",body["messages"][1]["content"])
            self.assertIn("max_completion_tokens" if provider=="OpenAI" else "max_tokens",body)
            if provider=="DeepSeek":self.assertEqual(body["thinking"],{"type":"disabled"})

    async def test_system_prompt_contains_a_complete_valid_example_not_enum_arrays(self):
        prompt=system_prompt(self.adapter().profile,self.context)
        start=prompt.index('choices when justified by the current evidence: ')+len('choices when justified by the current evidence: ')
        example,_=json.JSONDecoder().raw_decode(prompt[start:])
        self.assertIsInstance(example["stance"],str)
        request=Snapshot.from_dict(snapshot())
        validated=validate_policy(example,request,request,binding(),10)
        self.assertEqual(validated.production_focus,"native_baseline")

    async def test_policy_diagnostics_contain_types_and_booleans_only_not_values(self):
        bad=policy(self.context,stance=[FAKE_KEY],api_key=FAKE_KEY)
        diagnostic=structure_diagnostics(bad,self.context)
        self.assertEqual(diagnostic["stance"],{"type":"array","enum_match":False})
        self.assertNotIn(FAKE_KEY,json.dumps(diagnostic));self.assertNotIn("api_key",diagnostic)

    async def test_total_input_budget_rejects_before_any_http_request(self):
        context=copy.deepcopy(self.context);context["unexpected_large_context"]="x"*20000
        adapter=self.adapter(max_input_bytes=4096)
        with self.assertRaisesRegex(AdapterError,"input_budget_exceeded"):await adapter(context)
        self.assertEqual(self.requests,[]);self.assertEqual(adapter.metrics["attempts"],0)

    async def test_large_unicode_personality_is_bounded_without_broken_utf8(self):
        profile=Profile(COMMANDER,"mock",CONNECTION,"自定义","mock-model",2,"战"*4000,Endpoint.parse(self.url),FAKE_KEY)
        adapter=ChatAdapter(profile,total_timeout=.5)
        await adapter(self.context)
        prompt=self.requests[0]["body"]["messages"][0]["content"]
        self.assertIn('"traits_truncated": true',prompt);self.assertNotIn("战"*401,prompt)
        self.assertLessEqual(adapter.metrics["max_request_bytes"],16384)

    async def test_maximum_battlefield_and_personality_fit_actual_wire_budget(self):
        from dataclasses import replace
        from battle_agent import BattleAgent
        from engine import StrategyEngine
        from tactical_fixtures import tactical_snapshot
        raw=tactical_snapshot();contact=raw["battlefield"]["contacts"][0];formation=raw["battlefield"]["formations"][0]
        raw["battlefield"]["contacts"]=[dict(contact,contact_id="contact_"+"c"*45+str(i)) for i in range(64)]
        raw["battlefield"]["formations"]=[dict(formation,formation_id="formation_"+"f"*43+str(i),roles={role:1 for role in ["infantry","anti_air","anti_armor","armor","air","naval","economy","structure"]}) for i in range(32)]
        adapter=self.adapter(max_input_bytes=16384)
        adapter.profile=replace(adapter.profile,traits="战"*4000,model="m"*200)
        agent=BattleAgent(StrategyEngine(binding()),context_budget_bytes=8192)
        result=await agent.decide(raw,adapter)
        self.assertEqual(result.status,"accepted");self.assertEqual(len(self.requests),1)
        context=json.loads(self.requests[0]["body"]["messages"][1]["content"])
        battlefield=context["working_memory"]["battlefield"]
        self.assertLessEqual(len(battlefield["contacts"]),12);self.assertLessEqual(len(battlefield["formations"]),8)
        self.assertGreater(context["context_limits"]["contacts_omitted"],0)
        self.assertGreater(context["context_limits"]["formations_omitted"],0)
        self.assertTrue(context["context_limits"]["details_truncated"])
        self.assertLessEqual(adapter.input_size(context),adapter.max_input_bytes)
        self.assertEqual(adapter.metrics["attempts"],1)

    async def test_redirect_not_followed(self):
        async def redirect(_):return b"HTTP/1.1 302 Found\r\nLocation: /steal\r\nContent-Length: 0\r\n\r\n"
        self.behavior=redirect
        with self.assertRaisesRegex(AdapterError,"redirect_forbidden"):await self.adapter()(self.context)
        self.assertEqual(len(self.requests),1)

    async def test_total_timeout_includes_header_wait(self):
        async def hang(_):await asyncio.sleep(10)
        self.behavior=hang;adapter=self.adapter(total_timeout=.03);start=time.monotonic()
        with self.assertRaisesRegex(AdapterError,"transport_timeout"):await adapter(self.context)
        self.assertLess(time.monotonic()-start,.3);self.assertEqual(adapter.metrics["timeouts"],1)

    async def test_dns_worker_is_killed_on_total_timeout_without_external_dns(self):
        profile=Profile(COMMANDER,"mock",CONNECTION,"自定义","mock-model",0,"",Endpoint.parse("https://resolver.invalid/v1"),FAKE_KEY)
        adapter=ChatAdapter(profile,total_timeout=.08)
        adapter.RESOLVER_CODE="import sys,time;sys.stdin.buffer.read(4096);time.sleep(10)"
        start=time.monotonic()
        with self.assertRaisesRegex(AdapterError,"transport_timeout"):await adapter(self.context)
        self.assertLess(time.monotonic()-start,.5)
        self.assertEqual(self.requests,[])

    async def test_bounded_retry_only_when_explicitly_enabled(self):
        async def transient(request):
            return (503,b'{"error":"do not log '+FAKE_KEY.encode()+b'"}') if len(self.requests)==1 else (200,completion(self.context))
        self.behavior=transient;adapter=self.adapter(max_retries=1)
        await adapter(self.context);self.assertEqual(adapter.metrics["attempts"],2);self.assertEqual(adapter.metrics["retries"],1)
        self.requests.clear()
        with self.assertRaisesRegex(AdapterError,"http_status_503"):await self.adapter()(self.context)
        self.assertEqual(len(self.requests),1)

    async def test_shared_pool_bounds_concurrency(self):
        async def slow(_):await asyncio.sleep(.03);return 200,completion(self.context)
        self.behavior=slow;pool=TransportPool(1)
        await asyncio.gather(self.adapter(pool=pool)(self.context),self.adapter(pool=pool)(self.context))
        self.assertEqual(self.peak,1)

    async def test_chunked_response(self):
        async def chunked(_):
            body=completion(self.context);split=len(body)//2
            chunks=b"".join(hex(len(piece))[2:].encode()+b"\r\n"+piece+b"\r\n" for piece in [body[:split],body[split:]])
            return b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"+chunks+b"0\r\n\r\n"
        self.behavior=chunked
        self.assertEqual((await self.adapter()(self.context))["production_focus"],"anti_air")

    async def test_response_limit_and_incomplete_framing(self):
        for response,code in [(b"HTTP/1.1 200 OK\r\nContent-Length: 200000\r\n\r\n","response_too_large"),(b"HTTP/1.1 200 OK\r\nContent-Length: 20\r\n\r\n{}","incomplete_http_body"),(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nContent-Length: 2\r\n\r\n{}","duplicate_http_header")]:
            async def malformed(_,value=response):return value
            self.behavior=malformed
            with self.subTest(code=code),self.assertRaisesRegex(AdapterError,code):await self.adapter()(self.context)

    async def test_refusal_tools_length_and_invalid_json_are_rejected(self):
        variants=[{"finish_reason":"length","message":{"content":"{}"}},{"finish_reason":"stop","message":{"content":"{}","tool_calls":[{}]}},{"finish_reason":"stop","message":{"content":"{}","refusal":"no"}},{"finish_reason":"stop","message":{"content":"not JSON"}}]
        for choice in variants:
            async def invalid(_,value=choice):return 200,json.dumps({"choices":[value]}).encode()
            self.behavior=invalid
            with self.subTest(choice=choice),self.assertRaises(AdapterError):await self.adapter()(self.context)

    async def test_cancellation_does_not_retry(self):
        arrived=asyncio.Event()
        async def hang(_):arrived.set();await asyncio.sleep(10)
        self.behavior=hang;adapter=self.adapter(max_retries=1)
        task=asyncio.create_task(adapter(self.context));await arrived.wait();task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(adapter.metrics["attempts"],1)

    async def cli(self,root,*extra):
        proc=await asyncio.create_subprocess_exec(sys.executable,str(Path(__file__).with_name("service.py")),"--library",str(root/"library.v2.json"),"--commander",COMMANDER,*extra,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        stdout,stderr=await asyncio.wait_for(proc.communicate(),5)
        self.assertNotIn(FAKE_KEY,stdout.decode()+stderr.decode());self.assertNotIn(self.url,stdout.decode()+stderr.decode())
        self.assertEqual(stderr,b"")
        return proc.returncode,json.loads(stdout)

    @unittest.skipUnless(os.name=="nt","DPAPI service interoperability")
    async def test_cli_reads_desktop_dpapi_and_writes_validated_dry_run_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);library(root,self.url,remember=True);source=root/"snapshot.json";source.write_text(json.dumps(snapshot()),encoding="utf-8")
            code,result=await self.cli(root,"--player","3","--snapshot-file",str(source),"--runtime",str(root/"runtime"),"--once","--poll-seconds",".01")
            self.assertEqual(code,0);self.assertEqual(result["state"],"accepted");self.assertFalse(result["execution_enabled"])
            status_file=next((root/"runtime").rglob("status.json"));status=json.loads(status_file.read_text(encoding="utf-8"))
            self.assertFalse(status["execution"]["enabled"]);self.assertEqual(status["current_plan"]["production_focus"],"anti_air")
            sent=json.loads(self.requests[0]["body"]["messages"][1]["content"])
            self.assertEqual(sent["agent_protocol"],"battle_agent_v1");self.assertNotIn("production",sent)
            self.assertTrue(next((root/"runtime").rglob("agent-state.json")).is_file())
            self.assertFalse(json.loads(next((root/"runtime").rglob("jobs.json")).read_text(encoding="utf-8"))["execution_authorized"])
            for file in (root/"runtime").rglob("*"):
                if file.is_file():self.assertNotIn(FAKE_KEY,file.read_text(encoding="utf-8",errors="ignore"))

    async def test_redacted_profile_check_makes_no_request(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);library(root,self.url)
            code,result=await self.cli(root,"--check-profile")
            self.assertEqual(code,0);self.assertTrue(result["ready"]);self.assertTrue(result["keyless_loopback"])
            self.assertEqual(self.requests,[])

    async def test_cli_observes_updated_file_and_rejects_late_policy(self):
        arrived,release=asyncio.Event(),asyncio.Event()
        async def delayed(request):
            arrived.set();await release.wait()
            return 200,completion(json.loads(request["body"]["messages"][1]["content"]))
        self.behavior=delayed
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);library(root,self.url);source=root/"snapshot.json";source.write_text(json.dumps(snapshot()),encoding="utf-8")
            run=asyncio.create_task(self.cli(root,"--player","3","--snapshot-file",str(source),"--runtime",str(root/"runtime"),"--once","--poll-seconds",".01","--max-response-age","10"))
            await asyncio.wait_for(arrived.wait(),2)
            update=root/"new.json";update.write_text(json.dumps(snapshot(2,112)),encoding="utf-8");update.replace(source)
            await asyncio.sleep(.08);release.set()
            code,result=await run
            self.assertEqual(code,0);self.assertEqual(result["reason_code"],"stale_response")
            status=json.loads(next((root/"runtime").rglob("status.json")).read_text(encoding="utf-8"))
            self.assertEqual(status["latest_snapshot"]["snapshot_id"],2)
            self.assertEqual(status["current_plan"]["production_focus"],"native_baseline")

    async def test_cli_bound_stop_cancels_request_without_game_operations(self):
        arrived=asyncio.Event()
        async def hang(_):arrived.set();await asyncio.sleep(10)
        self.behavior=hang
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);library(root,self.url);source=root/"snapshot.json";source.write_text(json.dumps(snapshot()),encoding="utf-8");stop=root/"stop.json"
            run=asyncio.create_task(self.cli(root,"--player","3","--snapshot-file",str(source),"--runtime",str(root/"runtime"),"--stop-file",str(stop),"--poll-seconds",".01"))
            await asyncio.wait_for(arrived.wait(),2)
            stop.write_text(json.dumps({"stop":True,"session_id":SESSION,"player_id":3,"commander_id":COMMANDER}),encoding="utf-8")
            code,result=await run
            self.assertEqual(code,0);self.assertEqual(result["state"],"stopped")
            status=json.loads(next((root/"runtime").rglob("status.json")).read_text(encoding="utf-8"))
            self.assertIsNone(status["current_plan"]);self.assertFalse(status["execution"]["enabled"])


if __name__=="__main__":unittest.main(verbosity=2)
