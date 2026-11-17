//! The read: the tiles under a set of boxes joined into one PBF for the engine, duplicates dropped, every kept
//! relation's member ways from the relation store (tilestore.py join). The boxes are a cities file's, each padded by
//! the ring as the engine pads (tiles.py padded, box_tiles).

use crate::cols::{offsets, undelta, undelta32, unpack_cols};
use crate::npy;
use crate::pbf;
use crate::tiles::{frac_deg, key_of};
use rayon::prelude::*;
use std::collections::HashMap;
use std::fs::{self, File};
use std::io::{BufWriter, Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};
use std::time::Instant;

const M_LAT: f64 = 111_320.0;

/// the tile keys under the cities' boxes and their ring, sorted
pub fn tiles_of(cities: &Path, base: &Path, ring: f64, z: u32) -> Vec<u32> {
    let nt = (1u64 << z) as f64;
    let c: serde_json::Value = serde_json::from_slice(&fs::read(cities).expect("the cities file")).unwrap();
    let mut keys = Vec::new();
    for city in c["cities"].as_array().expect("cities") {
        let p = base.join(city["boundary"].as_str().expect("boundary"));
        let b: serde_json::Value = serde_json::from_slice(&fs::read(&p).unwrap_or_else(|e| panic!("{}: {e}", p.display()))).unwrap();
        let f = |k: &str| b["bounds"][k].as_f64().expect("bounds");
        let (s, w, n, e) = (f("minlat"), f("minlon"), f("maxlat"), f("maxlon"));
        let d_lat = ring / M_LAT;
        let d_lon = ring / (M_LAT * s.abs().max(n.abs()).min(85.0).to_radians().cos());
        let (s, w, n, e) = (s - d_lat, w - d_lon, n + d_lat, e + d_lon);
        let (x0, y1) = frac_deg(s, w, nt);
        let (x1, y0) = frac_deg(n, e, nt);
        for x in x0.floor() as i64..=x1.floor() as i64 {
            for y in y0.floor() as i64..=y1.floor() as i64 {
                keys.push(key_of(x, y, z));
            }
        }
    }
    keys.sort_unstable();
    keys.dedup();
    keys
}

/// "2026-11-12T00:00:00Z" as seconds since 1970
pub fn stamp_seconds(s: &str) -> i64 {
    let n = |a: usize, b: usize| s[a..b].parse::<i64>().unwrap_or_else(|_| panic!("a stamp like 2026-11-12T00:00:00Z, not {s}"));
    assert!(s.len() == 20 && s.ends_with('Z'), "a stamp like 2026-11-12T00:00:00Z, not {s}");
    let (y, m, d) = (n(0, 4), n(5, 7), n(8, 10));
    // days from the civil date (Howard Hinnant's algorithm)
    let y = if m <= 2 { y - 1 } else { y };
    let era = y.div_euclid(400);
    let yoe = y - era * 400;
    let doy = (153 * (if m > 2 { m - 3 } else { m + 9 }) + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    let days = era * 146_097 + doe - 719_468;
    days * 86_400 + n(11, 13) * 3600 + n(14, 16) * 60 + n(17, 19)
}

/// what one payload holds, decoded: a tile (nodes, ways, relations) or a relation store blob (ways, places)
#[derive(Default)]
pub(crate) struct Part {
    pub(crate) nid: Vec<i64>,
    pub(crate) lat: Vec<i32>,
    pub(crate) lon: Vec<i32>,
    /// per node, its number among the tagged ones, or -1
    pub(crate) tag_of: Vec<i32>,
    pub(crate) tver: Vec<i32>,
    pub(crate) tts: Vec<i64>,
    pub(crate) n_toff: Vec<usize>,
    pub(crate) ntb: Vec<u8>,
    pub(crate) wid: Vec<i64>,
    pub(crate) wver: Vec<i32>,
    pub(crate) wts: Vec<i64>,
    pub(crate) w_roff: Vec<usize>,
    pub(crate) wrefs: Vec<i64>,
    pub(crate) w_toff: Vec<usize>,
    pub(crate) wtb: Vec<u8>,
    pub(crate) rid: Vec<i64>,
    pub(crate) rver: Vec<i32>,
    pub(crate) rts: Vec<i64>,
    pub(crate) r_moff: Vec<usize>,
    pub(crate) rmt: Vec<i8>,
    pub(crate) rmref: Vec<i64>,
    pub(crate) rrl: Vec<i32>,
    /// per member, where its role starts in rroles
    pub(crate) r_rloff: Vec<usize>,
    pub(crate) rroles: Vec<u8>,
    pub(crate) r_toff: Vec<usize>,
    pub(crate) rtb: Vec<u8>,
}

impl Part {
    /// nothing yet, every offset column started (for appending)
    pub(crate) fn empty() -> Part {
        Part { n_toff: vec![0], w_roff: vec![0], w_toff: vec![0], r_moff: vec![0], r_rloff: vec![0], r_toff: vec![0], ..Default::default() }
    }

    fn ways(&mut self, c: &mut impl Iterator<Item = crate::cols::Col>) {
        self.wid = undelta(c.next().unwrap().i64());
        self.wver = c.next().unwrap().i32();
        self.wts = c.next().unwrap().i64();
        self.w_roff = offsets(&c.next().unwrap().i32());
        self.wrefs = undelta(c.next().unwrap().i64());
        self.w_toff = offsets(&c.next().unwrap().i32());
        self.wtb = c.next().unwrap().u8();
    }

    fn places(&mut self, c: &mut impl Iterator<Item = crate::cols::Col>) {
        self.nid = undelta(c.next().unwrap().i64());
        self.lat = undelta32(c.next().unwrap().i32());
        self.lon = undelta32(c.next().unwrap().i32());
        self.tag_of = vec![-1; self.nid.len()];
    }

    pub(crate) fn tile(buf: &[u8]) -> Part {
        let cols = unpack_cols(buf);
        assert!(cols.len() == 25, "a tile payload has 25 columns, not {}", cols.len());
        let mut c = cols.into_iter();
        let mut p = Part::default();
        p.places(&mut c);
        for (j, pos) in c.next().unwrap().i32().into_iter().enumerate() {
            p.tag_of[pos as usize] = j as i32;
        }
        p.tver = c.next().unwrap().i32();
        p.tts = c.next().unwrap().i64();
        p.n_toff = offsets(&c.next().unwrap().i32());
        p.ntb = c.next().unwrap().u8();
        p.ways(&mut c);
        p.rid = undelta(c.next().unwrap().i64());
        p.rver = c.next().unwrap().i32();
        p.rts = c.next().unwrap().i64();
        p.r_moff = offsets(&c.next().unwrap().i32());
        p.rmt = c.next().unwrap().i8();
        p.rmref = undelta(c.next().unwrap().i64());
        p.rrl = c.next().unwrap().i32();
        p.r_rloff = offsets(&p.rrl);
        p.rroles = c.next().unwrap().u8();
        p.r_toff = offsets(&c.next().unwrap().i32());
        p.rtb = c.next().unwrap().u8();
        p
    }

    pub(crate) fn relation_blob(buf: &[u8]) -> Part {
        let cols = unpack_cols(buf);
        assert!(cols.len() == 10, "a relation store blob has 10 columns, not {}", cols.len());
        let mut c = cols.into_iter();
        let mut p = Part::default();
        p.ways(&mut c);
        p.places(&mut c);
        p
    }
}

/// the payloads of these index rows, read one after another
pub(crate) fn payloads(dir: &Path, prefix: &str, rows: &[(i64, i32, i64, i32)]) -> Vec<Vec<u8>> {
    let mut files: HashMap<i32, File> = HashMap::new();
    rows.iter()
        .map(|&(_, pack, off, len)| {
            let f = files.entry(pack).or_insert_with(|| {
                let p = dir.join(format!("{prefix}-{pack:04}.bin"));
                File::open(&p).unwrap_or_else(|e| panic!("{}: {e}", p.display()))
            });
            let mut b = vec![0u8; len as usize];
            f.seek(SeekFrom::Start(off as u64)).unwrap();
            f.read_exact(&mut b).unwrap();
            b
        })
        .collect()
}

pub(crate) fn find(idx: &[(i64, i32, i64, i32)], key: i64) -> Option<(i64, i32, i64, i32)> {
    idx.binary_search_by_key(&key, |r| r.0).ok().map(|i| idx[i])
}

pub struct Args {
    pub store: PathBuf,
    pub gen: i64,
    pub cities: PathBuf,
    pub base: PathBuf,
    pub ring: f64,
    pub out: PathBuf,
    pub stamp: Option<String>,
}

pub fn read(a: &Args) {
    let t0 = Instant::now();
    let meta: serde_json::Value = serde_json::from_slice(&fs::read(a.store.join("store.json")).expect("store.json")).unwrap();
    let z = meta["z"].as_u64().expect("z") as u32;
    let gens: Vec<i64> = meta["generations"].as_array().expect("generations").iter().map(|g| g["gen"].as_i64().unwrap()).collect();
    let g = if a.gen < 0 { gens[(gens.len() as i64 + a.gen) as usize] } else { a.gen };
    assert!(gens.contains(&g), "the store has no generation {g}");
    let idx = npy::load_idx(&a.store.join(format!("idx-{g:04}.npy")));
    // the relation index of the newest generation up to g that wrote one
    let rg = gens.iter().copied().filter(|&x| x <= g && a.store.join(format!("relidx-{x:04}.npy")).exists()).max().expect("a relation index");
    let ridx = npy::load_idx(&a.store.join(format!("relidx-{rg:04}.npy")));

    let keys = tiles_of(&a.cities, &a.base, a.ring, z);
    let rows: Vec<_> = keys.iter().filter_map(|&k| find(&idx, k as i64)).collect();
    let bufs = payloads(&a.store, "pack", &rows);
    let tile_bytes: usize = bufs.iter().map(Vec::len).sum();
    let mut parts: Vec<Part> = bufs.par_iter().map(|b| Part::tile(b)).collect();
    drop(bufs);
    let mut rel_ids: Vec<i64> = parts.iter().flat_map(|p| p.rid.iter().copied()).collect();
    rel_ids.sort_unstable();
    rel_ids.dedup();
    let rrows: Vec<_> = rel_ids.iter().filter_map(|&r| find(&ridx, r)).collect();
    let bufs = payloads(&a.store, "rel", &rrows);
    let rel_bytes: usize = bufs.iter().map(Vec::len).sum();
    parts.par_extend(bufs.par_iter().map(|b| Part::relation_blob(b)));
    drop(bufs);
    let t_tiles = t0.elapsed().as_secs_f64();

    // one copy of each id; of a node, a copy that carries its tags if any tile holds one
    let t = Instant::now();
    let mut nodes: Vec<(i64, bool, u32, u32)> = Vec::new();
    let mut ways: Vec<(i64, u32, u32)> = Vec::new();
    let mut rels: Vec<(i64, u32, u32)> = Vec::new();
    for (s, p) in parts.iter().enumerate() {
        nodes.extend(p.nid.iter().enumerate().map(|(i, &id)| (id, p.tag_of[i] < 0, s as u32, i as u32)));
        ways.extend(p.wid.iter().enumerate().map(|(i, &id)| (id, s as u32, i as u32)));
        rels.extend(p.rid.iter().enumerate().map(|(i, &id)| (id, s as u32, i as u32)));
    }
    nodes.par_sort_unstable();
    nodes.dedup_by_key(|n| n.0);
    ways.par_sort_unstable();
    ways.dedup_by_key(|w| w.0);
    rels.par_sort_unstable();
    rels.dedup_by_key(|r| r.0);
    let t_merge = t.elapsed().as_secs_f64();

    let t = Instant::now();
    // blocks by count and by an estimate of their size (refs and members as varints, tags as bytes)
    let node_ranges = pbf::block_ranges(nodes.len(), |k| {
        let (_, _, s, i) = nodes[k];
        let p = &parts[s as usize];
        let j = p.tag_of[i as usize];
        24 + if j < 0 { 0 } else { p.n_toff[j as usize + 1] - p.n_toff[j as usize] }
    });
    let way_ranges = pbf::block_ranges(ways.len(), |k| {
        let (_, s, j) = ways[k];
        let (p, j) = (&parts[s as usize], j as usize);
        32 + 5 * (p.w_roff[j + 1] - p.w_roff[j]) + (p.w_toff[j + 1] - p.w_toff[j])
    });
    let rel_ranges = pbf::block_ranges(rels.len(), |k| {
        let (_, s, j) = rels[k];
        let (p, j) = (&parts[s as usize], j as usize);
        let (m0, m1) = (p.r_moff[j], p.r_moff[j + 1]);
        32 + 8 * (m1 - m0) + (p.r_rloff[m1] - p.r_rloff[m0]) + (p.r_toff[j + 1] - p.r_toff[j])
    });
    let node_blobs = node_ranges.into_par_iter().map(|r| {
        let ch = &nodes[r];
        let v: Vec<pbf::Node> = ch
            .iter()
            .map(|&(id, _, s, i)| {
                let (p, i) = (&parts[s as usize], i as usize);
                let j = p.tag_of[i];
                if j < 0 {
                    // an untagged node has only a place in the store: version 1, no timestamp
                    pbf::Node { id, lat7: p.lat[i], lon7: p.lon[i], version: 1, seconds: 0, tags: &[] }
                } else {
                    let j = j as usize;
                    pbf::Node { id, lat7: p.lat[i], lon7: p.lon[i], version: p.tver[j], seconds: p.tts[j], tags: &p.ntb[p.n_toff[j]..p.n_toff[j + 1]] }
                }
            })
            .collect();
        pbf::blob("OSMData", &pbf::node_block(&v))
    });
    let way_blobs = way_ranges.into_par_iter().map(|r| {
        let ch = &ways[r];
        let v: Vec<pbf::Way> = ch
            .iter()
            .map(|&(id, s, j)| {
                let (p, j) = (&parts[s as usize], j as usize);
                pbf::Way { id, version: p.wver[j], seconds: p.wts[j], refs: &p.wrefs[p.w_roff[j]..p.w_roff[j + 1]], tags: &p.wtb[p.w_toff[j]..p.w_toff[j + 1]] }
            })
            .collect();
        pbf::blob("OSMData", &pbf::way_block(&v))
    });
    let rel_blobs = rel_ranges.into_par_iter().map(|r| {
        let ch = &rels[r];
        let v: Vec<pbf::Relation> = ch
            .iter()
            .map(|&(id, s, j)| {
                let (p, j) = (&parts[s as usize], j as usize);
                let (m0, m1) = (p.r_moff[j], p.r_moff[j + 1]);
                pbf::Relation {
                    id,
                    version: p.rver[j],
                    seconds: p.rts[j],
                    mtype: &p.rmt[m0..m1],
                    mref: &p.rmref[m0..m1],
                    roles: &p.rroles[p.r_rloff[m0]..p.r_rloff[m1]],
                    role_len: &p.rrl[m0..m1],
                    tags: &p.rtb[p.r_toff[j]..p.r_toff[j + 1]],
                }
            })
            .collect();
        pbf::blob("OSMData", &pbf::relation_block(&v))
    });
    let blobs: Vec<Vec<u8>> = node_blobs.chain(way_blobs).chain(rel_blobs).collect();
    if let Some(d) = a.out.parent() {
        fs::create_dir_all(d).unwrap();
    }
    let mut f = BufWriter::with_capacity(1 << 22, File::create(&a.out).unwrap());
    f.write_all(&pbf::blob("OSMHeader", &pbf::header_block(a.stamp.as_deref().map(stamp_seconds)))).unwrap();
    let mut bytes = 0usize;
    for b in &blobs {
        f.write_all(b).unwrap();
        bytes += b.len();
    }
    f.flush().unwrap();
    let t_write = t.elapsed().as_secs_f64();

    let st = format!(
        "{{\"by\": \"tilestore (Rust)\", \"gen\": {g}, \"tiles\": {}, \"tileBytes\": {tile_bytes}, \"relBytes\": {rel_bytes}, \"nodes\": {}, \"ways\": {}, \"relations\": {}, \"pbfBytes\": {bytes}, \"secondsTiles\": {t_tiles:.2}, \"secondsMerge\": {t_merge:.2}, \"secondsWrite\": {t_write:.2}, \"seconds\": {:.2}, \"peakPrivateGiB\": {:.2}}}",
        rows.len(),
        nodes.len(),
        ways.len(),
        rels.len(),
        t0.elapsed().as_secs_f64(),
        crate::ptime::peak_private()
    );
    fs::write(format!("{}.json", a.out.display()), &st).unwrap();
    eprintln!("read: {st}");
}
