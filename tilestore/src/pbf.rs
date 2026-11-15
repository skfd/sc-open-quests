//! A small OSM PBF writer, the protobuf encoded by hand (the `osmpbf` crate only reads): a header with the
//! replication timestamp and "Sort.Type_then_ID", then blocks of one kind each (the engine refuses mixed blocks),
//! dense nodes with version and timestamp, zlib blobs.

use flate2::write::ZlibEncoder;
use flate2::Compression;
use std::collections::HashMap;
use std::io::Write;

pub const PER_BLOCK: usize = 8000;

fn varint(out: &mut Vec<u8>, mut v: u64) {
    while v >= 0x80 {
        out.push(v as u8 | 0x80);
        v >>= 7;
    }
    out.push(v as u8);
}

fn zigzag(v: i64) -> u64 {
    ((v << 1) ^ (v >> 63)) as u64
}

fn key(out: &mut Vec<u8>, field: u32, wire: u32) {
    varint(out, ((field << 3) | wire) as u64);
}

fn int(out: &mut Vec<u8>, field: u32, v: i64) {
    key(out, field, 0);
    varint(out, v as u64);
}

fn bytes(out: &mut Vec<u8>, field: u32, b: &[u8]) {
    key(out, field, 2);
    varint(out, b.len() as u64);
    out.extend_from_slice(b);
}

/// a block's strings; index 0 is the empty string, as the format asks
pub struct Strings<'a> {
    map: HashMap<&'a [u8], u32>,
    list: Vec<&'a [u8]>,
}

impl<'a> Strings<'a> {
    pub fn new() -> Self {
        Strings { map: HashMap::new(), list: vec![b""] }
    }

    pub fn id(&mut self, s: &'a [u8]) -> u32 {
        if let Some(&i) = self.map.get(s) {
            return i;
        }
        let i = self.list.len() as u32;
        self.list.push(s);
        self.map.insert(s, i);
        i
    }

    fn encode(&self) -> Vec<u8> {
        let mut t = Vec::new();
        for s in &self.list {
            bytes(&mut t, 1, s);
        }
        t
    }
}

/// the (key, value) pairs of b"k\0v\0..."
pub fn tag_pairs(tags: &[u8]) -> impl Iterator<Item = (&[u8], &[u8])> {
    let mut it = tags.split(|&b| b == 0);
    std::iter::from_fn(move || match (it.next(), it.next()) {
        (Some(k), Some(v)) => Some((k, v)),
        _ => None,
    })
}

pub struct Node<'a> {
    pub id: i64,
    pub lat7: i32,
    pub lon7: i32,
    pub version: i32,
    pub seconds: i64,
    pub tags: &'a [u8],
}

pub struct Way<'a> {
    pub id: i64,
    pub version: i32,
    pub seconds: i64,
    pub refs: &'a [i64],
    pub tags: &'a [u8],
}

pub struct Relation<'a> {
    pub id: i64,
    pub version: i32,
    pub seconds: i64,
    pub mtype: &'a [i8],
    pub mref: &'a [i64],
    /// the members' roles one after another, and each one's length
    pub roles: &'a [u8],
    pub role_len: &'a [i32],
    pub tags: &'a [u8],
}

fn block(strings: &Strings, group: &[u8]) -> Vec<u8> {
    let mut b = Vec::with_capacity(group.len() + 1024);
    bytes(&mut b, 1, &strings.encode());
    bytes(&mut b, 2, group);
    b
}

fn info(version: i32, seconds: i64) -> Vec<u8> {
    let mut i = Vec::with_capacity(12);
    int(&mut i, 1, version as i64);
    int(&mut i, 2, seconds);
    i
}

pub fn node_block(nodes: &[Node]) -> Vec<u8> {
    let mut st = Strings::new();
    let (mut ids, mut lats, mut lons) = (Vec::new(), Vec::new(), Vec::new());
    let (mut vers, mut tss, mut zeros, mut kvs) = (Vec::new(), Vec::new(), Vec::new(), Vec::new());
    let (mut pid, mut plat, mut plon, mut pts) = (0i64, 0i64, 0i64, 0i64);
    for n in nodes {
        varint(&mut ids, zigzag(n.id - pid));
        // granularity 100 nanodegrees, no offset: the raw value is the 1e-7 degree itself
        varint(&mut lats, zigzag(n.lat7 as i64 - plat));
        varint(&mut lons, zigzag(n.lon7 as i64 - plon));
        varint(&mut vers, n.version as u64);
        varint(&mut tss, zigzag(n.seconds - pts));
        zeros.push(0u8);
        (pid, plat, plon, pts) = (n.id, n.lat7 as i64, n.lon7 as i64, n.seconds);
        for (k, v) in tag_pairs(n.tags) {
            varint(&mut kvs, st.id(k) as u64);
            varint(&mut kvs, st.id(v) as u64);
        }
        kvs.push(0);
    }
    let mut di = Vec::new();
    bytes(&mut di, 1, &vers);
    bytes(&mut di, 2, &tss);
    // changeset, uid and user: zeros, so that a reader which expects all five finds them
    bytes(&mut di, 3, &zeros);
    bytes(&mut di, 4, &zeros);
    bytes(&mut di, 5, &zeros);
    let mut dense = Vec::new();
    bytes(&mut dense, 1, &ids);
    bytes(&mut dense, 5, &di);
    bytes(&mut dense, 8, &lats);
    bytes(&mut dense, 9, &lons);
    bytes(&mut dense, 10, &kvs);
    let mut group = Vec::new();
    bytes(&mut group, 2, &dense);
    block(&st, &group)
}

fn tags_of<'a>(st: &mut Strings<'a>, tags: &'a [u8]) -> (Vec<u8>, Vec<u8>) {
    let (mut ks, mut vs) = (Vec::new(), Vec::new());
    for (k, v) in tag_pairs(tags) {
        varint(&mut ks, st.id(k) as u64);
        varint(&mut vs, st.id(v) as u64);
    }
    (ks, vs)
}

pub fn way_block(ways: &[Way]) -> Vec<u8> {
    let mut st = Strings::new();
    let mut group = Vec::new();
    for w in ways {
        let mut m = Vec::new();
        int(&mut m, 1, w.id);
        let (ks, vs) = tags_of(&mut st, w.tags);
        bytes(&mut m, 2, &ks);
        bytes(&mut m, 3, &vs);
        bytes(&mut m, 4, &info(w.version, w.seconds));
        let mut refs = Vec::with_capacity(w.refs.len() * 2);
        let mut prev = 0i64;
        for &r in w.refs {
            varint(&mut refs, zigzag(r - prev));
            prev = r;
        }
        bytes(&mut m, 8, &refs);
        bytes(&mut group, 3, &m);
    }
    block(&st, &group)
}

pub fn relation_block(rels: &[Relation]) -> Vec<u8> {
    let mut st = Strings::new();
    let mut group = Vec::new();
    for r in rels {
        let mut m = Vec::new();
        int(&mut m, 1, r.id);
        let (ks, vs) = tags_of(&mut st, r.tags);
        bytes(&mut m, 2, &ks);
        bytes(&mut m, 3, &vs);
        bytes(&mut m, 4, &info(r.version, r.seconds));
        let (mut roles, mut ids, mut types) = (Vec::new(), Vec::new(), Vec::new());
        let (mut prev, mut at) = (0i64, 0usize);
        for i in 0..r.mref.len() {
            let len = r.role_len[i] as usize;
            varint(&mut roles, st.id(&r.roles[at..at + len]) as u64);
            at += len;
            varint(&mut ids, zigzag(r.mref[i] - prev));
            prev = r.mref[i];
            types.push(r.mtype[i] as u8);
        }
        bytes(&mut m, 8, &roles);
        bytes(&mut m, 9, &ids);
        bytes(&mut m, 10, &types);
        bytes(&mut group, 4, &m);
    }
    block(&st, &group)
}

/// the header block; `stamp`: the replication timestamp in seconds
pub fn header_block(stamp: Option<i64>) -> Vec<u8> {
    let mut h = Vec::new();
    bytes(&mut h, 4, b"OsmSchema-V0.6");
    bytes(&mut h, 4, b"DenseNodes");
    bytes(&mut h, 5, b"Sort.Type_then_ID");
    bytes(&mut h, 16, b"sc-open-quests tilestore");
    if let Some(s) = stamp {
        int(&mut h, 32, s);
    }
    h
}

/// one blob of the file: the length, the blob header, the blob with its payload deflated
pub fn blob(kind: &str, payload: &[u8]) -> Vec<u8> {
    let mut z = ZlibEncoder::new(Vec::with_capacity(payload.len() / 3), Compression::new(6));
    z.write_all(payload).unwrap();
    let z = z.finish().unwrap();
    let mut b = Vec::with_capacity(z.len() + 16);
    int(&mut b, 2, payload.len() as i64);
    bytes(&mut b, 3, &z);
    let mut h = Vec::new();
    bytes(&mut h, 1, kind.as_bytes());
    int(&mut h, 3, b.len() as i64);
    let mut out = Vec::with_capacity(4 + h.len() + b.len());
    out.extend_from_slice(&(h.len() as u32).to_be_bytes());
    out.extend_from_slice(&h);
    out.extend_from_slice(&b);
    out
}
