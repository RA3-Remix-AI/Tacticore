param([string]$Python = '', [switch]$SkipTests)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
# Resolve once and use this exact interpreter for installation, tests and the host.
# Explicit -Python never silently falls back to another installation.
$candidates = @()
if ($Python) {
    $candidates += [pscustomobject]@{ Command = $Python; Arguments = @() }
} else {
    $candidates += [pscustomobject]@{ Command = 'py'; Arguments = @('-3.12') }
    $candidates += [pscustomobject]@{ Command = 'python'; Arguments = @() }
}
$resolvedPython = $null
foreach ($candidate in $candidates) {
    $command = Get-Command $candidate.Command -CommandType Application -ErrorAction SilentlyContinue
    if (-not $command) { continue }
    $arguments = $candidate.Arguments
    try {
        $output = & $command.Source @arguments -c "import sys; assert sys.version_info >= (3, 12), 'Python 3.12+ required'; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $output) {
            $path = ($output | Select-Object -Last 1).Trim()
            if (Test-Path $path -PathType Leaf) { $resolvedPython = $path; break }
        }
    } catch { continue }
}
if (-not $resolvedPython) {
    throw 'Python 3.12+ was not found. Install Python or pass -Python with its executable path.'
}
$Python = $resolvedPython
Write-Output "Installing for host Python: $Python"
& $Python -m pip install -r (Join-Path $PSScriptRoot 'requirements-pydantic.lock')
if ($LASTEXITCODE) { throw 'Pinned runtime dependency installation failed' }
& $Python -m pip install --no-deps $PSScriptRoot
if ($LASTEXITCODE) { throw 'Runtime package installation failed' }
& $Python -m pip check
if ($LASTEXITCODE) { throw 'Dependency consistency check failed' }
if (-not $SkipTests) {
    $oldPath = $env:PYTHONPATH
    $oldBytecode = $env:PYTHONDONTWRITEBYTECODE
    $oldBanner = $env:PYDANTIC_AI_NO_BANNER
    $oldRequired = $env:TACTICORE_REQUIRE_FRAMEWORK
    Push-Location $repo
    try {
        $env:PYTHONPATH = (Join-Path $PSScriptRoot 'src') + ';' + (Join-Path $repo 'strategy')
        $env:PYTHONDONTWRITEBYTECODE = '1'
        $env:PYDANTIC_AI_NO_BANNER = '1'
        $env:TACTICORE_REQUIRE_FRAMEWORK = '1'
        & $Python -m unittest discover -s agent_runtime/tests -v
        if ($LASTEXITCODE) { throw 'Offline runtime verification failed' }
    } finally {
        Pop-Location
        $env:PYTHONPATH = $oldPath
        $env:PYTHONDONTWRITEBYTECODE = $oldBytecode
        $env:PYDANTIC_AI_NO_BANNER = $oldBanner
        $env:TACTICORE_REQUIRE_FRAMEWORK = $oldRequired
    }
}
Write-Output 'PydanticAI decision runtime installed. No game or model endpoint was started.'
Write-Output "Run strategy/service.py or integration/battle_host.py with this same interpreter: $Python"
