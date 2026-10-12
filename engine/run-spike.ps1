# Runs the installed spike (gradlew installDist first) and reports wall time and peak working set.
$ErrorActionPreference = 'Stop'
$env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr'
$bin = Join-Path $PSScriptRoot 'build\install\sc-open-quests-engine\bin\sc-open-quests-engine.bat'
$log = Join-Path $PSScriptRoot 'out\spike-run.log'
New-Item -ItemType Directory -Force (Join-Path $PSScriptRoot 'out') | Out-Null
Push-Location $PSScriptRoot
try {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $p = Start-Process -FilePath $bin -NoNewWindow -PassThru -RedirectStandardOutput $log -RedirectStandardError "$log.err"
    $peak = 0L
    while (-not $p.HasExited) {
        $java = Get-CimInstance Win32_Process -Filter "Name='java.exe'" |
            Where-Object { $_.CommandLine -like '*openquests.SpikeKt*' }
        foreach ($j in $java) { $ws = (Get-Process -Id $j.ProcessId -ErrorAction SilentlyContinue).WorkingSet64; if ($ws -gt $peak) { $peak = $ws } }
        Start-Sleep -Milliseconds 500
    }
    $sw.Stop()
    Get-Content $log
    "process wall {0:N1} s; peak working set {1:N0} MB (sampled every 0.5 s)" -f $sw.Elapsed.TotalSeconds, ($peak / 1MB)
} finally { Pop-Location }
