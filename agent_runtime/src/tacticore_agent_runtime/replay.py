"""Explicit in-memory replay, bound to the complete sanitized model context."""
from collections import deque
from dataclasses import dataclass, field
import hashlib
from typing import Callable, Iterable
from .protocol import CallableBackend, PolicyRequest, RuntimeAdapterError, encode_context, within_deadline


def context_digest(context: dict) -> str:
    return hashlib.sha256(encode_context(context).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReplayEntry:
    context_sha256: str
    response_json: str = field(repr=False)


class ReplayBackend(CallableBackend):
    def __init__(self, entries: Iterable[ReplayEntry], *, parse_json: Callable[[str], dict], timeout: float = 12):
        self._entries = deque(entries)
        self._parse = parse_json
        self._timeout = timeout

    async def run(self, request: PolicyRequest) -> dict:
        async def replay():
            if not self._entries:
                raise RuntimeAdapterError("replay_exhausted")
            if context_digest(request.context) != self._entries[0].context_sha256:
                raise RuntimeAdapterError("replay_context_mismatch")
            # Parse using the existing strict parser, preserving ContractError.
            return self._parse(self._entries.popleft().response_json)
        return await within_deadline(request, self._timeout, replay)
