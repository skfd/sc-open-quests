$taskName   = "kk-SCOpenQuests"
$projectDir = $PSScriptRoot
$logFile    = "$projectDir\logs\scheduler.log"

if (-not (Test-Path "$projectDir\logs")) {
    New-Item -ItemType Directory -Path "$projectDir\logs" | Out-Null
}

$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c cd /d `"$projectDir`" && python run.py update >> `"$logFile`" 2>&1"

# 17:15 UTC: 13:15 in summer, 12:15 in winter, clear of the sibling trackers. The trigger keeps the
# offset of the day it is registered, so it is given in UTC: registered at a local "13:15" in winter it
# would fire at 18:15 UTC, outside backfill_history.QUIET. Since Europe joined (2026-11-02) a run takes
# most of an hour, more on a slow download day; the limit leaves room.
$trigger  = New-ScheduledTaskTrigger -Daily -At ([DateTime]::SpecifyKind([DateTime]::Today.AddHours(17.25), 'Utc')).ToLocalTime()
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 4) -StartWhenAvailable

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force

Write-Host "Scheduled '$taskName' to run daily at 17:15 UTC ($($trigger.StartBoundary))."
Write-Host "Log: $logFile"
