$ErrorActionPreference='Stop'
$compiler='C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe'
& $compiler /nologo /target:exe /main:AcceptanceTests /platform:x86 /out:"$PSScriptRoot\AcceptanceTests.exe" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Net.Http.dll /reference:System.Web.Extensions.dll /reference:System.Security.dll /reference:System.Management.dll "$PSScriptRoot\CommanderHub.cs" "$PSScriptRoot\CommanderLibrary.cs" "$PSScriptRoot\RuntimeState.cs" "$PSScriptRoot\DarkControls.cs" "$PSScriptRoot\TacticalPanel.cs" "$PSScriptRoot\LiveBattle.cs" "$PSScriptRoot\HostLaunch.cs" "$PSScriptRoot\AcceptanceTests.cs"
if($LASTEXITCODE){throw 'Acceptance test compilation failed'}
& "$PSScriptRoot\AcceptanceTests.exe" | Tee-Object -FilePath "$PSScriptRoot\acceptance-tests.log"
if($LASTEXITCODE){throw 'Acceptance tests failed'}
