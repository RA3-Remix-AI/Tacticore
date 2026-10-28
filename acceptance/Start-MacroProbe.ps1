param([Parameter(Mandatory=$true)][string]$PackageDirectory)
$ErrorActionPreference='Stop'
$probeRoot=Split-Path $PSScriptRoot
$staging=[IO.Path]::GetFullPath((Join-Path $probeRoot 'native-ai\staging'))+[IO.Path]::DirectorySeparatorChar
$package=[IO.Path]::GetFullPath($PackageDirectory)
if(!$package.StartsWith($staging,[StringComparison]::OrdinalIgnoreCase)){throw 'Require an isolated macro staging package'}
$reportPath=Join-Path $package 'build-report.json'
$report=Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
$big=Join-Path $package 'TFMacroProbe.big'
$digest=(Get-FileHash -LiteralPath $big).Hash.ToLowerInvariant()
$assetCount=3
if($report.variant -eq 'expanded_macro_policy_v1'){
 $assetCount=14
 if($null -ne $report.regional_waypoints_revision){
  if($report.regional_waypoints_revision -notin @(1,2,3) -or $report.regional_map_id -ne 'map_mp_2_black1b' -or $report.regional_map_sha256 -ne 'ec4775f8c2d50ad15576544f00071ed1e409ee70f5a9dc7610282584e6798d66' -or @($report.regional_waypoints).Count -ne 2 -or $report.regional_field_verified -ne $false -or $report.regional_capability_granted -ne $false){throw 'Require reviewed, unqualified public waypoint research package'}
  $assetCount=16
 }
 if(@($report.consumers).Count -ne 13 -or $report.product_capability_granted -ne $false -or @($report.consumers | Where-Object {$_.field_verified -or $_.capability_granted}).Count){throw 'Expanded macro consumers must remain field-unqualified'}
}
if($report.kind -ne 'isolated_native_macro_probe' -or !$report.compiled -or $report.deployed -or $report.big_sha256 -ne $digest -or !$report.big_roundtrip_verified -or !$report.stock_micro_manager_preserved -or $report.original_assets_replaced -ne 0 -or @($report.assets).Count -ne $assetCount -or @($report.streams).Count -ne 3 -or @($report.streams | Where-Object {!$_.all_baseline_payloads_and_refs_preserved -or !$_.compiled_flags_present -or $_.added_assets -ne $assetCount}).Count){throw 'Macro probe compilation/preservation evidence mismatch'}
if((Get-FileHash -LiteralPath (Join-Path $package 'MacroProbe.xml')).Hash.ToLowerInvariant() -ne $report.macro_xml_sha256){throw 'Macro XML changed'}
$gamePath='E:\RedRar3\Data\RA3_1.12.game'
if((Get-FileHash -LiteralPath $gamePath).Hash.ToLowerInvariant() -ne 'ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165'){throw 'Unsupported game executable'}
if(@(Get-Process ra3_1.12.game -ErrorAction SilentlyContinue).Count){throw 'Existing game: no implicit restart allowed'}
$label=(Get-Date -Format yyyyMMdd-HHmmss)+'-macro-probe'
$run=Join-Path $PSScriptRoot ('runs\'+$label)
$deploy=Join-Path (Split-Path $probeRoot) ('Mods\TFMacroProbe-'+$label)
if((Test-Path -LiteralPath $run) -or (Test-Path -LiteralPath $deploy)){throw 'Fresh run and deployment paths required'}
New-Item -ItemType Directory -Path $run,$deploy | Out-Null
$sources=Join-Path $run 'pre-launch-source'
New-Item -ItemType Directory -Path $sources | Out-Null
$files=@('acceptance/Start-MacroProbe.ps1','native-ai/stage_macro_probe.py','native-ai/stage_macro_policy.py','native-ai/test_stage_macro_policy.py','native-ai/read_script_flags.py','native-ai/test_script_flags.py','native-ai/audit_macro_interfaces.py','native-ai/macro_observation.py','native-ai/test_macro_observation.py','native-ai/assess_macro_probe.py','native-ai/macro-flag-probe/shared.h','native-ai/macro-flag-probe/native.cpp','native-ai/macro-flag-probe/host.cpp','native-ai/macro-flag-probe/build.py','native-ai/macro-flag-probe/client.py','docs/commander-macro-goal-20261027.md')
$files+=@('native-ai/macro-policy-runtime/shared.h','native-ai/macro-policy-runtime/native.cpp','native-ai/macro-policy-runtime/host.cpp','native-ai/macro-policy-runtime/build.py','native-ai/macro-policy-runtime/client.py')
$files+=@('native-ai/macro_build_observation.py','native-ai/read_macro_build.py','native-ai/test_macro_build_observation.py')
$files+=@('native-ai/audit_macro_build.py','acceptance/macro_early_build_trial.py')
$files+=@('native-ai/stage_macro_regions.py','native-ai/read_map_waypoints.py','native-ai/test_stage_macro_regions.py')
$pins=@()
foreach($relative in $files){
 $source=Join-Path $probeRoot $relative
 $target=Join-Path $sources $relative
 [IO.Directory]::CreateDirectory((Split-Path $target)) | Out-Null
 Copy-Item -LiteralPath $source -Destination $target
 $pins+=@{path=$source;relative=$relative;sha256=(Get-FileHash -LiteralPath $target).Hash.ToLowerInvariant()}
}
$pins | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $sources 'sources.json') -Encoding utf8
Copy-Item -LiteralPath $big -Destination (Join-Path $deploy 'TFMacroProbe.big')
Copy-Item -LiteralPath $reportPath -Destination (Join-Path $run 'package-build-report.json')
Copy-Item -LiteralPath (Join-Path $package 'MacroProbe.xml') -Destination (Join-Path $run 'MacroProbe.xml')
$config=Join-Path $deploy 'TFMacroProbe_1.0.skudef'
[IO.File]::WriteAllText($config,"mod-game 1.12`r`nadd-big TFMacroProbe.big`r`n",[Text.Encoding]::ASCII)
if((Get-FileHash -LiteralPath (Join-Path $deploy 'TFMacroProbe.big')).Hash.ToLowerInvariant() -ne $digest){throw 'Deployed probe copy mismatch'}
$start=[Diagnostics.ProcessStartInfo]::new();$start.FileName=$gamePath;$start.WorkingDirectory='E:\RedRar3';$start.UseShellExecute=$false
$start.Arguments='-ui -win -xres 1600 -yres 900 -modConfig "'+$config+'" -config "E:\RedRar3\RA3_chinese_t_1.12.SkuDef"'
$game=[Diagnostics.Process]::Start($start)
$record=@{pid=$game.Id;start_time=$game.StartTime.ToString('o');process_creation_filetime=$game.StartTime.ToUniversalTime().ToFileTimeUtc();session_id=[guid]::NewGuid().ToString();run_directory=$run;game=$gamePath;arguments=$start.Arguments;mod_config=$config;mod_big=(Join-Path $deploy 'TFMacroProbe.big');mod_sha256=$digest;baseline_mod_sha256=$report.baseline_big_sha256;macro_package_report=$reportPath;phase='macro_native_interface_probe';seed_controlled=$false;real_model_calls=0;full_goal_complete=$false}
$record | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $run 'session.json') -Encoding utf8
$record | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'active-session.json') -Encoding utf8
$record | ConvertTo-Json
