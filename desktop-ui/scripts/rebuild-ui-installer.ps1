param(
    [Parameter(Mandatory=$true)][string]$PythonExecutable,
    [string]$ReleaseDirectory = 'C:\tacticore-release',
    [string]$TargetDirectory = 'C:\tacticore-target',
    [string]$ScratchDirectory = 'C:\tacticore-ui-rebuild',
    [string]$CompanionDirectory
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$release = [IO.Path]::GetFullPath($ReleaseDirectory)
$target = [IO.Path]::GetFullPath($TargetDirectory)
$scratch = [IO.Path]::GetFullPath($ScratchDirectory)
$baseUrl = 'https://github.com/RA3-Remix-AI/Tacticore/releases/download/v0.1.0-beta.1/Tacticore_0.1.0-beta.1_x64-setup.exe'
$baseSource = 'acc04f526f31b958b58cd5c4de89c82d5bbc3ca3'
$baseSha = 'e09a622cc01a5caed6cb19bc5e7188cb14fdf15ccb70fa078b4ca7400c503796'
$runtimeSha = 'a43ab48b1daaf58f8e21091f609b6a7d669d3493e4d7f14946469e74210c1388'
$rustcCommand = Get-Command rustc.exe -ErrorAction SilentlyContinue
$rustcExecutable = if ($rustcCommand) { $rustcCommand.Source } else { Join-Path $env:USERPROFILE '.cargo\bin\rustc.exe' }
if (-not (Test-Path -LiteralPath $rustcExecutable)) { throw 'Rust compiler unavailable for provenance.' }
$rustcVersion = (& $rustcExecutable -V)
if ($LASTEXITCODE -ne 0) { throw 'Rust compiler version query failed.' }
# This lane is only for a UI rebuild. Detect additions as well as edits: the
# frozen inventory alone cannot detect a newly added, unpackaged source file.
& git -C $repo diff --exit-code $baseSource HEAD -- integration strategy production native-ai tactical visibility agent_runtime probe.py acceptance/capture_macro_before_attach_v5.py
if ($LASTEXITCODE -ne 0) { throw 'Companion sources differ from the accepted base; stage a new runtime instead.' }
foreach ($directory in @($release,$target,$scratch)) {
    if (Test-Path -LiteralPath $directory) { throw "Fresh directory required: $directory" }
    New-Item -ItemType Directory -Path $directory | Out-Null
}
function Get-Sha([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Invoke-Python([string[]]$Arguments) {
    & $PythonExecutable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python verification failed: $($Arguments[0])" }
}
if ($CompanionDirectory) {
    # Reuse only an independently inventory-verified original companion. This
    # never adopts an installed runtime or alters its manifest/published bytes.
    $payload = (Resolve-Path -LiteralPath $CompanionDirectory).Path
    if ((Get-Sha (Join-Path $payload 'runtime/manifest.json')) -ne $runtimeSha) { throw 'Original companion pin mismatch.' }
    if (-not (Test-Path -LiteralPath (Join-Path $payload 'distribution-notices/index.json'))) { throw 'Original companion notices missing.' }
} else {
    $installer = Join-Path $scratch 'base-setup.exe'
    Invoke-WebRequest -Uri $baseUrl -OutFile $installer
    if ((Get-Sha $installer) -ne $baseSha) { throw 'Published base installer hash mismatch.' }
    $sevenZip = (Get-Command 7z.exe -ErrorAction Stop).Source
    $extracted = Join-Path $scratch 'extracted'
    & $sevenZip x $installer "-o$extracted" -y
    if ($LASTEXITCODE -ne 0) { throw 'Base installer extraction failed.' }
# NSIS includes a pre-install verifier copy too. Require the full application
# payload, identified by its exact manifest and adjacent license supplement.
$candidates = @(Get-ChildItem -LiteralPath $extracted -Filter manifest.json -Recurse -File | Where-Object {
    $_.Directory.Name -eq 'runtime' -and (Get-Sha $_.FullName) -eq $runtimeSha -and
    (Test-Path -LiteralPath (Join-Path $_.Directory.Parent.FullName 'distribution-notices/index.json'))
})
if ($candidates.Count -ne 1) { throw 'Expected exactly one manifest-bound application payload.' }
$payload = $candidates[0].Directory.Parent.FullName
}
Copy-Item -LiteralPath (Join-Path $payload 'runtime') -Destination $release -Recurse
$runtime = Join-Path $release 'runtime'
$preflight = Join-Path $PSScriptRoot 'release_preflight.py'
# The installer pins exact Windows source bytes. Diagnose checkout differences
# and restore ONLY a Git-equivalent LF/CRLF representation with the exact pin.
# Do not touch the companion, its manifest, or historical acceptance evidence.
$sourceByteCheck = @'
import hashlib, json, subprocess, sys
from pathlib import Path, PurePosixPath
repo, runtime, report_path = map(Path, sys.argv[1:4])
base, expected_runtime = sys.argv[4:6]
sys.path.insert(0, str(repo / 'desktop-ui/scripts'))
from release_preflight import verify_inventory
verify_inventory(runtime, expected=expected_runtime)
sources = json.loads((runtime / 'application-sources.json').read_bytes())['files']
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
def lf(raw):
    return raw.replace(b'\r\n', b'\n')
def blob(revision, name):
    return subprocess.check_output(['git', '-C', str(repo), 'show', revision + ':' + name])
rows, repairs, blocked = [], [], False
for name, expected in sorted(sources.items()):
    parts = PurePosixPath(name).parts
    if not parts or name.startswith('/') or any(p in ('.', '..') for p in parts) or ':' in name or '\\' in name:
        raise ValueError('source_byte_path_invalid')
    path = repo / name
    if path.is_symlink() or not path.resolve().is_relative_to(repo.resolve()):
        raise ValueError('source_byte_path_invalid')
    current = path.read_bytes()
    if sha(current) == expected:
        continue
    head_raw, base_raw = blob('HEAD', name), blob(base, name)
    forms = {'git_blob': head_raw, 'git_lf': lf(head_raw), 'git_crlf': lf(head_raw).replace(b'\n', b'\r\n')}
    match = next((form for form, raw in forms.items() if sha(raw) == expected), None)
    published = (runtime / 'app' / name).read_bytes()
    published_pin_matches = sha(published) == expected
    equivalent = lf(current) == lf(head_raw) == lf(base_raw) == lf(published)
    safe = equivalent and published_pin_matches
    row = dict(path=name, expected_sha256=expected, current_sha256=sha(current),
               base_git_sha256=sha(base_raw), git_form_sha256={key:sha(raw) for key,raw in forms.items()},
               normalized_git_content_equal=equivalent, matching_form=match,
               published_source_sha256=sha(published), published_pin_matches=published_pin_matches,
               line_ending_materialization_allowed=safe)
    rows.append(row)
    print(json.dumps(row), flush=True)
    if safe:
        repairs.append((path, published))
    else:
        blocked = True
report = dict(kind='published_source_byte_comparison', runtime_manifest_sha256=expected_runtime,
              compared_files=len(sources), mismatches=rows, blocked=blocked, materialized_files=[])
report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
if blocked:
    raise ValueError('published_source_content_mismatch_not_line_endings')
for path, raw in repairs:
    path.write_bytes(raw)
    if path.read_bytes() != raw:
        raise ValueError('source_byte_materialization_failed')
    report['materialized_files'].append(path.relative_to(repo).as_posix())
report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
verify_inventory(runtime, expected=expected_runtime)
print(json.dumps(dict(source_files=len(sources), exact_pin_line_ending_repairs=len(repairs))), flush=True)
'@
Invoke-Python -Arguments @('-B','-c',$sourceByteCheck,$repo,$runtime,(Join-Path $release 'source-byte-comparison.json'),$baseSource,$runtimeSha)
Invoke-Python -Arguments @('-B',$preflight,'--runtime',$runtime,'--candidate','--output',(Join-Path $release 'source-preflight.json'))
$uiSourceCheck = @'
import hashlib, json, subprocess, sys
from pathlib import Path
repo, target = map(Path, sys.argv[1:3])
names = subprocess.check_output(['git','-C',str(repo),'ls-files','--cached','--others','--exclude-standard','--','desktop-ui']).decode().splitlines()
files = {name:hashlib.sha256((repo/name).read_bytes()).hexdigest() for name in sorted(set(names)) if (repo/name).is_file()}
value = dict(kind='windows_ui_candidate_source_index', source_commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD']).decode().strip(),
             worktree_dirty=bool(subprocess.check_output(['git','-C',str(repo),'status','--porcelain','--untracked-files=normal','--','desktop-ui'])), files=files)
raw = (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
if target.exists():
    if target.read_bytes()!=raw: raise ValueError('ui_candidate_sources_changed_during_build')
else: target.write_bytes(raw)
'@
Invoke-Python -Arguments @('-B','-c',$uiSourceCheck,$repo,(Join-Path $release 'ui-source-index.json'))
# Rebuild only installer data for the exact compiler used today. The original
# runtime and all historical acceptance records stay byte-for-byte unchanged.
$nsisSource = Join-Path $payload 'distribution-notices/source-form/nsis-3.13-source.zip'
if (-not (Test-Path -LiteralPath $nsisSource -PathType Leaf)) { throw 'Original NSIS source archive missing.' }
Invoke-Python -Arguments @('-B',(Join-Path $PSScriptRoot 'supplement-beta-notices.py'),'--output',(Join-Path $release 'distribution-notices'),'--nsis-source',$nsisSource)
Invoke-Python -Arguments @('-B',(Join-Path $PSScriptRoot 'probe-python-stage.py'),'--runtime',$runtime,'--output',(Join-Path $release 'python-probe.json'))
Invoke-Python -Arguments @('-B',(Join-Path $PSScriptRoot 'probe-native6-integration.py'),'--runtime',$runtime,'--output',(Join-Path $release 'native6-probe.json'))
$previousTarget = $env:CARGO_TARGET_DIR
try {
    $env:CARGO_TARGET_DIR = $target
    & (Join-Path $PSScriptRoot 'build-windows.ps1') -ReleaseDirectory $release -BetaCandidate -PythonExecutable $PythonExecutable
} finally {
    $env:CARGO_TARGET_DIR = $previousTarget
}
Invoke-Python -Arguments @('-B',$preflight,'--runtime',$runtime,'--candidate','--output',(Join-Path $release 'final-preflight.json'))
Invoke-Python -Arguments @('-B','-c',$uiSourceCheck,$repo,(Join-Path $release 'ui-source-index.json'))
if ((Get-Sha (Join-Path $runtime 'manifest.json')) -ne $runtimeSha) { throw 'Frozen companion changed.' }
$artifacts = @(Get-ChildItem -LiteralPath $release -Filter '*setup.exe' -File)
if ($artifacts.Count -ne 1) { throw 'Expected exactly one rebuilt installer.' }
$version = (Get-Content -LiteralPath (Join-Path $repo 'desktop-ui/package.json') -Raw | ConvertFrom-Json).version
$commit = (& git -C $repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Source commit unavailable.' }
$clientSha = Get-Sha (Join-Path $release 'tacticore-desktop.exe')
$installerSha = Get-Sha $artifacts[0].FullName
$provenance = [ordered]@{
    schema_version = 1
    kind = 'windows_ui_installer_rebuild_candidate'
    version = $version
    source_commit = $commit
    ui_source_index_sha256 = Get-Sha (Join-Path $release 'ui-source-index.json')
    base_source_commit = $baseSource
    base_installer_url = $baseUrl
    base_installer_sha256 = $baseSha
    runtime_manifest_sha256 = $runtimeSha
    runtime_reused_unchanged = $true
    client_sha256 = $clientSha
    installer_filename = $artifacts[0].Name
    installer_sha256 = $installerSha
    rustc_version = $rustcVersion
    distribution_notices_index_sha256 = Get-Sha (Join-Path $release 'distribution-notices/index.json')
    windows_game_acceptance_performed = $false
    historical_acceptance_reused_as_new_pass = $false
    public_release_ready = $false
}
$provenance | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $release 'ui-rebuild-provenance.json') -Encoding utf8NoBOM
$sumFiles = @($artifacts[0].FullName,(Join-Path $release 'ui-rebuild-provenance.json'))
$sumFiles | ForEach-Object { "$(Get-Sha $_)  $([IO.Path]::GetFileName($_))" } | Set-Content -LiteralPath (Join-Path $release 'SHA256SUMS.txt') -Encoding utf8NoBOM
Write-Host "Built candidate: $($artifacts[0].Name). No game acceptance or public release claim."
