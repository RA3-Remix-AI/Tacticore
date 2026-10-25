"""Wrap an existing ChatAdapter instance; do not copy or patch legacy code."""
from typing import Awaitable, Callable
from .protocol import CallableBackend, PolicyRequest, within_deadline


class LegacyBackend(CallableBackend):
    def __init__(self, adapter: Callable[[dict], Awaitable[dict]], *, timeout: float = 12):
        self._adapter = adapter
        self._timeout = timeout

    @property
    def input_size(self):
        return getattr(self._adapter, "input_size", None)

    @property
    def max_input_bytes(self):
        return getattr(self._adapter, "max_input_bytes", None)

    @property
    def metrics(self): return self._adapter.metrics

    @property
    def last_error_code(self): return self._adapter.last_error_code

    @property
    def last_diagnostics(self): return self._adapter.last_diagnostics

    async def run(self, request: PolicyRequest) -> dict:
        # Preserve the exact legacy payload/result and ContractError identity.
        # Retry configuration, if any, still belongs to the existing adapter.
        return await within_deadline(request, self._timeout, lambda: self._adapter(request.context))
