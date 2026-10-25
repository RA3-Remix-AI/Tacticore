param([switch]$AllowExperimental)
$ErrorActionPreference='Stop'
if(!$AllowExperimental){throw 'Experimental frontend registration is not validated. Pass -AllowExperimental only for development.'}
$record=Join-Path $PSScriptRoot 'reports\commander-lab-session.json'
if(Test-Path $record){
 $session=Get-Content $record -Raw | ConvertFrom-Json
 $owned=Get-Process -Id $session.pid -ErrorAction SilentlyContinue
 if($owned){
  if($owned.Path -ne 'E:\RedRar3\Data\RA3_1.12.game' -or $owned.StartTime.ToUniversalTime().Ticks -ne ([datetime]$session.started).ToUniversalTime().Ticks){throw 'Test process identity mismatch'}
  Stop-Process -Id $owned.Id
  if(!$owned.WaitForExit(5000)){throw 'Owned game did not exit'}
 }
}
if(Get-Process ra3_1.12.game -ErrorAction SilentlyContinue){throw 'Another game is running'}
& E:\RA3Modding\SDK\Tools\MakeBig.exe -f E:\RA3Modding\SDK\BuiltMods\mods\CommanderLab '-x:*.asset' '-o:E:\RA3Modding\SDK\BuiltMods\CommanderLab.big'
if($LASTEXITCODE){throw 'Packaging failed'}
$deploy=Join-Path (Split-Path $PSScriptRoot) 'Mods\CommanderLab'
New-Item -ItemType Directory $deploy -Force | Out-Null
Copy-Item E:\RA3Modding\SDK\BuiltMods\CommanderLab.big (Join-Path $deploy 'CommanderLab.big')
$start=[Diagnostics.ProcessStartInfo]::new();$start.FileName='E:\RedRar3\Data\RA3_1.12.game';$start.WorkingDirectory='E:\RedRar3';$start.UseShellExecute=$false
$start.Arguments='-ui -win -xres 1600 -yres 900 -modConfig "'+(Join-Path $deploy 'CommanderLab_1.0.skudef')+'" -config "E:\RedRar3\RA3_chinese_t_1.12.SkuDef"'
$proc=[Diagnostics.Process]::Start($start)
@{pid=$proc.Id;started=$proc.StartTime.ToString('o');mod='CommanderLab-metadata'} | ConvertTo-Json | Set-Content $record
Write-Output $proc.Id
