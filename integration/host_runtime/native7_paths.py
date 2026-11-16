"""Separate Native7 journals and reports under the real Windows user folders."""
from .native6_paths import (Native6Paths, plain_local, known_folder,
                            LOCAL_APP_DATA, DOCUMENTS, session_hex)


class Native7Paths(Native6Paths):
    @classmethod
    def from_roots(cls, local_app_data, documents):
        return cls(plain_local(local_app_data) / 'Tacticore/desktop-runtime/native7',
                   plain_local(documents) / 'Red Alert 3/Mods')
