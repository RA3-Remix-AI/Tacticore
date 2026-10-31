fn main() {
    use sha2::{Digest, Sha256};
    println!("cargo:rerun-if-env-changed=TACTICORE_RUNTIME_MANIFEST");
    println!("cargo:rerun-if-env-changed=TACTICORE_BETA_CANDIDATE_PIN");
    let digest = match std::env::var_os("TACTICORE_RUNTIME_MANIFEST") {
        Some(path) => {
            println!("cargo:rerun-if-changed={}", std::path::Path::new(&path).display());
            let path=std::path::PathBuf::from(path);
            let bytes = std::fs::read(&path).expect("Unable to read the release companion manifest");
            let manifest: serde_json::Value = serde_json::from_slice(&bytes).expect("Invalid release companion manifest JSON");
            let files = manifest.get("files").and_then(|value| value.as_object()).expect("Release companion inventory required");
            if std::env::var("PROFILE").as_deref() == Ok("release") && files.contains_key("release-stage.json") {
                let pin=format!("{:x}",Sha256::digest(&bytes));
                let opt_in=std::env::var("TACTICORE_BETA_CANDIDATE_PIN").unwrap_or_default();
                assert_eq!(opt_in,pin,"A staging runtime requires explicit exact-pin beta candidate building.");
                let stage:serde_json::Value=serde_json::from_slice(&std::fs::read(path.parent().unwrap().join("release-stage.json")).unwrap()).unwrap();
                assert_eq!(stage["kind"],"portable_native6_field_trial_candidate");
                assert_eq!(stage["public_release_ready"],false);
                // This builds the exact installer that will be tested. Public
                // upload is separately gated on the frozen external evidence;
                // changing the runtime after those games invalidates its pin.
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
        .app_manifest(tauri_build::AppManifest::new().commands(&["host_request", "diagnostics_read", "connection_config_request","game_setup_request"])))
        .expect("Unable to generate the native RPC permission manifest");
}
