//! Rapport desktop shell: a thin Tauri window around the `rapport-core` sidecar.
//! The shell owns OS integration only; everything else lives in the sidecar or the web UI.

use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use tauri::{AppHandle, Manager, RunEvent, Url, WebviewWindow};

struct Core(Mutex<Option<Child>>);

/// Where the frozen backend and the built UI live: env overrides, then the app bundle, then the repo (dev).
fn locate(app: &AppHandle) -> (PathBuf, PathBuf, PathBuf) {
    let env_core = std::env::var("RAPPORT_CORE").ok().map(PathBuf::from);
    let env_ui = std::env::var("RAPPORT_UI").ok().map(PathBuf::from);
    let repo = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../..").canonicalize().unwrap_or_default();
    let bundled = app.path().resource_dir().ok();
    let core = env_core
        .or_else(|| bundled.as_ref().map(|r| r.join("core/rapport-core")).filter(|p| p.exists()))
        .unwrap_or_else(|| repo.join("desktop/sidecar/dist/rapport-core/rapport-core"));
    let ui = env_ui
        .or_else(|| bundled.as_ref().map(|r| r.join("ui")).filter(|p| p.join("index.html").exists()))
        .unwrap_or_else(|| repo.join("frontend/out"));
    // Existing users keep their library where it is; new users get ~/Rapport.
    let library = std::env::var("RAPPORT_LIBRARY").map(PathBuf::from).unwrap_or_else(|_| {
        let home = app.path().home_dir().unwrap_or_else(|_| PathBuf::from("."));
        let legacy = home.join("DJI Mic Library");
        if legacy.join("library.sqlite").exists() { legacy } else { home.join("Rapport") }
    });
    (core, ui, library)
}

fn token() -> String {
    uuid::Uuid::new_v4().simple().to_string()
}

fn set_status(win: &WebviewWindow, text: &str) {
    let _ = win.eval(&format!("window.__setStatus && window.__setStatus({})", serde_json::to_string(text).unwrap_or_default()));
}

fn start_core(app: AppHandle) {
    let win = app.get_webview_window("main").expect("main window");
    let (core, ui, library) = locate(&app);
    log::info!("core={core:?} ui={ui:?} library={library:?}");
    if !core.exists() {
        set_status(&win, "Backend not found. Build it with desktop/sidecar/build.sh.");
        log::error!("sidecar missing at {core:?}");
        return;
    }
    let tok = token();
    let mut child = match Command::new(&core)
        .args(["--port", "0", "--library"])
        .arg(&library)
        .args(["--token", &tok, "--ui"])
        .arg(&ui)
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
    {
        Ok(c) => c,
        Err(e) => {
            set_status(&win, &format!("Could not start the backend: {e}"));
            return;
        }
    };
    let stdout = child.stdout.take().expect("stdout");
    app.state::<Core>().0.lock().unwrap().replace(child);
    set_status(&win, "Loading models…");

    // Wait for `READY <port>` on the sidecar's stdout, then point the window at it.
    std::thread::spawn(move || {
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            log::info!("core: {line}");
            if let Some(port) = line.strip_prefix("READY ") {
                let url = format!("http://127.0.0.1:{}/?token={}", port.trim(), tok);
                if let Ok(u) = Url::parse(&url) {
                    let _ = win.navigate(u);
                }
                return;
            }
            if line.starts_with("FAILED") {
                set_status(&win, "The backend did not start. See the log.");
                return;
            }
        }
        set_status(&win, "The backend stopped unexpectedly.");
    });
}

fn stop_core(app: &AppHandle) {
    if let Some(mut child) = app.state::<Core>().0.lock().unwrap().take() {
        let _ = child.kill();
        let _ = child.wait();
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(Core(Mutex::new(None)))
        .plugin(tauri_plugin_log::Builder::default().level(log::LevelFilter::Info).build())
        .setup(|app| {
            start_core(app.handle().clone());
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| match event {
            RunEvent::ExitRequested { .. } | RunEvent::Exit => stop_core(app),
            _ => {}
        });
}
