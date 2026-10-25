$taskName = "kk-SCOpenQuests-weekly"

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Task '$taskName' removed."
} else {
    Write-Host "Task '$taskName' not found."
}
