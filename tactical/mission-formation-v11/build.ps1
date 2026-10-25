$ErrorActionPreference='Stop'
$bridge=Split-Path (Split-Path $PSScriptRoot)
$tool=Join-Path $bridge 'toolchain\w64devkit\bin'
$mh=Join-Path $bridge 'reference\Ra3-Copilot\ra3-copilot\third_party\minhook-1.3.3'
$out=Join-Path $PSScriptRoot 'bin';New-Item -ItemType Directory $out -Force | Out-Null
$python=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python (Join-Path $PSScriptRoot 'freeze_native.py') --record-inputs
if($LASTEXITCODE){throw 'Native input fingerprint failed'}
foreach($source in @('buffer.c','hook.c','trampoline.c','hde\hde32.c')){
 $name=[IO.Path]::GetFileNameWithoutExtension($source)
 & (Join-Path $tool 'gcc.exe') -O2 -Wall -c (Join-Path $mh "src\$source") -I (Join-Path $mh 'include') -o (Join-Path $out "$name.o")
 if($LASTEXITCODE){throw 'MinHook build failed'}
}
& (Join-Path $tool 'g++.exe') -std=c++17 -O2 -Wall -Wextra -static-libgcc -static-libstdc++ -shared (Join-Path $PSScriptRoot 'lease.cpp') -I (Join-Path $mh 'include') (Join-Path $out 'buffer.o') (Join-Path $out 'hook.o') (Join-Path $out 'trampoline.o') (Join-Path $out 'hde32.o') '-Wl,--kill-at' -o (Join-Path $out 'TacticalMissionFormation11.dll') -luser32
if($LASTEXITCODE){throw 'Tactical DLL build failed'}
& (Join-Path $tool 'g++.exe') -std=c++17 -O2 -Wall -Wextra -static-libgcc -static-libstdc++ (Join-Path $PSScriptRoot 'host.cpp') -o (Join-Path $out 'tactical_host.exe') -luser32 -ladvapi32
if($LASTEXITCODE){throw 'Tactical host build failed'}
Get-FileHash (Join-Path $out 'TacticalMissionFormation11.dll'),(Join-Path $out 'tactical_host.exe')

& $python (Join-Path $PSScriptRoot 'freeze_native.py')
if($LASTEXITCODE){throw 'Native source binding failed'}

& (Join-Path $tool 'g++.exe') -std=c++17 -O2 -Wall -static-libgcc -static-libstdc++ (Join-Path $PSScriptRoot 'native_snapshot.cpp') -o (Join-Path $out 'native_snapshot.exe') -ladvapi32
if($LASTEXITCODE){throw 'Read-only snapshot build failed'}
& (Join-Path $tool 'g++.exe') -std=c++17 -O2 -w (Join-Path $PSScriptRoot 'test_breadcrumb_native.cpp') -o (Join-Path $out 'test_breadcrumb_native.exe')
if($LASTEXITCODE){throw 'Native pure regression build failed'}
& (Join-Path $out 'test_breadcrumb_native.exe') (Join-Path $PSScriptRoot 'simulation-2km-native.json') | Tee-Object -FilePath (Join-Path $PSScriptRoot 'native-regression-results.jsonl')
if($LASTEXITCODE){throw 'Native pure regression failed'}
& (Join-Path $tool 'g++.exe') -std=c++17 -O2 -w -static-libgcc -static-libstdc++ (Join-Path $PSScriptRoot 'test_pending_native.cpp') -o (Join-Path $out 'test_pending_native.exe')
if($LASTEXITCODE){throw 'Pending lineage pure regression build failed'}
& (Join-Path $out 'test_pending_native.exe') (Join-Path $PSScriptRoot 'pending-native-positive.json') | Tee-Object -FilePath (Join-Path $PSScriptRoot 'pending-regression-results.json')
if($LASTEXITCODE){throw 'Pending lineage pure regression failed'}
& (Join-Path $tool 'g++.exe') -std=c++17 -O2 -Wall -static-libgcc -static-libstdc++ (Join-Path $PSScriptRoot 'test_scheduler_native.cpp') -o (Join-Path $out 'test_scheduler_native.exe') -luser32
if($LASTEXITCODE){throw 'Message scheduler pure regression build failed'}
& (Join-Path $out 'test_scheduler_native.exe') (Join-Path $PSScriptRoot 'scheduler-native-positive.json') | Tee-Object -FilePath (Join-Path $PSScriptRoot 'scheduler-regression-results.jsonl')
if($LASTEXITCODE){throw 'Message scheduler pure regression failed'}
& (Join-Path $tool 'g++.exe') -std=c++17 -O2 -Wall -static-libgcc -static-libstdc++ (Join-Path $PSScriptRoot 'test_tls_alignment_native.cpp') -o (Join-Path $out 'test_tls_alignment_native.exe') -luser32
if($LASTEXITCODE){throw 'TLS alignment regression build failed'}
& (Join-Path $out 'test_tls_alignment_native.exe') (Join-Path $PSScriptRoot 'tls-alignment-regression.json') | Tee-Object -FilePath (Join-Path $PSScriptRoot 'tls-alignment-regression.log')
if($LASTEXITCODE){throw 'TLS alignment regression failed'}
