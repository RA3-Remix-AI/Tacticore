param([string]$OutputDirectory)
$ErrorActionPreference='Stop'
$bridge=Split-Path (Split-Path $PSScriptRoot)
if(!$OutputDirectory){
    $stamp=(Get-Date -Format 'yyyyMMdd-HHmmss')+'-'+[guid]::NewGuid().ToString('N').Substring(0,8)
    $OutputDirectory=Join-Path $bridge ('reports/native-near-combat-replay-'+$stamp)
}
$output=[IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath $output){throw 'Replay output must be a new owned directory'}
New-Item -ItemType Directory -Path $output -ErrorAction Stop | Out-Null
$source=Join-Path $output 'source\tactical\runtime'
New-Item -ItemType Directory -Path $source -ErrorAction Stop | Out-Null
$inputs=@('near_combat.h','near_target.h','near_owner.h','near_attack_lineage.h','near_move_lineage.h','near_native_admission.h','near_native_hooks.h','near_weapon.h','hooks.h','test_near_native_admission.cpp','test_near_combat.cpp','test_near_target.cpp','test_near_owner.cpp','test_near_attack_lineage.cpp','controller.h','controller.cpp','protocol.h','memory_io.h','incarnations.h','home_clearance.h','build_near_combat_offline.ps1','test_near_combat_contract.py','audit_near_native.py')
$sourceRows=@()
foreach($name in $inputs){
    $original=Join-Path $PSScriptRoot $name
    $digest=(Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash.ToLowerInvariant()
    Copy-Item -LiteralPath $original -Destination (Join-Path $source $name)
    if((Get-FileHash -LiteralPath (Join-Path $source $name) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $digest){throw 'Frozen replay input differs'}
    $sourceRows+=@{file=('tactical/runtime/'+$name);sha256=$digest}
}
$outputs=@()
$vcvars='C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat'
if(!(Test-Path -LiteralPath $vcvars)){throw 'Installed x64 MSVC environment required'}
$environmentStart=[Diagnostics.ProcessStartInfo]::new($env:ComSpec)
$environmentStart.UseShellExecute=$false
$environmentStart.RedirectStandardOutput=$true
$environmentStart.Arguments='/d /s /c ""'+$vcvars+'" >nul && set"'
$environmentProcess=[Diagnostics.Process]::Start($environmentStart)
$environmentLines=$environmentProcess.StandardOutput.ReadToEnd() -split "`r?`n"
$environmentProcess.WaitForExit()
if($environmentProcess.ExitCode){throw 'x64 compiler environment failed'}
$nativeEnvironment=@{}
foreach($line in $environmentLines){
    if($line -match '^([^=]+)=(.*)$'){$nativeEnvironment[$matches[1]]=$matches[2]}
}
$compiler64=Join-Path $nativeEnvironment['VCToolsInstallDir'] 'bin/Hostx64/x64/cl.exe'
if(!(Test-Path -LiteralPath $compiler64)){throw 'Installed x64 compiler unavailable'}
foreach($architecture in @('x64','x86')){
    $compiler=if($architecture -eq 'x86'){Join-Path $bridge 'toolchain/w64devkit/bin/i686-w64-mingw32-g++.exe'}else{$compiler64}
    if(!(Test-Path -LiteralPath $compiler)){throw 'Fixed replay compiler unavailable'}
    $compilerHash=(Get-FileHash -LiteralPath $compiler -Algorithm SHA256).Hash.ToLowerInvariant()
    foreach($test in @('near_combat','near_target','near_owner','near_attack_lineage','near_native_admission')){
        $executable=Join-Path $output ('test_'+$test+'-'+$architecture+'.exe')
        if($architecture -eq 'x64'){
            $start=[Diagnostics.ProcessStartInfo]::new($compiler)
            $start.UseShellExecute=$false
            $start.WorkingDirectory=$output
            foreach($key in $nativeEnvironment.Keys){$start.Environment[$key]=$nativeEnvironment[$key]}
            $compileInputs=@((Join-Path $source ('test_'+$test+'.cpp')))
            if($test -in @('near_owner','near_native_admission')){$compileInputs+=Join-Path $source 'controller.cpp'}
            $objects=Join-Path $output ($test+'-x64-objects')
            New-Item -ItemType Directory -Path $objects | Out-Null
            foreach($argument in (@('/nologo','/std:c++17','/O2','/W4','/WX','/EHsc','/MT')+$compileInputs+@(('/Fo'+$objects+'\'),('/Fe'+$executable)))){$start.ArgumentList.Add($argument)}
            $compile=[Diagnostics.Process]::Start($start)
            $compile.WaitForExit()
            if($compile.ExitCode){throw 'x64 near-combat replay compile failed'}
        }else{
            $compileInputs=@((Join-Path $source ('test_'+$test+'.cpp')))
            if($test -in @('near_owner','near_native_admission')){$compileInputs+=Join-Path $source 'controller.cpp'}
            & $compiler -std=c++17 -O2 -Wall -Wextra -Werror -static-libgcc -static-libstdc++ @compileInputs -o $executable
            if($LASTEXITCODE){throw 'x86 near-combat replay compile failed'}
        }
        $pe=[IO.File]::ReadAllBytes($executable)
        $peOffset=[BitConverter]::ToInt32($pe,0x3c)
        $expectedMachine=if($architecture -eq 'x86'){0x14c}else{0x8664}
        if([BitConverter]::ToUInt32($pe,$peOffset) -ne 0x4550 -or [BitConverter]::ToUInt16($pe,$peOffset+4) -ne $expectedMachine){throw 'Replay executable architecture differs from label'}
        $result=& $executable
        if($LASTEXITCODE){throw 'Near-combat replay execution failed'}
        $result | Write-Output
        $outputs+=@{file=[IO.Path]::GetFileName($executable);architecture=$architecture;sha256=(Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash.ToLowerInvariant();compiler=$compiler;compiler_sha256=$compilerHash;result=($result -join "`n")}
    }
}
foreach($row in $sourceRows){
    $name=[IO.Path]::GetFileName($row.file)
    if((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $name) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $row.sha256){throw 'Replay input changed during compilation'}
}
$manifest=@{schema_version=1;kind='near_combat_development_replay';created_at=(Get-Date -Format o);sources=$sourceRows;outputs=$outputs;unique_groups=64;architectures=@('x64','x86');native_game_calls=0;explicit_fake_io=$true;native_wire_abi_defined=$false;field_verified=$false;capability_granted=$false;full_goal_complete=$false}
$manifestPath=Join-Path $output 'manifest.json'
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding utf8
@{manifest=$manifestPath;unique_groups=64;architectures=2;field_verified=$false;capability_granted=$false} | ConvertTo-Json -Compress
