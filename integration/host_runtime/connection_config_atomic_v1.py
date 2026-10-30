"""Complete staged bytes before exclusive publication; never replace a target."""
import os
from pathlib import Path
import uuid


def write_stage(stream, raw):
    stream.write(raw)
    stream.flush()
    os.fsync(stream.fileno())


def exclusive_bytes(path, raw):
    path = Path(path)
    temporary = path.with_name(path.name + '.' + str(uuid.uuid4()) + '.stage')
    try:
        with temporary.open('xb') as stream:
            write_stage(stream, raw)
        # Same-directory hard link atomically publishes only complete bytes.
        # FileExistsError preserves another writer's canonical value intact.
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
