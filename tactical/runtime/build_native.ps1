$ErrorActionPreference='Stop'
$repo=Split-Path (Split-Path $PSScriptRoot)
$tool=Join-Path $repo 'toolchain/w64devkit/bin'
$minhook=Join-Path $repo 'reference/Ra3-Copilot/ra3-copilot/third_party/minhook-1.3.3'
$out=Join-Path $PSScriptRoot 'bin'
New-Item -ItemType Directory -Path $out -Force | Out-Null
$msvcRoot='C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC'
$compiler64=Get-ChildItem -LiteralPath $msvcRoot -Directory | Sort-Object Name -Descending | ForEach-Object {Join-Path $_.FullName 'bin/Hostx64/x64/cl.exe'} | Where-Object {Test-Path -LiteralPath $_} | Select-Object -First 1
if(!$compiler64){throw 'Installed x64 compiler required for atomic host publication'}
& $compiler64 /nologo /O2 /GS- /LD (Join-Path $PSScriptRoot 'atomic_publish.cpp') ('/Fo'+(Join-Path $out 'atomic_publish.obj')) /link /NOENTRY /NODEFAULTLIB /MACHINE:X64 ('/OUT:'+(Join-Path $out 'atomic_publish.dll')) ('/IMPLIB:'+(Join-Path $out 'atomic_publish.lib'))
if($LASTEXITCODE){throw 'Host atomic publication bridge compilation failed'}
$objects=@()
foreach($relative in @('buffer.c','hook.c','trampoline.c','hde/hde32.c')){
    $object=Join-Path $out (([IO.Path]::GetFileNameWithoutExtension($relative))+'.o')
    & (Join-Path $tool 'gcc.exe') -O2 -Wall -c (Join-Path $minhook "src/$relative") -I (Join-Path $minhook 'include') -o $object
    if($LASTEXITCODE){throw 'Native observer dependency compilation failed'}
    $objects+=$object
}
$sources=@('controller.cpp','hooks.cpp','native_factory.cpp','channel_dll.cpp') | ForEach-Object {Join-Path $PSScriptRoot $_}
& (Join-Path $tool 'g++.exe') -std=c++17 -O2 -Wall -Wextra -Werror -static-libgcc -static-libstdc++ -shared @sources -I (Join-Path $minhook 'include') @objects '-Wl,--kill-at' -o (Join-Path $out 'TacticoreRuntime1.dll') -luser32 -ladvapi32
if($LASTEXITCODE){throw 'Active native runtime DLL compilation failed'}
& (Join-Path $tool 'g++.exe') -std=c++17 -O2 -Wall -Wextra -Werror -static-libgcc -static-libstdc++ (Join-Path $PSScriptRoot 'native_host.cpp') -o (Join-Path $out 'runtime_host.exe') -luser32 -ladvapi32
if($LASTEXITCODE){throw 'Native transport helper compilation failed'}
& (Join-Path $tool 'g++.exe') -std=c++17 -O2 -Wall -Wextra -Werror -static-libgcc -static-libstdc++ (Join-Path $PSScriptRoot 'test_channel.cpp') -o (Join-Path $out 'test_channel.exe')
if($LASTEXITCODE){throw 'Native channel actual-function test compilation failed'}
$channelTest=& (Join-Path $out 'test_channel.exe')
if($LASTEXITCODE){throw 'Native channel actual-function tests failed'}
$layout=& (Join-Path $out 'runtime_host.exe') --layout
if($LASTEXITCODE){throw 'Native transport ABI inventory failed'}
$inputs=@()
foreach($file in (Get-ChildItem -LiteralPath $PSScriptRoot -File | Where-Object {$_.Extension -in @('.h','.cpp','.ps1')} | Sort-Object Name)){
    $inputs+=@{file=$file.Name;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
}
$outputs=@()
foreach($name in @('TacticoreRuntime1.dll','runtime_host.exe','atomic_publish.dll')){
    $outputs+=@{file=$name;sha256=(Get-FileHash -LiteralPath (Join-Path $out $name) -Algorithm SHA256).Hash.ToLowerInvariant()}
}
$manifest=@{schema_version=1;protocol='tactical_runtime_v1';architecture='x86';inputs=$inputs;outputs=$outputs;layout=($layout|ConvertFrom-Json);channel_tests=($channelTest|ConvertFrom-Json);real_game_verified=$false;execution_ready=$false}
$manifest|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $out 'build-manifest.json') -Encoding utf8
$manifest|ConvertTo-Json -Depth 8
