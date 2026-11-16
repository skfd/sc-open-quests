//! The node places in a file by id (DESIGN.md, "The planet cut, designed"): at byte 8 * id the node's latitude
//! and longitude in 1e-7 degrees, little-endian, the latitude with 2^31 added so that eight zero bytes mean "no
//! such node". Written in id order in runs, read through a mapping. The planet's is about 115 GB; a region's
//! nodes are spread over the planet's id range, so its file is as long and is marked sparse.

use std::fs::{self, File, OpenOptions};
use std::io::{BufWriter, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};

/// ids apart by more than this start a new run: the file is sought, not filled with zeros
const GAP: i64 = 4096;

/// the writer stops, and deletes its file, when the disk it writes to has less than this free: a region's
/// sparse file can still take hundreds of GB (Germany's filled a disk with 258 GB free)
const FLOOR: u64 = 40 << 30;

extern "system" {
    fn GetDiskFreeSpaceExW(dir: *const u16, free_to_caller: *mut u64, total: *mut u64, free: *mut u64) -> i32;
}

/// bytes free on the disk that holds this folder
pub fn free_bytes(dir: &Path) -> Option<u64> {
    use std::os::windows::ffi::OsStrExt;
    let dir = if dir.as_os_str().is_empty() { Path::new(".") } else { dir };
    let wide: Vec<u16> = dir.as_os_str().encode_wide().chain(std::iter::once(0)).collect();
    let mut free = 0u64;
    // SAFETY: a nul-terminated path and one u64 to fill
    let ok = unsafe { GetDiskFreeSpaceExW(wide.as_ptr(), &mut free, std::ptr::null_mut(), std::ptr::null_mut()) };
    (ok != 0).then_some(free)
}

fn place_bytes(lat: i32, lon: i32) -> [u8; 8] {
    let mut b = [0u8; 8];
    b[..4].copy_from_slice(&(lat.wrapping_sub(i32::MIN)).to_le_bytes());
    b[4..].copy_from_slice(&lon.to_le_bytes());
    b
}

/// a block's nodes as runs of ids close together, each the bytes of its stretch of the file. An id not above the
/// one before it is left out (the writer counts what does not fit).
pub fn runs(ids: &[i64], lat: &[i32], lon: &[i32]) -> Vec<(i64, Vec<u8>)> {
    let mut runs: Vec<(i64, Vec<u8>)> = Vec::new();
    let mut last = i64::MIN;
    for i in 0..ids.len() {
        let id = ids[i];
        assert!(id >= 0, "a negative node id");
        if id <= last {
            continue;
        }
        if runs.is_empty() || id - last > GAP {
            runs.push((id, Vec::new()));
        } else {
            let r = &mut runs.last_mut().unwrap().1;
            r.resize(r.len() + (id - last - 1) as usize * 8, 0);
        }
        runs.last_mut().unwrap().1.extend_from_slice(&place_bytes(lat[i], lon[i]));
        last = id;
    }
    runs
}

pub struct NodeWriter {
    path: PathBuf,
    w: BufWriter<File>,
    next: i64,
    pub seeks: u64,
    /// runs that start below what is written: the nodes were not in id order
    pub out_of_order: u64,
    adds: u64,
    /// free on its disk when it was created
    pub free_at_start: Option<u64>,
}

impl NodeWriter {
    fn dir(&self) -> &Path {
        self.path.parent().unwrap_or(Path::new("."))
    }

    /// free on its disk now
    pub fn free(&self) -> Option<u64> {
        free_bytes(self.dir())
    }

    pub fn create(path: &Path, sparse: bool) -> NodeWriter {
        if let Some(d) = path.parent() {
            fs::create_dir_all(d).unwrap();
        }
        let file = OpenOptions::new().read(true).write(true).create(true).truncate(true).open(path).expect("create the node file");
        if sparse {
            let ok = std::process::Command::new("fsutil").args(["sparse", "setflag"]).arg(path).status().map(|s| s.success()).unwrap_or(false);
            assert!(ok, "fsutil sparse setflag failed");
        }
        let dir = path.parent().unwrap_or(Path::new("."));
        let free_at_start = free_bytes(dir);
        NodeWriter { path: path.to_path_buf(), w: BufWriter::with_capacity(1 << 24, file), next: 0, seeks: 0, out_of_order: 0, adds: 0, free_at_start }
    }

    /// a block's runs, after everything written so far
    pub fn add(&mut self, runs: &[(i64, Vec<u8>)]) {
        self.adds += 1;
        if self.adds % 256 == 0 {
            if let Some(free) = self.free() {
                if free < FLOOR {
                    let _ = fs::remove_file(&self.path);
                    panic!("the node file is deleted and the run stopped: {:.1} GiB free on its disk, under the floor of {} GiB", free as f64 / (1u64 << 30) as f64, FLOOR >> 30);
                }
            }
        }
        for (start, bytes) in runs {
            let start = *start;
            if start < self.next {
                self.out_of_order += 1;
                continue;
            }
            if start - self.next <= GAP {
                for _ in self.next..start {
                    self.w.write_all(&[0u8; 8]).unwrap();
                }
            } else {
                self.w.seek(SeekFrom::Start(start as u64 * 8)).unwrap();
                self.seeks += 1;
            }
            self.w.write_all(bytes).unwrap();
            self.next = start + bytes.len() as i64 / 8;
        }
    }

    /// the highest id written, -1 if none
    pub fn top(&self) -> i64 {
        self.next - 1
    }

    /// the file written out and mapped for reading; `sync`: wait until it is on the disk
    pub fn finish(mut self, sync: bool) -> NodeMap {
        self.w.flush().unwrap();
        let file = self.w.into_inner().unwrap();
        if sync {
            file.sync_all().unwrap();
        }
        let bytes = file.metadata().unwrap().len();
        // SAFETY: the file is ours and is not written while it is mapped
        let map = if bytes == 0 { None } else { Some(unsafe { memmap2::Mmap::map(&file) }.expect("map the node file")) };
        NodeMap { path: self.path, map, bytes, _file: file }
    }
}

pub struct NodeMap {
    path: PathBuf,
    map: Option<memmap2::Mmap>,
    pub bytes: u64,
    _file: File,
}

impl NodeMap {
    pub fn get(&self, id: i64) -> Option<(i32, i32)> {
        let at = usize::try_from(id).ok()?.checked_mul(8)?;
        let b = self.map.as_ref()?.get(at..at + 8)?;
        let lat = i32::from_le_bytes(b[..4].try_into().unwrap());
        if lat == 0 {
            return None;
        }
        Some((lat.wrapping_add(i32::MIN), i32::from_le_bytes(b[4..].try_into().unwrap())))
    }

    /// unmapped and removed from the disk
    pub fn delete(self) {
        let NodeMap { path, map, _file, .. } = self;
        drop(map);
        drop(_file);
        fs::remove_file(path).unwrap();
    }
}
