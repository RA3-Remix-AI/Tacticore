param([switch]$NativeTests, [string]$ReleaseDirectory, [string]$PythonExecutable, [switch]$BetaCandidate)
$ErrorActionPreference = 'Stop'
$desktopRoot = Split-Path -Parent $PSScriptRoot
if ($NativeTests -and $ReleaseDirectory) { throw 'Choose native tests or a release build.' }
if ($BetaCandidate -and -not $ReleaseDirectory) { throw 'A beta installer candidate needs a frozen ReleaseDirectory.' }
if ($ReleaseDirectory) {
    if (-not $PythonExecutable) {
        $PythonExecutable = Join-Path (Split-Path -Parent $desktopRoot) '.venv\Scripts\python.exe'
    }
    if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) { throw 'Supply -PythonExecutable for the release preflight.' }
    $preflightRuntime = Join-Path (Resolve-Path -LiteralPath $ReleaseDirectory).Path 'runtime'
    [string[]]$candidateArgs = @()
    if ($BetaCandidate) { $candidateArgs += '--candidate' }
    & $PythonExecutable (Join-Path $PSScriptRoot 'release_preflight.py') --runtime $preflightRuntime @candidateArgs
    if ($LASTEXITCODE -ne 0) { throw 'Windows beta release preflight failed. Resolve the reported blockers before building a release.' }
}
$cargoBin = Join-Path $env:USERPROFILE '.cargo\bin'
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path -LiteralPath $vswhere)) { throw 'Visual Studio Build Tools installer is unavailable.' }
$vsRoot = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vsRoot) { throw 'MSVC C++ Build Tools are not installed.' }
$developerScript = Join-Path $vsRoot 'Common7\Tools\VsDevCmd.bat'
$nodeExe = (Get-Command node.exe -ErrorAction Stop).Source
$nodeBin = Split-Path -Parent $nodeExe
if (-not (Test-Path -LiteralPath (Join-Path $cargoBin 'cargo.exe'))) { throw 'Rust toolchain is not installed.' }
$previousManifest = $env:TACTICORE_RUNTIME_MANIFEST
$previousCandidatePin = $env:TACTICORE_BETA_CANDIDATE_PIN
if ($ReleaseDirectory) {
    $releaseRoot = (Resolve-Path -LiteralPath $ReleaseDirectory).Path
    $manifestPath = Join-Path $releaseRoot 'runtime\manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'Generate a companion runtime first.' }
    $env:TACTICORE_RUNTIME_MANIFEST = $manifestPath
    if ($BetaCandidate) { $env:TACTICORE_BETA_CANDIDATE_PIN = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant() }
} else { Remove-Item Env:TACTICORE_RUNTIME_MANIFEST -ErrorAction SilentlyContinue }
$buildFlag = if ($ReleaseDirectory) { '' } else { ' --debug' }
$action = if ($NativeTests) { 'cargo test --manifest-path src-tauri\Cargo.toml --lib' } else { '"' + $nodeExe + '" node_modules\@tauri-apps\cli\tauri.js build' + $buildFlag }
$toolingOverride = $null
$bundleSnapshot = $null
$snapshotParent = $null
if ($BetaCandidate) {
    $supplementRoot = Join-Path $releaseRoot 'distribution-notices'
    & $PythonExecutable (Join-Path $PSScriptRoot 'supplement-beta-notices.py') --output $supplementRoot --verify
    if ($LASTEXITCODE -ne 0) { throw 'Complete installer-only original notices are required.' }
    $candidateTarget = if ($env:CARGO_TARGET_DIR) { $env:CARGO_TARGET_DIR } else { Join-Path $desktopRoot 'src-tauri/target' }
    $cachedSupplement = Join-Path $candidateTarget 'release/distribution-notices'
    if (Test-Path -LiteralPath $cachedSupplement) {
        & $PythonExecutable (Join-Path $PSScriptRoot 'supplement-beta-notices.py') --output $cachedSupplement --verify
        if ($LASTEXITCODE -ne 0 -or (Get-FileHash -LiteralPath (Join-Path $cachedSupplement 'index.json')).Hash -ne (Get-FileHash -LiteralPath (Join-Path $supplementRoot 'index.json')).Hash) {
            throw 'Installer notice cache changed. Use a fresh CARGO_TARGET_DIR; existing files were retained.'
        }
    }
    $cachedRuntime = Join-Path $candidateTarget 'release/runtime'
    if (Test-Path -LiteralPath $cachedRuntime) {
        $cachedManifest = Join-Path $cachedRuntime 'manifest.json'
        if (-not (Test-Path -LiteralPath $cachedManifest) -or (Get-FileHash -LiteralPath $cachedManifest).Hash -ne (Get-FileHash -LiteralPath $manifestPath).Hash) {
            throw 'Release resource cache belongs to another candidate. Use a fresh CARGO_TARGET_DIR; existing files were retained.'
        }
        & $PythonExecutable (Join-Path $PSScriptRoot 'release_preflight.py') --runtime $cachedRuntime --candidate
        if ($LASTEXITCODE -ne 0) { throw 'Release resource cache contains extra or changed files. Use a fresh CARGO_TARGET_DIR.' }
    }
    $toolingOverride = Join-Path ([IO.Path]::GetTempPath()) ('tacticore-beta-build-' + [guid]::NewGuid().ToString('N') + '.json')
    $runtimeResources = @{}
    # Tauri resource normalization strips Windows drive prefixes. Give it a
    # relative, byte-verified snapshot on the repository drive instead.
    $snapshotName = 'beta-bundle-' + [guid]::NewGuid().ToString('N')
    # Keep makensis source paths below its Win32 path limit, including the
    # byte-compiled historical evidence modules with long qualified names.
    $snapshotParent = Join-Path ([IO.Path]::GetPathRoot($desktopRoot)) 'CodexScratch/Tacticore-Beta-Bundles'
    $bundleSnapshot = Join-Path $snapshotParent $snapshotName
    New-Item -ItemType Directory -Path $bundleSnapshot | Out-Null
    Copy-Item -LiteralPath (Join-Path $releaseRoot 'runtime') -Destination $bundleSnapshot -Recurse
    Copy-Item -LiteralPath $supplementRoot -Destination $bundleSnapshot -Recurse
    & $PythonExecutable (Join-Path $PSScriptRoot 'release_preflight.py') --runtime (Join-Path $bundleSnapshot 'runtime') --candidate
    if ($LASTEXITCODE -ne 0) { throw 'Copied beta bundle did not match the frozen candidate.' }
    # Root-relative on the project drive avoids Tauri stripping a different
    # drive prefix and avoids makensis retaining a long sequence of ../.
    $snapshotRuntime = (Join-Path $bundleSnapshot 'runtime')
    if ([IO.Path]::GetPathRoot($snapshotRuntime) -ne [IO.Path]::GetPathRoot($desktopRoot)) { throw 'Bundle snapshot must be on the project drive.' }
    $runtimeResources[($snapshotRuntime.Substring(2).Replace('\','/') + '/')] = 'runtime/'
    $supplementSnapshot = (Join-Path $bundleSnapshot 'distribution-notices')
    $runtimeResources[($supplementSnapshot.Substring(2).Replace('\','/') + '/')] = 'distribution-notices/'
    $guardBinary = [IO.Path]::GetFullPath((Join-Path $candidateTarget 'release/tacticore-desktop.exe'))
    $guardHooks = Join-Path $bundleSnapshot 'installer-guard.nsh'
    $originalHooks = Join-Path $desktopRoot 'src-tauri/installer-hooks.nsh'
    foreach ($nsisPath in @($guardBinary,$snapshotRuntime,$originalHooks)) {
        if ($nsisPath.Contains('$') -or $nsisPath.Contains('"') -or $nsisPath.Contains("`n") -or $nsisPath.Contains("`r")) { throw 'Unsupported NSIS guard source path.' }
    }
    @(
        '!define TACTICORE_GUARD_BINARY "' + $guardBinary + '"'
        '!define TACTICORE_GUARD_RUNTIME "' + $snapshotRuntime + '"'
        '!include "' + $originalHooks + '"'
    ) | Set-Content -LiteralPath $guardHooks -Encoding utf8NoBOM
    @{ build = @{ beforeBuildCommand = 'node.exe node_modules/typescript/bin/tsc --noEmit && node.exe node_modules/vite/bin/vite.js build --config vite.beta.config.ts' }; bundle = @{resources=$runtimeResources;windows=@{nsis=@{installerHooks=$guardHooks}}} } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $toolingOverride -Encoding utf8NoBOM
    $action += ' --config "' + $toolingOverride + '"'
}
if (-not $NativeTests -and -not $BetaCandidate -and -not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    # The bundled workspace has Node without npm. Run the same two local build
    # tools through that fixed Node, without installing or changing global tools.
    $tscEntry = Join-Path $desktopRoot 'node_modules\typescript\bin\tsc'
    $viteEntry = Join-Path $desktopRoot 'node_modules\vite\bin\vite.js'
    if (-not (Test-Path -LiteralPath $tscEntry) -or -not (Test-Path -LiteralPath $viteEntry)) { throw 'Local frontend build dependencies are unavailable.' }
    $frontendBuild = 'node.exe node_modules/typescript/bin/tsc --noEmit && node.exe node_modules/vite/bin/vite.js build'
    $toolingOverride = Join-Path ([IO.Path]::GetTempPath()) ('tacticore-build-' + [guid]::NewGuid().ToString('N') + '.json')
    @{ build = @{ beforeBuildCommand = $frontendBuild } } | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $toolingOverride -Encoding utf8NoBOM
    $action += ' --config "' + $toolingOverride + '"'
}
$wrapper = @"
@echo off
chcp 65001 >nul
call "$developerScript" -no_logo -arch=x64
if errorlevel 1 exit /b %errorlevel%
set "PATH=$cargoBin;$nodeBin;%PATH%"
$action
exit /b %errorlevel%
"@
$wrapperPath = Join-Path ([IO.Path]::GetTempPath()) ('tacticore-build-' + [guid]::NewGuid().ToString('N') + '.cmd')
Set-Content -LiteralPath $wrapperPath -Value $wrapper -Encoding utf8NoBOM
Push-Location $desktopRoot
try {
    & cmd.exe /d /c $wrapperPath
    if ($LASTEXITCODE -ne 0) { throw "Native build failed (exit $LASTEXITCODE)." }
    if ($ReleaseDirectory) {
        $nativeTarget = if ($env:CARGO_TARGET_DIR) { $env:CARGO_TARGET_DIR } else { Join-Path $desktopRoot 'src-tauri\target' }
        Copy-Item -LiteralPath (Join-Path $nativeTarget 'release\tacticore-desktop.exe') -Destination (Join-Path $releaseRoot 'tacticore-desktop.exe')
        if ($BetaCandidate) {
            $installers = @(Get-ChildItem -LiteralPath (Join-Path $nativeTarget 'release\bundle\nsis') -Filter '*setup.exe' -File)
            if ($installers.Count -ne 1) { throw 'Exactly one beta installer is required.' }
            Copy-Item -LiteralPath $installers[0].FullName -Destination (Join-Path $releaseRoot 'Tacticore_0.1.0-beta.1_x64-setup.exe')
        }
    }
} finally {
    Pop-Location
    if ($null -eq $previousManifest) { Remove-Item Env:TACTICORE_RUNTIME_MANIFEST -ErrorAction SilentlyContinue }
    else { $env:TACTICORE_RUNTIME_MANIFEST = $previousManifest }
    if ($null -eq $previousCandidatePin) { Remove-Item Env:TACTICORE_BETA_CANDIDATE_PIN -ErrorAction SilentlyContinue }
    else { $env:TACTICORE_BETA_CANDIDATE_PIN=$previousCandidatePin }
    # The sole temporary wrapper belongs to this invocation, never a repo path.
    if (Test-Path -LiteralPath $wrapperPath) { Remove-Item -LiteralPath $wrapperPath }
    if ($toolingOverride -and (Test-Path -LiteralPath $toolingOverride)) { Remove-Item -LiteralPath $toolingOverride }
    if ($bundleSnapshot -and (Test-Path -LiteralPath $bundleSnapshot)) {
        $snapshotResolved = (Resolve-Path -LiteralPath $bundleSnapshot).Path
        $snapshotParentResolved = (Resolve-Path -LiteralPath $snapshotParent).Path
        if ((Split-Path -Parent $snapshotResolved) -ne $snapshotParentResolved -or (Split-Path -Leaf $snapshotResolved) -notmatch '^beta-bundle-[a-f0-9]{32}$') { throw 'Unexpected beta bundle cleanup path.' }
        Remove-Item -LiteralPath $snapshotResolved -Recurse
    }
}
