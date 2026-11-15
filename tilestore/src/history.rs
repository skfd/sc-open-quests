//! A history file (.osh.pbf) read at a date: of each object, the version that was current then, if it was not a
//! deletion. The rule is osmium's (`osmium time-filter FILE T`, DiffObject::is_visible_at): a version counts if
//! it is visible, its timestamp is at or before T, and the next version of the same object, if the file has
//! one, is after T. It looks only at a version and the one after it, so a block is decided on its own (on all
//! threads) but for its last version, which waits for the next block's first (`Stitch`, in the file's order).
//!
//!   tilestore at --pbf X.osh.pbf --at 2026-10-01T00:00:00Z [--out Y.osm.pbf] [--stamp T]
//!       the file at that date as a snapshot PBF, to hold against osmium's (tools/stream/tilecheck/pbfcmp.py);
//!       with no --out it is only read and counted
//!
//! Where a version is older than the one before it (timestamps running backwards) the rule can give two
//! versions of one object; `backwards` counts such pairs, and nothing here repairs them.

use crate::clip::Part;
use crate::pbf;
use crate::read::stamp_seconds;
use crate::stream::Blobs;
use std::fs::{self, File};
use std::io::{BufWriter, Write};
use std::path::Path;
use std::time::Instant;

/// (kind, id, timestamp in ms) of a version; kind 0 node, 1 way, 2 relation
pub type Key = (u8, i64, i64);

/// a block decided on its own
pub struct Sel {
    /// per version of the block: 0 not at the date, 1 at the date, 2 at the date unless the next block starts
    /// with a later version of it that is at or before the date (only the block's last version)
    pub dest: Vec<u8>,
    pub first: Option<Key>,
    pub last: Option<Key>,
    /// versions older than the one before them, inside the block
    pub backwards: u64,
}

pub fn select(meta: &[(u8, i64, i64, bool)], t_ms: i64) -> Sel {
    let n = meta.len();
    let mut dest = vec![0u8; n];
    let mut backwards = 0;
    for i in 0..n {
        let (k, id, ms, visible) = meta[i];
        let live = visible && ms <= t_ms;
        if i + 1 < n {
            let (k2, id2, ms2, _) = meta[i + 1];
            let same = k2 == k && id2 == id;
            if same && ms2 < ms {
                backwards += 1;
            }
            if live && !(same && ms2 <= t_ms) {
                dest[i] = 1;
            }
        } else if live {
            dest[i] = 2;
        }
    }
    let key = |m: &(u8, i64, i64, bool)| (m.0, m.1, m.2);
    Sel { dest, first: meta.first().map(key), last: meta.last().map(key), backwards }
}

/// the blocks' borders, in the file's order: holds a block's last version until the next block shows whether a
/// later version replaces it
pub struct Stitch<H> {
    t_ms: i64,
    held: Option<H>,
    last: Option<Key>,
    pub backwards: u64,
}

impl<H> Stitch<H> {
    pub fn new(t_ms: i64) -> Self {
        Stitch { t_ms, held: None, last: None, backwards: 0 }
    }

    /// the next block: its first and last versions, and its last version if `select` marked it 2. Gives back
    /// the block before's held version if it stands; that one comes before everything of this block.
    pub fn block(&mut self, first: Option<Key>, last: Option<Key>, held: Option<H>) -> Option<H> {
        // a block with nothing in it: the held version waits on
        let (k, id, ms) = first?;
        let mut out = self.held.take();
        if let Some((lk, lid, lms)) = self.last {
            if lk == k && lid == id {
                if ms < lms {
                    self.backwards += 1;
                }
                if ms <= self.t_ms {
                    out = None;
                }
            }
        }
        self.last = last;
        self.held = held;
        out
    }

    /// no block follows
    pub fn end(&mut self) -> Option<H> {
        self.last = None;
        self.held.take()
    }
}

#[derive(Default, Debug)]
pub struct Stats {
    pub versions: u64,
    pub kept: u64,
    pub backwards: u64,
}

/// a part's objects as PBF blobs, a kind at a time; and how many of each kind
fn blobs_of(p: &Part) -> (Vec<Vec<u8>>, [u64; 3]) {
    let mut out = Vec::new();
    // nodes
    let mut nodes: Vec<pbf::Node> = Vec::with_capacity(p.nid.len());
    let (mut tj, mut toff) = (0usize, 0usize);
    for i in 0..p.nid.len() {
        let mut tags: &[u8] = &[];
        if tj < p.tn_local.len() && p.tn_local[tj] as usize == i {
            let tl = p.tn_tlen[tj] as usize;
            tags = &p.tn_tags[toff..toff + tl];
            toff += tl;
            tj += 1;
        }
        nodes.push(pbf::Node { id: p.nid[i], lat7: p.lat7[i], lon7: p.lon7[i], version: p.n_ver[i], seconds: p.n_ts[i], tags });
    }
    for ch in nodes.chunks(pbf::PER_BLOCK) {
        out.push(pbf::blob("OSMData", &pbf::node_block(ch)));
    }
    // ways
    let mut ways: Vec<pbf::Way> = Vec::with_capacity(p.wid.len());
    let (mut roff, mut toff) = (0usize, 0usize);
    for w in 0..p.wid.len() {
        let (nr, tl) = (p.w_nref[w] as usize, p.w_tlen[w] as usize);
        ways.push(pbf::Way { id: p.wid[w], version: p.w_ver[w], seconds: p.w_ts[w], refs: &p.w_refs[roff..roff + nr], tags: &p.w_tags[toff..toff + tl] });
        roff += nr;
        toff += tl;
    }
    for ch in ways.chunks(pbf::PER_BLOCK) {
        out.push(pbf::blob("OSMData", &pbf::way_block(ch)));
    }
    // relations
    let role_len: Vec<i32> = p.m_rlen.iter().map(|&l| l as i32).collect();
    let mut rels: Vec<pbf::Relation> = Vec::with_capacity(p.rid.len());
    let (mut moff, mut rloff, mut toff) = (0usize, 0usize, 0usize);
    for r in 0..p.rid.len() {
        let (nm, tl) = (p.r_nmem[r] as usize, p.r_tlen[r] as usize);
        let rl: usize = p.m_rlen[moff..moff + nm].iter().map(|&l| l as usize).sum();
        rels.push(pbf::Relation {
            id: p.rid[r],
            version: p.r_ver[r],
            seconds: p.r_ts[r],
            mtype: &p.mtype[moff..moff + nm],
            mref: &p.mref[moff..moff + nm],
            roles: &p.roles[rloff..rloff + rl],
            role_len: &role_len[moff..moff + nm],
            tags: &p.r_tags[toff..toff + tl],
        });
        moff += nm;
        rloff += rl;
        toff += tl;
    }
    for ch in rels.chunks(pbf::PER_BLOCK) {
        out.push(pbf::blob("OSMData", &pbf::relation_block(ch)));
    }
    (out, [p.nid.len() as u64, p.wid.len() as u64, p.rid.len() as u64])
}

/// `tilestore at`: the history file at a date, as a snapshot PBF
pub fn at(pbf_path: &Path, at: &str, out: Option<&Path>, stamp: Option<&str>) {
    let t0 = Instant::now();
    let t = stamp_seconds(at);
    let blobs = Blobs::index(pbf_path);
    let t_index = t0.elapsed().as_secs_f64();
    // no --out: the file is read and decided, nothing is written (the reader's own speed)
    let mut f = out.map(|out| {
        if let Some(d) = out.parent() {
            fs::create_dir_all(d).unwrap();
        }
        let mut f = BufWriter::with_capacity(1 << 22, File::create(out).unwrap());
        f.write_all(&pbf::blob("OSMHeader", &pbf::header_block(stamp.map(stamp_seconds)))).unwrap();
        f
    });
    let write = f.is_some();
    let mut n = [0u64; 3];
    let mut bytes = 0u64;
    let (mut last, mut doubled) = ([i64::MIN; 3], 0u64);
    let st = blobs.each_at(
        0,
        blobs.offs.len(),
        Some(t),
        |p| {
            let ends = [(p.nid.first().copied(), p.nid.last().copied()), (p.wid.first().copied(), p.wid.last().copied()), (p.rid.first().copied(), p.rid.last().copied())];
            let inner = [&p.nid, &p.wid, &p.rid].map(|v| v.windows(2).filter(|w| w[0] >= w[1]).count() as u64);
            let made = if write { blobs_of(&p) } else { (Vec::new(), [p.nid.len() as u64, p.wid.len() as u64, p.rid.len() as u64]) };
            (made, ends, inner.iter().sum::<u64>())
        },
        |((bl, c), ends, inner)| {
            for b in &bl {
                f.as_mut().unwrap().write_all(b).unwrap();
                bytes += b.len() as u64;
            }
            // an object given twice (timestamps running backwards), or a file not in id order
            doubled += inner;
            for k in 0..3 {
                n[k] += c[k];
                if let (Some(a), Some(b)) = ends[k] {
                    if a <= last[k] {
                        doubled += 1;
                    }
                    last[k] = b;
                }
            }
        },
    );
    if let Some(f) = f.as_mut() {
        f.flush().unwrap();
    }
    let secs = t0.elapsed().as_secs_f64();
    let s = format!(
        "{{\"by\": \"tilestore at (Rust)\", \"at\": \"{at}\", \"versions\": {}, \"kept\": {}, \"nodes\": {}, \"ways\": {}, \"relations\": {}, \"backwards\": {}, \"notIncreasing\": {doubled}, \"pbfBytes\": {bytes}, \"secondsIndex\": {t_index:.2}, \"seconds\": {secs:.2}, \"versionsPerSecond\": {:.0}}}",
        st.versions,
        st.kept,
        n[0],
        n[1],
        n[2],
        st.backwards,
        st.versions as f64 / (secs - t_index).max(1e-9)
    );
    if let Some(out) = out {
        fs::write(format!("{}.json", out.display()), &s).unwrap();
    }
    eprintln!("at: {s}");
}

#[cfg(test)]
mod tests {
    use super::*;

    /// the rule on the whole file at once, as osmium applies it
    fn whole(meta: &[(u8, i64, i64, bool)], t: i64) -> Vec<usize> {
        (0..meta.len())
            .filter(|&i| {
                let (k, id, ms, vis) = meta[i];
                let next_after = match meta.get(i + 1) {
                    Some(&(k2, id2, ms2, _)) if k2 == k && id2 == id => ms2 > t,
                    _ => true,
                };
                vis && ms <= t && next_after
            })
            .collect()
    }

    /// the same through blocks cut at `cuts`, by select and Stitch; and the pairs running backwards
    fn blocks(meta: &[(u8, i64, i64, bool)], cuts: &[usize], t: i64) -> (Vec<usize>, u64) {
        let mut out = Vec::new();
        let mut st: Stitch<usize> = Stitch::new(t);
        let mut back = 0;
        let mut a = 0;
        for &b in cuts.iter().chain(std::iter::once(&meta.len())) {
            let sel = select(&meta[a..b], t);
            back += sel.backwards;
            let held = sel.dest.last().filter(|&&d| d == 2).map(|_| b - 1);
            out.extend(st.block(sel.first, sel.last, held));
            out.extend((a..b).filter(|&i| sel.dest[i - a] == 1));
            a = b;
        }
        out.extend(st.end());
        (out, back + st.backwards)
    }

    struct Rng(u64);
    impl Rng {
        fn next(&mut self, n: u64) -> u64 {
            self.0 = self.0.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            (self.0 >> 33) % n
        }
    }

    #[test]
    fn one_object_over_three_blocks() {
        // node 5: versions at 10, 20 (deleted), 30, 40; node 6 at 15
        let m = [(0, 5, 10, true), (0, 5, 20, false), (0, 5, 30, true), (0, 5, 40, true), (0, 6, 15, true)];
        for t in [5, 10, 15, 19, 20, 25, 30, 35, 40, 50] {
            let want = whole(&m, t);
            // every way of cutting five versions into blocks, empty blocks among them
            for mask in 0u32..16 {
                let cuts: Vec<usize> = (1..5).filter(|i| mask >> (i - 1) & 1 == 1).collect();
                assert_eq!(blocks(&m, &cuts, t).0, want, "t {t} cuts {cuts:?}");
                let mut twice = cuts.clone();
                twice.extend(cuts.iter().copied());
                twice.sort_unstable();
                assert_eq!(blocks(&m, &twice, t).0, want, "t {t} cuts {twice:?}");
            }
        }
        // at 20 the deletion is current: nothing of node 5; at 30 its third version, exactly on the second
        assert_eq!(whole(&m, 20), vec![4]);
        assert_eq!(whole(&m, 30), vec![2, 4]);
    }

    #[test]
    fn a_deletion_at_a_block_start_cancels_the_held_version() {
        let m = [(1, 7, 10, true), (1, 7, 20, false), (1, 8, 5, true)];
        assert_eq!(blocks(&m, &[1], 25).0, vec![2]);
        assert_eq!(blocks(&m, &[1], 15).0, vec![0, 2]);
        // the same id as another kind is another object
        let m = [(0, 7, 10, true), (1, 7, 20, false)];
        assert_eq!(blocks(&m, &[1], 25).0, vec![0]);
    }

    #[test]
    fn random_files_cut_at_random() {
        let mut r = Rng(42);
        let mut back_seen = 0;
        for round in 0..3000 {
            let mut m = Vec::new();
            let (mut kind, mut id) = (0u8, 0i64);
            for _ in 0..r.next(40) {
                id += 1 + r.next(3) as i64;
                if r.next(12) == 0 && kind < 2 {
                    kind += 1;
                    id = 1;
                }
                let mut ms = r.next(50) as i64;
                for _ in 0..1 + r.next(6) {
                    m.push((kind, id, ms, r.next(4) != 0));
                    // now and then the same second, or a step back
                    ms += match r.next(10) {
                        0 => 0,
                        1 => -(r.next(8) as i64),
                        _ => 1 + r.next(20) as i64,
                    };
                }
            }
            let mut cuts: Vec<usize> = (0..r.next(8)).map(|_| r.next(m.len() as u64 + 1) as usize).collect();
            cuts.sort_unstable();
            let t = r.next(120) as i64;
            let (got, back) = blocks(&m, &cuts, t);
            assert_eq!(got, whole(&m, t), "round {round} t {t} cuts {cuts:?} {m:?}");
            let want_back = m.windows(2).filter(|w| w[0].0 == w[1].0 && w[0].1 == w[1].1 && w[1].2 < w[0].2).count() as u64;
            assert_eq!(back, want_back, "round {round}");
            back_seen += back;
        }
        assert!(back_seen > 0);
    }
}
