$taskName   = "kk-SCOpenQuests-inputs"
$projectDir = $PSScriptRoot
$logFile    = "$projectDir\logs\inputs.log"

if (-not (Test-Path "$projectDir\logs")) {
    New-Item -ItemType Directory -Path "$projectDir\logs" | Out-Null
}

# conhost --headless: no window. Task Scheduler's result is then always 0; read the log.
$action = New-ScheduledTaskAction `
    -Execute "conhost.exe" `
    -Argument "--headless cmd.exe /c cd /d `"$projectDir`" && python run.py inputs >> `"$logFile`" 2>&1"

# 11:15 local: after the day's planet diff and notes dump are out, before the city run (17:15 UTC) and the world
# loop (14:45). About 5 minutes; up to 45 more when docker or the network has to be tried again.
$trigger  = New-ScheduledTaskTrigger -Daily -At "11:15"
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 3) -StartWhenAvailable `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force

Write-Host "Scheduled '$taskName' to run daily at 11:15."
Write-Host "Log: $logFile"
