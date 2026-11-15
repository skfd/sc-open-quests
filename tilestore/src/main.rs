//! The tile store in Rust, held against the Python prototype (tools/stream/tiles.py, tilestore.py; DESIGN.md,
//! "Measurement (c)", "The tile store in Rust", "The planet cut, designed"). It writes and reads the prototype's
//! store layout, so the Python tools and tools/stream/tilecheck/storecmp.py work on its stores unchanged.
//!
//!   tilestore cut --pbf X.osm.pbf --out S --day 2026-11-12 [--z 14]
//!       the cut with the whole file in memory: right for a clip, the oracle for the streaming cut
//!   tilestore scut --pbf X.osm.pbf --out S --day 2026-11-12 [--z 14] [--bucket-z 8] [--keep-spill] [--at T]
//!       the streaming cut (stream.rs): three passes and buckets, the planet cut's shape; with --at, of a
//!       history file as it was at T
//!   tilestore at --pbf X.osh.pbf --at 2026-10-01T00:00:00Z [--out Y.osm.pbf] [--stamp T]
//!       a history file at a date, as a snapshot PBF (history.rs)
//!   tilestore ptime --pbf X.os[mh].pbf [--at T] --nodes F.loc [--z 14] [--sparse] [--keep]
//!       the planet cut's passes 1 and 2 timed, the node places in a file by id (ptime.rs)
//!   tilestore read --store S [--gen -1] --cities C.json [--base DIR] [--ring 300] --out Y.osm.pbf [--stamp T]

mod clip;
mod cols;
mod history;
mod npy;
mod pairs;
mod pbf;
mod ptime;
mod read;
mod stream;
mod tiles;

use rayon::prelude::*;
use std::fs::{self, File};
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use std::time::Instant;

use clip::Clip;
use cols::{pack_cols, Col};

/// the system heap serialises large allocations: decoding a history file's relation blocks (many versions of
/// large relations) on 24 threads took three times as long as on one
#[global_allocator]
static ALLOC: mimalloc::MiMalloc = mimalloc::MiMalloc;

pub fn log(msg: &str) {
    eprintln!("{msg}");
}

fn arg(args: &[String], name: &str) -> Option<String> {
    args.iter().position(|a| a == name).and_then(|i| args.get(i + 1).cloned())
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let cmd = args.get(1).map(String::as_str);
    match cmd {
        Some("cut") | Some("scut") => {
            let pbf = PathBuf::from(arg(&args, "--pbf").expect("--pbf"));
            let out = PathBuf::from(arg(&args, "--out").expect("--out"));
            let day = arg(&args, "--day").expect("--day");
            let z: u32 = arg(&args, "--z").map(|s| s.parse().unwrap()).unwrap_or(14);
            assert!(z <= 16, "tile keys are 32 bits here");
            if cmd == Some("cut") {
                cut(&pbf, &out, &day, z);
            } else {
                let bz: u32 = arg(&args, "--bucket-z").map(|s| s.parse().unwrap()).unwrap_or(8);
                assert!(bz <= z, "a bucket is no finer than a tile");
                let at = arg(&args, "--at").map(|s| read::stamp_seconds(&s));
                stream::cut(&pbf, &out, &day, z, bz, args.iter().any(|a| a == "--keep-spill"), at);
            }
        }
        Some("read") => read::read(&read::Args {
            store: PathBuf::from(arg(&args, "--store").expect("--store")),
            gen: arg(&args, "--gen").map(|s| s.parse().unwrap()).unwrap_or(-1),
            cities: PathBuf::from(arg(&args, "--cities").expect("--cities")),
            base: PathBuf::from(arg(&args, "--base").unwrap_or_else(|| ".".into())),
            ring: arg(&args, "--ring").map(|s| s.parse().unwrap()).unwrap_or(300.0),
            out: PathBuf::from(arg(&args, "--out").expect("--out")),
            stamp: arg(&args, "--stamp"),
        }),
        Some("ptime") => ptime::run(
            &PathBuf::from(arg(&args, "--pbf").expect("--pbf")),
            arg(&args, "--at").map(|s| read::stamp_seconds(&s)),
            &PathBuf::from(arg(&args, "--nodes").expect("--nodes")),
            arg(&args, "--z").map(|s| s.parse().unwrap()).unwrap_or(14),
            args.iter().any(|a| a == "--sparse"),
            args.iter().any(|a| a == "--keep"),
        ),
        Some("at") => history::at(
            &PathBuf::from(arg(&args, "--pbf").expect("--pbf")),
            &arg(&args, "--at").expect("--at"),
            arg(&args, "--out").map(PathBuf::from).as_deref(),
            arg(&args, "--stamp").as_deref(),
        ),
        _ => {
            eprintln!(
                "usage: tilestore cut --pbf X.osm.pbf --out S --day D [--z 14]\n       tilestore scut --pbf X.osm.pbf --out S --day D [--z 14] [--bucket-z 8] [--keep-spill] [--at T]\n       tilestore at --pbf X.osh.pbf --at 2026-10-01T00:00:00Z [--out Y.osm.pbf] [--stamp T]\n       tilestore read --store S [--gen -1] --cities C.json [--base DIR] [--ring 300] --out Y.osm.pbf [--stamp 2026-11-12T00:00:00Z]"
            );
            std::process::exit(2);
        }
    }
}

/// what a cut records about itself in store.json
pub struct Meta<'a> {
    pub z: u32,
    pub day: &'a str,
    pub from: &'a Path,
    pub by: &'a str,
    pub tiles: usize,
    pub bytes: i64,
    pub relations: usize,
    pub member_ways: u64,
    pub rel_bytes: i64,
    pub seconds: f64,
    pub phases: &'a [(&'a str, f64)],
    pub copies: [usize; 3],
    pub extra: String,
}

pub fn write_meta(out: &Path, m: &Meta) {
    let ph: Vec<String> = m.phases.iter().map(|(n, s)| format!("\"{n}\": {s:.1}")).collect();
    let meta = format!(
        "{{\n \"z\": {z},\n \"generations\": [\n  {{\n   \"gen\": 0,\n   \"day\": \"{day}\",\n   \"from\": {from:?},\n   \"by\": \"{by}\",\n   \"tiles\": {tiles},\n   \"bytes\": {bytes},\n   \"relations\": {rels},\n   \"relationWays\": {mw},\n   \"relBytes\": {rb},\n   \"seconds\": {secs:.1},\n   \"phaseSeconds\": {{{ph}}},{extra}\n   \"copies\": {{\n    \"nodes\": {cn},\n    \"ways\": {cw},\n    \"relations\": {cr}\n   }}\n  }}\n ]\n}}\n",
        z = m.z,
        day = m.day,
        from = m.from.to_string_lossy(),
        by = m.by,
        tiles = m.tiles,
        bytes = m.bytes,
        rels = m.relations,
        mw = m.member_ways,
        rb = m.rel_bytes,
        secs = m.seconds,
        ph = ph.join(", "),
        extra = m.extra,
        cn = m.copies[0],
        cw = m.copies[1],
        cr = m.copies[2],
    );
    fs::write(out.join("store.json"), meta).unwrap();
}

fn cut(pbf: &Path, out: &Path, day: &str, z: u32) {
    let t0 = Instant::now();
    let mut phases: Vec<(&str, f64)> = Vec::new();
    let mut t = Instant::now();
    let lap = |name: &'static str, t: &mut Instant, phases: &mut Vec<(&str, f64)>| {
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

    let p = pairs::build(&c, z);
    log(&format!("tile pairs: {} node, {} way, {} relation copies", p.node.len(), p.way.len(), p.rel.len()));
    lap("tilePairs", &mut t, &mut phases);

    let keys = p.keys();
    fs::create_dir_all(out).unwrap();
    let mut idx: Vec<(i64, i32, i64, i32)> = Vec::with_capacity(keys.len());
    let mut off: i64 = 0;
    {
        let mut f = BufWriter::with_capacity(1 << 22, File::create(out.join("pack-0000.bin")).unwrap());
        for chunk in keys.chunks(1024) {
            let bufs: Vec<Vec<u8>> = chunk.par_iter().map(|&k| p.payload(&c, k).0).collect();
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
    let nw = c.wid.len();
    let nr = c.rid.len();
    let mut wp: Vec<(i64, i64)> = Vec::with_capacity(p.wt_key.len());
    for w in 0..nw {
        for &k in &p.wt_key[p.wt_off[w] as usize..p.wt_off[w + 1] as usize] {
            wp.push((c.wid[w], k as i64));
        }
    }
    npy::save_pairs(&out.join("wtiles-0000.npy"), &wp);
    drop(wp);
    let mut rp: Vec<(i64, i64)> = Vec::with_capacity(p.rel.len());
    for (r, ks) in p.rel_keys.iter().enumerate() {
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
    write_meta(
        out,
        &Meta {
            z,
            day,
            from: pbf,
            by: "tilestore cut (Rust, in memory)",
            tiles: keys.len(),
            bytes: off,
            relations: kept.len(),
            member_ways,
            rel_bytes: roff,
            seconds: secs,
            phases: &phases,
            copies: [p.node.len(), p.way.len(), p.rel.len()],
            extra: String::new(),
        },
    );
    log(&format!(
        "cut {day}: {} tiles, {:.2} GiB; relation store {} relations, {member_ways} member ways, {:.0} MiB; {secs:.1} s in all",
        keys.len(),
        off as f64 / (1u64 << 30) as f64,
        kept.len(),
        roff as f64 / (1u64 << 20) as f64
    ));
}
