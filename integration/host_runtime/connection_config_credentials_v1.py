"""Normal current-user Windows DPAPI. No credential is logged or returned."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import sys
from .contracts import ContractError


class WindowsConnectionCredentialsV1:
    def protect(self, value):
        if os.name != 'nt' or type(value) is not str:
            raise ContractError('connection_credential_unavailable')
        class Blob(ctypes.Structure):
            _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
        crypto = ctypes.WinDLL('crypt32', use_last_error=True)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        crypto.CryptProtectData.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        crypto.CryptProtectData.restype = wintypes.BOOL
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        raw = value.encode('utf8')
        storage = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
        source, target = Blob(len(raw), storage), Blob()
        try:
            if not crypto.CryptProtectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
                raise ContractError('connection_credential_unavailable')
            return ctypes.string_at(target.data, target.size)
        finally:
            ctypes.memset(storage, 0, len(raw))
            if target.data:
                ctypes.memset(target.data, 0, target.size)
                kernel.LocalFree(target.data)

    def unprotect(self, ciphertext):
        # Reuse the installed model loader's current-user DPAPI read API.
        folder = str(Path(__file__).resolve().parents[2] / 'strategy')
        if folder not in sys.path:
            sys.path.insert(0, folder)
        from http_adapter import unprotect_dpapi
        try:
            return unprotect_dpapi(ciphertext)
        except Exception:
            raise ContractError('connection_credential_unavailable') from None
