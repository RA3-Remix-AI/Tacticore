mod host_bridge;
mod runtime_package;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(host_bridge::HostBridge::default())
        .invoke_handler(tauri::generate_handler![host_bridge::host_request, host_bridge::diagnostics_read])
        .run(tauri::generate_context!())
        .expect("Unable to start the Tacticore desktop window");
}
