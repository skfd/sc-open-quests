<#
.SYNOPSIS
  Runs the installed engine (gradlew installDist first) from the repo root and reports wall time and
  the java process's peak working set, sampled every 0.5 s. Arguments are passed to the engine.

.EXAMPLE
  ./engine/measure.ps1 count --pbf C:\Users\kk\Code\.osm-data\ontario\ontario-2026-07-16.osm.pbf `
      --quests data/quests/v63.4.json --cities config/cities.json --out docs/data
#>
$ErrorActionPreference = 'Stop'
if (-not $env:JAVA_HOME) { $env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr' }
$bin = Join-Path $PSScriptRoot 'build\install\sc-open-quests-engine\bin\sc-open-quests-engine.bat'
$repo = Split-Path $PSScriptRoot
$logDir = Join-Path $PSScriptRoot 'out'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir 'run.log'
$quoted = $args | ForEach-Object { if ("$_" -match '\s') { '"' + $_ + '"' } else { "$_" } }
$sw = [Diagnostics.Stopwatch]::StartNew()
$p = Start-Process -FilePath $bin -ArgumentList $quoted -WorkingDirectory $repo -NoNewWindow -PassThru `
    -RedirectStandardOutput "$log.out" -RedirectStandardError $log
$peak = 0L
while (-not $p.HasExited) {
    $java = Get-CimInstance Win32_Process -Filter "Name='java.exe'" |
        Where-Object { $_.CommandLine -like '*openquests.MainKt*' }
    foreach ($j in $java) {
        $ws = (Get-Process -Id $j.ProcessId -ErrorAction SilentlyContinue).WorkingSet64
        if ($ws -gt $peak) { $peak = $ws }
    }
    Start-Sleep -Milliseconds 500
}
$p.WaitForExit()
$sw.Stop()
Get-Content $log
"exit {0}; process wall {1:N1} s; peak working set {2:N0} MB (sampled every 0.5 s)" -f $p.ExitCode, $sw.Elapsed.TotalSeconds, ($peak / 1MB)
exit $p.ExitCode
