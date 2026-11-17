//! The way lookup: given way ids, each way's node refs and every ref's position as a generation of the store holds
//! them (DESIGN.md, "Release 1: the world day", step 3: changed ways' old geometry and changed relations' member
//! ways, so tier 2 keeps no way index of its own).
//!
//! A way is found through the generation's way pair file (wtiles-G: way id -> the tiles it crosses) and one of those
//! tiles' payload, which holds the way whole (its refs, and the place of each ref); a ref a tile lacks sends the way
//! through all its tiles. A way in no tile (a member way that only the relation store keeps) is looked for in the
//! relation store blobs of the relations given with --rels (relidx of the newest generation up to G that wrote one).
//!
//! The pair file of a generation exists until the next update with --prune-pairs removes it: ask for D-1 before the
//! day's update, or without --prune-pairs. The tile index (idx-G) exists until `compact`.

use crate::npy;
use crate::read::{find, payloads, Part};
use rayon::prelude::*;
use std::collections::HashMap;
use std::fs::{self, File};
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use std::time::Instant;

pub struct Args {
    pub store: PathBuf,
    pub gen: i64,
    pub ids: PathBuf,
    pub rels: Option<PathBuf>,
    pub out: PathBuf,
}

/// a 1-d .npy of one plain dtype ('<i8', '<i4', '|u1')
pub(crate) fn load_vec_i64(path: &Path) -> Vec<i64> {
    let b = fs::read(path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    assert!(b.starts_with(b"\x93NUMPY\x01"), "{}: not a version 1 .npy", path.display());
    let start = 10 + u16::from_le_bytes([b[8], b[9]]) as usize;
    let head = std::str::from_utf8(&b[10..start]).unwrap();
    assert!(head.contains("'<i8'") && head.contains("'fortran_order': False"), "{}: want a 1-d '<i8' array, not {head}", path.display());
    b[start..].chunks_exact(8).map(|r| i64::from_le_bytes(r.try_into().unwrap())).collect()
}

pub(crate) fn save_vec<T: Copy>(path: &Path, descr: &str, v: &[T], bytes: impl Fn(T) -> Vec<u8>) {
    let mut f = BufWriter::with_capacity(1 << 22, File::create(path).unwrap());
    npy::header(&mut f, descr, v.len());
    for &x in v {
        f.write_all(&bytes(x)).unwrap();
    }
    f.flush().unwrap();
}

/// a way as found: refs and their places (i32::MIN where no payload held the node)
struct Found {
    how: u8,
    refs: Vec<i64>,
    lat: Vec<i32>,
    lon: Vec<i32>,
}

/// the way `wid` out of a decoded payload, its refs placed from that payload's nodes (None if the payload lacks it)
fn way_of(p: &Part, places: &HashMap<i64, (i32, i32)>, wid: i64, how: u8) -> Option<Found> {
    let j = p.wid.binary_search(&wid).ok()?;
    let refs = p.wrefs[p.w_roff[j]..p.w_roff[j + 1]].to_vec();
    let (mut lat, mut lon) = (Vec::with_capacity(refs.len()), Vec::with_capacity(refs.len()));
    for r in &refs {
        let (a, b) = places.get(r).copied().unwrap_or((i32::MIN, i32::MIN));
        lat.push(a);
        lon.push(b);
    }
    Some(Found { how, refs, lat, lon })
}

fn places_of(p: &Part) -> HashMap<i64, (i32, i32)> {
    p.nid.iter().enumerate().map(|(i, &n)| (n, (p.lat[i], p.lon[i]))).collect()
}

fn complete(f: &Found) -> bool {
    f.lat.iter().all(|&x| x != i32::MIN)
}

pub fn ways(a: &Args) {
    let t0 = Instant::now();
    let meta: serde_json::Value = serde_json::from_slice(&fs::read(a.store.join("store.json")).expect("store.json")).unwrap();
    let gens: Vec<i64> = meta["generations"].as_array().expect("generations").iter().map(|g| g["gen"].as_i64().unwrap()).collect();
    let g = if a.gen < 0 { gens[(gens.len() as i64 + a.gen) as usize] } else { a.gen };
    assert!(gens.contains(&g), "the store has no generation {g}");
    let wpath = a.store.join(format!("wtiles-{g:04}.npy"));
    assert!(wpath.exists(), "{}: generation {g}'s way pairs are gone (pruned by a later update with --prune-pairs); \
        ask before the update", wpath.display());
    let ipath = a.store.join(format!("idx-{g:04}.npy"));
    assert!(ipath.exists(), "{}: generation {g}'s tile index is gone (compacted)", ipath.display());
    let idx = npy::load_idx(&ipath);
    let wtm = npy::PairMap::open(&wpath);
    let wt = wtm.rows();
    let ids = load_vec_i64(&a.ids);

    // each way's tiles, sorted (the pair rows are sorted by id, then key)
    let tiles_of = |wid: i64| -> &[[i64; 2]] {
        let lo = wt.partition_point(|r| r[0] < wid);
        let hi = lo + wt[lo..].partition_point(|r| r[0] <= wid);
        &wt[lo..hi]
    };
    // first round: one tile per way, each tile read once for all the ways that chose it
    let mut by_tile: HashMap<i64, Vec<usize>> = HashMap::new();
    // TILESTORE_WAYS_RELS_ONLY=1: skip the tiles, so the relation store path is checked alone (waycmp.py --rels-only)
    let rels_only = std::env::var("TILESTORE_WAYS_RELS_ONLY").is_ok_and(|v| v == "1");
    for (i, &w) in ids.iter().enumerate() {
        if rels_only {
            break;
        }
        if let Some(r) = tiles_of(w).first() {
            by_tile.entry(r[1]).or_default().push(i);
        }
    }
    let mut found: Vec<Option<Found>> = (0..ids.len()).map(|_| None).collect();
    let read_tiles = |keys: &[i64]| -> Vec<(i64, Part)> {
        let rows: Vec<_> = keys.iter().filter_map(|&k| find(&idx, k)).collect();
        let bufs = payloads(&a.store, "pack", &rows);
        rows.iter().zip(bufs).collect::<Vec<_>>().into_par_iter().map(|(r, b)| (r.0, Part::tile(&b))).collect()
    };
    let keys: Vec<i64> = by_tile.keys().copied().collect();
    let mut n_tiles = keys.len();
    for chunk in keys.chunks(4096) {
        let parts = read_tiles(chunk);
        let got: Vec<(usize, Found)> = parts
            .par_iter()
            .flat_map_iter(|(k, p)| {
                let pl = places_of(p);
                by_tile[k].iter().filter_map(|&i| way_of(p, &pl, ids[i], 1).map(|f| (i, f))).collect::<Vec<_>>()
            })
            .collect();
        for (i, f) in got {
            found[i] = Some(f);
        }
    }
    // second round: a way the first tile did not hold whole is placed from all its tiles
    let short: Vec<usize> = (0..ids.len()).filter(|&i| found[i].as_ref().is_some_and(|f| !complete(f))).collect();
    if !short.is_empty() {
        let mut keys: Vec<i64> = short.iter().flat_map(|&i| tiles_of(ids[i]).iter().map(|r| r[1])).collect();
        keys.sort_unstable();
        keys.dedup();
        n_tiles += keys.len();
        let mut places: HashMap<i64, (i32, i32)> = HashMap::new();
        let want: std::collections::HashSet<i64> = short.iter().flat_map(|&i| found[i].as_ref().unwrap().refs.clone()).collect();
        for chunk in keys.chunks(4096) {
            for (_, p) in read_tiles(chunk) {
                for (j, &n) in p.nid.iter().enumerate() {
                    if want.contains(&n) {
                        places.insert(n, (p.lat[j], p.lon[j]));
                    }
                }
            }
        }
        for &i in &short {
            let f = found[i].as_mut().unwrap();
            for (k, r) in f.refs.iter().enumerate() {
                if let Some(&(la, lo)) = places.get(r) {
                    f.lat[k] = la;
                    f.lon[k] = lo;
                }
            }
        }
    }
    // third: ways in no tile, from the relation store blobs of the given relations
    let mut n_rel_blobs = 0;
    if let Some(rp) = &a.rels {
        let missing: HashMap<i64, usize> = (0..ids.len()).filter(|&i| found[i].is_none()).map(|i| (ids[i], i)).collect();
        if !missing.is_empty() {
            let rg = gens.iter().copied().filter(|&x| x <= g && a.store.join(format!("relidx-{x:04}.npy")).exists()).max().expect("a relation index");
            let ridx = npy::load_idx(&a.store.join(format!("relidx-{rg:04}.npy")));
            let mut rels = load_vec_i64(rp);
            rels.sort_unstable();
            rels.dedup();
            let rows: Vec<_> = rels.iter().filter_map(|&r| find(&ridx, r)).collect();
            n_rel_blobs = rows.len();
            let bufs = payloads(&a.store, "rel", &rows);
            for b in bufs {
                let p = Part::relation_blob(&b);
                let pl = places_of(&p);
                for &w in &p.wid {
                    if let Some(&i) = missing.get(&w) {
                        if found[i].is_none() {
                            found[i] = way_of(&p, &pl, w, 2);
                        }
                    }
                }
            }
        }
    }

    // out: ids (as asked), how (0 absent, 1 a tile, 2 the relation store), offs (n + 1), refs, lat7, lon7
    fs::create_dir_all(&a.out).unwrap();
    let (mut how, mut offs, mut refs, mut lat, mut lon) = (Vec::new(), vec![0i64], Vec::new(), Vec::new(), Vec::new());
    let mut unplaced = 0usize;
    for f in &found {
        match f {
            Some(f) => {
                how.push(f.how);
                refs.extend_from_slice(&f.refs);
                lat.extend_from_slice(&f.lat);
                lon.extend_from_slice(&f.lon);
                unplaced += f.lat.iter().filter(|&&x| x == i32::MIN).count();
            }
            None => how.push(0),
        }
        offs.push(refs.len() as i64);
    }
    save_vec(&a.out.join("ids.npy"), "'<i8'", &ids, |x| x.to_le_bytes().to_vec());
    save_vec(&a.out.join("how.npy"), "'|u1'", &how, |x| vec![x]);
    save_vec(&a.out.join("offs.npy"), "'<i8'", &offs, |x| x.to_le_bytes().to_vec());
    save_vec(&a.out.join("refs.npy"), "'<i8'", &refs, |x| x.to_le_bytes().to_vec());
    save_vec(&a.out.join("lat7.npy"), "'<i4'", &lat, |x| x.to_le_bytes().to_vec());
    save_vec(&a.out.join("lon7.npy"), "'<i4'", &lon, |x| x.to_le_bytes().to_vec());
    let n_tile = how.iter().filter(|&&h| h == 1).count();
    let n_rel = how.iter().filter(|&&h| h == 2).count();
    let st = format!(
        "{{\"by\": \"tilestore ways\", \"gen\": {g}, \"ways\": {}, \"fromTiles\": {n_tile}, \"fromRelationStore\": {n_rel}, \
         \"absent\": {}, \"refs\": {}, \"refsUnplaced\": {unplaced}, \"tilesRead\": {n_tiles}, \"relationBlobsRead\": {n_rel_blobs}, \
         \"seconds\": {:.2}, \"peakPrivateGiB\": {:.2}}}",
        ids.len(),
        ids.len() - n_tile - n_rel,
        refs.len(),
        t0.elapsed().as_secs_f64(),
        crate::ptime::peak_private()
    );
    fs::write(a.out.join("ways.json"), &st).unwrap();
    crate::log(&format!("ways: {st}"));
}
