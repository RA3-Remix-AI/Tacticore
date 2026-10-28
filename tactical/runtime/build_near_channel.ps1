param([string]$OutputDirectory)
$ErrorActionPreference='Stop'
$bridge=Split-Path (Split-Path $PSScriptRoot)
if(!$OutputDirectory){$OutputDirectory=Join-Path $bridge ('reports/near-channel2-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'-'+[guid]::NewGuid().ToString('N').Substring(0,8))}
$output=[IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath $output){throw 'Near channel output must be a new owned directory'}
New-Item -ItemType Directory -Path $output | Out-Null
$baseline=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'bin/build-manifest.json') -Raw | ConvertFrom-Json
$baselineManifest=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'bin/build-manifest.json')).Hash.ToLowerInvariant()
function Assert-ActiveBaseline {
    if((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'bin/build-manifest.json')).Hash.ToLowerInvariant() -ne $baselineManifest){throw 'Active v1 manifest changed'}
    foreach($row in $baseline.inputs){if((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $row.file)).Hash.ToLowerInvariant() -ne $row.sha256){throw 'Active v1 input differs'}}
    foreach($row in $baseline.outputs){if((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot ('bin/'+$row.file))).Hash.ToLowerInvariant() -ne $row.sha256){throw 'Active v1 output differs'}}
}
Assert-ActiveBaseline
$files=@('near_channel.h','near_channel_dll.cpp','near_native_host.cpp','test_near_channel.cpp','near_native_factory.cpp','near_native_factory.h','near_native_admission.h','near_owner.h','near_native_hooks.cpp','near_native_hooks.h','near_attack_lineage.h','near_move_lineage.h','near_combat.h','near_target.h','near_weapon.h','near_build_policy.h','near_build_policy.cpp','native_factory.h','shared_channel.h','hooks.h','memory_io.h','protocol.h','incarnations.h','home_clearance.h','membership.h','native_yield.h','controller.cpp','controller.h','endpoints.h','geometry.h','land_geometry.h','build_near_channel.ps1') | ForEach-Object {'tactical/runtime/'+$_}
$files+='production/persistent/shared.h'
$files+='tactical/runtime/near_layout.py'
$minhook='reference/Ra3-Copilot/ra3-copilot/third_party/minhook-1.3.3'
foreach($name in @('include/MinHook.h','src/buffer.c','src/buffer.h','src/hook.c','src/trampoline.c','src/trampoline.h','src/hde/hde32.c','src/hde/hde32.h','src/hde/table32.h','src/hde/pstdint.h')){$files+=($minhook+'/'+$name)}
$sources=@()
foreach($relative in $files){
    $original=Join-Path $bridge $relative;$frozen=Join-Path (Join-Path $output 'source') $relative
    New-Item -ItemType Directory -Path (Split-Path $frozen) -Force | Out-Null
    Copy-Item -LiteralPath $original -Destination $frozen
    $digest=(Get-FileHash -LiteralPath $original).Hash.ToLowerInvariant()
    if((Get-FileHash -LiteralPath $frozen).Hash.ToLowerInvariant() -ne $digest){throw 'Frozen near channel input differs'}
    $sources+=@{file=$relative;sha256=$digest}
}
$tool=Join-Path $bridge 'toolchain/w64devkit/bin'
$cpp=Join-Path $tool 'i686-w64-mingw32-g++.exe';$cc=Join-Path $tool 'gcc.exe'
foreach($compiler in @($cpp,$cc)){if((& $compiler -dumpmachine) -ne 'i686-w64-mingw32'){throw 'Explicit x86 native compiler required'}}
$root=Join-Path $output 'source';$runtime=Join-Path $root 'tactical/runtime';$library=Join-Path $root $minhook
$objects=@()
foreach($name in @('buffer.c','hook.c','trampoline.c','hde/hde32.c')){
    $object=Join-Path $output (([IO.Path]::GetFileNameWithoutExtension($name))+'.o')
    & $cc -O2 -Wall -c (Join-Path $library ('src/'+$name)) -I (Join-Path $library 'include') -o $object
    if($LASTEXITCODE){throw 'Near channel dependency compilation failed'}
    $objects+=$object
}
foreach($name in @('controller','near_build_policy','near_native_hooks','near_native_factory')){
    $object=Join-Path $output ($name+'.o')
    & $cpp -std=c++17 -O2 -Wall -Wextra -Werror -c (Join-Path $runtime ($name+'.cpp')) -I (Join-Path $library 'include') -o $object
    if($LASTEXITCODE){throw 'Near channel native component compilation failed'}
    $objects+=$object
}
$dll=Join-Path $output 'TacticoreNear2.dll'
& $cpp -std=c++17 -shared -O2 -Wall -Wextra -Werror -static-libgcc -static-libstdc++ '-Wl,--kill-at' (Join-Path $runtime 'near_channel_dll.cpp') @objects -o $dll -luser32 -ladvapi32
if($LASTEXITCODE){throw 'Near channel DLL link failed'}
$nativeHelper=Join-Path $output 'near_runtime_host.exe'
& $cpp -std=c++17 -O2 -Wall -Wextra -Werror -static-libgcc -static-libstdc++ (Join-Path $runtime 'near_native_host.cpp') -o $nativeHelper -luser32 -ladvapi32
if($LASTEXITCODE){throw 'Near channel helper compile failed'}
$test=Join-Path $output 'test_near_channel.exe'
& $cpp -std=c++17 -O2 -Wall -Wextra -Werror -static-libgcc -static-libstdc++ (Join-Path $runtime 'test_near_channel.cpp') -o $test
if($LASTEXITCODE){throw 'Near channel transport test compile failed'}
foreach($file in @($dll,$nativeHelper,$test)){
    $pe=[IO.File]::ReadAllBytes($file);$offset=[BitConverter]::ToInt32($pe,0x3c)
    if([BitConverter]::ToUInt32($pe,$offset) -ne 0x4550 -or [BitConverter]::ToUInt16($pe,$offset+4) -ne 0x14c){throw 'Near channel PE must be x86'}
}
$exports=& (Join-Path $tool 'objdump.exe') -p $dll
if($LASTEXITCODE -or !($exports -match '\bTacticoreNearControl\b')){throw 'Near channel control export absent'}
$layout=& $nativeHelper --layout
if($LASTEXITCODE){throw 'Near channel native layout failed'}
$parsed=$layout | ConvertFrom-Json
if($parsed.protocol -ne 2 -or $parsed.movement -ne 1624056 -or $parsed.combat_capacity -ne 512){throw 'Near channel native layout unexpected'}
$result=& $test
if($LASTEXITCODE -or $result -notmatch '^6 near channel groups passed'){throw 'Near channel transport check failed'}
$result | Write-Output
foreach($row in $sources){if((Get-FileHash -LiteralPath (Join-Path $bridge $row.file)).Hash.ToLowerInvariant() -ne $row.sha256){throw 'Near channel source changed during build'}}
Assert-ActiveBaseline
$outputs=@();foreach($file in (@($dll,$nativeHelper,$test)+$objects)){$outputs+=@{file=[IO.Path]::GetFileName($file);sha256=(Get-FileHash -LiteralPath $file).Hash.ToLowerInvariant()}}
$manifest=@{kind='isolated_near_native_channel2';schema_version=1;created_at=(Get-Date -Format o);architecture='x86';sources=$sources;outputs=$outputs;layout=$parsed;transport_groups=6;transport_result=($result -join "`n");active_v1_manifest_sha256=$baselineManifest;active_v1_unchanged=$true;native_host_hard_ms=180000;native_cleanup_grace_ms=10000;no_new_work_after_ms=90000;stop_requested_after_ms=150000;expected_hook_count=15;expected_restore_mask=32767;native_wire_abi_defined=$true;game_process_opened=$false;hooks_installed=$false;game_sdk_calls=0;model_requests=0;field_verified=$false;capability_granted=$false;full_goal_complete=$false}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $output 'manifest.json') -Encoding utf8
@{manifest=(Join-Path $output 'manifest.json');protocol=2;transport_groups=6;field_verified=$false;capability_granted=$false} | ConvertTo-Json -Compress
