# Vendored libraries

The page's two libraries, served from here so it depends on no CDN. Each folder holds the npm
package's own `dist` files, unchanged, and its licence.

| folder | package | files | sha384 (base64) |
|---|---|---|---|
| `uplot-1.6.31/` | `uplot@1.6.31` (MIT) | `uPlot.iife.min.js` | `XMP23k7YSCFr13Xrkxh4IO0v1W+8fB6AP+3Vycxphp2Z0V2vocAZHyuGaFCysrtM` |
| | | `uPlot.min.css` | `IfV0B7MIOYuO95kO9G5ySKPz/85zqFNOAs8iy4tkK5zd9izhJAB8b7lHrwYqqmYE` |
| `leaflet-1.9.4/` | `leaflet@1.9.4` (BSD-2-Clause) | `leaflet.js` | `cxOPjt7s7Iz04uaHJceBmS+qpjv2JkIHNVcuOrM+YHwZOmJGBXI00mdUXEq65HTH` |
| | | `leaflet.css`, `images/` | `sHL9NAb7lN7rfvG5lfHpm643Xkcjzp4jFvuavGOndn6pjVqS6ny56CAt3nsEVT4H` (the css) |

The hashes are the SRI values the page pinned while it loaded these from jsdelivr. To update one:
download the new version's `dist` files from `https://cdn.jsdelivr.net/npm/<package>@<version>/dist/`
into a new versioned folder, change the path in `index.html` (uPlot) or `app.js` (`LEAFLET`), and
delete the old folder. `.gitattributes` keeps git from touching the bytes.
