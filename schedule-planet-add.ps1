$taskName   = "kk-SCOpenQuests-planet"
$oldName    = "kk-SCOpenQuests-weekly"  # the same job's name until 2026-11
$projectDir = $PSScriptRoot
$logFile    = "$projectDir\logs\planet.log"

if (-not (Test-Path "$projectDir\logs")) {
    New-Item -ItemType Directory -Path "$projectDir\logs" | Out-Null
}

$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c cd /d `"$projectDir`" && python run.py planet >> `"$logFile`" 2>&1"

# The first Monday of each month, 07:30, while the owner is away: a month of planet diffs in one pass (about
# 2-2.5 h; at most 31 diffs a pass, so a longer gap costs a second 160 GB rewrite), then the re-cut of every
# osm-extracts clip from the new file (one more planet pass, 3-4 h), then the months the regions on clips
# lack (DESIGN.md, "Current clips in osm-extracts"). Each run rewrites the whole history file, so monthly
# (DESIGN.md, "Planet job: monthly while nothing counts from it"). run.py planet starts no step touching
# data/ that would reach the daily 13:15 update; the fetch and the re-cut touch only the store. Stopped
# after fourteen hours; what it staged is picked up the next month.
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 14) -StartWhenAvailable `
    -MultipleInstances IgnoreNew

# Register-ScheduledTask rejects a CIM monthly-day-of-week trigger, so schtasks makes the task and its
# trigger, and Set-ScheduledTask puts in the real action and settings.
schtasks /Create /F /TN $taskName /SC MONTHLY /MO FIRST /D MON /ST 07:30 /TR "cmd.exe /c exit" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "schtasks /Create failed ($LASTEXITCODE)" }
Set-ScheduledTask -TaskName $taskName -Action $action -Settings $settings | Out-Null

if (Get-ScheduledTask -TaskName $oldName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $oldName -Confirm:$false
    Write-Host "Removed the old task '$oldName'."
}
Write-Host "Scheduled '$taskName' to run on the first Monday of each month at 07:30."
Write-Host "Log: $logFile"
