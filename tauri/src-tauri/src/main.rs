// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use std::thread;
use tauri::{Manager, State};

/// Global state to track the Python Shadow process
struct ShadowProcessState {
    process: Arc<Mutex<Option<Child>>>,
}

/// Check if the Python Shadow dashboard is responding
async fn check_dashboard_ready(url: &str) -> bool {
    if let Ok(client) = reqwest::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
    {
        if let Ok(response) = client.get(url).send().await {
            return response.status().is_success();
        }
    }
    false
}

/// Find Python executable in the system PATH
fn find_python() -> Option<String> {
    let python_names = if cfg!(windows) {
        vec!["python.exe", "python3.exe"]
    } else {
        vec!["python3", "python"]
    };

    for name in python_names {
        if let Ok(output) = Command::new("which")
            .arg(name)
            .output()
        {
            if output.status.success() {
                if let Ok(path) = String::from_utf8(output.stdout) {
                    return Some(path.trim().to_string());
                }
            }
        }
    }
    None
}

/// Spawn the Python Shadow process
fn spawn_shadow_process() -> Result<Child, String> {
    let python = find_python()
        .ok_or("Python not found. Please install Python 3.10+ and add it to PATH.")?;

    let child = Command::new(&python)
        .arg("-m")
        .arg("shadow")
        .spawn()
        .map_err(|e| format!("Failed to start Shadow: {}", e))?;

    Ok(child)
}

/// Wait for the dashboard to become ready (with timeout)
async fn wait_for_dashboard(max_attempts: u32, delay_ms: u64) -> Result<(), String> {
    let url = "http://127.0.0.1:4747";

    for attempt in 0..max_attempts {
        if check_dashboard_ready(url).await {
            println!("Dashboard is ready!");
            return Ok(());
        }
        if attempt < max_attempts - 1 {
            println!("Waiting for dashboard... ({}/{})", attempt + 1, max_attempts);
            thread::sleep(Duration::from_millis(delay_ms));
        }
    }

    Err(format!(
        "Dashboard did not respond within {} seconds",
        (max_attempts * delay_ms as u32) / 1000
    ))
}

/// Tauri command: Get Shadow process status
#[tauri::command]
fn get_shadow_status(state: State<ShadowProcessState>) -> String {
    let process = state.process.lock().unwrap();
    if process.is_some() {
        "running".to_string()
    } else {
        "stopped".to_string()
    }
}

/// Tauri command: Restart Shadow process
#[tauri::command]
async fn restart_shadow(state: State<'_, ShadowProcessState>) -> Result<String, String> {
    // Kill existing process
    {
        let mut process = state.process.lock().unwrap();
        if let Some(mut child) = process.take() {
            let _ = child.kill();
        }
    }

    // Wait a moment for clean shutdown
    thread::sleep(Duration::from_millis(500));

    // Start new process
    let child = spawn_shadow_process()?;

    // Update state
    {
        let mut process = state.process.lock().unwrap();
        *process = Some(child);
    }

    // Wait for dashboard to be ready
    wait_for_dashboard(30, 500).await?;

    Ok("Shadow restarted successfully".to_string())
}

/// Tauri command: Get detected Python path
#[tauri::command]
fn get_python_path() -> String {
    find_python().unwrap_or_else(|| "Python not found".to_string())
}

fn main() {
    let process_state = ShadowProcessState {
        process: Arc::new(Mutex::new(None)),
    };

    tauri::Builder::default()
        .manage(process_state)
        .invoke_handler(tauri::generate_handler![
            get_shadow_status,
            restart_shadow,
            get_python_path
        ])
        .setup(|app| {
            let app_handle = app.app_handle();
            let state = app.state::<ShadowProcessState>();

            // Spawn the Python Shadow process on startup
            match spawn_shadow_process() {
                Ok(child) => {
                    let mut process = state.process.lock().unwrap();
                    *process = Some(child);
                    println!("Shadow process started (PID: spawning)");
                }
                Err(e) => {
                    eprintln!("Failed to start Shadow: {}", e);
                    eprintln!("Please ensure Shadow is installed: pip install shadow-agent");
                    // Continue anyway - user can retry via restart command
                }
            }

            // Wait for dashboard to be ready in a background task
            let app_handle_clone = app_handle.clone();
            tauri::async_runtime::spawn(async move {
                match wait_for_dashboard(60, 500).await {
                    Ok(()) => {
                        println!("Shadow dashboard is ready at http://127.0.0.1:4747");
                    }
                    Err(e) => {
                        eprintln!("Dashboard failed to start: {}", e);
                        let _ = app_handle_clone.emit_all("shadow:error", e);
                    }
                }
            });

            Ok(())
        })
        .on_window_event(|_window, event| {
            use tauri::WindowEvent;
            match event {
                WindowEvent::CloseRequested { .. } => {
                    // Let the default close behavior continue
                }
                _ => {}
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
