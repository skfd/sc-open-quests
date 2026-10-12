<#
.SYNOPSIS
  Vendors the StreetComplete (GPL-3.0) source files the engine needs from an SC checkout.

.DESCRIPTION
  Copies a fixed list of files from SC's commonMain into src/main/kotlin/sc/, keeping their
  original package names and licence headers, and records the SC tag and commit in SC-VERSION.txt.
  The checkout must be at exactly the requested tag.

  The files compile unchanged on a plain JVM because the build applies the kotlinx.serialization
  compiler plugin (for the @Serializable annotations in Element.kt, ElementGeometry.kt, ...) and uses
  the same Kotlin (2.4.0) and kotlinx-datetime (0.8.0) versions as SC v63.4. util/ktx/Element.kt
  imports de.westnordost.osmfeatures.GeometryType, which has no plain-JVM artifact; the engine
  provides a stub enum for it in src/main/kotlin/stubs/ (outside sc/, so the SC file stays as is).

  Patches applied after the copy (listed in SC-VERSION.txt, both hashes recorded):
    clock  util/ktx/Instant.kt: systemTimeNow() reads a settable `var systemClock: Clock`
           (default Clock.System) instead of Clock.System. Every wall-clock read in the vendored
           code (LocalDate.now(), LocalDateTime.now(), RelativeDate, nowAsCheckDateString()) goes
           through systemTimeNow(), so this one line lets the engine evaluate `older today -N` at
           the extract's timestamp. The script fails if the upstream line is not found verbatim.

.EXAMPLE
  ./sync-sc.ps1 -ScPath C:\Users\kk\AppData\Local\Temp\sc-v63.4 -Tag v63.4
#>
param(
    [Parameter(Mandatory = $true)][string]$ScPath,
    [string]$Tag = 'v63.4'
)
$ErrorActionPreference = 'Stop'

$commonMain = Join-Path $ScPath 'app/src/commonMain/kotlin'
$dest = Join-Path $PSScriptRoot 'src/main/kotlin/sc'

$actualTags = @(git -C $ScPath tag --points-at HEAD)
if ($actualTags -notcontains $Tag) {
    throw "SC checkout at $ScPath is not at tag $Tag (HEAD tags: $($actualTags -join ', '))"
}
$commit = (git -C $ScPath rev-parse HEAD).Trim()

function Get-Sha256([string]$path) {
    $bytes = [System.IO.File]::ReadAllBytes($path)
    -join ([System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') })
}

$pkg = 'de/westnordost/streetcomplete'
$files = @(
    # the element filter parser and matcher
    "$pkg/data/elementfilter/BooleanExpression.kt"
    "$pkg/data/elementfilter/BooleanExpressionBuilder.kt"
    "$pkg/data/elementfilter/ElementFilterExpression.kt"
    "$pkg/data/elementfilter/ElementFiltersParser.kt"
    "$pkg/data/elementfilter/NumberWithUnitParser.kt"
    "$pkg/data/elementfilter/OverpassQueryCreator.kt"
    "$pkg/data/elementfilter/filters/ElementFilter.kt"
    "$pkg/data/elementfilter/filters/ElementFilterOverpass.kt"
    "$pkg/data/elementfilter/filters/RegexOrSet.kt"
    "$pkg/data/elementfilter/filters/RelativeDate.kt"
    # what it matches against
    "$pkg/data/osm/mapdata/Element.kt"
    # check-date helpers used by `older`/`newer` (ResurveyUtils needs Tags = StringMapChangesBuilder)
    "$pkg/osm/ResurveyUtils.kt"
    "$pkg/osm/TagsUtils.kt"
    "$pkg/data/osm/edits/update_tags/StringMapChangesBuilder.kt"
    "$pkg/data/osm/edits/update_tags/StringMapChanges.kt"
    "$pkg/data/osm/edits/update_tags/StringMapEntryChange.kt"
    # parser and date utilities
    "$pkg/util/StringWithCursor.kt"
    "$pkg/util/ktx/Instant.kt"
    "$pkg/util/ktx/LocalDate.kt"
    "$pkg/util/ktx/LocalDateTime.kt"
    # constants spliced into quest filter strings (AddBuildingLevels, AddRoadSurface, AddStepsRamp)
    "$pkg/osm/BuildingLevelsUtils.kt"
    "$pkg/osm/surface/SurfaceUtils.kt"
    "$pkg/osm/surface/SurfaceParser.kt" # parseSurface(), used by SurfaceUtils
    "$pkg/osm/surface/Surface.kt"
    "$pkg/osm/surface/SurfaceCreator.kt" # applyTo(), used by SurfaceUtils
    "$pkg/osm/surface/SurfaceCategory.kt" # used by SurfaceCreator
    # quest position: how the app builds an element's geometry and its centre
    "$pkg/data/osm/geometry/ElementGeometryCreator.kt"
    "$pkg/data/osm/geometry/ElementGeometry.kt"
    "$pkg/data/osm/geometry/NodeWayMap.kt"
    "$pkg/data/osm/mapdata/MapData.kt"
    "$pkg/data/osm/mapdata/BoundingBox.kt"
    "$pkg/util/math/SphericalEarthMath.kt"
    "$pkg/util/math/SphericalEarthMathVector3d.kt"
    "$pkg/util/math/Vector3d.kt"
    "$pkg/util/math/AngleMath.kt" # normalizeDegrees/normalizeRadians
    "$pkg/util/ktx/Collections.kt"
    "$pkg/util/ktx/Double.kt"
    "$pkg/util/ktx/Element.kt" # isArea()
    "$pkg/osm/AreaUtils.kt" # IS_AREA_EXPRESSION
)

# Patches: file -> (name, upstream line, replacement lines). Applied after the copy; each must match
# exactly one line verbatim, or the script fails.
$patches = @(
    @{
        Name = 'clock'
        File = "$pkg/util/ktx/Instant.kt"
        Find = 'fun systemTimeNow(): Instant = Clock.System.now()'
        Replace = @(
            'fun systemTimeNow(): Instant = systemClock.now()'
            ''
            '/** sc-open-quests patch: the clock behind [systemTimeNow], settable so that age filters can be'
            ' *  evaluated at an extract''s timestamp instead of the wall clock. */'
            'var systemClock: Clock = Clock.System'
        )
        Description = 'util/ktx/Instant.kt: systemTimeNow() reads a settable `var systemClock: Clock` (default Clock.System)'
    }
)

if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }

$lines = @(
    "# StreetComplete source vendored by sync-sc.ps1. Do not edit the files under src/main/kotlin/sc/;"
    "# rerun the script instead. StreetComplete is GPL-3.0 (see src/main/kotlin/sc/LICENSE)."
    "tag=$Tag"
    "commit=$commit"
    "patches=$(($patches | ForEach-Object { $_.Name }) -join ',')"
)
foreach ($p in $patches) { $lines += "  $($p.Name): $($p.Description)" }
$lines += "files (sha256 of the copied file; patched files also give the upstream sha256):"

foreach ($f in $files) {
    $src = Join-Path $commonMain $f
    if (-not (Test-Path $src)) { throw "Missing in SC checkout: $src" }
    $target = Join-Path $dest $f
    New-Item -ItemType Directory -Force (Split-Path $target) | Out-Null
    Copy-Item $src $target
    $upstream = Get-Sha256 $target
    $patch = $patches | Where-Object { $_.File -eq $f }
    if ($patch) {
        $text = [System.IO.File]::ReadAllText($target)
        $nl = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }
        $fileLines = [regex]::Split($text, '\r?\n')
        $hits = @($fileLines | Where-Object { $_ -ceq $patch.Find }).Count
        if ($hits -ne 1) { throw "patch $($patch.Name): expected the line '$($patch.Find)' once in $f, found $hits" }
        $out = foreach ($l in $fileLines) { if ($l -ceq $patch.Find) { $patch.Replace } else { $l } }
        [System.IO.File]::WriteAllText($target, ($out -join $nl), (New-Object System.Text.UTF8Encoding $false))
        $lines += "  $(Get-Sha256 $target)  $f  (patch $($patch.Name); upstream $upstream)"
    } else {
        $lines += "  $upstream  $f"
    }
}
Copy-Item (Join-Path $ScPath 'LICENSE') (Join-Path $dest 'LICENSE')

[System.IO.File]::WriteAllLines((Join-Path $PSScriptRoot 'SC-VERSION.txt'), [string[]]$lines)
Write-Host "Vendored $($files.Count) files from StreetComplete $Tag ($commit) into $dest; patches: $(($patches | ForEach-Object { $_.Name }) -join ', ')"
