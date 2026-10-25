param([ValidatePattern('^[A-Za-z0-9.-]+\.exe$')][string]$OutputName='CommanderDesktop.exe')
$ErrorActionPreference='Stop'
$compiler='C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe'
& $compiler /nologo /target:winexe /platform:x86 /out:"$PSScriptRoot\$OutputName" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Net.Http.dll /reference:System.Web.Extensions.dll /reference:System.Security.dll /reference:System.Management.dll "$PSScriptRoot\CommanderHub.cs" "$PSScriptRoot\CommanderLibrary.cs" "$PSScriptRoot\RuntimeState.cs" "$PSScriptRoot\DarkControls.cs" "$PSScriptRoot\TacticalPanel.cs" "$PSScriptRoot\LiveBattle.cs" "$PSScriptRoot\HostLaunch.cs"
if($LASTEXITCODE){throw 'Desktop build failed'}
Get-FileHash "$PSScriptRoot\$OutputName"
