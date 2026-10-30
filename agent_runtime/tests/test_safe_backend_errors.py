"""Real SDK failures with MockTransport only: fixed codes, no exception text."""
import unittest
from unittest.mock import patch
import httpx2
from test_backends import context,profile
from tacticore_agent_runtime.factory import create_backend
from tacticore_agent_runtime.protocol import RuntimeAdapterError
from tacticore_agent_runtime.pydantic_backend import _framework_code,SAFE_RUNTIME_CODES,PydanticBackend

SECRET='PRIVATE-URL-CREDENTIAL-RESPONSE'


class SafeErrors(unittest.IsolatedAsyncioTestCase):
    async def exercise(self,handler,code,**kwargs):
        calls=[]
        async def track(request):
            calls.append(1)
            return await handler(request)
        b=create_backend(profile(),transport=httpx2.MockTransport(track),**kwargs)
        with self.assertRaises(RuntimeAdapterError) as caught: await b(context())
        self.assertEqual(caught.exception.args,(code,))
        self.assertEqual(b.last_error_code,code)
        self.assertEqual(calls,[1]);self.assertEqual(b.metrics['attempts'],1)
        self.assertEqual(b.metrics['responses'],0);self.assertEqual(b.metrics['retries'],0)
        self.assertIsNone(b.last_transport_receipt)
        return b

    async def test_http_status_codes_preserved_across_real_sdk_wrapping(self):
        for status in (301,400,401,403,408,429,500,503):
            async def handler(request): return httpx2.Response(status,text=SECRET)
            with self.subTest(status=status): await self.exercise(handler,f'http_status_{status}')

    async def test_typed_transport_failures_have_fixed_codes(self):
        for kind,code in (
            (httpx2.ConnectTimeout,'transport_connect_timeout'),
            (httpx2.ReadTimeout,'transport_read_timeout'),
            (httpx2.WriteTimeout,'transport_write_timeout'),
            (httpx2.PoolTimeout,'transport_pool_timeout'),
            (httpx2.ConnectError,'transport_connect_failed'),
            (httpx2.ReadError,'transport_read_failed'),
            (httpx2.WriteError,'transport_write_failed'),
            (httpx2.RemoteProtocolError,'transport_protocol_failed'),
            (httpx2.NetworkError,'transport_network_failed'),
            (httpx2.TimeoutException,'transport_timeout'),
            (httpx2.UnsupportedProtocol,'transport_failed'),
        ):
            async def handler(request): raise kind(SECRET,request=request)
            with self.subTest(kind=kind.__name__): await self.exercise(handler,code)

    async def test_stream_read_error_after_headers_is_still_redacted(self):
        class Stream(httpx2.AsyncByteStream):
            async def __aiter__(self):
                yield b'{'
                raise httpx2.ReadError(SECRET)
        async def handler(request): return httpx2.Response(200,stream=Stream())
        await self.exercise(handler,'transport_read_failed')

    async def test_invalid_encoding_and_raw_envelope_validation_codes(self):
        for content,code in ((b'\xff','invalid_completion_encoding'),
                             (b'{','invalid_completion_encoding'),
                             (b'{"choices":[],"choices":[]}','invalid_completion_encoding'),
                             (b'{}','invalid_completion')):
            async def handler(request): return httpx2.Response(200,content=content)
            with self.subTest(code=code,content=content): await self.exercise(handler,code)

    async def test_unknown_transport_exception_stays_generic(self):
        async def handler(request): raise ValueError(SECRET)
        await self.exercise(handler,'framework_request_failed')

    async def test_preflight_and_actual_sdk_body_bounds_never_call_transport(self):
        calls=[]
        async def handler(request): calls.append(1);raise AssertionError('forbidden')
        b=create_backend(profile(),transport=httpx2.MockTransport(handler),max_input_bytes=4096)
        with self.assertRaises(RuntimeAdapterError) as caught: await b(context())
        self.assertEqual(caught.exception.args,('input_budget_exceeded',))
        self.assertEqual(b.metrics['attempts'],0)
        # Isolate the independent serialized-body guard, without changing its
        # production bound. The usual conservative preflight runs above.
        with patch.object(PydanticBackend,'input_size',return_value=0):
            with self.assertRaises(RuntimeAdapterError) as caught: await b(context())
        self.assertEqual(caught.exception.args,('input_budget_exceeded',))
        self.assertEqual(b.metrics['attempts'],1)
        self.assertGreater(b.metrics['max_request_bytes'],4096)
        self.assertEqual(calls,[])

    def test_no_stringification_and_only_safe_local_cause_is_recovered(self):
        class Poison(RuntimeError):
            def __str__(self): raise AssertionError('exception text must not be read')
        e=Poison(SECRET)
        self.assertEqual(_framework_code(e),'framework_request_failed')
        e.__cause__=RuntimeAdapterError(SECRET)
        self.assertEqual(_framework_code(e),'framework_request_failed')
        e.__cause__=RuntimeAdapterError('http_status_401')
        self.assertEqual(_framework_code(e),'http_status_401')
        e.__cause__=e
        self.assertEqual(_framework_code(e),'framework_request_failed')

    def test_application_allowlist_contains_every_backend_code(self):
        from host_runtime.application import SAFE_BACKEND_ERROR_CODES
        self.assertLessEqual(SAFE_RUNTIME_CODES,SAFE_BACKEND_ERROR_CODES)


if __name__=='__main__': unittest.main()
