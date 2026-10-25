param(
 [ValidateSet('A_normal_only','B_root_metadata_three','C_data_metadata_three','D_root_metadata_four')][string]$Variant='A_normal_only',
 [switch]$RestartOwned,
 [switch]$ShortPath
)
$ErrorActionPreference='Stop'
$probeRoot=Split-Path $PSScriptRoot
$recordPath=Join-Path $PSScriptRoot 'active-session.json'
$package=Join-Path $probeRoot ('native-ai\side-probes\20261024-175800\'+$Variant)
$config=Join-Path $package ($Variant+'_1.0.skudef')
$big=Join-Path $package ($Variant+'.big')
if(!(Test-Path -LiteralPath $config) -or !(Test-Path -LiteralPath $big)){throw 'Probe package missing'}
$gamePath='E:\RedRar3\Data\RA3_1.12.game'
if((Get-FileHash -LiteralPath $gamePath).Hash.ToLowerInvariant() -ne 'ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'){throw 'Unsupported executable'}
$label=$Variant
if($ShortPath){
 if($Variant -ne 'A_normal_only'){throw 'Short-path isolation currently supports A only'}
 $short=Join-Path (Split-Path $probeRoot) 'Mods\TFProbeA'
 if(!(Test-Path -LiteralPath $short)){New-Item -ItemType Directory -Path $short | Out-Null}
 $shortBig=Join-Path $short 'TFProbeA.big'
 if(Test-Path -LiteralPath $shortBig){if((Get-FileHash -LiteralPath $shortBig).Hash -ne (Get-FileHash -LiteralPath $big).Hash){throw 'Existing short-path package differs'}}else{Copy-Item -LiteralPath $big -Destination $shortBig}
 $config=Join-Path $short 'TFProbeA_1.0.skudef'
 if(!(Test-Path -LiteralPath $config)){[IO.File]::WriteAllText($config,"mod-game 1.12`r`nadd-big TFProbeA.big`r`n",[Text.Encoding]::ASCII)}
 if((Get-Content -LiteralPath $config -Raw).Trim() -ne "mod-game 1.12`r`nadd-big TFProbeA.big"){throw 'Unexpected short-path config'}
 $big=$shortBig;$label='A_short_path'
}
$existing=@(Get-Process ra3_1.12.game -ErrorAction SilentlyContinue)
if($existing.Count){
 if(!$RestartOwned -or !(Test-Path -LiteralPath $recordPath)){throw 'Existing game requires a recorded owned test session'}
 $old=Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
 if($existing.Count -ne 1){throw 'Multiple game processes; refusing restart'}
 $owned=Get-Process -Id $old.pid -ErrorAction SilentlyContinue
 if(!$owned -or $existing[0].Id -ne $owned.Id -or $owned.Path -ne 'E:\RedRar3\Data\RA3_1.12.game' -or $owned.StartTime.ToUniversalTime().Ticks -ne ([datetime]$old.start_time).ToUniversalTime().Ticks){throw 'Owned process identity mismatch'}
 Stop-Process -Id $owned.Id
 if(!$owned.WaitForExit(5000)){throw 'Owned process did not exit'}
}
$run=Join-Path $PSScriptRoot ('runs\'+(Get-Date -Format yyyyMMdd-HHmmss)+'-'+$label)
New-Item -ItemType Directory -Path $run | Out-Null
$start=[Diagnostics.ProcessStartInfo]::new()
$start.FileName=$gamePath;$start.WorkingDirectory='E:\RedRar3';$start.UseShellExecute=$false
$start.Arguments='-ui -win -xres 1600 -yres 900 -modConfig "'+$config+'" -config "E:\RedRar3\RA3_chinese_t_1.12.SkuDef"'
$game=[Diagnostics.Process]::Start($start)
$record=@{pid=$game.Id;start_time=$game.StartTime.ToString('o');session_id=[guid]::NewGuid().ToString();run_directory=$run;game=$gamePath;arguments=$start.Arguments;mod_config=$config;mod_sha256=(Get-FileHash -LiteralPath $big).Hash.ToLowerInvariant();phase='side_binding_probe';variant=$label;seed_controlled=$false}
$record | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $run 'session.json')
$record | ConvertTo-Json | Set-Content -LiteralPath $recordPath
$record | ConvertTo-Json
