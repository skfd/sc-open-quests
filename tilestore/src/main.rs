//! The tile store in Rust, held against the Python prototype (tools/stream/tiles.py, tilestore.py; DESIGN.md,
//! "Measurement (c)", "The tile store in Rust", "The planet cut, designed"). It writes and reads the prototype's
//! store layout, so the Python tools and tools/stream/tilecheck/storecmp.py work on its stores unchanged.
//!
//!   tilestore cut --pbf X.osm.pbf --out S --day 2026-11-12 [--z 14]
//!       the cut with the whole file in memory: right for a clip, the oracle for the streaming cut
//!   tilestore scut --pbf X.osm.pbf --out S --day 2026-11-12 [--z 14] [--bucket-z 8] [--keep-spill] [--at T]
//!       [--file-z B] [--cut-gib 2] [--nodes F.loc [--sparse]]
//!       the streaming cut (stream.rs): three passes and buckets, the planet cut's shape; with --at, of a
//!       history file as it was at T. A spill file is a cell of zoom --file-z (default: a file a bucket);
//!       the spill files cut at once hold at most --cut-gib GiB of records (or are one file). With --nodes
//!       the node places are kept in that file by id (nodefile.rs), not in memory; it is deleted after pass 2
//!   tilestore at --pbf X.osh.pbf --at 2026-10-01T00:00:00Z [--out Y.osm.pbf] [--stamp T]
//!       a history file at a date, as a snapshot PBF (history.rs)
//!   tilestore ptime --pbf X.os[mh].pbf [--at T] --nodes F.loc [--z 14] [--sparse] [--keep]
//!       the planet cut's passes 1 and 2 timed, the node places in a file by id (ptime.rs)
//!   tilestore update --store S --diff N.osc.gz (--before D-1.osm.pbf | --before-loc planet.loc) --day 2026-11-13
//!       [--polygon P.geojson | --world] [--prune-pairs] [--group-z G | --group-mib M]
//!       a day's diff into a new generation of the store (update.rs, tilestore.py update step for step); the node
//!       places before the day from the clip's PBF of the day before, or from a node file by id in osmium's
//!       dense_file_array layout (the world stream's planet.loc); the polygon is the clip's, the store's region;
//!       --world: a store of the whole world, every tile in its region; --prune-pairs: the generation before's
//!       way and relation pair indexes deleted once this one's are written (the planet's way pairs are 22 GB);
//!       --group-z G: the reached tiles rebuilt a cell of zoom G at a time, not in one working set; --group-mib M:
//!       in groups of about M MiB of old payload, cells of zoom 8 in order
//!   tilestore loc build --pbf X.os[mh].pbf [--at T] --out F.loc | loc advance --loc F.loc --diff N.osc.gz --at T
//!       | loc check --loc F.loc --pbf Y.osm.pbf
//!       the node places by id in osmium's dense_file_array layout, as --before-loc reads them (locfile.rs): built
//!       from a file at a date, moved forward by a day's diff, checked against a snapshot of the same instant
//!   tilestore compact --store S [--min-dead 0.0] [--dry-run]
//!       the live tiles and relation blobs of older daily packs copied into the newest generation's files, the old
//!       packs and older generations' indexes removed; only the newest generation stays readable (compact.rs)
//!   tilestore punch --store S [--dry-run]
//!       pack 0's whole 64 KiB units no live tile touches given back in place (sparse file, zeroed ranges), every
//!       live tile hashed before and after; generation 0's pair indexes removed (punch.rs)
//!   tilestore read --store S [--gen -1] --cities C.json [--base DIR] [--ring 300] --out Y.osm.pbf [--stamp T]
//!   tilestore ways --store S [--gen -1] --ids W.npy [--rels R.npy] --out DIR
//!       each asked way's node refs and their places in generation G (ways.rs): through wtiles-G and a tile that holds
//!       the way whole; a way in no tile from the relation store blobs of the relations in R.npy. W.npy and R.npy are
//!       1-d '<i8' ids. DIR gets ids.npy (as asked), how.npy (u1: 0 absent, 1 a tile, 2 the relation store), offs.npy
//!       (i8, n + 1: way i's refs are refs[offs[i]:offs[i+1]], empty if absent), refs.npy (i8), lat7.npy and lon7.npy
//!       (i4, 1e-7 degrees; i32::MIN where no payload held the node), ways.json (counts, seconds, peak memory).
//!       wtiles-G goes at the next update with --prune-pairs: ask for D-1 before the day's update
//!   tilestore context --store S [--gen -1] [--ways W.npy] [--rels R.npy] [--nodes N.npy --node-places NP.npy]
//!       [--points P.npy] [--around 1] [--prefix addr: ...] [--rel-geometry] [--vertex-ways]
//!       [--crossing X.npy [--crossing-key highway ...]] --out DIR
//!       what tier 2's cover needs around a day's changes, at generation G (context.rs): ways' tags, refs, places,
//!       their refs with a --prefix tag and the relations holding them; relations' tags, members and member box
//!       (with --rel-geometry, their member ways' refs and places too); nodes' tags at their places (with
//!       --vertex-ways, every way they are a vertex of, with its geometry); the closed ways and multipolygons whose
//!       ring holds each point; with --crossing, the ways with a --crossing-key tag whose segments cross one of X's
//!       segments ('<i8' lat7, lon7, lat7, lon7 each), with their geometry. NP and P are '<i8' lat7, lon7 pairs.
//!       Ways and relations need G's pairs (gone at the next update with --prune-pairs), nodes, points and crossings
//!       only G's tile index. Out files are listed in context.rs

mod clip;
mod compact;
mod cols;
mod context;
mod history;
mod locfile;
mod nodefile;
mod npy;
mod osc;
mod pairs;
mod pbf;
mod punch;
mod ptime;
mod read;
mod stream;
mod tiles;
mod update;
mod ways;

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
                let fz: u32 = arg(&args, "--file-z").map(|s| s.parse().unwrap()).unwrap_or(bz);
                assert!(fz <= bz, "a spill file is no finer than a bucket");
                // GiB of spilled records cut at once
                let budget: f64 = arg(&args, "--cut-gib").map(|s| s.parse().unwrap()).unwrap_or(2.0);
                let budget = (budget * (1u64 << 30) as f64) as u64;
                let nodes = arg(&args, "--nodes").map(PathBuf::from);
                let nodes = nodes.as_deref().map(|p| (p, args.iter().any(|a| a == "--sparse")));
                stream::cut(&pbf, &out, &day, z, bz, fz, budget, args.iter().any(|a| a == "--keep-spill"), at, nodes);
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
        Some("ways") => ways::ways(&ways::Args {
            store: PathBuf::from(arg(&args, "--store").expect("--store")),
            gen: arg(&args, "--gen").map(|s| s.parse().unwrap()).unwrap_or(-1),
            ids: PathBuf::from(arg(&args, "--ids").expect("--ids")),
            rels: arg(&args, "--rels").map(PathBuf::from),
            out: PathBuf::from(arg(&args, "--out").expect("--out")),
        }),
        Some("context") => context::context(&context::Args {
            store: PathBuf::from(arg(&args, "--store").expect("--store")),
            gen: arg(&args, "--gen").map(|s| s.parse().unwrap()).unwrap_or(-1),
            ways: arg(&args, "--ways").map(PathBuf::from),
            rels: arg(&args, "--rels").map(PathBuf::from),
            nodes: arg(&args, "--nodes").map(PathBuf::from),
            node_places: arg(&args, "--node-places").map(PathBuf::from),
            points: arg(&args, "--points").map(PathBuf::from),
            around: arg(&args, "--around").map(|s| s.parse().unwrap()).unwrap_or(1),
            prefixes: {
                let v: Vec<String> = args.windows(2).filter(|w| w[0] == "--prefix").map(|w| w[1].clone()).collect();
                if v.is_empty() { vec!["addr:".to_string()] } else { v }
            },
            rel_geometry: args.iter().any(|x| x == "--rel-geometry"),
            crossing: arg(&args, "--crossing").map(PathBuf::from),
            crossing_keys: {
                let v: Vec<String> = args.windows(2).filter(|w| w[0] == "--crossing-key").map(|w| w[1].clone()).collect();
                if v.is_empty() { vec!["highway".to_string()] } else { v }
            },
            vertex_ways: args.iter().any(|x| x == "--vertex-ways"),
            out: PathBuf::from(arg(&args, "--out").expect("--out")),
        }),
        Some("update") => update::update(&update::Args {
            store: PathBuf::from(arg(&args, "--store").expect("--store")),
            diff: PathBuf::from(arg(&args, "--diff").expect("--diff")),
            before: PathBuf::from(arg(&args, "--before").or_else(|| arg(&args, "--before-loc")).expect("--before or --before-loc")),
            before_loc: arg(&args, "--before-loc").is_some(),
            world: args.iter().any(|x| x == "--world"),
            prune_pairs: args.iter().any(|x| x == "--prune-pairs"),
            group_z: arg(&args, "--group-z").map(|s| s.parse().unwrap()),
            group_mib: arg(&args, "--group-mib").map(|s| s.parse().unwrap()),
            day: arg(&args, "--day").expect("--day"),
            polygon: arg(&args, "--polygon").map(PathBuf::from),
        }),
        Some("ptime") => ptime::run(
            &PathBuf::from(arg(&args, "--pbf").expect("--pbf")),
            arg(&args, "--at").map(|s| read::stamp_seconds(&s)),
            &PathBuf::from(arg(&args, "--nodes").expect("--nodes")),
            arg(&args, "--z").map(|s| s.parse().unwrap()).unwrap_or(14),
            args.iter().any(|a| a == "--sparse"),
            args.iter().any(|a| a == "--keep"),
        ),
        Some("loc") => match args.get(2).map(String::as_str) {
            Some("build") => {
                let at_text = arg(&args, "--at");
                locfile::build(
                    &PathBuf::from(arg(&args, "--pbf").expect("--pbf")),
                    at_text.as_deref().map(read::stamp_seconds),
                    at_text.as_deref(),
                    &PathBuf::from(arg(&args, "--out").expect("--out")),
                )
            }
            Some("advance") => locfile::advance(
                &PathBuf::from(arg(&args, "--loc").expect("--loc")),
                &PathBuf::from(arg(&args, "--diff").expect("--diff")),
                &arg(&args, "--at").expect("--at: the instant the diff ends at"),
            ),
            Some("check") => {
                let differ = locfile::check(
                    &PathBuf::from(arg(&args, "--loc").expect("--loc")),
                    &PathBuf::from(arg(&args, "--pbf").expect("--pbf")),
                );
                if differ > 0 {
                    std::process::exit(1);
                }
            }
            _ => {
                eprintln!("tilestore loc build|advance|check: see main.rs");
                std::process::exit(2);
            }
        },
        Some("compact") => compact::compact(
            &PathBuf::from(arg(&args, "--store").expect("--store")),
            arg(&args, "--min-dead").map(|s| s.parse().unwrap()).unwrap_or(0.0),
            args.iter().any(|a| a == "--dry-run"),
        ),
        Some("punch") => punch::punch(&PathBuf::from(arg(&args, "--store").expect("--store")), args.iter().any(|a| a == "--dry-run")),
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
