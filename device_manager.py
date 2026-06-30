import json
import os
import signal
import subprocess
import time

from src.database import (
    fetch_device_control_states,
    clear_system_command,
    update_device_telemetry,
    update_camera_runtime_state,
)

PROJECT_ROOT = "/home/raspi5/VANGUARD_SYSTEM"
SETTINGS_PATH = os.path.join(PROJECT_ROOT, "config", "settings.json")
HAILO_ROOT = "/home/raspi5/hailo-apps-infra"
PYTHON_BIN = "/home/raspi5/hailo-apps-infra/venv_hailo_apps/bin/python"
MAIN_SCRIPT = "/home/raspi5/VANGUARD_SYSTEM/main.py"

POLL_SECONDS = 3
STOP_TIMEOUT_SECONDS = 10

with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
    settings = json.load(f)

DEVICE_ID = settings["device"]["device_id"]
camera_process = None


def log(message):
    print(message, flush=True)


def main_is_running():
    checks = [
        ["pgrep", "-f", MAIN_SCRIPT],
        ["pgrep", "-f", "python main.py"],
        ["pgrep", "-f", "python3 main.py"],
    ]

    for command in checks:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            return True

    return False


def start_ai():
    global camera_process

    if main_is_running():
        log("[MANAGER] main.py is already running. Not starting another copy.")
        update_camera_runtime_state(DEVICE_ID, "running")
        update_device_telemetry(DEVICE_ID, status="online", fps=0)
        return

    log("[MANAGER] Cloud Signal: ON. Starting main.py...")

    command = (
        f"cd {HAILO_ROOT} && "
        "source setup_env.sh && "
        f"cd {PROJECT_ROOT} && "
        f"exec {PYTHON_BIN} {MAIN_SCRIPT}"
    )

    camera_process = subprocess.Popen(
        ["/bin/bash", "-lc", command],
        cwd=PROJECT_ROOT,
        start_new_session=True,
    )

    time.sleep(4)

    if main_is_running():
        log("[MANAGER] Hailo Pipeline confirmed RUNNING.")
        update_camera_runtime_state(DEVICE_ID, "running")
        update_device_telemetry(DEVICE_ID, status="online", fps=0)
    else:
        log("[MANAGER ERROR] main.py failed to start.")
        update_camera_runtime_state(DEVICE_ID, "failed_to_start")


def stop_ai():
    global camera_process

    log("[MANAGER] Cloud Signal: OFF. Stopping main.py...")

    if camera_process is not None and camera_process.poll() is None:
        try:
            os.killpg(camera_process.pid, signal.SIGTERM)
            camera_process.wait(timeout=STOP_TIMEOUT_SECONDS)
        except Exception:
            try:
                os.killpg(camera_process.pid, signal.SIGKILL)
            except Exception:
                pass

    subprocess.run(["pkill", "-f", MAIN_SCRIPT])
    subprocess.run(["pkill", "-f", "python main.py"])
    subprocess.run(["pkill", "-f", "python3 main.py"])

    time.sleep(2)
    camera_process = None

    if main_is_running():
        log("[MANAGER ERROR] main.py is still running after stop.")
        update_camera_runtime_state(DEVICE_ID, "failed_to_stop")
    else:
        log("[MANAGER] Hailo Pipeline confirmed STOPPED.")
        update_camera_runtime_state(DEVICE_ID, "stopped")
        update_device_telemetry(DEVICE_ID, status="online", fps=0)


log(f"[MANAGER] Vanguard Manager started for device_id={DEVICE_ID}")
update_device_telemetry(DEVICE_ID, status="online", fps=0)

while True:
    try:
        control = fetch_device_control_states(DEVICE_ID)
        camera_status = control.get("camera_status", "off")
        system_command = control.get("system_command")

        log(f"[MANAGER DEBUG] control={control}")

        if system_command == "reboot":
            clear_system_command(DEVICE_ID)
            stop_ai()
            subprocess.run(["sudo", "reboot"])

        elif system_command == "poweroff":
            clear_system_command(DEVICE_ID)
            stop_ai()
            update_device_telemetry(DEVICE_ID, status="offline", fps=0)
            subprocess.run(["sudo", "poweroff"])

        elif camera_status == "on":
            start_ai()

        elif camera_status == "off":
            stop_ai()

    except Exception as error:
        log(f"[MANAGER ERROR] {error}")

    time.sleep(POLL_SECONDS)