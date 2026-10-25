param([switch]$RestartOwned,[string]$Phase='controlled_readonly')
$ErrorActionPreference='Stop'
$probeRoot=Split-Path $PSScriptRoot
$recordPath=Join-Path $PSScriptRoot 'active-session.json'
if(Get-Process ra3_1.12.game -ErrorAction SilentlyContinue){
 if(!$RestartOwned -or !(Test-Path $recordPath)){throw 'Game already running; only the recorded test session may be restarted'}
 $old=Get-Content $recordPath -Raw | ConvertFrom-Json
 $owned=Get-Process -Id $old.pid -ErrorAction SilentlyContinue
 if(!$owned -or $owned.Path -ne 'E:\RedRar3\Data\RA3_1.12.game' -or $owned.StartTime.ToUniversalTime().Ticks -ne ([datetime]$old.start_time).ToUniversalTime().Ticks){throw 'Recorded test process identity mismatch'}
 Stop-Process -Id $owned.Id
 if(!$owned.WaitForExit(5000)){throw 'Owned game did not exit'}
}
$run=Join-Path $PSScriptRoot ('runs\'+(Get-Date -Format yyyyMMdd-HHmmss))
New-Item -ItemType Directory $run -Force | Out-Null
$start=[Diagnostics.ProcessStartInfo]::new();$start.FileName='E:\RedRar3\Data\RA3_1.12.game';$start.WorkingDirectory='E:\RedRar3';$start.UseShellExecute=$false
$mod=Join-Path (Split-Path $probeRoot) 'Mods\TriadFront\TriadFront_1.0.skudef'
$start.Arguments='-ui -win -xres 1600 -yres 900 -modConfig "'+$mod+'" -config "E:\RedRar3\RA3_chinese_t_1.12.SkuDef"'
$game=[Diagnostics.Process]::Start($start)
$record=@{pid=$game.Id;start_time=$game.StartTime.ToString('o');session_id=[guid]::NewGuid().ToString();run_directory=$run;game=$start.FileName;arguments=$start.Arguments;mod_sha256=(Get-FileHash (Join-Path (Split-Path $mod) 'TriadFront.big')).Hash.ToLowerInvariant();phase=$Phase;seed_controlled=$false}
$record | ConvertTo-Json | Set-Content (Join-Path $run 'session.json')
$record | ConvertTo-Json | Set-Content $recordPath
$record | ConvertTo-Json
