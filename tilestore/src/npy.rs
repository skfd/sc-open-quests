//! The two .npy files the Python store reads: the index (key, pack, off, len) and the (id, key) pairs.

use std::fs::File;
use std::io::{BufWriter, Seek, SeekFrom, Write};
use std::path::Path;

fn header(f: &mut impl Write, descr: &str, n: usize) {
    let mut h = format!("{{'descr': {descr}, 'fortran_order': False, 'shape': ({n},), }}");
    // magic (6) + version (2) + header length (2) + header, a multiple of 64, ending in a newline
    while (10 + h.len() + 1) % 64 != 0 {
        h.push(' ');
    }
    h.push('\n');
    f.write_all(b"\x93NUMPY\x01\x00").unwrap();
    f.write_all(&(h.len() as u16).to_le_bytes()).unwrap();
    f.write_all(h.as_bytes()).unwrap();
}

pub fn save_idx(path: &Path, rows: &[(i64, i32, i64, i32)]) {
    let mut f = BufWriter::with_capacity(1 << 22, File::create(path).unwrap());
    header(&mut f, "[('key', '<i8'), ('pack', '<i4'), ('off', '<i8'), ('len', '<i4')]", rows.len());
    for &(key, pack, off, len) in rows {
        f.write_all(&key.to_le_bytes()).unwrap();
        f.write_all(&pack.to_le_bytes()).unwrap();
        f.write_all(&off.to_le_bytes()).unwrap();
        f.write_all(&len.to_le_bytes()).unwrap();
    }
    f.flush().unwrap();
}

pub fn save_pairs(path: &Path, rows: &[(i64, i64)]) {
    let mut f = BufWriter::with_capacity(1 << 22, File::create(path).unwrap());
    header(&mut f, "[('id', '<i8'), ('key', '<i8')]", rows.len());
    for &(id, key) in rows {
        f.write_all(&id.to_le_bytes()).unwrap();
        f.write_all(&key.to_le_bytes()).unwrap();
    }
    f.flush().unwrap();
}

/// an index file's rows: (key, pack, off, len)
pub fn load_idx(path: &Path) -> Vec<(i64, i32, i64, i32)> {
    let b = std::fs::read(path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    assert!(b.starts_with(b"\x93NUMPY\x01"), "{}: not a version 1 .npy", path.display());
    let start = 10 + u16::from_le_bytes([b[8], b[9]]) as usize;
    let head = std::str::from_utf8(&b[10..start]).unwrap();
    assert!(head.contains("('key', '<i8'), ('pack', '<i4'), ('off', '<i8'), ('len', '<i4')"), "{}: {head}", path.display());
    b[start..]
        .chunks_exact(24)
        .map(|r| {
            (
                i64::from_le_bytes(r[0..8].try_into().unwrap()),
                i32::from_le_bytes(r[8..12].try_into().unwrap()),
                i64::from_le_bytes(r[12..20].try_into().unwrap()),
                i32::from_le_bytes(r[20..24].try_into().unwrap()),
            )
        })
        .collect()
}

/// a pair file mapped, not read: the planet's way pairs are 22 GB
pub struct PairMap {
    map: Option<memmap2::Mmap>,
    start: usize,
}

impl PairMap {
    pub fn open(path: &Path) -> PairMap {
        let f = File::open(path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
        // SAFETY: read only; a generation's pair files are never written after they are made
        let map = unsafe { memmap2::Mmap::map(&f) }.unwrap_or_else(|e| panic!("map {}: {e}", path.display()));
        assert!(map.len() >= 10 && map[1..6] == *b"NUMPY" && map[6] == 1, "{}: not a version 1 .npy", path.display());
        let start = 10 + u16::from_le_bytes([map[8], map[9]]) as usize;
        let head = std::str::from_utf8(&map[10..start]).unwrap();
        assert!(head.contains("('id', '<i8'), ('key', '<i8')"), "{}: {head}", path.display());
        assert!((map.len() - start) % 16 == 0 && (map.as_ptr() as usize + start) % 8 == 0, "{}: pairs not whole or not aligned", path.display());
        PairMap { map: Some(map), start }
    }

    /// the (id, key) rows, sorted by id then key
    pub fn rows(&self) -> &[[i64; 2]] {
        let m = self.map.as_ref().unwrap();
        let b = &m[self.start..];
        // SAFETY: aligned and a whole number of 16-byte rows (checked in open); little-endian on this machine
        unsafe { std::slice::from_raw_parts(b.as_ptr() as *const [i64; 2], b.len() / 16) }
    }
}

/// the rows of `old` that `keep` keeps merged with `add` (sorted), written as a pair file; returns the count
pub fn merge_pairs(path: &Path, old: &[[i64; 2]], keep: impl Fn(&[i64; 2]) -> bool, add: &[[i64; 2]]) -> u64 {
    assert!(add.windows(2).all(|w| w[0] <= w[1]), "pairs to add are not sorted");
    let mut w = PairWriter::new(path);
    let mut j = 0;
    for r in old.iter().filter(|r| keep(r)) {
        while j < add.len() && add[j] < *r {
            w.push(add[j][0], add[j][1]);
            j += 1;
        }
        w.push(r[0], r[1]);
    }
    for a in &add[j..] {
        w.push(a[0], a[1]);
    }
    w.finish()
}

/// (id, key) pairs written as they come; the count goes into the header at the end
pub struct PairWriter {
    f: BufWriter<File>,
    n: u64,
}

const PAIR_HEADER: usize = 128;

fn pair_header(n: u64) -> Vec<u8> {
    let mut h = format!("{{'descr': [('id', '<i8'), ('key', '<i8')], 'fortran_order': False, 'shape': ({n},), }}");
    while 10 + h.len() + 1 < PAIR_HEADER {
        h.push(' ');
    }
    h.push('\n');
    let mut b = b"\x93NUMPY\x01\x00".to_vec();
    b.extend_from_slice(&(h.len() as u16).to_le_bytes());
    b.extend_from_slice(h.as_bytes());
    assert!(b.len() == PAIR_HEADER);
    b
}

impl PairWriter {
    pub fn new(path: &Path) -> PairWriter {
        let mut f = BufWriter::with_capacity(1 << 22, File::create(path).unwrap());
        f.write_all(&pair_header(0)).unwrap();
        PairWriter { f, n: 0 }
    }

    pub fn push(&mut self, id: i64, key: i64) {
        self.f.write_all(&id.to_le_bytes()).unwrap();
        self.f.write_all(&key.to_le_bytes()).unwrap();
        self.n += 1;
    }

    pub fn finish(mut self) -> u64 {
        self.f.flush().unwrap();
        let mut f = self.f.into_inner().unwrap();
        f.seek(SeekFrom::Start(0)).unwrap();
        f.write_all(&pair_header(self.n)).unwrap();
        self.n
    }
}
