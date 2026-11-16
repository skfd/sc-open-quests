//! The node places by id in osmium's dense_file_array layout, the planet update's node store (DESIGN.md, "The
//! planet's first day"): at byte 8 * id the longitude, then the latitude, in 1e-7 degrees as int32 little-endian;
//! both 2^31-1 where there is no node. The world stream's planet.loc has this layout (stream.py DenseLocations
//! keeps it with pyosmium), and `update --before-loc` reads it, so one file can serve both.
//!
//!   tilestore loc build --pbf X.os[mh].pbf [--at T] --out F.loc
//!       every node's place at T (or a snapshot's) written in id order; F.loc.state says what it holds
//!   tilestore loc advance --loc F.loc --diff N.osc.gz --at T
//!       the diff's last version of each node written in place (a deleted node emptied); refuses a T not after
//!       the one in F.loc.state, so an older diff cannot undo a newer one
//!   tilestore loc check --loc F.loc --pbf Y.osm.pbf
//!       every node of a snapshot against the file: the oracle, a clip of the same instant
//!
//! Unlike nodefile.rs's layout (the cut's, where eight zero bytes are "no node"), an empty place here is not zero
//! bytes, so the file is written whole, never sought over and never sparse: the planet's is about 115 GB.

use crate::nodefile::{free_bytes, under_floor};
use crate::stream::Blobs;
use crate::{log, osc};
use osmpbf::{BlobDecode, BlobReader};
use rayon::prelude::*;
use std::fs::{self, File, OpenOptions};
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use std::time::Instant;

/// osmium's undefined Location: both coordinates 2^31-1
pub const EMPTY: [u8; 8] = [0xff, 0xff, 0xff, 0x7f, 0xff, 0xff, 0xff, 0x7f];

pub fn place(lat: i32, lon: i32) -> [u8; 8] {
    let mut b = [0u8; 8];
    b[..4].copy_from_slice(&lon.to_le_bytes());
    b[4..].copy_from_slice(&lat.to_le_bytes());
    b
}

/// (lat, lon) of the eight bytes, None when empty or outside the world (osmium's Location::valid())
pub fn decode(b: &[u8]) -> Option<(i32, i32)> {
    let x = i32::from_le_bytes(b[..4].try_into().unwrap());
    let y = i32::from_le_bytes(b[4..8].try_into().unwrap());
    let ok = (-1_800_000_000..=1_800_000_000).contains(&x) && (-900_000_000..=900_000_000).contains(&y);
    ok.then_some((y, x))
}

fn state_path(loc: &Path) -> PathBuf {
    PathBuf::from(format!("{}.state", loc.display()))
}

/// a block's nodes as one stretch of the file from its first id, the gaps empty; ids not above the one before are
/// left out and counted
fn stretch(ids: &[i64], lat: &[i32], lon: &[i32]) -> Option<(i64, Vec<u8>, u64)> {
    let first = *ids.first()?;
    let mut out = Vec::with_capacity(ids.len() * 8);
    let (mut last, mut skipped) = (first - 1, 0u64);
    for i in 0..ids.len() {
        let id = ids[i];
        assert!(id >= 0, "a negative node id");
        if id <= last {
            skipped += 1;
            continue;
        }
        for _ in last + 1..id {
            out.extend_from_slice(&EMPTY);
        }
        out.extend_from_slice(&place(lat[i], lon[i]));
        last = id;
    }
    Some((first, out, skipped))
}

pub fn build(pbf: &Path, at: Option<i64>, at_text: Option<&str>, out: &Path) {
    let t0 = Instant::now();
    if let Some(d) = out.parent() {
        fs::create_dir_all(d).unwrap();
    }
    let dir = out.parent().filter(|d| !d.as_os_str().is_empty()).unwrap_or(Path::new("."));
    let _ = fs::remove_file(state_path(out));
    let blobs = Blobs::index(pbf);
    let nb = blobs.offs.len();
    log(&format!("{nb} blobs, nodes in the first {}; index {:.1} s", blobs.first_way, t0.elapsed().as_secs_f64()));
    let file = File::create(out).unwrap_or_else(|e| panic!("create {}: {e}", out.display()));
    let mut w = BufWriter::with_capacity(1 << 24, file);
    let (mut next, mut nodes, mut skipped, mut adds) = (0i64, 0u64, 0u64, 0u64);
    let mut stopped: Option<u64> = None;
    let t1 = Instant::now();
    let st = blobs.each_at(
        0,
        (blobs.first_way + 1).min(nb),
        at,
        |p| (stretch(&p.nid, &p.lat7, &p.lon7), p.nid.len() as u64),
        |(s, n)| {
            if stopped.is_some() {
                return;
            }
            adds += 1;
            if adds % 256 == 0 {
                if let Some(free) = under_floor(dir) {
                    stopped = Some(free);
                    return;
                }
            }
            let Some((first, bytes, sk)) = s else { return };
            nodes += n - sk;
            skipped += sk;
            let (mut first, mut bytes) = (first, &bytes[..]);
            if first < next {
                // a block that starts at or below what is written: only its part above
                let drop = ((next - first) as usize * 8).min(bytes.len());
                skipped += (drop / 8) as u64;
                bytes = &bytes[drop..];
                first = next;
            }
            for _ in next..first {
                w.write_all(&EMPTY).unwrap();
            }
            w.write_all(bytes).unwrap();
            next = first + bytes.len() as i64 / 8;
        },
    );
    if let Some(free) = stopped {
        drop(w);
        let _ = fs::remove_file(out);
        panic!("the node file is deleted and the run stopped: {:.1} GiB free, under the floor", free as f64 / (1u64 << 30) as f64);
    }
    let file = w.into_inner().unwrap();
    file.sync_all().unwrap();
    let bytes = file.metadata().unwrap().len();
    let held = at_text.map_or_else(|| format!("snapshot {}", pbf.file_name().unwrap().to_string_lossy()), str::to_string);
    fs::write(state_path(out), &held).unwrap();
    log(&format!(
        "loc build: {nodes} nodes, highest id {}, {:.2} GiB, {} skipped (ids not increasing; history reader: {} not increasing, {} backwards) in {:.1} s ({:.1} s the nodes); holds {held}; {:.1} GiB free after",
        next - 1,
        bytes as f64 / (1u64 << 30) as f64,
        skipped,
        st.not_increasing,
        st.backwards,
        t0.elapsed().as_secs_f64(),
        t1.elapsed().as_secs_f64(),
        free_bytes(dir).unwrap_or(0) as f64 / (1u64 << 30) as f64
    ));
    assert!(skipped == 0 && st.not_increasing == 0, "nodes out of id order: the file may hold a wrong version");
}

pub fn advance(loc: &Path, diff: &Path, at_text: &str) {
    let t0 = Instant::now();
    let at = crate::read::stamp_seconds(at_text);
    let sp = state_path(loc);
    let before = fs::read_to_string(&sp).unwrap_or_else(|e| panic!("{}: {e} (a node file says what it holds)", sp.display()));
    let before = before.trim().to_string();
    let held = before.strip_prefix("history file ").map(|_| None).unwrap_or_else(|| {
        // store.py's planet.loc names its history file until its first day; ours names the instant
        (!before.starts_with("snapshot ")).then(|| crate::read::stamp_seconds(&before))
    });
    if let Some(h) = held {
        assert!(at > h, "{} holds {before}; the diff to {at_text} is not after it", loc.display());
    } else {
        log(&format!("{} holds \"{before}\", not an instant: the diff's order is not checked", loc.display()));
    }
    let d = osc::read(diff);
    let t_diff = t0.elapsed().as_secs_f64();
    let top = d.n_all.last().copied().unwrap_or(-1);
    let f = OpenOptions::new().read(true).write(true).open(loc).unwrap_or_else(|e| panic!("{}: {e}", loc.display()));
    let len = f.metadata().unwrap().len();
    let want = ((top + 1).max(0) as u64) * 8;
    if want > len {
        // new ids above the file's end: the stretch between empty, not zero
        let mut w = BufWriter::new(&f);
        use std::io::{Seek, SeekFrom};
        w.seek(SeekFrom::Start(len)).unwrap();
        for _ in 0..(want - len) / 8 {
            w.write_all(&EMPTY).unwrap();
        }
        w.flush().unwrap();
    }
    // SAFETY: the file is ours while this runs; nothing else maps it for writing
    let mut m = unsafe { memmap2::MmapMut::map_mut(&f) }.expect("map the node file");
    let (mut set, mut emptied, mut moved, mut new) = (0u64, 0u64, 0u64, 0u64);
    let p = &d.part;
    for &id in &d.n_all {
        let at8 = id as usize * 8;
        let old = decode(&m[at8..at8 + 8]);
        let b = match p.nid.binary_search(&id) {
            Ok(i) => {
                set += 1;
                match old {
                    None => new += 1,
                    Some(o) if o != (p.lat[i], p.lon[i]) => moved += 1,
                    _ => {}
                }
                place(p.lat[i], p.lon[i])
            }
            Err(_) => {
                emptied += 1;
                EMPTY
            }
        };
        m[at8..at8 + 8].copy_from_slice(&b);
    }
    m.flush().unwrap();
    drop(m);
    f.sync_all().unwrap();
    let tmp = PathBuf::from(format!("{}.tmp", sp.display()));
    fs::write(&tmp, at_text).unwrap();
    fs::rename(&tmp, &sp).unwrap();
    log(&format!(
        "loc advance {before} -> {at_text}: {} nodes in the diff, {set} placed ({new} new, {moved} moved), {emptied} emptied; file {} -> {} bytes; {:.1} s ({:.1} s the diff)",
        d.n_all.len(),
        len,
        len.max(want),
        t0.elapsed().as_secs_f64(),
        t_diff
    ));
}

/// every node of a snapshot PBF against the file; returns the number that differ
pub fn check(loc: &Path, pbf: &Path) -> u64 {
    let t0 = Instant::now();
    let f = File::open(loc).unwrap_or_else(|e| panic!("{}: {e}", loc.display()));
    // SAFETY: read only
    let m = unsafe { memmap2::Mmap::map(&f) }.expect("map the node file");
    let reader = BlobReader::from_path(pbf).unwrap_or_else(|e| panic!("{}: {e}", pbf.display()));
    let blobs: Vec<_> = reader.map(|b| b.expect("a blob")).collect();
    // (nodes, differ, absent in the file, examples)
    let res: Vec<(u64, u64, u64, Vec<String>)> = blobs
        .par_iter()
        .map(|b| {
            let (mut n, mut differ, mut absent, mut ex) = (0u64, 0u64, 0u64, Vec::new());
            if let BlobDecode::OsmData(block) = b.decode().expect("decode a blob") {
                let mut one = |id: i64, lat: i32, lon: i32| {
                    n += 1;
                    let at8 = id as usize * 8;
                    let got = m.get(at8..at8 + 8).and_then(decode);
                    if got != Some((lat, lon)) {
                        if got.is_none() {
                            absent += 1;
                        }
                        differ += 1;
                        if ex.len() < 5 {
                            ex.push(format!("n{id}: file {got:?}, pbf {:?}", (lat, lon)));
                        }
                    }
                };
                for g in block.groups() {
                    for x in g.dense_nodes() {
                        one(x.id(), x.decimicro_lat(), x.decimicro_lon());
                    }
                    for x in g.nodes() {
                        one(x.id(), x.decimicro_lat(), x.decimicro_lon());
                    }
                }
            }
            (n, differ, absent, ex)
        })
        .collect();
    let (mut n, mut differ, mut absent) = (0u64, 0u64, 0u64);
    let mut ex: Vec<String> = Vec::new();
    for (a, b, c, e) in res {
        n += a;
        differ += b;
        absent += c;
        ex.extend(e);
    }
    ex.truncate(10);
    let state = fs::read_to_string(state_path(loc)).unwrap_or_default();
    log(&format!(
        "loc check {} (holds {}) against {}: {n} nodes, {differ} differ ({absent} of them absent from the file) in {:.1} s{}",
        loc.display(),
        state.trim(),
        pbf.display(),
        t0.elapsed().as_secs_f64(),
        if ex.is_empty() { String::new() } else { format!("; e.g. {}", ex.join("; ")) }
    ));
    differ
}
