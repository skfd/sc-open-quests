//! The two .npy files the Python store reads: the index (key, pack, off, len) and the (id, key) pairs.

use std::fs::File;
use std::io::{BufWriter, Write};
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
