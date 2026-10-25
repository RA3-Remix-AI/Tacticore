param([Parameter(Mandatory=$true)][string]$PackageDirectory,[switch]$RestartOwned,[ValidateSet('commander_live_validation','llm_full_match')][string]$Phase='commander_live_validation')
$ErrorActionPreference='Stop'
$probeRoot=Split-Path $PSScriptRoot
$staging=[IO.Path]::GetFullPath((Join-Path $probeRoot 'native-ai\staging'))+[IO.Path]::DirectorySeparatorChar
$package=[IO.Path]::GetFullPath($PackageDirectory)
if(!$package.StartsWith($staging,[StringComparison]::OrdinalIgnoreCase)){throw 'Expected a commander package in native-ai staging'}
$big=Join-Path $package 'TFNames.big';$registryPath=Join-Path $package 'commander-registry.json'
$registry=Get-Content -LiteralPath $registryPath -Raw | ConvertFrom-Json
$report=Get-Content -LiteralPath (Join-Path $package 'build-report.json') -Raw | ConvertFrom-Json
$digest=(Get-FileHash -LiteralPath $big).Hash.ToLowerInvariant()
if(!$registry.compiled_ids_verified -or $registry.package_sha256 -ne $digest -or $report.big_sha256 -ne $digest -or @($report.streams | Where-Object {!$_.all_baseline_payloads_and_refs_preserved}).Count){throw 'Compiled package evidence mismatch'}
$gamePath='E:\RedRar3\Data\RA3_1.12.game'
if((Get-FileHash -LiteralPath $gamePath).Hash.ToLowerInvariant() -ne 'ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'){throw 'Unsupported executable'}
$recordPath=Join-Path $PSScriptRoot 'active-session.json'
$existing=@(Get-Process ra3_1.12.game -ErrorAction SilentlyContinue)
if($existing.Count){
 if(!$RestartOwned -or !(Test-Path -LiteralPath $recordPath)){throw 'Existing game requires recorded owned test session'}
 $old=Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
 $owned=Get-Process -Id $old.pid -ErrorAction SilentlyContinue
 if($existing.Count -ne 1 -or !$owned -or $owned.Id -ne $existing[0].Id -or $owned.Path -ne $gamePath -or $owned.StartTime.ToUniversalTime().Ticks -ne ([datetime]$old.start_time).ToUniversalTime().Ticks){throw 'Owned process identity mismatch'}
 Stop-Process -Id $owned.Id
 if(!$owned.WaitForExit(5000)){throw 'Owned game did not exit'}
}
$deploy=Join-Path (Split-Path $probeRoot) 'Mods\TFCommanderPlay'
if(!(Test-Path -LiteralPath $deploy)){New-Item -ItemType Directory -Path $deploy | Out-Null}
Copy-Item -LiteralPath $big -Destination (Join-Path $deploy 'TFNames.big') -Force
Copy-Item -LiteralPath $registryPath -Destination (Join-Path $deploy 'commander-registry.json') -Force
$config=Join-Path $deploy 'TFNames_1.0.skudef'
[IO.File]::WriteAllText($config,"mod-game 1.12`r`nadd-big TFNames.big`r`n",[Text.Encoding]::ASCII)
$deployedBig=Join-Path $deploy 'TFNames.big'
if((Get-FileHash -LiteralPath $deployedBig).Hash.ToLowerInvariant() -ne $digest){throw 'Deployed copy mismatch'}
$run=Join-Path $PSScriptRoot ('runs\'+(Get-Date -Format yyyyMMdd-HHmmss)+'-commander')
New-Item -ItemType Directory -Path $run | Out-Null
$start=[Diagnostics.ProcessStartInfo]::new();$start.FileName=$gamePath;$start.WorkingDirectory='E:\RedRar3';$start.UseShellExecute=$false
$start.Arguments='-ui -win -xres 1600 -yres 900 -modConfig "'+$config+'" -config "E:\RedRar3\RA3_chinese_t_1.12.SkuDef"'
$game=[Diagnostics.Process]::Start($start)
$record=@{pid=$game.Id;start_time=$game.StartTime.ToString('o');session_id=[guid]::NewGuid().ToString();run_directory=$run;game=$gamePath;arguments=$start.Arguments;mod_config=$config;mod_big=$deployedBig;mod_sha256=$digest;baseline_mod_sha256=$report.baseline_big_sha256;registry=(Join-Path $deploy 'commander-registry.json');registry_revision=$registry.registry_revision;phase=$Phase;seed_controlled=$false}
$record | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $run 'session.json')
$record | ConvertTo-Json | Set-Content -LiteralPath $recordPath
$record | ConvertTo-Json
