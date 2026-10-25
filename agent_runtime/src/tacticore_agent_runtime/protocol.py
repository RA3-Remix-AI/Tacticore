"""In-process v1 interface; the existing host remains the policy authority."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import math
from typing import Awaitable, Callable, Protocol


class RuntimeAdapterError(RuntimeError):
    """Fixed local codes only. No prompts, provider exception text or secrets."""


@dataclass(frozen=True)
class PolicyRequest:
    context: dict = field(repr=False)
    # asyncio loop monotonic time, NOT wall clock/game clock/a portable IPC timestamp.
    deadline: float | None = None
    protocol_version: int = 1


class PolicyBackend(Protocol):
    async def __call__(self, context: dict) -> dict: ...
    async def run(self, request: PolicyRequest) -> dict: ...


def encode_context(context: dict, maximum: int | None = 16384) -> str:
    if type(context) is not dict:
        raise RuntimeAdapterError("context_object")
    try:
        value = json.dumps(context, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
        size = len(value.encode("utf-8"))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise RuntimeAdapterError("context_json") from None
    if maximum is not None and size > maximum:
        raise RuntimeAdapterError("input_budget_exceeded")
    return value


async def within_deadline(request: PolicyRequest, timeout: float,
                          operation: Callable[[], Awaitable[dict]]) -> dict:
    if type(request.protocol_version) is not int or request.protocol_version != 1:
        raise RuntimeAdapterError("protocol_version")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not .001 <= timeout <= 120:
        raise RuntimeAdapterError("timeout_configuration")
    now = asyncio.get_running_loop().time()
    deadline = now + timeout
    if request.deadline is not None:
        if type(request.deadline) not in (int, float) or not math.isfinite(request.deadline):
            raise RuntimeAdapterError("deadline_invalid")
        deadline = min(deadline, request.deadline)
    if deadline <= now:
        raise RuntimeAdapterError("deadline_exceeded")
    timer = asyncio.timeout_at(deadline)
    try:
        async with timer:
            result = await operation()
        # A badly behaved provider that suppresses cancellation may return late;
        # do not turn that late completion into a usable policy.
        if asyncio.get_running_loop().time() >= deadline:
            raise RuntimeAdapterError("deadline_exceeded")
        return result
    except TimeoutError:
        if timer.expired():
            raise RuntimeAdapterError("deadline_exceeded") from None
        raise


class CallableBackend:
    async def __call__(self, context: dict) -> dict:
        return await self.run(PolicyRequest(context))

    async def run(self, request: PolicyRequest) -> dict:
        raise NotImplementedError
