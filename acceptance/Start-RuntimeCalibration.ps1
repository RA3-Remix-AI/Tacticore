param([Parameter(Mandatory=$true)][string]$TemplateSession)
$ErrorActionPreference='Stop'
$probeRoot=Split-Path $PSScriptRoot
$runsRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'runs'))+[IO.Path]::DirectorySeparatorChar
$templatePath=[IO.Path]::GetFullPath($TemplateSession)
if(!$templatePath.StartsWith($runsRoot,[StringComparison]::OrdinalIgnoreCase)){throw 'Expected an existing local calibration session'}
$record=Get-Content -LiteralPath $templatePath -Raw | ConvertFrom-Json
if($record.scenario.trial_kind -ne 'tactical_runtime_single_actor_calibration' -or $record.scenario.model_requests_enabled -ne $false){throw 'Expected a non-model single-actor calibration template'}
if(Get-Process -Name 'ra3_1.12.game' -ErrorAction SilentlyContinue){throw 'Existing game must be independently ended before a new fixture'}
if((Get-FileHash -LiteralPath $record.game -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'){throw 'Game executable changed'}
if((Get-FileHash -LiteralPath $record.mod_big -Algorithm SHA256).Hash.ToLowerInvariant() -ne $record.mod_sha256){throw 'Mod package changed'}
& (Join-Path $probeRoot '.venv/Scripts/python.exe') (Join-Path $probeRoot 'tactical/runtime/diagnose.py') --session $templatePath --output (Join-Path $probeRoot 'reports/runtime-build-gate-current.json')
if($LASTEXITCODE){throw 'Runtime source/artifact/ABI gate failed'}
$run=Join-Path $PSScriptRoot ('runs/'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'-runtime-calibration')
New-Item -ItemType Directory -Path $run -ErrorAction Stop | Out-Null
$start=[Diagnostics.ProcessStartInfo]::new()
$start.FileName=$record.game
$start.WorkingDirectory=Split-Path (Split-Path $record.game)
$start.UseShellExecute=$false
$start.Arguments=$record.arguments
$game=[Diagnostics.Process]::Start($start)
$record.pid=$game.Id
$record.start_time=$game.StartTime.ToString('o')
$record.session_id=[guid]::NewGuid().ToString()
$record.run_directory=$run
$record.phase='runtime_calibration_menu_setup'
$record.scenario.lobby_verified=$false
$record.scenario.PSObject.Properties.Remove('lobby_screenshot')
$record.scenario.PSObject.Properties.Remove('lobby_screenshot_sha256')
$record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'session.json') -Encoding utf8
$record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'active-session.json') -Encoding utf8
[pscustomobject]@{pid=$game.Id;session=$record.session_id;run=$run;phase=$record.phase} | ConvertTo-Json -Compress
