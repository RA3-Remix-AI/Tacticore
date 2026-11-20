"""The per-session runtime descriptor ("macro bundle") and its scope.

The descriptor only names the installed native runtime; see native_runtime.
Older descriptor schemas (1-15) belonged to retired runtimes and are refused.
"""
from pathlib import Path
import hashlib


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_bundle(path, session=None):
    """(descriptor, NativeScope) for the session; ContractError otherwise."""
    from .native_runtime import load
    return load(path, session)
