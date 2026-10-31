mod host_bridge;
mod runtime_package;
mod game_setup;

pub fn prepare_update() -> bool { game_setup::maintenance() }

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(host_bridge::HostBridge::default())
        .manage(game_setup::GameSetup::default())
        .invoke_handler(tauri::generate_handler![host_bridge::host_request, host_bridge::diagnostics_read, host_bridge::connection_config_request,game_setup::game_setup_request])
        .run(tauri::generate_context!())
        .expect("Unable to start the Tacticore desktop window");
}
