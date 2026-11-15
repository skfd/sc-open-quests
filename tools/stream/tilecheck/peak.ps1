# Runs a program and reports its exit code, wall seconds and peak working set; its stderr goes to -Log.
#   peak.ps1 -Log run.log -Exe tilestore.exe -- cut --pbf ... --out ...
param([string]$Log, [string]$Exe, [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest)
$t = Get-Date
$p = Start-Process -FilePath $Exe -ArgumentList $Rest -NoNewWindow -PassThru -RedirectStandardError $Log
$h = $p.Handle
$peak = 0
while (-not $p.HasExited) {
    $p.Refresh()
    if ($p.PeakWorkingSet64 -gt $peak) { $peak = $p.PeakWorkingSet64 }
    Start-Sleep -Milliseconds 200
}
"exit $($p.ExitCode); $([math]::Round(((Get-Date) - $t).TotalSeconds, 1)) s; peak working set $([math]::Round($peak / 1GB, 2)) GiB"
Get-Content $Log
