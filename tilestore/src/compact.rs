//! Compaction by copying forward (DESIGN.md, "Compaction"): the live tiles of older daily packs, and the live blobs
//! of older relation files, appended to the newest generation's pack and relation file; then the newest indexes
//! point there, and the older packs and the older generations' indexes go. Pack 0 and relation file 0 (the cut's)
//! are never copied: they are too large to rewrite each time.
//!
//!   tilestore compact --store S [--min-dead 0.0] [--dry-run]
//!       packs 1 .. newest-1 whose dead share of what they were written with is at least --min-dead are copied
//!
//! Only the newest generation stays readable: store.json marks the older ones `"readable": false` before any file
//! is deleted. The copy is held against its source byte for byte before the indexes change. A run that stopped
//! leaves bytes past the newest pack's recorded length; the next run cuts them off first.

use crate::{log, npy};
use std::collections::BTreeMap;
use std::fs::{self, File, OpenOptions};
use std::io::{BufWriter, Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};
use std::time::Instant;

type Row = (i64, i32, i64, i32);

fn file(dir: &Path, prefix: &str, n: i64) -> PathBuf {
    dir.join(format!("{prefix}-{n:04}.bin"))
}

/// one kind of payload: tiles (`pack`, `idx`) or relation blobs (`rel`, `relidx`)
struct Kind {
    prefix: &'static str,
    index: &'static str,
    /// the recorded length of the newest file: what an update wrote, or what the last compaction left
    len_key: &'static str,
}

const TILES: Kind = Kind { prefix: "pack", index: "idx", len_key: "packBytes" };
const RELS: Kind = Kind { prefix: "rel", index: "relidx", len_key: "relFileBytes" };

struct Plan {
    rows: Vec<Row>,
    /// pack -> (written bytes, live bytes, live rows)
    packs: BTreeMap<i32, (u64, u64, u64)>,
}

fn plan(dir: &Path, k: &Kind, g: i64) -> Plan {
    let rows = npy::load_idx(&dir.join(format!("{}-{g:04}.npy", k.index)));
    let mut packs: BTreeMap<i32, (u64, u64, u64)> = BTreeMap::new();
    for r in &rows {
        let e = packs.entry(r.1).or_insert((0, 0, 0));
        e.1 += r.3 as u64;
        e.2 += 1;
    }
    for (&p, e) in packs.iter_mut() {
        e.0 = fs::metadata(file(dir, k.prefix, p as i64)).map(|m| m.len()).unwrap_or(0);
    }
    Plan { rows, packs }
}

/// the live payloads of `chosen` packs appended to the newest file, held against their source, and the new index
fn copy(dir: &Path, k: &Kind, g: i64, recorded: u64, p: &Plan, chosen: &[i32]) -> (Vec<Row>, u64, u64) {
    let dst_path = file(dir, k.prefix, g);
    let dst = OpenOptions::new().read(true).write(true).open(&dst_path).unwrap_or_else(|e| panic!("{}: {e}", dst_path.display()));
    let len = dst.metadata().unwrap().len();
    assert!(len >= recorded, "{} is {len} bytes, shorter than the {recorded} recorded", dst_path.display());
    if len > recorded {
        log(&format!("{}: {} bytes past the recorded end (a stopped run) cut off", dst_path.display(), len - recorded));
        dst.set_len(recorded).unwrap();
    }
    let mut rows = p.rows.clone();
    let mut order: Vec<usize> = (0..rows.len()).filter(|&i| chosen.contains(&rows[i].1)).collect();
    // by source file and offset: each source read front to back
    order.sort_unstable_by_key(|&i| (rows[i].1, rows[i].2));
    let mut w = BufWriter::with_capacity(1 << 24, &dst);
    w.seek(SeekFrom::Start(recorded)).unwrap();
    let mut off = recorded;
    let mut src: Option<(i32, File)> = None;
    let mut buf = Vec::new();
    for &i in &order {
        let (_, pack, o, n) = rows[i];
        if src.as_ref().map(|s| s.0) != Some(pack) {
            let path = file(dir, k.prefix, pack as i64);
            src = Some((pack, File::open(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()))));
        }
        let f = &mut src.as_mut().unwrap().1;
        buf.resize(n as usize, 0);
        f.seek(SeekFrom::Start(o as u64)).unwrap();
        f.read_exact(&mut buf).unwrap();
        w.write_all(&buf).unwrap();
        rows[i] = (rows[i].0, g as i32, off as i64, n);
        off += n as u64;
    }
    w.flush().unwrap();
    drop(w);
    dst.sync_all().unwrap();
    // held against the source before anything points at it
    let mut back = File::open(&dst_path).unwrap();
    let (mut a, mut b) = (Vec::new(), Vec::new());
    let mut src: Option<(i32, File)> = None;
    for &i in &order {
        let (_, pack, o, n) = p.rows[i];
        if src.as_ref().map(|s| s.0) != Some(pack) {
            src = Some((pack, File::open(file(dir, k.prefix, pack as i64)).unwrap()));
        }
        let f = &mut src.as_mut().unwrap().1;
        a.resize(n as usize, 0);
        f.seek(SeekFrom::Start(o as u64)).unwrap();
        f.read_exact(&mut a).unwrap();
        b.resize(n as usize, 0);
        back.seek(SeekFrom::Start(rows[i].2 as u64)).unwrap();
        back.read_exact(&mut b).unwrap();
        assert!(a == b, "copy of {} {} (from {} at {o}) differs from its source: nothing changed", k.prefix, rows[i].0, pack);
    }
    (rows, off, order.len() as u64)
}

pub fn compact(dir: &Path, min_dead: f64, dry: bool) {
    let t0 = Instant::now();
    let meta_path = dir.join("store.json");
    let mut meta: serde_json::Value = serde_json::from_slice(&fs::read(&meta_path).unwrap()).unwrap();
    let gens: Vec<i64> = meta["generations"].as_array().unwrap().iter().map(|x| x["gen"].as_i64().unwrap()).collect();
    let g = *gens.last().unwrap();
    let last = meta["generations"].as_array().unwrap().last().unwrap().clone();
    let recorded = |k: &Kind| -> u64 {
        last.get(k.len_key).and_then(|v| v.as_u64()).unwrap_or_else(|| {
            // an update records the bytes it wrote; a generation 0 is the cut's
            if k.prefix == "pack" { last["bytes"].as_u64().unwrap() } else { last["relBytes"].as_u64().unwrap() }
        })
    };
    let mut report = serde_json::Map::new();
    let mut work: Vec<(&Kind, Plan, Vec<i32>, u64)> = Vec::new();
    for k in [&TILES, &RELS] {
        let p = plan(dir, k, g);
        let mut chosen = Vec::new();
        let mut packs = serde_json::Map::new();
        for (&pk, &(written, live, n)) in &p.packs {
            let dead = if written == 0 { 0.0 } else { 1.0 - live as f64 / written as f64 };
            let pick = pk != 0 && pk as i64 != g && dead >= min_dead;
            if pick {
                chosen.push(pk);
            }
            packs.insert(pk.to_string(), serde_json::json!({"bytes": written, "live": live, "rows": n, "dead": (dead * 1000.0).round() / 1000.0, "copied": pick}));
            log(&format!("{} {pk}: {:.2} GiB written, {:.2} GiB live ({:.1}% dead), {n} rows{}", k.prefix, written as f64 / (1u64 << 30) as f64, live as f64 / (1u64 << 30) as f64, dead * 100.0, if pick { ": copied" } else { "" }));
        }
        report.insert(k.prefix.to_string(), serde_json::Value::Object(packs));
        let rec = recorded(k);
        work.push((k, p, chosen, rec));
    }
    let older: Vec<i64> = gens.iter().copied().filter(|&x| x < g).collect();
    if dry {
        log(&format!("dry run: generation {g}; nothing written ({:.1} s)", t0.elapsed().as_secs_f64()));
        return;
    }
    if crate::nodefile::under_floor(dir).is_some() {
        panic!("under the disk floor: nothing written");
    }
    // 1. copied and held against the source; the indexes still point at the old files
    let mut new_idx: Vec<(&Kind, Vec<Row>, u64, u64, Vec<i32>)> = Vec::new();
    for (k, p, chosen, rec) in &work {
        let (rows, end, n) = copy(dir, k, g, *rec, p, chosen);
        log(&format!("{}: {n} copied into {}-{g:04}, {} -> {end} bytes", k.prefix, k.prefix, rec));
        new_idx.push((k, rows, end, n, chosen.clone()));
    }
    // 2. store.json: the older generations unreadable, the newest files' lengths, the compaction recorded
    {
        let arr = meta["generations"].as_array_mut().unwrap();
        for x in arr.iter_mut() {
            if x["gen"].as_i64().unwrap() < g {
                x["readable"] = serde_json::json!(false);
            }
        }
        let lastm = arr.last_mut().unwrap();
        for (k, _, end, _, _) in &new_idx {
            lastm[k.len_key] = serde_json::json!(end);
        }
    }
    let rec = serde_json::json!({"gen": g, "seconds": (t0.elapsed().as_secs_f64() * 10.0).round() / 10.0, "minDead": min_dead,
        "copied": new_idx.iter().map(|(k, _, _, n, c)| (k.prefix.to_string(), serde_json::json!({"rows": n, "from": c}))).collect::<serde_json::Map<_, _>>(),
        "before": report});
    if !meta["compactions"].is_array() {
        meta["compactions"] = serde_json::json!([]);
    }
    meta["compactions"].as_array_mut().unwrap().push(rec.clone());
    let tmp = dir.join("store.json.tmp");
    fs::write(&tmp, serde_json::to_string_pretty(&meta).unwrap()).unwrap();
    fs::rename(&tmp, &meta_path).unwrap();
    // 3. the newest indexes point at the copies
    for (k, rows, _, _, _) in &new_idx {
        let path = dir.join(format!("{}-{g:04}.npy", k.index));
        let tmp = dir.join(format!("{}-{g:04}.npy.tmp", k.index));
        npy::save_idx(&tmp, rows);
        fs::rename(&tmp, &path).unwrap();
    }
    // 4. what nothing readable points at: the copied files, the older generations' indexes
    let mut freed = 0u64;
    let mut rm = |p: PathBuf| {
        if let Ok(m) = fs::metadata(&p) {
            freed += m.len();
            fs::remove_file(&p).unwrap_or_else(|e| panic!("{}: {e}", p.display()));
        }
    };
    for (k, _, _, _, chosen) in &new_idx {
        for &pk in chosen {
            rm(file(dir, k.prefix, pk as i64));
        }
        for &x in &older {
            rm(dir.join(format!("{}-{x:04}.npy", k.index)));
        }
    }
    log(&format!("compact generation {g}: {:.2} GiB of files removed in {:.1} s; {}", freed as f64 / (1u64 << 30) as f64, t0.elapsed().as_secs_f64(), rec));
}
