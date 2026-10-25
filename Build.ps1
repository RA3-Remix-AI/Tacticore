$ErrorActionPreference='Stop'
$compiler=Join-Path $PSScriptRoot 'toolchain\w64devkit\bin\g++.exe'
$output=Join-Path $PSScriptRoot 'bin'
New-Item -ItemType Directory $output -Force | Out-Null
& $compiler -std=c++17 -O2 -Wall -Wextra -static-libgcc -static-libstdc++ -shared (Join-Path $PSScriptRoot 'bridge.cpp') -o (Join-Path $output 'bridge.dll') '-Wl,--kill-at' -luser32
if($LASTEXITCODE){throw 'Bridge compilation failed'}
& $compiler -std=c++17 -O2 -Wall -Wextra -static-libgcc -static-libstdc++ (Join-Path $PSScriptRoot 'controller.cpp') -o (Join-Path $output 'controller.exe') -luser32
if($LASTEXITCODE){throw 'Controller compilation failed'}
Get-FileHash (Join-Path $output 'bridge.dll'),(Join-Path $output 'controller.exe')
