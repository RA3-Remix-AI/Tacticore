fn main() {
    use sha2::{Digest, Sha256};
    println!("cargo:rerun-if-env-changed=TACTICORE_RUNTIME_MANIFEST");
    let digest = match std::env::var_os("TACTICORE_RUNTIME_MANIFEST") {
        Some(path) => {
            println!("cargo:rerun-if-changed={}", std::path::Path::new(&path).display());
            let bytes = std::fs::read(path).expect("Unable to read the release companion manifest");
            format!("{:x}", Sha256::digest(bytes))
        }
        None => "unavailable".into(),
    };
    println!("cargo:rustc-env=TACTICORE_RUNTIME_MANIFEST_SHA256={digest}");
    tauri_build::try_build(tauri_build::Attributes::new()
        .app_manifest(tauri_build::AppManifest::new().commands(&["host_request", "diagnostics_read", "connection_config_request"])))
        .expect("Unable to generate the native RPC permission manifest");
}
