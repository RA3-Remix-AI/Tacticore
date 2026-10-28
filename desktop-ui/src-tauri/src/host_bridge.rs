//! Named RPC only. The WebView never supplies a path, executable or shell text.
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::io::{BufRead, BufReader, Read, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{mpsc, Arc, Mutex};
use std::time::Duration;

const MAX_LINE: usize = 65536;
const OPERATIONS: &[&str] = &[
    "profiles.list", "profiles.get", "profiles.save", "connections.list", "session.inspect",
    "run.check", "run.start", "run.status", "run.stop", "diagnostics.export",
];

struct ServiceProcess {
    child: Child,
    input: ChildStdin,
    output: mpsc::Receiver<Result<Vec<u8>, ()>>,
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct RuntimeRegistration {
    schema_version: u32,
    registration_id: String,
    library_path: PathBuf,
    library_sha256: String,
}

struct RuntimeSource { library: PathBuf, home: PathBuf, fingerprint: String }

fn runtime_source() -> Result<RuntimeSource, String> {
    let local = std::env::var_os("LOCALAPPDATA").ok_or("local_state_unavailable")?;
    source_at(PathBuf::from(local).join("Tacticore"))
}

fn source_at(home: PathBuf) -> Result<RuntimeSource, String> {
    let config = home.join("desktop-runtime-config.json");
    if !config.is_file() { return Err("runtime_library_unregistered".into()); }
    let file = std::fs::File::open(config).map_err(|_| "runtime_configuration_invalid")?;
    let mut bytes = Vec::new();
    file.take(16385).read_to_end(&mut bytes).map_err(|_| "runtime_configuration_invalid")?;
    if bytes.len() > 16384 { return Err("runtime_configuration_invalid".into()); }
    let record: RuntimeRegistration = serde_json::from_slice(&bytes).map_err(|_| "runtime_configuration_invalid")?;
    let id = record.registration_id.as_bytes();
    if record.schema_version != 1 || id.len() != 36 || !id.iter().enumerate().all(|(i,b)| {
        if [8,13,18,23].contains(&i) { *b == b'-' } else { b.is_ascii_hexdigit() && !b.is_ascii_uppercase() }
    }) || !record.library_path.is_absolute() || record.library_path.to_string_lossy().starts_with("\\\\")
        || record.library_sha256.len() != 64 || !record.library_sha256.bytes().all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase()) {
        return Err("runtime_configuration_invalid".into());
    }
    let file = std::fs::File::open(&record.library_path).map_err(|_| "runtime_library_unavailable")?;
    let mut library = Vec::new();
    file.take(1024*1024+1).read_to_end(&mut library).map_err(|_| "runtime_library_unavailable")?;
    if library.len() > 1024*1024 || format!("{:x}", Sha256::digest(&library)) != record.library_sha256 {
        return Err("registered_library_changed".into());
    }
    Ok(RuntimeSource { library: record.library_path, home, fingerprint: format!("{:x}", Sha256::digest(&bytes)) })
}

impl Drop for ServiceProcess {
    fn drop(&mut self) {
        // This is the configuration/RPC process, never a running game host.
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

impl ServiceProcess {
    #[cfg(not(debug_assertions))]
    fn spawn(source: &RuntimeSource) -> Result<Self, String> {
        let executable=std::env::current_exe().map_err(|_| "runtime_packaging_invalid")?;
        let root=executable.parent().ok_or("runtime_packaging_invalid")?.join("runtime");
        let companion=crate::runtime_package::verify(&root,env!("TACTICORE_RUNTIME_MANIFEST_SHA256"))?;
        Self::launch(source,companion.python,companion.integration,None)
    }

    #[cfg(debug_assertions)]
    fn spawn(source: &RuntimeSource) -> Result<Self, String> {
        let repo = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent().and_then(|p| p.parent()).ok_or("runtime_layout_unavailable")?.to_owned();
        let venv = repo.join(".venv");
        let config=std::fs::read_to_string(venv.join("pyvenv.cfg")).map_err(|_| "runtime_layout_unavailable")?;
        let homes:Vec<_>=config.lines().filter_map(|line|line.split_once('=')).filter(|(key,_)|key.trim()=="home").map(|(_,value)|value.trim()).collect();
        if homes.len()!=1 {return Err("runtime_layout_unavailable".into());}
        let python = PathBuf::from(homes[0]).join("python.exe");
        let integration = repo.join("integration");
        if !python.is_file() || !integration.join("host_runtime/bridge_service.py").is_file() {
            return Err("runtime_layout_unavailable".into());
        }
        if !python.is_absolute() {return Err("runtime_layout_unavailable".into());}
        let prefix=serde_json::to_string(&venv.to_string_lossy()).map_err(|_|"runtime_layout_unavailable")?;
        let imports=serde_json::to_string(&vec![integration.to_string_lossy().to_string(),venv.join("Lib/site-packages").to_string_lossy().to_string()]).map_err(|_|"runtime_layout_unavailable")?;
        let bootstrap=format!("import sys,runpy;sys.prefix=sys.exec_prefix={prefix};sys.path[:0]={imports};sys.argv[0]='host_runtime.bridge_service';runpy.run_module('host_runtime.bridge_service',run_name='__main__')");
        Self::launch(source,python,integration,Some(bootstrap))
    }

    fn launch(source: &RuntimeSource, python: PathBuf, integration: PathBuf, bootstrap: Option<String>) -> Result<Self, String> {
        let mut command = Command::new(python);
        command.args(["-I", "-S", "-B"]);
        match bootstrap {Some(code)=>{command.args(["-c",&code]);},None=>{command.args(["-m","host_runtime.bridge_service"]);}}
        command.current_dir(integration)
            .arg("--library")
            .arg(&source.library)
            .arg("--state-dir").arg(source.home.join("desktop-runtime"))
            .stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null());
        #[cfg(windows)] {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000); // CREATE_NO_WINDOW
        }
        let mut child = command.spawn().map_err(|_| "bridge_startup_failed")?;
        let input = child.stdin.take().ok_or("bridge_startup_failed")?;
        let stdout = child.stdout.take().ok_or("bridge_startup_failed")?;
        let (tx, output) = mpsc::sync_channel(1);
        std::thread::spawn(move || {
            let mut reader = BufReader::new(stdout);
            loop {
                let mut bytes = Vec::new();
                // take() bounds allocation even if the child emits no newline.
                let read = (&mut reader).take((MAX_LINE + 1) as u64).read_until(b'\n', &mut bytes);
                if read.is_err() || bytes.is_empty() || bytes.len() > MAX_LINE || !bytes.ends_with(b"\n") {
                    let _ = tx.send(Err(()));
                    break;
                }
                if tx.send(Ok(bytes)).is_err() { break; }
            }
        });
        Ok(Self { child, input, output })
    }

    fn exchange(&mut self, request: &Value) -> Result<Value, String> {
        let mut bytes = serde_json::to_vec(request).map_err(|_| "request_invalid")?;
        if bytes.len() >= MAX_LINE { return Err("request_too_large".into()); }
        bytes.push(b'\n');
        self.input.write_all(&bytes).and_then(|_| self.input.flush())
            .map_err(|_| "delivery_unknown")?;
        let response = self.output.recv_timeout(Duration::from_secs(60))
            .map_err(|_| "delivery_unknown")?.map_err(|_| "delivery_unknown")?;
        let value: Value = serde_json::from_slice(&response).map_err(|_| "delivery_unknown")?;
        if value.get("schema_version") != Some(&Value::from(1))
            || value.get("request_id") != request.get("request_id")
            || !value.get("ok").is_some_and(Value::is_boolean) {
            return Err("delivery_unknown".into());
        }
        Ok(value)
    }
}

#[derive(Default)]
struct BridgeState { process: Option<ServiceProcess>, source: Option<String> }

#[derive(Clone, Default)]
pub struct HostBridge(Arc<Mutex<BridgeState>>);

fn validate(request: &Value) -> Result<(), String> {
    let object = request.as_object().ok_or("request_invalid")?;
    if object.len() != 4 || object.get("schema_version") != Some(&Value::from(1))
        || !object.get("args").is_some_and(Value::is_object)
        || !object.get("operation").and_then(Value::as_str).is_some_and(|s| OPERATIONS.contains(&s)) {
        return Err("request_invalid".into());
    }
    let id = object.get("request_id").and_then(Value::as_str).ok_or("request_invalid")?;
    if id.len() != 36 || !id.bytes().enumerate().all(|(i, b)| {
        if [8, 13, 18, 23].contains(&i) { b == b'-' } else { b.is_ascii_hexdigit() && !b.is_ascii_uppercase() }
    }) { return Err("request_invalid".into()); }
    Ok(())
}

#[tauri::command]
pub async fn diagnostics_read(export_id: String, expected_sha256: String) -> Result<Value, String> {
    let valid_id = export_id.len() == 36 && export_id.bytes().enumerate().all(|(i,b)| {
        if [8,13,18,23].contains(&i) {b==b'-'} else {b.is_ascii_hexdigit()&&!b.is_ascii_uppercase()}
    });
    if !valid_id || expected_sha256.len()!=64 || !expected_sha256.bytes().all(|b|b.is_ascii_hexdigit()&&!b.is_ascii_uppercase()) {
        return Err("diagnostics_unavailable".into());
    }
    tauri::async_runtime::spawn_blocking(move || {
        let local=std::env::var_os("LOCALAPPDATA").ok_or("diagnostics_unavailable")?;
        let root=PathBuf::from(local).join("Tacticore/desktop-runtime/exports").canonicalize().map_err(|_|"diagnostics_unavailable")?;
        let target=root.join(format!("{}.json",export_id)).canonicalize().map_err(|_|"diagnostics_unavailable")?;
        if target.parent()!=Some(root.as_path()) {return Err("diagnostics_unavailable".into());}
        let file=std::fs::File::open(target).map_err(|_|"diagnostics_unavailable")?;
        let mut bytes=Vec::new();file.take(8*1024*1024+1).read_to_end(&mut bytes).map_err(|_|"diagnostics_unavailable")?;
        if bytes.len()>8*1024*1024 {return Err("diagnostics_unavailable".into());}
        let digest=format!("{:x}",Sha256::digest(&bytes));
        if digest!=expected_sha256 {return Err("diagnostics_changed".into());}
        let content=String::from_utf8(bytes).map_err(|_|"diagnostics_unavailable")?;
        let document:Value=serde_json::from_str(&content).map_err(|_|"diagnostics_unavailable")?;
        if document.get("export_id")!=Some(&Value::String(export_id.clone()))
            || document.get("schema_version")!=Some(&Value::from(1))
            || document.get("redacted")!=Some(&Value::Bool(true))
            || document.get("kind").and_then(Value::as_str)!=Some("tacticore_redacted_diagnostics")
            || document.pointer("/redaction/credentials")!=Some(&Value::Bool(false))
            || document.pointer("/redaction/private_native_addresses")!=Some(&Value::Bool(false)) {
            return Err("diagnostics_unavailable".into());
        }
        Ok(serde_json::json!({"export_id":export_id,"sha256":digest,"bytes":content.len(),"content":content}))
    }).await.map_err(|_|"diagnostics_unavailable".to_owned())?
}

#[tauri::command]
pub async fn host_request(request: Value, bridge: tauri::State<'_, HostBridge>) -> Result<Value, String> {
    validate(&request)?;
    let state = bridge.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let mut slot = state.0.lock().map_err(|_| "bridge_unavailable")?;
        let source = match runtime_source() {
            Ok(source) => source,
            Err(error) => {
                // A missing/changed registration also invalidates the existing
                // configuration service. It must not keep stale credentials
                // or configuration alive after a failed source check.
                slot.process = None;
                return Err(error);
            }
        };
        if slot.source.as_ref().is_some_and(|old| old != &source.fingerprint) {
            slot.process = None;
            return Err("runtime_configuration_changed".into());
        }
        if slot.process.is_none() {
            slot.process = Some(ServiceProcess::spawn(&source)?);
            slot.source = Some(source.fingerprint);
        }
        let result = slot.process.as_mut().ok_or("bridge_unavailable")?.exchange(&request);
        if result.is_err() { slot.process = None; } // Never retry an uncertain delivery.
        result
    }).await.map_err(|_| "bridge_unavailable".to_owned())?
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn fixture() -> (PathBuf, serde_json::Value) {
        let root = std::env::temp_dir().join(format!("tacticore-registry-{}-{}", std::process::id(), SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()));
        std::fs::create_dir(&root).unwrap();
        let library = root.join("library.json");
        std::fs::write(&library, b"{}").unwrap();
        let record = serde_json::json!({"schema_version":1,"registration_id":"45b37922-a953-4d54-bc3b-4a34804c1c56",
            "library_path":library,"library_sha256":format!("{:x}",Sha256::digest(b"{}"))});
        (root, record)
    }

    fn write(root: &PathBuf, record: &serde_json::Value) {
        std::fs::write(root.join("desktop-runtime-config.json"), serde_json::to_vec(record).unwrap()).unwrap();
    }

    fn cleanup(root: PathBuf) {
        assert!(root.starts_with(std::env::temp_dir()));
        assert!(root.file_name().unwrap().to_string_lossy().starts_with("tacticore-registry-"));
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn explicit_registered_source_has_bound_identity_and_content() {
        let (root, record) = fixture(); write(&root, &record);
        let source = source_at(root.clone()).unwrap();
        assert_eq!(source.library, root.join("library.json"));
        assert_eq!(source.fingerprint.len(), 64);
        std::fs::write(root.join("library.json"), b"changed").unwrap();
        assert!(matches!(source_at(root.clone()), Err(code) if code == "registered_library_changed"));
        cleanup(root);
    }

    #[test]
    fn missing_duplicate_unknown_and_relative_registration_fail_closed() {
        let (root, record) = fixture();
        assert!(matches!(source_at(root.clone()), Err(code) if code == "runtime_library_unregistered"));
        let mut extra = record.clone(); extra["unknown"] = Value::Bool(true); write(&root, &extra);
        assert!(matches!(source_at(root.clone()), Err(code) if code == "runtime_configuration_invalid"));
        let mut relative = record.clone(); relative["library_path"] = Value::String("relative.json".into()); write(&root, &relative);
        assert!(matches!(source_at(root.clone()), Err(code) if code == "runtime_configuration_invalid"));
        std::fs::write(root.join("desktop-runtime-config.json"), b"{\"schema_version\":1,\"schema_version\":1}").unwrap();
        assert!(matches!(source_at(root.clone()), Err(code) if code == "runtime_configuration_invalid"));
        cleanup(root);
    }
}
