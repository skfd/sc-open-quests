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

/// the columns of a payload, as pack_cols wrote them
pub fn unpack_cols(buf: &[u8]) -> Vec<Col> {
    let raw = zstd::stream::decode_all(buf).expect("a zstd payload");
    let i64_at = |p: usize| i64::from_le_bytes(raw[p..p + 8].try_into().unwrap());
    let k = i64_at(0) as usize;
    let mut pos = 8 * (1 + 2 * k);
    let mut out = Vec::with_capacity(k);
    for i in 0..k {
        let (code, n) = (i64_at(8 * (1 + 2 * i)), i64_at(8 * (2 + 2 * i)) as usize);
        let b = &raw[pos..];
        out.push(match code {
            0 => Col::I64((0..n).map(|j| i64::from_le_bytes(std::array::from_fn(|x| b[x * n + j]))).collect()),
            1 => Col::I32((0..n).map(|j| i32::from_le_bytes(std::array::from_fn(|x| b[x * n + j]))).collect()),
            2 => Col::I8(b[..n].iter().map(|&x| x as i8).collect()),
            3 => Col::U8(b[..n].to_vec()),
            _ => panic!("column type {code}"),
        });
        pos += n * [8, 4, 1, 1][code as usize];
    }
    out
}

impl Col {
    pub fn i64(self) -> Vec<i64> {
        match self {
            Col::I64(v) => v,
            _ => panic!("not an int64 column"),
        }
    }
    pub fn i32(self) -> Vec<i32> {
        match self {
            Col::I32(v) => v,
            _ => panic!("not an int32 column"),
        }
    }
    pub fn i8(self) -> Vec<i8> {
        match self {
            Col::I8(v) => v,
            _ => panic!("not an int8 column"),
        }
    }
    pub fn u8(self) -> Vec<u8> {
        match self {
            Col::U8(v) => v,
            _ => panic!("not a byte column"),
        }
    }
}

/// numpy's cumsum: the values back from their steps
pub fn undelta(mut v: Vec<i64>) -> Vec<i64> {
    let mut s = 0i64;
    for x in v.iter_mut() {
        s = s.wrapping_add(*x);
        *x = s;
    }
    v
}

pub fn undelta32(v: Vec<i32>) -> Vec<i32> {
    let mut s = 0i32;
    v.into_iter()
        .map(|x| {
            s = s.wrapping_add(x);
            s
        })
        .collect()
}

/// offsets from lengths, one more at the end
pub fn offsets(lens: &[i32]) -> Vec<usize> {
    let mut o = Vec::with_capacity(lens.len() + 1);
    let mut s = 0usize;
    o.push(0);
    for &l in lens {
        s += l as usize;
        o.push(s);
    }
    o
}
