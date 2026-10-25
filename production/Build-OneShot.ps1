$ErrorActionPreference='Stop'
$compiler=Join-Path (Split-Path $PSScriptRoot) 'toolchain\w64devkit\bin\g++.exe'
$output=Join-Path $PSScriptRoot 'bin'
New-Item -ItemType Directory $output -Force | Out-Null
& $compiler -std=c++17 -O2 -Wall -Wextra -static-libgcc -static-libstdc++ -shared (Join-Path $PSScriptRoot 'flak_oneshot.cpp') '-Wl,--kill-at' -o (Join-Path $output 'FlakOneShot.dll') -luser32
if($LASTEXITCODE){throw 'One-shot DLL build failed'}
& $compiler -std=c++17 -O2 -Wall -Wextra -static-libgcc -static-libstdc++ (Join-Path $PSScriptRoot 'run_flak.cpp') -o (Join-Path $output 'run_flak.exe') -luser32 -ladvapi32
if($LASTEXITCODE){throw 'One-shot host build failed'}
Get-FileHash (Join-Path $output 'FlakOneShot.dll'),(Join-Path $output 'run_flak.exe')
