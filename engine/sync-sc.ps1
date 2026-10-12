<#
.SYNOPSIS
  Vendors the StreetComplete (GPL-3.0) source files the engine needs from an SC checkout.

.DESCRIPTION
  Copies a fixed list of files from SC's commonMain into src/main/kotlin/sc/, keeping their
  original package names and licence headers, and records the SC tag and commit in SC-VERSION.txt.
  The checkout must be at exactly the requested tag.

  Patches applied to vendored files: none. They compile unchanged on a plain JVM because the
  build applies the kotlinx.serialization compiler plugin (for the @Serializable annotations in
  Element.kt and StringMapChanges*.kt) and uses the same Kotlin (2.4.0) and kotlinx-datetime (0.8.0)
  versions as SC v63.4. If a future tag needs a patch, apply it here, after the copy, and list it.

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
)

if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }

$lines = @(
    "# StreetComplete source vendored by sync-sc.ps1. Do not edit the files under src/main/kotlin/sc/;"
    "# rerun the script instead. StreetComplete is GPL-3.0 (see src/main/kotlin/sc/LICENSE)."
    "tag=$Tag"
    "commit=$commit"
    "patches=none"
    "files (sha256 of the copied file):"
)
foreach ($f in $files) {
    $src = Join-Path $commonMain $f
    if (-not (Test-Path $src)) { throw "Missing in SC checkout: $src" }
    $target = Join-Path $dest $f
    New-Item -ItemType Directory -Force (Split-Path $target) | Out-Null
    Copy-Item $src $target
    $bytes = [System.IO.File]::ReadAllBytes($target)
    $hash = -join ([System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') })
    $lines += "  $hash  $f"
}
Copy-Item (Join-Path $ScPath 'LICENSE') (Join-Path $dest 'LICENSE')

[System.IO.File]::WriteAllLines((Join-Path $PSScriptRoot 'SC-VERSION.txt'), [string[]]$lines)
Write-Host "Vendored $($files.Count) files from StreetComplete $Tag ($commit) into $dest"
