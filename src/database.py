from datetime import datetime
import os
import uuid

from supabase import create_client, Client


SUPABASE_URL = os.getenv("SUPABASE_URL", "https://nlxkzfgyruwkemkxrgxu.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_secret_yjYkETP2WOAilR1chqUuxw_K-fiCNpL")



def get_supabase() -> Client:
    if not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_KEY is missing. Add it to your .env file.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def initialize_database(db_name=None):
    print("[SUPABASE] Cloud connection pipeline initialized successfully.")


def save_violation(
    device_id,
    violation_type,
    class_name,
    confidence,
    location,
    latitude=None,
    longitude=None,
    tracking_id=None,
    db_name=None,
):
    event_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()

    data_payload = {
        "event_id": event_id,
        "timestamp": timestamp,
        "device_id": device_id,
        "tracking_id": str(tracking_id) if tracking_id is not None else None,
        "violation_type": violation_type,
        "class_name": class_name,
        "confidence": float(confidence),
        "location": location,
        "latitude": latitude,
        "longitude": longitude,
        "count": 1,
    }

    try:
        supabase = get_supabase()

        supabase.table("violations").insert(data_payload).execute()

        print(
            "[SUPABASE] Violation saved online | "
            f"event_id={event_id} | "
            f"tracking_id={data_payload['tracking_id']}"
        )

        return event_id

    except Exception as error:
        print(f"[SUPABASE ERROR] Data insert operation failed: {error}")
        return None


def get_recent_violations(limit=10, db_name=None):
    try:
        supabase = get_supabase()

        response = (
            supabase.table("violations")
            .select("*")
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )

        return response.data

    except Exception as error:
        print(f"[SUPABASE ERROR] Failed to fetch violation records: {error}")
        return []


def fetch_device_cloud_config(device_id):
    try:
        supabase = get_supabase()

        response = (
            supabase.table("devices")
            .select("location")
            .eq("device_id", device_id)
            .execute()
        )

        if response and len(response.data) > 0:
            return response.data[0].get("location")

    except Exception as error:
        print(f"[SUPABASE ERROR] Failed to fetch device cloud config: {error}")

    return None


def update_device_telemetry(device_id, status="online", fps=30):
    try:
        supabase = get_supabase()

        supabase.table("devices").update(
            {
                "status": status,
                "fps": fps,
                "last_ping": datetime.now().isoformat(),
            }
        ).eq("device_id", device_id).execute()

    except Exception as error:
        print(f"[SUPABASE ERROR] Failed to update device telemetry: {error}")
