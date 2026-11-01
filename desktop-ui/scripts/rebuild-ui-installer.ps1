param([Parameter(Mandatory=$true)][string]$PythonExecutable)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$release = 'C:\tacticore-release'
$target = 'C:\tacticore-target'
$scratch = 'C:\tacticore-ui-rebuild'
$baseUrl = 'https://github.com/RA3-Remix-AI/Tacticore/releases/download/v0.1.0-beta.1/Tacticore_0.1.0-beta.1_x64-setup.exe'
$baseSource = 'acc04f526f31b958b58cd5c4de89c82d5bbc3ca3'
$baseSha = 'e09a622cc01a5caed6cb19bc5e7188cb14fdf15ccb70fa078b4ca7400c503796'
$runtimeSha = 'a43ab48b1daaf58f8e21091f609b6a7d669d3493e4d7f14946469e74210c1388'
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
Copy-Item -LiteralPath (Join-Path $payload 'runtime') -Destination $release -Recurse
$runtime = Join-Path $release 'runtime'
$preflight = Join-Path $PSScriptRoot 'release_preflight.py'
Invoke-Python -Arguments @('-B',$preflight,'--runtime',$runtime,'--candidate','--output',(Join-Path $release 'source-preflight.json'))
# Rebuild only installer data for the exact compiler used today. The original
# runtime and all historical acceptance records stay byte-for-byte unchanged.
$nsisSource = Join-Path $payload 'distribution-notices/source-form/nsis-3.13-source.zip'
if (-not (Test-Path -LiteralPath $nsisSource -PathType Leaf)) { throw 'Original NSIS source archive missing.' }
Invoke-Python -Arguments @('-B',(Join-Path $PSScriptRoot 'supplement-beta-notices.py'),'--output',(Join-Path $release 'distribution-notices'),'--nsis-source',$nsisSource)
Invoke-Python -Arguments @('-B',(Join-Path $PSScriptRoot 'probe-python-stage.py'),'--runtime',$runtime,'--output',(Join-Path $release 'python-probe.json'))
Invoke-Python -Arguments @('-B',(Join-Path $PSScriptRoot 'probe-native6-runtime.py'),'--runtime',$runtime,'--output',(Join-Path $release 'native6-probe.json'))
$previousTarget = $env:CARGO_TARGET_DIR
try {
    $env:CARGO_TARGET_DIR = $target
    & (Join-Path $PSScriptRoot 'build-windows.ps1') -ReleaseDirectory $release -BetaCandidate -PythonExecutable $PythonExecutable
} finally {
    $env:CARGO_TARGET_DIR = $previousTarget
}
Invoke-Python -Arguments @('-B',$preflight,'--runtime',$runtime,'--candidate','--output',(Join-Path $release 'final-preflight.json'))
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
    base_source_commit = $baseSource
    base_installer_url = $baseUrl
    base_installer_sha256 = $baseSha
    runtime_manifest_sha256 = $runtimeSha
    runtime_reused_unchanged = $true
    client_sha256 = $clientSha
    installer_filename = $artifacts[0].Name
    installer_sha256 = $installerSha
    rustc_version = (& rustc -V)
    distribution_notices_index_sha256 = Get-Sha (Join-Path $release 'distribution-notices/index.json')
    windows_game_acceptance_performed = $false
    historical_acceptance_reused_as_new_pass = $false
    public_release_ready = $false
}
$provenance | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $release 'ui-rebuild-provenance.json') -Encoding utf8NoBOM
$sumFiles = @($artifacts[0].FullName,(Join-Path $release 'ui-rebuild-provenance.json'))
$sumFiles | ForEach-Object { "$(Get-Sha $_)  $([IO.Path]::GetFileName($_))" } | Set-Content -LiteralPath (Join-Path $release 'SHA256SUMS.txt') -Encoding utf8NoBOM
Write-Host "Built candidate: $($artifacts[0].Name). No game acceptance or public release claim."
