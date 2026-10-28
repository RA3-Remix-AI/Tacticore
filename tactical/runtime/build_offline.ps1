$ErrorActionPreference='Stop'
$bridge=Split-Path (Split-Path $PSScriptRoot)
$compiler=Join-Path $bridge 'toolchain/w64devkit/bin/g++.exe'
$out=Join-Path $PSScriptRoot 'bin'
New-Item -ItemType Directory $out -Force | Out-Null
& $compiler -std=c++17 -O2 -Wall -Wextra -Werror -static-libgcc -static-libstdc++ (Join-Path $PSScriptRoot 'controller.cpp') (Join-Path $PSScriptRoot 'test_controller.cpp') -o (Join-Path $out 'test_controller.exe')
if($LASTEXITCODE){throw 'Active runtime actual-function C++ build failed'}
& (Join-Path $out 'test_controller.exe')
if($LASTEXITCODE){throw 'Active runtime offline gate failed'}
& $compiler -std=c++17 -O2 -Wall -Wextra -Werror -c (Join-Path $PSScriptRoot 'windows_calls.cpp') -o (Join-Path $out 'windows_calls.o')
if($LASTEXITCODE){throw 'Original SDK boundary compilation failed'}
