//! The tile store's cut in Rust: a spike held against the Python prototype (tools/stream/tiles.py, tilestore.py;
//! DESIGN.md, "Measurement (c)" and "The tile store in Rust"). It writes the prototype's store layout, generation 0,
//! so the Python reader and tools/stream/tilecheck/storecmp.py work on it unchanged.
//!
//!   tilestore cut --pbf X.osm.pbf --out S --day 2026-11-12 [--z 14]
//!
//! Everything is held in memory: right for a clip, not for the planet (the planet cut is not built).

mod clip;
mod cols;
mod npy;
mod tiles;

use rayon::prelude::*;
use std::fs::{self, File};
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use std::time::Instant;

use clip::Clip;
use cols::{pack_cols, Col};

fn log(msg: &str) {
    eprintln!("{msg}");
}

fn arg(args: &[String], name: &str) -> Option<String> {
    args.iter().position(|a| a == name).and_then(|i| args.get(i + 1).cloned())
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.get(1).map(String::as_str) != Some("cut") {
        eprintln!("usage: tilestore cut --pbf X.osm.pbf --out S --day D [--z 14]");
        std::process::exit(2);
    }
    let pbf = PathBuf::from(arg(&args, "--pbf").expect("--pbf"));
    let out = PathBuf::from(arg(&args, "--out").expect("--out"));
    let day = arg(&args, "--day").expect("--day");
    let z: u32 = arg(&args, "--z").map(|s| s.parse().unwrap()).unwrap_or(14);
    assert!(z <= 16, "tile keys are 32 bits here");
    cut(&pbf, &out, &day, z);
}

/// the slice of `pairs` (sorted, key in the upper 32 bits) that holds `key`
fn of_key(pairs: &[u64], key: u32) -> &[u64] {
    let lo = pairs.partition_point(|&p| ((p >> 32) as u32) < key);
    let hi = lo + pairs[lo..].partition_point(|&p| ((p >> 32) as u32) <= key);
    &pairs[lo..hi]
}

fn rows_of(pairs: &[u64]) -> Vec<u32> {
    pairs.iter().map(|&p| p as u32).collect()
}

fn cut(pbf: &Path, out: &Path, day: &str, z: u32) {
    let t0 = Instant::now();
    let mut phases: Vec<(&str, f64)> = Vec::new();
    let mut t = Instant::now();
    let mut lap = |name: &'static str, t: &mut Instant, phases: &mut Vec<(&str, f64)>| {
        let s = t.elapsed().as_secs_f64();
        log(&format!("  {name}: {s:.1} s"));
        phases.push((name, s));
        *t = Instant::now();
    };

    let mut c = Clip::read(pbf);
    log(&format!(
        "read: {} nodes ({} tagged), {} ways ({} refs), {} relations ({} members, {} kept)",
        c.nid.len(),
        c.tn_ver.len(),
        c.wid.len(),
        c.wref_ids.len(),
        c.rid.len(),
        c.mref.len(),
        c.r_kept.iter().filter(|&&k| k).count()
    ));
    lap("read", &mut t, &mut phases);

    c.place(z);
    lap("place", &mut t, &mut phases);

    // (way, tile) for every tile a way's segments cross: per way, sorted
    let (wt_off, wt_key) = tiles::way_tiles(&c, z);
    log(&format!("way tiles: {} (way, tile) pairs", wt_key.len()));
    lap("wayTiles", &mut t, &mut phases);

    // relations: a member node's tile, every tile a member way crosses; kept relations only. Per relation, sorted.
    let nr = c.rid.len();
    let rel_keys: Vec<Vec<u32>> = (0..nr)
        .into_par_iter()
        .map(|r| {
            if !c.r_kept[r] {
                return Vec::new();
            }
            let mut k = Vec::new();
            for m in c.roffs[r] as usize..c.roffs[r + 1] as usize {
                match c.mtype[m] {
                    0 => {
                        if let Ok(row) = c.nid.binary_search(&c.mref[m]) {
                            k.push(c.nkey[row]);
                        }
                    }
                    1 => {
                        if let Ok(w) = c.wid.binary_search(&c.mref[m]) {
                            k.extend_from_slice(&wt_key[wt_off[w] as usize..wt_off[w + 1] as usize]);
                        }
                    }
                    _ => {}
                }
            }
            k.sort_unstable();
            k.dedup();
            k
        })
        .collect();
    let mut rel_pairs: Vec<u64> = Vec::new();
    for (r, ks) in rel_keys.iter().enumerate() {
        rel_pairs.extend(ks.iter().map(|&k| (k as u64) << 32 | r as u64));
    }
    rel_pairs.par_sort_unstable();

    // ways by tile
    let nw = c.wid.len();
    let mut way_pairs: Vec<u64> = Vec::with_capacity(wt_key.len());
    for w in 0..nw {
        for &k in &wt_key[wt_off[w] as usize..wt_off[w + 1] as usize] {
            way_pairs.push((k as u64) << 32 | w as u64);
        }
    }
    way_pairs.par_sort_unstable();

    // nodes: every node of every way in the tile, the tagged nodes in it, and the kept relations' member nodes there
    const CHUNK: usize = 1 << 14;
    let parts: Vec<Vec<u64>> = (0..nw.div_ceil(CHUNK))
        .into_par_iter()
        .map(|ci| {
            let mut v = Vec::new();
            for w in ci * CHUNK..((ci + 1) * CHUNK).min(nw) {
                let rows = &c.wrefs[c.woffs[w] as usize..c.woffs[w + 1] as usize];
                for &k in &wt_key[wt_off[w] as usize..wt_off[w + 1] as usize] {
                    for &row in rows {
                        if row != clip::NONE {
                            v.push((k as u64) << 32 | row as u64);
                        }
                    }
                }
            }
            v
        })
        .collect();
    let mut node_pairs: Vec<u64> = Vec::with_capacity(parts.iter().map(Vec::len).sum::<usize>() + c.tn_row.len());
    for p in parts {
        node_pairs.extend_from_slice(&p);
    }
    for &row in &c.tn_row {
        node_pairs.push((c.nkey[row as usize] as u64) << 32 | row as u64);
    }
    for r in 0..nr {
        if !c.r_kept[r] {
            continue;
        }
        for m in c.roffs[r] as usize..c.roffs[r + 1] as usize {
            if c.mtype[m] == 0 {
                if let Ok(row) = c.nid.binary_search(&c.mref[m]) {
                    node_pairs.push((c.nkey[row] as u64) << 32 | row as u64);
                }
            }
        }
    }
    node_pairs.par_sort_unstable();
    node_pairs.dedup();
    log(&format!(
        "tile pairs: {} node, {} way, {} relation copies",
        node_pairs.len(),
        way_pairs.len(),
        rel_pairs.len()
    ));
    lap("tilePairs", &mut t, &mut phases);

    let mut keys: Vec<u32> = node_pairs
        .iter()
        .chain(way_pairs.iter())
        .chain(rel_pairs.iter())
        .map(|&p| (p >> 32) as u32)
        .collect();
    keys.par_sort_unstable();
    keys.dedup();

    fs::create_dir_all(out).unwrap();
    let mut idx: Vec<(i64, i32, i64, i32)> = Vec::with_capacity(keys.len());
    let mut off: i64 = 0;
    {
        let mut f = BufWriter::with_capacity(1 << 22, File::create(out.join("pack-0000.bin")).unwrap());
        for chunk in keys.chunks(1024) {
            let bufs: Vec<Vec<u8>> = chunk
                .par_iter()
                .map(|&k| {
                    let mut cols: Vec<Col> = Vec::with_capacity(25);
                    c.node_cols(&rows_of(of_key(&node_pairs, k)), &mut cols);
                    c.way_cols(&rows_of(of_key(&way_pairs, k)), &mut cols);
                    c.rel_cols(&rows_of(of_key(&rel_pairs, k)), &mut cols);
                    pack_cols(&cols)
                })
                .collect();
            for (k, b) in chunk.iter().zip(&bufs) {
                f.write_all(b).unwrap();
                idx.push((*k as i64, 0, off, b.len() as i32));
                off += b.len() as i64;
            }
        }
        f.flush().unwrap();
    }
    npy::save_idx(&out.join("idx-0000.npy"), &idx);
    lap("tiles", &mut t, &mut phases);

    // the tiles of every way and relation, by id: a day's update finds a changed object's old tiles here
    let mut wp: Vec<(i64, i64)> = Vec::with_capacity(wt_key.len());
    for w in 0..nw {
        for &k in &wt_key[wt_off[w] as usize..wt_off[w + 1] as usize] {
            wp.push((c.wid[w], k as i64));
        }
    }
    npy::save_pairs(&out.join("wtiles-0000.npy"), &wp);
    drop(wp);
    let mut rp: Vec<(i64, i64)> = Vec::with_capacity(rel_pairs.len());
    for (r, ks) in rel_keys.iter().enumerate() {
        rp.extend(ks.iter().map(|&k| (c.rid[r], k as i64)));
    }
    npy::save_pairs(&out.join("rtiles-0000.npy"), &rp);
    drop(rp);
    lap("pairIndexes", &mut t, &mut phases);

    // the relation store: per kept relation, its member ways whole with their nodes' places
    let kept: Vec<u32> = (0..nr as u32).filter(|&r| c.r_kept[r as usize]).collect();
    let mut ridx: Vec<(i64, i32, i64, i32)> = Vec::with_capacity(kept.len());
    let mut roff: i64 = 0;
    let mut member_ways: u64 = 0;
    {
        let mut f = BufWriter::with_capacity(1 << 22, File::create(out.join("rel-0000.bin")).unwrap());
        for chunk in kept.chunks(8192) {
            let bufs: Vec<(Vec<u8>, usize)> = chunk
                .par_iter()
                .map(|&r| {
                    let r = r as usize;
                    let mut wi: Vec<u32> = Vec::new();
                    for m in c.roffs[r] as usize..c.roffs[r + 1] as usize {
                        if c.mtype[m] == 1 {
                            if let Ok(w) = c.wid.binary_search(&c.mref[m]) {
                                wi.push(w as u32);
                            }
                        }
                    }
                    wi.sort_unstable();
                    wi.dedup();
                    let mut u: Vec<u32> = Vec::new();
                    for &w in &wi {
                        let w = w as usize;
                        u.extend(c.wrefs[c.woffs[w] as usize..c.woffs[w + 1] as usize].iter().filter(|&&x| x != clip::NONE));
                    }
                    u.sort_unstable();
                    u.dedup();
                    let mut cols: Vec<Col> = Vec::with_capacity(10);
                    c.way_cols(&wi, &mut cols);
                    c.place_cols(&u, &mut cols);
                    (pack_cols(&cols), wi.len())
                })
                .collect();
            for (&r, (b, n)) in chunk.iter().zip(&bufs) {
                f.write_all(b).unwrap();
                ridx.push((c.rid[r as usize], 0, roff, b.len() as i32));
                roff += b.len() as i64;
                member_ways += *n as u64;
            }
        }
        f.flush().unwrap();
    }
    npy::save_idx(&out.join("relidx-0000.npy"), &ridx);
    lap("relationStore", &mut t, &mut phases);

    let secs = t0.elapsed().as_secs_f64();
    let ph: Vec<String> = phases.iter().map(|(n, s)| format!("\"{n}\": {s:.1}")).collect();
    let meta = format!(
        "{{\n \"z\": {z},\n \"generations\": [\n  {{\n   \"gen\": 0,\n   \"day\": \"{day}\",\n   \"from\": {from:?},\n   \"by\": \"tilestore (Rust)\",\n   \"tiles\": {tiles},\n   \"bytes\": {off},\n   \"relations\": {rels},\n   \"relationWays\": {member_ways},\n   \"relBytes\": {roff},\n   \"seconds\": {secs:.1},\n   \"phaseSeconds\": {{{ph}}},\n   \"copies\": {{\n    \"nodes\": {cn},\n    \"ways\": {cw},\n    \"relations\": {cr}\n   }}\n  }}\n ]\n}}\n",
        from = pbf.to_string_lossy(),
        tiles = keys.len(),
        rels = kept.len(),
        ph = ph.join(", "),
        cn = node_pairs.len(),
        cw = way_pairs.len(),
        cr = rel_pairs.len(),
    );
    fs::write(out.join("store.json"), meta).unwrap();
    log(&format!(
        "cut {day}: {} tiles, {:.2} GiB; relation store {} relations, {member_ways} member ways, {:.0} MiB; {secs:.1} s in all",
        keys.len(),
        off as f64 / (1u64 << 30) as f64,
        kept.len(),
        roff as f64 / (1u64 << 20) as f64
    ));
}
