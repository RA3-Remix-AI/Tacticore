param([switch]$NativeTests, [string]$ReleaseDirectory, [string]$PythonExecutable)
$ErrorActionPreference = 'Stop'
$desktopRoot = Split-Path -Parent $PSScriptRoot
if ($NativeTests -and $ReleaseDirectory) { throw 'Choose native tests or a release build.' }
if ($ReleaseDirectory) {
    if (-not $PythonExecutable) {
        $PythonExecutable = Join-Path (Split-Path -Parent $desktopRoot) '.venv\Scripts\python.exe'
    }
    if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) { throw 'Supply -PythonExecutable for the release preflight.' }
    $preflightRuntime = Join-Path (Resolve-Path -LiteralPath $ReleaseDirectory).Path 'runtime'
    & $PythonExecutable (Join-Path $PSScriptRoot 'release_preflight.py') --runtime $preflightRuntime
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
if ($ReleaseDirectory) {
    $releaseRoot = (Resolve-Path -LiteralPath $ReleaseDirectory).Path
    $manifestPath = Join-Path $releaseRoot 'runtime\manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'Generate a companion runtime first.' }
    $env:TACTICORE_RUNTIME_MANIFEST = $manifestPath
} else { Remove-Item Env:TACTICORE_RUNTIME_MANIFEST -ErrorAction SilentlyContinue }
$buildFlag = if ($ReleaseDirectory) { '' } else { ' --debug' }
$action = if ($NativeTests) { 'cargo test --manifest-path src-tauri\Cargo.toml --lib' } else { '"' + $nodeExe + '" node_modules\@tauri-apps\cli\tauri.js build' + $buildFlag }
$toolingOverride = $null
if (-not $NativeTests -and -not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
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
        Copy-Item -LiteralPath (Join-Path $desktopRoot 'src-tauri\target\release\tacticore-desktop.exe') -Destination (Join-Path $releaseRoot 'tacticore-desktop.exe')
    }
} finally {
    Pop-Location
    if ($null -eq $previousManifest) { Remove-Item Env:TACTICORE_RUNTIME_MANIFEST -ErrorAction SilentlyContinue }
    else { $env:TACTICORE_RUNTIME_MANIFEST = $previousManifest }
    # The sole temporary wrapper belongs to this invocation, never a repo path.
    if (Test-Path -LiteralPath $wrapperPath) { Remove-Item -LiteralPath $wrapperPath }
    if ($toolingOverride -and (Test-Path -LiteralPath $toolingOverride)) { Remove-Item -LiteralPath $toolingOverride }
}
