//! The tile rule on a clip in memory (tilestore.py tile_pairs): which nodes, ways and relations each tile holds.
//! Used by the in-memory cut on a whole file and by the streaming cut on one bucket at a time.

use crate::clip::{Clip, NONE};
use crate::cols::{pack_cols, Col};
use crate::tiles;
use rayon::prelude::*;

pub struct Pairs {
    /// per way, the sorted tiles its segments cross: offsets and keys
    pub wt_off: Vec<u64>,
    pub wt_key: Vec<u32>,
    /// per relation, its sorted tiles (empty for one not kept)
    pub rel_keys: Vec<Vec<u32>>,
    /// (tile key << 32 | row), sorted
    pub node: Vec<u64>,
    pub way: Vec<u64>,
    pub rel: Vec<u64>,
}

pub fn build(c: &Clip, z: u32) -> Pairs {
    let (wt_off, wt_key) = tiles::way_tiles(c, z);
    // relations: a member node's tile, every tile a member way crosses; kept relations only
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
    let mut rel: Vec<u64> = Vec::new();
    for (r, ks) in rel_keys.iter().enumerate() {
        rel.extend(ks.iter().map(|&k| (k as u64) << 32 | r as u64));
    }
    rel.par_sort_unstable();

    let nw = c.wid.len();
    let mut way: Vec<u64> = Vec::with_capacity(wt_key.len());
    for w in 0..nw {
        for &k in &wt_key[wt_off[w] as usize..wt_off[w + 1] as usize] {
            way.push((k as u64) << 32 | w as u64);
        }
    }
    way.par_sort_unstable();

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
                        if row != NONE {
                            v.push((k as u64) << 32 | row as u64);
                        }
                    }
                }
            }
            v
        })
        .collect();
    let mut node: Vec<u64> = Vec::with_capacity(parts.iter().map(Vec::len).sum::<usize>() + c.tn_row.len());
    for p in parts {
        node.extend_from_slice(&p);
    }
    for &row in &c.tn_row {
        node.push((c.nkey[row as usize] as u64) << 32 | row as u64);
    }
    for r in 0..nr {
        if !c.r_kept[r] {
            continue;
        }
        for m in c.roffs[r] as usize..c.roffs[r + 1] as usize {
            if c.mtype[m] == 0 {
                if let Ok(row) = c.nid.binary_search(&c.mref[m]) {
                    node.push((c.nkey[row] as u64) << 32 | row as u64);
                }
            }
        }
    }
    node.par_sort_unstable();
    node.dedup();
    Pairs { wt_off, wt_key, rel_keys, node, way, rel }
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

impl Pairs {
    /// every tile with something in it, sorted
    pub fn keys(&self) -> Vec<u32> {
        let mut keys: Vec<u32> =
            self.node.iter().chain(self.way.iter()).chain(self.rel.iter()).map(|&p| (p >> 32) as u32).collect();
        keys.par_sort_unstable();
        keys.dedup();
        keys
    }

    /// one tile's payload, and how many nodes, ways and relations it holds
    pub fn payload(&self, c: &Clip, key: u32) -> (Vec<u8>, [usize; 3]) {
        let (n, w, r) = (of_key(&self.node, key), of_key(&self.way, key), of_key(&self.rel, key));
        let mut cols: Vec<Col> = Vec::with_capacity(25);
        c.node_cols(&rows_of(n), &mut cols);
        c.way_cols(&rows_of(w), &mut cols);
        c.rel_cols(&rows_of(r), &mut cols);
        (pack_cols(&cols), [n.len(), w.len(), r.len()])
    }
}
