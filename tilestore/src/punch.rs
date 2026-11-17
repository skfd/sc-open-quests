//! The cut's pack given back in place (DESIGN.md, "Compaction"): pack 0 is too large to copy forward, but the
//! whole 64 KiB units of it that no live tile of the newest generation touches can be zeroed in a sparse file,
//! which gives their space back without a rewrite.
//!
//!   tilestore punch --store S [--dry-run]
//!
//! Every live tile of pack 0 is hashed before and after; a change stops the run with the store marked damaged.
//! The older generations are marked unreadable before any byte changes, and generation 0's pair indexes (kept
//! for a redo from the cut, which is no longer possible) are removed after. TILESTORE_TEST_PUNCH_LIVE=1 punches one
//! unit holding a live tile too: the negative control, for a throwaway copy only.

use crate::{log, npy};
use std::fs::{self, File, OpenOptions};
use std::hash::Hasher;
use std::path::Path;
use std::time::Instant;

extern "system" {
    fn DeviceIoControl(
        device: isize,
        code: u32,
        inbuf: *const u8,
        inlen: u32,
        outbuf: *mut u8,
        outlen: u32,
        returned: *mut u32,
        overlapped: *mut u8,
    ) -> i32;
}

const FSCTL_SET_SPARSE: u32 = 0x0009_00C4;
const FSCTL_SET_ZERO_DATA: u32 = 0x0009_80C8;
/// NTFS gives a sparse file's space back in whole units of 16 clusters: 64 KiB on a 4 KiB-cluster volume
const UNIT: i64 = 64 << 10;

fn ioctl(f: &File, code: u32, input: &[u8]) -> std::io::Result<()> {
    use std::os::windows::io::AsRawHandle;
    let mut got = 0u32;
    // SAFETY: a handle we own, an input buffer of the stated length, no output, synchronous
    let ok = unsafe {
        DeviceIoControl(f.as_raw_handle() as isize, code, input.as_ptr(), input.len() as u32, std::ptr::null_mut(), 0, &mut got, std::ptr::null_mut())
    };
    if ok == 0 {
        Err(std::io::Error::last_os_error())
    } else {
        Ok(())
    }
}

const FSCTL_QUERY_ALLOCATED_RANGES: u32 = 0x0009_40CF;
const ERROR_MORE_DATA: i32 = 234;

/// the ranges of the file that hold space (all of it, for a file that is not sparse)
fn allocated(f: &File, len: i64) -> Vec<(i64, i64)> {
    use std::os::windows::io::AsRawHandle;
    let mut out: Vec<(i64, i64)> = Vec::new();
    let mut from = 0i64;
    loop {
        let mut input = [0u8; 16];
        input[..8].copy_from_slice(&from.to_le_bytes());
        input[8..].copy_from_slice(&(len - from).to_le_bytes());
        let mut buf = vec![0u8; 16 * 4096];
        let mut got = 0u32;
        // SAFETY: a handle we own, buffers of the stated lengths, synchronous
        let ok = unsafe {
            DeviceIoControl(f.as_raw_handle() as isize, FSCTL_QUERY_ALLOCATED_RANGES, input.as_ptr(), 16, buf.as_mut_ptr(), buf.len() as u32, &mut got, std::ptr::null_mut())
        };
        let more = ok == 0 && std::io::Error::last_os_error().raw_os_error() == Some(ERROR_MORE_DATA);
        assert!(ok != 0 || more, "FSCTL_QUERY_ALLOCATED_RANGES: {}", std::io::Error::last_os_error());
        for r in buf[..got as usize].chunks_exact(16) {
            let o = i64::from_le_bytes(r[..8].try_into().unwrap());
            let n = i64::from_le_bytes(r[8..].try_into().unwrap());
            out.push((o, o + n));
        }
        if !more || got == 0 {
            break;
        }
        from = out.last().unwrap().1;
    }
    out
}

/// the parts of `want` that lie in `have` (both sorted, disjoint [a, b) lists)
pub fn intersect(want: &[(i64, i64)], have: &[(i64, i64)]) -> Vec<(i64, i64)> {
    let (mut i, mut j, mut out) = (0, 0, Vec::new());
    while i < want.len() && j < have.len() {
        let (a, b) = (want[i].0.max(have[j].0), want[i].1.min(have[j].1));
        if b > a {
            out.push((a, b));
        }
        if want[i].1 < have[j].1 {
            i += 1;
        } else {
            j += 1;
        }
    }
    out
}

/// the whole units of [0, len) that no live (offset, length) range touches, merged; the tail to the file's end
pub fn dead_ranges(live: &mut [(i64, i64)], len: i64) -> Vec<(i64, i64)> {
    live.sort_unstable();
    let mut out: Vec<(i64, i64)> = Vec::new();
    let mut end = 0i64;
    for &(o, n) in live.iter() {
        if n <= 0 {
            continue;
        }
        if o > end {
            let (a, b) = ((end + UNIT - 1) / UNIT * UNIT, o / UNIT * UNIT);
            if b > a {
                out.push((a, b));
            }
        }
        end = end.max(o + n);
    }
    let a = (end + UNIT - 1) / UNIT * UNIT;
    if len > a {
        out.push((a, len));
    }
    out
}

/// a hash of every live range, in the order given
fn hashes(path: &Path, live: &[(i64, i64)]) -> Vec<u64> {
    use rayon::prelude::*;
    let f = File::open(path).unwrap();
    // SAFETY: read only, and nothing writes the file while it is mapped here
    let m = unsafe { memmap2::Mmap::map(&f) }.expect("map the pack");
    live.par_iter()
        .map(|&(o, n)| {
            let mut h = std::collections::hash_map::DefaultHasher::new();
            h.write(&m[o as usize..(o + n) as usize]);
            h.finish()
        })
        .collect()
}

fn save(path: &Path, meta: &serde_json::Value) {
    let tmp = path.with_extension("json.tmp");
    fs::write(&tmp, serde_json::to_string_pretty(meta).unwrap()).unwrap();
    fs::rename(&tmp, path).unwrap();
}

pub fn punch(dir: &Path, dry: bool) {
    let t0 = Instant::now();
    let meta_path = dir.join("store.json");
    let mut meta: serde_json::Value = serde_json::from_slice(&fs::read(&meta_path).unwrap()).unwrap();
    let g = meta["generations"].as_array().unwrap().last().unwrap()["gen"].as_i64().unwrap();
    assert!(g > 0, "generation 0 alone: nothing in its pack is dead");
    let pack = dir.join("pack-0000.bin");
    let len = fs::metadata(&pack).unwrap().len() as i64;
    let rows = npy::load_idx(&dir.join(format!("idx-{g:04}.npy")));
    let mut live: Vec<(i64, i64)> = rows.iter().filter(|r| r.1 == 0).map(|r| (r.2, r.3 as i64)).collect();
    let live_bytes: i64 = live.iter().map(|x| x.1).sum();
    let mut ranges = dead_ranges(&mut live, len);
    if std::env::var("TILESTORE_TEST_PUNCH_LIVE").is_ok() {
        let (o, _) = live[live.len() / 2];
        ranges.push((o / UNIT * UNIT, o / UNIT * UNIT + UNIT));
        log("TEST: one unit holding a live tile is punched too");
    }
    let dead: i64 = ranges.iter().map(|r| r.1 - r.0).sum();
    let gib = |x: i64| x as f64 / (1u64 << 30) as f64;
    log(&format!(
        "pack-0000: {:.2} GiB, {} live tiles {:.2} GiB; {} dead ranges of whole 64 KiB units, {:.2} GiB ({dead} bytes)",
        gib(len),
        live.len(),
        gib(live_bytes),
        ranges.len(),
        gib(dead)
    ));
    // only what still holds space: a range punched before is not punched again (each call costs about 0.5 s on a
    // 233 GiB pack; the planet's first punch of 41,404 ranges took 5.45 h)
    ranges.sort_unstable();
    let held = allocated(&File::open(&pack).unwrap(), len);
    let ranges = intersect(&ranges, &held);
    let todo: i64 = ranges.iter().map(|r| r.1 - r.0).sum();
    log(&format!("still holding space: {} of those ranges, {:.2} GiB ({todo} bytes); the file holds {} allocated ranges", ranges.len(), gib(todo), held.len()));
    if dry {
        log(&format!("dry run: generation {g}; nothing written ({:.1} s)", t0.elapsed().as_secs_f64()));
        return;
    }
    let free0 = crate::nodefile::free_bytes(dir).unwrap_or(0) as i64;
    let before = hashes(&pack, &live);
    let t_hash = t0.elapsed().as_secs_f64();
    // the older generations unreadable before any byte changes: their tiles may lie in what is punched
    for x in meta["generations"].as_array_mut().unwrap().iter_mut() {
        if x["gen"].as_i64().unwrap() < g {
            x["readable"] = serde_json::json!(false);
        }
    }
    save(&meta_path, &meta);
    let f = OpenOptions::new().read(true).write(true).open(&pack).unwrap();
    ioctl(&f, FSCTL_SET_SPARSE, &[1u8]).unwrap_or_else(|e| panic!("FSCTL_SET_SPARSE on {}: {e}", pack.display()));
    for &(a, b) in &ranges {
        let mut input = [0u8; 16];
        input[..8].copy_from_slice(&a.to_le_bytes());
        input[8..].copy_from_slice(&b.to_le_bytes());
        ioctl(&f, FSCTL_SET_ZERO_DATA, &input).unwrap_or_else(|e| panic!("FSCTL_SET_ZERO_DATA [{a}, {b}) on {}: {e}", pack.display()));
    }
    f.sync_all().unwrap();
    drop(f);
    let t_punch = t0.elapsed().as_secs_f64();
    let after = hashes(&pack, &live);
    let bad = before.iter().zip(&after).filter(|(a, b)| a != b).count();
    let free1 = crate::nodefile::free_bytes(dir).unwrap_or(0) as i64;
    let rec = serde_json::json!({"gen": g, "ranges": ranges.len(), "bytes": dead, "punched": todo, "liveTiles": live.len(), "liveChanged": bad,
        "freeBefore": free0, "freeAfter": free1, "seconds": (t0.elapsed().as_secs_f64() * 10.0).round() / 10.0});
    if !meta["punches"].is_array() {
        meta["punches"] = serde_json::json!([]);
    }
    meta["punches"].as_array_mut().unwrap().push(rec.clone());
    if bad > 0 {
        meta["damaged"] = serde_json::json!(true);
        save(&meta_path, &meta);
        panic!("{bad} live tiles of pack-0000 changed in the punch: the store is damaged ({rec})");
    }
    // generation 0 is unreadable now, so a redo from it is not possible: its pair indexes go
    let mut freed_pairs = 0i64;
    for name in ["wtiles", "rtiles"] {
        let p = dir.join(format!("{name}-0000.npy"));
        if p.exists() {
            freed_pairs += fs::metadata(&p).unwrap().len() as i64;
            fs::remove_file(&p).unwrap();
        }
    }
    save(&meta_path, &meta);
    log(&format!(
        "punch generation {g}: {:.2} GiB of pack-0000 zeroed ({} ranges still holding space), free {:.2} -> {:.2} GiB (+{:.2}) before the pairs; generation 0's pairs {:.2} GiB removed; every live tile the same; hash {t_hash:.1} s, punch {:.1} s, all {:.1} s",
        gib(todo),
        ranges.len(),
        gib(free0),
        gib(free1),
        gib(free1 - free0),
        gib(freed_pairs),
        t_punch - t_hash,
        t0.elapsed().as_secs_f64()
    ));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dead_ranges_are_whole_untouched_units() {
        let u = UNIT;
        // live [10, 20) in unit 0 and [3u+5, 3u+10) in unit 3; the file 6u+100 long
        let mut live = vec![(3 * u + 5, 5), (10, 10)];
        assert_eq!(dead_ranges(&mut live, 6 * u + 100), vec![(u, 3 * u), (4 * u, 6 * u + 100)]);
        // a live range across a unit border keeps both units
        let mut live = vec![(u - 1, 2)];
        assert_eq!(dead_ranges(&mut live, 4 * u), vec![(2 * u, 4 * u)]);
        // nothing live: the whole file
        assert_eq!(dead_ranges(&mut [], 3 * u + 7), vec![(0, 3 * u + 7)]);
        assert_eq!(intersect(&[(0, 10), (20, 30), (40, 50)], &[(5, 25), (45, 100)]), vec![(5, 10), (20, 25), (45, 50)]);
        assert_eq!(intersect(&[(0, 10)], &[]), vec![]);
        // live to the very end: nothing
        let mut live = vec![(0, 2 * u)];
        assert_eq!(dead_ranges(&mut live, 2 * u), vec![]);
    }
}
