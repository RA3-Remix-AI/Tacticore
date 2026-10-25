"""Repository bootstrap only; all provider/backend assembly lives in agent_runtime."""
from pathlib import Path
import sys

_source = Path(__file__).resolve().parent.parent / "agent_runtime" / "src"
if _source.is_dir():
    sys.path.insert(0, str(_source))

from tacticore_agent_runtime.factory import BACKENDS, DEFAULT_BACKEND, check_backend_available, create_backend
from tacticore_agent_runtime.protocol import RuntimeAdapterError

__all__ = ["BACKENDS", "DEFAULT_BACKEND", "check_backend_available", "create_backend", "RuntimeAdapterError"]
