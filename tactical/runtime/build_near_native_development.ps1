param([string]$OutputDirectory)
$ErrorActionPreference='Stop'
$bridge=Split-Path (Split-Path $PSScriptRoot)
if(!$OutputDirectory){$OutputDirectory=Join-Path $bridge ('reports/near-native-development-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'-'+[guid]::NewGuid().ToString('N').Substring(0,8))}
$output=[IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath $output){throw 'Native development output must be a new owned directory'}
New-Item -ItemType Directory -Path $output | Out-Null
$files=@('near_native_hooks.cpp','near_native_hooks.h','near_attack_lineage.h','near_move_lineage.h','near_combat.h','near_target.h','near_owner.h','near_native_admission.h','near_native_factory.h','near_native_factory.cpp','native_factory.h','shared_channel.h','near_weapon.h','near_build_policy.h','near_build_policy.cpp','hooks.h','memory_io.h','protocol.h','incarnations.h','home_clearance.h','lineage.h','membership.h','native_yield.h','test_near_native_boundary.cpp','test_near_move_regression.cpp','test_controller.cpp','controller.cpp','controller.h','endpoints.h','geometry.h','land_geometry.h','build_near_native_development.ps1') | ForEach-Object {'tactical/runtime/'+$_}
$files+='production/persistent/shared.h'
$minhook='reference/Ra3-Copilot/ra3-copilot/third_party/minhook-1.3.3'
$dependencies=@('include/MinHook.h','src/buffer.c','src/buffer.h','src/hook.c','src/trampoline.c','src/trampoline.h','src/hde/hde32.c','src/hde/hde32.h','src/hde/table32.h','src/hde/pstdint.h')
foreach($name in $dependencies){$files+=($minhook+'/'+$name)}
$sources=@()
foreach($relative in $files){
    $original=Join-Path $bridge $relative;$frozen=Join-Path (Join-Path $output 'source') $relative
    New-Item -ItemType Directory -Path (Split-Path $frozen) -Force | Out-Null
    $hash=(Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash.ToLowerInvariant()
    Copy-Item -LiteralPath $original -Destination $frozen
    if((Get-FileHash -LiteralPath $frozen -Algorithm SHA256).Hash.ToLowerInvariant() -ne $hash){throw 'Frozen native source differs'}
    $sources+=@{file=$relative;sha256=$hash}
}
$tool=Join-Path $bridge 'toolchain/w64devkit/bin'
$cpp=Join-Path $tool 'i686-w64-mingw32-g++.exe';$cc=Join-Path $tool 'gcc.exe'
foreach($compiler in @($cpp,$cc)){if((& $compiler -dumpmachine) -ne 'i686-w64-mingw32'){throw 'Explicit x86 development compiler required'}}
$frozenRoot=Join-Path $output 'source';$runtime=Join-Path $frozenRoot 'tactical/runtime';$library=Join-Path $frozenRoot $minhook
$objects=@()
foreach($name in @('buffer.c','hook.c','trampoline.c','hde/hde32.c')){
    $object=Join-Path $output (([IO.Path]::GetFileNameWithoutExtension($name))+'.o')
    & $cc -O2 -Wall -c (Join-Path $library ('src/'+$name)) -I (Join-Path $library 'include') -o $object
    if($LASTEXITCODE){throw 'Frozen native dependency compilation failed'}
    $objects+=$object
}
$observer=Join-Path $output 'near_native_hooks.o'
& $cpp -std=c++17 -O2 -Wall -Wextra -Werror -c (Join-Path $runtime 'near_native_hooks.cpp') -I (Join-Path $library 'include') -o $observer
if($LASTEXITCODE){throw 'Native attack observer compilation failed'}
$policy=Join-Path $output 'near_build_policy.o'
& $cpp -std=c++17 -O2 -Wall -Wextra -Werror -c (Join-Path $runtime 'near_build_policy.cpp') -o $policy
if($LASTEXITCODE){throw 'Exact native build policy compilation failed'}
$factory=Join-Path $output 'near_native_factory.o'
& $cpp -std=c++17 -O2 -Wall -Wextra -Werror -c (Join-Path $runtime 'near_native_factory.cpp') -o $factory
if($LASTEXITCODE){throw 'Near native execution factory compilation failed'}
$motion=Join-Path $output 'controller.o'
& $cpp -std=c++17 -O2 -Wall -Wextra -Werror -c (Join-Path $runtime 'controller.cpp') -o $motion
if($LASTEXITCODE){throw 'Original motion controller compilation failed'}
$test=Join-Path $output 'test_near_native_boundary.exe'
& $cpp -std=c++17 -O2 -Wall -Wextra -Werror -static-libgcc -static-libstdc++ (Join-Path $runtime 'test_near_native_boundary.cpp') $observer $policy $factory $motion @objects -o $test -luser32 -ladvapi32
if($LASTEXITCODE){throw 'Actual native-boundary link failed'}
$pe=[IO.File]::ReadAllBytes($test);$peOffset=[BitConverter]::ToInt32($pe,0x3c)
if([BitConverter]::ToUInt32($pe,$peOffset) -ne 0x4550 -or [BitConverter]::ToUInt16($pe,$peOffset+4) -ne 0x14c){throw 'Actual native-boundary executable must be x86'}
$result=& $test
if($LASTEXITCODE){throw 'Actual native-boundary offline check failed'}
$result | Write-Output
$regression=Join-Path $output 'test_near_move_regression.exe'
& $cpp -std=c++17 -O2 -Wall -Wextra -Werror -static-libgcc -static-libstdc++ (Join-Path $runtime 'test_near_move_regression.cpp') (Join-Path $runtime 'controller.cpp') -o $regression
if($LASTEXITCODE){throw 'Actual Move/Stop regression compilation failed'}
$regressionResult=& $regression
if($LASTEXITCODE){throw 'Actual Move/Stop regression failed'}
$regressionReport=$regressionResult | ConvertFrom-Json
if(!$regressionReport.passed -or $regressionReport.actual_cpp_function_suites -ne 51 -or $regressionReport.game_access -or $regressionReport.field_verified){throw 'Invalid Move/Stop regression result'}
$regressionResult | Write-Output
foreach($row in $sources){if((Get-FileHash -LiteralPath (Join-Path $bridge $row.file) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $row.sha256){throw 'Native source changed during build'}}
$outputs=@();foreach($path in (@($observer,$policy,$factory,$motion,$test,$regression)+$objects)){$outputs+=@{file=[IO.Path]::GetFileName($path);sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}}
$compilers=@();foreach($compiler in @($cpp,$cc)){$compilers+=@{file=$compiler;sha256=(Get-FileHash -LiteralPath $compiler -Algorithm SHA256).Hash.ToLowerInvariant()}}
$manifest=@{schema_version=1;kind='near_native_observer_development';created_at=(Get-Date -Format o);architecture='x86';sources=$sources;outputs=$outputs;compilers=$compilers;result=($result -join "`n");offline_native_boundary_groups=5;regression_test_suites=51;regression_result=($regressionResult -join "`n");game_process_opened=$false;hooks_installed=$false;game_sdk_calls=0;published_wire_abi=$false;field_verified=$false;capability_granted=$false;full_goal_complete=$false;default_admission='deny';expected_hook_count=15;expected_restore_mask=32767}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $output 'manifest.json') -Encoding utf8
@{manifest=(Join-Path $output 'manifest.json');native_boundary_groups=5;field_verified=$false} | ConvertTo-Json -Compress
