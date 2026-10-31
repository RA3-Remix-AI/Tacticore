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
    "profiles.list", "profiles.get", "profiles.save", "connections.list", "session.inspect", "session.discover", "session.prepare",
    "run.resume", "run.check", "run.start", "run.status", "run.stop", "diagnostics.export",
];
const CONTROL_OPERATIONS: &[&str] = &["run.resume", "run.status", "run.stop", "diagnostics.export"];

fn configure_runtime_authority(command: &mut Command, pin: Option<&str>) {
    // A debug launcher must never inherit a release/trial grant from its
    // caller. Release supplies only the manifest pin compiled into this EXE.
    command.env_remove("TACTICORE_RUNTIME_MANIFEST_SHA256");
    if let Some(expected) = pin { command.env("TACTICORE_RUNTIME_MANIFEST_SHA256",expected); }
}

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

struct RuntimeSource { library: PathBuf, home: PathBuf, fingerprint: String, configuration: bool, control: bool }

impl RuntimeSource {
    fn module(&self) -> &'static str {
        if self.control { "host_runtime.control_only_server_v1" }
        else if self.configuration { "host_runtime.connection_config_server_v1" }
        else { "host_runtime.bridge_service" }
    }
}

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
    Ok(RuntimeSource { library: record.library_path, home, fingerprint: format!("{:x}", Sha256::digest(&bytes)), configuration: false, control: false })
}

fn control_source_at(home: PathBuf) -> Result<RuntimeSource, String> {
    if !home.is_absolute() || home.to_string_lossy().starts_with("\\\\") {
        return Err("local_state_unavailable".into());
    }
    let fingerprint=format!("control-v1:{:x}",Sha256::digest(home.to_string_lossy().as_bytes()));
    // No registration/library read or fallback: this mode has no such input.
    Ok(RuntimeSource { library: PathBuf::new(), home, fingerprint, configuration: false, control: true })
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
        Self::launch(source,companion.python,companion.integration,None,Some(env!("TACTICORE_RUNTIME_MANIFEST_SHA256")))
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
        let module=source.module();
        let bootstrap=format!("import sys,runpy;sys.prefix=sys.exec_prefix={prefix};sys.path[:0]={imports};sys.argv[0]='{module}';runpy.run_module('{module}',run_name='__main__')");
        Self::launch(source,python,integration,Some(bootstrap),None)
    }

    fn launch(source: &RuntimeSource, python: PathBuf, integration: PathBuf, bootstrap: Option<String>, runtime_pin: Option<&str>) -> Result<Self, String> {
        let mut command = Command::new(python);
        configure_runtime_authority(&mut command,runtime_pin);
        command.args(["-I", "-S", "-B"]);
        let module=source.module();
        match bootstrap {Some(code)=>{command.args(["-c",&code]);},None=>{command.args(["-m",module]);}}
        command.current_dir(integration)
            .arg("--state-dir").arg(source.home.join("desktop-runtime"))
            .stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null());
        if !source.control { command.arg("--library").arg(&source.library); }
        if source.configuration {
            command.arg("--registration").arg(source.home.join("desktop-runtime-config.json"))
                .arg("--commander-id").arg("57e668b4-4d89-43bd-bc92-0dd436f046ef");
        }
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
struct BridgeState { process: Option<ServiceProcess>, source: Option<String>, configuration: Option<ServiceProcess>, configuration_source: Option<String> }

#[derive(Default)]
struct ControlBridgeState { process: Option<ServiceProcess>, source: Option<String> }

#[derive(Clone, Default)]
pub struct HostBridge(Arc<Mutex<BridgeState>>, Arc<Mutex<ControlBridgeState>>);

fn public_id(value: Option<&Value>) -> bool {
    value.and_then(Value::as_str).is_some_and(|id| id.len()==36 && id.bytes().enumerate().all(|(i,b)| {
        if [8,13,18,23].contains(&i) {b==b'-'} else {b.is_ascii_hexdigit()&&!b.is_ascii_uppercase()}
    }))
}

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
    let args = object.get("args").and_then(Value::as_object).ok_or("request_invalid")?;
    match object.get("operation").and_then(Value::as_str) {
        Some("session.discover" | "run.resume") if !args.is_empty() => return Err("request_invalid".into()),
        Some("run.status" | "diagnostics.export") if args.len()!=1 || !public_id(args.get("run_id")) => return Err("request_invalid".into()),
        Some("run.stop") if args.len()!=2 || !public_id(args.get("run_id")) || !public_id(args.get("session_id")) => return Err("request_invalid".into()),
        Some("session.prepare") => {
            let id = args.get("candidate_id").and_then(Value::as_str).ok_or("request_invalid")?;
            if args.len() != 1 || id.len() != 36 || !id.bytes().enumerate().all(|(i,b)| {
                if [8,13,18,23].contains(&i) {b==b'-'} else {b.is_ascii_hexdigit()&&!b.is_ascii_uppercase()}
            }) { return Err("request_invalid".into()); }
        },
        _ => {},
    }
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
        let local = std::env::var_os("LOCALAPPDATA").ok_or("local_state_unavailable")?;
        dispatch_host_at(&state, &request, PathBuf::from(local).join("Tacticore"))
    }).await.map_err(|_| "bridge_unavailable".to_owned())?
}

fn dispatch_host_at(state: &HostBridge, request: &Value, home: PathBuf) -> Result<Value, String> {
        validate(request)?;
        if request.get("operation").and_then(Value::as_str).is_some_and(|op| CONTROL_OPERATIONS.contains(&op)) {
            // STOP/status cannot queue behind a stalled configuration exchange.
            let mut slot=state.1.lock().map_err(|_|"bridge_unavailable")?;
            let source=control_source_at(home)?;
            if slot.source.as_ref().is_some_and(|old| old!=&source.fingerprint) {slot.process=None;}
            if slot.process.is_none() {
                slot.process=Some(ServiceProcess::spawn(&source)?);slot.source=Some(source.fingerprint);
            }
            let result=slot.process.as_mut().ok_or("bridge_unavailable")?.exchange(request);
            if result.is_err() {slot.process=None;} // Unknown is never replayed.
            return result;
        }
        let mut slot = state.0.lock().map_err(|_| "bridge_unavailable")?;
        let source = match source_at(home) {
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
        let result = slot.process.as_mut().ok_or("bridge_unavailable")?.exchange(request);
        if result.is_err() { slot.process = None; } // Never retry an uncertain delivery.
        result
}


// Independent configuration source selection never admits a game Host. It may
// open the old registered library identity so the signed transaction service
// can reconcile an interrupted hash update. Ordinary source_at stays strict.
fn configuration_source_at(home: PathBuf) -> Result<RuntimeSource, String> {
    let config=home.join("desktop-runtime-config.json");
    if !config.exists() {
        return Ok(RuntimeSource {library:home.join("library.v2.json"),home,fingerprint:"first-use-v1".into(),configuration:true,control:false});
    }
    let file=std::fs::File::open(config).map_err(|_|"runtime_configuration_invalid")?;
    let mut bytes=Vec::new();file.take(16385).read_to_end(&mut bytes).map_err(|_|"runtime_configuration_invalid")?;
    if bytes.len()>16384 {return Err("runtime_configuration_invalid".into());}
    let record:RuntimeRegistration=serde_json::from_slice(&bytes).map_err(|_|"runtime_configuration_invalid")?;
    let id=record.registration_id.as_bytes();
    if record.schema_version!=1 || id.len()!=36 || !id.iter().enumerate().all(|(i,b)| {
        if [8,13,18,23].contains(&i) {*b==b'-'} else {b.is_ascii_hexdigit()&&!b.is_ascii_uppercase()}
    }) || !record.library_path.is_absolute() || record.library_path.to_string_lossy().starts_with("\\\\")
      || record.library_sha256.len()!=64 || !record.library_sha256.bytes().all(|b|b.is_ascii_hexdigit()&&!b.is_ascii_uppercase()) {
        return Err("runtime_configuration_invalid".into());
    }
    Ok(RuntimeSource {library:record.library_path,home,fingerprint:format!("{:x}",Sha256::digest(&bytes)),configuration:true,control:false})
}

fn validate_configuration(request:&Value)->Result<(),String> {
    let object=request.as_object().ok_or("request_invalid")?;
    let operations=["connections.configuration","connections.configure","connections.recover","connections.cleanup_retired","connections.bootstrap"];
    if object.len()!=4 || request.get("schema_version")!=Some(&Value::from(1))
      || !request.get("args").is_some_and(Value::is_object)
      || !request.get("operation").and_then(Value::as_str).is_some_and(|v|operations.contains(&v))
      || serde_json::to_vec(request).map_err(|_|"request_invalid")?.len()>16384 {return Err("request_invalid".into());}
    let id=request.get("request_id").and_then(Value::as_str).ok_or("request_invalid")?;
    if id.len()!=36 || !id.bytes().enumerate().all(|(i,b)|if [8,13,18,23].contains(&i){b==b'-'}else{b.is_ascii_hexdigit()&&!b.is_ascii_uppercase()}) {
        return Err("request_invalid".into());
    }
    Ok(())
}

#[tauri::command]
pub async fn connection_config_request(request:Value,bridge:tauri::State<'_,HostBridge>)->Result<Value,String> {
    validate_configuration(&request)?;
    let state=bridge.inner().clone();
    tauri::async_runtime::spawn_blocking(move|| {
        let mut slot=state.0.lock().map_err(|_|"bridge_unavailable")?;
        let local=std::env::var_os("LOCALAPPDATA").ok_or("local_state_unavailable")?;
        let source=configuration_source_at(PathBuf::from(local).join("Tacticore"))?;
        if slot.configuration_source.as_ref().is_some_and(|old|old!=&source.fingerprint) {slot.configuration=None;}
        if slot.configuration.is_none() {
            slot.configuration=Some(ServiceProcess::spawn(&source)?);
            slot.configuration_source=Some(source.fingerprint);
        }
        let result=slot.configuration.as_mut().ok_or("bridge_unavailable")?.exchange(&request);
        if result.is_err(){slot.configuration=None;}
        if result.as_ref().is_ok_and(|value|value.get("ok")==Some(&Value::Bool(true)))
          && matches!(request.get("operation").and_then(Value::as_str),Some("connections.configure"|"connections.recover"|"connections.bootstrap")) {
            // Successful mutation invalidates old profile/readiness observations.
            // This stops only the configuration pipe; it never kills a game Host.
            slot.process=None;slot.source=None;slot.configuration=None;slot.configuration_source=None;
        }
        result
    }).await.map_err(|_|"bridge_unavailable".to_owned())?
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn runtime_authority_is_supplied_by_native_release_and_removed_in_debug() {
        let mut debug = Command::new("python.exe");
        configure_runtime_authority(&mut debug,None);
        assert!(debug.get_envs().any(|(key,value)|key=="TACTICORE_RUNTIME_MANIFEST_SHA256" && value.is_none()));
        let mut release = Command::new("python.exe");
        configure_runtime_authority(&mut release,Some("compiled-pin"));
        assert!(release.get_envs().any(|(key,value)|key=="TACTICORE_RUNTIME_MANIFEST_SHA256" && value==Some(std::ffi::OsStr::new("compiled-pin"))));
    }
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
    fn discovery_and_resume_are_named_bounded_operations() {
        for operation in ["session.discover", "run.resume"] {
            let request = serde_json::json!({"schema_version":1,"request_id":"45b37922-a953-4d54-bc3b-4a34804c1c56",
                                            "operation":operation,"args":{}});
            assert!(validate(&request).is_ok());
            let mut invalid=request.clone();invalid["args"]["pid"]=Value::from(123);
            assert!(validate(&invalid).is_err());
        }
    }

    #[test]
    fn prepare_accepts_opaque_candidate_only_and_never_a_path_or_pid() {
        let request = serde_json::json!({"schema_version":1,"request_id":"45b37922-a953-4d54-bc3b-4a34804c1c56",
            "operation":"session.prepare","args":{"candidate_id":"45b37922-a953-4d54-bc3b-4a34804c1c56"}});
        assert!(validate(&request).is_ok());
        let mut invalid=request.clone();invalid["args"]["path"]=Value::from("C:/private");
        assert!(validate(&invalid).is_err());
        let mut invalid=request.clone();invalid["args"]["candidate_id"]=Value::from("arbitrary");
        assert!(validate(&invalid).is_err());
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

    #[test]
    fn configuration_channel_is_bounded_and_never_accepts_game_operations() {
        let mut request=serde_json::json!({"schema_version":1,"request_id":"11111111-1111-4111-8111-111111111111","operation":"connections.configuration","args":{}});
        assert!(validate_configuration(&request).is_ok());
        for operation in ["run.start","run.stop","run.check","model.call"] {
            request["operation"]=Value::String(operation.into());assert!(validate_configuration(&request).is_err());
        }
        request["operation"]=Value::String("connections.configure".into());
        request["args"]=serde_json::json!({"api_key":"x".repeat(16384)});
        assert!(validate_configuration(&request).is_err());
    }

    #[test]
    fn recovery_source_selection_does_not_relax_ordinary_host_source_validation() {
        let (root,record)=fixture();write(&root,&record);
        std::fs::write(root.join("library.json"),b"interrupted library hash update").unwrap();
        assert!(source_at(root.clone()).is_err());
        let source=configuration_source_at(root.clone()).unwrap();
        assert!(source.configuration);assert_eq!(source.library,root.join("library.json"));
        cleanup(root);
    }

    #[test]
    fn first_use_configuration_paths_are_native_fixed_and_relative_registration_is_rejected() {
        let (root,record)=fixture();
        let source=configuration_source_at(root.clone()).unwrap();
        assert_eq!(source.library,root.join("library.v2.json"));assert!(source.configuration);
        let mut invalid=record.clone();invalid["library_path"]=Value::String("relative.json".into());write(&root,&invalid);
        assert!(configuration_source_at(root.clone()).is_err());cleanup(root);
    }

    fn control_fixture() -> PathBuf {
        let base=PathBuf::from("D:/CodexScratch/tacticore-control-only-channel-20261029-v1/rust-tests");
        std::fs::create_dir_all(&base).unwrap();
        let root=base.join(format!("control-{}-{}",std::process::id(),SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()));
        std::fs::create_dir(&root).unwrap();root
    }

    fn cleanup_control(root: PathBuf) {
        assert!(root.starts_with("D:/CodexScratch/tacticore-control-only-channel-20261029-v1/rust-tests"));
        assert!(root.file_name().unwrap().to_string_lossy().starts_with("control-"));
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn real_control_dispatch_survives_cold_broken_registration_without_creating_ledgers() {
        let root=control_fixture();
        std::fs::write(root.join("desktop-runtime-config.json"),b"broken registry").unwrap();
        assert!(source_at(root.clone()).is_err());
        let bridge=HostBridge::default();
        for op in CONTROL_OPERATIONS {
            let args=match *op {
                "run.resume"=>serde_json::json!({}),
                "run.stop"=>serde_json::json!({"run_id":"11111111-1111-4111-8111-111111111111","session_id":"22222222-2222-4222-8222-222222222222"}),
                _=>serde_json::json!({"run_id":"11111111-1111-4111-8111-111111111111"}),
            };
            let request=serde_json::json!({"schema_version":1,"request_id":"33333333-3333-4333-8333-333333333333","operation":op,"args":args});
            let result=dispatch_host_at(&bridge,&request,root.clone()).unwrap();
            if *op=="run.resume" {
                assert_eq!(result["ok"],true);assert!(result["result"]["run"].is_null());
            } else {assert_eq!(result["error"]["code"],"run_not_found");}
        }
        assert!(!root.join("desktop-runtime").exists());
        drop(bridge);cleanup_control(root);
    }

    #[test]
    fn control_dispatch_does_not_wait_for_ordinary_configuration_mutex() {
        let root=control_fixture();let bridge=HostBridge::default();
        let held=bridge.0.lock().unwrap();
        let copied=bridge.clone();let home=root.clone();let(tx,rx)=mpsc::channel();
        let worker=std::thread::spawn(move|| {
            let request=serde_json::json!({"schema_version":1,"request_id":"33333333-3333-4333-8333-333333333333","operation":"run.resume","args":{}});
            tx.send(dispatch_host_at(&copied,&request,home)).unwrap();
        });
        let result=rx.recv_timeout(Duration::from_secs(8)).expect("control queued behind ordinary/configuration lock").unwrap();
        assert_eq!(result["ok"],true);
        drop(held);worker.join().unwrap();drop(bridge);cleanup_control(root);
    }

    #[test]
    fn control_route_never_relaxes_normal_admission_or_accepts_path_pid_arguments() {
        let (root,record)=fixture();write(&root,&record);
        std::fs::write(root.join("library.json"),b"prepared new library, old registry").unwrap();
        let bridge=HostBridge::default();
        for operation in ["run.check","run.start","profiles.list","profiles.save","session.inspect"] {
            let request=serde_json::json!({"schema_version":1,"request_id":"33333333-3333-4333-8333-333333333333","operation":operation,"args":{}});
            assert!(matches!(dispatch_host_at(&bridge,&request,root.clone()),Err(code) if code=="registered_library_changed"));
        }
        for operation in CONTROL_OPERATIONS {
            let request=serde_json::json!({"schema_version":1,"request_id":"33333333-3333-4333-8333-333333333333","operation":operation,"args":{"path":"C:/outside","pid":123}});
            assert!(validate(&request).is_err());
        }
        let source=control_source_at(root.clone()).unwrap();
        assert!(source.control&&!source.configuration&&source.library.as_os_str().is_empty());
        assert_eq!(source.module(),"host_runtime.control_only_server_v1");
        assert!(control_source_at(PathBuf::from("relative")).is_err());
        cleanup(root);
    }

}
