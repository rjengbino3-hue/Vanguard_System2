import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(PROJECT_ROOT, "config", "settings.json")
HAILO_APPS_ROOT = "/home/raspi5/hailo-apps-infra"

sys.path.append(PROJECT_ROOT)


def add_hailo_module_paths():
    hailo_root = Path(HAILO_APPS_ROOT)

    if not hailo_root.exists():
        print(f"[SYSTEM WARNING] Hailo apps root does not exist: {HAILO_APPS_ROOT}")
        return

    detection_path_found = False
    gstreamer_path_found = False

    for detection_file in hailo_root.rglob("detection_pipeline.py"):
        if detection_file.parent.name == "detection":
            sys.path.append(str(detection_file.parent.parent))
            print(f"[SYSTEM] Added Hailo detection path: {detection_file.parent.parent}")
            detection_path_found = True
            break

    for gstreamer_file in hailo_root.rglob("gstreamer_app.py"):
        if gstreamer_file.parent.name == "gstreamer":
            sys.path.append(str(gstreamer_file.parent.parent))
            print(f"[SYSTEM] Added Hailo gstreamer path: {gstreamer_file.parent.parent}")
            gstreamer_path_found = True
            break

    if not detection_path_found:
        print("[SYSTEM WARNING] Hailo detection_pipeline.py was not found.")

    if not gstreamer_path_found:
        print("[SYSTEM WARNING] Hailo gstreamer_app.py was not found.")


add_hailo_module_paths()

from detection.detection_pipeline import GStreamerDetectionApp
from gstreamer.gstreamer_app import app_callback_class

from src.database import initialize_database, update_device_telemetry
from src.pipeline import VanguardPipeline


class VanguardCallbackData(app_callback_class):
    def __init__(self, pipeline):
        super().__init__()
        self.pipeline = pipeline


def load_settings():
    with open(SETTINGS_PATH, "r", encoding="utf-8") as settings_file:
        return json.load(settings_file)


def resolve_project_path(relative_path):
    return os.path.join(PROJECT_ROOT, relative_path)


def configure_hailo_arguments(settings):
    hef_path = resolve_project_path(settings["model"]["hef_path"])
    labels_path = resolve_project_path(settings["model"]["labels_path"])
    input_source = settings["video"]["source"]

    sys.argv.extend(
        [
            "--input",
            input_source,
            "--hef-path",
            hef_path,
            "--labels-json",
            labels_path,
            "--arch",
            "hailo8l",
            "--show-fps",
        ]
    )

    print(f"[SYSTEM] HEF model loaded from: {hef_path}")
    print(f"[SYSTEM] Labels loaded from: {labels_path}")
    print(f"[SYSTEM] Input source: {input_source}")
    print("[SYSTEM] Stable motorcycle identity layer enabled in VanguardTracker.")


def app_callback(element, buffer, user_data):
    if buffer is None:
        return

    user_data.pipeline.process_hailo_buffer(buffer)


def main():
    print("\n========================================================")
    print("      VANGUARD: EDGE AI TRAFFIC MONITORING SYSTEM       ")
    print("========================================================")
    print("[SYSTEM] Booting application management layers...")

    settings = None

    try:
        settings = load_settings()
    except Exception as error:
        print(f"[CRITICAL ERROR] Failed to load settings.json: {error}")
        sys.exit(1)

    try:
        initialize_database(settings["database"]["db_name"])
    except Exception as error:
        print(f"[CRITICAL ERROR] Failed to initialize Supabase connection: {error}")
        sys.exit(1)

    try:
        print("[SYSTEM] Initializing VanGuard detection logic...")
        vanguard_pipeline = VanguardPipeline()

        print("[SYSTEM] Configuring Hailo camera inference pipeline...")
        configure_hailo_arguments(settings)

        user_data = VanguardCallbackData(vanguard_pipeline)

        print("[SYSTEM] Starting live Raspberry Pi Camera + Hailo inference...")
        print("[INFO] Press Ctrl+C in the terminal to terminate safely.\n")

        app = GStreamerDetectionApp(app_callback, user_data)
        app.run()

    except KeyboardInterrupt:
        print("\n[SYSTEM] Keyboard interrupt caught. Shutting down safely...")

    except Exception as error:
        print(f"\n[CRITICAL ERROR] Main system pipeline crashed unexpectedly: {error}")
        sys.exit(1)

    finally:
        try:
            if settings is not None:
                print("[SYSTEM] Turning off device active telemetry status...")
                update_device_telemetry(
                    settings["device"]["device_id"],
                    status="offline",
                    fps=0,
                )
        except Exception as telemetry_error:
            print(f"[SYSTEM WARNING] Failed to send offline telemetry signal: {telemetry_error}")

    print("========================================================")
    print("          VANGUARD SYSTEM SAFELY TERMINATED             ")
    print("========================================================\n")


if __name__== "__main__":
    main()
