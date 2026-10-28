//! Complete companion inventory, pinned by the native binary at build time.
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::{collections::{BTreeMap, BTreeSet}, io::Read, path::{Component, Path, PathBuf}};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Manifest {
    schema_version: u32,
    python: String,
    working_directory: String,
    files: BTreeMap<String, String>,
}

pub struct Companion { pub python: PathBuf, pub integration: PathBuf }

fn plain(path: &Path) -> bool {
    let Ok(metadata) = std::fs::symlink_metadata(path) else { return false; };
    if metadata.file_type().is_symlink() { return false; }
    #[cfg(windows)] {
        use std::os::windows::fs::MetadataExt;
        if metadata.file_attributes() & 0x400 != 0 { return false; }
    }
    metadata.is_dir() || metadata.is_file()
}

fn relative(name: &str) -> bool {
    !name.is_empty() && !name.contains('\\') && !name.contains(':')
        && Path::new(name).components().all(|c| matches!(c, Component::Normal(_)))
        && name.split('/').all(|p| !p.is_empty() && p != "." && p != "..")
}

fn digest(path: &Path) -> Result<String, String> {
    let file = std::fs::File::open(path).map_err(|_| "runtime_packaging_invalid")?;
    if file.metadata().map_err(|_| "runtime_packaging_invalid")?.len() > 256*1024*1024 {
        return Err("runtime_packaging_invalid".into());
    }
    let mut hash = Sha256::new(); let mut source = std::io::BufReader::new(file);
    let mut block = [0u8; 65536];
    loop { let n = source.read(&mut block).map_err(|_| "runtime_packaging_invalid")?; if n==0 {break;} hash.update(&block[..n]); }
    Ok(format!("{:x}", hash.finalize()))
}

pub fn verify(root: &Path, expected: &str) -> Result<Companion, String> {
    if expected.len()!=64 { return Err("runtime_packaging_unavailable".into()); }
    if !plain(root) || !plain(&root.join("manifest.json")) { return Err("runtime_packaging_invalid".into()); }
    let file=std::fs::File::open(root.join("manifest.json")).map_err(|_| "runtime_packaging_invalid")?;
    let mut bytes=Vec::new(); file.take(4*1024*1024+1).read_to_end(&mut bytes).map_err(|_| "runtime_packaging_invalid")?;
    if bytes.len()>4*1024*1024 || format!("{:x}",Sha256::digest(&bytes))!=expected {return Err("runtime_packaging_invalid".into());}
    let manifest:Manifest=serde_json::from_slice(&bytes).map_err(|_| "runtime_packaging_invalid")?;
    if manifest.schema_version!=1 || manifest.python!="python/python.exe" || manifest.working_directory!="app/integration"
        || manifest.files.is_empty() || manifest.files.len()>100000 || !manifest.files.contains_key(&manifest.python)
        || !manifest.files.contains_key("app/integration/host_runtime/bridge_service.py")
        || manifest.files.keys().any(|s|!relative(s) || s=="manifest.json") {return Err("runtime_packaging_invalid".into());}
    let mut found=BTreeSet::new(); let mut queue=vec![root.to_owned()]; let mut dirs=0;
    while let Some(directory)=queue.pop() {
        dirs+=1; if dirs>50000 {return Err("runtime_packaging_invalid".into());}
        for entry in std::fs::read_dir(directory).map_err(|_| "runtime_packaging_invalid")? {
            let path=entry.map_err(|_| "runtime_packaging_invalid")?.path();
            if !plain(&path) {return Err("runtime_packaging_invalid".into());}
            if path.is_dir() {queue.push(path);continue;}
            let name=path.strip_prefix(root).map_err(|_| "runtime_packaging_invalid")?.to_str().ok_or("runtime_packaging_invalid")?.replace('\\',"/");
            if name=="manifest.json" {continue;}
            if manifest.files.get(&name)!=Some(&digest(&path)?) {return Err("runtime_packaging_invalid".into());}
            found.insert(name);
        }
    }
    if found.len()!=manifest.files.len() {return Err("runtime_packaging_invalid".into());}
    Ok(Companion {python:root.join(manifest.python),integration:root.join(manifest.working_directory)})
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture() -> (PathBuf,String) {
        let root=std::env::temp_dir().join(format!("tacticore-package-{}-{}",std::process::id(),std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()));
        std::fs::create_dir_all(root.join("python")).unwrap();std::fs::create_dir_all(root.join("app/integration/host_runtime")).unwrap();
        std::fs::write(root.join("python/python.exe"),b"trusted python").unwrap();std::fs::write(root.join("app/integration/host_runtime/bridge_service.py"),b"trusted bridge").unwrap();
        let files:BTreeMap<String,String>=["python/python.exe","app/integration/host_runtime/bridge_service.py"].iter().map(|s|(s.to_string(),digest(&root.join(s)).unwrap())).collect();
        let raw=serde_json::to_vec(&serde_json::json!({"schema_version":1,"python":"python/python.exe","working_directory":"app/integration","files":files})).unwrap();
        std::fs::write(root.join("manifest.json"),&raw).unwrap();(root,format!("{:x}",Sha256::digest(raw)))
    }
    #[test] fn full_inventory_rejects_added_code_and_modified_binary() {
        let (root,pin)=fixture();assert!(verify(&root,&pin).is_ok());
        std::fs::write(root.join("python/injected.py"),b"extra").unwrap();assert!(verify(&root,&pin).is_err());std::fs::remove_file(root.join("python/injected.py")).unwrap();
        std::fs::write(root.join("python/python.exe"),b"changed").unwrap();assert!(verify(&root,&pin).is_err());std::fs::remove_dir_all(root).unwrap();
    }
    #[test] fn wrong_pin_and_missing_file_fail_closed() {
        let(root,pin)=fixture();assert!(verify(&root,&"0".repeat(64)).is_err());std::fs::remove_file(root.join("python/python.exe")).unwrap();assert!(verify(&root,&pin).is_err());std::fs::remove_dir_all(root).unwrap();
    }
    #[test] fn no_relative_escape_or_ambiguous_separator() {
        for path in ["../x","/x","C:/x","python\\x","python//x","python/./x","python/../x"] {assert!(!relative(path));}
        assert!(relative("python/Lib/os.py"));
    }
}
