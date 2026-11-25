$taskName   = "kk-SCOpenQuests-site"
$projectDir = $PSScriptRoot
$logFile    = "$projectDir\logs\site.log"

if (-not (Test-Path "$projectDir\logs")) {
    New-Item -ItemType Directory -Path "$projectDir\logs" | Out-Null
}

# conhost --headless: no window. Task Scheduler's result is then always 0; read the log.
$action = New-ScheduledTaskAction `
    -Execute "conhost.exe" `
    -Argument "--headless cmd.exe /c cd /d `"$projectDir`" && python run.py site >> `"$logFile`" 2>&1"

# Hourly from 07:20 to 23:20: the world's day closes at any hour, and a run with nothing new is a second.
# One that deploys takes about 6 minutes.
$trigger  = New-ScheduledTaskTrigger -Daily -At "07:20"
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At "07:20" -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Hours 16 -Minutes 1)).Repetition
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force

Write-Host "Scheduled '$taskName' to run hourly from 07:20 to 23:20."
Write-Host "Log: $logFile"
