$ErrorActionPreference='Stop'
$bridge=Split-Path (Split-Path $PSScriptRoot)
$tool=Join-Path $bridge 'toolchain\w64devkit\bin'
$mh=Join-Path $bridge 'reference\Ra3-Copilot\ra3-copilot\third_party\minhook-1.3.3'
$out=Join-Path $PSScriptRoot 'bin';New-Item -ItemType Directory $out -Force | Out-Null
foreach($source in @('buffer.c','hook.c','trampoline.c','hde\hde32.c')){
 $name=[IO.Path]::GetFileNameWithoutExtension($source)
 & (Join-Path $tool 'gcc.exe') -O2 -Wall -c (Join-Path $mh "src\$source") -I (Join-Path $mh 'include') -o (Join-Path $out "$name.o")
 if($LASTEXITCODE){throw 'MinHook build failed'}
}
& (Join-Path $tool 'g++.exe') -std=c++17 -O2 -Wall -Wextra -static-libgcc -static-libstdc++ -shared (Join-Path $PSScriptRoot 'lease.cpp') -I (Join-Path $mh 'include') (Join-Path $out 'buffer.o') (Join-Path $out 'hook.o') (Join-Path $out 'trampoline.o') (Join-Path $out 'hde32.o') '-Wl,--kill-at' -o (Join-Path $out 'TacticalMissionCombat7.dll') -luser32
if($LASTEXITCODE){throw 'Tactical DLL build failed'}
& (Join-Path $tool 'g++.exe') -std=c++17 -O2 -Wall -Wextra -static-libgcc -static-libstdc++ (Join-Path $PSScriptRoot 'host.cpp') -o (Join-Path $out 'tactical_host.exe') -luser32 -ladvapi32
if($LASTEXITCODE){throw 'Tactical host build failed'}
Get-FileHash (Join-Path $out 'TacticalMissionCombat7.dll'),(Join-Path $out 'tactical_host.exe')
