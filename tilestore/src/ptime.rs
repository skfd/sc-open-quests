//! The planet cut's passes 1 and 2, timed with the node places in a file by id (DESIGN.md, "The planet cut,
//! designed", unknown 2): the nodes' places written at 8 bytes an id, then every way's nodes found in that file
//! and its tiles computed. Nothing is spilled and no store is written.
//!
//!   tilestore ptime --pbf X.os[mh].pbf [--at T] --nodes F.loc [--z 14] [--sparse] [--keep]
//!
//! The node file is nodefile.rs's; the planet's is about 115 GB. --sparse marks
//! it sparse (fsutil), for a region, whose nodes are spread over the planet's id range. It is deleted at the end
//! unless --keep.

use crate::nodefile::{self, NodeWriter};
use crate::stream::Blobs;
use crate::tiles::keys_of_way;
use crate::log;
use std::fs;
use std::path::Path;
use std::time::Instant;

#[repr(C)]
#[derive(Default)]
struct Counters {
    cb: u32,
    page_faults: u32,
    peak_working_set: usize,
    working_set: usize,
    pools: [usize; 4],
    pagefile: usize,
    peak_pagefile: usize,
}

extern "system" {
    fn GetCurrentProcess() -> isize;
    fn K32GetProcessMemoryInfo(process: isize, counters: *mut Counters, cb: u32) -> i32;
}

/// (working set, its peak, private bytes) in GiB. The working set counts the pages of a mapped file that are in
/// memory, so in pass 2 it holds the node file's touched part; the private bytes are the program's own.
pub fn memory() -> (f64, f64, f64) {
    let mut c = Counters { cb: std::mem::size_of::<Counters>() as u32, ..Default::default() };
    // SAFETY: the struct is PROCESS_MEMORY_COUNTERS and cb is its size
    unsafe { K32GetProcessMemoryInfo(GetCurrentProcess(), &mut c, c.cb) };
    let g = |b: usize| b as f64 / (1u64 << 30) as f64;
    (g(c.working_set), g(c.peak_working_set), g(c.pagefile))
}

#[derive(Default)]
struct Ways {
    ways: u64,
    refs: u64,
    absent: u64,
    pairs: u64,
    no_tile: u64,
    /// ways with two nodes in a row more than 180 degrees of longitude apart
    wide: u64,
    wide_pairs: u64,
    most_keys: u64,
    key_sum: u64,
}

pub fn run(pbf: &Path, at: Option<i64>, nodes: &Path, z: u32, sparse: bool, keep: bool) {
    let t0 = Instant::now();
    let mut phases: Vec<String> = Vec::new();
    let mut t = Instant::now();
    let mut lap = |name: &str, t: &mut Instant, extra: String| {
        let s = t.elapsed().as_secs_f64();
        let (ws, peak, private) = memory();
        log(&format!("  {name}: {s:.1} s; working set {ws:.2} GiB (peak {peak:.2}), private {private:.2} GiB"));
        phases.push(format!("\"{name}\": {{\"seconds\": {s:.1}, \"workingSetGiB\": {ws:.2}, \"peakWorkingSetGiB\": {peak:.2}, \"privateGiB\": {private:.2}{extra}}}"));
        *t = Instant::now();
    };

    let blobs = Blobs::index(pbf);
    let nb = blobs.offs.len();
    log(&format!("{nb} blobs; ways from blob {}, relations from blob {}", blobs.first_way, blobs.first_rel));
    lap("index", &mut t, format!(", \"blobs\": {nb}, \"firstWay\": {}, \"firstRelation\": {}", blobs.first_way, blobs.first_rel));

    // pass 1: every node's place into the file, at its id
    let mut nw = NodeWriter::create(nodes, sparse);
    let (mut n_nodes, mut n_tagged) = (0u64, 0u64);
    let st1 = blobs.each_at(
        0,
        (blobs.first_way + 1).min(nb),
        at,
        |p| {
            (nodefile::runs(&p.nid, &p.lat7, &p.lon7), p.nid.len() as u64, p.tn_local.len() as u64)
        },
        |(runs, n, tagged)| {
            n_nodes += n;
            n_tagged += tagged;
            nw.add(&runs);
        },
    );
    let (seeks, top) = (nw.seeks, nw.top());
    // written out and on the disk before it is read: the wait is part of pass 1
    let map = nw.finish(true);
    let node_bytes = map.bytes;
    log(&format!(
        "pass 1: {n_nodes} nodes, {n_tagged} tagged, highest id {top}; node file {:.2} GiB, {seeks} seeks; {} versions read, {} older than the one before, {} ids not increasing",
        node_bytes as f64 / (1u64 << 30) as f64,
        st1.versions,
        st1.backwards,
        st1.not_increasing
    ));
    lap(
        "pass1Nodes",
        &mut t,
        format!(
            ", \"nodes\": {n_nodes}, \"tagged\": {n_tagged}, \"highestId\": {top}, \"nodeFileBytes\": {node_bytes}, \"versions\": {}, \"backwards\": {}, \"notIncreasing\": {}",
            st1.versions, st1.backwards, st1.not_increasing
        ),
    );
    let mut ways = Ways::default();
    let st2 = blobs.each_at(
        blobs.first_way,
        (blobs.first_rel + 1).min(nb),
        at,
        |p| {
            let mut o = Ways::default();
            let mut pl: Vec<Option<(i32, i32)>> = Vec::new();
            let mut keys: Vec<u32> = Vec::new();
            let mut roff = 0usize;
            for wi in 0..p.wid.len() {
                let refs = &p.w_refs[roff..roff + p.w_nref[wi] as usize];
                roff += refs.len();
                pl.clear();
                pl.extend(refs.iter().map(|&r| map.get(r)));
                keys_of_way(&pl, z, &mut keys);
                o.ways += 1;
                o.refs += refs.len() as u64;
                o.absent += pl.iter().filter(|p| p.is_none()).count() as u64;
                o.pairs += keys.len() as u64;
                o.no_tile += keys.is_empty() as u64;
                o.most_keys = o.most_keys.max(keys.len() as u64);
                o.key_sum = keys.iter().fold(o.key_sum, |s, &k| s.wrapping_add(k as u64));
                let wide = pl.windows(2).any(|w| match (w[0], w[1]) {
                    (Some(a), Some(b)) => (a.1 as i64 - b.1 as i64).abs() > 1_800_000_000,
                    _ => false,
                });
                if wide {
                    o.wide += 1;
                    o.wide_pairs += keys.len() as u64;
                }
            }
            o
        },
        |o| {
            ways.ways += o.ways;
            ways.refs += o.refs;
            ways.absent += o.absent;
            ways.pairs += o.pairs;
            ways.no_tile += o.no_tile;
            ways.wide += o.wide;
            ways.wide_pairs += o.wide_pairs;
            ways.most_keys = ways.most_keys.max(o.most_keys);
            ways.key_sum = ways.key_sum.wrapping_add(o.key_sum);
        },
    );
    log(&format!(
        "pass 2: {} ways ({} with no tile), {} refs ({} with no node), {} (way, tile) pairs, the most for one way {}; {} ways with nodes over 180 degrees apart, {} pairs of theirs; {} versions read, {} older than the one before, {} ids not increasing",
        ways.ways, ways.no_tile, ways.refs, ways.absent, ways.pairs, ways.most_keys, ways.wide, ways.wide_pairs, st2.versions, st2.backwards, st2.not_increasing
    ));
    lap(
        "pass2Ways",
        &mut t,
        format!(
            ", \"ways\": {}, \"noTile\": {}, \"refs\": {}, \"refsNoNode\": {}, \"pairs\": {}, \"mostPairsOfAWay\": {}, \"waysOver180\": {}, \"pairsOfWaysOver180\": {}, \"keySum\": {}, \"versions\": {}, \"backwards\": {}, \"notIncreasing\": {}",
            ways.ways, ways.no_tile, ways.refs, ways.absent, ways.pairs, ways.most_keys, ways.wide, ways.wide_pairs, ways.key_sum, st2.versions, st2.backwards, st2.not_increasing
        ),
    );
    if keep {
        drop(map);
    } else {
        map.delete();
        log("the node file is deleted");
    }
    let s = format!(
        "{{\"by\": \"tilestore ptime (Rust)\", \"pbf\": {:?}, \"at\": {}, \"z\": {z}, \"seconds\": {:.1}, \"phases\": {{{}}}}}",
        pbf.to_string_lossy(),
        at.map(|a| a.to_string()).unwrap_or("null".into()),
        t0.elapsed().as_secs_f64(),
        phases.join(", ")
    );
    fs::write(format!("{}.json", nodes.display()), &s).unwrap();
    eprintln!("ptime: {s}");
}
