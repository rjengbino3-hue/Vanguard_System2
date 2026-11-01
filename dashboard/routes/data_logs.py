
from flask import Blueprint, render_template, request, jsonify
from src.database import get_supabase
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from dashboard.auth_utils import login_required
import logging

data_logs_bp = Blueprint("data_logs", __name__)


@data_logs_bp.route("/")
@data_logs_bp.route("")
@login_required
def index():
    # Load only the page layout. Do not retrieve violation records here.
    return render_template("data_logs.html")


@data_logs_bp.route("/data", methods=["GET"])
@login_required
def get_logs_data():
    selected_date = request.args.get("date", "").strip()

    # A date is required before any database query is performed.
    if not selected_date:
        return jsonify({
            "success": False,
            "error": "Please select a date."
        }), 400

    try:
        # Validate the date.
        date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date()
        next_date = date_obj + timedelta(days=1)

        # Use explicit UTC boundaries to preserve the existing
        # UTC calendar-date filtering behavior.
        start_timestamp = (
            f"{date_obj.isoformat()}T00:00:00+00:00"
        )
        end_timestamp = (
            f"{next_date.isoformat()}T00:00:00+00:00"
        )

        supabase = get_supabase()

        # Retrieve all records for the selected date in batches.
        # This avoids stopping at Supabase's usual 1,000-row limit.
        page_size = 500
        offset = 0
        raw_records = []

        while True:
            response = (
                supabase.table("violations")
                .select("timestamp,tracking_id,location,device_id")
                .gte("timestamp", start_timestamp)
                .lt("timestamp", end_timestamp)
                .order("timestamp", desc=True)
                .range(offset, offset + page_size - 1)
                .execute()
            )

            batch = response.data or []
            raw_records.extend(batch)

            # Stop when the returned batch is smaller than the page size.
            if len(batch) < page_size:
                break

            offset += page_size

        # Count violations by location and collect every device ID
        # associated with each location.
        hotspot_counts = Counter()
        location_device_ids = defaultdict(set)

        for log in raw_records:
            location = log.get("location")

            if location:
                hotspot_counts[location] += 1

                device_id = log.get("device_id")

                if device_id:
                    location_device_ids[location].add(str(device_id))

        # Prepare hotspot data for the frontend.
        hotspots = []

        for location, count in hotspot_counts.most_common():
            device_ids = sorted(location_device_ids[location])

            hotspots.append({
                "location": location,
                "count": count,
                "timestamp": selected_date + " 00:00:00",
                "device_id": (
                    ", ".join(device_ids) if device_ids else "N/A"
                )
            })

        return jsonify({
            "success": True,
            "logs": raw_records,
            "hotspots": hotspots
        })

    except ValueError:
        return jsonify({
            "success": False,
            "error": "Invalid date format."
        }), 400

    except Exception:
        # Keep technical error details in the server log,
        # not in the response sent to the browser.
        logging.exception("Failed to retrieve Data Logs records.")

        return jsonify({
            "success": False,
            "error": "Unable to retrieve records. Please try again."
        }), 500
