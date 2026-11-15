//! The tile maths of tools/stream/tiles.py, operation for operation: a difference in the last digit moves a node on
//! a tile's edge to its neighbour, so no fused multiply-add and no reciprocal in place of a division.

use crate::clip::{Clip, NONE};
use rayon::prelude::*;
use std::f64::consts::PI;

/// web mercator tile coordinates at z, fractional (tiles.py frac_xy)
#[inline]
pub fn frac_xy(lat7: i32, lon7: i32, nt: f64) -> (f64, f64) {
    frac_deg(lat7 as f64 / 1e7, lon7 as f64 / 1e7, nt)
}

/// the same from degrees
#[inline]
pub fn frac_deg(lat: f64, lon: f64, nt: f64) -> (f64, f64) {
    let lat = lat.clamp(-85.0511, 85.0511);
    let fx = (lon + 180.0) / 360.0 * nt;
    let r = lat * (PI / 180.0);
    let fy = (1.0 - (r.tan() + 1.0 / r.cos()).ln() / PI) / 2.0 * nt;
    (fx, fy)
}

#[inline]
pub fn key_of(x: i64, y: i64, z: u32) -> u32 {
    let m = (1i64 << z) - 1;
    ((x.clamp(0, m) << z) | y.clamp(0, m)) as u32
}

/// every tile a segment crosses (tiles.py segment_tiles): column by column, its rows between the segment's y where
/// it enters and leaves the column
fn segment_tiles(fx0: f64, fy0: f64, fx1: f64, fy1: f64, z: u32, out: &mut Vec<u32>) {
    const EPS: f64 = 1e-9;
    let (xa, xb) = (fx0.min(fx1), fx0.max(fx1));
    let (c0, c1) = (xa.floor() as i64, xb.floor() as i64);
    let (dx, dy) = (fx1 - fx0, fy1 - fy0);
    for col in c0..=c1 {
        let lo = (col as f64).max(xa);
        let hi = ((col + 1) as f64).min(xb);
        let t_lo = if dx != 0.0 { (lo - fx0) / dx } else { 0.0 };
        let t_hi = if dx != 0.0 { (hi - fx0) / dx } else { 1.0 };
        let ya = fy0 + t_lo * dy;
        let yb = fy0 + t_hi * dy;
        let r0 = (ya.min(yb) - EPS).floor() as i64;
        let r1 = (ya.max(yb) + EPS).floor() as i64;
        for row in r0..=r1 {
            out.push(key_of(col, row, z));
        }
    }
}

/// per way, the sorted tiles its segments cross: (offsets, keys)
pub fn way_tiles(c: &Clip, z: u32) -> (Vec<u64>, Vec<u32>) {
    let nt = (1u64 << z) as f64;
    let nw = c.wid.len();
    const CHUNK: usize = 1 << 14;
    let parts: Vec<(Vec<u32>, Vec<u32>)> = (0..nw.div_ceil(CHUNK))
        .into_par_iter()
        .map(|ci| {
            let mut counts = Vec::with_capacity(CHUNK);
            let mut keys = Vec::new();
            let mut k: Vec<u32> = Vec::new();
            for w in ci * CHUNK..((ci + 1) * CHUNK).min(nw) {
                k.clear();
                let rows = &c.wrefs[c.woffs[w] as usize..c.woffs[w + 1] as usize];
                let mut prev = NONE;
                for &row in rows {
                    if row != NONE {
                        let key = c.nkey[row as usize];
                        k.push(key);
                        // a segment: consecutive refs of one way, both placed, in different tiles
                        if prev != NONE && c.nkey[prev as usize] != key {
                            let (ax, ay) = frac_xy(c.lat7[prev as usize], c.lon7[prev as usize], nt);
                            let (bx, by) = frac_xy(c.lat7[row as usize], c.lon7[row as usize], nt);
                            segment_tiles(ax, ay, bx, by, z, &mut k);
                        }
                    }
                    prev = row;
                }
                k.sort_unstable();
                k.dedup();
                counts.push(k.len() as u32);
                keys.extend_from_slice(&k);
            }
            (counts, keys)
        })
        .collect();
    let mut off = Vec::with_capacity(nw + 1);
    let mut keys = Vec::with_capacity(parts.iter().map(|p| p.1.len()).sum());
    let mut o = 0u64;
    off.push(0);
    for (counts, ks) in parts {
        for n in counts {
            o += n as u64;
            off.push(o);
        }
        keys.extend_from_slice(&ks);
    }
    (off, keys)
}
