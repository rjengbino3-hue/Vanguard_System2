from flask import Blueprint, render_template, request, jsonify
from src.database import get_supabase

cameras_bp = Blueprint("cameras", __name__)


def default_device(device_id, location):
    return {
        "device_id": device_id,
        "location": location,
        "status": "offline",
        "fps": 0,
        "total_detections": 0
    }


@cameras_bp.route("/")
def index():
    try:
        supabase = get_supabase()
        response = supabase.table("devices").select("*").execute()
        device_list = response.data if response and hasattr(response, "data") else []
    except Exception as error:
        print(f"[DATABASE ERROR] Could not read device list: {error}")
        device_list = []

    devices_dict = {device["device_id"]: device for device in device_list}

    cam001 = devices_dict.get("cam001", default_device("cam001", "Lapu-lapu"))
    cam002 = devices_dict.get("cam002", default_device("cam002", "Roxas Ext."))

    total_cameras = len(device_list) if device_list else 2
    active_count = sum(
        1 for device in device_list
        if device.get("status") == "online"
    )
    offline_count = total_cameras - active_count

    return render_template(
        "cameras.html",
        cam001=cam001,
        cam002=cam002,
        total_cameras=total_cameras,
        active_count=active_count,
        offline_count=offline_count,
    )


@cameras_bp.route("/update_location", methods=["POST"])
def update_location():
    try:
        data = request.get_json()
        device_id = data.get("device_id")
        new_location = data.get("location")

        if not device_id or not new_location:
            return jsonify({"success": False, "error": "Missing parameters"}), 400

        supabase = get_supabase()
        supabase.table("devices").update(
            {"location": new_location}
        ).eq("device_id", device_id).execute()

        return jsonify({"success": True})

    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500