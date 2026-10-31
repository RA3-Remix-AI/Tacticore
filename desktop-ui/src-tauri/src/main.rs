#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    if std::env::args().any(|arg|arg=="--prepare-update") {
        std::process::exit(if tacticore_desktop_lib::prepare_update(){0}else{2});
    }
    if std::env::args().any(|arg|arg=="--version") {return;}
    tacticore_desktop_lib::run();
}
