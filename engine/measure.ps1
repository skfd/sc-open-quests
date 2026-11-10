<#
.SYNOPSIS
  Runs the installed engine (gradlew installDist first) from the repo root and reports wall time, the
  java process's CPU time (read after exit, so exact) and its peak working set, sampled every 0.5 s.
  CPU time is the figure to compare between runs: other load on the machine barely moves it. Arguments are passed to the engine.

.EXAMPLE
  ./engine/measure.ps1 count --pbf C:\Users\kk\Code\.osm-data\ontario\ontario-2026-10-10.osm.pbf `
      --quests data/quests/v64.1.json --cities config/cities.json --out docs/data
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
$held = @{}   # pid -> Process with an open handle, so its CPU time can still be read after it exits
while (-not $p.HasExited) {
    $java = Get-CimInstance Win32_Process -Filter "Name='java.exe' AND ParentProcessId=$($p.Id)"
    foreach ($j in $java) {
        $id = [int]$j.ProcessId
        if (-not $held.ContainsKey($id)) {
            $proc = Get-Process -Id $id -ErrorAction SilentlyContinue
            if ($proc) { try { $null = $proc.Handle; $held[$id] = $proc } catch {} }
        }
        if ($held.ContainsKey($id)) {
            $held[$id].Refresh()
            try { $ws = $held[$id].WorkingSet64; if ($ws -gt $peak) { $peak = $ws } } catch {}
        }
    }
    Start-Sleep -Milliseconds 500
}
$p.WaitForExit()
$sw.Stop()
$cpu = 0.0
foreach ($proc in $held.Values) { $proc.Refresh(); $cpu += $proc.TotalProcessorTime.TotalSeconds }
Get-Content $log
$wall = $sw.Elapsed.TotalSeconds
"exit {0}; process wall {1:N1} s; cpu {2:N1} s ({3:N1} threads busy on average); peak working set {4:N0} MB (sampled every 0.5 s)" -f `
    $p.ExitCode, $wall, $cpu, ($cpu / $wall), ($peak / 1MB)
exit $p.ExitCode
