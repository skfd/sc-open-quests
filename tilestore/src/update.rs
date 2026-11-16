//! The day's update (tilestore.py update), step for step, so that its generation equals the prototype's tile for
//! tile, blob for blob and pair for pair (tools/stream/tilecheck/storecmp.py). The tiles a day changes are rebuilt
//! from a working set: the old payloads of every tile the day reaches, the relation store's old blobs of the
//! relations it reaches, and the diff over them; the tile rule (pairs.rs) runs again on that set and only the reached
//! tiles are written, into a new generation. A tile is reached through the old and new tiles of: each changed node
//! (its own place), each changed way and each way holding a changed node (found in that node's old home tile, which
//! holds every way with a node there: no way index), and each relation that changed or has such a way or node as
//! member.
//!
//! Where the prototype's choices look arbitrary (which copies make up the working set, what is filtered by the
//! store's region and what is not) they are kept as they are: the port is held against its output.

use crate::clip::{Clip, NONE};
use crate::cols::{pack_cols, Col};
use crate::read::{find, payloads, Part};
use crate::tiles::{frac_deg, frac_xy, key_of};
use crate::{log, npy, osc, pairs, tiles};
use osmpbf::{BlobDecode, BlobReader};
use rayon::prelude::*;
use std::collections::{BTreeSet, HashMap, HashSet};
use std::fs::{self, File};
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use std::time::Instant;

type Row = (i64, i32, i64, i32);

pub struct Args {
    pub store: PathBuf,
    pub diff: PathBuf,
    /// the node places before the day: a clip's PBF of the day before, or a node file by id
    pub before: PathBuf,
    /// `before` is a node file by id in osmium's dense_file_array layout (the world stream's planet.loc), not a PBF
    pub before_loc: bool,
    /// a store of the whole world: every tile is in its region (no polygon, no edge)
    pub world: bool,
    /// delete the generation before's pair indexes once this one is written (the next update reads only the newest)
    pub prune_pairs: bool,
    /// rebuild the reached tiles in groups, one per cell of this zoom, not in one working set (a planet day's would
    /// not fit in memory)
    pub group_z: Option<u32>,
    /// rebuild the reached tiles in groups of about this many MiB of old payload, in the order of their zoom-8 cells
    pub group_mib: Option<u64>,
    pub day: String,
    /// the clip's polygon: the store's region (the planet diff's changes elsewhere stay out)
    pub polygon: Option<PathBuf>,
}

/// the node places before the day (tilestore.py NodeTable): a clip's, read from its PBF into memory, or the world's,
/// a node file by id mapped (osmium's dense_file_array, as stream.py DenseLocations keeps it: at byte 8 * id the
/// longitude and latitude in 1e-7 degrees, int32 little-endian; both 2^31-1 when there is no such node)
enum NodeTable {
    Mem { id: Vec<i64>, lat: Vec<i32>, lon: Vec<i32> },
    Dense(memmap2::Mmap),
}

impl NodeTable {
    fn len(&self) -> usize {
        match self {
            NodeTable::Mem { id, .. } => id.len(),
            NodeTable::Dense(m) => m.len() / 8,
        }
    }

    fn dense(path: &Path) -> NodeTable {
        let f = File::open(path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
        // SAFETY: read only; the stream writes its node file only on its own save(), not while an update runs
        NodeTable::Dense(unsafe { memmap2::Mmap::map(&f) }.unwrap_or_else(|e| panic!("map {}: {e}", path.display())))
    }

    fn from_pbf(pbf: &Path) -> NodeTable {
        let (mut ids, mut lats, mut lons) = (Vec::new(), Vec::new(), Vec::new());
        let mut reader = BlobReader::from_path(pbf).unwrap_or_else(|e| panic!("{}: {e}", pbf.display()));
        loop {
            let batch: Vec<_> = reader.by_ref().take(256).map(|b| b.expect("read a blob")).collect();
            if batch.is_empty() {
                break;
            }
            let parts: Vec<(Vec<i64>, Vec<i32>, Vec<i32>)> = batch
                .par_iter()
                .map(|b| {
                    let (mut i, mut la, mut lo) = (Vec::new(), Vec::new(), Vec::new());
                    if let BlobDecode::OsmData(block) = b.decode().expect("decode a blob") {
                        for g in block.groups() {
                            for n in g.dense_nodes() {
                                i.push(n.id());
                                la.push(n.decimicro_lat());
                                lo.push(n.decimicro_lon());
                            }
                            for n in g.nodes() {
                                i.push(n.id());
                                la.push(n.decimicro_lat());
                                lo.push(n.decimicro_lon());
                            }
                        }
                    }
                    (i, la, lo)
                })
                .collect();
            for (i, la, lo) in parts {
                ids.extend_from_slice(&i);
                lats.extend_from_slice(&la);
                lons.extend_from_slice(&lo);
            }
        }
        assert!(ids.windows(2).all(|w| w[0] < w[1]), "{}: node ids not increasing", pbf.display());
        NodeTable::Mem { id: ids, lat: lats, lon: lons }
    }

    fn get(&self, id: i64) -> Option<(i32, i32)> {
        match self {
            NodeTable::Mem { id: ids, lat, lon } => ids.binary_search(&id).ok().map(|i| (lat[i], lon[i])),
            NodeTable::Dense(m) => {
                let at = usize::try_from(id).ok()?.checked_mul(8)?;
                let b = m.get(at..at + 8)?;
                let x = i32::from_le_bytes(b[..4].try_into().unwrap());
                let y = i32::from_le_bytes(b[4..].try_into().unwrap());
                // osmium's Location::valid(): an empty place (both 2^31-1) is outside the world too
                let ok = (-1_800_000_000..=1_800_000_000).contains(&x) && (-900_000_000..=900_000_000).contains(&y);
                ok.then_some((y, x))
            }
        }
    }
}

fn has(v: &[i64], x: i64) -> bool {
    v.binary_search(&x).is_ok()
}

/// the (id, key) pairs of one id in a sorted pair index
fn pairs_of(p: &[[i64; 2]], id: i64) -> &[[i64; 2]] {
    let lo = p.partition_point(|x| x[0] < id);
    let hi = lo + p[lo..].partition_point(|x| x[0] <= id);
    &p[lo..hi]
}

fn sorted_union(a: &[i64], b: &[i64]) -> Vec<i64> {
    let mut v: Vec<i64> = a.iter().chain(b).copied().collect();
    v.sort_unstable();
    v.dedup();
    v
}

struct Store {
    dir: PathBuf,
    z: u32,
    meta: serde_json::Value,
    gen: i64,
    idx: Vec<Row>,
    ridx: Vec<Row>,
}

impl Store {
    fn open(dir: &Path) -> Store {
        let meta: serde_json::Value =
            serde_json::from_slice(&fs::read(dir.join("store.json")).unwrap_or_else(|e| panic!("{}: {e}", dir.display()))).unwrap();
        let z = meta["z"].as_u64().expect("z") as u32;
        let gens: Vec<i64> = meta["generations"].as_array().expect("generations").iter().map(|g| g["gen"].as_i64().unwrap()).collect();
        let gen = *gens.last().expect("a generation");
        let idx = npy::load_idx(&dir.join(format!("idx-{gen:04}.npy")));
        let rg = gens.iter().copied().filter(|&x| x <= gen && dir.join(format!("relidx-{x:04}.npy")).exists()).max().expect("a relation index");
        let ridx = npy::load_idx(&dir.join(format!("relidx-{rg:04}.npy")));
        Store { dir: dir.to_path_buf(), z, meta, gen, idx, ridx }
    }

    fn row(&self, key: u32) -> Option<Row> {
        find(&self.idx, key as i64)
    }
}

/// the old tiles decoded so far, in the order they were asked for (the working set's copies come in that order)
struct Decoded {
    order: Vec<u32>,
    map: HashMap<u32, Option<Part>>,
}

impl Decoded {
    fn add(&mut self, st: &Store, keys: impl IntoIterator<Item = u32>) {
        let mut seen: std::collections::HashSet<u32> = std::collections::HashSet::new();
        let mut new: Vec<u32> = Vec::new();
        for k in keys {
            if !self.map.contains_key(&k) && seen.insert(k) {
                new.push(k);
            }
        }
        let rows: Vec<Option<Row>> = new.iter().map(|&k| st.row(k)).collect();
        let have: Vec<Row> = rows.iter().flatten().copied().collect();
        let bufs = payloads(&st.dir, "pack", &have);
        let parts: Vec<Part> = bufs.par_iter().map(|b| Part::tile(b)).collect();
        let mut parts = parts.into_iter();
        for (k, r) in new.into_iter().zip(rows) {
            self.order.push(k);
            self.map.insert(k, r.map(|_| parts.next().unwrap()));
        }
    }

    fn parts(&self) -> impl Iterator<Item = &Part> {
        self.order.iter().filter_map(|k| self.map[k].as_ref())
    }
}

/// what the working set is made of, besides the copies out of tiles and blobs
struct Ctx<'a> {
    z: u32,
    diff: &'a osc::Diff,
    bt: &'a NodeTable,
    /// changed nodes inside the region, sorted
    cn: Vec<i64>,
    /// nodes the new versions need: the changed ways' refs and the changed relations' member nodes, sorted
    needed: Vec<i64>,
    /// the diff's share of every working set: its visible nodes among cn and needed, its visible ways among cw, and
    /// every visible relation
    dsub: Part,
}

fn push_node(dst: &mut Part, p: &Part, i: usize) {
    dst.nid.push(p.nid[i]);
    dst.lat.push(p.lat[i]);
    dst.lon.push(p.lon[i]);
    let t = p.tag_of[i];
    if t < 0 {
        dst.tag_of.push(-1);
    } else {
        let t = t as usize;
        dst.tag_of.push(dst.tver.len() as i32);
        dst.tver.push(p.tver[t]);
        dst.tts.push(p.tts[t]);
        dst.ntb.extend_from_slice(&p.ntb[p.n_toff[t]..p.n_toff[t + 1]]);
        dst.n_toff.push(dst.ntb.len());
    }
}

fn push_way(dst: &mut Part, p: &Part, i: usize) {
    dst.wid.push(p.wid[i]);
    dst.wver.push(p.wver[i]);
    dst.wts.push(p.wts[i]);
    dst.wrefs.extend_from_slice(&p.wrefs[p.w_roff[i]..p.w_roff[i + 1]]);
    dst.w_roff.push(dst.wrefs.len());
    dst.wtb.extend_from_slice(&p.wtb[p.w_toff[i]..p.w_toff[i + 1]]);
    dst.w_toff.push(dst.wtb.len());
}

fn push_rel(dst: &mut Part, p: &Part, i: usize) {
    dst.rid.push(p.rid[i]);
    dst.rver.push(p.rver[i]);
    dst.rts.push(p.rts[i]);
    for m in p.r_moff[i]..p.r_moff[i + 1] {
        dst.rmt.push(p.rmt[m]);
        dst.rmref.push(p.rmref[m]);
        dst.rrl.push(p.rrl[m]);
        dst.rroles.extend_from_slice(&p.rroles[p.r_rloff[m]..p.r_rloff[m + 1]]);
        dst.r_rloff.push(dst.rroles.len());
    }
    dst.r_moff.push(dst.rmt.len());
    dst.rtb.extend_from_slice(&p.rtb[p.r_toff[i]..p.r_toff[i + 1]]);
    dst.r_toff.push(dst.rtb.len());
}

/// the diff's share of every working set (see Ctx::dsub)
fn diff_share(d: &osc::Diff, cn: &[i64], cw: &[i64], needed: &[i64]) -> Part {
    let p = &d.part;
    let mut s = Part::empty();
    for i in 0..p.nid.len() {
        if has(cn, p.nid[i]) || has(needed, p.nid[i]) {
            push_node(&mut s, p, i);
        }
    }
    for i in 0..p.wid.len() {
        if has(cw, p.wid[i]) {
            push_way(&mut s, p, i);
        }
    }
    for i in 0..p.rid.len() {
        push_rel(&mut s, p, i);
    }
    s
}

/// copies taken out of tiles as they pass, one per id (and a node's tagged copy after an untagged one)
struct Capture {
    part: Part,
    nodes: HashSet<i64>,
    tagged: HashSet<i64>,
    ways: HashSet<i64>,
    rels: HashSet<i64>,
}

impl Capture {
    fn new() -> Capture {
        Capture { part: Part::empty(), nodes: HashSet::new(), tagged: HashSet::new(), ways: HashSet::new(), rels: HashSet::new() }
    }

    fn node(&mut self, p: &Part, i: usize) {
        let id = p.nid[i];
        let fresh = if p.tag_of[i] >= 0 { self.tagged.insert(id) } else { !self.tagged.contains(&id) && self.nodes.insert(id) };
        if fresh {
            push_node(&mut self.part, p, i);
        }
    }

    /// a way and the copies of its nodes the tile holds (a tile holds every node of its ways)
    fn way(&mut self, p: &Part, w: usize) {
        if self.ways.insert(p.wid[w]) {
            push_way(&mut self.part, p, w);
            for &r in &p.wrefs[p.w_roff[w]..p.w_roff[w + 1]] {
                if let Ok(j) = p.nid.binary_search(&r) {
                    self.node(p, j);
                }
            }
        }
    }

    fn rel(&mut self, p: &Part, r: usize) {
        if self.rels.insert(p.rid[r]) {
            push_rel(&mut self.part, p, r);
        }
    }
}

/// these tiles decoded a batch at a time and handed over in order, none kept
fn each_tile(st: &Store, keys: &[u32], mut f: impl FnMut(u32, &Part)) -> usize {
    let mut n = 0;
    for chunk in keys.chunks(2048) {
        let rows: Vec<Row> = chunk.iter().filter_map(|&k| st.row(k)).collect();
        let bufs = payloads(&st.dir, "pack", &rows);
        let parts: Vec<Part> = bufs.par_iter().map(|b| Part::tile(b)).collect();
        for (r, p) in rows.iter().zip(&parts) {
            f(r.0 as u32, p);
        }
        n += rows.len();
    }
    n
}

/// the needed nodes no copy holds (an untagged node no way held): a place from the store before
fn orphans(ctx: &Ctx, srcs: &[&Part]) -> Part {
    let mut held: Vec<i64> = srcs.iter().flat_map(|p| p.nid.iter().copied()).collect();
    held.par_sort_unstable();
    held.dedup();
    let mut o = Part::empty();
    for &id in &ctx.needed {
        if !has(&held, id) {
            if let Some((lat, lon)) = ctx.bt.get(id) {
                o.nid.push(id);
                o.lat.push(lat);
                o.lon.push(lon);
                o.tag_of.push(-1);
            }
        }
    }
    o
}

/// tilestore.py update's working(): the copies of every object in these sources (one per id, a tagged node's copy
/// first; the prototype's needed nodes no tile held come in as a source of their own, see orphans), less what the
/// diff touches, and the diff's share over them
fn working(ctx: &Ctx, srcs: &[&Part]) -> Clip {
    let d = &ctx.diff;
    let ds = &ctx.dsub;
    let sd = srcs.len() as u32;
    let src = |s: u32| if s == sd { ds } else { srcs[s as usize] };
    // nodes: (id, untagged, source, row), the first copy of each id with a tagged one first
    let mut cand: Vec<(i64, bool, u32, u32)> = Vec::new();
    for (s, p) in srcs.iter().enumerate() {
        cand.extend(p.nid.iter().enumerate().map(|(i, &id)| (id, p.tag_of[i] < 0, s as u32, i as u32)));
    }
    cand.par_sort_unstable();
    cand.dedup_by_key(|c| c.0);
    let mut nodes: Vec<(i64, u32, u32)> = cand.iter().filter(|c| !has(&d.n_all, c.0)).map(|c| (c.0, c.2, c.3)).collect();
    drop(cand);
    nodes.extend(ds.nid.iter().enumerate().map(|(i, &id)| (id, sd, i as u32)));
    nodes.par_sort_unstable();
    assert!(nodes.windows(2).all(|w| w[0].0 < w[1].0), "a node twice in the working set");
    // ways: the first copy of each id, the changed ones from the diff
    let mut wc: Vec<(i64, u32, u32)> = Vec::new();
    for (s, p) in srcs.iter().enumerate() {
        wc.extend(p.wid.iter().enumerate().map(|(i, &id)| (id, s as u32, i as u32)));
    }
    wc.par_sort_unstable();
    wc.dedup_by_key(|c| c.0);
    wc.retain(|c| !has(&d.w_all, c.0));
    wc.extend(ds.wid.iter().enumerate().map(|(i, &id)| (id, sd, i as u32)));
    wc.par_sort_unstable();
    assert!(wc.windows(2).all(|w| w[0].0 < w[1].0), "a way twice in the working set");
    // relations: the tiles' (blobs hold none), every visible one of the diff
    let mut rc: Vec<(i64, u32, u32)> = Vec::new();
    for (s, p) in srcs.iter().enumerate() {
        rc.extend(p.rid.iter().enumerate().map(|(i, &id)| (id, s as u32, i as u32)));
    }
    rc.par_sort_unstable();
    rc.dedup_by_key(|c| c.0);
    rc.retain(|c| !has(&d.r_all, c.0));
    rc.extend(ds.rid.iter().enumerate().map(|(i, &id)| (id, sd, i as u32)));
    rc.par_sort_unstable();
    assert!(rc.windows(2).all(|w| w[0].0 < w[1].0), "a relation twice in the working set");

    let mut c = Clip::new();
    for &(id, s, i) in &nodes {
        let (p, i) = (src(s), i as usize);
        c.nid.push(id);
        c.lat7.push(p.lat[i]);
        c.lon7.push(p.lon[i]);
        let t = p.tag_of[i];
        if t >= 0 {
            let t = t as usize;
            c.tn_row.push(c.nid.len() as u32 - 1);
            c.tn_ver.push(p.tver[t]);
            c.tn_ts.push(p.tts[t]);
            c.tn_tags.extend_from_slice(&p.ntb[p.n_toff[t]..p.n_toff[t + 1]]);
            c.tn_toff.push(c.tn_tags.len() as u64);
        }
    }
    for &(id, s, i) in &wc {
        let (p, i) = (src(s), i as usize);
        c.wid.push(id);
        c.w_ver.push(p.wver[i]);
        c.w_ts.push(p.wts[i]);
        c.wref_ids.extend_from_slice(&p.wrefs[p.w_roff[i]..p.w_roff[i + 1]]);
        c.woffs.push(c.wref_ids.len() as u64);
        c.w_tags.extend_from_slice(&p.wtb[p.w_toff[i]..p.w_toff[i + 1]]);
        c.w_toff.push(c.w_tags.len() as u64);
    }
    for &(id, s, i) in &rc {
        let (p, i) = (src(s), i as usize);
        c.rid.push(id);
        c.r_ver.push(p.rver[i]);
        c.r_ts.push(p.rts[i]);
        for m in p.r_moff[i]..p.r_moff[i + 1] {
            c.mtype.push(p.rmt[m]);
            c.mref.push(p.rmref[m]);
            c.roles.extend_from_slice(&p.rroles[p.r_rloff[m]..p.r_rloff[m + 1]]);
            c.r_roff.push(c.roles.len() as u64);
        }
        c.roffs.push(c.mref.len() as u64);
        c.r_tags.extend_from_slice(&p.rtb[p.r_toff[i]..p.r_toff[i + 1]]);
        c.r_toff.push(c.r_tags.len() as u64);
    }
    assert!(c.nid.len() < NONE as usize, "node rows are 32 bits here");
    c.keep_relations();
    c.place(ctx.z);
    c
}

/// a kept relation's blob for the relation store: its member ways in the working set, whole, and their nodes' places
fn rel_blob(m: &Clip, r: usize) -> Vec<u8> {
    let mut wi: Vec<u32> = Vec::new();
    for j in m.roffs[r] as usize..m.roffs[r + 1] as usize {
        if m.mtype[j] == 1 {
            if let Ok(w) = m.wid.binary_search(&m.mref[j]) {
                wi.push(w as u32);
            }
        }
    }
    wi.sort_unstable();
    wi.dedup();
    let mut u: Vec<u32> = Vec::new();
    for &w in &wi {
        let w = w as usize;
        u.extend(m.wrefs[m.woffs[w] as usize..m.woffs[w + 1] as usize].iter().filter(|&&x| x != NONE));
    }
    u.sort_unstable();
    u.dedup();
    let mut cols: Vec<Col> = Vec::with_capacity(10);
    m.way_cols(&wi, &mut cols);
    m.place_cols(&u, &mut cols);
    pack_cols(&cols)
}

/// the new generation's pack: reached tiles written when they changed
struct TileWriter {
    f: BufWriter<File>,
    gen: i64,
    off: i64,
    entries: Vec<Row>,
    unchanged: Vec<u32>,
    changed: BTreeSet<u32>,
}

impl TileWriter {
    /// these tiles (sorted) rebuilt by `payload`: an empty one is dropped, one equal to its old payload keeps its entry
    fn put(&mut self, st: &Store, keys: &[u32], payload: impl Fn(u32) -> (Vec<u8>, [usize; 3]) + Sync) {
        for chunk in keys.chunks(1024) {
            let olds: Vec<Option<Row>> = chunk.iter().map(|&k| st.row(k)).collect();
            let have: Vec<Row> = olds.iter().flatten().copied().collect();
            let mut obufs = payloads(&st.dir, "pack", &have).into_iter();
            let obufs: Vec<Option<Vec<u8>>> = olds.iter().map(|o| o.map(|_| obufs.next().unwrap())).collect();
            let res: Vec<Option<(Vec<u8>, bool)>> = chunk
                .par_iter()
                .zip(obufs.par_iter())
                .map(|(&k, old)| {
                    let (buf, counts) = payload(k);
                    if counts == [0, 0, 0] {
                        return None;
                    }
                    let same = old.as_ref().is_some_and(|o| {
                        zstd::stream::decode_all(&o[..]).unwrap() == zstd::stream::decode_all(&buf[..]).unwrap()
                    });
                    Some((buf, same))
                })
                .collect();
            for (&k, r) in chunk.iter().zip(res) {
                match r {
                    None => {
                        self.changed.insert(k); // the tile is empty now
                    }
                    Some((_, true)) => self.unchanged.push(k), // reached, but the same: the old entry stays
                    Some((buf, false)) => {
                        self.changed.insert(k);
                        self.f.write_all(&buf).unwrap();
                        self.entries.push((k as i64, self.gen as i32, self.off, buf.len() as i32));
                        self.off += buf.len() as i64;
                    }
                }
            }
        }
    }
}

/// the tile keys under a box in degrees (tiles.py box_tiles)
fn box_tiles(s: f64, w: f64, n: f64, e: f64, z: u32, out: &mut Vec<u32>) {
    let nt = (1u64 << z) as f64;
    let (x0, y1) = frac_deg(s, w, nt);
    let (x1, y0) = frac_deg(n, e, nt);
    for y in y0.floor() as i64..=y1.floor() as i64 {
        for x in x0.floor() as i64..=x1.floor() as i64 {
            out.push(key_of(x, y, z));
        }
    }
}

/// tilestore.py region_of: the tiles the store holds and those under each part of the clip's polygon (its outer
/// ring's box); without a polygon, the tiles near those it holds. Sorted.
fn region_of(st: &Store, polygon: Option<&Path>) -> Vec<u32> {
    let z = st.z;
    let mut out: Vec<u32> = st.idx.iter().map(|r| r.0 as u32).collect();
    match polygon {
        None => {
            let r = 1i64 << z.saturating_sub(14);
            let m = (1i64 << z) - 1;
            let held = out.clone();
            for k in held {
                let (x, y) = ((k >> z) as i64, (k as i64) & m);
                for dx in -r..=r {
                    for dy in -r..=r {
                        out.push(key_of(x + dx, y + dy, z));
                    }
                }
            }
        }
        Some(p) => {
            let g: serde_json::Value = serde_json::from_slice(&fs::read(p).unwrap_or_else(|e| panic!("{}: {e}", p.display()))).unwrap();
            for f in g["features"].as_array().expect("features") {
                let geo = &f["geometry"];
                let polys: Vec<&serde_json::Value> = if geo["type"] == "MultiPolygon" {
                    geo["coordinates"].as_array().unwrap().iter().collect()
                } else {
                    vec![&geo["coordinates"]]
                };
                for part in polys {
                    let ring = part[0].as_array().expect("a ring");
                    let (mut s, mut w, mut n, mut e) = (f64::MAX, f64::MAX, f64::MIN, f64::MIN);
                    for pt in ring {
                        let (lon, lat) = (pt[0].as_f64().unwrap(), pt[1].as_f64().unwrap());
                        s = s.min(lat);
                        n = n.max(lat);
                        w = w.min(lon);
                        e = e.max(lon);
                    }
                    box_tiles(s, w, n, e, z, &mut out);
                }
            }
        }
    }
    out.par_sort_unstable();
    out.dedup();
    out
}

fn key7(lat: i32, lon: i32, z: u32) -> u32 {
    let (fx, fy) = frac_xy(lat, lon, (1u64 << z) as f64);
    key_of(fx.floor() as i64, fy.floor() as i64, z)
}

fn pair_path(dir: &Path, name: &str, gen: i64) -> PathBuf {
    dir.join(format!("{name}-{gen:04}.npy"))
}

pub fn update(a: &Args) {
    let t0 = Instant::now();
    let st = Store::open(&a.store);
    let (z, g) = (st.z, st.gen);
    let ng = g + 1;
    assert!(a.group_z.is_none_or(|x| x <= z), "a group is no finer than a tile");
    assert!(!(a.group_z.is_some() && a.group_mib.is_some()), "groups by cell or by size, not both");
    let grouped = a.group_z.is_some() || a.group_mib.is_some();
    let wtm = npy::PairMap::open(&pair_path(&st.dir, "wtiles", g));
    let rtm = npy::PairMap::open(&pair_path(&st.dir, "rtiles", g));
    let (wt, rt) = (wtm.rows(), rtm.rows());
    assert!(!(a.world && a.polygon.is_some()), "a world store has no polygon");
    // None: the whole world
    let region = (!a.world).then(|| region_of(&st, a.polygon.as_deref()));
    let in_region = |k: Option<u32>| k.is_some_and(|k| region.as_ref().is_none_or(|r| r.binary_search(&k).is_ok()));
    let diff = osc::read(&a.diff);
    let d = &diff;
    let t_diff = t0.elapsed().as_secs_f64();
    let t = Instant::now();
    let bt = if a.before_loc { NodeTable::dense(&a.before) } else { NodeTable::from_pbf(&a.before) };
    log(&format!("node places before the day: {} nodes (or ids) in {:.1} s", bt.len(), t.elapsed().as_secs_f64()));
    let t1 = Instant::now();
    let dn_get = |id: i64| d.part.nid.binary_search(&id).ok().map(|i| (d.part.lat[i], d.part.lon[i]));
    // node places after the day: the diff's (none for a deleted node), else the store before
    let after_pos = |id: i64| if has(&d.n_all, id) { dn_get(id) } else { bt.get(id) };
    let k7 = |p: Option<(i32, i32)>| p.map(|(la, lo)| key7(la, lo, z));
    // the single working set keeps every tile it decodes; the grouped update keeps copies out of them (Capture)
    let mut dec = Decoded { order: Vec::new(), map: HashMap::new() };
    let mut decoded_n = 0usize;

    // changed nodes: old and new home tiles, inside the store's region
    let mut cn = Vec::new();
    let mut okey = Vec::new();
    let mut nkey = Vec::new();
    for &id in &d.n_all {
        let (o, n) = (k7(bt.get(id)), k7(dn_get(id)));
        if in_region(o) || in_region(n) {
            cn.push(id);
            okey.push(o);
            nkey.push(n);
        }
    }
    // ways holding a changed node: in the node's old home tile
    let homes: Vec<u32> = okey.iter().flatten().copied().collect::<BTreeSet<u32>>().into_iter().collect();
    let mut parents: BTreeSet<i64> = BTreeSet::new();
    let find_parents = |p: &Part, parents: &mut BTreeSet<i64>| {
        for w in 0..p.wid.len() {
            if p.wrefs[p.w_roff[w]..p.w_roff[w + 1]].iter().any(|&r| has(&cn, r)) {
                parents.insert(p.wid[w]);
            }
        }
    };
    if !grouped {
        dec.add(&st, homes.iter().copied());
        for k in &homes {
            if let Some(p) = &dec.map[k] {
                find_parents(p, &mut parents);
            }
        }
    } else {
        decoded_n += each_tile(&st, &homes, |_, p| find_parents(p, &mut parents));
    }
    // changed ways reaching the region: old tiles from the index, new ones from their refs' places after the day
    let mut cw: Vec<i64> = d.w_all.iter().copied().filter(|&id| !pairs_of(wt, id).is_empty()).collect();
    let dp = &d.part;
    for w in 0..dp.wid.len() {
        if dp.wrefs[dp.w_roff[w]..dp.w_roff[w + 1]].iter().any(|&r| in_region(k7(after_pos(r)))) {
            cw.push(dp.wid[w]);
        }
    }
    cw.sort_unstable();
    cw.dedup();
    let parents: Vec<i64> = parents.into_iter().filter(|w| !has(&cw, *w)).collect();
    let n_changed_ways = cw.len();
    let n_parents = parents.len();
    let moved = sorted_union(&cw, &parents);
    // one old tile of each (it holds the old version, its nodes, and every relation it is a member of), and the old
    // home tiles of the nodes of the new versions (their tagged attributes)
    let old_w: Vec<&[[i64; 2]]> = moved.iter().map(|&id| pairs_of(wt, id)).collect();
    let old_mins: Vec<u32> = old_w.iter().filter(|s| !s.is_empty()).map(|s| s.iter().map(|p| p[1] as u32).min().unwrap()).collect();
    let mut new_refs: Vec<i64> = Vec::new();
    for w in 0..dp.wid.len() {
        if has(&cw, dp.wid[w]) {
            new_refs.extend_from_slice(&dp.wrefs[dp.w_roff[w]..dp.w_roff[w + 1]]);
        }
    }
    new_refs.sort_unstable();
    new_refs.dedup();
    // the changed relations' member nodes too: an untagged one no tile held must still place its relation
    let mut rel_nodes: Vec<i64> = (0..dp.rmt.len()).filter(|&m| dp.rmt[m] == 0).map(|m| dp.rmref[m]).collect();
    rel_nodes.sort_unstable();
    rel_nodes.dedup();
    rel_nodes.retain(|&id| in_region(k7(after_pos(id))));
    let needed = sorted_union(&new_refs, &rel_nodes);
    let before_keys: Vec<u32> = new_refs.iter().filter_map(|&id| k7(bt.get(id))).collect::<BTreeSet<u32>>().into_iter().collect();
    let dsub = diff_share(d, &cn, &cw, &needed);
    let ctx = Ctx { z, diff: d, bt: &bt, cn, needed, dsub };

    // the working set so far, to find the new tiles of the moved ways and the relations they reach. Grouped: copies of
    // what that working set would hold and the day can need: the moved ways (with their nodes), the relations they or
    // a changed node reach, the needed nodes, and the changed relations' member ways that did not move (whether the
    // working set holds them decides the relation store's blobs)
    let mut carry = Capture::new();
    let mut needtab = Capture::new();
    let mut capc = Capture::new();
    let mut dr_ways: Vec<i64> = (0..dp.rmt.len()).filter(|&m| dp.rmt[m] == 1).map(|m| dp.rmref[m]).filter(|w| !has(&moved, *w)).collect();
    dr_ways.sort_unstable();
    dr_ways.dedup();
    let hit = |p: &Part, r: usize| {
        (p.r_moff[r]..p.r_moff[r + 1]).any(|m| (p.rmt[m] == 1 && has(&moved, p.rmref[m])) || (p.rmt[m] == 0 && has(&ctx.cn, p.rmref[m])))
    };
    let grab_dr_ways = |p: &Part, capc: &mut Capture| {
        for w in 0..p.wid.len() {
            if has(&dr_ways, p.wid[w]) {
                capc.way(p, w);
            }
        }
    };
    let orph;
    let m1 = if !grouped {
        dec.add(&st, old_mins.iter().copied());
        dec.add(&st, before_keys.iter().copied());
        let mut srcs: Vec<&Part> = dec.parts().collect();
        orph = orphans(&ctx, &srcs);
        srcs.push(&orph);
        working(&ctx, &srcs)
    } else {
        let mut seen: HashSet<u32> = HashSet::new();
        let ta: Vec<u32> = homes.iter().chain(&old_mins).chain(&before_keys).copied().filter(|&k| seen.insert(k)).collect();
        decoded_n += each_tile(&st, &ta, |_, p| {
            for w in 0..p.wid.len() {
                if has(&moved, p.wid[w]) {
                    carry.way(p, w);
                }
            }
            grab_dr_ways(p, &mut capc);
            for i in 0..p.nid.len() {
                if has(&ctx.needed, p.nid[i]) {
                    needtab.node(p, i);
                }
            }
            for r in 0..p.rid.len() {
                if !has(&d.r_all, p.rid[r]) && hit(p, r) {
                    carry.rel(p, r);
                }
            }
        });
        // every needed node those tiles hold is in needtab, so these are the prototype's orphans of this working set
        orph = orphans(&ctx, &[&needtab.part]);
        log(&format!(
            "carried: {} ways, {} relations, {} nodes; {} needed nodes held, {} from the store before",
            carry.part.wid.len(),
            carry.part.rid.len(),
            carry.part.nid.len(),
            needtab.part.nid.len(),
            orph.nid.len()
        ));
        working(&ctx, &[&carry.part, &needtab.part, &orph])
    };
    let t_find = t1.elapsed().as_secs_f64();
    let t2 = Instant::now();
    let (wt_off, wt_key) = tiles::way_tiles(&m1, z);
    let new_w: HashMap<i64, &[u32]> = moved
        .iter()
        .map(|&id| {
            let s: &[u32] = match m1.wid.binary_search(&id) {
                Ok(r) => &wt_key[wt_off[r] as usize..wt_off[r + 1] as usize],
                Err(_) => &[],
            };
            (id, s)
        })
        .collect();
    // relations reached: changed ones, and those with a moved way or a changed node as member
    let mut ar: BTreeSet<i64> = BTreeSet::new();
    for r in 0..m1.rid.len() {
        let hit = (m1.roffs[r] as usize..m1.roffs[r + 1] as usize)
            .any(|m| (m1.mtype[m] == 1 && has(&moved, m1.mref[m])) || (m1.mtype[m] == 0 && has(&ctx.cn, m1.mref[m])));
        if hit {
            ar.insert(m1.rid[r]);
        }
    }
    for &rid in &d.r_all {
        if !pairs_of(rt, rid).is_empty() {
            ar.insert(rid);
        }
    }
    // a changed relation reaching the region: a member way with tiles, or a member node placed there
    for r in 0..dp.rid.len() {
        let hit = (dp.r_moff[r]..dp.r_moff[r + 1]).any(|m| match dp.rmt[m] {
            1 => has(&moved, dp.rmref[m]) || !pairs_of(wt, dp.rmref[m]).is_empty(),
            0 => in_region(k7(after_pos(dp.rmref[m]))),
            _ => false,
        });
        if hit {
            ar.insert(dp.rid[r]);
        }
    }
    let ar: Vec<i64> = ar.into_iter().collect();
    // the tiles reached, and why: a changed node's home, old and new; a moved way's tiles, old and new; a changed
    // relation's tiles, old and new (its record is in all of them). An unchanged relation's tiles change only where a
    // moved member way came or went, which are reached already.
    let why_node: BTreeSet<u32> = okey.iter().chain(nkey.iter()).flatten().copied().collect();
    let mut why_way: BTreeSet<u32> = BTreeSet::new();
    for s in &old_w {
        why_way.extend(s.iter().map(|p| p[1] as u32));
    }
    for s in new_w.values() {
        why_way.extend(s.iter().copied());
    }
    let mut why_rel: BTreeSet<u32> = BTreeSet::new();
    for &rid in ar.iter().filter(|&&r| has(&d.r_all, r)) {
        why_rel.extend(pairs_of(rt, rid).iter().map(|p| p[1] as u32));
    }
    let mut member_nodes: Vec<i64> = Vec::new();
    for &rid in ar.iter().filter(|&&r| has(&dp.rid, r)) {
        let Ok(j) = m1.rid.binary_search(&rid) else { continue };
        if !m1.r_kept[j] {
            continue; // a relation the app ignores is in no tile
        }
        for m in m1.roffs[j] as usize..m1.roffs[j + 1] as usize {
            let r = m1.mref[m];
            match m1.mtype[m] {
                1 => {
                    if let Some(s) = new_w.get(&r) {
                        why_rel.extend(s.iter().copied());
                    }
                    if !has(&moved, r) {
                        why_rel.extend(pairs_of(wt, r).iter().map(|p| p[1] as u32));
                    }
                }
                0 => member_nodes.push(r),
                _ => {}
            }
        }
    }
    member_nodes.sort_unstable();
    member_nodes.dedup();
    why_rel.extend(member_nodes.iter().filter_map(|&id| k7(after_pos(id))));
    let reach: Vec<u32> = why_node
        .iter()
        .chain(why_way.iter())
        .chain(why_rel.iter())
        .copied()
        .collect::<BTreeSet<u32>>()
        .into_iter()
        .filter(|&k| in_region(Some(k)))
        .collect();
    // the relation store's old blobs of the relations reached: their far member ways
    let rrows: Vec<Row> = ar.iter().filter_map(|&rid| find(&st.ridx, rid)).collect();
    let blobs: Vec<Part> = payloads(&st.dir, "rel", &rrows).par_iter().map(|b| Part::relation_blob(b)).collect();
    let t_reach = t2.elapsed().as_secs_f64();

    // rebuild the reached tiles into the new generation
    let t3 = Instant::now();
    let dir = &st.dir;
    let mut tw = TileWriter {
        f: BufWriter::with_capacity(1 << 22, File::create(dir.join(format!("pack-{ng:04}.bin"))).unwrap()),
        gen: ng,
        off: 0,
        entries: Vec::new(),
        unchanged: Vec::new(),
        changed: BTreeSet::new(),
    };
    let mut wadd: Vec<[i64; 2]> = Vec::new();
    let mut radd: Vec<[i64; 2]> = Vec::new();
    // per reached relation the app keeps, its new blob; and the ids of those
    let rel_out: Vec<(i64, Vec<u8>)>;
    let mut groups = 1usize;
    if !grouped {
        drop(m1);
        dec.add(&st, reach.iter().copied());
        let mut srcs: Vec<&Part> = dec.parts().chain(blobs.iter()).collect();
        let o = orphans(&ctx, &srcs);
        srcs.push(&o);
        let m = working(&ctx, &srcs);
        let p = pairs::build(&m, z);
        log(&format!("tile pairs: {} node, {} way, {} relation copies", p.node.len(), p.way.len(), p.rel.len()));
        tw.put(&st, &reach, |k| p.payload(&m, k));
        for &id in &moved {
            if let Ok(r) = m.wid.binary_search(&id) {
                wadd.extend(p.wt_key[p.wt_off[r] as usize..p.wt_off[r + 1] as usize].iter().map(|&k| [id, k as i64]));
            }
        }
        for &rid in &ar {
            if let Ok(r) = m.rid.binary_search(&rid) {
                radd.extend(p.rel_keys[r].iter().filter(|k| reach.binary_search(k).is_ok()).map(|&k| [rid, k as i64]));
            }
        }
        let kept: Vec<usize> = ar.iter().filter_map(|&rid| m.rid.binary_search(&rid).ok()).filter(|&r| m.r_kept[r]).collect();
        rel_out = kept.par_iter().map(|&r| (m.rid[r], rel_blob(&m, r))).collect();
        decoded_n = dec.order.len();
    } else {
        // the reached tiles in groups, in the order of their cells at zoom cz: a whole cell each with --group-z; with
        // --group-mib, cells run together until the old payloads reach the budget. Each group's working set is its own
        // old tiles and the carried copies, which hold every object that lands in its tiles (DESIGN.md); any partition
        // gives the same store
        let cz = a.group_z.unwrap_or(z.min(8));
        let (sh, mask) = (z - cz, (1u32 << z) - 1);
        let cell = |k: u32| ((k >> z) >> sh) << cz | ((k & mask) >> sh);
        let mut by_cell: Vec<(u32, u32)> = reach.iter().map(|&k| (cell(k), k)).collect();
        by_cell.sort_unstable();
        let budget = a.group_mib.map(|m| m << 20);
        let mut glist: Vec<Vec<u32>> = Vec::new();
        let (mut cur, mut acc, mut cur_cell): (Vec<u32>, u64, Option<u32>) = (Vec::new(), 0, None);
        for &(c, k) in &by_cell {
            let close = match budget {
                None => cur_cell.is_some_and(|x| x != c),
                Some(b) => acc >= b,
            };
            if close {
                glist.push(std::mem::take(&mut cur));
                acc = 0;
            }
            cur.push(k);
            acc += st.row(k).map_or(0, |r| r.3 as u64) + 1024;
            cur_cell = Some(c);
        }
        if !cur.is_empty() {
            glist.push(cur);
        }
        groups = glist.len();
        for mut keys in glist {
            keys.sort_unstable();
            let rows: Vec<Row> = keys.iter().filter_map(|&k| st.row(k)).collect();
            let parts: Vec<Part> = payloads(dir, "pack", &rows).par_iter().map(|b| Part::tile(b)).collect();
            decoded_n += parts.len();
            for p in &parts {
                grab_dr_ways(p, &mut capc);
            }
            let srcs: Vec<&Part> = parts.iter().chain([&carry.part, &needtab.part, &orph]).collect();
            let m = working(&ctx, &srcs);
            let p = pairs::build(&m, z);
            tw.put(&st, &keys, |k| p.payload(&m, k));
            for &rid in &ar {
                if let Ok(r) = m.rid.binary_search(&rid) {
                    radd.extend(p.rel_keys[r].iter().filter(|k| keys.binary_search(k).is_ok()).map(|&k| [rid, k as i64]));
                }
            }
        }
        for &id in &moved {
            if let Ok(r) = m1.wid.binary_search(&id) {
                wadd.extend(wt_key[wt_off[r] as usize..wt_off[r + 1] as usize].iter().map(|&k| [id, k as i64]));
            }
        }
        // the relation store: the reached relations from their old blobs and the carried copies
        let mut srcs: Vec<&Part> = blobs.iter().collect();
        srcs.extend([&carry.part, &capc.part, &needtab.part, &orph]);
        let mc = working(&ctx, &srcs);
        let kept: Vec<usize> = ar.iter().filter_map(|&rid| mc.rid.binary_search(&rid).ok()).filter(|&r| mc.r_kept[r]).collect();
        rel_out = kept.par_iter().map(|&r| (mc.rid[r], rel_blob(&mc, r))).collect();
        log(&format!("{groups} groups (cells of zoom {cz}, budget {:?} MiB); {} member ways of changed relations carried for the relation store", a.group_mib, capc.part.wid.len()));
    }
    tw.f.flush().unwrap();
    let t_rule = t3.elapsed().as_secs_f64();

    let t4 = Instant::now();
    let TileWriter { entries: new_entries, mut unchanged, changed, off, .. } = tw;
    unchanged.sort_unstable(); // grouped, the tiles come a cell at a time
    let replaced: BTreeSet<u32> = reach.iter().copied().filter(|k| unchanged.binary_search(k).is_err()).collect();
    let mut idx: Vec<Row> = st.idx.iter().copied().filter(|r| !replaced.contains(&(r.0 as u32))).collect();
    idx.extend_from_slice(&new_entries);
    idx.par_sort_unstable_by_key(|r| r.0);
    npy::save_idx(&dir.join(format!("idx-{ng:04}.npy")), &idx);
    // the way and relation tile indexes
    let gone_w = sorted_union(&moved, &d.w_all);
    wadd.sort_unstable();
    npy::merge_pairs(&pair_path(dir, "wtiles", ng), wt, |q| !has(&gone_w, q[0]), &wadd);
    // a reached relation's tiles: the working set's inside the day's reach, the old ones outside it (a far member node
    // or way is not in the working set, and a tile not reached did not change)
    let kept_ar: Vec<i64> = rel_out.iter().map(|r| r.0).collect();
    let gone_r = sorted_union(&ar, &d.r_all);
    radd.sort_unstable();
    npy::merge_pairs(&pair_path(dir, "rtiles", ng), rt, |q| {
        !has(&gone_r, q[0]) || (has(&kept_ar, q[0]) && reach.binary_search(&(q[1] as u32)).is_err())
    }, &radd);
    // the relation store: the reached relations' blobs again
    let mut rentries: Vec<Row> = Vec::new();
    let mut roff: i64 = 0;
    {
        let mut f = BufWriter::with_capacity(1 << 22, File::create(dir.join(format!("rel-{ng:04}.bin"))).unwrap());
        for (rid, b) in &rel_out {
            f.write_all(b).unwrap();
            rentries.push((*rid, ng as i32, roff, b.len() as i32));
            roff += b.len() as i64;
        }
        f.flush().unwrap();
    }
    let mut ridx: Vec<Row> = st.ridx.iter().copied().filter(|r| !has(&gone_r, r.0)).collect();
    ridx.extend_from_slice(&rentries);
    ridx.par_sort_unstable_by_key(|r| r.0);
    npy::save_idx(&dir.join(format!("relidx-{ng:04}.npy")), &ridx);
    let t_write = t4.elapsed().as_secs_f64();

    // what it did, in the prototype's words
    let reach_set: BTreeSet<u32> = reach.iter().copied().collect();
    let old_len = |k: u32| st.row(k).map_or(0i64, |r| r.3 as i64);
    let by = |s: &BTreeSet<u32>| {
        let ch: Vec<u32> = s.intersection(&changed).copied().collect();
        serde_json::json!({"tiles": s.intersection(&reach_set).count(), "changed": ch.len(),
                           "changedBytes": ch.iter().map(|&k| old_len(k)).sum::<i64>()})
    };
    let new_keys: BTreeSet<u32> = new_entries.iter().map(|r| r.0 as u32).collect();
    let tiles_new = new_entries.iter().filter(|r| st.row(r.0 as u32).is_none()).count();
    let tiles_dropped =
        reach.iter().filter(|&&k| st.row(k).is_some() && !new_keys.contains(&k) && unchanged.binary_search(&k).is_err()).count();
    let r1 = |x: f64| (x * 10.0).round() / 10.0;
    let stats = serde_json::json!({
        "changedNodes": ctx.cn.len(), "changedWays": n_changed_ways, "parentWays": n_parents, "relations": ar.len(),
        "reachedBy": {"node": by(&why_node), "way": by(&why_way), "relation": by(&why_rel)},
        "tilesUnchanged": unchanged.len(), "gen": ng, "day": a.day, "diff": a.diff.to_string_lossy(),
        "by": "tilestore update (Rust)", "before": a.before.to_string_lossy(),
        "polygon": a.polygon.as_ref().map(|p| p.to_string_lossy().into_owned()), "world": a.world, "prunePairs": a.prune_pairs,
        "groupZ": a.group_z, "groupMiB": a.group_mib, "groups": groups,
        "tilesReached": reach.len(), "tilesWritten": new_entries.len(), "tilesNew": tiles_new, "tilesDropped": tiles_dropped,
        "bytes": off, "relBytes": roff, "relBlobs": rentries.len(), "tilesDecoded": decoded_n,
        "secondsDiff": r1(t_diff), "secondsFind": r1(t_find), "secondsReach": r1(t_reach), "secondsRule": r1(t_rule),
        "secondsWrite": r1(t_write), "seconds": r1(t0.elapsed().as_secs_f64()),
    });
    let mut meta = st.meta.clone();
    meta["generations"].as_array_mut().unwrap().push(stats.clone());
    // store.json last, whole or not at all: until it names the generation, its files are only leftovers
    let tmp = dir.join("store.json.tmp");
    fs::write(&tmp, serde_json::to_string_pretty(&meta).unwrap()).unwrap();
    fs::rename(&tmp, dir.join("store.json")).unwrap();
    if a.prune_pairs {
        // only the newest pair indexes are read (by the next update); a planet generation's way pairs are 22 GB
        drop((wtm, rtm));
        for name in ["wtiles", "rtiles"] {
            fs::remove_file(pair_path(dir, name, g)).unwrap();
        }
    }
    log(&format!("update to {}: {}", a.day, stats));
}
