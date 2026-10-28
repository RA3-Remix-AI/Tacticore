param([Parameter(Mandatory=$true)][string]$TemplateSession)
$ErrorActionPreference='Stop'
$runsRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'runs'))+[IO.Path]::DirectorySeparatorChar
$templatePath=[IO.Path]::GetFullPath($TemplateSession)
if(!$templatePath.StartsWith($runsRoot,[StringComparison]::OrdinalIgnoreCase)){throw 'Expected a recorded local session template'}
$record=Get-Content -LiteralPath $templatePath -Raw | ConvertFrom-Json
if($record.scenario.computer_player_index -ne 3 -or $record.scenario.participant_count -ne 2){throw 'Expected the verified two-AI player3 configuration'}
$runningGame=Get-Process | Where-Object { $_.Path -eq $record.game -or $_.ProcessName -match '^ra3(?:[_.]|$)' }
if($runningGame){throw 'Existing game or RA3 launcher must be independently ended before a new match'}
if((Get-FileHash -LiteralPath $record.game -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'){throw 'Game executable changed'}
if((Get-FileHash -LiteralPath $record.mod_big -Algorithm SHA256).Hash.ToLowerInvariant() -ne $record.mod_sha256){throw 'Mod package changed'}
$run=Join-Path $PSScriptRoot ('runs/'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'-desktop-match')
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
$record.phase='desktop_host_end_to_end_live_validation'
$record.scenario.trial_kind='desktop_client_model_native_assisted_full_match'
$record.scenario.model_requests_enabled=$true
$record.scenario.diagnostic_only=$false
$record.scenario.lobby_verified=$false
$record.scenario.PSObject.Properties.Remove('field_source_granted')
$record.scenario.PSObject.Properties.Remove('lobby_screenshot')
$record.scenario.PSObject.Properties.Remove('lobby_screenshot_sha256')
$record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $run 'session.json') -Encoding utf8
$record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'active-session.json') -Encoding utf8
[pscustomobject]@{pid=$game.Id;session=$record.session_id;run=$run;phase=$record.phase;model_enabled=$true;commands_dispatched=0} | ConvertTo-Json -Compress
