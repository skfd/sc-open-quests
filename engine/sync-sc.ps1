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
  imports de.westnordost.osmfeatures.GeometryType, from the osmfeatures library (jvm variant). osm/Sides.kt
  imports SC's Side enum from a Compose file; the engine stubs it in src/main/kotlin/stubs/.

  Custom quests are not vendored (their files hold Android UI code); their logic is transcribed into
  src/main/kotlin/openquests/custom/ or generated into src/main/kotlin/ported/ by port_area_quests.py,
  and each upstream file is pinned in PORTED-QUESTS.txt. The script fails before copying anything if a
  pinned file changed at the requested tag.

  Patches applied after the copy (listed in SC-VERSION.txt, both hashes recorded):
    clock  util/ktx/Instant.kt: systemTimeNow() reads a settable `var systemClock: Clock`
           (default Clock.System) instead of Clock.System. Every wall-clock read in the vendored
           code (LocalDate.now(), LocalDateTime.now(), RelativeDate, nowAsCheckDateString()) goes
           through systemTimeNow(), so this one line lets the engine evaluate `older today -N` at
           the extract's timestamp. The script fails if the upstream line is not found verbatim.
    multiplier  data/elementfilter/filters/RelativeDate.kt: `RelativeDate.MULTIPLIER` (the app's
           resurvey setting) reads a thread-local override first, so that one pass can count the
           age quests at 0.5, 1 and 2. Same verbatim-line rule.

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
    # helpers of the custom quests ported in src/main/kotlin/openquests/custom/ (see PORTED-QUESTS.txt)
    "$pkg/osm/RoadUtils.kt" # ALL_ROADS, MOTORWAYS, ROADS_ASSUMED_TO_BE_PAVED
    "$pkg/osm/maxspeed/MaxSpeedUtils.kt" # MAX_SPEED_TYPE_KEYS
    "$pkg/osm/Sides.kt"
    "$pkg/osm/sidewalk/Sidewalk.kt"
    "$pkg/osm/sidewalk/SidewalkParser.kt" # parseSidewalkSides()
    "$pkg/osm/Places.kt" # isPlace(), isDisusedPlace()
    "$pkg/osm/Feature.kt" # applyTo(), used by Places.kt
    "$pkg/osm/opening_hours/OpeningHoursValidator.kt" # isSupported()
    "$pkg/osm/opening_hours/Utils.kt" # getMonths(), getWeekdays(), used by OpeningHoursValidator
    "$pkg/osm/opening_hours/HierarchicOpeningHours.kt" # used by Utils.kt
    "$pkg/osm/LifecycleUtils.kt" # asIfItWasnt(), used by Places.kt
    "$pkg/quests/recycling_material/RecyclingMaterial.kt"
    "$pkg/util/tree/Node.kt" # buildTree(), used by RecyclingMaterial
    "$pkg/util/ktx/FeatureDictionary.kt" # getFeature(), as the app's registry gets it
    # map data for the quests that need surroundings (src/main/kotlin/ported/, port_area_quests.py)
    "$pkg/data/osm/mapdata/MapDataWithGeometry.kt"
    "$pkg/data/osm/mapdata/MutableMapDataWithGeometry.kt"
    "$pkg/data/osm/mapdata/MutableMapData.kt"
    "$pkg/data/osm/mapdata/MapDataXt.kt" # filter(String)
    "$pkg/data/osm/geometry/ElementGeometryEntry.kt"
    "$pkg/osm/WaysCrossingUtils.kt" # findNodesAtCrossingsOf()
    "$pkg/quests/barrier_type/DetectWayBarrierIntersectionUtil.kt"
    "$pkg/osm/kerb/KerbUtil.kt" # findAllKerbNodes(), couldBeAKerb()
    "$pkg/data/download/tiles/TilesRect.kt" # z16 download tiles (AreaPass)
    "$pkg/data/meta/CountryInfo.kt" # used by osm/cycleway/Cycleway.kt
    # country metadata for getCountryInfoByLocation (AddHousenumber, AddCycleway, AddRoofShape), as the
    # app wires it: countryInfos.get(countryBoundaries, position) (openquests/custom/CountryInfos.kt)
    "$pkg/data/meta/CountryInfos.kt" # needs Res.readBytesOrNull, stubbed in src/main/kotlin/stubs/
    "$pkg/util/countryboundaries/CountryBoundaries.kt"
    "$pkg/util/countryboundaries/Countries.kt"
    "$pkg/osm/cycleway/Cycleway.kt"
    "$pkg/osm/cycleway/CyclewayParser.kt"
    "$pkg/osm/street_parking/StreetParking.kt"
    "$pkg/osm/street_parking/StreetParkingParser.kt"
    "$pkg/osm/oneway/Direction.kt"
    "$pkg/osm/oneway/OnewayUtils.kt"
    "$pkg/osm/shoulders/Shoulders.kt"
    "$pkg/osm/shoulders/ShouldersParser.kt"
    "$pkg/osm/ParsingUtils.kt" # expandSidesTags()
    "$pkg/quests/barrier_type/StileTypeAnswer.kt"
    "$pkg/util/ktx/Map.kt" # containsAll()
    "$pkg/util/ktx/Boolean.kt" # toYesNo()
    "$pkg/util/math/LatLonRaster.kt"
    "$pkg/util/math/ElementGeometryMath.kt" # intersects(), isInMultipolygon()
    "$pkg/osm/RoadWidthUtils.kt" # estimateUsableRoadwayWidth()
    "$pkg/osm/Things.kt" # isThing()
    "$pkg/osm/CrossingUtils.kt" # isCrossing()
    "$pkg/data/osm/mapdata/ElementKey.kt"
    # notes: the note quest (openquests/NoteQuest.kt) and the hiding of quests at open notes
    "$pkg/data/osmnotes/Note.kt"
    "$pkg/data/user/User.kt" # NoteComment.user
    "$pkg/util/ktx/LatLon.kt" # truncateTo6Decimals()
)

# Data files copied from app/src/commonMain/composeResources/files/ into src/main/resources/sc/. The
# feature presets: the base file and the localizations osmfeatures reads for the engine's pinned
# locale en-CA ("en", then "en-CA"). Brand presets are left out: SC's getFeature() asks for
# isSuggestion = false, so the brand collection is never read.
$composeFiles = Join-Path $ScPath 'app/src/commonMain/composeResources/files'
$resDest = Join-Path $PSScriptRoot 'src/main/resources/sc'
$resources = @(
    'osmfeatures/default/presets.json'
    'osmfeatures/default/en.json'
    'osmfeatures/default/en-CA.json'
    # SC's country boundaries and the country metadata an Ontario position reads (CA-ON, CA, default).
    # Positions elsewhere (Quebec, US) get only default.yml here; quests there are not counted.
    'boundaries.ser'
    'country_metadata/default.yml'
    'country_metadata/CA.yml'
    'country_metadata/CA-ON.yml'
)

# Custom quests live in SC's androidMain next to their Android forms, so they are not vendored: their
# applicability logic is transcribed into src/main/kotlin/openquests/custom/. PORTED-QUESTS.txt pins
# the upstream file of each (sha256 of the file with LF line endings, i.e. of the git blob's text).
# If one changed, the script fails: re-check the port against the new file, then update its hash.
$androidMain = Join-Path $ScPath 'app/src/androidMain/kotlin'
$portsFile = Join-Path $PSScriptRoot 'PORTED-QUESTS.txt'

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
    @{
        Name = 'multiplier'
        File = "$pkg/data/elementfilter/filters/RelativeDate.kt"
        Find = '        var MULTIPLIER: Float = 1f'
        Replace = @(
            '        var MULTIPLIER: Float'
            '            get() = multiplierOverride.get() ?: defaultMultiplier'
            '            set(value) { defaultMultiplier = value }'
            ''
            '        /** sc-open-quests patch: a thread can evaluate at another resurvey multiplier (the app''s'
            '         *  ResurveyIntervals setting: 0.5, 1 or 2), so that one pass counts all three. */'
            '        val multiplierOverride = ThreadLocal<Float?>()'
            '        @Volatile private var defaultMultiplier: Float = 1f'
        )
        Description = 'data/elementfilter/filters/RelativeDate.kt: MULTIPLIER reads a thread-local override first (`multiplierOverride`)'
    }
)

function Get-Sha256Lf([string]$path) {
    $text = [System.IO.File]::ReadAllText($path) -replace "`r`n", "`n"
    $bytes = (New-Object System.Text.UTF8Encoding $false).GetBytes($text)
    -join ([System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') })
}

$portLines = @()
$changed = @()
foreach ($l in [System.IO.File]::ReadAllLines($portsFile)) {
    if ($l -match '^\s*(#|$)') { continue }
    $name, $path, $sha = -split $l
    # "cm:<path>" pins a commonMain file whose code is transcribed (e.g. ApplicationConstants.ignoreRelation)
    $src = if ($path.StartsWith('cm:')) { Join-Path $commonMain "$pkg/$($path.Substring(3))" } else { Join-Path $androidMain "$pkg/$path" }
    if (-not (Test-Path $src)) { $changed += "$name ($path is gone)"; continue }
    $now = Get-Sha256Lf $src
    if ($now -ne $sha) { $changed += "$name ($path is now $now)" }
    $portLines += "  $sha  $path  ($name)"
}
if ($changed) {
    throw "Ported custom quests changed upstream in ${Tag}; re-check the ports, then update PORTED-QUESTS.txt:`n  " + ($changed -join "`n  ")
}

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

if (Test-Path $resDest) { Remove-Item -Recurse -Force $resDest }
$lines += "data files (from app/src/commonMain/composeResources/files/ into src/main/resources/sc/):"
foreach ($f in $resources) {
    $src = Join-Path $composeFiles $f
    if (-not (Test-Path $src)) { throw "Missing in SC checkout: $src" }
    $target = Join-Path $resDest $f
    New-Item -ItemType Directory -Force (Split-Path $target) | Out-Null
    Copy-Item $src $target
    $lines += "  $(Get-Sha256 $target)  $f"
}

$lines += "ported custom quests (sha256 of the androidMain file with LF line endings; logic in src/main/kotlin/openquests/custom/):"
$lines += $portLines

[System.IO.File]::WriteAllLines((Join-Path $PSScriptRoot 'SC-VERSION.txt'), [string[]]$lines)
Write-Host "Vendored $($files.Count) files from StreetComplete $Tag ($commit) into $dest; patches: $(($patches | ForEach-Object { $_.Name }) -join ', ')"
