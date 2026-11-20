"""Native-owned beta installation preparation, without a fabricated match.

Only the native file picker supplies input paths. Nothing here opens Game
memory, calls a provider or grants an execution capability. A real session is
created later by the existing discover/prepare broker and live admission.

The installed runtime is verified file-by-file against its pinned manifest at
setup, at status and before each game launch. When the runtime changes, setup
is refreshed only while no game runs; earlier runs are then archived as
finished history (their native state ended with their game process).
"""

from dataclasses import fields
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import uuid

from .contracts import ContractError, identifier, object_fields
from .native_paths import known_folder, LOCAL_APP_DATA, DOCUMENTS, plain_local
from .native_runtime import PACKAGE_REPORT, REGISTRY, create, current, load, runtime_root, trusted_pin
from .native_runtime_contract import GAME_SHA, PACKAGE_SHA, PROTOCOL, read, sha
from .session_discovery import DiscoveryPolicy, TrustedFiles
from . import beta_launch

VERSION = "0.1.0-beta.1"
KIND = "native_installed_discovery_v2"
ARCHIVE = "history-archive.json"
LAUNCH_INDEX = "desktop-launch-index.sqlite3"


def descriptor_path(state, pin):
    return state / "sessions" / ("native-runtime-" + pin + ".json")


def launcher_path(state, policy):
    return state / ("game-launch-" + policy["policy_id"] + ".json")


def locations():
    # MSIX desktop callers can see an ordinary-looking directory whose final
    # physical path is LocalCache. Reject reparse points first, then use the
    # OS-resolved directory identity consistently for metadata/SQLite paths.
    legacy = plain_local(known_folder(LOCAL_APP_DATA) / "Tacticore", existing=False).resolve()
    home = legacy / "beta1"
    state = home / "desktop-runtime"
    mods = known_folder(DOCUMENTS) / ("Red Alert 3/Mods/Tacticore-beta4-" + PACKAGE_SHA[:12])
    return home, state, mods, legacy


def no_game():
    """Setup never changes while a Red Alert 3 process runs."""
    from .session_discovery_native import Win32ReadOnly

    api = Win32ReadOnly()
    if any(api.process_ids(name) for name in ("RA3_1.12.game", "RA3.exe")):
        raise ContractError("beta_game_already_running")


def archived_through(state):
    """Highest launch-index row archived as finished history (0 if none)."""
    path = Path(state) / ARCHIVE
    if not path.is_file():
        return 0
    value = read(path)
    if type(value) is not dict or type(value.get("archived_through_rowid")) is not int:
        raise ContractError("run_history_unverifiable")
    return value["archived_through_rowid"]


def archive_history(state):
    """Mark every recorded launch as finished history. Caller ensured no game runs."""
    index = Path(state) / LAUNCH_INDEX
    highest = 0
    if index.is_file():
        connection = sqlite3.connect(index.as_uri() + "?mode=ro", uri=True)
        try:
            row = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='launches'").fetchone()
            if row is not None:
                highest = connection.execute("SELECT coalesce(max(rowid),0) FROM launches").fetchone()[0]
        finally:
            connection.close()
    highest = max(highest, archived_through(state))
    replace_file(
        Path(state) / ARCHIVE, (json.dumps(dict(schema_version=1, archived_through_rowid=highest)) + "\n").encode()
    )
    return highest


def replace_file(path, raw):
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def exact_file(path, raw):
    path = plain_local(path, existing=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    plain_local(path.parent)
    try:
        with path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        if path.read_bytes() != raw:
            raise ContractError("beta_owned_file_conflict")


def current_scope():
    from .session_discovery_native import SCOPE

    return dict(SCOPE, native_epoch=PROTOCOL)


def prepare(game, mod):
    root, pin, inventory, build = current()
    game, mod = plain_local(game), plain_local(mod)
    if game.name.lower() != "ra3_1.12.game" or sha(game) != GAME_SHA:
        raise ContractError("beta_game_unsupported")
    if mod.suffix.lower() != ".big" or sha(mod) != PACKAGE_SHA:
        raise ContractError("beta_mod_unsupported")
    beta_launch.base_config(game)
    home, state, mods, legacy = locations()
    from .session_discovery_native import NAME, read_object

    target = state / NAME
    old = read_object(target)[0] if target.exists() else None
    no_game()
    for folder in (home, state, mods, state / "sessions"):
        plain_local(folder, existing=False)
        folder.mkdir(parents=True, exist_ok=True)
        plain_local(folder)
    destination = mods / "TFCommander.big"
    if destination.exists():
        if sha(destination) != PACKAGE_SHA:
            raise ContractError("beta_owned_file_conflict")
    else:
        # An interrupted copy is kept separate; it is never accepted as the Mod.
        temporary = mods / (uuid.uuid4().hex + ".partial")
        with mod.open("rb") as source, temporary.open("xb") as destination_stream:
            shutil.copyfileobj(source, destination_stream)
            destination_stream.flush()
            os.fsync(destination_stream.fileno())
        if sha(temporary) != PACKAGE_SHA or sha(mod) != PACKAGE_SHA:
            raise ContractError("beta_mod_changed")
        # Rename without replacing unrelated or concurrently created content.
        temporary.rename(destination)
    config = mods / "TFCommander_1.0.SkuDef"
    exact_file(config, b"mod-game 1.12\nadd-big TFCommander.big\n")
    descriptor = descriptor_path(state, pin)
    if descriptor.exists():
        load(descriptor)
    else:
        create(descriptor)
    values = dict(
        game=game,
        mod_config=config,
        mod_big=destination,
        registry=root / REGISTRY,
        macro_bundle=descriptor,
        package_report=root / PACKAGE_REPORT,
    )
    pins = {}
    for key, path in values.items():
        pins[key] = str(path)
        pins["mod_sha256" if key == "mod_big" else key + "_sha256"] = sha(path)
    record = dict(
        schema_version=2,
        kind=KIND,
        policy_id=str(uuid.uuid4()),
        session_root=str(state / "sessions"),
        runtime_manifest_sha256=pin,
        files=pins,
        scope=current_scope(),
    )
    comparable = lambda value: {k: v for k, v in value.items() if k != "policy_id"}
    if old is not None and comparable(old) == comparable(record):
        record = old
    elif old is not None:
        # The runtime or the selections changed while no game runs: earlier
        # launches become finished history, then the new policy replaces the old.
        archive_history(state)
    else:
        from .desktop_session_registry import register_root

        register_root(state / "sessions", state)
    launch = (json.dumps(beta_launch.record(game, config, pin, record["policy_id"]), sort_keys=True) + "\n").encode()
    exact_file(launcher_path(state, record), launch)
    if old is None:
        exact_file(target, (json.dumps(record, sort_keys=True) + "\n").encode())
    elif record is not old:
        replace_file(target, (json.dumps(record, sort_keys=True) + "\n").encode())
    return dict(
        schema_version=1,
        prepared=True,
        version=VERSION,
        game_verified=True,
        mod_verified=True,
        requires_live_discovery=True,
        host_started=False,
        native_commands_issued=0,
        model_requests=0,
    )


def load_policy(state, record):
    """The installed policy; file hashes are re-checked, the runtime is not re-scanned."""
    home, expected, mods, legacy = locations()
    if Path(state) != expected:
        raise ContractError("discovery_policy_invalid")
    object_fields(
        record, {"schema_version", "kind", "policy_id", "session_root", "runtime_manifest_sha256", "files", "scope"}
    )
    root = runtime_root()
    pin = trusted_pin()
    if (
        type(record["schema_version"]) is not int
        or record["schema_version"] != 2
        or record["kind"] != KIND
        or record["runtime_manifest_sha256"] != pin
        or record["scope"] != current_scope()
        or Path(record["session_root"]) != expected / "sessions"
    ):
        raise ContractError("discovery_policy_invalid")
    identifier(record["policy_id"])
    object_fields(record["files"], {field.name for field in fields(TrustedFiles)})
    cooked = {
        key: plain_local(value) if field.type is Path else value
        for field in fields(TrustedFiles)
        for key, value in ((field.name, record["files"][field.name]),)
    }
    files = TrustedFiles(**cooked)
    # dataclasses may retain postponed type names in the shared broker.
    for key in ("game", "mod_config", "mod_big", "registry", "macro_bundle", "package_report"):
        object.__setattr__(files, key, plain_local(getattr(files, key)))
        digest = "mod_sha256" if key == "mod_big" else key + "_sha256"
        if sha(getattr(files, key)) != getattr(files, digest):
            raise ContractError("discovery_source_changed")
    if (
        files.game.name.lower() != "ra3_1.12.game"
        or files.game_sha256 != GAME_SHA
        or files.mod_sha256 != PACKAGE_SHA
        or files.mod_big != mods / "TFCommander.big"
        or files.mod_config != mods / "TFCommander_1.0.SkuDef"
        or files.registry != root / REGISTRY
        or files.package_report != root / PACKAGE_REPORT
        or files.macro_bundle != descriptor_path(expected, pin)
    ):
        raise ContractError("discovery_policy_invalid")
    from .session_discovery_native import validate_mod_file

    validate_mod_file(files.mod_config, files.mod_big)
    if read(launcher_path(state, record)) != beta_launch.record(files.game, files.mod_config, pin, record["policy_id"]):
        raise ContractError("beta_game_launcher_changed")
    return record, DiscoveryPolicy(files, plain_local(expected / "sessions"), plain_local(expected), **record["scope"])


def status():
    home, state, mods, legacy = locations()
    from .session_discovery_native import NAME

    target = state / NAME
    if not target.exists():
        return dict(schema_version=1, prepared=False, version=VERSION)
    old = read(target)
    current()  # the installed runtime, every file against the pinned manifest
    pin = trusted_pin()
    setup_changed = (
        old.get("kind") != KIND or old.get("runtime_manifest_sha256") != pin or old.get("scope") != current_scope()
    )
    if setup_changed:
        files = old.get("files") if type(old.get("files")) is dict else {}
        if files.get("mod_sha256") != PACKAGE_SHA:
            return dict(schema_version=1, prepared=False, version=VERSION, reason_code="beta_mod_update_required")
        if type(files.get("game")) is not str or type(files.get("mod_big")) is not str:
            raise ContractError("beta_setup_changed_requires_migration")
        # The previous native picker's selections retain their authorization;
        # prepare re-checks the exact Game/Mod hashes and requires no game.
        prepare(Path(files["game"]), Path(files["mod_big"]))
    load_policy(state, read(target))
    return dict(
        schema_version=1,
        prepared=True,
        version=VERSION,
        game_verified=True,
        mod_verified=True,
        requires_live_discovery=True,
        host_started=False,
        setup_changed=setup_changed,
    )


def launch():
    no_game()
    home, state, mods, legacy = locations()
    from .session_discovery_native import NAME

    current()  # the installed runtime, every file against the pinned manifest
    _, policy = load_policy(state, read(state / NAME))
    game = policy.files.game
    if sha(game) != GAME_SHA or sha(policy.files.mod_big) != PACKAGE_SHA:
        raise ContractError("beta_game_launcher_changed")
    # User's explicit native button; fixed arguments only. Discovery later
    # validates the actual Game image/incarnation, package, map and own UUID.
    # Do not re-read mutable launch JSON after load_policy validated it. The
    # executed base path is derived again from the verified Game and pins.
    base = beta_launch.base_config(game)
    subprocess.Popen(
        beta_launch.arguments(game, policy.files.mod_config, base),
        cwd=game.parent.parent,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return dict(schema_version=1, game_launch_requested=True, host_started=False, model_requests=0)


def main():
    # This pipe is launched only by the native command; it is not a WebView
    # RPC operation. Native owns both paths; output never exposes them.
    import sys
    from .bridge_service import decode_request

    request = decode_request(sys.stdin.buffer.readline(65537))
    operation = request.get("operation")
    try:
        if operation == "status":
            object_fields(request, {"operation"})
            result = status()
        elif operation == "prepare":
            object_fields(request, {"operation", "game", "mod"})
            result = prepare(request["game"], request["mod"])
        elif operation == "launch":
            object_fields(request, {"operation"})
            result = launch()
        elif operation == "guard":
            # Before an application update: no game, hence no native state.
            object_fields(request, {"operation"})
            no_game()
            result = {"quiet": True}
        else:
            raise ContractError("operation_unsupported")
        print(json.dumps(dict(ok=True, result=result)))
        return 0
    except ContractError as error:
        print(json.dumps(dict(ok=False, error=dict(code=error.code))))
        return 2
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
        print(json.dumps(dict(ok=False, error=dict(code="beta_setup_unavailable"))))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
