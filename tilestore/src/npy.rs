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
