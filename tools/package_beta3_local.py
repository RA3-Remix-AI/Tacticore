"""Assemble the already accepted Beta3 bytes locally. Does not build or publish."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
from datetime import datetime, timezone
import zipfile

REPO = Path(__file__).resolve().parents[1]
REPORT = REPO / "reports/windows-v0.1.0-beta.3"
INSTALLER = "Tacticore_0.1.0-beta.3_x64-setup.exe"
INSTALLER_SHA = "714c971dc44978c795f15a40dca46326f630af7970e28011e53d88c024bb2f35"
MANIFEST_SHA = "e328808cdb23001170e6daa426ad1bd162869f454f0f7a4c4f4778d4261c2373"
SECRET = re.compile(rb"(?:sk-[A-Za-z0-9_-]{24,}|Bearer[ \t]+[A-Za-z0-9_.-]{24,})")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def relative_path(name):
    parts = PurePosixPath(name)
    if not name or parts.is_absolute() or "\\" in name or ":" in name or any(p in ("", ".", "..") for p in name.split("/")):
        raise ValueError("invalid_relative_path")
    return parts


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args])


def verify_sources(tag, pins):
    names = sorted(pins)
    for name in names:
        relative_path(name)
        assert sha(REPO / name) == pins[name], name
    raw = subprocess.check_output(
        ["git", "-C", str(REPO), "cat-file", "--batch"],
        input="".join(f"{tag}:{name}\n" for name in names).encode("utf-8"))
    offset = 0
    for name in names:
        end = raw.index(b"\n", offset)
        fields = raw[offset:end].split()
        assert len(fields) == 3 and fields[1] == b"blob", name
        size = int(fields[2]); offset = end + 1
        blob = raw[offset:offset + size]
        assert hashlib.sha256(blob).hexdigest() == pins[name], name
        offset += size + 1
    assert offset == len(raw)


def assemble(release, output, tag):
    assert release.is_dir() and not output.exists(), "output_must_be_new"
    commit = git("rev-parse", tag + "^{commit}").decode().strip()
    assert commit == git("rev-parse", "HEAD").decode().strip(), "tag_must_identify_current_commit"
    pins = load(REPORT / "source-pins.json")["files"]
    assert len(pins) == 999
    verify_sources(tag, pins)
    assert sha(release / INSTALLER) == INSTALLER_SHA
    assert (release / INSTALLER).stat().st_size == 37874168
    runtime = release / "runtime"
    assert sha(runtime / "manifest.json") == MANIFEST_SHA
    inventory = load(runtime / "manifest.json")["files"]
    actual = {p.relative_to(runtime).as_posix() for p in runtime.rglob("*") if p.is_file()}
    assert actual == set(inventory) | {"manifest.json"}
    for name, pin in inventory.items():
        relative_path(name)
        assert sha(runtime / name) == pin, name
    identity = load(REPORT / "artifact-identity.json")["identity"]
    assert sha(release / "ui-source-index.json") == identity["ui_source_index_sha256"]
    assert sha(release / "distribution-notices/index.json") == identity["notices_index_sha256"]
    notice_index = load(release / "distribution-notices/index.json")
    for component in notice_index["components"]:
        for notice in component["notices"]:
            relative_path(notice["file"])
            assert sha(release / "distribution-notices" / notice["file"]) == notice["sha256"]
    summary = load(REPORT / "acceptance-summary.json")
    assert summary["complete_P0_P1"] and summary["formal_games_passed"] == 3
    assert summary["cross_machine_verified"] is False
    evidence = load(REPORT / "evidence-index.json")
    # Verify every referenced original before selecting only already-redacted exports.
    for row in evidence["files"]:
        relative_path(row["path"])
        assert sha(REPO / row["path"]) == row["sha256"], row["path"]
    output.mkdir(parents=True)

    def copy(source, name, scan=False):
        relative_path(name)
        assert source.is_file() and not source.is_symlink()
        if scan:
            assert not SECRET.search(source.read_bytes()), "credential_like_value_in_export:" + source.name
        dest = output / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        assert sha(source) == sha(dest)

    copy(release / INSTALLER, INSTALLER)
    copy(REPO / "docs/windows-v0.1.0-beta.3-player-guide.md", "docs/windows-v0.1.0-beta.3-player-guide.md", True)
    copy(REPO / "docs/windows-v0.1.0-beta.3-release-notes.md", "docs/windows-v0.1.0-beta.3-release-notes.md", True)
    copy(REPO / "docs/windows-beta3-delivery-plan-20261104.md", "docs/windows-beta3-delivery-plan-20261104.md", True)
    copy(REPO / "docs/commander-final-acceptance-strategic-20261029.md", "docs/commander-final-acceptance-strategic-20261029.md", True)
    for path in sorted(REPORT.iterdir()):
        if path.is_file():
            copy(path, "reports/windows-v0.1.0-beta.3/" + path.name, True)
    for row in evidence["files"]:
        if row.get("delivery_path"):
            copy(REPO / row["path"], row["delivery_path"], row.get("redacted_export", False))
    notices = release / "distribution-notices"
    assert notices.is_dir()
    for path in sorted(notices.rglob("*")):
        if path.is_file():
            copy(path, "distribution-notices/" + path.relative_to(notices).as_posix())
    # The installer supplement links to the runtime dependency licenses.
    for path in sorted((runtime / "notices").rglob("*")):
        if path.is_file():
            copy(path, "runtime/notices/" + path.relative_to(runtime / "notices").as_posix())
    copy(runtime / "third-party-inventory.json", "runtime/third-party-inventory.json")
    copy(runtime / "application-sources.json", "provenance/application-sources.json")
    copy(runtime / "manifest.json", "provenance/runtime-manifest.json")
    copy(release / "ui-source-index.json", "provenance/ui-source-index.json")
    readme = (
        "弈核 Tacticore v0.1.0-beta.3 本地内测交付包\n\n"
        "先阅读 docs/windows-v0.1.0-beta.3-player-guide.md，再运行根目录安装器。\n"
        "docs/windows-v0.1.0-beta.3-release-notes.md 记录兼容范围、安装摘要与已知限制。\n"
        "evidence/N01、N02、N03 含三局完整脱敏诊断、离线过程页和原生录像。\n"
        "离线过程页可直接在浏览器打开；原生录像有提前结束缺陷，应交叉查看诊断。\n"
        "SHA256SUMS.txt 覆盖除自身外的每份文件；payload-index.json 记录主要载荷。\n"
        "本包不含游戏、Mod BIG、用户配置、账户密码或模型密钥；跨机器未验收。\n"
        f"源码标签：{tag}；提交：{commit}。这是本地交付包，未公开发布。\n"
    )
    (output / "README.txt").write_text(readme, encoding="utf-8", newline="\n")
    provenance = dict(kind="local_beta3_delivery", at_utc=datetime.now(timezone.utc).isoformat(),
                      version="0.1.0-beta.3", candidate_id="windows-beta3-v11", tag=tag,
                      source_commit=commit, source_committed_after_original_build=True,
                      original_build_base="36bac49b", original_build_worktree_dirty=True,
                      accepted_sources_verified=999, runtime_files_verified=len(inventory) + 1,
                      installer_sha256=INSTALLER_SHA, runtime_manifest_sha256=MANIFEST_SHA,
                      binary_rebuilt=False, game_started=False, model_calls=0,
                      cross_machine_verified=False, public_release_created=False,
                      release_set_sha256=load(REPORT / "artifact-identity.json")["release_set_sha256"])
    save(output / "delivery-provenance.json", provenance)
    index = {p.relative_to(output).as_posix(): dict(bytes=p.stat().st_size, sha256=sha(p))
             for p in sorted(output.rglob("*")) if p.is_file()}
    save(output / "payload-index.json", dict(schema_version=1, files=index,
         excludes=["payload-index.json", "SHA256SUMS.txt"]))
    sums = "".join(f"{sha(p)}  {p.relative_to(output).as_posix()}\n"
                   for p in sorted(output.rglob("*")) if p.is_file())
    (output / "SHA256SUMS.txt").write_text(sums, encoding="utf-8", newline="\n")
    for line in sums.splitlines():
        pin, name = line.split("  ", 1)
        assert sha(output / name) == pin
    archive = output.parent / (output.name + ".zip")
    assert not archive.exists()
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                zipped.write(path, output.name + "/" + path.relative_to(output).as_posix())
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        entries = {i.filename: i for i in zipped.infolist()}
        for path in output.rglob("*"):
            if path.is_file():
                name = output.name + "/" + path.relative_to(output).as_posix()
                assert hashlib.sha256(zipped.read(name)).hexdigest() == sha(path), name
        assert len(entries) == sum(p.is_file() for p in output.rglob("*"))
    archive_sha = sha(archive)
    archive.with_suffix(".zip.sha256").write_text(f"{archive_sha}  {archive.name}\n", encoding="utf-8")
    result = dict(passed=True, output=str(output), zip=str(archive), zip_sha256=archive_sha,
                  files=len(entries), installer_sha256=INSTALLER_SHA, tag=tag, source_commit=commit,
                  runtime_files_verified=len(inventory) + 1, frozen_sources_verified=999,
                  cross_machine_verified=False, published=False)
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tag", default="v0.1.0-beta.3")
    args = parser.parse_args()
    assemble(args.release_root.resolve(), args.output.resolve(), args.tag)
