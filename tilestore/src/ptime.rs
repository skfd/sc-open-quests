//! The planet cut's passes 1 and 2, timed with the node places in a file by id (DESIGN.md, "The planet cut,
//! designed", unknown 2): the nodes' places written at 8 bytes an id, then every way's nodes found in that file
//! and its tiles computed. Nothing is spilled and no store is written.
//!
//!   tilestore ptime --pbf X.os[mh].pbf [--at T] --nodes F.loc [--z 14] [--sparse] [--keep]
//!
//! The node file: at byte 8 * id the node's latitude and longitude in 1e-7 degrees, little-endian, the latitude
//! with 2^31 added so that eight zero bytes mean "no such node". The planet's is about 108 GB. --sparse marks
//! it sparse (fsutil), for a region, whose nodes are spread over the planet's id range. It is deleted at the end
//! unless --keep.

use crate::stream::Blobs;
use crate::tiles::keys_of_way;
use crate::log;
use std::fs::{self, OpenOptions};
use std::io::{BufWriter, Seek, SeekFrom, Write};
use std::path::Path;
use std::time::Instant;

/// ids apart by more than this start a new run: the file is sought, not filled with zeros
const GAP: i64 = 4096;

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

fn place_bytes(lat: i32, lon: i32) -> [u8; 8] {
    let mut b = [0u8; 8];
    b[..4].copy_from_slice(&(lat.wrapping_sub(i32::MIN)).to_le_bytes());
    b[4..].copy_from_slice(&lon.to_le_bytes());
    b
}

fn place_at(map: &[u8], id: i64) -> Option<(i32, i32)> {
    let at = (id as usize).checked_mul(8)?;
    let b = map.get(at..at + 8)?;
    let lat = i32::from_le_bytes(b[..4].try_into().unwrap());
    if lat == 0 {
        return None;
    }
    Some((lat.wrapping_add(i32::MIN), i32::from_le_bytes(b[4..].try_into().unwrap())))
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
    if let Some(d) = nodes.parent() {
        fs::create_dir_all(d).unwrap();
    }
    let file = OpenOptions::new().read(true).write(true).create(true).truncate(true).open(nodes).expect("create the node file");
    if sparse {
        let ok = std::process::Command::new("fsutil").args(["sparse", "setflag"]).arg(nodes).status().map(|s| s.success()).unwrap_or(false);
        assert!(ok, "fsutil sparse setflag failed");
    }
    let mut w = BufWriter::with_capacity(1 << 24, file);
    let (mut next, mut n_nodes, mut n_tagged, mut seeks, mut top) = (0i64, 0u64, 0u64, 0u64, -1i64);
    let st1 = blobs.each_at(
        0,
        (blobs.first_way + 1).min(nb),
        at,
        |p| {
            // runs of ids close together, each as the bytes of its stretch of the file
            let mut runs: Vec<(i64, Vec<u8>)> = Vec::new();
            let mut last = i64::MIN;
            for i in 0..p.nid.len() {
                let id = p.nid[i];
                assert!(id >= 0, "a negative node id");
                if id <= last {
                    // given twice or out of order: counted by the reader, not written
                    continue;
                }
                if runs.is_empty() || id - last > GAP {
                    runs.push((id, Vec::new()));
                } else {
                    let r = &mut runs.last_mut().unwrap().1;
                    r.resize(r.len() + (id - last - 1) as usize * 8, 0);
                }
                runs.last_mut().unwrap().1.extend_from_slice(&place_bytes(p.lat7[i], p.lon7[i]));
                last = id;
            }
            (runs, p.nid.len() as u64, p.tn_local.len() as u64)
        },
        |(runs, n, tagged)| {
            n_nodes += n;
            n_tagged += tagged;
            for (start, bytes) in runs {
                if start < next {
                    continue;
                }
                if start - next <= GAP {
                    for _ in next..start {
                        w.write_all(&[0u8; 8]).unwrap();
                    }
                } else {
                    w.seek(SeekFrom::Start(start as u64 * 8)).unwrap();
                    seeks += 1;
                }
                w.write_all(&bytes).unwrap();
                next = start + bytes.len() as i64 / 8;
                top = next - 1;
            }
        },
    );
    w.flush().unwrap();
    let file = w.into_inner().unwrap();
    let node_bytes = file.metadata().unwrap().len();
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
    file.sync_all().unwrap();
    lap("nodeFileToDisk", &mut t, String::new());

    // pass 2: every way's nodes found in the file, its tiles computed
    // SAFETY: the file is ours and is not written while it is mapped
    let map = unsafe { memmap2::Mmap::map(&file) }.expect("map the node file");
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
                pl.extend(refs.iter().map(|&r| place_at(&map, r)));
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
    drop(map);
    drop(file);
    if !keep {
        fs::remove_file(nodes).unwrap();
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
