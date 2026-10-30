$taskName   = "kk-SCOpenQuests-weekly"
$projectDir = $PSScriptRoot
$logFile    = "$projectDir\logs\weekly.log"

if (-not (Test-Path "$projectDir\logs")) {
    New-Item -ItemType Directory -Path "$projectDir\logs" | Out-Null
}

$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c cd /d `"$projectDir`" && python run.py weekly >> `"$logFile`" 2>&1"

# The first Monday of each month, 07:30, while the owner is away: a month of planet diffs in one pass (about
# 2-2.5 h; at most 31 diffs a pass, so a longer gap costs a second 160 GB rewrite), the planet clip (about
# an hour), then the weekly regions' counts. Monthly, not weekly, while no region reads the planet: each
# run rewrites the whole history file (DESIGN.md, "Planet job: monthly while nothing counts from it").
# run.py weekly starts no step that would reach the daily 13:15 update. Stopped after ten hours; what it
# staged is picked up the next month.
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 10) -StartWhenAvailable `
    -MultipleInstances IgnoreNew

# Register-ScheduledTask rejects a CIM monthly-day-of-week trigger, so schtasks makes the task and its
# trigger, and Set-ScheduledTask puts in the real action and settings.
schtasks /Create /F /TN $taskName /SC MONTHLY /MO FIRST /D MON /ST 07:30 /TR "cmd.exe /c exit" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "schtasks /Create failed ($LASTEXITCODE)" }
Set-ScheduledTask -TaskName $taskName -Action $action -Settings $settings | Out-Null

Write-Host "Scheduled '$taskName' to run on the first Monday of each month at 07:30."
Write-Host "Log: $logFile"
