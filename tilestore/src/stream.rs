//! The streaming cut (DESIGN.md, "The planet cut, designed"): three passes over a file sorted by type then id, then
//! the buckets one by one. Nothing of the whole file is held but the relations, the node places (in memory here: a
//! file by id for the planet, not built) and what the member ways and nodes of kept relations need.
//!
//! A bucket is a cell at zoom `bz`; a spill file holds the buckets of one cell at `bz - 2`. A bucket's spill holds
//! everything its tiles need: every way crossing it with its nodes' places, the tagged nodes at home in it, the
//! tagged nodes of its ways at home elsewhere (the "needs"), the member nodes of kept relations in it, and the kept
//! relations with a tile in it. So a bucket is cut alone, by the in-memory cut's code, and only its own tiles kept.

use crate::clip::{self, Clip, Part};
use crate::history;
use crate::nodefile::{self, NodeMap, NodeWriter};
use crate::cols::{delta32, delta64, pack_cols, Col};
use crate::npy;
use crate::pairs;
use crate::tiles::{frac_xy, key_of, keys_of_way};
use crate::{log, write_meta, Meta};
use osmpbf::{BlobDecode, BlobReader, BlobType, ByteOffset, PrimitiveBlock};
use rayon::prelude::*;
use std::collections::{BTreeSet, HashMap};
use std::fs::{self, File, OpenOptions};
use std::io::{BufReader, BufWriter, Read, Write};
use std::os::windows::fs::FileExt;
use std::path::{Path, PathBuf};
use std::sync::mpsc::{sync_channel, SyncSender};
use std::thread::JoinHandle;
use std::time::Instant;

/// a way's ref with no node in the file, in a spilled way
const ABSENT: i32 = i32::MIN;
const NO_KEY: u32 = u32::MAX;
const KIND_NODE: u8 = 0;
const KIND_WAY: u8 = 1;
const KIND_REL: u8 = 2;

// --- bytes ------------------------------------------------------------------------------------------

fn p32(o: &mut Vec<u8>, v: u32) {
    o.extend_from_slice(&v.to_le_bytes());
}
fn pi32(o: &mut Vec<u8>, v: i32) {
    o.extend_from_slice(&v.to_le_bytes());
}
fn pi64(o: &mut Vec<u8>, v: i64) {
    o.extend_from_slice(&v.to_le_bytes());
}

/// a signed number as a varint: zigzag, seven bits a byte, low first
fn pvar(o: &mut Vec<u8>, v: i64) {
    let mut u = ((v << 1) ^ (v >> 63)) as u64;
    while u >= 0x80 {
        o.push(u as u8 | 0x80);
        u >>= 7;
    }
    o.push(u as u8);
}

struct Cur<'a> {
    b: &'a [u8],
    p: usize,
}

impl<'a> Cur<'a> {
    fn new(b: &'a [u8]) -> Self {
        Cur { b, p: 0 }
    }
    fn u8(&mut self) -> u8 {
        self.p += 1;
        self.b[self.p - 1]
    }
    fn u32(&mut self) -> u32 {
        self.p += 4;
        u32::from_le_bytes(self.b[self.p - 4..self.p].try_into().unwrap())
    }
    fn i32(&mut self) -> i32 {
        self.u32() as i32
    }
    fn i64(&mut self) -> i64 {
        self.p += 8;
        i64::from_le_bytes(self.b[self.p - 8..self.p].try_into().unwrap())
    }
    fn var(&mut self) -> i64 {
        let (mut u, mut sh) = (0u64, 0);
        loop {
            let b = self.u8();
            u |= ((b & 0x7f) as u64) << sh;
            if b < 0x80 {
                break;
            }
            sh += 7;
        }
        (u >> 1) as i64 ^ -((u & 1) as i64)
    }
    fn bytes(&mut self, n: usize) -> &'a [u8] {
        self.p += n;
        &self.b[self.p - n..self.p]
    }
    fn done(&self) -> bool {
        self.p >= self.b.len()
    }
}

// --- cells ------------------------------------------------------------------------------------------

#[derive(Clone, Copy)]
struct Geo {
    z: u32,
    bz: u32,
    fz: u32,
}

impl Geo {
    fn bucket(&self, key: u32) -> u32 {
        let s = self.z - self.bz;
        let (x, y) = (key >> self.z, key & ((1 << self.z) - 1));
        ((x >> s) << self.bz) | (y >> s)
    }
    fn file(&self, bucket: u32) -> u32 {
        let s = self.bz - self.fz;
        let (x, y) = (bucket >> self.bz, bucket & ((1u32 << self.bz) - 1));
        ((x >> s) << self.fz) | (y >> s)
    }
}

// --- the spill --------------------------------------------------------------------------------------

/// records by spill file, kept in memory until a file's share passes a few MB, then appended to it as one zstd
/// frame: [compressed length][raw length][bytes]. A record: [kind][bucket][body length][body].
/// The pass's thread only fills the buffers: a full one is handed to a worker, which compresses it and appends
/// it. A file always goes to the same worker, so its frames are whole and in order.
struct Spill {
    /// to each worker: a file and a buffer of its records. Bounded, so the pass waits when the workers are behind
    /// and what is queued stays small
    to: Vec<SyncSender<(u32, Vec<u8>)>>,
    /// each worker: the bytes it wrote and the seconds it worked
    workers: Vec<JoinHandle<(u64, f64)>>,
    /// the workers' seconds together, known at the end
    worker_secs: f64,
    dir: PathBuf,
    geo: Geo,
    bufs: HashMap<u32, Vec<u8>>,
    files: BTreeSet<u32>,
    /// per file, its records' bytes before compression and before the ways' refs were coded: the cut budget's unit
    sizes: HashMap<u32, u64>,
    /// bytes waiting in `bufs`
    held: usize,
    raw: u64,
    written: u64,
    /// appends to spill files, the times all buffers went out at once, and the seconds the pass's thread spent
    /// handing buffers over (waiting for a worker, when they are behind)
    flushes: u64,
    flush_alls: u64,
    flush_secs: f64,
    /// per kind: records and their bytes before compression; and the refs of the way records
    kinds: [(u64, u64); 3],
    way_refs: u64,
}

impl Spill {
    const FLUSH: usize = 4 << 20;
    /// all the buffers together: past this every one is written out (a file a bucket means many files)
    const HELD: usize = 1 << 30;
    const WORKERS: usize = 6;
    /// buffers waiting for one worker, at most
    const QUEUE: usize = 8;

    fn new(dir: &Path, geo: Geo) -> Spill {
        let _ = fs::remove_dir_all(dir);
        fs::create_dir_all(dir).unwrap();
        let (mut to, mut workers) = (Vec::new(), Vec::new());
        for _ in 0..Self::WORKERS {
            let (tx, rx) = sync_channel::<(u32, Vec<u8>)>(Self::QUEUE);
            let dir = dir.to_path_buf();
            to.push(tx);
            workers.push(std::thread::spawn(move || {
                let (mut written, mut secs) = (0u64, 0f64);
                let mut frame = Vec::new();
                for (file, b) in rx {
                    let t = Instant::now();
                    let z = zstd::bulk::compress(&b, 1).expect("compress a spill frame");
                    frame.clear();
                    frame.extend_from_slice(&(z.len() as u32).to_le_bytes());
                    frame.extend_from_slice(&(b.len() as u32).to_le_bytes());
                    frame.extend_from_slice(&z);
                    let mut f = OpenOptions::new().create(true).append(true).open(dir.join(format!("f{file}.bin"))).expect("open a spill file");
                    f.write_all(&frame).expect("append to a spill file");
                    written += frame.len() as u64;
                    secs += t.elapsed().as_secs_f64();
                }
                (written, secs)
            }));
        }
        Spill { to, workers, worker_secs: 0.0, dir: dir.to_path_buf(), geo, bufs: HashMap::new(), files: BTreeSet::new(), sizes: HashMap::new(), held: 0, raw: 0, written: 0, flushes: 0, flush_alls: 0, flush_secs: 0.0, kinds: [(0, 0); 3], way_refs: 0 }
    }

    fn path(&self, file: u32) -> PathBuf {
        self.dir.join(format!("f{file}.bin"))
    }

    fn add(&mut self, kind: u8, bucket: u32, body: &[u8]) {
        self.add_as(kind, bucket, body, body.len());
    }

    /// `units`: what the body counts for in its file's size (a way: its bytes before its refs were coded)
    fn add_as(&mut self, kind: u8, bucket: u32, body: &[u8], units: usize) {
        let file = self.geo.file(bucket);
        *self.sizes.entry(file).or_default() += 9 + units as u64;
        let b = self.bufs.entry(file).or_default();
        b.push(kind);
        p32(b, bucket);
        p32(b, body.len() as u32);
        b.extend_from_slice(body);
        self.held += 9 + body.len();
        self.kinds[kind as usize].0 += 1;
        self.kinds[kind as usize].1 += 9 + body.len() as u64;
        if kind == KIND_WAY {
            self.way_refs += u32::from_le_bytes(body[20..24].try_into().unwrap()) as u64;
        }
        if b.len() >= Self::FLUSH {
            self.flush(file);
        } else if self.held >= Self::HELD {
            let files: Vec<u32> = self.bufs.iter().filter(|(_, b)| !b.is_empty()).map(|(&f, _)| f).collect();
            for f in files {
                self.flush(f);
            }
            // the buffers themselves go too: cleared ones would keep what they grew to
            self.bufs.clear();
            self.flush_alls += 1;
        }
    }

    fn flush(&mut self, file: u32) {
        let Some(b) = self.bufs.get_mut(&file) else { return };
        if b.is_empty() {
            return;
        }
        let t = Instant::now();
        // the buffer itself goes to the worker; the next records of this file start a new one
        let b = std::mem::take(b);
        self.flushes += 1;
        self.raw += b.len() as u64;
        self.files.insert(file);
        self.held -= b.len();
        // a worker that died (a write failed) has closed its end: the run stops here
        self.to[file as usize % Self::WORKERS].send((file, b)).expect("a spill worker stopped: its write failed");
        self.flush_secs += t.elapsed().as_secs_f64();
    }

    /// everything written and the workers ended: after this the files can be read
    fn finish(&mut self) {
        let files: Vec<u32> = self.bufs.keys().copied().collect();
        for f in files {
            self.flush(f);
        }
        self.bufs.clear();
        self.to.clear();
        for w in self.workers.drain(..) {
            let (written, secs) = w.join().expect("a spill worker failed");
            self.written += written;
            self.worker_secs += secs;
        }
    }

    /// a spill file's records, decompressed
    fn load(&self, file: u32) -> Vec<u8> {
        let mut f = BufReader::with_capacity(1 << 22, File::open(self.path(file)).unwrap());
        let mut out = Vec::new();
        let mut head = [0u8; 8];
        while f.read_exact(&mut head).is_ok() {
            let (zl, rl) = (u32::from_le_bytes(head[0..4].try_into().unwrap()), u32::from_le_bytes(head[4..8].try_into().unwrap()));
            let mut z = vec![0u8; zl as usize];
            f.read_exact(&mut z).unwrap();
            out.extend_from_slice(&zstd::bulk::decompress(&z, rl as usize).unwrap());
        }
        out
    }
}

// --- the file's blobs --------------------------------------------------------------------------------

/// the data blobs' offsets, and the first blob that holds a way and the first that holds a relation (the file is
/// sorted by type, so each pass reads one run of blobs)
pub struct Blobs {
    path: PathBuf,
    pub offs: Vec<ByteOffset>,
    pub first_way: usize,
    pub first_rel: usize,
}

fn kind_of(block: &PrimitiveBlock) -> u8 {
    let mut k = 0;
    for g in block.groups() {
        if g.relations().len() > 0 {
            k = k.max(2);
        } else if g.ways().len() > 0 {
            k = k.max(1);
        }
    }
    k
}

impl Blobs {
    pub fn index(path: &Path) -> Blobs {
        let mut r = BlobReader::seekable_from_path(path).expect("open the pbf");
        let mut offs = Vec::new();
        while let Some(h) = r.next_header_skip_blob() {
            let (h, off) = h.expect("a blob header");
            if matches!(h.blob_type(), BlobType::OsmData) {
                offs.push(off.expect("an offset"));
            }
        }
        let n = offs.len();
        let mut first = |want: u8| {
            let (mut lo, mut hi) = (0usize, n);
            while lo < hi {
                let mid = (lo + hi) / 2;
                let blob = r.blob_from_offset(offs[mid]).expect("a blob");
                let k = match blob.decode().expect("decode a blob") {
                    BlobDecode::OsmData(block) => kind_of(&block),
                    _ => 0,
                };
                if k >= want {
                    hi = mid;
                } else {
                    lo = mid + 1;
                }
            }
            lo
        };
        let (first_way, first_rel) = (first(1), first(2));
        Blobs { path: path.to_path_buf(), offs, first_way, first_rel }
    }

    /// the blocks of blobs [from, to), decoded and mapped on all threads, consumed in the file's order
    fn each<T: Send>(&self, from: usize, to: usize, map: impl Fn(&PrimitiveBlock) -> T + Sync, mut consume: impl FnMut(T)) {
        let mut r = BlobReader::seekable_from_path(&self.path).expect("open the pbf");
        let mut at = from;
        while at < to {
            let end = (at + 256).min(to);
            let batch: Vec<_> = self.offs[at..end].iter().map(|&o| r.blob_from_offset(o).expect("a blob")).collect();
            let out: Vec<Option<T>> = batch
                .par_iter()
                .map(|b| match b.decode().expect("decode a blob") {
                    BlobDecode::OsmData(block) => Some(map(&block)),
                    _ => None,
                })
                .collect();
            for t in out.into_iter().flatten() {
                consume(t);
            }
            at = end;
        }
    }

    /// `each` over parsed blocks; with `at` (seconds), a history file read at that date (history.rs): each
    /// block's versions decided and mapped on all threads, a version held at a block's end mapped and consumed
    /// before the next block's. `from` is the file's start or the first blob of a kind.
    pub fn each_at<T: Send>(
        &self,
        from: usize,
        to: usize,
        at: Option<i64>,
        map: impl Fn(Part) -> T + Sync,
        mut consume: impl FnMut(T),
    ) -> history::Stats {
        let mut stats = history::Stats::default();
        let Some(at) = at else {
            self.each(from, to, |block| map(clip::parse(block)), consume);
            return stats;
        };
        let t_ms = at * 1000;
        let mut stitch: history::Stitch<Part> = history::Stitch::new(t_ms);
        let mut order = history::Order::default();
        self.each(
            from,
            to,
            |block| {
                let sel = history::select(&clip::metas(block), t_ms);
                let (mut a, mut b) = (Part::default(), Part::default());
                clip::parse_into(block, |i| sel.dest[i], &mut a, &mut b);
                let ends = history::Ends::of(&a);
                (map(a), sel, b, ends)
            },
            |(t, sel, b, ends)| {
                stats.versions += sel.dest.len() as u64;
                stats.kept += sel.dest.iter().filter(|&&d| d == 1).count() as u64;
                stats.backwards += sel.backwards;
                let held = (sel.dest.last() == Some(&2)).then_some(b);
                if let Some(h) = stitch.block(sel.first, sel.last, held) {
                    stats.kept += 1;
                    order.add(&history::Ends::of(&h));
                    consume(map(h));
                }
                order.add(&ends);
                consume(t);
            },
        );
        // the last version read: the blob after the range, if there is one, may hold a later version of it
        let mut tail = None;
        if to < self.offs.len() {
            let mut r = BlobReader::seekable_from_path(&self.path).expect("open the pbf");
            let blob = r.blob_from_offset(self.offs[to]).expect("a blob");
            if let BlobDecode::OsmData(block) = blob.decode().expect("decode a blob") {
                if let Some(&(k, id, ms, _)) = clip::metas(&block).first() {
                    tail = Some(stitch.block(Some((k, id, ms)), None, None));
                }
            }
        }
        if let Some(h) = tail.unwrap_or_else(|| stitch.end()) {
            stats.kept += 1;
            order.add(&history::Ends::of(&h));
            consume(map(h));
        }
        stats.backwards += stitch.backwards;
        stats.not_increasing = order.not_increasing;
        stats
    }
}

// --- node places -------------------------------------------------------------------------------------

/// every node's place, found by id: in memory, sorted by id, as the file gives them (right up to a country), or
/// in a file by id (nodefile.rs: the planet's way, 8 bytes an id)
#[derive(Default)]
struct MemPlaces {
    ids: Vec<i64>,
    lat: Vec<i32>,
    lon: Vec<i32>,
}

enum Places {
    Mem(MemPlaces),
    File(NodeMap),
}

impl Places {
    fn get(&self, id: i64) -> Option<(i32, i32)> {
        match self {
            Places::Mem(m) => m.ids.binary_search(&id).ok().map(|i| (m.lat[i], m.lon[i])),
            Places::File(f) => f.get(id),
        }
    }

    /// no pass needs them any more: the memory given back, the file deleted
    fn done(self) {
        if let Places::File(f) = self {
            f.delete();
        }
    }
}

/// a bit per node id: tagged
#[derive(Default)]
struct Bits(Vec<u64>);

impl Bits {
    fn set(&mut self, id: i64) {
        let w = (id >> 6) as usize;
        if w >= self.0.len() {
            self.0.resize(w + 1, 0);
        }
        self.0[w] |= 1 << (id & 63);
    }
    fn get(&self, id: i64) -> bool {
        self.0.get((id >> 6) as usize).is_some_and(|w| w >> (id & 63) & 1 == 1)
    }
}

// --- records -----------------------------------------------------------------------------------------

/// a node's record: id, place, then version, timestamp and tags if it is tagged
fn node_body(o: &mut Vec<u8>, id: i64, lat: i32, lon: i32, attrs: Option<(i32, i64, &[u8])>) {
    pi64(o, id);
    pi32(o, lat);
    pi32(o, lon);
    match attrs {
        None => o.push(0),
        Some((ver, ts, tags)) => {
            o.push(1);
            pi32(o, ver);
            pi64(o, ts);
            p32(o, tags.len() as u32);
            o.extend_from_slice(tags);
        }
    }
}

struct WayRec<'a> {
    id: i64,
    ver: i32,
    ts: i64,
    refs: Vec<i64>,
    /// per ref its place; lat ABSENT: no node in the file
    pl: Vec<(i32, i32)>,
    tags: &'a [u8],
}

/// a way's record: id, version, timestamp, the count of refs; the refs, their latitudes and their longitudes (a
/// ref with no node: latitude ABSENT, longitude 0), each run as differences in varints; the tags. `pl` is per ref.
fn way_body(o: &mut Vec<u8>, id: i64, ver: i32, ts: i64, refs: &[i64], pl: &[Option<(i32, i32)>], tags: &[u8]) {
    pi64(o, id);
    pi32(o, ver);
    pi64(o, ts);
    p32(o, refs.len() as u32);
    let mut prev = 0i64;
    for &r in refs {
        pvar(o, r.wrapping_sub(prev));
        prev = r;
    }
    prev = 0;
    for p in pl {
        let lat = p.map_or(ABSENT, |p| p.0) as i64;
        pvar(o, lat - prev);
        prev = lat;
    }
    prev = 0;
    for p in pl {
        let lon = p.map_or(0, |p| p.1) as i64;
        pvar(o, lon - prev);
        prev = lon;
    }
    p32(o, tags.len() as u32);
    o.extend_from_slice(tags);
}

/// what a way's record took before its refs were coded (16 bytes a ref): the cut budget and the spill files'
/// sizes are still counted in these bytes, which is what the bucket phase's memory was measured against
fn way_units(n_refs: usize, tags: usize) -> usize {
    28 + 16 * n_refs + tags
}

fn way_rec(body: &[u8]) -> WayRec<'_> {
    let mut c = Cur::new(body);
    let (id, ver, ts, n) = (c.i64(), c.i32(), c.i64(), c.u32() as usize);
    // the refs, then their latitudes, then their longitudes: each the difference from the one before, as a varint
    let mut refs = Vec::with_capacity(n);
    let mut prev = 0i64;
    for _ in 0..n {
        prev = prev.wrapping_add(c.var());
        refs.push(prev);
    }
    let mut pl = vec![(0i32, 0i32); n];
    prev = 0;
    for p in pl.iter_mut() {
        prev += c.var();
        p.0 = prev as i32;
    }
    prev = 0;
    for p in pl.iter_mut() {
        prev += c.var();
        p.1 = prev as i32;
    }
    let tl = c.u32() as usize;
    WayRec { id, ver, ts, refs, pl, tags: c.bytes(tl) }
}

/// a bucket's records as a clip in memory: its nodes are the placed nodes of its ways and its node records
fn clip_of(data: &[u8], recs: &[(u8, usize, usize)]) -> Clip {
    let mut c = Clip::new();
    let mut nodes: Vec<(i64, i32, i32)> = Vec::new();
    let mut tagged: Vec<(i64, usize, usize)> = Vec::new();
    let mut ways: Vec<(i64, usize, usize)> = Vec::new();
    let mut rels: Vec<(i64, usize, usize)> = Vec::new();
    for &(kind, a, b) in recs {
        let body = &data[a..b];
        let id = i64::from_le_bytes(body[0..8].try_into().unwrap());
        match kind {
            KIND_NODE => {
                let mut cu = Cur::new(body);
                let (id, lat, lon) = (cu.i64(), cu.i32(), cu.i32());
                nodes.push((id, lat, lon));
                if cu.u8() == 1 {
                    tagged.push((id, a, b));
                }
            }
            KIND_WAY => ways.push((id, a, b)),
            _ => rels.push((id, a, b)),
        }
    }
    ways.sort_unstable();
    ways.dedup_by_key(|w| w.0);
    for &(_, a, b) in &ways {
        let w = way_rec(&data[a..b]);
        c.wid.push(w.id);
        c.w_ver.push(w.ver);
        c.w_ts.push(w.ts);
        for (i, &r) in w.refs.iter().enumerate() {
            if w.pl[i].0 != ABSENT {
                nodes.push((r, w.pl[i].0, w.pl[i].1));
            }
        }
        c.wref_ids.extend_from_slice(&w.refs);
        c.woffs.push(c.wref_ids.len() as u64);
        c.w_tags.extend_from_slice(w.tags);
        c.w_toff.push(c.w_tags.len() as u64);
    }
    nodes.sort_unstable();
    nodes.dedup_by_key(|n| n.0);
    c.nid = nodes.iter().map(|n| n.0).collect();
    c.lat7 = nodes.iter().map(|n| n.1).collect();
    c.lon7 = nodes.iter().map(|n| n.2).collect();
    tagged.sort_unstable();
    tagged.dedup_by_key(|t| t.0);
    for &(id, a, b) in &tagged {
        let mut cu = Cur::new(&data[a..b]);
        cu.bytes(17);
        c.tn_row.push(c.nid.binary_search(&id).unwrap() as u32);
        c.tn_ver.push(cu.i32());
        c.tn_ts.push(cu.i64());
        let tl = cu.u32() as usize;
        c.tn_tags.extend_from_slice(cu.bytes(tl));
        c.tn_toff.push(c.tn_tags.len() as u64);
    }
    rels.sort_unstable();
    rels.dedup_by_key(|r| r.0);
    for &(_, a, b) in &rels {
        let mut cu = Cur::new(&data[a..b]);
        c.rid.push(cu.i64());
        c.r_ver.push(cu.i32());
        c.r_ts.push(cu.i64());
        for _ in 0..cu.u32() {
            c.mtype.push(cu.u8() as i8);
            c.mref.push(cu.i64());
            let rl = cu.u32() as usize;
            c.roles.extend_from_slice(cu.bytes(rl));
            c.r_roff.push(c.roles.len() as u64);
        }
        c.roffs.push(c.mref.len() as u64);
        let tl = cu.u32() as usize;
        c.r_tags.extend_from_slice(cu.bytes(tl));
        c.r_toff.push(c.r_tags.len() as u64);
    }
    c.r_kept = vec![true; c.rid.len()];
    c
}

// --- the passes --------------------------------------------------------------------------------------

/// a block of nodes, mapped: places, and the records to spill
struct NodeOut {
    ids: Vec<i64>,
    lat: Vec<i32>,
    lon: Vec<i32>,
    /// with a node file: the places as its runs, and how many nodes
    runs: Vec<(i64, Vec<u8>)>,
    n: u64,
    bodies: Vec<u8>,
    /// (home bucket, body start, body end, tagged, id)
    list: Vec<(u32, u32, u32, bool, i64)>,
    /// member nodes of kept relations in this block: (index among the member nodes, tile key)
    member: Vec<(usize, u32)>,
}

/// a block of ways, mapped
struct WayOut {
    bodies: Vec<u8>,
    /// (bucket, body start, body end, the record's bytes before its refs were coded)
    list: Vec<(u32, u32, u32, u32)>,
    /// ways read back from their records and found equal (the self-check)
    checked: u64,
    wt: Vec<(i64, u32)>,
    needs: Vec<(i64, u32)>,
    /// member ways of kept relations: (id, body start, body end, where its keys start in `keys`)
    members: Vec<(i64, u32, u32, u32)>,
    keys: Vec<u32>,
    refs: u64,
}

/// `at`: the file is a history file, cut as it was at that date (seconds)
/// `nodes`: the node places go into this file by id, not into memory (and is it sparse);
/// `fz`: a spill file is a cell of this zoom (at most `bz`: a file a bucket); `budget`: the spill files cut at
/// once hold at most this many bytes of records, or are one file
pub fn cut(pbf: &Path, out: &Path, day: &str, z: u32, bz: u32, fz: u32, budget: u64, keep_spill: bool, at: Option<i64>, nodes: Option<(&Path, bool)>) {
    let t0 = Instant::now();
    let geo = Geo { z, bz, fz };
    let nt = (1u64 << z) as f64;
    let mut phases: Vec<(&str, f64)> = Vec::new();
    let mut t = Instant::now();
    let lap = |name: &'static str, t: &mut Instant, phases: &mut Vec<(&str, f64)>| {
        let s = t.elapsed().as_secs_f64();
        let (ws, peak, private) = crate::ptime::memory();
        log(&format!("  {name}: {s:.1} s; working set {ws:.2} GiB (peak so far {peak:.2}), private {private:.2} GiB"));
        phases.push((name, s));
        *t = Instant::now();
    };
    fs::create_dir_all(out).unwrap();
    let work = out.join("work");
    let mut spill = Spill::new(&work.join("spill"), geo);

    let blobs = Blobs::index(pbf);
    let nb = blobs.offs.len();
    log(&format!("{nb} blobs; ways from blob {}, relations from blob {}", blobs.first_way, blobs.first_rel));
    lap("index", &mut t, &mut phases);

    // pass 0: the relations, whole; the member ways and member nodes of the kept ones
    let mut rel = Clip::new();
    let mut hist = history::Stats::default();
    let mut seen = |s: history::Stats| {
        hist.versions += s.versions;
        hist.kept += s.kept;
        hist.backwards += s.backwards;
        // the rule gave an object twice (its timestamps run backwards around the date): no store of that
        assert!(s.not_increasing == 0, "{} objects are given twice or out of order at this date: the history file's timestamps run backwards around it", s.not_increasing);
    };
    // only the block's relations (a block shared with ways gives its ways to pass 2), and of them only the kept:
    // the others are counted and let go
    let (mut n_rels, mut last_rel) = (0usize, i64::MIN);
    seen(blobs.each_at(
        blobs.first_rel,
        nb,
        at,
        |p| {
            let increasing = p.rid.windows(2).all(|w| w[0] < w[1]);
            (clip::kept_relations(&p), p.rid.len(), p.rid.first().copied(), p.rid.last().copied(), increasing)
        },
        |(q, n, first, last, increasing)| {
            assert!(increasing && first.is_none_or(|f| f > last_rel), "relation ids are not strictly increasing: the file is not sorted");
            last_rel = last.unwrap_or(last_rel);
            n_rels += n;
            rel.append(&q);
        },
    ));
    rel.keep_relations();
    let nr = rel.rid.len();
    let (mut member_ways, mut member_nodes): (Vec<i64>, Vec<i64>) = (Vec::new(), Vec::new());
    for r in 0..nr {
        if rel.r_kept[r] {
            for m in rel.roffs[r] as usize..rel.roffs[r + 1] as usize {
                match rel.mtype[m] {
                    0 => member_nodes.push(rel.mref[m]),
                    1 => member_ways.push(rel.mref[m]),
                    _ => {}
                }
            }
        }
    }
    member_ways.par_sort_unstable();
    member_ways.dedup();
    member_nodes.par_sort_unstable();
    member_nodes.dedup();
    let kept: Vec<usize> = (0..nr).filter(|&r| rel.r_kept[r]).collect();
    log(&format!(
        "pass 0: {n_rels} relations, {} kept, with {} member ways and {} member nodes",
        kept.len(),
        member_ways.len(),
        member_nodes.len()
    ));
    lap("pass0Relations", &mut t, &mut phases);

    // pass 1: the nodes' places; tagged nodes and kept relations' member nodes to their home buckets
    let mut mem = MemPlaces::default();
    let mut node_writer = nodes.map(|(path, sparse)| NodeWriter::create(path, sparse));
    let use_file = node_writer.is_some();
    let mut n_nodes = 0u64;
    let mut tagged_bit = Bits::default();
    let mut mn_key = vec![NO_KEY; member_nodes.len()];
    let tagged_path = work.join("tagged.bin");
    let mut tagged_file = BufWriter::with_capacity(1 << 22, File::create(&tagged_path).unwrap());
    let mut n_tagged = 0u64;
    seen(blobs.each_at(
        0,
        (blobs.first_way + 1).min(nb),
        at,
        |p| {
            let mut o = NodeOut { ids: Vec::new(), lat: Vec::new(), lon: Vec::new(), runs: Vec::new(), n: p.nid.len() as u64, bodies: Vec::new(), list: Vec::new(), member: Vec::new() };
            let (mut tj, mut toff) = (0usize, 0usize);
            for i in 0..p.nid.len() {
                let (id, lat, lon) = (p.nid[i], p.lat7[i], p.lon7[i]);
                let tagged = tj < p.tn_local.len() && p.tn_local[tj] as usize == i;
                let member = member_nodes.binary_search(&id).ok();
                if !tagged && member.is_none() {
                    continue;
                }
                let (fx, fy) = frac_xy(lat, lon, nt);
                let key = key_of(fx.floor() as i64, fy.floor() as i64, z);
                let a = o.bodies.len() as u32;
                if tagged {
                    let tl = p.tn_tlen[tj] as usize;
                    node_body(&mut o.bodies, id, lat, lon, Some((p.tn_ver[tj], p.tn_ts[tj], &p.tn_tags[toff..toff + tl])));
                    toff += tl;
                    tj += 1;
                } else {
                    node_body(&mut o.bodies, id, lat, lon, None);
                }
                o.list.push((geo.bucket(key), a, o.bodies.len() as u32, tagged, id));
                if let Some(m) = member {
                    o.member.push((m, key));
                }
            }
            if use_file {
                o.runs = nodefile::runs(&p.nid, &p.lat7, &p.lon7);
            } else {
                (o.ids, o.lat, o.lon) = (p.nid, p.lat7, p.lon7);
            }
            o
        },
        |o| {
            for &(bucket, a, b, tagged, id) in &o.list {
                let body = &o.bodies[a as usize..b as usize];
                spill.add(KIND_NODE, bucket, body);
                if tagged {
                    tagged_bit.set(id);
                    tagged_file.write_all(body).unwrap();
                    n_tagged += 1;
                }
            }
            for &(m, key) in &o.member {
                mn_key[m] = key;
            }
            n_nodes += o.n;
            match node_writer.as_mut() {
                Some(w) => w.add(&o.runs),
                None => {
                    mem.ids.extend_from_slice(&o.ids);
                    mem.lat.extend_from_slice(&o.lat);
                    mem.lon.extend_from_slice(&o.lon);
                }
            }
        },
    ));
    tagged_file.flush().unwrap();
    drop(tagged_file);
    assert!(mem.ids.windows(2).all(|w| w[0] < w[1]), "node ids are not strictly increasing: the file is not sorted");
    let places = match node_writer {
        Some(w) => {
            assert!(w.out_of_order == 0, "node ids are not increasing: the file is not sorted");
            let (seeks, top) = (w.seeks, w.top());
            // what the file took of the disk, as the free space says (other writers on the disk are in it too)
            let took = match (w.free_at_start, w.free()) {
                (Some(a), Some(b)) => format!("{:.1} GiB less free on its disk than before it", (a as f64 - b as f64) / (1u64 << 30) as f64),
                _ => "free space not read".to_string(),
            };
            let m = w.finish(false);
            log(&format!("node file: {:.2} GiB long, highest id {top}, {seeks} seeks; {took}", m.bytes as f64 / (1u64 << 30) as f64));
            Places::File(m)
        }
        None => Places::Mem(mem),
    };
    log(&format!("pass 1: {n_nodes} nodes, {n_tagged} tagged"));
    lap("pass1Nodes", &mut t, &mut phases);

    // pass 2: the ways, with their nodes' places, to every bucket they cross
    let mut wtiles = npy::PairWriter::new(&out.join("wtiles-0000.npy"));
    let mut needs: Vec<(i64, u32)> = Vec::new();
    let member_path = work.join("member-ways.bin");
    let mut member_file = BufWriter::with_capacity(1 << 22, File::create(&member_path).unwrap());
    // the member ways found, in id order: where each one's record is, and its tiles
    let (mut mw_id, mut mw_pos, mut mw_koff, mut mw_keys): (Vec<i64>, Vec<(u64, u32)>, Vec<u32>, Vec<u32>) =
        (Vec::new(), Vec::new(), vec![0], Vec::new());
    let mut member_at = 0u64;
    let (mut n_ways, mut n_refs, mut last_way) = (0u64, 0u64, i64::MIN);
    // TILESTORE_TEST_WAY_CODING: every way is read back from its record and compared with what went in
    let self_check = std::env::var_os("TILESTORE_TEST_WAY_CODING").is_some();
    let mut n_checked = 0u64;
    seen(blobs.each_at(
        blobs.first_way,
        (blobs.first_rel + 1).min(nb),
        at,
        |p| {
            let mut o = WayOut { bodies: Vec::new(), list: Vec::new(), checked: 0, wt: Vec::new(), needs: Vec::new(), members: Vec::new(), keys: Vec::new(), refs: 0 };
            let mut pl: Vec<Option<(i32, i32)>> = Vec::new();
            let mut keys: Vec<u32> = Vec::new();
            let mut buckets: Vec<u32> = Vec::new();
            let (mut roff, mut toff) = (0usize, 0usize);
            for w in 0..p.wid.len() {
                let refs = &p.w_refs[roff..roff + p.w_nref[w] as usize];
                roff += refs.len();
                let tags = &p.w_tags[toff..toff + p.w_tlen[w] as usize];
                toff += tags.len();
                pl.clear();
                pl.extend(refs.iter().map(|&r| places.get(r)));
                keys_of_way(&pl, z, &mut keys);
                o.refs += refs.len() as u64;
                o.wt.extend(keys.iter().map(|&k| (p.wid[w], k)));
                let a = o.bodies.len() as u32;
                way_body(&mut o.bodies, p.wid[w], p.w_ver[w], p.w_ts[w], refs, &pl, tags);
                let b = o.bodies.len() as u32;
                if self_check {
                    let r = way_rec(&o.bodies[a as usize..b as usize]);
                    let same = r.id == p.wid[w]
                        && r.ver == p.w_ver[w]
                        && r.ts == p.w_ts[w]
                        && r.refs == refs
                        && r.tags == tags
                        && r.pl.iter().zip(&pl).all(|(x, y)| *x == y.unwrap_or((ABSENT, 0)));
                    assert!(same && r.pl.len() == pl.len(), "way {} does not come back from its record as it went in", p.wid[w]);
                    o.checked += 1;
                }
                let units = way_units(refs.len(), tags.len()) as u32;
                buckets.clear();
                buckets.extend(keys.iter().map(|&k| geo.bucket(k)));
                buckets.sort_unstable();
                buckets.dedup();
                for &bk in &buckets {
                    o.list.push((bk, a, b, units));
                }
                // a tagged node of this way at home in another bucket: that bucket's tiles give it its tags too
                for (i, &r) in refs.iter().enumerate() {
                    if let Some((lat, lon)) = pl[i] {
                        if tagged_bit.get(r) {
                            let (fx, fy) = frac_xy(lat, lon, nt);
                            let home = geo.bucket(key_of(fx.floor() as i64, fy.floor() as i64, z));
                            for &bk in &buckets {
                                if bk != home {
                                    o.needs.push((r, bk));
                                }
                            }
                        }
                    }
                }
                if member_ways.binary_search(&p.wid[w]).is_ok() {
                    o.members.push((p.wid[w], a, b, o.keys.len() as u32));
                    o.keys.extend_from_slice(&keys);
                }
            }
            o
        },
        |o| {
            for &(bucket, a, b, units) in &o.list {
                spill.add_as(KIND_WAY, bucket, &o.bodies[a as usize..b as usize], units as usize);
            }
            n_checked += o.checked;
            for &(id, k) in &o.wt {
                assert!(id >= last_way, "way ids are not increasing: the file is not sorted");
                if id != last_way {
                    n_ways += 1;
                }
                last_way = id;
                wtiles.push(id, k as i64);
            }
            needs.extend_from_slice(&o.needs);
            for (i, &(id, a, b, k0)) in o.members.iter().enumerate() {
                let body = &o.bodies[a as usize..b as usize];
                member_file.write_all(body).unwrap();
                mw_id.push(id);
                mw_pos.push((member_at, body.len() as u32));
                member_at += body.len() as u64;
                let k1 = o.members.get(i + 1).map(|m| m.3 as usize).unwrap_or(o.keys.len());
                mw_keys.extend_from_slice(&o.keys[k0 as usize..k1]);
                mw_koff.push(mw_keys.len() as u32);
            }
            n_refs += o.refs;
        },
    ));
    if at.is_some() {
        log(&format!("history: {} versions read over the three passes, {} at the date, {} older than the one before", hist.versions, hist.kept, hist.backwards));
    }
    member_file.flush().unwrap();
    drop(member_file);
    let way_copies = wtiles.finish();
    log(&format!(
        "pass 2: {n_ways} ways with a tile, {n_refs} refs, {way_copies} (way, tile) pairs, {} needs, {} member ways found",
        needs.len(),
        mw_id.len()
    ));
    if self_check {
        log(&format!("self-check: {n_checked} ways read back from their records, all as they went in"));
    }
    places.done();
    lap("pass2Ways", &mut t, &mut phases);

    // the needs: each tagged node's record, to the buckets that hold a way of it and are not its home
    needs.par_sort_unstable();
    needs.dedup();
    // TILESTORE_TEST_NO_NEEDS: a wrong cut on purpose, to show that the comparison with the in-memory cut fails
    if std::env::var_os("TILESTORE_TEST_NO_NEEDS").is_some() {
        log("TEST: the needs are dropped; this store is wrong on purpose");
        needs.clear();
    }
    {
        // the needs and the tagged-node file are both in id order: one read of the file, no index of it. A
        // record: id, place, 1, version, timestamp, the tags' length (at byte 29), the tags.
        let mut f = BufReader::with_capacity(1 << 22, File::open(&tagged_path).unwrap());
        let mut body = vec![0u8; 33];
        let mut j = 0;
        while j < needs.len() {
            body.resize(33, 0);
            f.read_exact(&mut body).expect("a needed node is tagged");
            let id = i64::from_le_bytes(body[0..8].try_into().unwrap());
            let tl = u32::from_le_bytes(body[29..33].try_into().unwrap()) as usize;
            body.resize(33 + tl, 0);
            f.read_exact(&mut body[33..]).unwrap();
            assert!(needs[j].0 >= id, "a needed node is tagged");
            while j < needs.len() && needs[j].0 == id {
                spill.add(KIND_NODE, needs[j].1, &body);
                j += 1;
            }
        }
    }
    let n_needs = needs.len();
    drop(needs);

    // the kept relations: their tiles, their lines of the relation-tiles index, their records to their buckets
    let mut rtiles = npy::PairWriter::new(&out.join("rtiles-0000.npy"));
    {
        let mut body = Vec::new();
        let mut keys: Vec<u32> = Vec::new();
        let mut buckets: Vec<u32> = Vec::new();
        for &r in &kept {
            keys.clear();
            for m in rel.roffs[r] as usize..rel.roffs[r + 1] as usize {
                match rel.mtype[m] {
                    0 => {
                        if let Ok(i) = member_nodes.binary_search(&rel.mref[m]) {
                            if mn_key[i] != NO_KEY {
                                keys.push(mn_key[i]);
                            }
                        }
                    }
                    1 => {
                        if let Ok(i) = mw_id.binary_search(&rel.mref[m]) {
                            keys.extend_from_slice(&mw_keys[mw_koff[i] as usize..mw_koff[i + 1] as usize]);
                        }
                    }
                    _ => {}
                }
            }
            keys.sort_unstable();
            keys.dedup();
            if keys.is_empty() {
                continue;
            }
            for &k in &keys {
                rtiles.push(rel.rid[r], k as i64);
            }
            body.clear();
            pi64(&mut body, rel.rid[r]);
            pi32(&mut body, rel.r_ver[r]);
            pi64(&mut body, rel.r_ts[r]);
            p32(&mut body, (rel.roffs[r + 1] - rel.roffs[r]) as u32);
            for m in rel.roffs[r] as usize..rel.roffs[r + 1] as usize {
                body.push(rel.mtype[m] as u8);
                pi64(&mut body, rel.mref[m]);
                let role = &rel.roles[rel.r_roff[m] as usize..rel.r_roff[m + 1] as usize];
                p32(&mut body, role.len() as u32);
                body.extend_from_slice(role);
            }
            let tags = &rel.r_tags[rel.r_toff[r] as usize..rel.r_toff[r + 1] as usize];
            p32(&mut body, tags.len() as u32);
            body.extend_from_slice(tags);
            buckets.clear();
            buckets.extend(keys.iter().map(|&k| geo.bucket(k)));
            buckets.sort_unstable();
            buckets.dedup();
            for &bk in &buckets {
                spill.add(KIND_REL, bk, &body);
            }
        }
    }
    rtiles.finish();
    spill.finish();
    log(&format!(
        "spill: {} files, {:.2} GiB raw, {:.2} GiB written; {:.2} bytes a ref written; {} appends ({} times every buffer at once); the pass waited {:.1} s handing them to {} workers, which compressed and wrote for {:.1} s together",
        spill.files.len(),
        spill.raw as f64 / (1u64 << 30) as f64,
        spill.written as f64 / (1u64 << 30) as f64,
        spill.written as f64 / n_refs.max(1) as f64,
        spill.flushes,
        spill.flush_alls,
        spill.flush_secs,
        Spill::WORKERS,
        spill.worker_secs
    ));
    {
        let g = |b: u64| b as f64 / (1u64 << 30) as f64;
        let k = spill.kinds;
        log(&format!(
            "spill by kind, before compression: {} node records {:.2} GiB; {} way records {:.2} GiB with {} refs; {} relation records {:.2} GiB",
            k[0].0, g(k[0].1), k[1].0, g(k[1].1), spill.way_refs, k[2].0, g(k[2].1)
        ));
    }
    lap("needsAndRelations", &mut t, &mut phases);

    // the relation store: per kept relation, its member ways whole with their nodes' places, from the member-way file
    let mut ridx: Vec<(i64, i32, i64, i32)> = Vec::with_capacity(kept.len());
    let mut roff: i64 = 0;
    let mut n_member_ways: u64 = 0;
    {
        let mf = File::open(&member_path).unwrap();
        let mut f = BufWriter::with_capacity(1 << 22, File::create(out.join("rel-0000.bin")).unwrap());
        for chunk in kept.chunks(8192) {
            let bufs: Vec<(Vec<u8>, usize)> = chunk
                .par_iter()
                .map(|&r| {
                    let mut wi: Vec<usize> = Vec::new();
                    for m in rel.roffs[r] as usize..rel.roffs[r + 1] as usize {
                        if rel.mtype[m] == 1 {
                            if let Ok(i) = mw_id.binary_search(&rel.mref[m]) {
                                wi.push(i);
                            }
                        }
                    }
                    wi.sort_unstable();
                    wi.dedup();
                    let bodies: Vec<Vec<u8>> = wi
                        .iter()
                        .map(|&i| {
                            let mut b = vec![0u8; mw_pos[i].1 as usize];
                            mf.seek_read(&mut b, mw_pos[i].0).unwrap();
                            b
                        })
                        .collect();
                    let ways: Vec<WayRec> = bodies.iter().map(|b| way_rec(b)).collect();
                    let mut nodes: Vec<(i64, i32, i32)> = Vec::new();
                    for w in &ways {
                        for (i, &rf) in w.refs.iter().enumerate() {
                            if w.pl[i].0 != ABSENT {
                                nodes.push((rf, w.pl[i].0, w.pl[i].1));
                            }
                        }
                    }
                    nodes.sort_unstable();
                    nodes.dedup_by_key(|n| n.0);
                    let mut tl = Vec::new();
                    let mut tb = Vec::new();
                    for w in &ways {
                        tl.push(w.tags.len() as i32);
                        tb.extend_from_slice(w.tags);
                    }
                    let cols = vec![
                        Col::I64(delta64(ways.iter().map(|w| w.id))),
                        Col::I32(ways.iter().map(|w| w.ver).collect()),
                        Col::I64(ways.iter().map(|w| w.ts).collect()),
                        Col::I32(ways.iter().map(|w| w.refs.len() as i32).collect()),
                        Col::I64(delta64(ways.iter().flat_map(|w| w.refs.iter().copied()))),
                        Col::I32(tl),
                        Col::U8(tb),
                        Col::I64(delta64(nodes.iter().map(|n| n.0))),
                        Col::I32(delta32(nodes.iter().map(|n| n.1))),
                        Col::I32(delta32(nodes.iter().map(|n| n.2))),
                    ];
                    (pack_cols(&cols), wi.len())
                })
                .collect();
            for (&r, (b, n)) in chunk.iter().zip(&bufs) {
                f.write_all(b).unwrap();
                ridx.push((rel.rid[r], 0, roff, b.len() as i32));
                roff += b.len() as i64;
                n_member_ways += *n as u64;
            }
        }
        f.flush().unwrap();
    }
    npy::save_idx(&out.join("relidx-0000.npy"), &ridx);
    lap("relationStore", &mut t, &mut phases);
    // nothing of the passes is needed by the buckets
    drop(rel);
    drop((member_ways, member_nodes, mn_key, tagged_bit));
    drop((mw_id, mw_pos, mw_koff, mw_keys));

    // the buckets: each spill file's buckets cut in memory, only their own tiles kept
    let mut idx: Vec<(i64, i32, i64, i32)> = Vec::new();
    let mut off: i64 = 0;
    let mut copies = [0usize; 3];
    let (mut n_buckets, mut largest, mut largest_group, mut n_groups) = (0usize, 0usize, 0u64, 0usize);
    // the working set through this phase, looked at every 50 ms: the process's own peak cannot be reset, and
    // the passes before may have set it
    let stop = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false));
    let sampler = {
        let stop = stop.clone();
        std::thread::spawn(move || {
            let mut top = 0f64;
            while !stop.load(std::sync::atomic::Ordering::Relaxed) {
                top = top.max(crate::ptime::memory().0);
                std::thread::sleep(std::time::Duration::from_millis(50));
            }
            top
        })
    };
    {
        let mut f = BufWriter::with_capacity(1 << 22, File::create(out.join("pack-0000.bin")).unwrap());
        let files: Vec<u32> = spill.files.iter().copied().collect();
        let mut at_file = 0;
        while at_file < files.len() {
            // the files cut at once: as many as the budget holds, one at least
            let mut end = at_file;
            let mut sum = 0u64;
            while end < files.len() && (end == at_file || sum + spill.sizes[&files[end]] <= budget) {
                sum += spill.sizes[&files[end]];
                end += 1;
            }
            let group = &files[at_file..end];
            at_file = end;
            largest = largest.max(group.iter().map(|f| spill.sizes[f] as usize).max().unwrap());
            largest_group = largest_group.max(sum);
            let cut: Vec<(usize, Vec<(u32, Vec<u8>, [usize; 3])>)> = group
                .par_iter()
                .map(|&file| {
                    let data = spill.load(file);
                    let mut by: HashMap<u32, Vec<(u8, usize, usize)>> = HashMap::new();
                    let mut c = Cur::new(&data);
                    while !c.done() {
                        let (kind, bucket, len) = (c.u8(), c.u32(), c.u32() as usize);
                        by.entry(bucket).or_default().push((kind, c.p, c.p + len));
                        c.p += len;
                    }
                    let mut buckets: Vec<(u32, Vec<(u8, usize, usize)>)> = by.into_iter().collect();
                    buckets.sort_unstable_by_key(|b| b.0);
                    let tiles: Vec<Vec<(u32, Vec<u8>, [usize; 3])>> = buckets
                        .par_iter()
                        .map(|(bucket, recs)| {
                            let mut c = clip_of(&data, recs);
                            c.place(z);
                            let p = pairs::build(&c, z);
                            let keys: Vec<u32> = p.keys().into_iter().filter(|&k| geo.bucket(k) == *bucket).collect();
                            keys.par_iter()
                                .map(|&k| {
                                    let (buf, n) = p.payload(&c, k);
                                    (k, buf, n)
                                })
                                .collect()
                        })
                        .collect();
                    (buckets.len(), tiles.into_iter().flatten().collect())
                })
                .collect();
            for (nb, tiles) in cut {
                n_buckets += nb;
                for (k, buf, n) in tiles {
                    f.write_all(&buf).unwrap();
                    idx.push((k as i64, 0, off, buf.len() as i32));
                    off += buf.len() as i64;
                    for i in 0..3 {
                        copies[i] += n[i];
                    }
                }
            }
            n_groups += 1;
            if !keep_spill {
                for &file in group {
                    fs::remove_file(spill.path(file)).unwrap();
                }
            }
        }
        f.flush().unwrap();
    }
    idx.par_sort_unstable();
    assert!(idx.windows(2).all(|w| w[0].0 < w[1].0), "a tile was written by two buckets");
    npy::save_idx(&out.join("idx-0000.npy"), &idx);
    stop.store(true, std::sync::atomic::Ordering::Relaxed);
    let buckets_top = sampler.join().unwrap();
    log(&format!("buckets: {n_groups} groups of spill files, the largest {:.2} GiB of records; working set at most {buckets_top:.2} GiB in this phase", largest_group as f64 / (1u64 << 30) as f64));
    lap("buckets", &mut t, &mut phases);
    if !keep_spill {
        let _ = fs::remove_dir_all(&work);
    }

    let secs = t0.elapsed().as_secs_f64();
    let extra = format!(
        "\n   \"bucketZ\": {bz},\n   \"buckets\": {n_buckets},\n   \"spillFiles\": {},\n   \"spillRawBytes\": {},\n   \"spillBytes\": {},\n   \"largestSpillFileRawBytes\": {largest},\n   \"fileZ\": {fz},\n   \"cutBudgetBytes\": {budget},\n   \"cutGroups\": {n_groups},\n   \"largestCutGroupRawBytes\": {largest_group},\n   \"peakWorkingSetGiB\": {:.2},\n   \"bucketsWorkingSetGiB\": {:.2},\n   \"refs\": {n_refs},\n   \"needs\": {n_needs},",
        spill.files.len(),
        spill.raw,
        spill.written,
        crate::ptime::memory().1,
        buckets_top
    );
    write_meta(
        out,
        &Meta {
            z,
            day,
            from: pbf,
            by: "tilestore scut (Rust, streaming)",
            tiles: idx.len(),
            bytes: off,
            relations: kept.len(),
            member_ways: n_member_ways,
            rel_bytes: roff,
            seconds: secs,
            phases: &phases,
            copies,
            extra,
        },
    );
    log(&format!(
        "scut {day}: {} tiles in {n_buckets} buckets (z{bz}), {:.2} GiB; relation store {} relations, {n_member_ways} member ways, {:.0} MiB; {secs:.1} s in all",
        idx.len(),
        off as f64 / (1u64 << 30) as f64,
        kept.len(),
        roff as f64 / (1u64 << 20) as f64
    ));
}
