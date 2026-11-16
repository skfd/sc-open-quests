//! A clip in memory, by row: what tiles.py geom + attrs and tilestore.py Clip hold. Nodes, ways and relations in the
//! file's (id) order; tags as b"k\0v\0..." per object; untagged nodes keep only a place.

use crate::cols::{delta32, delta64, Col};
use crate::tiles::{frac_xy, key_of};
use osmpbf::{BlobDecode, BlobReader, PrimitiveBlock, RelMemberType};
use rayon::prelude::*;
use std::path::Path;

/// a way's ref with no node in the clip
pub const NONE: u32 = u32::MAX;

#[derive(Default)]
pub struct Clip {
    // nodes
    pub nid: Vec<i64>,
    pub lat7: Vec<i32>,
    pub lon7: Vec<i32>,
    pub nkey: Vec<u32>,
    /// the tagged nodes' rows, and per node row its number among the tagged (-1: untagged)
    pub tn_row: Vec<u32>,
    pub tagged_of: Vec<i32>,
    pub tn_ver: Vec<i32>,
    pub tn_ts: Vec<i64>,
    pub tn_toff: Vec<u64>,
    pub tn_tags: Vec<u8>,
    // ways
    pub wid: Vec<i64>,
    pub w_ver: Vec<i32>,
    pub w_ts: Vec<i64>,
    pub woffs: Vec<u64>,
    pub wref_ids: Vec<i64>,
    /// the refs as node rows; NONE: not in the clip
    pub wrefs: Vec<u32>,
    pub w_toff: Vec<u64>,
    pub w_tags: Vec<u8>,
    // relations
    pub rid: Vec<i64>,
    pub r_ver: Vec<i32>,
    pub r_ts: Vec<i64>,
    pub roffs: Vec<u64>,
    pub mtype: Vec<i8>,
    pub mref: Vec<i64>,
    /// per member, where its role starts in `roles` (one more at the end)
    pub r_roff: Vec<u64>,
    pub roles: Vec<u8>,
    pub r_toff: Vec<u64>,
    pub r_tags: Vec<u8>,
    /// tagged and not one the app ignores
    pub r_kept: Vec<bool>,
}

/// one block's share, appended in file order
#[derive(Default)]
pub struct Part {
    pub nid: Vec<i64>,
    pub lat7: Vec<i32>,
    pub lon7: Vec<i32>,
    /// every node's version and timestamp (the tagged ones' are in tn_ver and tn_ts too)
    pub n_ver: Vec<i32>,
    pub n_ts: Vec<i64>,
    pub tn_local: Vec<u32>,
    pub tn_ver: Vec<i32>,
    pub tn_ts: Vec<i64>,
    pub tn_tlen: Vec<u32>,
    pub tn_tags: Vec<u8>,
    pub wid: Vec<i64>,
    pub w_ver: Vec<i32>,
    pub w_ts: Vec<i64>,
    pub w_nref: Vec<u32>,
    pub w_refs: Vec<i64>,
    pub w_tlen: Vec<u32>,
    pub w_tags: Vec<u8>,
    pub rid: Vec<i64>,
    pub r_ver: Vec<i32>,
    pub r_ts: Vec<i64>,
    pub r_nmem: Vec<u32>,
    pub mtype: Vec<i8>,
    pub mref: Vec<i64>,
    pub m_rlen: Vec<u32>,
    pub roles: Vec<u8>,
    pub r_tlen: Vec<u32>,
    pub r_tags: Vec<u8>,
}

fn push_tag(out: &mut Vec<u8>, st: &[Vec<u8>], k: usize, v: usize) {
    out.extend_from_slice(&st[k]);
    out.push(0);
    out.extend_from_slice(&st[v]);
    out.push(0);
}

/// every version in the block, in the order `parse_into` walks it: (kind, id, timestamp in ms, visible)
pub fn metas(block: &PrimitiveBlock) -> Vec<(u8, i64, i64, bool)> {
    let mut m = Vec::new();
    for g in block.groups() {
        for n in g.dense_nodes() {
            let (ms, vis) = n.info().map(|i| (i.milli_timestamp(), i.visible())).unwrap_or((0, true));
            m.push((0, n.id(), ms, vis));
        }
        for n in g.nodes() {
            let i = n.info();
            m.push((0, n.id(), i.milli_timestamp().unwrap_or(0), i.visible()));
        }
        for w in g.ways() {
            let i = w.info();
            m.push((1, w.id(), i.milli_timestamp().unwrap_or(0), i.visible()));
        }
        for r in g.relations() {
            let i = r.info();
            m.push((2, r.id(), i.milli_timestamp().unwrap_or(0), i.visible()));
        }
    }
    m
}

pub fn parse(block: &PrimitiveBlock) -> Part {
    let mut p = Part::default();
    parse_into(block, |_| 1, &mut p, &mut Part::default());
    p
}

/// the block's objects, each where `dest` sends it by its number in the block: 0 nowhere (nothing of it is
/// copied), 1 into `a`, anything else into `b`
pub fn parse_into(block: &PrimitiveBlock, mut dest: impl FnMut(usize) -> u8, a: &mut Part, b: &mut Part) {
    let st = block.raw_stringtable();
    let mut at = 0usize;
    macro_rules! part {
        () => {{
            at += 1;
            match dest(at - 1) {
                0 => continue,
                1 => &mut *a,
                _ => &mut *b,
            }
        }};
    }
    for g in block.groups() {
        for n in g.dense_nodes() {
            let p = part!();
            p.nid.push(n.id());
            p.lat7.push(n.decimicro_lat());
            p.lon7.push(n.decimicro_lon());
            let (ver, ms) = n.info().map(|i| (i.version(), i.milli_timestamp())).unwrap_or((0, 0));
            p.n_ver.push(ver);
            p.n_ts.push(ms.div_euclid(1000));
            let before = p.tn_tags.len();
            for (k, v) in n.raw_tags() {
                push_tag(&mut p.tn_tags, st, k as usize, v as usize);
            }
            if p.tn_tags.len() > before {
                p.tn_local.push(p.nid.len() as u32 - 1);
                p.tn_tlen.push((p.tn_tags.len() - before) as u32);
                p.tn_ver.push(ver);
                p.tn_ts.push(ms.div_euclid(1000));
            }
        }
        for n in g.nodes() {
            let p = part!();
            p.nid.push(n.id());
            p.lat7.push(n.decimicro_lat());
            p.lon7.push(n.decimicro_lon());
            let i = n.info();
            let (ver, ts) = (i.version().unwrap_or(0), i.milli_timestamp().unwrap_or(0).div_euclid(1000));
            p.n_ver.push(ver);
            p.n_ts.push(ts);
            let before = p.tn_tags.len();
            for (k, v) in n.raw_tags() {
                push_tag(&mut p.tn_tags, st, k as usize, v as usize);
            }
            if p.tn_tags.len() > before {
                p.tn_local.push(p.nid.len() as u32 - 1);
                p.tn_tlen.push((p.tn_tags.len() - before) as u32);
                p.tn_ver.push(ver);
                p.tn_ts.push(ts);
            }
        }
        for w in g.ways() {
            let p = part!();
            p.wid.push(w.id());
            let i = w.info();
            p.w_ver.push(i.version().unwrap_or(0));
            p.w_ts.push(i.milli_timestamp().unwrap_or(0).div_euclid(1000));
            let before = p.w_refs.len();
            p.w_refs.extend(w.refs());
            p.w_nref.push((p.w_refs.len() - before) as u32);
            let before = p.w_tags.len();
            for (k, v) in w.raw_tags() {
                push_tag(&mut p.w_tags, st, k as usize, v as usize);
            }
            p.w_tlen.push((p.w_tags.len() - before) as u32);
        }
        for r in g.relations() {
            let p = part!();
            p.rid.push(r.id());
            let i = r.info();
            p.r_ver.push(i.version().unwrap_or(0));
            p.r_ts.push(i.milli_timestamp().unwrap_or(0).div_euclid(1000));
            let mut n = 0u32;
            for m in r.members() {
                p.mtype.push(match m.member_type {
                    RelMemberType::Node => 0,
                    RelMemberType::Way => 1,
                    RelMemberType::Relation => 2,
                });
                p.mref.push(m.member_id);
                let role = &st[m.role_sid as usize];
                p.m_rlen.push(role.len() as u32);
                p.roles.extend_from_slice(role);
                n += 1;
            }
            p.r_nmem.push(n);
            let before = p.r_tags.len();
            for (k, v) in r.raw_tags() {
                push_tag(&mut p.r_tags, st, k as usize, v as usize);
            }
            p.r_tlen.push((p.r_tags.len() - before) as u32);
        }
    }
}

fn offsets(off: &mut Vec<u64>, lens: &[u32]) {
    let mut o = *off.last().unwrap();
    for &l in lens {
        o += l as u64;
        off.push(o);
    }
}

fn increasing(v: &[i64], what: &str) {
    assert!(v.windows(2).all(|w| w[0] < w[1]), "{what} ids are not strictly increasing: the file is not sorted");
}

/// engine/.../IgnoreRelation.kt (SC's ApplicationConstants.ignoreRelation), as tilestore.py ignore_relation
fn ignore_relation(tags: &[u8]) -> bool {
    const IGNORED: [&[u8]; 13] = [
        b"route_master", b"superroute", b"network", b"disused:route", b"boundary", b"water", b"waterway",
        b"watershed", b"collection", b"person", b"power", b"pipeline", b"railway",
    ];
    let (mut typ, mut route): (Option<&[u8]>, Option<&[u8]>) = (None, None);
    let mut it = tags.split(|&b| b == 0);
    while let (Some(k), Some(v)) = (it.next(), it.next()) {
        if k == b"type" {
            typ = Some(v);
        } else if k == b"route" {
            route = Some(v);
        }
    }
    match typ {
        None => false,
        Some(b"route") => route != Some(b"ferry"),
        Some(t) => IGNORED.contains(&t),
    }
}

/// a part's kept relations (tagged, not ones the app ignores) and nothing else of it
pub fn kept_relations(p: &Part) -> Part {
    let mut q = Part::default();
    let (mut m, mut ro, mut to) = (0usize, 0usize, 0usize);
    for r in 0..p.rid.len() {
        let (nm, tl) = (p.r_nmem[r] as usize, p.r_tlen[r] as usize);
        let rl: usize = p.m_rlen[m..m + nm].iter().map(|&l| l as usize).sum();
        let tags = &p.r_tags[to..to + tl];
        if !tags.is_empty() && !ignore_relation(tags) {
            q.rid.push(p.rid[r]);
            q.r_ver.push(p.r_ver[r]);
            q.r_ts.push(p.r_ts[r]);
            q.r_nmem.push(p.r_nmem[r]);
            q.mtype.extend_from_slice(&p.mtype[m..m + nm]);
            q.mref.extend_from_slice(&p.mref[m..m + nm]);
            q.m_rlen.extend_from_slice(&p.m_rlen[m..m + nm]);
            q.roles.extend_from_slice(&p.roles[ro..ro + rl]);
            q.r_tlen.push(p.r_tlen[r]);
            q.r_tags.extend_from_slice(tags);
        }
        m += nm;
        ro += rl;
        to += tl;
    }
    q
}

impl Clip {
    /// an empty clip, its offset columns started
    pub fn new() -> Clip {
        let mut c = Clip::default();
        for o in [&mut c.tn_toff, &mut c.woffs, &mut c.w_toff, &mut c.roffs, &mut c.r_roff, &mut c.r_toff] {
            o.push(0);
        }
        c
    }

    /// one block's share, after what is there
    pub fn append(&mut self, p: &Part) {
        let c = self;
        let base = c.nid.len() as u32;
        c.nid.extend_from_slice(&p.nid);
        c.lat7.extend_from_slice(&p.lat7);
        c.lon7.extend_from_slice(&p.lon7);
        c.tn_row.extend(p.tn_local.iter().map(|&i| base + i));
        c.tn_ver.extend_from_slice(&p.tn_ver);
        c.tn_ts.extend_from_slice(&p.tn_ts);
        offsets(&mut c.tn_toff, &p.tn_tlen);
        c.tn_tags.extend_from_slice(&p.tn_tags);
        c.wid.extend_from_slice(&p.wid);
        c.w_ver.extend_from_slice(&p.w_ver);
        c.w_ts.extend_from_slice(&p.w_ts);
        offsets(&mut c.woffs, &p.w_nref);
        c.wref_ids.extend_from_slice(&p.w_refs);
        offsets(&mut c.w_toff, &p.w_tlen);
        c.w_tags.extend_from_slice(&p.w_tags);
        c.rid.extend_from_slice(&p.rid);
        c.r_ver.extend_from_slice(&p.r_ver);
        c.r_ts.extend_from_slice(&p.r_ts);
        offsets(&mut c.roffs, &p.r_nmem);
        c.mtype.extend_from_slice(&p.mtype);
        c.mref.extend_from_slice(&p.mref);
        offsets(&mut c.r_roff, &p.m_rlen);
        c.roles.extend_from_slice(&p.roles);
        offsets(&mut c.r_toff, &p.r_tlen);
        c.r_tags.extend_from_slice(&p.r_tags);
    }

    /// which relations are kept: tagged and not ones the app ignores
    pub fn keep_relations(&mut self) {
        self.r_kept = (0..self.rid.len())
            .map(|r| {
                let t = &self.r_tags[self.r_toff[r] as usize..self.r_toff[r + 1] as usize];
                !t.is_empty() && !ignore_relation(t)
            })
            .collect();
    }

    pub fn read(pbf: &Path) -> Clip {
        let mut c = Clip::new();
        let mut reader = BlobReader::from_path(pbf).expect("open the pbf");
        loop {
            let batch: Vec<_> = reader.by_ref().take(256).map(|b| b.expect("read a blob")).collect();
            if batch.is_empty() {
                break;
            }
            // decoded on all threads, appended in the file's order
            let parts: Vec<Option<Part>> = batch
                .par_iter()
                .map(|b| match b.decode().expect("decode a blob") {
                    BlobDecode::OsmData(block) => Some(parse(&block)),
                    _ => None,
                })
                .collect();
            for p in parts.into_iter().flatten() {
                c.append(&p);
            }
        }
        assert!(c.nid.len() < NONE as usize, "node rows are 32 bits here");
        increasing(&c.nid, "node");
        increasing(&c.wid, "way");
        increasing(&c.rid, "relation");
        c.keep_relations();
        c
    }

    /// every node's tile, the tagged nodes' numbers, and the ways' refs as node rows
    pub fn place(&mut self, z: u32) {
        let nt = (1u64 << z) as f64;
        self.nkey = (0..self.nid.len())
            .into_par_iter()
            .map(|i| {
                let (fx, fy) = frac_xy(self.lat7[i], self.lon7[i], nt);
                key_of(fx.floor() as i64, fy.floor() as i64, z)
            })
            .collect();
        self.tagged_of = vec![-1; self.nid.len()];
        for (i, &row) in self.tn_row.iter().enumerate() {
            self.tagged_of[row as usize] = i as i32;
        }
        let nid = &self.nid;
        self.wrefs = self.wref_ids.par_iter().map(|r| nid.binary_search(r).map(|i| i as u32).unwrap_or(NONE)).collect();
    }

    fn tags(off: &[u64], tags: &[u8], rows: impl Iterator<Item = usize>, out: &mut Vec<Col>) {
        let mut tl = Vec::new();
        let mut tb = Vec::new();
        for r in rows {
            let (a, b) = (off[r] as usize, off[r + 1] as usize);
            tl.push((b - a) as i32);
            tb.extend_from_slice(&tags[a..b]);
        }
        out.push(Col::I32(tl));
        out.push(Col::U8(tb));
    }

    /// ids and places of these node rows (sorted), delta-coded
    pub fn place_cols(&self, rows: &[u32], out: &mut Vec<Col>) {
        out.push(Col::I64(delta64(rows.iter().map(|&r| self.nid[r as usize]))));
        out.push(Col::I32(delta32(rows.iter().map(|&r| self.lat7[r as usize]))));
        out.push(Col::I32(delta32(rows.iter().map(|&r| self.lon7[r as usize]))));
    }

    /// tilestore.py Clip.node_cols; rows sorted
    pub fn node_cols(&self, rows: &[u32], out: &mut Vec<Col>) {
        self.place_cols(rows, out);
        let mut tpos = Vec::new();
        let mut ti = Vec::new();
        for (i, &r) in rows.iter().enumerate() {
            let t = self.tagged_of[r as usize];
            if t >= 0 {
                tpos.push(i as i32);
                ti.push(t as usize);
            }
        }
        out.push(Col::I32(tpos));
        out.push(Col::I32(ti.iter().map(|&t| self.tn_ver[t]).collect()));
        out.push(Col::I64(ti.iter().map(|&t| self.tn_ts[t]).collect()));
        Self::tags(&self.tn_toff, &self.tn_tags, ti.iter().copied(), out);
    }

    /// tilestore.py Clip.way_cols; rows sorted
    pub fn way_cols(&self, rows: &[u32], out: &mut Vec<Col>) {
        out.push(Col::I64(delta64(rows.iter().map(|&r| self.wid[r as usize]))));
        out.push(Col::I32(rows.iter().map(|&r| self.w_ver[r as usize]).collect()));
        out.push(Col::I64(rows.iter().map(|&r| self.w_ts[r as usize]).collect()));
        out.push(Col::I32(rows.iter().map(|&r| (self.woffs[r as usize + 1] - self.woffs[r as usize]) as i32).collect()));
        out.push(Col::I64(delta64(rows.iter().flat_map(|&r| {
            self.wref_ids[self.woffs[r as usize] as usize..self.woffs[r as usize + 1] as usize].iter().copied()
        }))));
        Self::tags(&self.w_toff, &self.w_tags, rows.iter().map(|&r| r as usize), out);
    }

    /// tilestore.py Clip.rel_cols; rows sorted
    pub fn rel_cols(&self, rows: &[u32], out: &mut Vec<Col>) {
        let members =
            || rows.iter().flat_map(|&r| self.roffs[r as usize] as usize..self.roffs[r as usize + 1] as usize);
        out.push(Col::I64(delta64(rows.iter().map(|&r| self.rid[r as usize]))));
        out.push(Col::I32(rows.iter().map(|&r| self.r_ver[r as usize]).collect()));
        out.push(Col::I64(rows.iter().map(|&r| self.r_ts[r as usize]).collect()));
        out.push(Col::I32(rows.iter().map(|&r| (self.roffs[r as usize + 1] - self.roffs[r as usize]) as i32).collect()));
        out.push(Col::I8(members().map(|m| self.mtype[m]).collect()));
        out.push(Col::I64(delta64(members().map(|m| self.mref[m]))));
        out.push(Col::I32(members().map(|m| (self.r_roff[m + 1] - self.r_roff[m]) as i32).collect()));
        let mut roles = Vec::new();
        for m in members() {
            roles.extend_from_slice(&self.roles[self.r_roff[m] as usize..self.r_roff[m + 1] as usize]);
        }
        out.push(Col::U8(roles));
        Self::tags(&self.r_toff, &self.r_tags, rows.iter().map(|&r| r as usize), out);
    }
}
