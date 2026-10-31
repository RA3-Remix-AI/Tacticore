fn main() {
    use sha2::{Digest, Sha256};
    println!("cargo:rerun-if-env-changed=TACTICORE_RUNTIME_MANIFEST");
    let digest = match std::env::var_os("TACTICORE_RUNTIME_MANIFEST") {
        Some(path) => {
            println!("cargo:rerun-if-changed={}", std::path::Path::new(&path).display());
            let bytes = std::fs::read(path).expect("Unable to read the release companion manifest");
            let manifest: serde_json::Value = serde_json::from_slice(&bytes).expect("Invalid release companion manifest JSON");
            let files = manifest.get("files").and_then(|value| value.as_object()).expect("Release companion inventory required");
            if std::env::var("PROFILE").as_deref() == Ok("release") && files.contains_key("release-stage.json") {
                panic!("A Python staging artifact is not a Windows beta release runtime.");
            }
            format!("{:x}", Sha256::digest(bytes))
        }
        None => {
            if std::env::var("PROFILE").as_deref() == Ok("release") {
                panic!("Release builds require TACTICORE_RUNTIME_MANIFEST. Use the Windows release preflight and build script.");
            }
            "unavailable".into()
        },
    };
    println!("cargo:rustc-env=TACTICORE_RUNTIME_MANIFEST_SHA256={digest}");
    tauri_build::try_build(tauri_build::Attributes::new()
        .app_manifest(tauri_build::AppManifest::new().commands(&["host_request", "diagnostics_read", "connection_config_request"])))
        .expect("Unable to generate the native RPC permission manifest");
}
