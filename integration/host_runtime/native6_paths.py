"""Native6 paths owned by the Windows user, independent of repo/env/cwd.

No model/RPC path is accepted. Known Folder resolution is lazy and never
falls back to an installation directory or inherited LOCALAPPDATA variable.
"""
from dataclasses import dataclass
import ctypes as c
import os
from pathlib import Path
import re
import uuid

LOCAL_APP_DATA = 'f1b32785-6fba-4fcf-9d55-7b8e7f157091'
DOCUMENTS = 'fdd39ad0-238f-46af-adb4-6c85480369c7'


def known_folder(identifier):
    if os.name != 'nt':
        raise ValueError('native6_windows_known_folder_required')
    guid = (c.c_ubyte * 16).from_buffer_copy(uuid.UUID(identifier).bytes_le)
    shell = c.WinDLL('shell32', use_last_error=True)
    ole = c.WinDLL('ole32', use_last_error=True)
    shell.SHGetKnownFolderPath.argtypes = [c.c_void_p, c.c_uint32, c.c_void_p, c.POINTER(c.c_wchar_p)]
    shell.SHGetKnownFolderPath.restype = c.c_long
    ole.CoTaskMemFree.argtypes = [c.c_void_p]
    value = c.c_wchar_p()
    result = shell.SHGetKnownFolderPath(c.byref(guid), 0, None, c.byref(value))
    try:
        if result or not value.value:
            raise ValueError('native6_windows_known_folder_unavailable')
        return plain_local(value.value)
    finally:
        if value:
            ole.CoTaskMemFree(c.cast(value, c.c_void_p))


def plain_local(value, *, existing=True):
    path = Path(value)
    if (not path.is_absolute() or re.fullmatch(r'[A-Za-z]:', path.drive) is None
            or '..' in path.parts or '\x00' in str(path) or len(str(path).encode('utf-16-le')) > 1038):
        raise ValueError('native6_plain_local_path_required')
    for ancestor in (path, *path.parents):
        try:
            information = ancestor.lstat()
        except FileNotFoundError:
            if existing or ancestor == Path(path.anchor):
                raise
            continue
        if ancestor.is_symlink() or getattr(information, 'st_file_attributes', 0) & 0x400:
            raise ValueError('native6_reparse_path_refused')
    return path


def session_hex(value):
    if type(value) is not str or str(uuid.UUID(value)) != value:
        raise ValueError('native6_canonical_session_required')
    if uuid.UUID(value).int == 0:
        raise ValueError('native6_nonzero_session_required')
    return uuid.UUID(value).hex


@dataclass(frozen=True)
class Native6Paths:
    root: Path
    mods: Path

    @classmethod
    def current(cls):
        return cls.from_roots(known_folder(LOCAL_APP_DATA), known_folder(DOCUMENTS))

    @classmethod
    def from_roots(cls, local_app_data, documents):
        return cls(plain_local(local_app_data) / 'Tacticore/desktop-runtime/native6',
                   plain_local(documents) / 'Red Alert 3/Mods')

    @property
    def reports(self):
        return self.root / 'reports'

    @property
    def journals(self):
        return self.root / 'journals'

    def ensure(self):
        for directory in (self.root, self.reports, self.journals):
            plain_local(directory, existing=False)
            directory.mkdir(parents=True, exist_ok=True)
            plain_local(directory)

    def report(self, session_id):
        return self.reports / session_hex(session_id)

    def journal(self, session_id):
        return self.journals / (session_hex(session_id) + '.bin')

    def require_mod(self, value):
        path = plain_local(value)
        if not path.is_relative_to(self.mods) or path.suffix.lower() != '.big' or not path.is_file():
            raise ValueError('native6_owned_documents_mod_required')
        return path
