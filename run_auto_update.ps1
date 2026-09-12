# WOTDB automatikus adatfrissítés futtatója.
# Ezt a fájlt a Windows Feladatütemező indítja tízpercenként.

$ErrorActionPreference = "Stop"
$projectDirectory = $PSScriptRoot
$logDirectory = Join-Path $projectDirectory "logs"
$logFile = Join-Path $logDirectory "tank-update.log"

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

Push-Location $projectDirectory

try {
    $python = Get-Command python -ErrorAction Stop
    "`n[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Tankfrissítés indítása" |
        Tee-Object -FilePath $logFile -Append

    & $python.Source "update_tanks.py" *>> $logFile

    if ($LASTEXITCODE -ne 0) {
        throw "Az update_tanks.py hibakóddal állt le: $LASTEXITCODE"
    }
}
catch {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] HIBA: $($_.Exception.Message)" |
        Tee-Object -FilePath $logFile -Append
    exit 1
}
finally {
    Pop-Location
}
