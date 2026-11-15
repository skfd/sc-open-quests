//! A payload's columns, as tilestore.py packs them: a header of int64s (the count, then a type code and a length per
//! column), each column byte-shuffled (all first bytes, then all second bytes, ...), zstd level 3 over the whole.

pub enum Col {
    I64(Vec<i64>),
    I32(Vec<i32>),
    I8(Vec<i8>),
    U8(Vec<u8>),
}

pub const LEVEL: i32 = 3;

fn shuffle<const N: usize>(out: &mut Vec<u8>, n: usize, bytes: impl Fn(usize) -> [u8; N]) {
    let start = out.len();
    out.resize(start + n * N, 0);
    let dst = &mut out[start..];
    for i in 0..n {
        let b = bytes(i);
        for (j, &x) in b.iter().enumerate() {
            dst[j * n + i] = x;
        }
    }
}

pub fn pack_cols(cols: &[Col]) -> Vec<u8> {
    let mut raw: Vec<u8> = Vec::new();
    raw.extend_from_slice(&(cols.len() as i64).to_le_bytes());
    for c in cols {
        let (code, len) = match c {
            Col::I64(v) => (0i64, v.len()),
            Col::I32(v) => (1, v.len()),
            Col::I8(v) => (2, v.len()),
            Col::U8(v) => (3, v.len()),
        };
        raw.extend_from_slice(&code.to_le_bytes());
        raw.extend_from_slice(&(len as i64).to_le_bytes());
    }
    for c in cols {
        match c {
            Col::I64(v) => shuffle(&mut raw, v.len(), |i| v[i].to_le_bytes()),
            Col::I32(v) => shuffle(&mut raw, v.len(), |i| v[i].to_le_bytes()),
            Col::I8(v) => raw.extend(v.iter().map(|&x| x as u8)),
            Col::U8(v) => raw.extend_from_slice(v),
        }
    }
    zstd::bulk::compress(&raw, LEVEL).unwrap()
}

/// numpy's diff with a zero before the first: the first value itself, then the steps
pub fn delta64(v: impl Iterator<Item = i64>) -> Vec<i64> {
    let mut prev = 0i64;
    v.map(|x| {
        let d = x.wrapping_sub(prev);
        prev = x;
        d
    })
    .collect()
}

/// the same on 32-bit places: the step is taken in 64 bits and cut to 32, as the prototype's astype does
pub fn delta32(v: impl Iterator<Item = i32>) -> Vec<i32> {
    let mut prev = 0i64;
    v.map(|x| {
        let d = (x as i64 - prev) as i32;
        prev = x as i64;
        d
    })
    .collect()
}
