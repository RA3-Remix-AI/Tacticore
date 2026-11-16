"""Select the transport declared in the native launcher's pinned inventory."""
import hashlib
import json
import os
from pathlib import Path

from .contracts import ContractError


def protocol():
    pin=os.environ.get('TACTICORE_RUNTIME_MANIFEST_SHA256')
    if pin is None:return 6
    path=Path(__file__).resolve().parents[3]/'manifest.json'
    try:
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('manifest pin')
        files=json.loads(raw)['files']
        entries=[version for version in (6,7) if f'native/strategic{version}/build-manifest.json' in files]
        if len(entries)!=1:raise ValueError('unique transport')
        return entries[0]
    except (OSError,ValueError,KeyError,TypeError):
        raise ContractError('portable_native_runtime_not_qualified') from None
