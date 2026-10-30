"""Bounded process-local memoization of fully verified, immutable file scopes.

Every reuse hashes the complete verified evidence set again. No native state,
session, profile, admission token or failed/partial verification is cached.
"""
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from threading import RLock

from .contracts import ContractError


def refuse():raise ContractError('macro_bundle_not_qualified')


@dataclass(frozen=True)
class FileStamp:
    resolved:str
    device:int
    inode:int
    size:int
    modified_ns:int
    sha256:str


def _identity(value):return value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns


def stable_file(path,*,maximum=None,keep_bytes=False):
    """Hash original bytes and reject replacement, relocation or concurrent writes."""
    path=Path(os.path.abspath(path));resolved=path.resolve(strict=True)
    digest=hashlib.sha256();parts=[]
    with resolved.open('rb') as stream:
        first=os.fstat(stream.fileno())
        if maximum is not None and first.st_size>maximum:refuse()
        count=0
        while True:
            block=stream.read(1024*1024)
            if not block:break
            count+=len(block)
            if maximum is not None and count>maximum:refuse()
            digest.update(block)
            if keep_bytes:parts.append(block)
        last=os.fstat(stream.fileno())
    if (count!=first.st_size or _identity(first)!=_identity(last)
            or path.resolve(strict=True)!=resolved or _identity(path.stat())!=_identity(first)):
        refuse()
    return FileStamp(str(resolved),first.st_dev,first.st_ino,first.st_size,first.st_mtime_ns,digest.hexdigest()),b''.join(parts)


class VerifiedFileScopeCache:
    def __init__(self,*,capacity=4,source_paths=()):
        if type(capacity) is not int or not 1<=capacity<=16:raise ValueError('file_scope_cache_capacity')
        self.capacity=capacity;self._lock=RLock();self._entries=OrderedDict()
        # Code already imported in this process cannot be replaced by a newer
        # on-disk version and then silently used with old Python function bodies.
        sources=dict.fromkeys((Path(__file__).resolve(),*(Path(path).resolve() for path in source_paths)))
        self._sources={str(path):stable_file(path)[0] for path in sources}

    def clear(self):
        with self._lock:self._entries.clear()

    def _source_guard(self):
        if any(stable_file(path)[0]!=stamp for path,stamp in self._sources.items()):refuse()

    def _pins(self,value):
        pins=value.get('pins')
        if type(pins) is not dict or not 1<=len(pins)<=8192:refuse()
        stamps={}
        for name,digest in pins.items():
            if (type(name) is not str or not Path(name).is_absolute() or type(digest) is not str
                    or re.fullmatch('[0-9a-f]{64}',digest) is None):refuse()
            stamp=stable_file(name)[0]
            if stamp.sha256!=digest:refuse()
            stamps[name]=stamp
        return stamps

    def load(self,path,validator):
        """validator is the existing complete pure-file proof; return fresh copies."""
        key=os.path.abspath(path)
        with self._lock:
            try:
                self._source_guard()
                stamp,raw=stable_file(key,maximum=2*1024*1024,keep_bytes=True)
                value=json.loads(raw.decode('utf-8-sig'))
                if type(value) is not dict:refuse()
                entry=self._entries.get(key)
                if entry is not None:
                    saved_stamp,saved_value,saved_scope,saved_pins=entry
                    if stamp!=saved_stamp or value!=saved_value:refuse()
                    if self._pins(value)!=saved_pins:refuse()
                    self._source_guard()
                    # Catch mutation of the bundle while its evidence was read.
                    if stable_file(key,maximum=2*1024*1024)[0]!=stamp:refuse()
                    self._entries.move_to_end(key)
                    return deepcopy(saved_value),deepcopy(saved_scope)
                # Untrusted declared pin paths are not read until the full
                # validator has established their exact expected membership.
                verified_value,scope=validator(Path(key))
                if verified_value!=value:refuse()
                pins=self._pins(verified_value)
                self._source_guard()
                if stable_file(key,maximum=2*1024*1024)[0]!=stamp:refuse()
                saved_value=deepcopy(verified_value);saved_scope=deepcopy(scope)
                self._entries[key]=(stamp,saved_value,saved_scope,pins)
                self._entries.move_to_end(key)
                while len(self._entries)>self.capacity:self._entries.popitem(last=False)
                return deepcopy(saved_value),deepcopy(saved_scope)
            except (OSError,ValueError,TypeError,KeyError,UnicodeError,RecursionError):
                self._entries.pop(key,None)
                refuse()
