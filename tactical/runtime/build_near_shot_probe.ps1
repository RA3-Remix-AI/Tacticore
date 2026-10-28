param([Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference='Stop'
$bridge=Split-Path (Split-Path $PSScriptRoot);$output=[IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath $output){throw 'Passive shot probe requires a fresh isolated directory'}
New-Item -ItemType Directory -Path $output | Out-Null
$baseline=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'bin/build-manifest.json') -Raw | ConvertFrom-Json
function Assert-Baseline {
 foreach($row in $baseline.inputs){if((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $row.file)).Hash.ToLowerInvariant() -ne $row.sha256){throw 'Original v1 source changed'}}
 foreach($row in $baseline.outputs){if((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot ('bin/'+$row.file))).Hash.ToLowerInvariant() -ne $row.sha256){throw 'Original v1 artifact changed'}}
}
Assert-Baseline
$files=@('near_shot_probe.h','near_shot_probe_dll.cpp','near_shot_probe_host.cpp','near_shot_target_policy.h','test_near_shot_probe.cpp','near_build_policy.h','near_build_policy.cpp','near_weapon.h','near_target.h','near_combat.h','protocol.h','memory_io.h','incarnations.h','home_clearance.h','build_near_shot_probe.ps1') | ForEach-Object {'tactical/runtime/'+$_}
$minhook='reference/Ra3-Copilot/ra3-copilot/third_party/minhook-1.3.3'
foreach($name in @('include/MinHook.h','src/buffer.c','src/buffer.h','src/hook.c','src/trampoline.c','src/trampoline.h','src/hde/hde32.c','src/hde/hde32.h','src/hde/table32.h','src/hde/pstdint.h')){$files+=($minhook+'/'+$name)}
$rows=@()
foreach($relative in $files){
 $source=Join-Path $bridge $relative;$dest=Join-Path (Join-Path $output 'source') $relative
 New-Item -ItemType Directory -Path (Split-Path $dest) -Force | Out-Null
 Copy-Item -LiteralPath $source -Destination $dest;$digest=(Get-FileHash -LiteralPath $source).Hash.ToLowerInvariant()
 if((Get-FileHash -LiteralPath $dest).Hash.ToLowerInvariant() -ne $digest){throw 'Shot probe frozen source differs'}
 $rows+=@{file=$relative;sha256=$digest}
}
$tools=Join-Path $bridge 'toolchain/w64devkit/bin';$cpp=Join-Path $tools 'i686-w64-mingw32-g++.exe';$cc=Join-Path $tools 'gcc.exe'
foreach($compiler in @($cpp,$cc)){if((& $compiler -dumpmachine) -ne 'i686-w64-mingw32'){throw 'Actual x86 compiler required'}}
$source=Join-Path $output 'source/tactical/runtime';$library=Join-Path (Join-Path $output 'source') $minhook;$objects=@()
foreach($name in @('buffer.c','hook.c','trampoline.c','hde/hde32.c')){
 $object=Join-Path $output (([IO.Path]::GetFileNameWithoutExtension($name))+'.o')
 & $cc -O2 -Wall -c (Join-Path $library ('src/'+$name)) -I (Join-Path $library 'include') -o $object
 if($LASTEXITCODE){throw 'Shot probe dependency compile failed'}
 $objects+=$object
}
$dll=Join-Path $output 'TacticoreShotProbe.dll'
& $cpp -std=c++17 -O2 -Wall -Wextra -Werror -static-libgcc -static-libstdc++ -shared (Join-Path $source 'near_shot_probe_dll.cpp') (Join-Path $source 'near_build_policy.cpp') @objects -I (Join-Path $library 'include') '-Wl,--kill-at' -o $dll -luser32 -ladvapi32
if($LASTEXITCODE){throw 'Passive shot probe DLL compile failed'}
$helper=Join-Path $output 'shot_probe_host.exe'
& $cpp -std=c++17 -O2 -Wall -Wextra -Werror -static-libgcc -static-libstdc++ (Join-Path $source 'near_shot_probe_host.cpp') -o $helper -luser32
if($LASTEXITCODE){throw 'Passive shot probe helper compile failed'}
$test=Join-Path $output 'test_near_shot_probe.exe'
& $cpp -std=c++17 -O2 -Wall -Wextra -Werror -static-libgcc -static-libstdc++ (Join-Path $source 'test_near_shot_probe.cpp') -o $test -luser32
if($LASTEXITCODE){throw 'Passive shot probe test compile failed'}
foreach($path in @($dll,$helper,$test)){
 $bytes=[IO.File]::ReadAllBytes($path);$offset=[BitConverter]::ToInt32($bytes,0x3c)
 if([BitConverter]::ToUInt16($bytes,$offset+4) -ne 0x14c){throw 'Passive shot probe artifact must be x86'}
}
$result=& $test $dll
if($LASTEXITCODE -or $result -notmatch '^7 passive shot probe boundary groups passed'){throw 'Passive shot probe refusal/terminal tests failed'}
$layout=& $helper --layout
if($LASTEXITCODE){throw 'Passive shot probe layout failed'}
foreach($row in $rows){if((Get-FileHash -LiteralPath (Join-Path $bridge $row.file)).Hash.ToLowerInvariant() -ne $row.sha256){throw 'Shot probe source changed during build'}}
Assert-Baseline
$outputs=@();foreach($path in (@($dll,$helper,$test)+$objects)){$outputs+=@{file=[IO.Path]::GetFileName($path);sha256=(Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant()}}
$manifest=@{kind='isolated_native_passive_shot_probe';created_at=(Get-Date -Format o);sources=$rows;outputs=$outputs;layout=($layout|ConvertFrom-Json);boundary_groups=7;boundary_result=($result -join "`n");game_entry_detours=3;expected_restore_mask=7;module_game_sdk_calls=0;unit_control_supported=$false;task_attribution_supported=$false;game_process_opened=$false;field_verified=$false;capability_granted=$false;full_goal_complete=$false}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $output 'manifest.json') -Encoding utf8
$result | Write-Output
$layout | Write-Output
