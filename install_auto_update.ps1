# Egyszeri telepítő: létrehozza a WOTDB 10 percenkénti frissítő feladatát.

$ErrorActionPreference = "Stop"
$taskName = "WOTDB Tank Data Update"
$runnerPath = Join-Path $PSScriptRoot "run_auto_update.ps1"

if (-not (Test-Path -LiteralPath $runnerPath)) {
    throw "Hiányzik a futtató fájl: $runnerPath"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runnerPath`""

$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 10) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Force | Out-Null

Write-Host "A '$taskName' feladat elkészült: 10 percenként frissíti a tanks.json fájlt."
Write-Host "Napló: $(Join-Path $PSScriptRoot 'logs\\tank-update.log')"
