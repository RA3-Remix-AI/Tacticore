$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot
$tool=Join-Path $root 'toolchain\w64devkit\bin'
$minhook=Join-Path $root 'reference\Ra3-Copilot\ra3-copilot\third_party\minhook-1.3.3'
$output=Join-Path $PSScriptRoot 'bin';New-Item -ItemType Directory $output -Force | Out-Null
foreach($source in @('buffer.c','hook.c','trampoline.c','hde\hde32.c')){
 $name=[IO.Path]::GetFileNameWithoutExtension($source)
 & (Join-Path $tool 'gcc.exe') -O2 -Wall -c (Join-Path $minhook "src\$source") -I (Join-Path $minhook 'include') -o (Join-Path $output "$name.o")
 if($LASTEXITCODE){throw "MinHook compilation failed: $source"}
}
& (Join-Path $tool 'g++.exe') -std=c++17 -O2 -Wall -Wextra -static-libgcc -static-libstdc++ -shared (Join-Path $PSScriptRoot 'production_observer.cpp') -I (Join-Path $minhook 'include') (Join-Path $output 'buffer.o') (Join-Path $output 'hook.o') (Join-Path $output 'trampoline.o') (Join-Path $output 'hde32.o') '-Wl,--kill-at' -o (Join-Path $output 'NativeProductionObserver.dll') -luser32
if($LASTEXITCODE){throw 'Observer DLL compilation failed'}
& (Join-Path $tool 'g++.exe') -std=c++17 -O2 -Wall -Wextra -static-libgcc -static-libstdc++ (Join-Path $PSScriptRoot 'observe_build.cpp') -o (Join-Path $output 'observe_build.exe') -luser32 -ladvapi32
if($LASTEXITCODE){throw 'Observer controller compilation failed'}
Copy-Item (Join-Path $minhook 'LICENSE.txt') (Join-Path $output 'MinHook-LICENSE.txt')
Get-FileHash (Join-Path $output 'NativeProductionObserver.dll'),(Join-Path $output 'observe_build.exe')
