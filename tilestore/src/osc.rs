//! A day's diff (.osc or .osc.gz) as tilestore.py read_osc reads it through osmium: the last version of every object
//! in file order, the visible ones as columns, and the ids of all (deleted ones too). A node is visible when it is
//! not in a <delete> section (nor marked visible="false") and has a valid location. Coordinates are parsed to
//! 1e-7 degrees as libosmium does (no float in between); attribute values are normalised as an XML parser must
//! (a raw tab, newline or carriage return is a space) and then unescaped; tags are b"k\0v\0..."; timestamps are
//! whole seconds.

use crate::read::{stamp_seconds, Part};
use quick_xml::events::{BytesStart, Event};
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;

pub struct Diff {
    /// every id the diff touches, sorted
    pub n_all: Vec<i64>,
    pub w_all: Vec<i64>,
    pub r_all: Vec<i64>,
    /// the visible last versions, sorted by id
    pub part: Part,
}

/// libosmium's string_to_location_coordinate, for the decimal forms a diff holds: up to 7 decimals kept, the 8th
/// rounds half up, the rest are skipped
pub fn coordinate(s: &str) -> Option<i32> {
    let b = s.as_bytes();
    let mut i = 0;
    let neg = b.first() == Some(&b'-');
    if neg {
        i += 1;
    }
    let mut r: i64 = 0;
    let mut digits = 0;
    while i < b.len() && b[i].is_ascii_digit() {
        r = r * 10 + (b[i] - b'0') as i64;
        i += 1;
        digits += 1;
        if digits > 10 {
            return None;
        }
    }
    let mut scale = 0;
    if i < b.len() && b[i] == b'.' {
        i += 1;
        while i < b.len() && b[i].is_ascii_digit() && scale < 7 {
            r = r * 10 + (b[i] - b'0') as i64;
            i += 1;
            scale += 1;
        }
        if i < b.len() && b[i].is_ascii_digit() {
            if b[i] >= b'5' {
                r += 1;
            }
            while i < b.len() && b[i].is_ascii_digit() {
                i += 1;
            }
        }
    }
    if i != b.len() || (digits == 0 && scale == 0) {
        return None;
    }
    for _ in scale..7 {
        r *= 10;
    }
    let r = if neg { -r } else { r };
    i32::try_from(r).ok()
}

/// an attribute's value as an XML parser hands it over: line ends and tabs as spaces, entities resolved
fn value(raw: &[u8]) -> String {
    let s = String::from_utf8_lossy(raw);
    let s = s.replace("\r\n", " ").replace(['\r', '\n', '\t'], " ");
    quick_xml::escape::unescape(&s).unwrap_or_else(|e| panic!("an attribute value {s:?}: {e}")).into_owned()
}

fn attrs(e: &BytesStart) -> Vec<(Vec<u8>, String)> {
    e.attributes()
        .map(|a| {
            let a = a.expect("an attribute");
            (a.key.as_ref().to_vec(), value(&a.value))
        })
        .collect()
}

fn get<'a>(a: &'a [(Vec<u8>, String)], k: &[u8]) -> Option<&'a str> {
    a.iter().find(|(x, _)| x == k).map(|(_, v)| v.as_str())
}

#[derive(Clone, Default)]
struct Obj {
    kind: u8,
    id: i64,
    ver: i32,
    ts: i64,
    visible: bool,
    loc: Option<(i32, i32)>,
    tags: Vec<u8>,
    refs: Vec<i64>,
    /// (type, ref, role)
    members: Vec<(i8, i64, Vec<u8>)>,
}

fn start(e: &BytesStart, kind: u8, in_delete: bool) -> Obj {
    let a = attrs(e);
    let id: i64 = get(&a, b"id").expect("an id").parse().expect("a numeric id");
    let ver: i32 = get(&a, b"version").map_or(0, |v| v.parse().expect("a numeric version"));
    let ts = get(&a, b"timestamp").map_or(0, stamp_seconds);
    let visible = !in_delete && get(&a, b"visible") != Some("false");
    let loc = if kind == 0 {
        match (get(&a, b"lat").and_then(coordinate), get(&a, b"lon").and_then(coordinate)) {
            // osmium's Location::valid(): within the world
            (Some(lat), Some(lon)) if (-900_000_000..=900_000_000).contains(&lat) && (-1_800_000_000..=1_800_000_000).contains(&lon) => {
                Some((lat, lon))
            }
            _ => None,
        }
    } else {
        None
    };
    Obj { kind, id, ver, ts, visible, loc, ..Default::default() }
}

pub fn read(path: &Path) -> Diff {
    let f = File::open(path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    let src: Box<dyn BufRead> = if path.extension().is_some_and(|x| x == "gz") {
        Box::new(BufReader::with_capacity(1 << 20, flate2::read::MultiGzDecoder::new(BufReader::with_capacity(1 << 20, f))))
    } else {
        Box::new(BufReader::with_capacity(1 << 20, f))
    };
    let mut rd = quick_xml::Reader::from_reader(src);
    let mut buf = Vec::new();
    let mut objs: Vec<Obj> = Vec::new();
    let mut cur: Option<Obj> = None;
    let mut in_delete = false;
    loop {
        let ev = rd.read_event_into(&mut buf).unwrap_or_else(|e| panic!("{} at {}: {e}", path.display(), rd.buffer_position()));
        let (e, empty) = match &ev {
            Event::Start(e) => (Some(e), false),
            Event::Empty(e) => (Some(e), true),
            Event::End(e) => {
                match e.name().as_ref() {
                    b"node" | b"way" | b"relation" => objs.push(cur.take().expect("an end without a start")),
                    b"delete" => in_delete = false,
                    _ => {}
                }
                buf.clear();
                continue;
            }
            Event::Eof => break,
            _ => (None, false),
        };
        if let Some(e) = e {
            match e.name().as_ref() {
                b"delete" if !empty => in_delete = true,
                n @ (b"node" | b"way" | b"relation") => {
                    let kind = match n {
                        b"node" => 0,
                        b"way" => 1,
                        _ => 2,
                    };
                    let o = start(e, kind, in_delete);
                    if empty {
                        objs.push(o);
                    } else {
                        cur = Some(o);
                    }
                }
                b"tag" => {
                    let a = attrs(e);
                    let o = cur.as_mut().expect("a tag outside an object");
                    o.tags.extend_from_slice(get(&a, b"k").expect("a key").as_bytes());
                    o.tags.push(0);
                    o.tags.extend_from_slice(get(&a, b"v").expect("a value").as_bytes());
                    o.tags.push(0);
                }
                b"nd" => {
                    let a = attrs(e);
                    cur.as_mut().expect("a nd outside a way").refs.push(get(&a, b"ref").expect("a ref").parse().unwrap());
                }
                b"member" => {
                    let a = attrs(e);
                    let t = match get(&a, b"type").expect("a member type") {
                        "node" => 0,
                        "way" => 1,
                        "relation" => 2,
                        t => panic!("a member type {t}"),
                    };
                    let r: i64 = get(&a, b"ref").expect("a ref").parse().unwrap();
                    let role = get(&a, b"role").unwrap_or("").as_bytes().to_vec();
                    cur.as_mut().expect("a member outside a relation").members.push((t, r, role));
                }
                _ => {}
            }
        }
        buf.clear();
    }
    // the last version of each object in file order
    let mut order: Vec<usize> = (0..objs.len()).collect();
    order.sort_by_key(|&i| (objs[i].kind, objs[i].id, i));
    let mut last: Vec<usize> = Vec::new();
    for (j, &i) in order.iter().enumerate() {
        let next = order.get(j + 1).map(|&n| (objs[n].kind, objs[n].id));
        if next != Some((objs[i].kind, objs[i].id)) {
            last.push(i);
        }
    }
    let mut d = Diff { n_all: Vec::new(), w_all: Vec::new(), r_all: Vec::new(), part: Part::empty() };
    let p = &mut d.part;
    for &i in &last {
        let o = &objs[i];
        match o.kind {
            0 => {
                d.n_all.push(o.id);
                if let (true, Some((lat, lon))) = (o.visible, o.loc) {
                    p.nid.push(o.id);
                    p.lat.push(lat);
                    p.lon.push(lon);
                    if o.tags.is_empty() {
                        p.tag_of.push(-1);
                    } else {
                        p.tag_of.push(p.tver.len() as i32);
                        p.tver.push(o.ver);
                        p.tts.push(o.ts);
                        p.ntb.extend_from_slice(&o.tags);
                        p.n_toff.push(p.ntb.len());
                    }
                }
            }
            1 => {
                d.w_all.push(o.id);
                if o.visible {
                    p.wid.push(o.id);
                    p.wver.push(o.ver);
                    p.wts.push(o.ts);
                    p.wrefs.extend_from_slice(&o.refs);
                    p.w_roff.push(p.wrefs.len());
                    p.wtb.extend_from_slice(&o.tags);
                    p.w_toff.push(p.wtb.len());
                }
            }
            _ => {
                d.r_all.push(o.id);
                if o.visible {
                    p.rid.push(o.id);
                    p.rver.push(o.ver);
                    p.rts.push(o.ts);
                    for (t, r, role) in &o.members {
                        p.rmt.push(*t);
                        p.rmref.push(*r);
                        p.rrl.push(role.len() as i32);
                        p.rroles.extend_from_slice(role);
                        p.r_rloff.push(p.rroles.len());
                    }
                    p.r_moff.push(p.rmt.len());
                    p.rtb.extend_from_slice(&o.tags);
                    p.r_toff.push(p.rtb.len());
                }
            }
        }
    }
    crate::log(&format!(
        "diff {}: {} nodes, {} ways, {} relations ({} objects in the file)",
        path.file_name().unwrap().to_string_lossy(),
        d.n_all.len(),
        d.w_all.len(),
        d.r_all.len(),
        objs.len()
    ));
    d
}

#[cfg(test)]
mod tests {
    use super::coordinate;

    #[test]
    fn coordinates_as_osmium() {
        assert_eq!(coordinate("51.54"), Some(515_400_000));
        assert_eq!(coordinate("-0.09"), Some(-900_000));
        assert_eq!(coordinate("-0.0000001"), Some(-1));
        assert_eq!(coordinate("12.12345675"), Some(121_234_568));
        assert_eq!(coordinate("12.12345674"), Some(121_234_567));
        assert_eq!(coordinate("180"), Some(1_800_000_000));
        assert_eq!(coordinate("."), None);
        assert_eq!(coordinate("1x"), None);
    }
}
