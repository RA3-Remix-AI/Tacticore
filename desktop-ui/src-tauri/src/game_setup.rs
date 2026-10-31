//! Native owns file selections. WebView supplies only a fixed operation name.
use serde_json::{json,Value};
use std::{io::{Read,Write},path::PathBuf,process::Stdio,sync::{Arc,Mutex}};

#[derive(Default)]
struct Selection { game:Option<PathBuf>,mod_big:Option<PathBuf> }
#[derive(Default,Clone)]
pub struct GameSetup(Arc<Mutex<Selection>>);

pub(crate) fn local_home() -> Result<PathBuf,String> {
    #[cfg(windows)] {
        use windows_sys::Win32::{UI::Shell::{SHGetKnownFolderPath,FOLDERID_LocalAppData},System::Com::CoTaskMemFree};
        use std::os::windows::ffi::OsStringExt;
        let mut raw=std::ptr::null_mut();
        let status=unsafe {SHGetKnownFolderPath(&FOLDERID_LocalAppData,0,std::ptr::null_mut(),&mut raw)};
        if status<0 || raw.is_null(){return Err("local_state_unavailable".into());}
        let value=unsafe {
            let mut n=0;while *raw.add(n)!=0 && n<32768 {n+=1;}
            let value=std::ffi::OsString::from_wide(std::slice::from_raw_parts(raw,n));
            CoTaskMemFree(raw.cast());value
        };
        let home=PathBuf::from(value).join("Tacticore/beta1");
        std::fs::create_dir_all(&home).map_err(|_|"local_state_unavailable")?;
        let canonical=std::fs::canonicalize(home).map_err(|_|"local_state_unavailable")?;
        // Rust canonicalize emits the Win32 device prefix. Python/Native6
        // deliberately accept only plain drive paths in their contracts.
        let text=canonical.to_string_lossy();
        return Ok(PathBuf::from(text.strip_prefix("\\\\?\\").unwrap_or(&text)));
    }
    #[cfg(not(windows))] {Err("local_state_unavailable".into())}
}

fn pick(game:bool) -> Result<Option<PathBuf>,String> {
    #[cfg(windows)] {
        use windows_sys::Win32::UI::Controls::Dialogs::{GetOpenFileNameW,CommDlgExtendedError,OPENFILENAMEW,
            OFN_FILEMUSTEXIST,OFN_PATHMUSTEXIST,OFN_NOCHANGEDIR,OFN_EXPLORER};
        use std::os::windows::ffi::OsStringExt;
        let title:Vec<u16>=(if game {"选择 Data 目录中的 RA3_1.12.game\0"} else {"选择已有的兼容指挥官 Mod BIG 文件\0"}).encode_utf16().collect();
        let filter:Vec<u16>=(if game {"RA3 1.12 游戏文件\0RA3_1.12.game\0\0"} else {"兼容 Mod BIG 文件\0*.big\0\0"}).encode_utf16().collect();
        let mut path=[0u16;520];let mut value=OPENFILENAMEW::default();
        value.lStructSize=std::mem::size_of::<OPENFILENAMEW>() as u32;
        value.lpstrTitle=title.as_ptr();value.lpstrFilter=filter.as_ptr();value.nFilterIndex=1;
        value.lpstrFile=path.as_mut_ptr();value.nMaxFile=path.len() as u32;
        value.Flags=OFN_FILEMUSTEXIST|OFN_PATHMUSTEXIST|OFN_NOCHANGEDIR|OFN_EXPLORER;
        if unsafe {GetOpenFileNameW(&mut value)}==0 {
            if unsafe{CommDlgExtendedError()}!=0 {return Err("beta_file_dialog_failed".into());}
            return Ok(None);
        }
        let end=path.iter().position(|x|*x==0).ok_or("beta_file_dialog_failed")?;
        let selected=PathBuf::from(std::ffi::OsString::from_wide(&path[..end]));
        if !selected.is_absolute() || selected.to_string_lossy().starts_with("\\\\") {return Err("beta_file_dialog_failed".into());}
        return Ok(Some(selected));
    }
    #[cfg(not(windows))] {let _=game;Err("beta_file_dialog_failed".into())}
}

fn pipe(request:Value)->Result<Value,String> {
    let mut command=crate::host_bridge::setup_command()?;
    command.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null());
    let mut child=command.spawn().map_err(|_|"beta_setup_unavailable")?;
    let raw=serde_json::to_vec(&request).map_err(|_|"request_invalid")?;
    child.stdin.take().ok_or("beta_setup_unavailable")?.write_all(&[raw,b"\n".to_vec()].concat()).map_err(|_|"beta_setup_unavailable")?;
    let mut output=Vec::new();
    child.stdout.take().ok_or("beta_setup_unavailable")?.take(65537).read_to_end(&mut output).map_err(|_|"beta_setup_unavailable")?;
    let _=child.wait();
    if output.len()>65536 {return Err("beta_setup_unavailable".into());}
    let value:Value=serde_json::from_slice(&output).map_err(|_|"beta_setup_unavailable")?;
    if value.get("ok")==Some(&Value::Bool(true)) {Ok(value["result"].clone())}
    else {
        let code=value.pointer("/error/code").and_then(Value::as_str).unwrap_or("beta_setup_unavailable");
        if code.len()>80 || !code.bytes().all(|b|b.is_ascii_lowercase()||b.is_ascii_digit()||b==b'_'){return Err("beta_setup_unavailable".into());}
        Err(code.into())
    }
}

pub fn maintenance()->bool { pipe(json!({"operation":"guard"})).is_ok() }

#[tauri::command]
pub async fn game_setup_request(operation:String,state:tauri::State<'_,GameSetup>,bridge:tauri::State<'_,crate::host_bridge::HostBridge>)->Result<Value,String> {
    if !["select_game","select_mod","prepare","status","launch"].contains(&operation.as_str()){return Err("operation_unsupported".into());}
    let state=state.inner().clone();let bridge=bridge.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let mut chosen=state.0.lock().map_err(|_|"beta_setup_unavailable")?;
        if operation=="select_game" || operation=="select_mod" {
            let selected=pick(operation=="select_game")?;
            let cancelled=selected.is_none();
            if let Some(path)=selected {if operation=="select_game"{chosen.game=Some(path);}else{chosen.mod_big=Some(path);}}
            return Ok(json!({"game_selected":chosen.game.is_some(),"mod_selected":chosen.mod_big.is_some(),"cancelled":cancelled}));
        }
        let payload=if operation=="prepare" {
            json!({"operation":"prepare","game":chosen.game.as_ref().ok_or("beta_select_game_required")?,
                   "mod":chosen.mod_big.as_ref().ok_or("beta_select_mod_required")?})
        } else {json!({"operation":operation})};
        let result=pipe(payload)?;
        if operation=="prepare" {bridge.invalidate_setup()?;}
        Ok(result)
    }).await.map_err(|_|"beta_setup_unavailable".to_string())?
}
