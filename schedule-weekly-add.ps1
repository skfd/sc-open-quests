$taskName   = "kk-SCOpenQuests-weekly"
$projectDir = $PSScriptRoot
$logFile    = "$projectDir\logs\weekly.log"

if (-not (Test-Path "$projectDir\logs")) {
    New-Item -ItemType Directory -Path "$projectDir\logs" | Out-Null
}

$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c cd /d `"$projectDir`" && python run.py weekly >> `"$logFile`" 2>&1"

# Monday 07:30, while the owner is away: a week of planet diffs (about 1-1.5 h), the planet clip (about an
# hour), then the weekly regions' counts. run.py weekly starts no step that would reach the daily 13:15
# update. Stopped after ten hours; what it staged is picked up the next week.
$trigger  = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "07:30"
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 10) -StartWhenAvailable `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force

Write-Host "Scheduled '$taskName' to run on Mondays at 07:30."
Write-Host "Log: $logFile"
