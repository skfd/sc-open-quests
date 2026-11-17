//! The context query: what tier 2's cover needs to know about elements around a day's changes, as a generation of
//! the store holds them (DESIGN.md, "What tier 2 must recount, from the code": the gaps of the big-polygon rule).
//!
//! - ways (--ways W.npy): each way's tags, refs and their places, the refs that carry a tag whose key starts with one
//!   of --prefix (default "addr:"), and the relations that hold the way. Found as `tilestore ways` finds them: the
//!   way pairs (wtiles-G) and a tile holding the way whole; a tile holds every kept relation with a member crossing
//!   it, so the first tile also gives the holding relations, and it holds the tags of the way's tagged nodes (the cut's
//!   "needs"). A way in no tile is looked for in the relation store blobs of the relations given with --rels.
//! - relations (--rels R.npy): each relation's tags and members at G, through the relation pairs (rtiles-G) and its
//!   first tile; with the box of its member ways from the relation store.
//! - nodes (--nodes N.npy --node-places NP.npy): each node's tags at G, from the tile at its place (NP: '<i8' lat7,
//!   lon7 pairs, the places at G, e.g. from the node file at D-1); untagged or absent: no tags. Also the closed ways
//!   that have the node as a vertex (all in the node's own tile), for an address on an area's outline.
//! - points (--points P.npy, '<i8' lat7, lon7 pairs): the closed ways and multipolygon relations whose ring holds each
//!   point (even-odd), looked for in the tiles of the point's tile and its --around neighbours each way (default 1, a
//!   3 x 3 block, about 7 km at mid latitudes): a container whose outline crosses none of them is not found.
//!
//! - with --rel-geometry, each asked relation's member ways from its relation store blob (refs and places), for its
//!   quest point when a member way changed but the relation did not (its centre moves);
//! - with --vertex-ways, every way (open or closed) an asked node is a vertex of, with its geometry, from the node's
//!   own tile: an untouched way whose node moved has a quest point that moved;
//! - crossings (--crossing X.npy, '<i8' lat7, lon7, lat7, lon7 per segment; --crossing-key K, default highway): the
//!   ways with a tag key K whose segments cross (or touch) one of X's segments, with their geometry, from the tiles the
//!   segments cross (a tile holds every way crossing it whole): the roads under a changed bridge (AddMaxHeight).
//!
//! No new index: way pairs, relation pairs, tiles and the relation store hold all of it. Way pairs go at the next
//! `update --prune-pairs` and the tile index at `compact`: the ways and relations parts need G's pairs, the nodes and
//! points parts only its tile index.
//!
//! Out (DIR), tags as the store keeps them (b"k\0v\0..." one after another, with i8 offsets n + 1):
//!   w_ids, w_how (u1: 0 absent, 1 a tile, 2 the relation store), w_offs/w_refs/w_lat7/w_lon7 (as `ways`), w_toffs +
//!   w_tags.bin, w_aoffs + w_anodes (the refs with a --prefix tag), w_hoffs + w_hrels (holding relation ids);
//!   r_ids, r_found (u1), r_toffs + r_tags.bin, r_moffs + r_mtype (u1: 0 node, 1 way, 2 relation) + r_mref,
//!   r_box (i4, 4 per relation: s, w, n, e in 1e-7 degrees; i32::MIN unknown);
//!   n_ids, n_found (u1: 1 tagged, 2 untagged, 0 not in the tile at its place), n_toffs + n_tags.bin, n_voffs + n_vways (closed ways with it as
//!   a vertex); p_offs + p_kind (u1: 1 way, 2 relation) + p_id; for every closed way or multipolygon a node or a point
//!   found: e_kind, e_id, e_box (i4, 4 each), e_toffs + e_tags.bin; context.json (counts, seconds, peak memory).
//!   --rel-geometry: r_woffs (n + 1, into rw_*) + rw_ids + rw_poffs + rw_refs/rw_lat7/rw_lon7 (each member way's
//!   refs and places). --vertex-ways: v_ids + v_offs + v_refs/v_lat7/v_lon7 + v_toffs/v_tags.bin (the union of the
//!   ways). --crossing: x_ids + x_offs + x_refs/x_lat7/x_lon7 + x_toffs/x_tags.bin.

use crate::npy;
use crate::pbf::tag_pairs;
use crate::read::{find, payloads, Part};
use crate::tiles::{frac_xy, key_of, segment_tiles};
use crate::ways::{load_vec_i64, save_vec};
use rayon::prelude::*;
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};
use std::time::Instant;

pub struct Args {
    pub store: PathBuf,
    pub gen: i64,
    pub ways: Option<PathBuf>,
    pub rels: Option<PathBuf>,
    pub nodes: Option<PathBuf>,
    pub node_places: Option<PathBuf>,
    pub points: Option<PathBuf>,
    pub around: i64,
    pub prefixes: Vec<String>,
    pub rel_geometry: bool,
    pub crossing: Option<PathBuf>,
    pub crossing_keys: Vec<String>,
    pub vertex_ways: bool,
    pub out: PathBuf,
}

const NO: i32 = i32::MIN;

struct Store {
    dir: PathBuf,
    z: u32,
    g: i64,
    gens: Vec<i64>,
    idx: Vec<(i64, i32, i64, i32)>,
}

impl Store {
    fn tiles(&self, keys: &[i64]) -> Vec<(i64, Part)> {
        let rows: Vec<_> = keys.iter().filter_map(|&k| find(&self.idx, k)).collect();
        let bufs = payloads(&self.dir, "pack", &rows);
        rows.iter().zip(bufs).collect::<Vec<_>>().into_par_iter().map(|(r, b)| (r.0, Part::tile(&b))).collect()
    }

    fn relidx(&self) -> Vec<(i64, i32, i64, i32)> {
        let rg = self.gens.iter().copied().filter(|&x| x <= self.g && self.dir.join(format!("relidx-{x:04}.npy")).exists()).max().expect("a relation index");
        npy::load_idx(&self.dir.join(format!("relidx-{rg:04}.npy")))
    }

    fn pairs(&self, name: &str) -> npy::PairMap {
        let p = self.dir.join(format!("{name}-{:04}.npy", self.g));
        assert!(p.exists(), "{}: generation {}'s pairs are gone (pruned by a later update with --prune-pairs); ask before the update", p.display(), self.g);
        npy::PairMap::open(&p)
    }

    fn key_at(&self, lat7: i32, lon7: i32) -> (i64, i64) {
        let nt = (1u64 << self.z) as f64;
        let (fx, fy) = frac_xy(lat7, lon7, nt);
        (fx.floor() as i64, fy.floor() as i64)
    }
}

fn rows_of(rows: &[[i64; 2]], id: i64) -> &[[i64; 2]] {
    let lo = rows.partition_point(|r| r[0] < id);
    let hi = lo + rows[lo..].partition_point(|r| r[0] <= id);
    &rows[lo..hi]
}

fn has_prefix(tags: &[u8], prefixes: &[String]) -> bool {
    tag_pairs(tags).any(|(k, _)| prefixes.iter().any(|p| k.starts_with(p.as_bytes())))
}

fn node_tags<'a>(p: &'a Part, i: usize) -> Option<&'a [u8]> {
    let j = p.tag_of[i];
    (j >= 0).then(|| &p.ntb[p.n_toff[j as usize]..p.n_toff[j as usize + 1]])
}

/// the box of a relation store blob's ways (all places it holds)
fn blob_box(p: &Part) -> [i32; 4] {
    if p.lat.is_empty() {
        return [NO; 4];
    }
    let (mut s, mut w, mut n, mut e) = (i32::MAX, i32::MAX, i32::MIN, i32::MIN);
    for (&la, &lo) in p.lat.iter().zip(&p.lon) {
        s = s.min(la);
        n = n.max(la);
        w = w.min(lo);
        e = e.max(lo);
    }
    [s, w, n, e]
}

/// even-odd over segments (lat, lon pairs in 1e-7 degrees): the engine's test (Polygon.contains), in f64
fn evenodd(segs: &[[f64; 4]], lat: f64, lon: f64) -> bool {
    let mut inside = false;
    for &[y1, x1, y2, x2] in segs {
        if (y1 > lat) != (y2 > lat) && lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1 {
            inside = !inside;
        }
    }
    inside
}

#[derive(Default)]
struct Out {
    ids: Vec<i64>,
    toffs: Vec<i64>,
    tags: Vec<u8>,
}

impl Out {
    fn new() -> Out {
        Out { toffs: vec![0], ..Default::default() }
    }
    fn push(&mut self, id: i64, tags: &[u8]) {
        self.ids.push(id);
        self.tags.extend_from_slice(tags);
        self.toffs.push(self.tags.len() as i64);
    }
}

fn save_i8(dir: &Path, name: &str, v: &[i64]) {
    save_vec(&dir.join(name), "'<i8'", v, |x| x.to_le_bytes().to_vec());
}
fn save_i4(dir: &Path, name: &str, v: &[i32]) {
    save_vec(&dir.join(name), "'<i4'", v, |x| x.to_le_bytes().to_vec());
}
fn save_u1(dir: &Path, name: &str, v: &[u8]) {
    save_vec(&dir.join(name), "'|u1'", v, |x| vec![x]);
}

/// ways with their geometry, for an output prefix: ids, offs, refs, places, tags
#[derive(Default)]
struct Geo {
    ids: Vec<i64>,
    offs: Vec<i64>,
    refs: Vec<i64>,
    lat: Vec<i32>,
    lon: Vec<i32>,
    toffs: Vec<i64>,
    tags: Vec<u8>,
}

impl Geo {
    fn new() -> Geo {
        Geo { offs: vec![0], toffs: vec![0], ..Default::default() }
    }
    /// way j of payload p, its places from the payload (NO where it has none)
    fn push_way(&mut self, p: &Part, j: usize) {
        self.ids.push(p.wid[j]);
        for r in &p.wrefs[p.w_roff[j]..p.w_roff[j + 1]] {
            self.refs.push(*r);
            match p.nid.binary_search(r) {
                Ok(q) => {
                    self.lat.push(p.lat[q]);
                    self.lon.push(p.lon[q]);
                }
                Err(_) => {
                    self.lat.push(NO);
                    self.lon.push(NO);
                }
            }
        }
        self.offs.push(self.refs.len() as i64);
        self.tags.extend_from_slice(&p.wtb[p.w_toff[j]..p.w_toff[j + 1]]);
        self.toffs.push(self.tags.len() as i64);
    }
    fn save(&self, dir: &Path, prefix: &str) {
        save_i8(dir, &format!("{prefix}_ids.npy"), &self.ids);
        save_i8(dir, &format!("{prefix}_offs.npy"), &self.offs);
        save_i8(dir, &format!("{prefix}_refs.npy"), &self.refs);
        save_i4(dir, &format!("{prefix}_lat7.npy"), &self.lat);
        save_i4(dir, &format!("{prefix}_lon7.npy"), &self.lon);
        save_i8(dir, &format!("{prefix}_toffs.npy"), &self.toffs);
        fs::write(dir.join(format!("{prefix}_tags.bin")), &self.tags).unwrap();
    }
}

/// do segments a-b and c-d (lat7, lon7 as f64) cross or touch: orientation tests, collinear overlap included
fn seg_cross(a: (f64, f64), b: (f64, f64), c: (f64, f64), d: (f64, f64)) -> bool {
    fn orient(p: (f64, f64), q: (f64, f64), r: (f64, f64)) -> f64 {
        (q.0 - p.0) * (r.1 - p.1) - (q.1 - p.1) * (r.0 - p.0)
    }
    fn on(p: (f64, f64), q: (f64, f64), r: (f64, f64)) -> bool {
        r.0 >= p.0.min(q.0) && r.0 <= p.0.max(q.0) && r.1 >= p.1.min(q.1) && r.1 <= p.1.max(q.1)
    }
    let (d1, d2, d3, d4) = (orient(c, d, a), orient(c, d, b), orient(a, b, c), orient(a, b, d));
    if ((d1 > 0.0 && d2 < 0.0) || (d1 < 0.0 && d2 > 0.0)) && ((d3 > 0.0 && d4 < 0.0) || (d3 < 0.0 && d4 > 0.0)) {
        return true;
    }
    (d1 == 0.0 && on(c, d, a)) || (d2 == 0.0 && on(c, d, b)) || (d3 == 0.0 && on(a, b, c)) || (d4 == 0.0 && on(a, b, d))
}

fn has_key(tags: &[u8], keys: &[String]) -> bool {
    tag_pairs(tags).any(|(k, _)| keys.iter().any(|x| k == x.as_bytes()))
}

/// a way in a decoded payload: refs, places (NO where absent), tags, the refs carrying a prefix tag, holding relations
struct WayFound {
    how: u8,
    refs: Vec<i64>,
    lat: Vec<i32>,
    lon: Vec<i32>,
    tags: Vec<u8>,
    anodes: Vec<i64>,
    hrels: Vec<i64>,
}

fn way_in(p: &Part, wid: i64, how: u8, prefixes: &[String]) -> Option<WayFound> {
    let j = p.wid.binary_search(&wid).ok()?;
    let refs = p.wrefs[p.w_roff[j]..p.w_roff[j + 1]].to_vec();
    let at: HashMap<i64, usize> = p.nid.iter().enumerate().map(|(i, &n)| (n, i)).collect();
    let (mut lat, mut lon, mut anodes) = (Vec::with_capacity(refs.len()), Vec::with_capacity(refs.len()), Vec::new());
    for r in &refs {
        match at.get(r) {
            Some(&i) => {
                lat.push(p.lat[i]);
                lon.push(p.lon[i]);
                if node_tags(p, i).is_some_and(|t| has_prefix(t, prefixes)) && !anodes.contains(r) {
                    anodes.push(*r);
                }
            }
            None => {
                lat.push(NO);
                lon.push(NO);
            }
        }
    }
    let tags = p.wtb[p.w_toff[j]..p.w_toff[j + 1]].to_vec();
    // the relations of this payload with the way as a member (a tile: every kept relation holding it)
    let mut hrels = Vec::new();
    for k in 0..p.rid.len() {
        let (m0, m1) = (p.r_moff[k], p.r_moff[k + 1]);
        if (m0..m1).any(|m| p.rmt[m] == 1 && p.rmref[m] == wid) {
            hrels.push(p.rid[k]);
        }
    }
    Some(WayFound { how, refs, lat, lon, tags, anodes, hrels })
}

pub fn context(a: &Args) {
    let t0 = Instant::now();
    let meta: serde_json::Value = serde_json::from_slice(&fs::read(a.store.join("store.json")).expect("store.json")).unwrap();
    let z = meta["z"].as_u64().expect("z") as u32;
    let gens: Vec<i64> = meta["generations"].as_array().expect("generations").iter().map(|g| g["gen"].as_i64().unwrap()).collect();
    let g = if a.gen < 0 { gens[(gens.len() as i64 + a.gen) as usize] } else { a.gen };
    assert!(gens.contains(&g), "the store has no generation {g}");
    let ipath = a.store.join(format!("idx-{g:04}.npy"));
    assert!(ipath.exists(), "{}: generation {g}'s tile index is gone (compacted)", ipath.display());
    let st = Store { dir: a.store.clone(), z, g, gens, idx: npy::load_idx(&ipath) };
    fs::create_dir_all(&a.out).unwrap();
    let mut stats = serde_json::Map::new();
    let mut relidx: Option<Vec<(i64, i32, i64, i32)>> = None;
    let mut blobs: HashMap<i64, Part> = HashMap::new(); // relation store blobs read so far, by relation id
    let fetch_blobs = |ids: &[i64], relidx: &mut Option<Vec<(i64, i32, i64, i32)>>, blobs: &mut HashMap<i64, Part>| {
        let ri = relidx.get_or_insert_with(|| st.relidx());
        let want: Vec<i64> = ids.iter().copied().filter(|r| !blobs.contains_key(r)).collect::<HashSet<_>>().into_iter().collect();
        let rows: Vec<_> = want.iter().filter_map(|&r| find(ri, r)).collect();
        let bufs = payloads(&st.dir, "rel", &rows);
        let parts: Vec<(i64, Part)> = rows.iter().zip(bufs).collect::<Vec<_>>().into_par_iter().map(|(r, b)| (r.0, Part::relation_blob(&b))).collect();
        blobs.extend(parts);
    };

    // the ways' holding relations, asked about as relations too (their tags, members and boxes)
    let mut held_by: Vec<i64> = Vec::new();
    // every closed way or multipolygon a node or a point found: (kind, id) -> (box, tags)
    let mut elements: HashMap<(u8, i64), ([i32; 4], Vec<u8>)> = HashMap::new();

    // --- ways -----------------------------------------------------------------------------------------------
    if let Some(wp) = &a.ways {
        let t = Instant::now();
        let ids = load_vec_i64(wp);
        let wtm = st.pairs("wtiles");
        let wt = wtm.rows();
        let mut by_tile: HashMap<i64, Vec<usize>> = HashMap::new();
        for (i, &w) in ids.iter().enumerate() {
            if let Some(r) = rows_of(wt, w).first() {
                by_tile.entry(r[1]).or_default().push(i);
            }
        }
        let mut found: Vec<Option<WayFound>> = (0..ids.len()).map(|_| None).collect();
        let keys: Vec<i64> = by_tile.keys().copied().collect();
        let mut n_tiles = keys.len();
        for chunk in keys.chunks(4096) {
            let got: Vec<(usize, WayFound)> = st
                .tiles(chunk)
                .par_iter()
                .flat_map_iter(|(k, p)| by_tile[k].iter().filter_map(|&i| way_in(p, ids[i], 1, &a.prefixes).map(|f| (i, f))).collect::<Vec<_>>())
                .collect();
            for (i, f) in got {
                found[i] = Some(f);
            }
        }
        // a way its first tile did not hold whole: places and tags of its refs from all its tiles
        let short: Vec<usize> = (0..ids.len()).filter(|&i| found[i].as_ref().is_some_and(|f| f.lat.contains(&NO))).collect();
        if !short.is_empty() {
            let mut keys: Vec<i64> = short.iter().flat_map(|&i| rows_of(wt, ids[i]).iter().map(|r| r[1])).collect();
            keys.sort_unstable();
            keys.dedup();
            n_tiles += keys.len();
            let want: HashSet<i64> = short.iter().flat_map(|&i| found[i].as_ref().unwrap().refs.clone()).collect();
            let mut places: HashMap<i64, (i32, i32, bool)> = HashMap::new();
            for chunk in keys.chunks(4096) {
                for (_, p) in st.tiles(chunk) {
                    for (j, &n) in p.nid.iter().enumerate() {
                        if want.contains(&n) {
                            let tagged = node_tags(&p, j).is_some_and(|t| has_prefix(t, &a.prefixes));
                            let e = places.entry(n).or_insert((p.lat[j], p.lon[j], false));
                            e.2 |= tagged;
                        }
                    }
                }
            }
            for &i in &short {
                let f = found[i].as_mut().unwrap();
                for k in 0..f.refs.len() {
                    if let Some(&(la, lo, tg)) = places.get(&f.refs[k]) {
                        f.lat[k] = la;
                        f.lon[k] = lo;
                        if tg && !f.anodes.contains(&f.refs[k]) {
                            f.anodes.push(f.refs[k]);
                        }
                    }
                }
            }
        }
        // ways in no tile: the relation store blobs of the given relations
        if let Some(rp) = &a.rels {
            let missing: HashMap<i64, usize> = (0..ids.len()).filter(|&i| found[i].is_none()).map(|i| (ids[i], i)).collect();
            if !missing.is_empty() {
                fetch_blobs(&load_vec_i64(rp), &mut relidx, &mut blobs);
                for p in blobs.values() {
                    for &w in &p.wid {
                        if let Some(&i) = missing.get(&w) {
                            if found[i].is_none() {
                                found[i] = way_in(p, w, 2, &a.prefixes).map(|mut f| {
                                    f.hrels.clear(); // a blob has no relations: unknown, not none
                                    f
                                });
                            }
                        }
                    }
                }
            }
        }
        let (mut how, mut offs, mut refs, mut lat, mut lon) = (Vec::new(), vec![0i64], Vec::new(), Vec::new(), Vec::new());
        let mut tags = Out::new();
        let (mut aoffs, mut anodes, mut hoffs, mut hrels) = (vec![0i64], Vec::new(), vec![0i64], Vec::new());
        for (i, f) in found.iter().enumerate() {
            match f {
                Some(f) => {
                    how.push(f.how);
                    refs.extend_from_slice(&f.refs);
                    lat.extend_from_slice(&f.lat);
                    lon.extend_from_slice(&f.lon);
                    tags.push(ids[i], &f.tags);
                    anodes.extend_from_slice(&f.anodes);
                    hrels.extend_from_slice(&f.hrels);
                }
                None => {
                    how.push(0);
                    tags.push(ids[i], &[]);
                }
            }
            offs.push(refs.len() as i64);
            aoffs.push(anodes.len() as i64);
            hoffs.push(hrels.len() as i64);
        }
        let d = &a.out;
        save_i8(d, "w_ids.npy", &ids);
        save_u1(d, "w_how.npy", &how);
        save_i8(d, "w_offs.npy", &offs);
        save_i8(d, "w_refs.npy", &refs);
        save_i4(d, "w_lat7.npy", &lat);
        save_i4(d, "w_lon7.npy", &lon);
        save_i8(d, "w_toffs.npy", &tags.toffs);
        fs::write(d.join("w_tags.bin"), &tags.tags).unwrap();
        save_i8(d, "w_aoffs.npy", &aoffs);
        save_i8(d, "w_anodes.npy", &anodes);
        save_i8(d, "w_hoffs.npy", &hoffs);
        save_i8(d, "w_hrels.npy", &hrels);
        stats.insert("ways".into(), serde_json::json!({
            "asked": ids.len(), "fromTiles": how.iter().filter(|&&h| h == 1).count(),
            "fromRelationStore": how.iter().filter(|&&h| h == 2).count(), "absent": how.iter().filter(|&&h| h == 0).count(),
            "withPrefixNodes": (0..ids.len()).filter(|&i| aoffs[i + 1] > aoffs[i]).count(), "holdingRelations": hrels.len(),
            "tilesRead": n_tiles, "seconds": t.elapsed().as_secs_f64()}));
        held_by = hrels;
    }

    // --- relations: the asked ones and the ways' holding relations -------------------------------------------
    let mut rel_ids: Vec<i64> = a.rels.as_ref().map(|p| load_vec_i64(p)).unwrap_or_default();
    rel_ids.extend_from_slice(&held_by);
    rel_ids.sort_unstable();
    rel_ids.dedup();
    if !rel_ids.is_empty() {
        let t = Instant::now();
        let rtm = st.pairs("rtiles");
        let rt = rtm.rows();
        let mut by_tile: HashMap<i64, Vec<usize>> = HashMap::new();
        for (i, &r) in rel_ids.iter().enumerate() {
            if let Some(row) = rows_of(rt, r).first() {
                by_tile.entry(row[1]).or_default().push(i);
            }
        }
        type RelFound = (Vec<u8>, Vec<u8>, Vec<i64>);
        let mut found: Vec<Option<RelFound>> = (0..rel_ids.len()).map(|_| None).collect();
        let keys: Vec<i64> = by_tile.keys().copied().collect();
        for chunk in keys.chunks(4096) {
            for (k, p) in st.tiles(chunk) {
                for &i in &by_tile[&k] {
                    if let Ok(j) = p.rid.binary_search(&rel_ids[i]) {
                        let (m0, m1) = (p.r_moff[j], p.r_moff[j + 1]);
                        found[i] = Some((p.rtb[p.r_toff[j]..p.r_toff[j + 1]].to_vec(), p.rmt[m0..m1].iter().map(|&x| x as u8).collect(), p.rmref[m0..m1].to_vec()));
                    }
                }
            }
        }
        fetch_blobs(&rel_ids, &mut relidx, &mut blobs);
        if a.rel_geometry {
            // each relation's member ways from its blob (the relation store keeps a kept relation's member ways whole)
            let mut geo = Geo::new();
            let mut woffs = vec![0i64];
            for r in &rel_ids {
                if let Some(b) = blobs.get(r) {
                    for j in 0..b.wid.len() {
                        geo.push_way(b, j);
                    }
                }
                woffs.push(geo.ids.len() as i64);
            }
            save_i8(&a.out, "r_woffs.npy", &woffs);
            save_i8(&a.out, "rw_ids.npy", &geo.ids);
            save_i8(&a.out, "rw_poffs.npy", &geo.offs);
            save_i8(&a.out, "rw_refs.npy", &geo.refs);
            save_i4(&a.out, "rw_lat7.npy", &geo.lat);
            save_i4(&a.out, "rw_lon7.npy", &geo.lon);
        }
        let mut tags = Out::new();
        let (mut fnd, mut moffs, mut mtype, mut mref, mut boxes) = (Vec::new(), vec![0i64], Vec::new(), Vec::new(), Vec::new());
        for (i, f) in found.iter().enumerate() {
            match f {
                Some((tg, mt, mr)) => {
                    fnd.push(1u8);
                    tags.push(rel_ids[i], tg);
                    mtype.extend_from_slice(mt);
                    mref.extend_from_slice(mr);
                }
                None => {
                    fnd.push(0);
                    tags.push(rel_ids[i], &[]);
                }
            }
            moffs.push(mref.len() as i64);
            boxes.extend_from_slice(&blobs.get(&rel_ids[i]).map(blob_box).unwrap_or([NO; 4]));
        }
        let d = &a.out;
        save_i8(d, "r_ids.npy", &rel_ids);
        save_u1(d, "r_found.npy", &fnd);
        save_i8(d, "r_toffs.npy", &tags.toffs);
        fs::write(d.join("r_tags.bin"), &tags.tags).unwrap();
        save_i8(d, "r_moffs.npy", &moffs);
        save_u1(d, "r_mtype.npy", &mtype);
        save_i8(d, "r_mref.npy", &mref);
        save_i4(d, "r_box.npy", &boxes);
        stats.insert("relations".into(), serde_json::json!({
            "asked": rel_ids.len(), "found": fnd.iter().filter(|&&x| x == 1).count(),
            "withBox": boxes.chunks(4).filter(|b| b[0] != NO).count(), "seconds": t.elapsed().as_secs_f64()}));
    }

    // --- nodes: tags at G from the tile at each node's place --------------------------------------------------
    if let (Some(np_), Some(pp)) = (&a.nodes, &a.node_places) {
        let t = Instant::now();
        let ids = load_vec_i64(np_);
        let pl = load_vec_i64(pp);
        assert_eq!(pl.len(), 2 * ids.len(), "--node-places: lat7, lon7 for each node");
        let mut by_tile: HashMap<i64, Vec<usize>> = HashMap::new();
        for i in 0..ids.len() {
            let (la, lo) = (pl[2 * i], pl[2 * i + 1]);
            if la == NO as i64 || lo == NO as i64 {
                continue;
            }
            let (x, y) = st.key_at(la as i32, lo as i32);
            by_tile.entry(key_of(x, y, st.z) as i64).or_default().push(i);
        }
        let mut found: Vec<Option<Vec<u8>>> = (0..ids.len()).map(|_| None).collect();
        // the tile at its place holds the node (untagged when `found` has nothing): not the same as absent, which a
        // clip's store says of a node outside its polygon
        let mut present = vec![false; ids.len()];
        // the closed ways with the node as a vertex (a tile holds every way crossing it, so the node's own tile has
        // them all): an area with an address on its outline is a container (AddHousenumber)
        let mut vways: Vec<Vec<i64>> = vec![Vec::new(); ids.len()];
        // --vertex-ways: every way with an asked node as a vertex, its geometry (the union over the nodes)
        let mut vgeo = Geo::new();
        let mut vseen: HashSet<i64> = HashSet::new();
        let keys: Vec<i64> = by_tile.keys().copied().collect();
        for chunk in keys.chunks(4096) {
            for (k, p) in st.tiles(chunk) {
                let at: HashMap<i64, usize> = p.nid.iter().enumerate().map(|(i, &n)| (n, i)).collect();
                let asked: HashSet<i64> = by_tile[&k].iter().map(|&i| ids[i]).collect();
                let mut ring_of: HashMap<i64, Vec<usize>> = HashMap::new();
                for j in 0..p.wid.len() {
                    let r = &p.wrefs[p.w_roff[j]..p.w_roff[j + 1]];
                    if a.vertex_ways && !vseen.contains(&p.wid[j]) && r.iter().any(|n| asked.contains(n)) {
                        vseen.insert(p.wid[j]);
                        vgeo.push_way(&p, j);
                    }
                    if r.len() >= 4 && r[0] == r[r.len() - 1] {
                        for &n in &r[..r.len() - 1] {
                            if asked.contains(&n) {
                                ring_of.entry(n).or_default().push(j);
                            }
                        }
                    }
                }
                for &i in &by_tile[&k] {
                    if let Some(&j) = at.get(&ids[i]) {
                        present[i] = true;
                        if let Some(t) = node_tags(&p, j) {
                            found[i] = Some(t.to_vec());
                        }
                    }
                    for &j in ring_of.get(&ids[i]).map(Vec::as_slice).unwrap_or(&[]) {
                        let wid = p.wid[j];
                        if vways[i].contains(&wid) {
                            continue;
                        }
                        let r = &p.wrefs[p.w_roff[j]..p.w_roff[j + 1]];
                        let pos: Vec<(i32, i32)> = r.iter().filter_map(|n| at.get(n).map(|&q| (p.lat[q], p.lon[q]))).collect();
                        if pos.is_empty() {
                            continue;
                        }
                        let bx = [pos.iter().map(|q| q.0).min().unwrap(), pos.iter().map(|q| q.1).min().unwrap(),
                                  pos.iter().map(|q| q.0).max().unwrap(), pos.iter().map(|q| q.1).max().unwrap()];
                        vways[i].push(wid);
                        elements.entry((1, wid)).or_insert_with(|| (bx, p.wtb[p.w_toff[j]..p.w_toff[j + 1]].to_vec()));
                    }
                }
            }
        }
        let mut tags = Out::new();
        let (mut fnd, mut voffs, mut vflat) = (Vec::new(), vec![0i64], Vec::new());
        for (i, f) in found.iter().enumerate() {
            fnd.push(if f.is_some() { 1 } else if present[i] { 2 } else { 0 });
            tags.push(ids[i], f.as_deref().unwrap_or(&[]));
            vflat.extend_from_slice(&vways[i]);
            voffs.push(vflat.len() as i64);
        }
        save_i8(&a.out, "n_ids.npy", &ids);
        save_u1(&a.out, "n_found.npy", &fnd);
        save_i8(&a.out, "n_toffs.npy", &tags.toffs);
        fs::write(a.out.join("n_tags.bin"), &tags.tags).unwrap();
        save_i8(&a.out, "n_voffs.npy", &voffs);
        save_i8(&a.out, "n_vways.npy", &vflat);
        if a.vertex_ways {
            vgeo.save(&a.out, "v");
        }
        stats.insert("nodes".into(), serde_json::json!({"asked": ids.len(), "tagged": fnd.iter().filter(|&&x| x == 1).count(),
            "untagged": fnd.iter().filter(|&&x| x == 2).count(), "absent": fnd.iter().filter(|&&x| x == 0).count(),
            "onClosedWays": (0..ids.len()).filter(|&i| voffs[i + 1] > voffs[i]).count(), "vertexWays": vgeo.ids.len(),
            "tilesRead": keys.len(), "seconds": t.elapsed().as_secs_f64()}));
    }

    // --- points: the closed ways and multipolygons holding each point ------------------------------------------
    if let Some(pp) = &a.points {
        let t = Instant::now();
        let pl = load_vec_i64(pp);
        let n = pl.len() / 2;
        let pts: Vec<(i32, i32)> = (0..n).map(|i| (pl[2 * i] as i32, pl[2 * i + 1] as i32)).collect();
        // points by home tile, the home tiles in chunks: each chunk reads its block of tiles once
        let mut by_home: HashMap<(i64, i64), Vec<usize>> = HashMap::new();
        for (i, &(la, lo)) in pts.iter().enumerate() {
            by_home.entry(st.key_at(la, lo)).or_default().push(i);
        }
        let mut homes: Vec<(i64, i64)> = by_home.keys().copied().collect();
        homes.sort_unstable();
        let mut hits: Vec<Vec<(u8, i64)>> = vec![Vec::new(); n];
        let n_el0 = elements.len();
        let m = (1i64 << st.z) - 1;
        let mut n_tiles = 0usize;
        for chunk in homes.chunks(512) {
            let mut keys: Vec<i64> = Vec::new();
            for &(x, y) in chunk {
                for dx in -a.around..=a.around {
                    for dy in -a.around..=a.around {
                        let (xx, yy) = (x + dx, y + dy);
                        if (0..=m).contains(&xx) && (0..=m).contains(&yy) {
                            keys.push(key_of(xx, yy, st.z) as i64);
                        }
                    }
                }
            }
            keys.sort_unstable();
            keys.dedup();
            n_tiles += keys.len();
            let tiles: HashMap<i64, Part> = st.tiles(&keys).into_iter().collect();
            // multipolygons in these tiles: their blobs, for the ring test and the box
            let mp: Vec<i64> = tiles
                .values()
                .flat_map(|p| (0..p.rid.len()).filter(|&k| tag_pairs(&p.rtb[p.r_toff[k]..p.r_toff[k + 1]]).any(|(k_, v)| k_ == b"type" && v == b"multipolygon")).map(|k| p.rid[k]).collect::<Vec<_>>())
                .collect::<HashSet<_>>()
                .into_iter()
                .collect();
            fetch_blobs(&mp, &mut relidx, &mut blobs);
            for &home in chunk {
                let block: Vec<&Part> = (-a.around..=a.around)
                    .flat_map(|dx| (-a.around..=a.around).map(move |dy| (home.0 + dx, home.1 + dy)))
                    .filter(|(xx, yy)| (0..=m).contains(xx) && (0..=m).contains(yy))
                    .filter_map(|(xx, yy)| tiles.get(&(key_of(xx, yy, st.z) as i64)))
                    .collect();
                for &i in &by_home[&home] {
                    let (la, lo) = (pts[i].0 as f64, pts[i].1 as f64);
                    let mut seen: HashSet<(u8, i64)> = HashSet::new();
                    for p in &block {
                        for j in 0..p.wid.len() {
                            let r = &p.wrefs[p.w_roff[j]..p.w_roff[j + 1]];
                            if r.len() < 4 || r[0] != r[r.len() - 1] || seen.contains(&(1, p.wid[j])) {
                                continue;
                            }
                            let id = p.wid[j];
                            let pos: Vec<(i32, i32)> = r
                                .iter()
                                .filter_map(|n| p.nid.binary_search(n).ok().map(|k| (p.lat[k], p.lon[k])))
                                .collect();
                            if pos.len() != r.len() {
                                continue; // a ring the tile does not place whole: another tile of the block does
                            }
                            let (s, n_) = (pos.iter().map(|q| q.0).min().unwrap(), pos.iter().map(|q| q.0).max().unwrap());
                            let (w, e) = (pos.iter().map(|q| q.1).min().unwrap(), pos.iter().map(|q| q.1).max().unwrap());
                            if la < s as f64 || la > n_ as f64 || lo < w as f64 || lo > e as f64 {
                                continue;
                            }
                            seen.insert((1, id));
                            let segs: Vec<[f64; 4]> = pos.windows(2).map(|q| [q[0].0 as f64, q[0].1 as f64, q[1].0 as f64, q[1].1 as f64]).collect();
                            if evenodd(&segs, la, lo) {
                                hits[i].push((1, id));
                                elements.entry((1, id)).or_insert_with(|| ([s, w, n_, e], p.wtb[p.w_toff[j]..p.w_toff[j + 1]].to_vec()));
                            }
                        }
                        for k in 0..p.rid.len() {
                            let id = p.rid[k];
                            if seen.contains(&(2, id)) {
                                continue;
                            }
                            let rtags = &p.rtb[p.r_toff[k]..p.r_toff[k + 1]];
                            if !tag_pairs(rtags).any(|(k_, v)| k_ == b"type" && v == b"multipolygon") {
                                continue;
                            }
                            seen.insert((2, id));
                            let Some(b) = blobs.get(&id) else { continue };
                            let bx = blob_box(b);
                            if bx[0] == NO || la < bx[0] as f64 || la > bx[2] as f64 || lo < bx[1] as f64 || lo > bx[3] as f64 {
                                continue;
                            }
                            // every member way's segments (outer and inner alike: even-odd over all of them)
                            let at: HashMap<i64, (i32, i32)> = b.nid.iter().enumerate().map(|(q, &nn)| (nn, (b.lat[q], b.lon[q]))).collect();
                            let mut segs = Vec::new();
                            for q in 0..b.wid.len() {
                                let r = &b.wrefs[b.w_roff[q]..b.w_roff[q + 1]];
                                for s2 in r.windows(2) {
                                    if let (Some(&u), Some(&v)) = (at.get(&s2[0]), at.get(&s2[1])) {
                                        segs.push([u.0 as f64, u.1 as f64, v.0 as f64, v.1 as f64]);
                                    }
                                }
                            }
                            if evenodd(&segs, la, lo) {
                                hits[i].push((2, id));
                                elements.entry((2, id)).or_insert_with(|| (bx, rtags.to_vec()));
                            }
                        }
                    }
                }
            }
        }
        let (mut poffs, mut pkind, mut pid) = (vec![0i64], Vec::new(), Vec::new());
        for h in &hits {
            for &(k, id) in h {
                pkind.push(k);
                pid.push(id);
            }
            poffs.push(pid.len() as i64);
        }
        let d = &a.out;
        save_i8(d, "p_offs.npy", &poffs);
        save_u1(d, "p_kind.npy", &pkind);
        save_i8(d, "p_id.npy", &pid);
        stats.insert("points".into(), serde_json::json!({"asked": n, "withContainer": hits.iter().filter(|h| !h.is_empty()).count(),
            "newContainers": elements.len() - n_el0, "tilesRead": n_tiles, "around": a.around, "seconds": t.elapsed().as_secs_f64()}));
    }

    // --- crossings: the ways with a key whose segments cross the given segments ----------------------------------
    if let Some(xp) = &a.crossing {
        let t = Instant::now();
        let v = load_vec_i64(xp);
        assert!(v.len() % 4 == 0, "--crossing: lat7, lon7, lat7, lon7 per segment");
        let segs: Vec<[f64; 4]> = v.chunks(4).map(|c| [c[0] as f64, c[1] as f64, c[2] as f64, c[3] as f64]).collect();
        let nt = (1u64 << st.z) as f64;
        let mut by_tile: HashMap<i64, Vec<usize>> = HashMap::new();
        let mut k: Vec<u32> = Vec::new();
        for (i, s_) in segs.iter().enumerate() {
            k.clear();
            let (ax, ay) = frac_xy(s_[0] as i32, s_[1] as i32, nt);
            let (bx, by) = frac_xy(s_[2] as i32, s_[3] as i32, nt);
            k.push(key_of(ax.floor() as i64, ay.floor() as i64, st.z));
            k.push(key_of(bx.floor() as i64, by.floor() as i64, st.z));
            segment_tiles(ax, ay, bx, by, st.z, &mut k);
            k.sort_unstable();
            k.dedup();
            for &key in &k {
                by_tile.entry(key as i64).or_default().push(i);
            }
        }
        let mut keys: Vec<i64> = by_tile.keys().copied().collect();
        keys.sort_unstable();
        let mut geo = Geo::new();
        let mut seen: HashSet<i64> = HashSet::new();
        let mut tested = 0usize;
        for chunk in keys.chunks(1024) {
            for (key, p) in st.tiles(chunk) {
                let mine: Vec<[f64; 4]> = by_tile[&key].iter().map(|&i| segs[i]).collect();
                // the given segments' box in this tile, a first cut for each way
                let (bs, bw, bn, be) = mine.iter().fold((f64::MAX, f64::MAX, f64::MIN, f64::MIN), |b, s_| {
                    (b.0.min(s_[0]).min(s_[2]), b.1.min(s_[1]).min(s_[3]), b.2.max(s_[0]).max(s_[2]), b.3.max(s_[1]).max(s_[3]))
                });
                for j in 0..p.wid.len() {
                    if seen.contains(&p.wid[j]) || !has_key(&p.wtb[p.w_toff[j]..p.w_toff[j + 1]], &a.crossing_keys) {
                        continue;
                    }
                    let r = &p.wrefs[p.w_roff[j]..p.w_roff[j + 1]];
                    let pos: Vec<Option<(f64, f64)>> =
                        r.iter().map(|n| p.nid.binary_search(n).ok().map(|q| (p.lat[q] as f64, p.lon[q] as f64))).collect();
                    tested += 1;
                    let mut hit = false;
                    'way: for w2 in pos.windows(2) {
                        let (Some(u), Some(w_)) = (w2[0], w2[1]) else { continue };
                        if u.0.max(w_.0) < bs || u.0.min(w_.0) > bn || u.1.max(w_.1) < bw || u.1.min(w_.1) > be {
                            continue;
                        }
                        for s_ in &mine {
                            if seg_cross(u, w_, (s_[0], s_[1]), (s_[2], s_[3])) {
                                hit = true;
                                break 'way;
                            }
                        }
                    }
                    if hit {
                        seen.insert(p.wid[j]);
                        geo.push_way(&p, j);
                    }
                }
            }
        }
        geo.save(&a.out, "x");
        stats.insert("crossing".into(), serde_json::json!({"segments": segs.len(), "tilesRead": keys.len(),
            "waysTested": tested, "waysCrossing": geo.ids.len(), "keys": a.crossing_keys, "seconds": t.elapsed().as_secs_f64()}));
    }

    if !elements.is_empty() || a.points.is_some() || a.nodes.is_some() {
        let mut el: Vec<_> = elements.into_iter().collect();
        el.sort_unstable_by_key(|e| e.0);
        let mut tags = Out::new();
        let (mut ekind, mut ebox) = (Vec::new(), Vec::new());
        for ((k, id), (bx, tg)) in &el {
            ekind.push(*k);
            ebox.extend_from_slice(bx);
            tags.push(*id, tg);
        }
        let d = &a.out;
        save_u1(d, "e_kind.npy", &ekind);
        save_i8(d, "e_id.npy", &tags.ids);
        save_i4(d, "e_box.npy", &ebox);
        save_i8(d, "e_toffs.npy", &tags.toffs);
        fs::write(d.join("e_tags.bin"), &tags.tags).unwrap();
    }

    stats.insert("gen".into(), g.into());
    stats.insert("seconds".into(), t0.elapsed().as_secs_f64().into());
    stats.insert("peakPrivateGiB".into(), crate::ptime::peak_private().into());
    let s = serde_json::Value::Object(stats).to_string();
    fs::write(a.out.join("context.json"), &s).unwrap();
    crate::log(&format!("context: {s}"));
}
