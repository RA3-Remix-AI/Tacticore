param([Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference='Stop'
$bridge=Split-Path (Split-Path $PSScriptRoot);$output=[IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath $output){throw 'Readonly probe build needs a new directory'}
New-Item -ItemType Directory -Path $output | Out-Null
$source=Join-Path $output 'source/tactical/runtime';New-Item -ItemType Directory -Path $source | Out-Null
$inputs=@('near_readonly_probe.h','near_readonly_probe_dll.cpp','near_readonly_probe_host.cpp','near_target.h','near_combat.h','memory_io.h','protocol.h','incarnations.h','home_clearance.h','build_near_readonly_probe.ps1')
$rows=@();foreach($name in $inputs){$p=Join-Path $PSScriptRoot $name;$sha=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant();Copy-Item -LiteralPath $p -Destination (Join-Path $source $name);$rows+=@{file=('tactical/runtime/'+$name);sha256=$sha}}
$compiler=Join-Path $bridge 'toolchain/w64devkit/bin/i686-w64-mingw32-g++.exe'
& $compiler -std=c++17 -O2 -Wall -Wextra -Werror -static-libgcc -static-libstdc++ -shared (Join-Path $source 'near_readonly_probe_dll.cpp') '-Wl,--kill-at' -o (Join-Path $output 'TacticoreReadonlyProbe.dll') -luser32 -ladvapi32
if($LASTEXITCODE){throw 'Read-only native diagnostic DLL compilation failed'}
& $compiler -std=c++17 -O2 -Wall -Wextra -Werror -static-libgcc -static-libstdc++ (Join-Path $source 'near_readonly_probe_host.cpp') -o (Join-Path $output 'readonly_probe_host.exe') -luser32
if($LASTEXITCODE){throw 'Read-only native diagnostic transport compilation failed'}
$layout=& (Join-Path $output 'readonly_probe_host.exe') --layout
if($LASTEXITCODE){throw 'Read-only diagnostic layout failed'}
$outputs=@();foreach($name in @('TacticoreReadonlyProbe.dll','readonly_probe_host.exe')){
    $p=Join-Path $output $name;$raw=[IO.File]::ReadAllBytes($p);$offset=[BitConverter]::ToInt32($raw,0x3c)
    if([BitConverter]::ToUInt16($raw,$offset+4) -ne 0x14c){throw 'Readonly diagnostic must be x86'}
    $outputs+=@{file=$name;sha256=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}
}
foreach($row in $rows){if((Get-FileHash -LiteralPath (Join-Path $bridge $row.file) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $row.sha256){throw 'Readonly probe source changed during build'}}
@{kind='near_native_readonly_probe';created_at=(Get-Date -Format o);sources=$rows;outputs=$outputs;compiler=$compiler;compiler_sha256=(Get-FileHash -LiteralPath $compiler -Algorithm SHA256).Hash.ToLowerInvariant();layout=($layout|ConvertFrom-Json);game_entry_detours=0;module_game_sdk_calls=0;unit_control_supported=$false;field_verified=$false;capability_granted=$false} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $output 'manifest.json') -Encoding utf8
$layout | Write-Output
