/// A window shell only. No command handler, shell/filesystem plugin, sidecar,
/// game process access, or credential storage is exposed to the WebView.
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("Unable to start the Tacticore desktop window");
}
